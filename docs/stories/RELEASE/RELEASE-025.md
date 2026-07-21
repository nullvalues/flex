---
id: RELEASE-025
rail: RELEASE
title: Fleet migration — sync anchor to pairmode 0.3.0 thin-harness loop
status: planned
phase: "HARNESS016-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
  - skills/pairmode/scripts/pairmode_migrate.py
  - skills/pairmode/scripts/fleet_discovery.py
touches:
  - docs/fleet-snapshot.md
---

## Requires

- This story is one of the fleet migrations RELEASE-015's DP8 gate checks
  for — it is a *prerequisite* to RELEASE-015 passing, not gated by it. Run
  independently of RELEASE-015/016/017/018.
- `/mnt/work/anchor` is on pairmode 0.1.0 with `binding: version`
  (Signal-1 absent), confirmed via fresh `fleet_discovery.py` run 2026-07-21.
- **0.1.0 schema gap**: `/mnt/work/anchor`'s `.companion/state.json` is on
  pairmode 0.1.0, missing the entire 0.2.x context-budget field set
  (`context_budget_threshold`, `context_budget_user_turn_seq`,
  `context_current_tokens`, `mode`, `last_session_*`, etc. — confirmed via
  key-diff against a 0.2.0 project on 2026-07-21). `pairmode_migrate.py
  to-030`'s docstring assumes a "0.2.x-bootstrapped project" and only seeds
  `expected_step_tokens`, rewrites the Era-2 stamp, and removes `pipe_path` —
  it does **not** backfill the missing 0.2.x context-budget keys.
- **Cross-repo scope, not enforced by scope_guard**: this story's actual file
  writes happen entirely inside `/mnt/work/anchor`, outside
  `/mnt/work/flex-harness`'s project root. `scope_guard.check_path()`
  normalises paths via `Path.relative_to(project_dir)`; a path outside
  flex-harness's root cannot be normalised, and if an active story has
  non-empty `allowed_paths`, such a write is hard-blocked ("path escapes
  project root") rather than fail-open like every other scope_guard case.
  **Do not dispatch this story to a spawn-builder subagent scoped to
  flex-harness's file permissions** — execute it directly (operator-run, or
  an agent given no flex-harness story-scope restriction),. This matches the runbook's own
  framing of fleet migration as operator-initiated, not a spawned build
  story.
- Seam gate (`docs/harness-cutover-runbook.md` § Seam gate) passes for
  `/mnt/work/anchor`:
  - `git -C /mnt/work/anchor status --porcelain` is empty (all work committed
    and pushed).
  - `uv run python flex_build.py read-attempt-count` (run from
    `/mnt/work/anchor`) returns `0`.
  - `/mnt/work/anchor` is at a phase boundary (checkpoint tag, or every
    current-phase story `status: complete`).
  - `flex_build.py check-stubs --project-dir /mnt/work/anchor` returns clean.
  - `/mnt/work/anchor` appears in `fleet_discovery.py list-projects`.
  If any seam-gate item fails, defer this story until `/mnt/work/anchor`'s
  own maintainer resolves it — do not force migration mid-story.

## Ensures

- `/mnt/work/anchor`'s `.companion/state.json` reads
  `"pairmode_version": "0.3.0"`.
- `/mnt/work/anchor`'s `CLAUDE.build.md` bakes an absolute
  `pairmode_scripts_dir` pointing at
  `/mnt/work/flex-harness/skills/pairmode/scripts` (Signal-1 present).
- `fleet_discovery.py discover --project-dir /mnt/work/anchor` (run from
  flex-harness) reports `binding: scripts`.
- One complete pairmode story cycle has run through `/mnt/work/anchor`'s
  migrated loop with no regressions, and the result is committed and pushed
  in `/mnt/work/anchor`'s own repo.
- No changes to any file inside `/mnt/work/flex-harness` other than an
  updated fleet snapshot (if regenerated).

## Instructions

Execute the runbook's 6-step Era 3 procedure (`docs/harness-cutover-runbook.md`
§ Per-project mechanic) against `/mnt/work/anchor`, all commands run with
`PATH=$HOME/.local/bin:$PATH` from `/mnt/work/flex-harness` except where
noted:

1. Confirm the seam gate (Requires) passes.
2. Dry-run:
   `uv run python skills/pairmode/scripts/pairmode_sync.py sync-all --project-dir /mnt/work/anchor --dry-run`.
   Review the diff.
3. Apply:
   `uv run python skills/pairmode/scripts/pairmode_sync.py sync-all --project-dir /mnt/work/anchor --apply --yes`.
4. Normalize:
   `uv run python skills/pairmode/scripts/pairmode_migrate.py to-030 --project-dir /mnt/work/anchor --apply`.

4a. **0.1.0 backfill** (this project only): after step 4 and before step 5,
    diff `/mnt/work/anchor/.companion/state.json`'s keys against a known-good
    0.2.0 project (e.g. `/mnt/work/radar`). Manually add any of
    `context_budget_threshold`, `context_budget_overrun_pct`,
    `expected_step_tokens`, `context_budget_reprompt_margin` (10000),
    `context_current_tokens` (seed to `1`), or `mode` that are still missing
    after `to-030`, matching `bootstrap.py`'s `_record_state()` defaults. This
    prevents RELEASE-021's `CONTEXT CHECK REQUIRED` fail-closed gate from
    tripping immediately on first use over a field that was simply never
    populated, rather than a genuine stale/missing-token condition.
5. Verify Signal-1:
   `uv run python skills/pairmode/scripts/fleet_discovery.py discover --project-dir /mnt/work/anchor`
   shows `binding: scripts`. If absent, stop and fix `CLAUDE.build.md` before
   continuing.
6. Run one complete story cycle in `/mnt/work/anchor`'s migrated loop (any
   story — doc/lesson stories are fine). Confirm `pairmode_version: 0.3.0`
   in `.companion/state.json`, then from `/mnt/work/anchor`:
   `git add -A && git commit -m "sync: migrate to pairmode 0.3.0 thin-harness loop" && git push`.

If step 5 or 6 fails, roll back per the runbook's rollback procedure
(`git -C /mnt/work/anchor checkout HEAD -- CLAUDE.build.md .companion/state.json`)
and re-run the Era 2 loop; do not leave `/mnt/work/anchor` half-migrated.

## Tests

- `PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/fleet_discovery.py discover --project-dir /mnt/work/anchor`
  reports `pairmode_version: 0.3.0` and `binding: scripts`.
- `git -C /mnt/work/anchor status --porcelain` is empty after the story
  (committed and pushed).
- If `/mnt/work/anchor` has its own test suite, it passes post-migration
  (project-specific — check for a `tests/` dir or documented test command in
  its own `CLAUDE.md`).
