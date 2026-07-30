---
id: INFRA-327
rail: INFRA
title: Exempt loop-breaker from the context-budget gate — it is the deterministic double-fail step, not discretionary
status: draft
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - hooks/pre_tool_use.py
  - tests/pairmode/test_pre_tool_use_hook.py
  - docs/architecture.md
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-327.md
---

<!-- SPEC-WRITER NOTE (frontmatter): `touches:` is block-style per CER-115 —
     flow-style `[a, b]` parses as a string and crashes create-story-worktree's
     `generate_permissions_artifact`. `hooks/**` is a PROTECTED path
     (`scope_guard.PROTECTED_GLOBS`, `scope_guard.py:32-40`) and is therefore
     satisfiable only via this explicit declaration plus a valid permissions
     artifact (INFRA-253) — deliberate, not an oversight. `docs/cer/backlog.md`
     is NOT touched: this story was routed directly into phase 114 by explicit
     operator instruction, not pulled from an existing CER backlog row.  -->

## Context

Operator report (2026-07-29): "loop-breaker used to, and should run
automatically after two failed build attempts — that's its purpose, to
break a loop. Human intervention is only required if loop-breaker's
supplied fix doesn't work to break the build failure."

Investigation confirmed the intended behavior is already correctly
implemented in `next_action.py`'s FAIL ladder: Row 6
(`skills/pairmode/scripts/next_action.py`, ~line 1312) fires
unconditionally when `attempt_count == 2` and the last attempt outcome is
`FAIL`, returning `spawn-loop-breaker` with no branch, no operator
judgment call, no alternative action — exactly the same shape as
`reviewer`'s dispatch after every builder attempt. Row 7 (attempt 3+
failed) is the correct human-intervention point: only after a builder
attempt informed by the loop-breaker's proposed fix *also* fails does
`next-action` return `await-user`. `CLAUDE.build.md`'s
`ACTION_SUBAGENT_TYPE` map correctly resolves `spawn-loop-breaker` to the
`loop-breaker` subagent type, and
`skills/pairmode/skills/loop-breaker/procedure.md` contains no requirement
for human confirmation before running — its own spec is silent on the
question, meaning nothing in the loop-breaker's own logic gates it on a
human.

The actual regression is in `hooks/pre_tool_use.py`'s `BUILD_CYCLE_SUBAGENTS`
set (~line 71), which governs the context-budget gate (INFRA-199): a
`Task`/`Agent` spawn whose `subagent_type` is in this set can be blocked by
`context_budget.decide()` pending operator acknowledgment ("CONTEXT CHECK
REQUIRED" or an overrun block) before it is allowed to proceed. The set
currently contains `builder`, `loop-breaker`, `security-auditor`,
`intent-reviewer` — but `reviewer` is explicitly exempted (INFRA-246), per
the module's own docstring: "`BUILD_CYCLE_SUBAGENTS` covers only
discretionary or escalation build-cycle spawns — spawns where the
orchestrator has a legitimate alternative action (report tokens, `/clear`,
or reconsider whether to spawn at all) and blocking-to-conserve is a valid
tradeoff. It never gates a spawn that is the mandatory, only-valid next
step in the build loop." `loop-breaker`'s Row-6 dispatch meets that same
exemption criterion exactly — it is the mandatory, only-valid next step on
a double-fail, with no orchestrator alternative to "reconsider" — but it
was never added to the exemption alongside `reviewer` when INFRA-246
landed. The practical consequence matches the operator's report exactly:
when context budget is tight at the moment of a double-fail, the automatic
loop-breaker dispatch can be blocked pending operator acknowledgment,
defeating the mechanism's entire purpose (autonomously breaking a stuck
build loop) at precisely the moment it's needed — a stuck loop is often
also a context-heavy one.

## Requires

- `hooks/pre_tool_use.py`'s existing `reviewer` exemption (INFRA-246) as
  the direct precedent and model for this fix — same reasoning, same
  mechanism, just a different subagent_type.
- `tests/pairmode/test_pre_tool_use_hook.py`'s existing INFRA-246 reviewer
  exemption test (~line 472) as the model for the new loop-breaker test.

## Ensures

- `loop-breaker` is removed from `hooks/pre_tool_use.py`'s
  `BUILD_CYCLE_SUBAGENTS` frozenset — a `Task`/`Agent` spawn with
  `subagent_type == "loop-breaker"` passes through the `Task`/`Agent`
  branch ungated (matching `reviewer`'s current exemption exactly), never
  invoking `context_budget.decide()` or writing any acknowledgment state.
- `builder`, `security-auditor`, `intent-reviewer` remain in
  `BUILD_CYCLE_SUBAGENTS`, ungated by this story — this is a single,
  narrow exemption, not a broader gate rollback.
- The module docstring and the `BUILD_CYCLE_SUBAGENTS` definition's inline
  comment are updated to document the `loop-breaker` exemption alongside
  `reviewer`'s, with the same "mandatory, only-valid next step" rationale
  and a citation of this story (mirroring the existing INFRA-246 citation
  style).
- `tests/pairmode/test_pre_tool_use_hook.py` gains a regression test
  mirroring the existing INFRA-246 reviewer-exemption test, asserting a
  `Task`/`Agent` spawn with `subagent_type: "loop-breaker"` is never
  blocked by the context-budget gate regardless of `context_current_tokens`
  state (e.g. reuse or parallel the same over-budget fixture the reviewer
  test uses).
- No existing test in `tests/pairmode/` regresses (full suite run without
  `-x`, per this project's pytest-no-x-before-merge convention).
- `docs/architecture.md`'s description of the context-budget gate's
  `BUILD_CYCLE_SUBAGENTS` membership (wherever INFRA-246's reviewer
  exemption is documented) is updated to include loop-breaker.

## Instructions

1. Read `hooks/pre_tool_use.py` in full, focusing on the
   `BUILD_CYCLE_SUBAGENTS` definition and its docstring/inline comments
   (~lines 1-30, ~lines 60-75).
2. Read `tests/pairmode/test_pre_tool_use_hook.py`'s existing INFRA-246
   reviewer-exemption test (~line 472) to match its exact structure and
   fixture shape for the new loop-breaker test.
3. Remove `"loop-breaker"` from the `BUILD_CYCLE_SUBAGENTS` frozenset;
   update the docstring and inline comment to cite this story and explain
   the exemption using the same "mandatory, only-valid next step" language
   already used for `reviewer`.
4. Add the regression test per the Ensures above.
5. Update `docs/architecture.md` wherever INFRA-246's exemption is
   documented.
6. Run `uv run pytest tests/pairmode/ -q` (no `-x`) and confirm no
   regressions, and specifically confirm the new test passes and the
   existing reviewer-exemption test still passes unchanged.

## Tests

`uv run pytest tests/pairmode/test_pre_tool_use_hook.py -q` plus a full
`uv run pytest tests/pairmode/ -q` (no `-x`) run before merge.
