---
id: INFRA-246
rail: INFRA
title: Exempt reviewer spawns from the context-budget gate — mandatory pipeline step, not discretionary
status: planned
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/pre_tool_use.py
touches:
  - skills/pairmode/scripts/context_budget.py
  - docs/architecture.md
  - tests/pairmode/test_pre_tool_use_hook.py
---

## Context

The context-budget gate in `hooks/pre_tool_use.py` gates Task/Agent spawns for
`subagent_type` in `BUILD_CYCLE_SUBAGENTS` (currently `{builder, reviewer,
loop-breaker, security-auditor, intent-reviewer}`, lines ~59-65) through
`context_budget.decide()`. When `context_current_tokens` is absent or stale
relative to `context_session_reset_at`, `decide()` returns a "CONTEXT CHECK
REQUIRED" block that refuses the spawn entirely until the orchestrator
manually reports a token count via `set-context-tokens`.

The operator has determined this is a design flaw specifically for
`reviewer`. The other four members of `BUILD_CYCLE_SUBAGENTS` are
discretionary or escalation steps — `builder` is the entry point of a story
attempt, `loop-breaker`/`security-auditor`/`intent-reviewer` are
conditional/checkpoint-stage spawns — and for those, blocking to force a
manual context check is a legitimate conservation tradeoff: the orchestrator
has a valid alternative action (report tokens, `/clear`, or reconsider
whether to spawn at all).

`reviewer` has no such alternative. Per `CLAUDE.build.md`'s build loop
(`on reviewer PASS: merge-story-worktree`, `on reviewer FAIL:
discard-story-worktree`), reviewer is the mandatory, deterministic next step
after every builder attempt — there is no path through the build loop that
skips review, and no other action the orchestrator can legitimately take once
a builder attempt is in hand. Blocking a mandatory pipeline step doesn't
conserve context; it just wedges the loop with no valid alternative action,
forcing the operator to manually intervene via `/context` +
`set-context-tokens` every time the counter goes stale.

This is a distinct bug from INFRA-245 (compact-aware counter refresh, this
same phase). INFRA-245 narrows the *frequency* of staleness by adding a
missing refresh trigger for one specific event (`/compact`). It does not
change which spawns the gate blocks, and does not cover every staleness path
(e.g. a stale counter that predates the current session for reasons other
than compaction). This story is orthogonal and complementary: even after
INFRA-245 lands, a mandatory step should not be interruptible by a
resource-conservation gate at all — the fix here is to stop gating `reviewer`
in the first place, regardless of how fresh or stale the counter is.

## Requires

- No dependency on INFRA-245 landing first or in any particular order — the
  two stories touch the same allowlist file for different reasons (INFRA-245
  changes when the counter refreshes; this story changes which subagent types
  the gate applies to) and do not conflict.
- `hooks/pre_tool_use.py`'s current `BUILD_CYCLE_SUBAGENTS` frozenset and
  `main()` dispatch, as read this session (frozenset ~line 59-65, Task/Agent
  dispatch ~line 102-120), is the baseline this story amends.

## Ensures

- `BUILD_CYCLE_SUBAGENTS` in `hooks/pre_tool_use.py` no longer contains
  `"reviewer"`. It contains exactly `{"builder", "loop-breaker",
  "security-auditor", "intent-reviewer"}`.
- A Task/Agent spawn with `tool_input.subagent_type == "reviewer"` always
  passes through (`sys.exit(0)`, empty stdout, no block) regardless of the
  state of `context_current_tokens` in `.companion/state.json` — including
  when the key is absent entirely, when it is present but stale relative to
  `context_session_reset_at`, and when it is present and numerically over the
  configured `context_budget_threshold`. In all three cases `decide()` must
  not be invoked for a `reviewer` spawn (proven the same way the existing
  non-allowlisted-subagent test proves it — a `context_budget.py` stub whose
  `decide()` raises, imported via `PYTHONPATH`, confirming the branch
  short-circuits before import).
- `builder`, `loop-breaker`, `security-auditor`, and `intent-reviewer` spawns
  remain gated exactly as before this change — the existing
  `test_allowlisted_subagent_type_still_gates` parametrization for those four
  types continues to pass unmodified.
- `hooks/pre_tool_use.py`'s module docstring and the `BUILD_CYCLE_SUBAGENTS`
  comment block are updated so neither claims `reviewer` is gated. The
  comment must state the new invariant precisely: the gate governs
  discretionary build-cycle spawns only (spawns where the orchestrator has a
  legitimate alternative action); it never gates a spawn that is the
  mandatory, only-valid next step in the build loop. `reviewer` is named
  explicitly as the exemption, with the one-sentence reasoning (mandatory
  pipeline step, no alternative action exists), so a future reader does not
  need to re-derive it from git history.
- Any docstring/comment in `skills/pairmode/scripts/context_budget.py` that
  enumerates or references the five build-cycle types (e.g. the string this
  session found at ~line 78-79, "build-cycle agent spawn
  (builder/reviewer/loop-breaker/security-auditor/intent-reviewer) that would
  normally refresh it") is corrected to reflect the new four-member set, or
  reworded so it does not imply `reviewer` is one of the gated types calling
  `decide()`. Do not touch `decide()`'s logic itself — this story changes
  only which subagent types reach it, never its internal behavior.
- `docs/architecture.md`'s § "Spawn contract: subagent_type resolution
  (INFRA-241)" section and the "9.5"-area context-budget section (both
  currently describing `BUILD_CYCLE_SUBAGENTS` as "the five build-cycle
  types") are updated to describe four gated types plus the `reviewer`
  exemption, with a one-line pointer to this story (INFRA-246) as the source
  of the change, following this doc's existing convention of citing the story
  ID that introduced each behavioral note.
- `tests/pairmode/test_pre_tool_use_hook.py`'s
  `test_allowlisted_subagent_type_still_gates` parametrization (~line
  357-360) no longer includes `"reviewer"` in its still-gated list.
- A new test (or tests) added to `tests/pairmode/test_pre_tool_use_hook.py`
  proves the `reviewer`-exemption behavior described in the second bullet
  above — modeled on the existing
  `test_non_allowlisted_subagent_type_passes_through_without_calling_decide`
  pattern (spy `context_budget.py` stub whose `decide` raises if called),
  parametrized or asserted across at minimum: missing
  `context_current_tokens`, and an over-ceiling `context_current_tokens`
  value that would block a `builder` spawn under the identical state.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run
  without `-x`; confirm only the known CER-070 environmental failure
  remains, per this project's pytest-no-x-before-merge convention).

## Instructions

1. In `hooks/pre_tool_use.py`, remove `"reviewer"` from the
   `BUILD_CYCLE_SUBAGENTS` frozenset literal (~line 59-65).
2. Update the frozenset's preceding comment block and the module docstring's
   description of the Task/Agent branch to state the new invariant: the gate
   applies only to discretionary/escalation build-cycle spawns
   (`builder`, `loop-breaker`, `security-auditor`, `intent-reviewer`);
   `reviewer` is exempt because it is the build loop's mandatory,
   deterministic next step after every builder attempt (per
   `CLAUDE.build.md`'s `on reviewer PASS` / `on reviewer FAIL` routing) and
   has no valid alternative action for the gate to preserve by blocking it.
3. No other logic in `main()`'s Task/Agent branch needs to change — the
   existing `if subagent_type not in BUILD_CYCLE_SUBAGENTS: sys.exit(0)` check
   now naturally passes `reviewer` through once it is removed from the set.
4. Grep `skills/pairmode/scripts/context_budget.py` for prose that names all
   five build-cycle types together (the INFRA-245 docstring addition at
   ~line 78-79 is one confirmed hit) and correct each hit to the new
   four-member set, or reword to avoid the implication that `reviewer` calls
   `decide()`. Do not change any executable logic in this file.
5. Update `docs/architecture.md`: the "Spawn contract: subagent_type
   resolution (INFRA-241)" section's "the five build-cycle types
   (`BUILD_CYCLE_SUBAGENTS`: `builder`, `reviewer`, `loop-breaker`,
   `security-auditor`, `intent-reviewer`)" line, and the context-budget
   section's "those five roles" line (~line 312), both need the count and
   membership corrected, with a short note citing INFRA-246 and the
   mandatory-step reasoning. Do not rewrite the surrounding INFRA-241
   historical narrative beyond what's needed for accuracy.
6. In `tests/pairmode/test_pre_tool_use_hook.py`:
   a. Remove `"reviewer"` from the `test_allowlisted_subagent_type_still_gates`
      parametrize list (~line 357-360).
   b. Add a new test (or a parametrized extension of an existing one) proving
      a `reviewer` spawn is never gated — assert passthrough (`sys.exit(0)`,
      empty stdout) under both a missing `context_current_tokens` state and
      an over-ceiling `context_current_tokens` state, using the spy-stub
      pattern from `test_non_allowlisted_subagent_type_passes_through_without_calling_decide`
      to prove `decide()` is never called (the stub's `decide()` raises;
      a passing test with empty stdout confirms the branch short-circuited).
      Also assert the acknowledgment keys (`context_budget_acknowledged_at`,
      `context_budget_acknowledged_user_turn_seq`) are not written to
      `state.json`, mirroring the existing non-allowlisted test's assertions.
7. Run the full test suite without `-x` and confirm only the known CER-070
   environmental failure remains.

## Out of scope

- Any change to `context_budget.decide()`'s internal logic, threshold
  calculation, or the "CONTEXT CHECK REQUIRED" / "CONTEXT BUDGET" block
  messages themselves — this story changes only which `subagent_type`s reach
  `decide()`, never what `decide()` does once called.
- INFRA-245's compact-aware counter refresh — a separate, complementary fix
  to *when* the counter goes stale, not *which spawns* are gated. Building
  this story does not require INFRA-245 and does not supersede it; both
  should land in this phase.
- Any change to `builder`, `loop-breaker`, `security-auditor`, or
  `intent-reviewer`'s gated status — those four remain gated exactly as
  today. This story does not re-derive or revisit whether they should be
  discretionary vs. mandatory; the operator has only made that determination
  for `reviewer`.
- Re-registering or renaming any `.claude/agents/*.md` shell files, or any
  change to the spawn/model contract established by INFRA-241 — this story
  only touches the context-budget allowlist, not the agent registration
  mechanism.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure;
new/updated coverage in `tests/pairmode/test_pre_tool_use_hook.py` proves a
`reviewer` spawn is never blocked by the context-budget gate (missing-tokens
and over-ceiling cases both pass through without `decide()` being called),
while `builder`/`loop-breaker`/`security-auditor`/`intent-reviewer` remain
gated exactly as before.
