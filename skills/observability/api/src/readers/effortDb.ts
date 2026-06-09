import Database from 'better-sqlite3';
import { createRequire } from 'node:module';

// ---------------------------------------------------------------------------
// Output shapes
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Open DB (read-only URI)
// ---------------------------------------------------------------------------

/**
 * Open the effort.db at the given path in read-only mode.
 * Returns null if the file does not exist or cannot be opened.
 */
export function openEffortDb(dbPath: string): Database.Database | null {
  try {
    // Ensure the file exists before attempting to open (better-sqlite3 will
    // create an empty DB if the file is absent, which we do not want).
    const db = new Database(dbPath, { readonly: true, fileMustExist: true });
    return db;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Median helper (SQLite has no built-in MEDIAN)
// ---------------------------------------------------------------------------

/**
 * Compute median of a numeric column for a given WHERE clause.
 * Uses ORDER BY ... LIMIT 1 OFFSET count/2 for efficiency.
 * Returns null when no rows match.
 */
function sqliteMedian(
  db: Database.Database,
  table: string,
  column: string,
  where: string,
  params: unknown[],
): number | null {
  const countRow = db
    .prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE ${where} AND ${column} IS NOT NULL`)
    .get(...params) as { n: number } | undefined;
  const n = countRow?.n ?? 0;
  if (n === 0) return null;
  const offset = Math.floor(n / 2);
  const row = db
    .prepare(
      `SELECT ${column} AS v FROM ${table} WHERE ${where} AND ${column} IS NOT NULL ORDER BY ${column} LIMIT 1 OFFSET ?`,
    )
    .get(...params, offset) as { v: number } | undefined;
  return row?.v ?? null;
}

// ---------------------------------------------------------------------------
// p90 helper
// ---------------------------------------------------------------------------

function sqliteP90(
  db: Database.Database,
  table: string,
  column: string,
  where: string,
  params: unknown[],
): number | null {
  const countRow = db
    .prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE ${where} AND ${column} IS NOT NULL`)
    .get(...params) as { n: number } | undefined;
  const n = countRow?.n ?? 0;
  if (n === 0) return null;
  const offset = Math.floor(n * 0.9);
  const row = db
    .prepare(
      `SELECT ${column} AS v FROM ${table} WHERE ${where} AND ${column} IS NOT NULL ORDER BY ${column} LIMIT 1 OFFSET ?`,
    )
    .get(...params, offset) as { v: number } | undefined;
  return row?.v ?? null;
}

// ---------------------------------------------------------------------------
// Query: waypoints
// ---------------------------------------------------------------------------

/**
 * Return reviewer FAIL attempts ordered by ts descending, max 100 rows.
 * near_miss = tokens_total > threshold * 0.85
 * delta_above_threshold = tokens_total - threshold when tokens_total > threshold, else null
 */
export function queryWaypoints(
  db: Database.Database,
  threshold: number,
): Waypoint[] {
  interface Row {
    created_at: string | null;
    tokens_total: number;
    story_id: string | null;
    phase: string | null;
    agent_role: string | null;
    outcome: string | null;
  }

  // Check if created_at or ts column exists
  let tsColumn = 'created_at';
  try {
    const cols = db.prepare("PRAGMA table_info('attempts')").all() as Array<{ name: string }>;
    const colNames = cols.map((c) => c.name);
    if (colNames.includes('ts')) tsColumn = 'ts';
    else if (colNames.includes('created_at')) tsColumn = 'created_at';
  } catch {
    // Fall back to created_at
  }

  let rows: Row[];
  try {
    rows = db
      .prepare(
        `SELECT ${tsColumn} AS created_at, tokens_total, story_id, phase, agent_role, outcome
         FROM attempts
         WHERE tokens_total IS NOT NULL
           AND outcome = 'FAIL'
           AND agent_role = 'reviewer'
         ORDER BY ${tsColumn} DESC
         LIMIT 100`,
      )
      .all() as Row[];
  } catch {
    return [];
  }

  return rows.map((row) => {
    const tokens = row.tokens_total;
    const near_miss = tokens > threshold * 0.85;
    const delta_above_threshold = tokens > threshold ? tokens - threshold : null;
    return {
      ts: row.created_at ?? '',
      tokens,
      story_id: row.story_id,
      phase: row.phase,
      agent_role: row.agent_role,
      outcome: row.outcome,
      near_miss,
      delta_above_threshold,
    };
  });
}

// ---------------------------------------------------------------------------
// Query: effort summary
// ---------------------------------------------------------------------------

/**
 * Return totals and per-phase breakdown (max 20 phases, ordered by phase desc).
 */
export function queryEffortSummary(db: Database.Database): EffortSummary {
  interface TotalRow {
    total: number;
  }

  let total_attempts = 0;
  try {
    const totalRow = db.prepare('SELECT COUNT(*) AS total FROM attempts').get() as
      | TotalRow
      | undefined;
    total_attempts = totalRow?.total ?? 0;
  } catch {
    return { total_attempts: 0, by_phase: [] };
  }

  // Get distinct phases
  interface PhaseRow {
    phase: string | null;
  }
  let phaseRows: PhaseRow[];
  try {
    phaseRows = db
      .prepare(
        `SELECT DISTINCT phase FROM attempts WHERE phase IS NOT NULL
         ORDER BY phase DESC LIMIT 20`,
      )
      .all() as PhaseRow[];
  } catch {
    return { total_attempts, by_phase: [] };
  }

  const by_phase: PhaseEffort[] = [];

  for (const pr of phaseRows) {
    const phase = pr.phase ?? '';
    interface CountRow {
      n: number;
    }
    const countRow = db
      .prepare(`SELECT COUNT(*) AS n FROM attempts WHERE phase = ?`)
      .get(phase) as CountRow | undefined;
    const attempts = countRow?.n ?? 0;

    const median_tokens = sqliteMedian(db, 'attempts', 'tokens_total', 'phase = ?', [phase]);
    const p90_tokens = sqliteP90(db, 'attempts', 'tokens_total', 'phase = ?', [phase]);
    const median_duration_ms = sqliteMedian(db, 'attempts', 'duration_ms', 'phase = ?', [phase]);

    by_phase.push({ phase, attempts, median_tokens, p90_tokens, median_duration_ms });
  }

  return { total_attempts, by_phase };
}

// ---------------------------------------------------------------------------
// Query: misses
// ---------------------------------------------------------------------------

/**
 * Return rows where tokens_total > threshold * 1.10 (max 10, most recent first).
 */
export function queryMisses(
  db: Database.Database,
  threshold: number,
): { count: number; entries: MissEntry[] } {
  const ceiling = threshold * 1.1;

  // Check timestamp column name
  let tsColumn = 'created_at';
  try {
    const cols = db.prepare("PRAGMA table_info('attempts')").all() as Array<{ name: string }>;
    const colNames = cols.map((c) => c.name);
    if (colNames.includes('ts')) tsColumn = 'ts';
    else if (colNames.includes('created_at')) tsColumn = 'created_at';
  } catch {
    // Fall back to created_at
  }

  interface CountRow {
    n: number;
  }
  interface MissRow {
    created_at: string | null;
    phase: string | null;
    tokens_total: number;
    story_id: string | null;
  }

  let count = 0;
  let rows: MissRow[] = [];
  try {
    const countRow = db
      .prepare(`SELECT COUNT(*) AS n FROM attempts WHERE tokens_total > ?`)
      .get(ceiling) as CountRow | undefined;
    count = countRow?.n ?? 0;

    rows = db
      .prepare(
        `SELECT ${tsColumn} AS created_at, phase, tokens_total, story_id
         FROM attempts
         WHERE tokens_total > ?
         ORDER BY ${tsColumn} DESC
         LIMIT 10`,
      )
      .all(ceiling) as MissRow[];
  } catch {
    return { count: 0, entries: [] };
  }

  const entries: MissEntry[] = rows.map((row) => ({
    ts: row.created_at ?? '',
    phase: row.phase,
    tokens_at_block: row.tokens_total,
    story_id: row.story_id,
  }));

  return { count, entries };
}
