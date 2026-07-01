import { spawnSync } from 'node:child_process';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Output shapes (OBS-001)
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

// ---------------------------------------------------------------------------
// Path to the Python flex_build CLI (relative to this file in dist/)
// ---------------------------------------------------------------------------

function getFlexBuildPath(): string {
  // This file sits at skills/observability/api/dist/readers/resolverState.js
  // flex_build.py is at skills/pairmode/scripts/flex_build.py
  const thisFile = fileURLToPath(import.meta.url);
  const obsApiDir = path.resolve(path.dirname(thisFile), '..', '..', '..', '..');
  return path.join(obsApiDir, '..', 'pairmode', 'scripts', 'flex_build.py');
}

// ---------------------------------------------------------------------------
// Reader
// ---------------------------------------------------------------------------

/**
 * Shell `flex_build.py resolver-state` and return the typed state model.
 * Returns null if the CLI is unavailable or the output cannot be parsed.
 */
export function readResolverState(projectDir: string): ResolverStateDoc | null {
  const flexBuildPath = getFlexBuildPath();

  const result = spawnSync(
    'uv',
    ['run', 'python', flexBuildPath, 'resolver-state', '--project-dir', projectDir],
    {
      encoding: 'utf8',
      timeout: 10000,
      env: { ...process.env, PATH: `${process.env['HOME'] ?? ''}/.local/bin:${process.env['PATH'] ?? ''}` },
    },
  );

  if (result.status !== 0 || !result.stdout) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(result.stdout);
    if (parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as ResolverStateDoc;
    }
  } catch {
    // unparseable JSON
  }
  return null;
}
