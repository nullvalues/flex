---
id: BUILD-036
rail: BUILD
title: "current-phase: first-incomplete selection + status classification"
status: complete
phase: "79"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build_current_phase.py
---

# BUILD-036 — current-phase: first-incomplete selection + status classification

## Context

`cmd_current_phase` (`skills/pairmode/scripts/flex_build.py:422`) picks the
active phase from `docs/phases/index.md` with this loop
(`flex_build.py:439–442`):

```python
active_phase_ref: str | None = None
for phase_ref, status in phase_rows:
    if status != "complete":
        active_phase_ref = phase_ref
```

Two defects, both confirmed by reproduction:

1. **Last-non-complete wins.** The loop keeps the *last* non-complete row.
   When the index lists a later **planned** phase whose `phase-<ref>.md` file
   does not exist yet, that row wins, `candidate.exists()` (line 446) is False,
   and the command falls through to *"No active phase found — all stories
   complete."* (line 452, exit 1) even though an earlier phase is genuinely
   active. This is the upstream symptom ("falsely reported all complete").
   It also returns a later planned phase over the real active one (the "returns
   PM038 instead of the first incomplete phase" report).

2. **Exact-match status misclassifies terminal/parked states.**
   `status != "complete"` treats `complete (partial)` as active (it is a
   terminal state → should count as complete) and `deferred` as active (the
   phase has been moved/resumed elsewhere → should be skipped, never returned).

   Reproduction against this repo's own index:
   ```
   non-complete rows: [('23', 'complete (partial)'), ('64', 'deferred')]
   LAST-wins picks: 64  -> returns phase-64.md   (deferred — wrong)
   ```

`_parse_index_phases` itself is correct (status at `parts[3]` for both the
4-column native and 5-column seeded layouts) and is **not** changed by this
story. This is selection logic only.

## Acceptance criteria

1. **First-incomplete selection.** Among index rows that are *active* (per the
   classification below), `current-phase` selects the **first in build order**
   (earliest row), not the last.

2. **Status classification** applied before selection:
   - A status that is exactly `complete` **or** begins with `complete` (e.g.
     `complete (partial)`) is **terminal** → not a candidate.
   - A status of `deferred` is **parked** → not a candidate (skipped entirely;
     a deferred phase is never returned as active).
   - Any other status (`planned`, `in-progress`, `in progress`, etc.) is
     **active** → eligible.

   Match is case-insensitive and whitespace-trimmed (statuses already arrive
   lowercased from `_parse_index_phases`).

3. **Fileless-phase guard.** If the selected active phase's
   `docs/phases/phase-<ref>.md` does not exist, `current-phase` does **not**
   silently report "all complete". It continues to the **next** active row in
   order and returns the first active phase whose file exists. Only when no
   active row has an existing file does it fall through to the existing
   "No active phase found" message (exit 1). (Rationale: a planned-but-fileless
   future row must never mask an earlier active phase that has a file.)

4. Against this repo's current `docs/phases/index.md`, `current-phase` reports
   `No active phase found — all stories complete.` (exit 1) — because rows `23`
   (`complete (partial)`) and `64` (`deferred`) are both now correctly terminal/
   parked, and HARNESS001-main is not yet listed. This is the correct era-002
   behaviour (the orchestrator drives the active harness phase off `next_story`).

5. The fallback path (no index file → scan `phase-*.md` via `find_next_story`,
   `flex_build.py:455–481`) is **unchanged**.

6. Build gate green:
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Implementation guidance

- Introduce a small classifier helper (module-level, testable), e.g.
  `_is_terminal_status(status)` / `_is_active_status(status)`, so the rule is
  unit-testable independent of the CLI. Keep it beside `_parse_index_phases`.
- Replace the last-wins loop with a forward scan that returns the first active
  row whose phase file exists. Because the fileless-guard (AC3) needs the file
  check inside the selection loop, fold the `candidate.exists()` test into the
  iteration rather than doing it once after the loop.
- Do not change `_parse_index_phases`, `_is_aggregate_range`, or the no-index
  fallback.
- Watch the `deferred` rule: it must be *excluded*, not merely deprioritised —
  a deferred phase is never a valid `current-phase` result even if it is the
  only non-complete row.

## Tests

Add to `tests/pairmode/test_flex_build_current_phase.py`:

1. Two active phases (e.g. `planned`) both with files → returns the **first**.
2. An earlier active phase **with** a file plus a later `planned` phase
   **without** a file → returns the earlier one (not "all complete").
3. A `deferred` row is skipped (never returned), even when it is the only
   non-complete row → "all complete" exit 1.
4. A `complete (partial)` row is treated as terminal (not returned).
5. Regression: a single normal active phase still resolves correctly.
6. Mixed 5-column seeded layout (`| Phase | Title | Status | Deferred from |
   Link |`) resolves the same as the 4-column layout (proves selection is
   layout-independent).

Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_current_phase.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- `mark-phase-complete` column corruption — BUILD-037.
- Reviewer revert breadth — BUILD-038.
- Any change to `_parse_index_phases` parsing or the no-index fallback scan.
