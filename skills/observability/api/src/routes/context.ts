import type { FastifyInstance } from 'fastify';
import * as path from 'node:path';
import { readRegistry } from '../registry.js';
import { readStateJson } from '../readers/stateJson.js';
import {
  openEffortDb,
  queryWaypoints,
  queryEffortSummary,
  queryMisses,
} from '../readers/effortDb.js';
import { readResolverState, type ResolverStateDoc } from '../readers/resolverState.js';
import { parseStoryFrontmatter } from '../parsers/storyFrontmatter.js';

// ---------------------------------------------------------------------------
// Threshold definitions
// ---------------------------------------------------------------------------

interface ThresholdDef {
  name: string;
  stateKey: string | null;
  default: number;
  editable_via: string | null;
  phase2_writable: boolean;
  source_override?: string; // used for flex_factor
  provenance?: string; // human-readable origin label (OBS-003)
}

const THRESHOLD_DEFS: ThresholdDef[] = [
  {
    name: 'context_budget_threshold',
    stateKey: 'context_budget_threshold',
    default: 120000,
    editable_via: 'flex_build.py set-context-tokens',
    phase2_writable: true,
  },
  {
    name: 'context_budget_overrun_pct',
    stateKey: 'context_budget_overrun_pct',
    default: 0.10,
    editable_via: null,
    phase2_writable: true,
  },
  {
    name: 'expected_step_tokens',
    stateKey: 'expected_step_tokens',
    default: 5000,
    editable_via: null,
    phase2_writable: false,
    provenance: 'thin-harness return-block growth',
  },
  {
    name: 'context_budget_reprompt_margin',
    stateKey: 'context_budget_reprompt_margin',
    default: 10000,
    editable_via: null,
    phase2_writable: true,
  },
  {
    name: 'context_current_tokens_ttl_minutes',
    stateKey: 'context_current_tokens_ttl_minutes',
    default: 60,
    editable_via: null,
    phase2_writable: false,
  },
  {
    name: 'flex_factor',
    stateKey: null,
    default: 1.0,
    editable_via: 'hand-edit story file',
    phase2_writable: true,
    source_override: 'story-frontmatter',
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
}

interface CurrentOut {
  tokens: number | null;
  recorded_at: string | null;
  age_seconds: number | null;
  stale: boolean;
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
  misses: ReturnType<typeof queryMisses>;
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
const CACHE_TTL_MS = 2000;

// ---------------------------------------------------------------------------
// Build the context payload for one repo
// ---------------------------------------------------------------------------

function buildCurrentField(
  state: Record<string, unknown>,
  ttlMinutes: number,
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
        stale = age_seconds > ttlMinutes * 60;
      }
    } catch {
      // Unparseable timestamp — leave age_seconds null, stale false
    }
  }

  // story_id and phase from resolver state position (OBS-002: replaced orchestrator-signal reads)
  const story_id = resolverState?.position.next_story_id ?? null;
  const phase = resolverState?.position.active_phase_file ?? null;

  return { tokens, recorded_at, age_seconds, stale, story_id, phase };
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

  // 2. Derive TTL (for staleness check)
  const ttlMinutes =
    typeof state['context_current_tokens_ttl_minutes'] === 'number'
      ? state['context_current_tokens_ttl_minutes']
      : 60;

  // 3. Read resolver state first (used for current field position)
  const resolver_state = readResolverState(projectDir);

  // 4. Build current field from token state + resolver position
  const current = buildCurrentField(state, ttlMinutes, resolver_state);

  // 5. Build thresholds (async — reads story frontmatter for flex_factor)
  const thresholds = await buildThresholds(projectDir, state);

  // 6. Determine context_budget_threshold value for waypoints/misses queries
  const thresholdValue =
    thresholds.find((t) => t.name === 'context_budget_threshold')?.value ?? 120000;

  // 7. Open effort.db
  const dbPath = path.join(projectDir, '.companion', 'effort.db');
  const db = openEffortDb(dbPath);

  let waypoints: ReturnType<typeof queryWaypoints> = [];
  let effort_summary: ReturnType<typeof queryEffortSummary> = {
    total_attempts: 0,
    by_phase: [],
  };
  let misses: ReturnType<typeof queryMisses> = { count: 0, entries: [] };

  if (db !== null) {
    try {
      waypoints = queryWaypoints(db, thresholdValue);
      effort_summary = queryEffortSummary(db);
      misses = queryMisses(db, thresholdValue);
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
    misses,
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

    const data = await buildContextPayload(repo.project_dir, id);

    cache.set(id, { ts: now, data });

    reply.header('Content-Type', 'application/json');
    return data;
  });
}
