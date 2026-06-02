---
id: INFRA-135
rail: INFRA
title: "Effort-tracking integrity audit + `flex_build.py story-cost-estimate` subcommand"
status: planned
phase: "53"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - tests/pairmode/test_flex_build_story_cost_estimate.py
  - tests/pairmode/test_record_attempt_usage_parsing.py
---

# INFRA-135 — Effort-tracking integrity audit + `flex_build.py story-cost-estimate` subcommand

## Background

Phase 52's minimal return surface (BUILD-013) compressed agent output to a
single structured block — `BUILD-RESULT` / `REVIEW-RESULT` + `SUMMARY` +
`<usage>`. The orchestrator parses `<usage>` and feeds those numbers to
`record_attempt.py` to populate `effort.db`. Two follow-on concerns:

**1. Pipeline integrity audit.** With the verbose blocks gone, the only
remaining numerical surface is `<usage>`. The instructions in
`CLAUDE.build.md` Step 1 and Step 2 enumerate the `<usage>` fields the
orchestrator should extract and pass to `record_attempt.py`. A fixture test
is needed to confirm the exact `<usage>` shape the runtime emits round-trips
every documented field into the DB row correctly.

**2. Story cost estimate at the context gate.** `effort.db` already accrues
per-attempt token counts segmented by `rail`, `agent_role`, `outcome`, and
`story_class`. The Phase 52 `/context` gate (BUILD-014) tells the user "you're
at N / threshold — proceed or /clear", but does not surface how expensive the
upcoming story is likely to be. With accumulated PASS-outcome data, the
median (`rail`, `story_class`) cost is a reasonable single-number estimate.
Surfacing it inline at the gate turns the /clear decision from guesswork into
"this story type typically costs 42k tokens; you have 90k headroom; safe to
proceed" or "this story type typically costs 110k tokens; you have 30k
headroom; /clear first."

A new `flex_build.py story-cost-estimate` subcommand reads story frontmatter,
queries `effort.db` for matching PASS-outcome rows, returns the median, and
the orchestrator displays the result right after `CONTEXT: N / threshold —
proceeding`.

## Ensures

### Pipeline integrity audit

- `tests/pairmode/test_record_attempt_usage_parsing.py` (new) covers
  round-tripping every numeric field documented in `CLAUDE.build.md` Step 1's
  `<usage>` format block: `total_tokens`, `input_tokens`, `output_tokens`,
  `cache_read_tokens`, `cache_write_tokens`, `tool_uses`, `duration_ms`.
- A test writes a `<usage>` block (the literal shape documented in
  `CLAUDE.build.md`) to a tmp file, invokes `record_attempt.py
  --usage-block <tmp>` with the minimum other required flags, and queries the
  resulting DB row via `effort_db` to confirm every parsed field is persisted
  to the correct column.
- A second test variant omits the optional cache fields from the `<usage>`
  block and confirms the corresponding DB columns are NULL.
- A third variant supplies `--tokens-total` explicitly alongside
  `--usage-block` and confirms the explicit flag wins (per
  `record_attempt.py`'s existing behaviour).

### `story-cost-estimate` subcommand

- `flex_build.py` gains a `story-cost-estimate` subcommand with options
  `--story-id RAIL-NNN` and `--project-dir DIR`.
- The command reads the story's frontmatter (using the existing
  `_read_story_frontmatter` helper) to extract `rail` and `story_class`.
  If `story_class` is absent it defaults to `"code"`.
- The command resolves the effort DB path via `resolve_effort_db_path` and
  queries `attempts` for rows matching: `rail = <rail>` AND
  `story_class = <story_class>` AND `outcome = 'PASS'` AND
  `tokens_total IS NOT NULL AND tokens_total > 0`.
- If three or more rows match: prints
  `estimate: <median> tokens (median of <N> PASS attempts on <RAIL>/<story_class>)`
  where `<median>` is `int(statistics.median(tokens_total))`. Exit 0.
- If fewer than three rows match: prints
  `estimate: insufficient data (<N> PASS attempts on <RAIL>/<story_class>)`.
  Exit 0.
- If the effort DB file does not exist: prints
  `estimate: insufficient data (0 PASS attempts on <RAIL>/<story_class>)`.
  Exit 0 — never raises.
- The command applies the same `_depth_guard` pattern as other subcommands.

### Context gate integration

- `CLAUDE.build.md` "Context gate" section: after the
  `CONTEXT: [N] / [threshold] tokens — proceeding` output line, the
  orchestrator calls `flex_build.py story-cost-estimate --story-id RAIL-NNN`
  and displays the `estimate: ...` line as the next line of the gate report.
- The instruction notes the estimate is **informational** (does not block)
  and adds a soft heuristic: if `[threshold] - [N]` is less than the
  estimated token count, append:
  > Estimated story cost exceeds remaining headroom; consider /clear before
  > proceeding.
- The "THRESHOLD REACHED" branch is unchanged.
- `skills/pairmode/templates/CLAUDE.build.md.j2` mirrors all edits using
  `{{ pairmode_scripts_dir }}/flex_build.py` for the script path.

## Out of scope

- Adding new columns to `attempts` or changing `record_attempt.py`'s schema.
- Pricing-aware estimates (tokens only, no cost-per-token math).
- Persisting the estimate alongside the attempt row.
- Changing the rail-median guardrail (`check_guardrail`) — it remains a
  separate post-attempt informational check.
- A `flex_build.py phase-cost-estimate` companion (separate future story).

## Instructions

### 1. Add the `story-cost-estimate` subcommand to `flex_build.py`

After the `cmd_clear_attempt_count` command (added by BUILD-022), add:

```python
# ---------------------------------------------------------------------------
# Story cost estimate (INFRA-135)
# ---------------------------------------------------------------------------

_COST_MIN_SAMPLE = 3


def _query_story_cost_samples(
    db_path: Path, rail: str, story_class: str
) -> list[int]:
    """Return tokens_total values for PASS rows matching (rail, story_class)."""
    import sqlite3

    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tokens_total
              FROM attempts
             WHERE rail = ?
               AND story_class = ?
               AND outcome = 'PASS'
               AND tokens_total IS NOT NULL
               AND tokens_total > 0
            """,
            (rail, story_class),
        )
        return [int(row[0]) for row in cur.fetchall()]
    finally:
        conn.close()


@flex_build.command("story-cost-estimate")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-135).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_story_cost_estimate(story_id: str, project_dir: str) -> None:
    """Print a one-line median PASS-token estimate for (rail, story_class)."""
    import statistics

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    story_path = _story_path(story_id, project_path)
    fm = _read_story_frontmatter(story_path) if story_path.exists() else {}
    rail = (fm.get("rail") or story_id.split("-", 1)[0]).strip()
    story_class = (fm.get("story_class") or "code").strip()

    db_path = resolve_effort_db_path(project_path)
    samples = _query_story_cost_samples(db_path, rail, story_class)
    n = len(samples)

    if n < _COST_MIN_SAMPLE:
        click.echo(
            f"estimate: insufficient data ({n} PASS attempts on {rail}/{story_class})"
        )
        return

    median = int(statistics.median(samples))
    click.echo(
        f"estimate: {median} tokens (median of {n} PASS attempts on {rail}/{story_class})"
    )
```

Check whether `resolve_effort_db_path` is already imported at the top of
`flex_build.py` and add the import if absent.

### 2. Wire the cost estimate into the `CLAUDE.build.md` context gate

In `CLAUDE.build.md` "Context gate" section, under the "If the token count
is **below** the threshold:" branch, replace:

```
Output: `CONTEXT: [N] / [threshold] tokens — proceeding`
Continue to the pre-story schema gate.
```

with:

```
Output: `CONTEXT: [N] / [threshold] tokens — proceeding`

Then call:
  PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
    story-cost-estimate --story-id RAIL-NNN --project-dir .

Display its output verbatim as the next line of the gate report.

If the printed estimate is a numeric token count (not "insufficient data")
and `[threshold] - [N]` is less than that estimate, append:

  Estimated story cost exceeds remaining headroom; consider /clear before
  proceeding.

The estimate is informational — it does not block. Continue to the
pre-story schema gate.
```

Leave the "THRESHOLD REACHED" branch untouched.

### 3. Mirror in `CLAUDE.build.md.j2`

Apply the same step-2 edit to `skills/pairmode/templates/CLAUDE.build.md.j2`,
substituting `{{ pairmode_scripts_dir }}/flex_build.py` for the absolute path.

### 4. Pipeline integrity audit tests

Create `tests/pairmode/test_record_attempt_usage_parsing.py`. Use a tmp
`.companion/state.json` with `effort_tracking: true` and a tmp
`effort_db_path`. Write the `<usage>` block fixture using the exact field
names documented in `CLAUDE.build.md` Step 1. Invoke `record_attempt.py` with
`--usage-block <fixture-path>`. Query the resulting DB row and assert values.

### 5. story-cost-estimate tests

Create `tests/pairmode/test_flex_build_story_cost_estimate.py` following
the subprocess pattern in `test_flex_build_current_phase.py` and the DB
seeding pattern in `test_effort_db.py`.

## Tests

`tests/pairmode/test_record_attempt_usage_parsing.py` (new):

1. `test_usage_block_full_round_trip` — all documented fields present; assert
   each lands in the correct DB column.
2. `test_usage_block_missing_optional_cache_fields_writes_null` — omit
   `cache_read_tokens` and `cache_write_tokens`; assert those DB columns NULL.
3. `test_explicit_flag_overrides_usage_block` — fixture has `total_tokens: 100`;
   invoke with `--tokens-total 999`; assert DB row has `tokens_total = 999`.

`tests/pairmode/test_flex_build_story_cost_estimate.py` (new):

1. `test_estimate_returns_median_when_sufficient_samples` — seed 5 PASS rows
   for `(BUILD, methodology)`; assert stdout matches
   `estimate: <median> tokens (median of 5 PASS attempts on BUILD/methodology)`.
2. `test_estimate_insufficient_data_when_fewer_than_three_rows` — seed 2 PASS
   rows; assert "insufficient data (2 PASS attempts ...)".
3. `test_estimate_insufficient_data_when_no_db` — no `.companion/` directory;
   assert "insufficient data (0 PASS attempts ...)" and no crash.
4. `test_estimate_ignores_fail_rows` — seed 3 FAIL rows + 0 PASS rows; assert
   "insufficient data".
5. `test_estimate_ignores_null_tokens_total` — seed 3 PASS rows with
   `tokens_total=NULL`; assert "insufficient data".
6. `test_estimate_segregates_by_story_class` — seed 5 PASS rows for
   `(BUILD, code)` and 0 for `(BUILD, methodology)`; query methodology story;
   assert "insufficient data".
7. `test_estimate_segregates_by_rail` — seed 5 PASS rows for `(BUILD, code)`
   and 0 for `(INFRA, code)`; query INFRA story; assert "insufficient data".
8. `test_estimate_falls_back_to_story_class_code_when_frontmatter_missing` —
   story frontmatter absent `story_class`; assert query uses `story_class = 'code'`.
9. `test_estimate_depth_guard` — shallow `--project-dir`; assert non-zero exit.
