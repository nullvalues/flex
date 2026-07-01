---
id: INFRA-165
rail: INFRA
title: "`context_budget.py` flex_factor correctness — NaN clamp + `render_alert_prompt` ceiling"
status: complete
phase: "HARNESS007-main"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - tests/pairmode/test_context_budget.py
touches: []
---

# INFRA-165 — `context_budget.py` flex_factor correctness

## Context

Two bugs introduced by INFRA-160 (Phase 63), found in the cold-eyes review
(findings 2, 5):

1. The `flex_factor` clamp guard (`<= 0` and `> 5.0`) does not catch NaN.
   `float('nan') <= 0` and `float('nan') > 5.0` are both False (IEEE-754),
   so NaN passes through. `ceiling = threshold * (1+overrun_pct) * NaN = NaN`
   and `(current + expected) > NaN` is always False — the gate never fires
   at any token count.

2. `render_alert_prompt` computes the displayed remaining-tokens value using
   the un-factored ceiling `threshold * (1 + overrun_pct)`. When
   `flex_factor != 1.0` the block was triggered at a different (factored)
   ceiling, so the `[R]` value shown to the orchestrator contradicts the
   actual decision.

## Ensures

### `skills/pairmode/scripts/context_budget.py`

1. **NaN guard.** `import math` added at the top of the file (stdlib).
   Inside `decide()`, the NaN check is inserted *before* the existing
   `<= 0` check:
   ```python
   if math.isnan(flex_factor):
       print(
           "context_budget.decide: flex_factor is NaN; clamped to 1.0",
           file=sys.stderr,
       )
       flex_factor = 1.0
   if flex_factor <= 0:
       ...
   ```
   The two existing guards and their warning messages are unchanged.

2. **`render_alert_prompt` receives `flex_factor`.** The function signature
   gains an optional parameter (appended, default 1.0):
   ```python
   def render_alert_prompt(
       story_id,
       tokens,
       threshold,
       overrun_pct,
       expected_next,
       flex_factor: float = 1.0,
   ) -> str:
   ```
   The ceiling line inside the function changes from:
   ```python
   ceiling = int(threshold * (1.0 + overrun_pct))
   ```
   to:
   ```python
   ceiling = int(threshold * (1.0 + overrun_pct) * flex_factor)
   ```
   The call site in `decide()` passes the validated `flex_factor`:
   ```python
   return render_alert_prompt(
       story_id, current_tokens, threshold, overrun_pct, expected_next,
       flex_factor,
   )
   ```

3. All existing call sites of `render_alert_prompt` that do not pass
   `flex_factor` continue to work identically (default 1.0 = no change).

### `tests/pairmode/test_context_budget.py`

4. New test cases:

   - **`test_flex_factor_nan_clamped`** — call `decide()` with
     `flex_factor=float('nan')`, current tokens below normal ceiling. Assert
     return is `None` (passes, same as default 1.0 behaviour). Assert stderr
     contains `"NaN"`.

   - **`test_render_alert_prompt_factored_ceiling`** — call
     `render_alert_prompt(story_id="S", tokens=70000, threshold=120000,
     overrun_pct=0.10, expected_next=1000, flex_factor=0.5)`. Assert the
     returned string contains `"[R] -5000"` or the equivalent value derived
     from `ceiling = int(120000 * 1.10 * 0.5) = 66000`,
     `remaining = 66000 − 70000 = −5000`.

   - **`test_decide_alert_uses_factored_ceiling`** — full `decide()` call
     with `flex_factor=0.5`, `threshold=120000`, `overrun_pct=0.10`,
     `current_tokens=70000`, `expected_step_tokens=1000`. Assert the returned
     block dict's `"output"` field contains the string `"-5000"` (negative
     remaining confirms factored ceiling is used).

5. All existing tests continue to pass.

## Instructions

- `import math` goes at the top of `context_budget.py` with existing stdlib
  imports. No new dependencies.
- The NaN check must be placed first, before `<= 0`, so that NaN does not
  accidentally satisfy `<= 0` on some Python implementations (though in
  CPython `NaN <= 0` is reliably False, ordering still makes intent clear).
- Do not restructure `render_alert_prompt` or `decide()` beyond the two
  named changes.
- The `test_render_alert_prompt_factored_ceiling` test calls
  `render_alert_prompt` directly; it does not need a full `decide()` setup.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget.py -x -q
```

All tests must pass.

## Out of scope

- Wiring `flex_factor` from story frontmatter through `hooks/pre_tool_use.py`
  into `decide()` (Phase 65 / when the hook reads the story file).
- Any change to the clamp range (currently [1.0 default for invalid, 5.0 max]).
