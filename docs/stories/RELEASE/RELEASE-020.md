---
id: RELEASE-020
rail: RELEASE
title: Wire flex_factor into the context-budget PreToolUse gate
status: planned
phase: "HARNESS016-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/pre_tool_use.py
touches:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/flex_build.py
  - docs/architecture.md
  - tests/pairmode/test_pre_tool_use_hook.py
---

## Requires

- RELEASE-019 complete (this story must not run against pre-reconciliation
  `pre_tool_use.py`).
- `docs/architecture.md` (lines ~245-250, ~1300-1303) documents story
  frontmatter `flex_factor` as overriding the effective context ceiling for
  that story, and the observability SPA displays the raised ceiling
  accordingly.
- `context_budget.decide()` already accepts a `flex_factor` parameter
  (`skills/pairmode/scripts/context_budget.py`) and `flex_build.py` already
  parses `flex_factor` from story frontmatter — both sides of the wiring
  exist.
- The sole production caller, `hooks/pre_tool_use.py`, calls
  `context_budget.decide(project_dir=project_dir)` with no `flex_factor`
  argument, so the override is always 1.0 in practice regardless of what a
  story's frontmatter declares. A user who raises `flex_factor` on a story
  sees the dashboard confirm a larger ceiling while the gate silently
  enforces the unraised one — a sanctioned override that appears to work but
  doesn't, found via cold-eyes review 2026-07-17.

## Ensures

- `hooks/pre_tool_use.py` resolves the current story's `flex_factor` (via
  the same story-resolution path `flex_build.py` uses to read frontmatter —
  reuse existing resolution logic, do not duplicate it) and passes it to
  `context_budget.decide()`.
- If no current story is resolvable, or the story has no `flex_factor` set,
  the gate behaves exactly as before (factor defaults to 1.0) — no change to
  the no-override path.
- A story with `flex_factor` set to a value other than 1.0 measurably changes
  the gate's block/allow decision at the boundary token count that the
  default factor would have blocked — covered by a new test case in
  `tests/pairmode/test_pre_tool_use_hook.py`.
- The observability SPA's displayed ceiling and the gate's enforced ceiling
  agree for the same story (no separate fix needed if the SPA already reads
  the same frontmatter field — verify, don't assume).

## Instructions

1. Read how `flex_build.py` resolves the current story and reads
   `flex_factor` from its frontmatter; identify the shared resolution
   helper (if any) usable from `pre_tool_use.py` without duplicating
   story-lookup logic.
2. Thread the resolved `flex_factor` through to the `decide()` call in
   `hooks/pre_tool_use.py`.
3. Add a test exercising a story with a non-default `flex_factor` to confirm
   the gate's decision changes accordingly.
4. Do not change `context_budget.decide()`'s signature or default behavior —
   it already accepts the parameter correctly.

## Tests

- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pre_tool_use_hook.py tests/pairmode/test_context_budget.py -x -q`.
- New test: a story with `flex_factor: 2.0` and a token count that would
  block under the default ceiling passes under the raised one, exercised
  through `pre_tool_use.py`'s actual entry point (not just calling
  `decide()` directly with the factor pre-supplied).
