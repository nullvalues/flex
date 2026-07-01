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
    default: 53000,
    editable_via: 'flex_build.py refresh-effort-baseline',
    phase2_writable: true,
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

function buildCurrentField(state: Record<string, unknown>, ttlMinutes: number): CurrentOut {
  const tokens =
    typeof state['context_current_tokens'] === 'number'
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

  // story_id from current_story
  let story_id: string | null = null;
  const currentStory = state['current_story'];
  if (currentStory !== null && typeof currentStory === 'object' && !Array.isArray(currentStory)) {
    const cs = currentStory as Record<string, unknown>;
    if (typeof cs['id'] === 'string') story_id = cs['id'];
  }

  // phase from current_phase
  const phase =
    typeof state['current_phase'] === 'string' ? state['current_phase'] : null;

  return { tokens, recorded_at, age_seconds, stale, story_id, phase };
}

function buildThresholds(state: Record<string, unknown>): ThresholdOut[] {
  return THRESHOLD_DEFS.map((def) => {
    if (def.source_override) {
      // flex_factor — always "story-frontmatter", always default value
      return {
        name: def.name,
        value: def.default,
        default: def.default,
        source: def.source_override,
        editable_via: def.editable_via,
        phase2_writable: def.phase2_writable,
      };
    }

    const stateKey = def.stateKey!;
    const hasKey = Object.prototype.hasOwnProperty.call(state, stateKey);
    const rawValue = state[stateKey];
    const value = typeof rawValue === 'number' ? rawValue : def.default;
    const source = hasKey ? 'state.json' : 'default';

    return {
      name: def.name,
      value,
      default: def.default,
      source,
      editable_via: def.editable_via,
      phase2_writable: def.phase2_writable,
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

  // 3. Build current field
  const current = buildCurrentField(state, ttlMinutes);

  // 4. Build thresholds
  const thresholds = buildThresholds(state);

  // 5. Determine context_budget_threshold value for waypoints/misses queries
  const thresholdValue =
    thresholds.find((t) => t.name === 'context_budget_threshold')?.value ?? 120000;

  // 6. Open effort.db
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

  const resolver_state = readResolverState(projectDir);

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
