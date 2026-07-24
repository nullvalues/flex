import { useQuery } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// API base URL — always relative so dev proxy and prod static serve both work.
// ---------------------------------------------------------------------------

const API_BASE = '/api';

// ---------------------------------------------------------------------------
// Shared error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string, message?: string) {
    super(message ?? `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  const text = await res.text();
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = JSON.parse(text);
      if (j && typeof j === 'object' && 'error' in j && typeof j.error === 'string') {
        msg = j.error;
      }
    } catch {
      // non-JSON body
    }
    throw new ApiError(res.status, text, msg);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(res.status, text, 'invalid JSON in response');
  }
}

// ---------------------------------------------------------------------------
// Shared response shapes
// ---------------------------------------------------------------------------

export interface Repo {
  id: string;
  project_dir: string;
  color: string;
  registered: boolean;
  state_json_present: boolean;
}

export interface ReposResponse {
  generated_at: string;
  repos: Repo[];
}

export interface Story {
  id: string;
  rail: string;
  title: string;
  status: string;
  story_class: string;
  flex_factor: number;
  primary_files: string[];
  touches: string[];
}

export interface Phase {
  phase_ref: string;
  file: string | null;
  title: string | null;
  status: string;
  checkpoint_tag: string | null;
  era: string | null;
  stories: Story[];
  deferred: string[];
}

// ---------------------------------------------------------------------------
// Resolver state model (OBS-001/002)
// ---------------------------------------------------------------------------

export interface ResolverAction {
  action: string;
  scalar?: string | null;
  model?: string | null;
  reason?: string | null;
  meta?: Record<string, unknown>;
}

export interface ResolverPosition {
  active_phase_file: string | null;
  next_story_id: string | null;
  next_story_file: string | null;
  attempt_count: number;
  builder_model: string | null;
  builder_model_reason: string | null;
  gate_stub: { ok: boolean; blocked_reason: string };
  gate_schema: { ok: boolean; blocked_reason: string };
  gate_auth: { ok: boolean; blocked_reason: string };
  last_attempt_outcome: string;
  checkpoint_step: string[];
  needs_spec: boolean;
}

export interface EffortRoleEntry {
  count: number;
  median_tokens: number | null;
}

export interface ResolverIndexEntry {
  phase_ref: string;
  status: string;
  active: boolean;
}

export interface ResolverStateDoc {
  schema_version: number;
  action: ResolverAction;
  position: ResolverPosition;
  effort_by_role: Record<string, EffortRoleEntry>;
  index: ResolverIndexEntry[];
}

export interface SystemResponse {
  repo_id: string;
  generated_at: string;
  phases: Phase[];
  resolver_state: ResolverStateDoc | null;
}

export interface Threshold {
  name: string;
  value: number;
  default: number;
  source: string;
  editable_via: string | null;
  phase2_writable: boolean;
  provenance: string | null;
}

export interface CurrentContext {
  tokens: number | null;
  recorded_at: string | null;
  age_seconds: number | null;
  stale: boolean;
  story_id: string | null;
  phase: string | null;
}

export interface Waypoint {
  ts: string;
  tokens: number;
  story_id: string | null;
  phase: string | null;
  agent_role: string | null;
  outcome: string | null;
  near_miss: boolean;
  delta_above_threshold: number | null;
}

export interface PhaseEffort {
  phase: string;
  attempts: number;
  median_tokens: number | null;
  p90_tokens: number | null;
  median_duration_ms: number | null;
}

export interface EffortSummary {
  total_attempts: number;
  by_phase: PhaseEffort[];
}

export interface MissEntry {
  ts: string;
  phase: string | null;
  tokens_at_block: number;
  story_id: string | null;
}

export interface MissesBlock {
  count: number;
  entries: MissEntry[];
}

export interface ContextResponse {
  repo_id: string;
  generated_at: string;
  current: CurrentContext;
  thresholds: Threshold[];
  waypoints: Waypoint[];
  effort_summary: EffortSummary;
  misses: MissesBlock;
  resolver_state: ResolverStateDoc | null;
}

export interface Lesson {
  id: string;
  date?: string;
  status?: string;
  trigger?: string;
  problem?: string;
  learning?: string;
  methodology_change?: { affects?: string[]; description?: string };
  applies_to?: string[];
  source_project?: string;
  promotion_candidate: boolean;
  promotion_reasons: string[];
}

export interface LessonsResponse {
  repo_id: string;
  generated_at: string;
  lessons: Lesson[];
}

// ---------------------------------------------------------------------------
// Query hooks — one per endpoint.
// ---------------------------------------------------------------------------

export function useRepos() {
  return useQuery<ReposResponse>({
    queryKey: ['repos'],
    queryFn: () => fetchJson<ReposResponse>(`${API_BASE}/repos`),
  });
}

export function useSystem(repoId: string) {
  return useQuery<SystemResponse>({
    queryKey: ['system', repoId],
    queryFn: () => fetchJson<SystemResponse>(`${API_BASE}/repos/${repoId}/system`),
    enabled: Boolean(repoId),
  });
}

export function useContext(repoId: string) {
  return useQuery<ContextResponse>({
    queryKey: ['context', repoId],
    queryFn: () => fetchJson<ContextResponse>(`${API_BASE}/repos/${repoId}/context`),
    enabled: Boolean(repoId),
  });
}

export function useLessons(repoId: string) {
  return useQuery<LessonsResponse>({
    queryKey: ['lessons', repoId],
    queryFn: () => fetchJson<LessonsResponse>(`${API_BASE}/repos/${repoId}/lessons`),
    enabled: Boolean(repoId),
  });
}
