---
id: INFRA-222
rail: INFRA
title: Fix escaped-pipe corruption in next_action.py's _check_phase_completion Stories-table status parse (CER-066 recurrence)
status: complete
phase: "95"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
  - tests/pairmode/test_next_action.py
touches:  # If this story changes any documented architecture, add docs/architecture.md to this list.
---

## Requires

- `skills/pairmode/scripts/next_action.py` exists with `_check_phase_completion`
  at lines 286-322 (RESOLVER-008 pre-checkpoint guard 1).
- `skills/pairmode/scripts/story_update.py`'s `_update_story_row_in_phase`
  (CER-066 fix, Phase 94/INFRA-207) already establishes the correct pattern:
  `re.split(r'(?<!\\)\|', stripped)` — splitting only on pipes not preceded by
  a backslash, so an escaped pipe (`\|`) inside a title cell (e.g.
  `` `Task\|Agent` ``) is treated as literal cell content, not a column
  separator.

## Context

`_check_phase_completion` (guard 1 of the three pre-checkpoint guards) parses
each Stories-table row with a naive `stripped.split("|")` and reads the status
from a fixed index, `cols[2]`. This is the exact bug class already documented
and resolved once before under CER-066 (`story_update.py`, Phase 94) — a title
cell containing an escaped pipe (this repo's INFRA rail routinely documents
hook matchers like `` `Task\|Agent` `` or `` `Write\|Edit\|MultiEdit` ``)
shreds the row into extra "columns" during the naive split, so `cols[2]` lands
on a title fragment instead of the real status cell.

Live-hit: Phase 95's own Stories table (INFRA-208, INFRA-209) both have
escaped pipes in their titles. With both stories genuinely `complete`, the
checkpoint guard still reports `phase-incomplete` because `cols[2]` resolves
to garbage, not `"complete"`.

The fix is **not** "read the last column" — a Stories table can gain trailing
whitespace-only cells or (in principle) additional columns later, and "last
column = status" is exactly the kind of positional assumption that broke here
in the first place, just relocated. Instead: split correctly (respecting
escaped pipes, matching the already-proven `story_update.py` pattern) and
then read the status from its known schema position (`| ID | Title | Status |`
→ index 3 after a correct split, matching `story_update.py`'s own indexing at
line 294), the same convention every phase doc's Stories table already follows
and that `schema_validator.py` / `story_new.py` / `story_update.py` all assume.
Once the split correctly treats `\|` as literal, fixed-index-by-schema is
reliable — the bug was in the split, not in using a schema-known index.

## Ensures

1. `_check_phase_completion` in `skills/pairmode/scripts/next_action.py` splits
   each Stories-table data row using an unescaped-pipe boundary
   (`re.split(r'(?<!\\)\|', stripped)`), not `stripped.split("|")`.
2. The status cell is read from the row's known schema position (the third
   data cell, matching `| ID | Title | Status |`) after the corrected split —
   not from `len(cols) - 1` / "last column".
3. A phase file whose Stories table contains a row with an escaped pipe in the
   title (e.g. `` `Task\|Agent` ``) and status `complete` is correctly
   evaluated as complete by `_check_phase_completion`.
4. A phase file whose Stories table contains a row with an escaped pipe in the
   title and status `planned` (or any non-complete/deferred status) is
   correctly evaluated as incomplete.
5. Existing `_check_phase_completion` behavior for rows without escaped pipes
   is unchanged (regression-safe).
6. Running `flex_build.py next-action --json --project-dir .` against this
   repo's actual `docs/phases/phase-95.md` (INFRA-208 and INFRA-209 both
   `complete`, both titles containing escaped pipes) no longer returns
   `await-user` / `checkpoint-guard-failed:phase-incomplete`.

## Instructions

1. In `skills/pairmode/scripts/next_action.py`, in `_check_phase_completion`
   (around line 311), replace:
   ```python
   cols = [c.strip() for c in stripped.split("|") if c.strip()]
   ```
   with an unescaped-pipe split mirroring `story_update.py`'s
   `_update_story_row_in_phase`:
   ```python
   raw_cols = re.split(r'(?<!\\)\|', stripped)
   cols = [c.strip() for c in raw_cols if c.strip()]
   ```
   Note `next_action.py` must `import re` at module level if not already
   imported (check first — do not add a duplicate import).
2. Keep `status = cols[2].lower()` as-is once the split is corrected — do not
   change it to `cols[-1]`. The fix is in how `cols` is built, not in which
   index is read. Add a one-line comment at the split site (mirroring
   `story_update.py`'s CER-066 comment) explaining why the naive split was
   wrong, so a future editor doesn't "simplify" it back.
3. Do not touch `_check_cer_do_now` (the second `split("|")` call in this file,
   around line 352) — it only uses `cols` to detect the header row and never
   indexes into a specific data column by position; it substring-matches
   `RESOLVED`/`SUPERSEDED` directly on the raw line, so it is not affected by
   this bug class. Leave it unchanged.
4. Do not touch any other file. A repo-wide audit found the same naive
   `split("|")` pattern used positionally in `next_story.py`,
   `index_integrity.py`, `flex_build.py` (three call sites), and
   `story_resolver.py`. Whether each of those is actually vulnerable (i.e.
   reads a fixed index rather than just filtering/counting) has not been
   verified per-site and is out of scope here — file as a CER backlog finding
   for a follow-up audit story, not fixed in this story.

## Tests

Add to `tests/pairmode/test_next_action.py` (create the file if it does not
already exist; check first):

- `test_check_phase_completion_handles_escaped_pipe_in_title_complete`: a
  fixture phase file with a Stories-table row whose title contains
  `` `Task\|Agent` `` and status `complete` → `_check_phase_completion`
  returns `True`.
- `test_check_phase_completion_handles_escaped_pipe_in_title_planned`: same
  fixture shape but status `planned` → returns `False`.
- `test_check_phase_completion_multiple_escaped_pipes_in_title`: a title with
  two escaped pipes (e.g. `` `Write\|Edit\|MultiEdit` ``) and status
  `complete` → returns `True` (regression against partial fixes that only
  handle a single escaped pipe).
- `test_check_phase_completion_unaffected_rows_still_work`: existing
  no-escaped-pipe fixture rows (complete, deferred, planned) still resolve as
  before.
- Regression test reproducing this story's own live-hit: point
  `_check_phase_completion` at this repo's real
  `docs/phases/phase-95.md` and assert `True` (both INFRA-208 and INFRA-209
  are `complete` with escaped-pipe titles).

Run: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`
