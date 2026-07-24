---
id: RELEASE-019
rail: RELEASE
title: Second pre-fold reconciliation — merge main (36 commits, incl. INFRA-205/206/207) into fold-prep
status: complete
phase: "HARNESS016-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/hooks.json
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/story_update.py
touches:
  - tests/pairmode/test_hooks_json.py
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_sync.py
  - docs/cer-backlog.md
  - docs/phases/phase-91.md
  - docs/phases/phase-92.md
  - docs/phases/phase-93.md
  - docs/phases/phase-94.md
---

## Requires

- RELEASE-014 (status: complete) reconciled 31 main-only commits into
  `fold-prep` at its authoring time (2026-07-16).
- `main` has since advanced 36 further commits not present on `fold-prep`
  (`git log fold-prep..main --oneline`, verified 2026-07-17), through
  `2936f2a docs(checkpoint-92): record cp92 acceptance note`.
- Of these, two are load-bearing for the cold-eyes review that motivated this
  story batch:
  - **INFRA-205** (`d9744a1`) — registers the `Edit|Write` and `Read`
    `PreToolUse` matchers in `hooks/hooks.json` so `scope_guard.py` and
    `cold_read_guard.py`'s dispatch branches in `hooks/pre_tool_use.py`
    (already present on `fold-prep`, unreachable without this) actually
    fire. Adds a regression test (`tests/pairmode/test_hooks_json.py`) that
    scans `pre_tool_use.py` for dispatched tool-name literals and fails if
    `hooks.json` doesn't register a matching matcher.
  - **INFRA-206** (`5b87922`) — widens `bootstrap.py`'s
    `_register_pretooluse_hook` to the full `Task|Agent|Edit|Write|Read`
    matcher for downstream projects, migrating a stale `Task`-only or
    `Task|Agent` block in place by matching on command rather than matcher
    string.
- The remaining main-only commits (INFRA-200-204, 207, the `story_update.py`
  pipe-corruption fix and its CER-064/066 backlog closures, and
  checkpoint/spec-scaffold chores for phases 91-94) are real and lower-stakes
  for the fold; port them in the same merge per Ensures below rather than
  deferring, per RELEASE-014's precedent of not letting `fold-prep` fall
  further behind.

## Ensures

- `git merge main` into `fold-prep` completes with all conflicts resolved; no
  unresolved markers in any file.
- INFRA-205 and INFRA-206 land intact and compose correctly with
  `fold-prep`'s existing era-3 hook/gate code — no regression to either
  side's tests. After the merge, `hooks/hooks.json`'s `PreToolUse` array
  registers matchers covering every tool name dispatched in
  `hooks/pre_tool_use.py` (verified by the ported
  `test_hooks_json.py` regression test, not just visual inspection).
- INFRA-207's `_update_story_row_in_phase` escaped-pipe fix lands intact and
  composes with any phase-table-writing code already on `fold-prep`.
- `git log fold-prep..main` is empty after the merge.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes on
  the merged tree.

## Instructions

Mirror RELEASE-014's procedure: enumerate `git log fold-prep..main --oneline`,
categorize each commit (already-ported / port-needed / superseded), perform
the merge on `fold-prep` in `/mnt/work/flex-harness`, resolve conflicts per
the same conventions (prefer the union of both sides' feature sets; retired-
file conflicts resolve as delete only if equivalent functionality already
exists on `fold-prep`), and run the full suite after each non-trivial file's
resolution, not just at the end.

Do not tag. Do not push to `origin/fold-prep` as part of this story unless
the merge and full test suite are both clean — commit locally first, verify,
then push.

## Tests

- Full suite: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.
- Assert `git log fold-prep..main --oneline` returns no commits.
- Spot-check: `hooks/hooks.json` registers a matcher for every tool name
  dispatched in `hooks/pre_tool_use.py` (the INFRA-205 regression test
  covers this; run it explicitly).
