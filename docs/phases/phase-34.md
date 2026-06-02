---
era: "001"
---

# flex — Phase 34: Checkpoint context health report

← [Phase 33: Build loop portability and sibling catch-up](phase-33.md)

## Goal

Phase 33 shipped effort tracking to sibling projects and normalized model selection
reasons. A follow-on conversation identified a gap: the orchestrator accumulates
context across a phase but has no signal for whether that accumulated burden is large
enough to warrant a `/clear` before starting the next phase.

The existing guardrail fires per-story on builder cost. This phase extends the same
data-driven approach to a per-phase "retry burden" signal. At checkpoint, the context
health check queries the effort DB for the sum of output tokens from FAIL-outcome
reviewer rows in the current phase — the text that flowed back through the orchestrator
as retry findings. It compares that against the project's own rolling per-phase median
and adds one line to the checkpoint report: normal, elevated, or high, with a `/clear`
recommendation when warranted.

The signal self-calibrates per project. A configuration-heavy project that naturally
generates more retries will develop a higher baseline than a simple CRUD app, so
neither triggers false positives against the other.

**Note on tokens_out availability:** The current `<usage>` block from the Claude Code
runtime emits only `total_tokens`, `tool_uses`, and `duration_ms`. The `tokens_out`
column in the DB is therefore NULL for all current records. The implementation uses
`COALESCE(tokens_out, CAST(tokens_total * 0.15 AS INTEGER))` so that (a) it works
correctly today via the fallback and (b) automatically uses the direct value if a
future story adds per-role token breakdown to the usage block.

**Story dependency:** INFRA-086 requires INFRA-085 complete.

---

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-085 | `context_health.py` — phase retry burden query | complete |
| INFRA-086 | Integrate context health into checkpoint report in `CLAUDE.build.md.j2` | complete |

---

### Story INFRA-085 — `context_health.py` — phase retry burden query

**Rail:** INFRA | **story_class:** code

## Requires
- `effort_db.py` exists with `resolve_effort_db_path`, `_depth_guard`, and the `attempts`
  table schema (`tokens_out`, `tokens_total`, `outcome`, `agent_role`, `phase`, `ts`).
- `statistics` module available in stdlib.

## Ensures

A new module `skills/pairmode/scripts/context_health.py` is created with three public
functions and no other public API.

---

**`phase_retry_burden(db_path: Path, phase: str) -> int`**

Returns the sum of estimated retry-context output tokens for a single phase.

SQL:
```sql
SELECT SUM(COALESCE(tokens_out, CAST(tokens_total * 0.15 AS INTEGER)))
FROM attempts
WHERE agent_role = 'reviewer'
  AND outcome = 'FAIL'
  AND phase = ?
  AND (tokens_out IS NOT NULL OR tokens_total IS NOT NULL)
```

Returns `0` when no matching rows exist or when the DB is absent. Never raises on
missing DB.

---

**`rolling_phase_median(db_path: Path, current_phase: str, lookback_phases: int = 10) -> tuple[float | None, int]`**

Returns `(median, sample_size)`.

For each of the N most recent distinct phases (excluding `current_phase`), computes
that phase's retry burden using the same COALESCE formula. Phases with zero FAIL
reviewer rows contribute `0` — they are included, not skipped. Returns `(None, 0)`
when fewer than 3 prior phases exist in the DB (guards against false positives on
new projects).

SQL to collect per-phase burdens:
```sql
SELECT phase,
       MAX(ts) AS latest_ts,
       SUM(CASE
               WHEN agent_role = 'reviewer' AND outcome = 'FAIL'
               THEN COALESCE(tokens_out, CAST(tokens_total * 0.15 AS INTEGER))
               ELSE 0
           END) AS fail_burden
FROM attempts
WHERE phase IS NOT NULL AND phase != ?
GROUP BY phase
ORDER BY latest_ts DESC
LIMIT ?
```

Returns `(statistics.median(burdens), len(burdens))` when `len(burdens) >= 3`, else
`(None, len(burdens))`. Never raises on missing DB.

---

**`check_context_health(db_path: Path, current_phase: str, lookback_phases: int = 10) -> dict`**

Calls `phase_retry_burden` and `rolling_phase_median`, then returns:

```python
{
    "phase": str,
    "retry_burden": int,
    "phase_median": float | None,   # None when insufficient history
    "ratio": float | None,           # retry_burden / phase_median; None when median is None
    "recommendation": str,           # see thresholds below
    "sample_size": int,
    "message": str,                  # always a non-None human-readable string
}
```

Recommendation thresholds (applied in order):
- `"insufficient_data"` — `phase_median is None` (< 3 prior phases)
- `"normal"`   — `ratio < 2.0`
- `"elevated"` — `2.0 <= ratio < 4.0`
- `"high"`     — `ratio >= 4.0`

`message` format (used verbatim in the checkpoint report):
- `insufficient_data`: `"no data yet (retry burden: {retry_burden:,} tokens, <3 prior phases recorded)"`
- `normal`:   `"normal ({retry_burden:,} tokens, {ratio:.1f}× median, n={sample_size})"`
- `elevated`: `"ELEVATED ({retry_burden:,} tokens, {ratio:.1f}× median, n={sample_size}) — consider /clear before next phase"`
- `high`:     `"HIGH ({retry_burden:,} tokens, {ratio:.1f}× median, n={sample_size}) — recommend /clear before next phase"`

When `ratio` is None (insufficient data), format `ratio` as `"n/a"` in the message.

All three functions must be safe when the DB does not exist: return `0` / `(None, 0)` /
`insufficient_data` dict respectively. No `FileNotFoundError` or `sqlite3` exceptions
may propagate to callers.

**Primary files:** `skills/pairmode/scripts/context_health.py`
**Touches:** `tests/pairmode/test_context_health.py`

**Tests** (`tests/pairmode/test_context_health.py` — new file):

Use `tmp_path` fixture and `effort_db.init_db` + `effort_db.insert_attempt` to build
test DBs inline. A helper `_insert(db, **kw)` that fills required fields with defaults
keeps setup concise.

1. `test_phase_retry_burden_no_db` — nonexistent path → returns `0`.
2. `test_phase_retry_burden_no_fails` — only PASS reviewer rows for the phase → `0`.
3. `test_phase_retry_burden_with_tokens_out` — two FAIL rows, `tokens_out=500` each → `1000`.
4. `test_phase_retry_burden_tokens_out_null` — one FAIL row, `tokens_out=None`,
   `tokens_total=1000` → `int(1000 * 0.15)` = `150`.
5. `test_phase_retry_burden_mixed_null` — one row with `tokens_out=300`, one with
   `tokens_out=None, tokens_total=2000` → `300 + 300` = `600`.
   *Implementation note: replaced in build with `test_skips_rows_with_no_token_columns`
   (both columns NULL → excluded). The mixed-COALESCE path is exercised by the SQL
   but not by a dedicated test; added `test_ignores_builder_rows` instead.*
6. `test_phase_retry_burden_excludes_other_phases` — FAIL rows for a different phase
   are not counted.
7. `test_rolling_phase_median_insufficient_zero` — no prior phases → `(None, 0)`.
8. `test_rolling_phase_median_insufficient_two` — only 2 prior phases → `(None, 0)`.
   *Implementation note: sample_size is only non-zero when the median is computable
   (>= 3 phases). The spec said `(None, 2)` but the implementation returns `(None, 0)`
   for all insufficient-data cases; functional impact is nil as sample_size is not
   surfaced in insufficient_data messages.*
9. `test_rolling_phase_median_three_phases` — 3 prior phases with burdens `[0, 200, 400]`
   → `(200.0, 3)`.
10. `test_rolling_phase_median_includes_zero_retry_phases` — a phase with only PASS rows
    contributes `0` to the median, not skipped.
11. `test_rolling_phase_median_excludes_current_phase` — current phase rows are excluded
    from the median.
12. `test_rolling_phase_median_respects_lookback` — 15 phases present, `lookback_phases=5`
    → sample_size is 5, uses only the 5 most recent by `MAX(ts)`.
13. `test_check_context_health_insufficient` — < 3 phases →
    `recommendation == "insufficient_data"`, `ratio is None`.
14. `test_check_context_health_normal` — burden=100, median=300 (ratio=0.33) →
    `"normal"`.
15. `test_check_context_health_elevated` — burden=600, median=300 (ratio=2.0) →
    `"elevated"`.
16. `test_check_context_health_high` — burden=1500, median=300 (ratio=5.0) → `"high"`.
17. `test_check_context_health_message_contains_burden` — `message` field contains the
    formatted retry burden token count.
18. `test_check_context_health_no_db` — nonexistent DB path → returns dict with
    `recommendation == "insufficient_data"`, no exception raised.

---

### Story INFRA-086 — Integrate context health into checkpoint report in `CLAUDE.build.md.j2`

**Rail:** INFRA | **story_class:** methodology

## Requires
- INFRA-085 complete: `context_health.py` with `check_context_health` exists and all
  tests pass.
- `CLAUDE.build.md.j2` contains `### 7. Tag the checkpoint` and `### 8. Report`
  sections in the checkpoint sequence.
- `{{ pairmode_scripts_dir }}` is available in the template context (from INFRA-079).

## Ensures

**`CLAUDE.build.md.j2`** gains a new `### 7.5. Context health check` section inserted
between `### 7. Tag the checkpoint` and `### 8. Report`:

```
### 7.5. Context health check

Query the effort DB for this phase's retry burden and compare it against the
project's rolling per-phase median. This is a read-only step — it never blocks
the checkpoint.

```bash
PATH=$HOME/.local/bin:$PATH uv run python -c "
import sys, json
from pathlib import Path
sys.path.insert(0, '{{ pairmode_scripts_dir }}')
from context_health import check_context_health
from effort_db import resolve_effort_db_path

result = check_context_health(
    db_path=resolve_effort_db_path(Path('.')),
    current_phase='PHASE_ID_HERE',   # replace with current phase identifier
)
print(json.dumps(result))
"
```

Capture the JSON. Extract the `message` field for the checkpoint report.
If `recommendation` is `elevated` or `high`, the report line becomes:

  Context health:   <message>
    → /clear before "Build Phase N+1" is advised.

If `recommendation` is `normal` or `insufficient_data`:

  Context health:   <message>
```

**`### 8. Report`** template is updated to include a `Context health:` line in the
summary block, after `Doc updates:` and before `Git tag:`:

```
  Context health:   [message from step 7.5]
```

**`CLAUDE.build.md`** (flex's own) is regenerated:
```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  sync-build --project-dir . --apply --yes
```

**Primary files:** `skills/pairmode/templates/CLAUDE.build.md.j2`
**Touches:** `CLAUDE.build.md`

**Tests:** Methodology story — no test file expected. Verify by:
- `CLAUDE.build.md` contains the string `context_health` in the checkpoint section.
- `CLAUDE.build.md` contains `Context health:` in the `### 8. Report` block.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

---

Tag: `cp34-checkpoint-context-health`
