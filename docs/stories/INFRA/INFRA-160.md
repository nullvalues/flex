---
id: INFRA-160
rail: INFRA
title: "`flex_factor` frontmatter field — read path through `context_budget.decide()`"
status: planned
phase: "63"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/context_budget.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_flex_build_story_cost.py
touches: []
---

# INFRA-160 — `flex_factor` frontmatter field + read path through `context_budget.decide()`

## Context

`flex_factor` is a per-story override of the effective context ceiling
(phase doc D9). When a story is known to be larger than average — a
long-running refactor, a multi-file scaffolding task — the spec writer
sets `flex_factor: 1.3` in the story frontmatter to widen the ceiling
by 30% for that story only. Values <1.0 tighten the ceiling for
"small" stories.

Effective ceiling when flex_factor is set:
  `threshold × (1 + overrun_pct) × flex_factor`

Phase 63 is read-only: `flex_factor` is parsed from frontmatter and
applied in `context_budget.decide()`. The SPA surfaces it (INFRA-159).
Phase 64 will add a SPA control to set it.

## Ensures

### `skills/pairmode/scripts/flex_build.py`

1. `_read_story_frontmatter` already returns a dict of frontmatter keys.
   After this story, the returned dict includes `flex_factor: float`
   (default `1.0` when the key is absent or non-numeric).

2. `story-cost-estimate` subcommand output is unchanged. The `flex_factor`
   is not surfaced in the cost-estimate output (it affects the gate, not
   the estimate).

3. No new subcommands added. No changes to `set-context-tokens`,
   `current-phase`, or any other subcommand.

### `skills/pairmode/scripts/context_budget.py`

4. The `decide()` function signature gains an optional `flex_factor: float = 1.0`
   parameter:
   ```python
   def decide(
       state: dict,
       flex_factor: float = 1.0,
   ) -> DecideResult:
   ```

5. The effective ceiling inside `decide()` is updated from:
   ```python
   ceiling = threshold * (1.0 + overrun_pct)
   ```
   to:
   ```python
   ceiling = threshold * (1.0 + overrun_pct) * flex_factor
   ```

6. All call sites of `decide()` that do not pass `flex_factor` continue to
   work identically (default 1.0 = no change in behaviour).

7. `flex_factor` is validated: values ≤ 0 are clamped to 1.0 with a warning
   to stderr. Values > 5.0 are clamped to 5.0 with a warning to stderr.
   These are guardrails against runaway specs.

8. The hook dispatch path (`hooks/pre_tool_use.py` → `context_budget.py`)
   does not pass `flex_factor` in this story — it uses the default 1.0.
   Phase 64 will wire the story frontmatter value through the hook.

### `tests/pairmode/test_context_budget.py`

9. Existing tests continue to pass unchanged (default `flex_factor=1.0`
   preserves all current behaviour).

10. New test cases:

    - **`test_flex_factor_widens_ceiling`** — threshold 120000, overrun_pct
      0.10, flex_factor 1.5. Current tokens 170000. Assert `decide()` returns
      `allow` (ceiling = 120000 × 1.10 × 1.50 = 198000 > 170000).

    - **`test_flex_factor_tightens_ceiling`** — threshold 120000, overrun_pct
      0.10, flex_factor 0.5. Current tokens 70000. Assert `decide()` returns
      `block` (ceiling = 120000 × 1.10 × 0.50 = 66000 < 70000).

    - **`test_flex_factor_default_unchanged`** — threshold 120000,
      overrun_pct 0.10, flex_factor omitted. Current tokens 125000.
      Assert same result as before this story.

    - **`test_flex_factor_clamped_at_zero`** — flex_factor=0. Assert clamped
      to 1.0 (warning to stderr, behaviour unchanged from default).

    - **`test_flex_factor_clamped_at_high`** — flex_factor=10.0. Assert
      clamped to 5.0.

### `tests/pairmode/test_flex_build_story_cost.py`

11. Existing tests pass unchanged. `_read_story_frontmatter` returning
    `flex_factor: 1.0` for stories without the field is verified by
    checking an existing story fixture.

## Instructions

- `flex_factor` parsing in `_read_story_frontmatter`: use `float(fm.get("flex_factor", 1.0) or 1.0)`.
  Wrap in try/except ValueError to default to 1.0 on non-numeric values.
- The `decide()` change is minimal — one multiplication. Do not restructure
  the function.
- The clamp logic: `if flex_factor <= 0: warn; flex_factor = 1.0`.
  `if flex_factor > 5.0: warn; flex_factor = 5.0`.

## Out of scope

- Reading `flex_factor` from the story file inside the hook dispatch path
  (Phase 64).
- Surfacing `flex_factor` in the effort DB or attempt records.
- Setting `flex_factor` from the SPA (Phase 64).
- Changing the `story-cost-estimate` output format.
