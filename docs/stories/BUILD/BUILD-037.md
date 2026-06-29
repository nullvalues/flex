---
id: BUILD-037
rail: BUILD
title: "mark-phase-complete: column-count-preserving status rewrite"
status: planned
phase: "79"
story_class: code
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build_mark_phase_complete.py
---

# BUILD-037 — mark-phase-complete: column-count-preserving status rewrite

## Context

`cmd_mark_phase_complete` (`skills/pairmode/scripts/flex_build.py:544`) rewrites
the matching phase row in `docs/phases/index.md` to set its status cell to
`complete`. The rewrite is hardcoded to a 4-column output
(`flex_build.py:580–590`):

```python
if len(parts) >= 5:
    cell_phase = parts[1].strip()
    cell_status = parts[3].strip()
    if cell_phase == phase_key and cell_status != "complete":
        new_row = (
            f"| {parts[1].strip()} | {parts[2].strip()} | complete |"
            f" {parts[4].strip()} |\n"
        )
```

On this repo's **native 4-column** index (`| Phase | Title | Status | Tag |`)
this is correct. But on the **seeded 5-column** index that fleet projects get
from `index.md.j2` (`| Phase | Title | Status | Deferred from | Link |`) the
rewrite:

- drops the **Link** cell (original `parts[5]`) entirely, and
- collapses the row to 4 columns, leaving it narrower than the table header,
- mislabelling `Deferred from` (original `parts[4]`) into the old Tag slot.

Reproduction:
```
input  (5-col): | RK002-main | The phase | planned | — | [phase-RK002-main.md](...) |
output (4-col): | RK002-main | The phase | complete | — |
```

Every checkpoint on a 5-column index re-corrupts the active row, forcing manual
repair. The fix: preserve the row's existing column count and only swap the
status cell.

## Acceptance criteria

1. The status cell (column index 3 in the split, i.e. the 3rd data column) of
   the matching `phase_key` row is set to `complete`. **All other cells in that
   row are preserved verbatim**, including any columns beyond the status cell
   (Deferred-from, Link, Tag, or any future columns).

2. The rewritten row has the **same number of columns** as the original row —
   no columns added or dropped. A 5-column row stays 5 columns; a 4-column row
   stays 4 columns; an N-column row stays N columns.

3. Cell whitespace/padding normalisation is acceptable (the existing code
   already `.strip()`s and re-pads with single spaces) **as long as** every
   original cell's content is retained in its original position. Only the
   status cell's content changes.

4. Idempotency unchanged: a row already `complete` exits 0 without rewriting
   (existing behaviour, `flex_build.py:566–569`).

5. Not-found and missing-index error paths unchanged
   (`flex_build.py:551–564`). Atomic temp-file + `os.replace` write unchanged
   (`flex_build.py:595–607`).

6. The minimum-column guard still rejects malformed rows: a row must have at
   least enough columns to contain a status cell (phase, title, status) before
   it is eligible for rewrite.

7. Build gate green:
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Implementation guidance

- Rebuild the row from its own `parts` list rather than from a fixed format
  string. Split into the inner cells (drop the leading/trailing empty `parts[0]`
  / `parts[-1]` produced by `"|...|".split("|")`), set the status cell, and
  re-join with `| ` / ` |` framing. Example shape:
  ```python
  cells = [p.strip() for p in stripped.split("|")[1:-1]]  # inner cells only
  # cells[0]=phase, cells[1]=title, cells[2]=status, cells[3:]=rest
  cells[2] = "complete"
  new_row = "| " + " | ".join(cells) + " |\n"
  ```
- Keep the match condition (`cells[0] == phase_key and cells[2] != "complete"`)
  and the `replaced` single-shot guard.
- Status cell is the **3rd inner cell** (index 2), consistent with
  `_parse_index_phases` reading `parts[3]` of the raw split.
- Do not change `_parse_index_phases`, the idempotency check, the not-found
  path, or the atomic write.

## Tests

Add to `tests/pairmode/test_flex_build_mark_phase_complete.py`:

1. **5-column row preserved.** Seed a 5-column index, mark a `planned` row
   complete, assert the row is still 5 columns and the Link + Deferred-from
   cells are byte-for-byte retained (only status changed).
2. **4-column row preserved.** Existing native layout still produces a correct
   4-column `complete` row (regression).
3. Idempotent: marking an already-`complete` row is a no-op (exit 0, file
   unchanged).
4. Not-found phase_key exits 1, file unchanged.
5. Round-trip: after `mark-phase-complete`, re-parsing the index with
   `_parse_index_phases` yields the same row set with the target row now
   `complete` and no column-count drift on any row.

Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_mark_phase_complete.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- `current-phase` selection logic — BUILD-036.
- Reviewer revert breadth — BUILD-038.
- Any change to the seeded `index.md.j2` template column set.
