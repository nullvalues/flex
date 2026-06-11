---
id: INFRA-171
rail: INFRA
title: "Estimation fallback — cross-phase global median + cross-rail story-cost-estimate"
status: planned
phase: "65"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_flex_build_story_cost.py
---

# INFRA-171 — Estimation fallback: cross-phase global median + cross-rail story-cost-estimate

## Context

Part D of the Phase 65 fix. Two estimation functions require ≥5 samples and fall back
to a static default when the threshold is not met. In practice, new phases and low-volume
rails almost never have 5 samples, so the fallback fires constantly:

- `estimate_next_step_tokens()` in `context_budget.py` — filters by `phase`, needs ≥5
  rows. Used by the hook's `decide()`. Falls back to `seeded_default` (53k).
- `_query_story_cost_samples()` / `story-cost-estimate` in `flex_build.py` — filters
  by `(rail, story_class)`, needs ≥5 PASS rows. Falls back to "insufficient data."

The fix: a waterfall fallback that makes progressively broader queries before giving up.

## Acceptance criteria

### `estimate_next_step_tokens` (context_budget.py)

1. If per-phase rows ≥ 5: use per-phase median (unchanged behavior).

2. If per-phase rows < 5 **and** global all-phases rows ≥ 5: use global all-phases
   median (new fallback). The function signature gains an optional `fallback_db_query`
   parameter or handles the extra query inline — either is acceptable.

3. If global rows < 5: use `seeded_default` (unchanged).

4. Tests cover: per-phase wins (≥5 per-phase rows), global-fallback wins
   (< 5 per-phase, ≥5 global), seeded fallback (< 5 global).

### `_query_story_cost_samples` / `story-cost-estimate` (flex_build.py)

5. If (rail, story_class) rows ≥ 5: use those (unchanged).

6. If (rail, story_class) < 5 **and** (all-rails, same story_class) ≥ 5: use
   all-rails same-class median as fallback. Output format:
   `estimate: N tokens (median of M PASS attempts, all rails, story_class=code)`

7. If all-rails same-class < 5 **and** all PASS rows ≥ 5: use global median.
   Output: `estimate: N tokens (median of M PASS attempts, global)`

8. If global < 5: "insufficient data" (unchanged).

9. Tests cover all four tiers.

## Implementation guidance

### context_budget.py — `estimate_next_step_tokens`

The function currently takes `(db_path, phase, seeded_default)` and queries:
```sql
SELECT tokens_total FROM attempts WHERE phase = ? AND tokens_total IS NOT NULL
```

Add a second query as fallback:
```sql
SELECT tokens_total FROM attempts WHERE tokens_total IS NOT NULL
```

No signature change needed (the global fallback is always attempted with the same
db_path); the two-tier logic lives inside the function.

### flex_build.py — `_query_story_cost_samples`

Currently returns rows for `(rail, story_class)`. Rename or extend to support the
three-tier waterfall:

```python
def _query_story_cost_samples(db_path, rail, story_class):
    # Tier 1: specific rail + story_class
    rows = _query(db_path, "WHERE rail=? AND story_class=? AND outcome='PASS'", rail, story_class)
    if len(rows) >= _COST_MIN_SAMPLE:
        return rows, "rail"
    # Tier 2: all rails, same story_class
    rows = _query(db_path, "WHERE story_class=? AND outcome='PASS'", story_class)
    if len(rows) >= _COST_MIN_SAMPLE:
        return rows, "all-rails"
    # Tier 3: all PASS rows
    rows = _query(db_path, "WHERE outcome='PASS'")
    if len(rows) >= _COST_MIN_SAMPLE:
        return rows, "global"
    return rows, "insufficient"
```

`cmd_story_cost_estimate` adjusts the output line to reflect which tier was used.
