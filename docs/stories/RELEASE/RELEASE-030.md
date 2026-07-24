---
id: RELEASE-030
rail: RELEASE
title: Fleet migration — sync cora to pairmode 0.3.0 thin-harness loop
status: backlog
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

## Deferred (2026-07-21)

**This story is deferred, not part of the current fold's DP8 requirement.**
`cora` was the testbed where anchor/flex build-loop principles were
originally proven out (anchor itself is flex's frozen predecessor — see
the phase doc's exclusion note) and still holds artifacts worth porting
into flex before a routine sync-all overwrites them — notably a rule
discovered there about not allowing a
schema-introducing story to complete without a matching UI management
story: violations pass smoke tests but fail immediately in UAT. flex's own
`CLAUDE.md` "Conceptual rebuild completeness" policy already codifies a
version of this rule at the global level, but cora's specific artifacts
(the concrete case that prompted it) have not been reviewed for anything
flex's codified version doesn't yet cover.

This is deferred rather than dropped (contrast anchor, RELEASE-025 —
removed outright, not deferred, since anchor is a frozen predecessor with
no further development). cora combines the 0.1.0 schema gap (below) with
this extra artifact-extraction need, making it a larger story than the
standard per-project migration. RELEASE-015's DP8 gate (see its Requires)
is updated to exclude `cora` from the current fold's hard-block
requirement; this story is resumed as its own dedicated story once the
artifact-extraction work is scoped — track alongside the CER backlog
(`docs/cer/backlog.md`) if extraction surfaces reusable findings.

## Requires

- `/mnt/work/cora` is on pairmode 0.1.0 with `binding: version`
  (Signal-1 absent), confirmed via fresh `fleet_discovery.py` run 2026-07-21.
- **0.1.0 schema gap**: `/mnt/work/cora`'s `.companion/state.json` is on
  pairmode 0.1.0, missing the entire 0.2.x context-budget field set
  (`context_budget_threshold`, `context_budget_user_turn_seq`,
  `context_current_tokens`, `mode`, `last_session_*`, etc. — confirmed via
  key-diff against a 0.2.0 project on 2026-07-21). `pairmode_migrate.py
  to-030`'s docstring assumes a "0.2.x-bootstrapped project" and only seeds
  `expected_step_tokens`, rewrites the Era-2 stamp, and removes `pipe_path` —
  it does **not** backfill the missing 0.2.x context-budget keys.
- **Cross-repo scope, not enforced by scope_guard**: this story's actual file
  writes happen entirely inside `/mnt/work/cora`, outside
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
  `/mnt/work/cora`:
  - `git -C /mnt/work/cora status --porcelain` is empty (all work committed
    and pushed).
  - `uv run python flex_build.py read-attempt-count` (run from
    `/mnt/work/cora`) returns `0`.
  - `/mnt/work/cora` is at a phase boundary (checkpoint tag, or every
    current-phase story `status: complete`).
  - `flex_build.py check-stubs --project-dir /mnt/work/cora` returns clean.
  - `/mnt/work/cora` appears in `fleet_discovery.py list-projects`.
  If any seam-gate item fails, defer this story until `/mnt/work/cora`'s
  own maintainer resolves it — do not force migration mid-story.

## Ensures

- `/mnt/work/cora`'s `.companion/state.json` reads
  `"pairmode_version": "0.3.0"`.
- `/mnt/work/cora`'s `CLAUDE.build.md` bakes an absolute
  `pairmode_scripts_dir` pointing at
  `/mnt/work/flex-harness/skills/pairmode/scripts` (Signal-1 present).
- `fleet_discovery.py discover --project-dir /mnt/work/cora` (run from
  flex-harness) reports `binding: scripts`.
- One complete pairmode story cycle has run through `/mnt/work/cora`'s
  migrated loop with no regressions, and the result is committed and pushed
  in `/mnt/work/cora`'s own repo.
- No changes to any file inside `/mnt/work/flex-harness` other than an
  updated fleet snapshot (if regenerated).

## Instructions

Execute the runbook's 6-step Era 3 procedure (`docs/harness-cutover-runbook.md`
§ Per-project mechanic) against `/mnt/work/cora`, all commands run with
`PATH=$HOME/.local/bin:$PATH` from `/mnt/work/flex-harness` except where
noted:

1. Confirm the seam gate (Requires) passes.
2. Dry-run:
   `uv run python skills/pairmode/scripts/pairmode_sync.py sync-all --project-dir /mnt/work/cora --dry-run`.
   Review the diff.
3. Apply:
   `uv run python skills/pairmode/scripts/pairmode_sync.py sync-all --project-dir /mnt/work/cora --apply --yes`.
4. Normalize:
   `uv run python skills/pairmode/scripts/pairmode_migrate.py to-030 --project-dir /mnt/work/cora --apply`.

4a. **0.1.0 backfill** (this project only): after step 4 and before step 5,
    diff `/mnt/work/cora/.companion/state.json`'s keys against a known-good
    0.2.0 project (e.g. `/mnt/work/radar`). Manually add any of
    `context_budget_threshold`, `context_budget_overrun_pct`,
    `expected_step_tokens`, `context_budget_reprompt_margin` (10000),
    `context_current_tokens` (seed to `1`), or `mode` that are still missing
    after `to-030`, matching `bootstrap.py`'s `_record_state()` defaults. This
    prevents RELEASE-021's `CONTEXT CHECK REQUIRED` fail-closed gate from
    tripping immediately on first use over a field that was simply never
    populated, rather than a genuine stale/missing-token condition.
5. Verify Signal-1:
   `uv run python skills/pairmode/scripts/fleet_discovery.py discover --project-dir /mnt/work/cora`
   shows `binding: scripts`. If absent, stop and fix `CLAUDE.build.md` before
   continuing.
6. Run one complete story cycle in `/mnt/work/cora`'s migrated loop (any
   story — doc/lesson stories are fine). Confirm `pairmode_version: 0.3.0`
   in `.companion/state.json`, then from `/mnt/work/cora`:
   `git add -A && git commit -m "sync: migrate to pairmode 0.3.0 thin-harness loop" && git push`.

If step 5 or 6 fails, roll back per the runbook's rollback procedure
(`git -C /mnt/work/cora checkout HEAD -- CLAUDE.build.md .companion/state.json`)
and re-run the Era 2 loop; do not leave `/mnt/work/cora` half-migrated.

## Tests

- `PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/fleet_discovery.py discover --project-dir /mnt/work/cora`
  reports `pairmode_version: 0.3.0` and `binding: scripts`.
- `git -C /mnt/work/cora status --porcelain` is empty after the story
  (committed and pushed).
- If `/mnt/work/cora` has its own test suite, it passes post-migration
  (project-specific — check for a `tests/` dir or documented test command in
  its own `CLAUDE.md`).
