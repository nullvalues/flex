---
id: INFRA-174
rail: INFRA
title: "Seed `context_current_tokens` in `_record_state()` to skip manual bootstrap step"
status: complete
phase: "67"
story_class: code
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_context_budget.py
---

# INFRA-174 — Seed `context_current_tokens` in `_record_state()` to skip manual bootstrap step

**Phase:** 67  
**Rail:** INFRA  
**Status:** planned

## Problem

When pairmode is bootstrapped into a new repo, `_record_state()` creates
`state.json` and seeds context-budget thresholds (`context_budget_threshold`,
`context_budget_overrun_pct`, `expected_step_tokens`,
`context_budget_reprompt_margin`) but does **not** seed `context_current_tokens`.

As a result, the very first build attempt hits `context_budget.decide()` →
`read_context_tokens_from_state()` returns `None` → `decide()` returns the
CONTEXT CHECK REQUIRED block, forcing a manual `/context` read and
`set-context-tokens` call before any build can proceed.

## Fix

In `bootstrap.py::_record_state()`, add one line to the `if is_new_state:` block:

```python
data.setdefault("context_current_tokens", 1)
```

`1` is the minimum positive integer that passes the `value <= 0` guard in
`read_context_tokens_from_state`. It produces `(1 + expected_next) < ceiling`
(~53 001 vs ~132 000), so the first build step proceeds without blocking.

No TTL (`context_current_tokens_recorded_at`) is seeded — the staleness check
short-circuits on a missing `recorded_at` and returns the value as-is, which
is fine: the orchestrator's `set-context-tokens` call will replace `1` with the
real value before the first actual build step.

## Acceptance criteria

1. After `_record_state()` creates a new `state.json`, the file contains
   `"context_current_tokens": 1`.
2. `context_budget.decide()` called with that fresh `state.json` returns `None`
   (no block) — not CONTEXT CHECK REQUIRED.
3. Existing `state.json` files (with real token values) are unaffected — the
   `setdefault` only fires during the `is_new_state` branch.
4. All existing tests pass.

## Primary files

- `skills/pairmode/scripts/bootstrap.py`

## Touches

- `tests/pairmode/test_bootstrap.py` (add test for criterion 1)
- `tests/pairmode/test_context_budget.py` (add test for criterion 2)
