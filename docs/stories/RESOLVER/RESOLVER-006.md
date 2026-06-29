---
id: RESOLVER-006
rail: RESOLVER
title: CF-1 / CER-060 — retry-path model composition fix (DP7)
status: planned
phase: "HARNESS002-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_next_action_compose.py
touches:
  - tests/pairmode/test_next_action.py
---

## Context

The bundled carry-forward fix CF-1 ← CER-060 (agreements `HARNESS002-main.md`
DP7.2 + the Carry-forward section). HARNESS002 already opens `next_action.py` for
the DP4 action, so CF-1 is naturally co-located here rather than promoted to a
standalone phase.

**The defect:** `resolve_next_action` Row 5 (attempt-1 FAIL → spawn attempt 2,
`retry-upgrade`) **hardcodes** `model="opus"` and `reason="retry-upgrade"`
instead of delegating to the selector. Behaviour is correct *today* (it matches
the `model_selector` table: any `code` story at attempt ≥ 2 → opus /
`retry-upgrade`), but the retry tier is now encoded in **two places**. Root
cause: `infer_position` computes `builder_model` at
`select_builder_model(..., attempt_number=max(attempt_count, 1))`, i.e. one
attempt **behind** the retry spawn — at Row 5 the Position holds the attempt-1
model, so the state machine cannot emit `position.builder_model` and must
hardcode opus. If a future phase rebalances the selector table, the state machine
silently diverges.

**The fix (DP7.2, option 1 — preferred):** on inferred **FAIL**, have
`infer_position` compute the Position's `builder_model` at the *next* attempt
number (`attempt_count + 1`), so Row 5 emits `position.builder_model` and the
**selector is the single source of the retry tier** (true DP5 composition). The
acceptance must verify **no other row regresses** — Row 2 / first attempt must
still resolve the attempt-1 model. Closes CER-060.

## Requires

- RESOLVER-005 complete: `next_action.py` is already opened for the
  `spawn-gate-worker` action in this phase; this story builds on that same file
  to avoid two phases touching the resolver. (No functional dependency on the
  worker — this is a self-contained composition fix.)
- RESOLVER-002/-003 (inherited): `infer_position` and `resolve_next_action`
  exist; the DP5 compose guard `test_next_action_compose.py` exists.

## Ensures

- `infer_position` computes `builder_model` / `builder_model_reason` at the
  **next** attempt number when the inferred outcome is FAIL: i.e. when
  `last_attempt_outcome == "FAIL"`, the selector is called with
  `attempt_number = attempt_count + 1`; otherwise (`none`/`PASS`/`unknown`) it
  is called as today with `attempt_number = max(attempt_count, 1)`.
- Row 5 of `resolve_next_action` emits **`position.builder_model`** and
  **`position.builder_model_reason`** (no longer the hardcoded `model="opus"` /
  `reason="retry-upgrade"`); the selector is the single source of the retry tier.
- **No other row regresses:**
  - Row 2 (first attempt, `attempt_count == 0`, outcome `none`) still resolves
    the **attempt-1** model (e.g. `sonnet` / `auto-baseline` for a small `code`
    story).
  - Row 8 (PASS, next story attempt 1) still resolves an attempt-1 model.
  - Rows 6/7 (further FAIL ladder) behave as before (Row 6 still spawns the
    loop-breaker; Row 7 still pauses).
- The two-places encoding is removed: `next_action.py` no longer hardcodes the
  retry model in Row 5.
- `test_next_action_compose.py` gains a **call-site coverage** assertion (the
  DP5 guard previously asserted import-*presence* only, not coverage): Row 5's
  emitted model equals `select_builder_model(<code story>, ...,
  attempt_number=2)[0]`, so a future selector-table rebalance fails loudly here
  rather than silently diverging.
- The resolver stays **pure-read** (no durable state introduced); `grep`
  confirms no `write_text` / `json.dump` added.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes,
  including the existing RESOLVER-004 state matrix unchanged.

## Instructions

- Make the `attempt_number` adjustment in `infer_position`'s model-selection
  block (§4). Compute the effective attempt-for-selection as
  `attempt_count + 1` only on FAIL, else `max(attempt_count, 1)`. Keep it a
  single, readable conditional — do not duplicate the selector call.
- In Row 5 of `resolve_next_action`, replace the literal `model="opus"` /
  `reason="retry-upgrade"` with `builder_model` / `builder_model_reason` from the
  Position (falling back defensively only if `builder_model is None`).
- Verify the RESOLVER-004 exhaustive matrix (`test_next_action_states.py`) still
  passes unchanged — if a row's expected model shifts, that is a regression to
  investigate, not a test to loosen. (Row 5's expectation may need updating to
  read the selector value rather than the literal `opus`; that is acceptable as
  it now reflects the real composition. Confirm the *value* is still opus for the
  matrix's `code` story.)
- The compose-guard addition is the DP7.2 "single source" protection — name the
  drifted function in the failure message so a future selector change is loud.

## Tests

Extend `tests/pairmode/test_next_action_compose.py` (call-site coverage) and add
a focused Row-2-vs-Row-5 attempt-number case to `tests/pairmode/test_next_action.py`:

- Row 5 emitted `model` == `select_builder_model(code-story, ...,
  attempt_number=2)[0]`, and `reason` == that call's reason (`retry-upgrade`).
- Row 2 first-attempt `model` == `select_builder_model(code-story, ...,
  attempt_number=1)[0]` (regression guard — first attempt stays attempt-1).
- `infer_position` on a FAIL position returns a `builder_model` computed at
  `attempt_count + 1`; on a `none`/first-launch position it returns the
  attempt-1 model.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_compose.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action_states.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: Row 5 model is selector-sourced; Row 2 stays attempt-1; full suite
(incl. the RESOLVER-004 matrix) green. CER-060 closes on this build.

### Out of scope

- The gate worker, verdict grammar, and `spawn-gate-worker` routing
  (WORKER-001/002, RESOLVER-005).
- The exhaustive isolation matrix (DP8) — WORKER-003 carries the consolidated
  CF-1 regression alongside the rest.
- Wiring into the live `CLAUDE.build.md` loop (the flip — HARNESS006).
