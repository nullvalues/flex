import { promises as fsp } from 'node:fs';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import Database from 'better-sqlite3';

/**
 * A minimal, hermetic "flex project" tree — enough shape for every
 * observability API route to exercise its real parsers/readers against a
 * fixture rather than the live flex repo (INFRA-312 Instructions §3).
 *
 * Not the live flex repo: generated fresh in a temp dir per test file, torn
 * down afterwards. `readResolverState` (which shells out to
 * `flex_build.py resolver-state`) is expected to fail gracefully (returns
 * null) against this fixture — that null is itself a legitimate, asserted
 * response shape, not a test bug.
 */
export interface FixtureProject {
  dir: string;
}

const STORY_MD = `---
id: DEMO-001
rail: DEMO
title: Demo fixture story
status: complete
story_class: code
flex_factor: 1.0
primary_files:
  - fixtures/demo.ts
touches:
  - fixtures/demo-helper.ts
---

## Context

Fixture story for INFRA-312 route smoke tests.
`;

const PHASE_INDEX_MD = `# Phase index

| Phase | Title | Status | Tag |
|---|---|---|---|
| 1 | Demo phase | complete | cp-1 |
`;

const PHASE_1_MD = `---
era: "001"
---

# Phase 1 — Demo phase

## Stories

| ID | Title | Status |
|---|---|---|
| DEMO-001 | Demo fixture story | complete |

## Deferred stories

- DEMO-002 — deferred for fixture purposes, resumed in Phase 2.
`;

function buildLessonsJson(): string {
  return JSON.stringify(
    {
      version: '1',
      lessons: [
        {
          id: 'lesson-001',
          date: '2026-01-01',
          status: 'applied',
          trigger: 'fixture trigger',
          problem: 'fixture problem',
          learning: 'fixture learning',
          methodology_change: {
            affects: ['scripts/effort_db.py'],
            description: 'add a check for the fixture condition',
          },
          applies_to: ['pairmode'],
          source_project: 'flex',
        },
        {
          id: 'lesson-002',
          date: '2026-01-02',
          status: 'draft',
          trigger: 'fixture trigger 2',
          problem: 'fixture problem 2',
          learning: 'fixture learning 2',
          methodology_change: { affects: [], description: 'not yet applied' },
          applies_to: [],
          source_project: 'flex',
        },
      ],
    },
    null,
    2,
  );
}

function buildStateJson(): string {
  return JSON.stringify(
    {
      context_budget_threshold: 120000,
      context_budget_overrun_pct: 0.1,
      expected_step_tokens: 5000,
      context_budget_reprompt_margin: 10000,
      story_spend_threshold: 100000,
      context_current_tokens: 42000,
      context_current_tokens_recorded_at: new Date().toISOString(),
      current_story: { id: 'DEMO-001', rail: 'DEMO' },
    },
    null,
    2,
  );
}

function seedEffortDb(dbPath: string): void {
  const db = new Database(dbPath);
  db.exec(`
    CREATE TABLE attempts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT,
      tokens_total INTEGER,
      story_id TEXT,
      phase TEXT,
      agent_role TEXT,
      outcome TEXT,
      duration_ms INTEGER
    );
  `);
  const insert = db.prepare(
    `INSERT INTO attempts (created_at, tokens_total, story_id, phase, agent_role, outcome, duration_ms)
     VALUES (@created_at, @tokens_total, @story_id, @phase, @agent_role, @outcome, @duration_ms)`,
  );
  const rows = [
    {
      created_at: '2026-01-01T00:00:00.000Z',
      tokens_total: 15000,
      story_id: 'DEMO-001',
      phase: '1',
      agent_role: 'builder',
      outcome: 'PASS',
      duration_ms: 12000,
    },
    {
      created_at: '2026-01-01T01:00:00.000Z',
      tokens_total: 130000,
      story_id: 'DEMO-001',
      phase: '1',
      agent_role: 'builder',
      outcome: 'FAIL',
      duration_ms: 45000,
    },
    {
      created_at: '2026-01-01T02:00:00.000Z',
      tokens_total: 8000,
      story_id: null,
      phase: null,
      agent_role: 'seed-miner',
      outcome: null,
      duration_ms: 3000,
    },
    // INFRA-348 (Ensures 4): a phase-1 row with a NULL duration_ms, mixed in
    // with the two already-populated phase-1 rows above — proves
    // queryEffortSummary's median_duration_ms aggregation filters NULLs
    // rather than coercing them to 0 or letting them poison the median.
    {
      created_at: '2026-01-01T03:00:00.000Z',
      tokens_total: 5000,
      story_id: 'DEMO-001',
      phase: '1',
      agent_role: 'builder',
      outcome: 'PASS',
      duration_ms: null,
    },
  ];
  for (const row of rows) insert.run(row);
  db.close();
}

/**
 * Build a fresh fixture project tree in a new temp directory. Callers must
 * call `cleanupFixtureProject` in an `afterAll`/`afterEach`.
 */
export async function createFixtureProject(): Promise<FixtureProject> {
  const dir = await fsp.mkdtemp(path.join(os.tmpdir(), 'flex-obs-fixture-'));

  await fsp.mkdir(path.join(dir, 'docs', 'stories', 'DEMO'), { recursive: true });
  await fsp.mkdir(path.join(dir, 'docs', 'phases'), { recursive: true });
  await fsp.mkdir(path.join(dir, '.companion'), { recursive: true });
  await fsp.mkdir(path.join(dir, 'lessons'), { recursive: true });

  await fsp.writeFile(path.join(dir, 'docs', 'stories', 'DEMO', 'DEMO-001.md'), STORY_MD, 'utf8');
  await fsp.writeFile(path.join(dir, 'docs', 'phases', 'index.md'), PHASE_INDEX_MD, 'utf8');
  await fsp.writeFile(path.join(dir, 'docs', 'phases', 'phase-1.md'), PHASE_1_MD, 'utf8');
  await fsp.writeFile(path.join(dir, '.companion', 'state.json'), buildStateJson(), 'utf8');
  await fsp.writeFile(path.join(dir, 'lessons', 'lessons.json'), buildLessonsJson(), 'utf8');

  seedEffortDb(path.join(dir, '.companion', 'effort.db'));

  return { dir };
}

export async function cleanupFixtureProject(project: FixtureProject): Promise<void> {
  await fsp.rm(project.dir, { recursive: true, force: true });
}

/**
 * Write a registry.json pointing at the given fixture project directories,
 * return its path. Point `FLEX_OBS_REGISTRY` at the result before invoking
 * routes that call `readRegistry()`.
 */
export async function writeRegistry(
  registryDir: string,
  repos: Array<{ id: string; project_dir: string; color: string }>,
): Promise<string> {
  const registryPath = path.join(registryDir, 'registry.json');
  fs.writeFileSync(registryPath, JSON.stringify({ version: 1, repos }, null, 2), 'utf8');
  return registryPath;
}
