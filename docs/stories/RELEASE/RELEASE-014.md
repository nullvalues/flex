---
id: RELEASE-014
rail: RELEASE
title: Pre-fold reconciliation — merge main (31 commits) into fold-prep
status: planned
phase: "HARNESS016-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/pre_tool_use.py
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/scripts/sync.py
  - hooks/hooks.json
  - hooks/user_prompt_submit.py
  - .claude/settings.json
touches:
  - CLAUDE.md
  - docs/architecture.md
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/templates/CLAUDE.md.j2
  - skills/pairmode/scripts/cold_read_guard.py
  - skills/pairmode/scripts/story_new.py
  - skills/pairmode/scripts/story_resolver.py
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/templates/.pairmode-overrides.j2
  - lessons/LESSONS.md
  - lessons/lessons.json
  - tests/pairmode/test_pre_tool_use_hook.py
  - tests/pairmode/test_pre_tool_use_scope_guard.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_cold_read_guard.py
  - tests/pairmode/test_user_prompt_submit_hook.py
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_sync.py
  - tests/pairmode/test_story_new.py
  - tests/pairmode/test_flex_build_permissions_create.py
---

## Requires

- RELEASE-008 (status: complete) reconciled 46 main-only commits into `fold-prep`
  at its authoring time (`docs/stories/RELEASE/RELEASE-008.md`).
- `main` has since advanced 31 further commits not present on `fold-prep`
  (`git log fold-prep..main --oneline`, verified 2026-07-16), through
  `928d89a fix(permissions): convert Write(path) rules to Edit(path)`.
- Of these, four are load-bearing for this fold phase specifically:
  - **INFRA-192** (`9496d3a`) — `UserPromptSubmit` hook adds a user-turn sequence
    counter (`hooks/user_prompt_submit.py`, `hooks/hooks.json`).
  - **INFRA-193** (`93306b4`) — context-budget acknowledgment gate requires a
    genuine user turn since the last block (`context_budget.py`,
    `hooks/pre_tool_use.py`); depends on INFRA-192's counter.
  - **INFRA-199** (`3c6e146`) — scopes the budget `PreToolUse` gate to the
    build-cycle `subagent_type` allowlist instead of gating every Task spawn
    (`hooks/pre_tool_use.py`).
  - **INFRA-195** (`5c6d42f`) — checklist-item-level section granularity in
    `audit.py`/`sync.py` — the tooling RELEASE-015/017 depend on.
- The remaining main-only commits (INFRA-194, 196, 197, 198, the recovered
  `story_resolver.py` fix, and checkpoint/spec-scaffold chores) are real but
  lower-stakes for the fold; port them in the same merge per Ensures below
  rather than deferring, since `fold-prep` should not fall further behind.

## Ensures

- `git merge main` into `fold-prep` completes with all conflicts resolved; no
  unresolved markers in any file.
- The budget-gate chain (INFRA-192 → INFRA-193 → INFRA-199) lands intact and
  composed correctly with `fold-prep`'s own era-3 budget-gate code (the
  `expected_step_tokens` / `context_budget.decide()` path exercised by the
  `PreToolUse` hook on `Task` spawns) — no regression to either side's tests.
- INFRA-195's audit/sync granularity changes land intact and compose with any
  era-3-only changes already in `sync.py`/`audit.py` on `fold-prep` (if any
  overlap exists, the merged version is the union of both feature sets, per
  the RELEASE-008 precedent of "combined validator handles both").
- INFRA-196 (cold-read enforcement hook) and INFRA-198 (permissions-create
  self-block fix) land intact; where they touch `CLAUDE.build.md` /
  `skills/pairmode/templates/CLAUDE.build.md.j2`, reconcile against
  `fold-prep`'s already-thin-harness-reduced template (HARNESS006-main) rather
  than reverting the reduction.
- INFRA-197 (`story_new.py` suffixed-phase glob) and INFRA-194
  (`permissions-create` idempotency in `flex_build.py`) land intact.
- The recovered `story_resolver.py` rail-regex fix and its L019 lesson entry
  land intact in `lessons/lessons.json` (append-only — no existing lesson
  entries are altered, only appended).
- `928d89a`'s `Write(path)` → `Edit(path)` permission-rule conversion is
  applied consistently, including to the `Write(docs/phases/permissions/**)`
  rule this repo's `.claude/settings.json` gained via the earlier `sync-all`
  run this session — convert that rule to `Edit(...)` too, for consistency
  with the same convention, unless doing so breaks an existing test.
- `git log fold-prep..main` is empty after the merge.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes on
  the merged tree.

## Instructions

Mirror RELEASE-008's procedure: enumerate `git log fold-prep..main --oneline`,
categorize each commit (already-ported / port-needed / superseded), perform the
merge on `fold-prep` in `/mnt/work/flex-harness`, resolve conflicts per the
conventions above (prefer the union of both sides' feature sets over either
side's exclusive version; retired-file delete/modify conflicts resolve as
delete only if the equivalent functionality already exists elsewhere on
`fold-prep`, per RELEASE-008's agent-template precedent), and run the full
suite after each non-trivial file's resolution, not just at the end.

Do not tag. Do not push to `origin/fold-prep` as part of this story unless the
merge and full test suite are both clean — commit locally first, verify, then
push.

## Tests

- Full suite: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.
- Assert `git log fold-prep..main --oneline` returns no commits.
- Spot-check: `hooks/pre_tool_use.py` contains both the build-cycle allowlist
  scoping (INFRA-199) and any era-3-specific gate logic already on `fold-prep`.
