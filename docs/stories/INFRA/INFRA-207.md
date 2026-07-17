---
id: INFRA-207
rail: INFRA
title: "Fix escaped-pipe row corruption in _update_story_row_in_phase: split Stories-table rows on unescaped pipes only (\\| treated as a literal cell character, not a column separator), so titles documenting matcher strings like Edit\\|Write update the real status cell instead of truncating the title"
status: planned
phase: "94"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_update.py
  - tests/pairmode/test_story_update.py
touches: []
---

# INFRA-207 — Fix escaped-pipe row corruption in `_update_story_row_in_phase`: split Stories-table rows on unescaped pipes only

## Context

`_update_story_row_in_phase(text, story_id, status)` in
`skills/pairmode/scripts/story_update.py` (lines 229-319) parses each
`## Stories`-table data row with a naive `parts = stripped.split('|')`
(line 262). It then indexes `parts[1]` as the ID cell (via
`_strip_link(parts[1])`, line 280-281), reassigns `parts[3]` as the status
cell (lines 288-298), and rejoins with `'|'.join(parts)` (line 313).

This naive split does not distinguish a markdown-escaped pipe (`\|`, meant to
render a literal `|` character inside a cell) from a real column-separator
pipe. Story titles in this repo's own INFRA rail routinely contain escaped
pipes because they document hook matcher syntax like `Edit\|Write` or
`Task\|Agent` (see INFRA-205 and INFRA-206, whose own titles carry this
pattern). When such a title is present, `str.split('|')` shreds the title into
extra "columns" at each `\|` boundary, so `parts[3]` is **not** the real status
cell — it is a fragment of the title. Reassigning `parts[3]` corrupts the title
and leaves the real status cell untouched.

This is a live, reproduced data-corruption bug (CER-066, "Do Now", HIGH):

- Reproduced directly with a fixture phase row
  `| INFRA-1 | Register the Edit\|Write matcher | planned |`. Calling
  `update_phase_story_status("INFRA-1", ..., "complete")` corrupted the row to
  `| INFRA-1 | Register the Edit\|complete | planned |` — the title was
  truncated at `\|` and the intended status was spliced into the truncated
  fragment, while the real status cell stayed `planned`.
- Live-hit twice during Phase 93's own build: `story_update.py --story-id
  INFRA-205 --status complete` corrupted `docs/phases/phase-93.md`'s INFRA-205
  row this exact way; INFRA-206 carries the same escaped-pipe pattern and hit
  the same corruption. Both rows were manually repaired by the orchestrator
  outside the tool.

The fix replaces the naive split with one that treats `\|` as a literal
character within a cell rather than a column separator — a negative-lookbehind
regex split, `re.split(r'(?<!\\)\|', stripped)` (or an equivalent tokenizer) —
so a preceding backslash suppresses the split at that pipe. `re` is already
imported at the top of the module (line 18).

Everything downstream that indexes into `parts` must continue to work once
cells can carry literal `\|` sequences: the ID-column comparison
(`_strip_link(parts[1])`), the status-column reassignment (`parts[3]`), the
`len(parts) < 3` / `len(parts) > 3` guards, and the final `'|'.join(parts)`
reconstruction. Because the split boundary is the only thing changing (the
number of segments a well-formed 3-column row produces is unchanged — a
correct row still yields `['', id, title, status, '']`), the existing index
positions remain correct; the bug was purely that escaped pipes were inflating
the segment count and shifting `parts[3]` off the real status cell.

Note: the ID column itself cannot contain an escaped pipe in practice
(`_STORY_ID_RE`, line 37, constrains story IDs to `RAIL-NNN` shape), but the
fix is general — correct for any cell, not special-cased to the title column.
The header-row and separator-row skip logic (`header_seen` / `separator_seen`,
lines 251-277) keys only on line position within the table, not on cell
content, so it is unaffected by the split change.

## Ensures

1. **Row-splitting treats `\|` as a literal cell character, not a column
   separator.** `_update_story_row_in_phase` splits each `## Stories`-table row
   with a negative-lookbehind regex (`re.split(r'(?<!\\)\|', stripped)`, or an
   equivalent tokenizer that suppresses the split when the pipe is preceded by a
   backslash) in place of the naive `stripped.split('|')`. `re` is already
   imported.

2. **A title containing `\|` sequences is preserved byte-for-byte except for
   the status cell.** A story title such as `Edit\|Write` or `Task\|Agent`
   survives a status update unchanged; only the status cell is rewritten. The
   exact INFRA-205/INFRA-206 collision shape is covered by a regression test
   using a fixture that reproduces it precisely (a title that literally contains
   `Edit\|Write` in a matcher-registration sentence), asserting the resulting
   row's title is unchanged and only the status cell changed.

3. **The original CER-066 reproduction is captured as an explicit regression
   test.** A fixture row `| INFRA-1 | Register the Edit\|Write matcher | planned |`,
   after `update_phase_story_status("INFRA-1", ..., "complete")`, reads
   `| INFRA-1 | Register the Edit\|Write matcher | complete |` — NOT the
   corrupted `| INFRA-1 | Register the Edit\|complete | planned |`. The test
   asserts both the positive (correct row) and, by exact-row equality, the
   absence of the corrupted form.

4. **Existing non-escaped-pipe row-matching behavior is unchanged.** All
   pre-existing `tests/pairmode/test_story_update.py` tests continue to pass
   unmodified, including link-syntax-in-ID-cell handling
   (`test_phase_manifest_with_link_syntax_in_id_cell` / `_strip_link`),
   multi-row tables (`test_only_matching_row_updated_multiple_rows`), spacing
   preservation in the status cell, and the INFRA-204 phase-scoping tests.

5. **ID-column comparison and status-cell reassignment both land correctly
   against the new split.** The fix is verified end-to-end, not just at the
   split line: `_strip_link(parts[1])` still resolves the ID cell, `parts[3]`
   still targets the real status cell, the `len(parts) < 3` / `len(parts) > 3`
   guards still gate correctly, and `'|'.join(parts)` still reconstructs a
   well-formed row (the escaped pipe reappears verbatim in the rejoined title
   because it was never treated as a boundary).

6. **Full pairmode test suite passes.**
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` is green.

## Instructions

- Edit `_update_story_row_in_phase` in
  `skills/pairmode/scripts/story_update.py` (lines 229-319). The only
  substantive change is the row-splitting line (line 262): replace
  `parts = stripped.split('|')` with a negative-lookbehind regex split,
  `parts = re.split(r'(?<!\\)\|', stripped)` (or an equivalent tokenizer with
  the same semantics). `re` is already imported at line 18 — do not add an
  import.

- Add a short comment on the split line cross-referencing CER-066 and stating
  that `\|` is a literal cell character (escaped pipe), so the split must not
  break on a backslash-preceded pipe — this preserves the contract against
  future edits.

- Do **not** change the index positions downstream (`parts[1]`, `parts[3]`),
  the `len(parts)` guards, the `_strip_link` call, the spacing-preservation
  logic in the status cell (lines 289-297), the newline-suffix preservation
  (lines 304-311), or the `'|'.join(parts)` reconstruction (line 313). Read the
  full function to confirm each still lands correctly under the new split before
  concluding — the whole point of the bug is a downstream-index shift, so verify
  the indices, do not just swap the split line and stop.

- Do **not** change `update_phase_story_status`, `_read_story_declared_phase`,
  `_resolve_phase_manifests`, `_strip_link`, `_parse_story_id`,
  `update_story_status`, the CLI option surface, or `story_new.py`.

- No change to `docs/architecture.md` is required: its `story_update.py`
  paragraph (lines 452-462) describes the tool at the contract level ("updates
  the status column in matching `## Stories`-table row(s)"), which remains true;
  the internal pipe-splitting mechanism is not documented there and this fix
  introduces no caller-visible behavior or contract change.

## Tests

`story_class: code` — a real change to row-parsing logic. Run the gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Add these cases to `tests/pairmode/test_story_update.py`, reusing the existing
`_make_project`, `_make_story`, and `_make_phase` fixtures. Note that
`_make_phase` builds rows via `f"| {sid} | {title} | {st} |\n"`, so passing a
`title` that contains `Edit\|Write` (a Python string with a literal backslash,
i.e. `"Register the Edit\\|Write matcher"`) reproduces the on-disk escaped-pipe
shape directly — no bespoke phase-file writer is needed. Give each such story a
`phase:` value consistent with its phase filename so the INFRA-204 scoped path
resolves the manifest (e.g. `_make_story(..., phase="1")` with a `phase-1.md`
manifest, or align to the existing `phase="001"` / `phase-001.md` pairing).

- `test_escaped_pipe_in_title_updates_real_status_cell` — the exact CER-066
  reproduction. Create a phase manifest with a row whose title is
  `Register the Edit\|Write matcher` (Python `"Register the Edit\\|Write matcher"`)
  and status `planned`. Run the status update to `complete`. Assert the row now
  reads exactly `| INFRA-1 | Register the Edit\|Write matcher | complete |` and
  assert the corrupted form `| INFRA-1 | Register the Edit\|complete | planned |`
  is **not** present in the file.

- `test_escaped_pipe_infra205_collision_shape` — the INFRA-205/INFRA-206 live
  shape. Create a row with a matcher-registration title containing `Edit\|Write`
  (as close to the real INFRA-205 title as practical). Capture the title
  substring pre-update; run the status update; assert the title substring is
  byte-for-byte unchanged in the updated file and only the status cell flipped.

- `test_multiple_escaped_pipes_in_title_preserved` — a title containing more
  than one escaped pipe (e.g. `Task\|Agent and Edit\|Write matchers`). Assert
  every `\|` survives verbatim and only the status cell is updated — guards
  against an off-by-N shift when several escaped pipes are present.

- `test_escaped_pipe_row_status_spacing_preserved` — a row whose status cell
  has non-default surrounding spacing, with an escaped-pipe title. Assert the
  status-cell leading/trailing spacing is preserved (the spacing logic still
  operates on the correct `parts[3]`).

- Confirm the existing `test_phase_manifest_with_link_syntax_in_id_cell`,
  `test_only_matching_row_updated_multiple_rows`,
  `test_phase_manifest_status_column_updated`, and the INFRA-204 phase-scoping
  tests remain green unmodified.

### Out of scope

- Any change to markdown-cell escaping beyond the pipe character (`\|`). Other
  markdown escapes inside cells are not a known corruption vector and are not
  addressed here.
- Changing `_strip_link`, first-column equality matching, spacing preservation,
  or newline-suffix handling in `_update_story_row_in_phase` beyond what the
  split change requires.
- The INFRA-204 phase-scoping logic (`update_phase_story_status`,
  `_read_story_declared_phase`, `_resolve_phase_manifests`) — CER-064 is already
  resolved; this story does not touch manifest selection.
- Any change to the CLI option surface, valid-status choices, or the
  `update_story_status` frontmatter writer.
- Adding a general markdown-table parser or importing an external table
  library. The fix is a targeted split-boundary correction, not a parser
  rewrite.
