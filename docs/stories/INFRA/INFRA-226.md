---
id: INFRA-226
rail: INFRA
title: Add fable as an escalation-tier model; document mandatory custom-model entry at model-upgrade gates
status: complete
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/model_selector.py
  - skills/pairmode/scripts/next_action.py
  - CLAUDE.build.md
  - tests/pairmode/test_model_selector.py
  - tests/pairmode/test_next_action.py
touches:
  - docs/architecture.md
---

## Context

Discovered live: forqsite's own build session hit a model-upgrade prompt and
the operator wanted to key in `fable` as the upgrade choice, but `fable`
doesn't exist anywhere in `model_selector.py`'s vocabulary — the module only
knows a strict three-rung ladder (`haiku` < `sonnet` < `opus`), and the
"ask the user" flow at a model-upgrade gate isn't codified in
`CLAUDE.build.md` at all (each orchestrator session has been improvising its
own `AskUserQuestion` ad hoc). Separately, `next_action.py`'s loop-breaker
dispatch (Row 6: `attempt_count == 2 and last_attempt_outcome == FAIL`,
`next_action.py:1055-1066`) hardcodes `model="opus"` inline — no selector
function, no way to escalate further when opus itself has already failed
twice.

Operator direction (2026-07-22): `fable` ranks **above** `opus` in the
escalation ladder, specifically for retry-upgrade/methodology-upgrade
escalation and loop-breaker-adjacent situations (i.e., the point where the
harness has already tried its normal top tier and failed). The model list
itself does not need to stay perpetually current — but the harness must
always let an operator key in an arbitrary model name at any model-selection
judgment-handoff, not just whatever tiers happen to be enumerated in code.

## Requires

- `model_selector.py`'s existing `MODEL_HAIKU`/`MODEL_SONNET`/`MODEL_OPUS`
  constants and `select_builder_model`/`select_reviewer_model` functions
  (current form, confirmed present this session).
- `next_action.py`'s Row 6 loop-breaker dispatch (`next_action.py:1055-1066`),
  confirmed to hardcode `model="opus"` with no selector function backing it.
- `record_attempt.py --model` is already free-text (no `Choice()` constraint)
  — confirmed this session; no change needed there.

## Ensures

- `model_selector.py` defines `MODEL_FABLE = "fable"` and
  `REASON_ESCALATION_UPGRADE = "escalation-upgrade"` constants.
- A new function `select_loop_breaker_model() -> tuple[str, str]` exists in
  `model_selector.py`, returning `(MODEL_FABLE, REASON_ESCALATION_UPGRADE)`.
  Deterministic, no arguments beyond what's needed — this is the loop-breaker
  rung's dedicated selector, mirroring the existing
  `select_intent_reviewer_model`/`select_security_auditor_model` pattern.
- `next_action.py`'s Row 6 (`next_action.py:1055-1066`) calls
  `select_loop_breaker_model()` instead of hardcoding `model="opus"` — the
  loop-breaker now dispatches on `fable` by default.
- `model_selector.py`'s module docstring is updated to document the new
  function and the `fable` tier's place in the ladder (above `opus`, used
  for loop-breaker/escalation situations only — not inserted into the
  ordinary `select_builder_model`/`select_reviewer_model` attempt-1/attempt-2
  tables, which stay haiku/sonnet/opus as-is per operator direction).
- `CLAUDE.build.md` gains an explicit subsection (near the existing model
  selection references, or under the build loop) documenting: whenever
  `next-action` returns `await-user` with a model-selection reason
  (`model-upgrade`, or any future judgment-handoff reason involving a model
  choice), the orchestrator's `AskUserQuestion` **must** include a way for
  the operator to key in any model name — not just the suggested model and
  a baseline fallback. `AskUserQuestion`'s built-in "Other" free-text option
  satisfies this; the instruction exists so this isn't left to each
  session's improvisation (as it was before this story).
- Existing test `TestResolveNextActionSpawnLoopBreaker::test_row_6_double_fail`
  (`tests/pairmode/test_next_action.py:850-867`) is updated to assert
  `action["model"] == "fable"` (an intentional behavior change, not a
  regression) — and continues to assert `action["meta"]["fail_rung"] ==
  "double-fail"` unchanged.
- A new regression test for `select_loop_breaker_model()` exists in
  `tests/pairmode/test_model_selector.py`, asserting it returns exactly
  `("fable", "escalation-upgrade")`.
- `docs/architecture.md`'s "Loop-breaker" bullet (build-loop mechanics list,
  currently reading "the orchestrator invokes the loop-breaker subagent
  (opus)") is updated to say `fable`, not `opus`.
- `docs/architecture.md`'s model-pinning "Default" note (currently reading
  "The `loop-breaker` is the one exception: it is opus by default, because
  by the time the loop-breaker fires the case is — by definition — hard,
  and the reasoning premium is justified") is updated to name `fable`
  instead of `opus`, preserving the same justification (the reasoning
  premium at the double-fail rung), and phrased so it stays consistent with
  `model_selector.py`'s new "escalation tier ranking above opus" framing.
- No other content in `docs/architecture.md` is modified.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. In `skills/pairmode/scripts/model_selector.py`:
   a. Add `MODEL_FABLE = "fable"` alongside the existing `MODEL_HAIKU`/
      `MODEL_SONNET`/`MODEL_OPUS` constants.
   b. Add `REASON_ESCALATION_UPGRADE = "escalation-upgrade"` alongside the
      existing `REASON_*` constants.
   c. Add `select_loop_breaker_model() -> tuple[str, str]`, returning
      `(MODEL_FABLE, REASON_ESCALATION_UPGRADE)`. No parameters — this rung
      is unconditional (loop-breaker is only ever reached at the
      double-fail rung, per `next_action.py` Row 6).
   d. Update the module docstring: add `select_loop_breaker_model` to the
      "Public API" list with its own short description, and add a one-line
      note near the existing selection tables that `fable` is the
      escalation tier above `opus`, used only by the loop-breaker rung —
      not part of the ordinary builder/reviewer attempt-based tables.
2. In `skills/pairmode/scripts/next_action.py`, Row 6 (`next_action.py:1055-1066`):
   replace the hardcoded `model="opus"` with a call to
   `select_loop_breaker_model()` (import it alongside the other
   `model_selector` imports already used in this file), using its returned
   model string. The `reason=""` field on this action can stay `""` (Row 6's
   existing convention — the reason lives in `meta["fail_rung"]`, not the
   top-level `reason` field) unless doing so conflicts with `validate_action`
   — check and adjust only if necessary.
3. In `CLAUDE.build.md`, add a short subsection (placement: wherever reads
   most naturally alongside the existing build-loop description — e.g. near
   where `await-user` / model-selection actions are discussed, or as a new
   "Model-upgrade prompts" subsection under the build loop) stating: at any
   `await-user` action whose reason involves a model choice, present the
   suggested/default model(s) as named options via `AskUserQuestion`, and
   always leave room for the operator to key in an arbitrary model name
   (e.g. via `AskUserQuestion`'s "Other" input) — the enumerated tiers in
   `model_selector.py` are not guaranteed to be current or exhaustive.
4. Update `tests/pairmode/test_next_action.py::TestResolveNextActionSpawnLoopBreaker::test_row_6_double_fail`
   to assert `action["model"] == "fable"` instead of `"opus"`.
5. Add the new `select_loop_breaker_model()` regression test to
   `tests/pairmode/test_model_selector.py` (create the file if it does not
   already exist, following the existing test file's conventions for the
   other `select_*` functions).
6. Run the full suite and confirm green.

## Out of scope

- Any change to the ordinary `select_builder_model`/`select_reviewer_model`
  attempt-1/attempt-2 tables — those stay haiku/sonnet/opus exactly as they
  are today. `fable` is additive at the loop-breaker/escalation rung only,
  per operator direction.
- Building any mechanism to keep the model list "always current" (e.g.
  fetching a live model catalog) — operator explicitly declined this as
  impractical; the fix is the custom-entry path, not an auto-updating list.
- Any change to `record_attempt.py`'s `--model` handling — already free-text,
  confirmed no change needed.
- Retrofitting this session's own ad hoc `AskUserQuestion` prompts (e.g. the
  ones already asked during RELEASE-042/INFRA-225's model-upgrade gates) —
  this story only fixes the mechanism and documents the convention going
  forward.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: full suite green, including the updated Row 6 assertion
(`model == "fable"`) and the new `select_loop_breaker_model()` regression
test.
