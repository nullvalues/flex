---
id: BUILD-033
rail: BUILD
title: "fix multi-era index parser in _parse_index_phases"
status: planned
phase: "77"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build.py
---

# BUILD-033 — fix multi-era index parser in _parse_index_phases

**Phase:** 77
**Rail:** BUILD

## Background

`_parse_index_phases` in `flex_build.py` scans `docs/phases/index.md` line by
line to build the list of `(phase_ref, status)` rows used by `current-phase`
and `mark-phase-complete`. The current exit condition on entering a table is:

```python
if not stripped.startswith("|"):
    if in_table and stripped:
        break
    continue
```

Any non-empty, non-pipe line — including a markdown heading like `## Era 002`
— causes an immediate `break`. For a single-era index this is fine: there is
only one table and the first such line is EOF context or unrelated prose. For a
multi-era index the section heading between tables terminates the scan early,
leaving all rows in later tables unseen.

`current-phase` receives only era-1 rows (all `complete`), concludes no active
phase exists, and exits 1. The active phase in era 2 is never found.

## Ensures

1. `current-phase` returns the correct phase file for a project whose active
   phase lives in a second (or later) era table.
2. `current-phase` still returns exit 1 when all phases across all tables are
   `complete`.
3. `mark-phase-complete` correctly finds and updates a phase ref in any era
   table.
4. Single-era indexes continue to behave identically to before.
5. All existing `_parse_index_phases` tests pass; new tests cover multi-era cases.

## Out of scope

- Changing the index.md file format.
- Any other `flex_build.py` command.

## Instructions

Replace the `break` in `_parse_index_phases` with a table-state reset so the
parser continues scanning after a section boundary:

```python
if not stripped.startswith("|"):
    if in_table and stripped:
        # End of this table — reset and keep scanning for more tables.
        in_table = False
        header_seen = False
        separator_seen = False
    continue
```

No other changes to `_parse_index_phases`. No changes to callers.

## Tests

Add to `tests/pairmode/test_flex_build.py` (or the existing test file that
covers `_parse_index_phases`):

- `test_parse_index_phases_multi_era_returns_all_rows` — index with two era
  sections each containing a table; assert rows from both tables are returned.
- `test_parse_index_phases_multi_era_active_in_second_era` — era-1 rows all
  `complete`, era-2 has one `planned` row; assert the `planned` row is returned.
- `test_parse_index_phases_single_era_unchanged` — single-table index; assert
  existing behaviour is preserved.
- `test_current_phase_finds_active_in_second_era` — integration test using a
  temp project dir with a multi-era index and a matching phase file; assert
  `cmd_current_phase` exits 0 and prints the correct path.
