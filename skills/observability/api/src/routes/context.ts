import type { FastifyInstance } from 'fastify';
import * as path from 'node:path';
import { readRegistry } from '../registry.js';
import { readStateJson } from '../readers/stateJson.js';
import {
  openEffortDb,
  queryWaypoints,
  queryEffortSummary,
  querySpendOutliers,
} from '../readers/effortDb.js';
import { readResolverState, type ResolverStateDoc } from '../readers/resolverState.js';
import { parseStoryFrontmatter } from '../parsers/storyFrontmatter.js';

// ---------------------------------------------------------------------------
// Threshold definitions
// ---------------------------------------------------------------------------

// INFRA-321 § E1: every threshold carries an explicit track. This must never
// be inferred from the name alone — 'orchestrator-window' is the only track a
// pause/headroom judgment may be computed from; 'story-spend' is
// informational (retrospective subagent cost).
type Track = 'orchestrator-window' | 'story-spend';

interface ThresholdDef {
  name: string;
  stateKey: string | null;
  default: number;
  editable_via: string | null;
  phase2_writable: boolean;
  track: Track;
  source_override?: string; // used for flex_factor
  provenance?: string; // human-readable origin label (OBS-003)
}

const THRESHOLD_DEFS: ThresholdDef[] = [
  {
    name: 'context_budget_threshold',
    stateKey: 'context_budget_threshold',
    default: 120000,
    // INFRA-321 § E2: 'flex_build.py set-context-tokens' was false —
    // that command writes the *current count*, not this threshold. No
    // dedicated write path exists for this key today.
    editable_via: null,
    phase2_writable: true,
    track: 'orchestrator-window',
  },
  {
    name: 'context_budget_overrun_pct',
    stateKey: 'context_budget_overrun_pct',
    default: 0.10,
    editable_via: null,
    phase2_writable: true,
    track: 'orchestrator-window',
  },
  {
    name: 'expected_step_tokens',
    stateKey: 'expected_step_tokens',
    default: 5000,
    editable_via: null,
    phase2_writable: false,
    provenance: 'thin-harness return-block growth',
    track: 'orchestrator-window',
  },
  {
    name: 'context_budget_reprompt_margin',
    stateKey: 'context_budget_reprompt_margin',
    default: 10000,
    editable_via: null,
    phase2_writable: true,
    track: 'orchestrator-window',
  },
  {
    name: 'flex_factor',
    stateKey: null,
    default: 1.0,
    editable_via: 'hand-edit story file',
    phase2_writable: true,
    source_override: 'story-frontmatter',
    track: 'orchestrator-window',
  },
  {
    // INFRA-321 § A3/E1: the dedicated story-spend threshold. Never falls
    // back to context_budget_threshold when absent — the source field below
    // (`state.json` vs `default`) makes that visible rather than silent.
    name: 'story_spend_threshold',
    stateKey: 'story_spend_threshold',
    default: 120000,
    editable_via: null,
    phase2_writable: true,
    track: 'story-spend',
  },
];

// ---------------------------------------------------------------------------
// Output shapes
// ---------------------------------------------------------------------------

interface ThresholdOut {
  name: string;
  value: number;
  default: number;
  source: string;
  editable_via: string | null;
  phase2_writable: boolean;
  provenance: string | null;
  track: Track;
}

interface CurrentOut {
  tokens: number | null;
  recorded_at: string | null;
  age_seconds: number | null;
  stale: boolean;
  gate_stale: boolean;
  story_id: string | null;
  phase: string | null;
}

interface ContextOut {
  repo_id: string;
  generated_at: string;
  current: CurrentOut;
  thresholds: ThresholdOut[];
  waypoints: ReturnType<typeof queryWaypoints>;
  effort_summary: ReturnType<typeof queryEffortSummary>;
  spend_outliers: ReturnType<typeof querySpendOutliers>;
  resolver_state: ResolverStateDoc | null;
}

// ---------------------------------------------------------------------------
// In-process cache (2-second TTL per repo_id)
// ---------------------------------------------------------------------------

interface CacheEntry {
  ts: number;
  data: ContextOut;
}

const cache = new Map<string, CacheEntry>();
const inflight = new Map<string, Promise<ContextOut>>();
const CACHE_TTL_MS = 2000;

// Display-staleness heuristic ("is this number old?") for the SPA's `stale`
// badge — CER-045/CER-054's resolution note leans on this badge existing to
// distinguish a genuinely idle project from a broken writer. It is
// deliberately NOT the gate's own rule: the gate
// (`context_budget._is_stale`, Python) compares
// `context_current_tokens_recorded_at` against `context_session_reset_at`
// (a session-invalidation anchor), which this route has no way to evaluate
// client-side without duplicating that logic — see `gate_stale` below,
// which does duplicate it, for the field that answers the gate's actual
// question. CER-041 (INFRA-272): this used to be sourced from a per-project
// state.json TTL key that no code ever actually read for a decision; it is
// now a fixed, named local rather than a state-tunable knob (see
// `docs/architecture.md`'s state-key reference for that key's retirement).
const DISPLAY_STALE_SECONDS = 3600;

// ---------------------------------------------------------------------------
// Build the context payload for one repo
// ---------------------------------------------------------------------------

/**
 * gate_stale mirrors context_budget._is_stale()'s verdict exactly:
 * false when context_session_reset_at is absent or either timestamp is
 * unparseable (fail-open, same as the Python gate); true when
 * context_current_tokens_recorded_at is absent while context_session_reset_at
 * is present; otherwise recorded < reset.
 */
function computeGateStale(state: Record<string, unknown>): boolean {
  const resetAt = state['context_session_reset_at'];
  if (typeof resetAt !== 'string' || !resetAt) {
    return false;
  }
  const recordedAt = state['context_current_tokens_recorded_at'];
  if (typeof recordedAt !== 'string' || !recordedAt) {
    return true;
  }
  const resetMs = new Date(resetAt).getTime();
  const recordedMs = new Date(recordedAt).getTime();
  if (!Number.isFinite(resetMs) || !Number.isFinite(recordedMs)) {
    return false;
  }
  return recordedMs < resetMs;
}

function buildCurrentField(
  state: Record<string, unknown>,
  resolverState: ResolverStateDoc | null,
): CurrentOut {
  const tokens =
    typeof state['context_current_tokens'] === 'number' &&
    (state['context_current_tokens'] as number) > 0
      ? state['context_current_tokens']
      : null;

  const recorded_at =
    typeof state['context_current_tokens_recorded_at'] === 'string'
      ? state['context_current_tokens_recorded_at']
      : null;

  let age_seconds: number | null = null;
  let stale = false;

  if (recorded_at !== null) {
    try {
      const recordedMs = new Date(recorded_at).getTime();
      if (Number.isFinite(recordedMs)) {
        age_seconds = Math.floor((Date.now() - recordedMs) / 1000);
        stale = age_seconds > DISPLAY_STALE_SECONDS;
      }
    } catch {
      // Unparseable timestamp — leave age_seconds null, stale false
    }
  }

  const gate_stale = computeGateStale(state);

  // story_id and phase from resolver state position (OBS-002: replaced orchestrator-signal reads)
  const story_id = resolverState?.position.next_story_id ?? null;
  const phase = resolverState?.position.active_phase_file ?? null;

  return { tokens, recorded_at, age_seconds, stale, gate_stale, story_id, phase };
}

async function buildThresholds(
  projectDir: string,
  stateObj: Record<string, unknown>,
): Promise<ThresholdOut[]> {
  // Resolve flex_factor from current story frontmatter (INFRA-166 fix 2)
  let flexFactorValue = 1.0;
  let flexFactorSource = 'default';

  const currentStory = stateObj['current_story'];
  if (currentStory && typeof currentStory === 'object') {
    const cs = currentStory as Record<string, unknown>;
    const id = cs['id'];
    const rail = cs['rail'];
    if (typeof id === 'string' && typeof rail === 'string') {
      const relPath = `docs/stories/${rail}/${id}.md`;
      try {
        const fm = await parseStoryFrontmatter(projectDir, relPath);
        if (fm && fm !== 'missing') {
          flexFactorValue = fm.flex_factor;
          flexFactorSource = 'story-frontmatter';
        }
      } catch {
        flexFactorValue = 1.0;
        flexFactorSource = 'story-frontmatter (fallback)';
      }
    }
  }

  return THRESHOLD_DEFS.map((def) => {
    if (def.source_override) {
      // flex_factor — live read from story frontmatter (INFRA-166)
      return {
        name: def.name,
        value: flexFactorValue,
        default: def.default,
        source: flexFactorSource,
        editable_via: def.editable_via,
        phase2_writable: def.phase2_writable,
        provenance: def.provenance ?? null,
        track: def.track,
      };
    }

    const stateKey = def.stateKey!;
    const hasKey = Object.prototype.hasOwnProperty.call(stateObj, stateKey);
    const rawValue = stateObj[stateKey];
    // NaN guard: typeof NaN === 'number', so check explicitly (INFRA-166 fix 4)
    const value =
      typeof rawValue === 'number' && !Number.isNaN(rawValue)
        ? rawValue
        : def.default;
    const source = hasKey ? 'state.json' : 'default';

    return {
      name: def.name,
      value,
      default: def.default,
      source,
      editable_via: def.editable_via,
      phase2_writable: def.phase2_writable,
      provenance: def.provenance ?? null,
      track: def.track,
    };
  });
}

async function buildContextPayload(
  projectDir: string,
  repoId: string,
): Promise<ContextOut> {
  const generated_at = new Date().toISOString();

  // 1. Read state.json
  const state = await readStateJson(projectDir);

  // 2. Read resolver state first (used for current field position)
  const resolver_state = readResolverState(projectDir);

  // 3. Build current field from token state + resolver position
  const current = buildCurrentField(state, resolver_state);

  // 4. Build thresholds (async — reads story frontmatter for flex_factor)
  const thresholds = await buildThresholds(projectDir, state);

  // 5. Determine the STORY-SPEND threshold for waypoints/spend-outliers
  //    queries (INFRA-321 § E3) — never the orchestrator-window
  //    context_budget_threshold. story_spend_threshold's own default (above)
  //    already covers the "absent from state.json" case.
  const spendThresholdValue =
    thresholds.find((t) => t.name === 'story_spend_threshold')?.value ?? 120000;

  // 6. Open effort.db
  const dbPath = path.join(projectDir, '.companion', 'effort.db');
  const db = openEffortDb(dbPath);

  let waypoints: ReturnType<typeof queryWaypoints> = [];
  let effort_summary: ReturnType<typeof queryEffortSummary> = {
    total_attempts: 0,
    by_phase: [],
  };
  let spend_outliers: ReturnType<typeof querySpendOutliers> = { count: 0, entries: [] };

  if (db !== null) {
    try {
      waypoints = queryWaypoints(db, spendThresholdValue);
      effort_summary = queryEffortSummary(db);
      spend_outliers = querySpendOutliers(db, spendThresholdValue);
    } finally {
      db.close();
    }
  }

  return {
    repo_id: repoId,
    generated_at,
    current,
    thresholds,
    waypoints,
    effort_summary,
    spend_outliers,
    resolver_state,
  };
}

// ---------------------------------------------------------------------------
// Route registration
// ---------------------------------------------------------------------------

export async function registerContextRoutes(app: FastifyInstance): Promise<void> {
  app.get<{ Params: { id: string } }>('/api/repos/:id/context', async (request, reply) => {
    const { id } = request.params;

    // Resolve repo in registry
    const registry = await readRegistry();
    const repo = registry.repos.find((r) => r.id === id);

    if (!repo) {
      reply.code(404).header('Content-Type', 'application/json');
      return { error: 'repo not found', id };
    }

    // Check cache
    const now = Date.now();
    const cached = cache.get(id);
    if (cached && now - cached.ts < CACHE_TTL_MS) {
      reply.header('Content-Type', 'application/json');
      return cached.data;
    }

    // In-flight dedup: concurrent misses share one build promise
    const existing = inflight.get(id);
    if (existing) return existing;

    const promise = buildContextPayload(repo.project_dir, id)
      .then((data) => {
        cache.set(id, { ts: Date.now(), data });
        inflight.delete(id);
        return data;
      })
      .catch((err) => {
        inflight.delete(id);
        throw err;
      });

    inflight.set(id, promise);
    return promise;
  });
}
