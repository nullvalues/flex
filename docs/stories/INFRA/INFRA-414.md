---
id: INFRA-414
rail: INFRA
title: Escape pipe in phase-manifest Stories-table title (CER-221)
status: draft
phase: "144"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_story_new.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

`story_new.py`'s `_append_to_phase` (~line 432) writes a new phase-manifest
Stories-table row as `f"| {story_id} | {title} | draft |"` with no pipe
escaping on `title`. The reader, `table_utils.split_table_row`, has a
documented convention that a literal `|` inside a cell must be written as
`\|` — any unescaped `|` in a title shifts the row's column count on read.
This is a live, verified bug (CER-221): a story title containing a pipe
(e.g. from a title mentioning `Edit | Write`) causes
`next_action._check_phase_completion` to misread the story's actual
`status` cell (`draft`) as a different column's value (in the reported
case, `complete`) — a checkpoint-bypass, since phase completion is gated on
every story's status reading `complete`. Phase 144's Goal names this as one
of two independent write sites (with CER-222/INFRA-415) that serialize
operator-supplied free text into a format with its own escaping contract
without verifying against the real reader. This story closes the CER-221
half: escape `title` at the single write site in `_append_to_phase`, and
add a regression test proving the fix by reproducing the exact failure mode
end-to-end (write, then read via `_check_phase_completion`), not just by
asserting the written string contains `\|`.

## Requires

None — the bug and its fix are isolated to `story_new.py`'s
`_append_to_phase` write site and `table_utils.split_table_row`'s existing
(already-documented) escaping contract; no prior story in this phase is a
precondition.

## Ensures

- `_append_to_phase` escapes every literal `|` in `title` as `\|` before
  interpolating it into the Stories-table row, matching
  `table_utils.split_table_row`'s documented escaping convention (the same
  convention `story_update._update_story_row_in_phase`'s status-flip
  rewrite already relies on for its split/rejoin).
- A regression test creates a story via `story_new.py` (or its
  `_append_to_phase` entry point) with a pipe-bearing title (e.g. `"handle
  Edit | Write correctly"`), then reads that story's status back through
  `next_action._check_phase_completion` (or the phase-completion check's
  underlying row lookup) and asserts the status read is the story's actual
  frontmatter status (`draft`) — not a shifted-column value (`complete`).
  Forbidden proxy: a test that only asserts the written table row *string*
  contains `\|` without also reading it back through
  `_check_phase_completion` — that would pass even if the reader-side
  parsing were still broken, and would not reproduce CER-221's actual
  failure mode (a misread status, not a malformed string).
- A second regression test (or an assertion within the same test) verifies,
  by exercising `story_update._update_story_row_in_phase`'s status-flip
  path on the same pipe-bearing-title row, that the already-escaped `\|`
  survives the split/rejoin unchanged (still reads back as a literal `|` in
  the title, and the status flip lands in the correct column) — confirming
  live, rather than assuming from the finding's own note that this path
  "should already be safe."

## Instructions

1. In `story_new.py`'s `_append_to_phase`, escape `title` before it is
   interpolated into `new_row`: replace every literal `|` with `\|` (do not
   double-escape a `\|` that may already be present in the title — use a
   single unconditional `|` → `\|` replace, since a raw operator-supplied
   title cannot itself already contain the escape sequence).
2. Add a regression test to `tests/pairmode/test_story_new.py` that:
   - Calls `_append_to_phase` (or `story_new.py`'s public create path) with
     a title containing a pipe, e.g. `"handle Edit | Write correctly"`,
     against a temp phase doc fixture.
   - Reads the resulting phase doc's Stories table via
     `table_utils.split_table_row` (or by calling
     `next_action._check_phase_completion` against the fixture) and asserts
     the story's status column reads `draft` — the story's actual status —
     not a shifted value.
3. In the same test file (new test or an extension of the above), exercise
   `story_update._update_story_row_in_phase`'s status-flip rewrite on the
   pipe-bearing row (flip `draft` → `complete` or similar) and assert both:
   the title's `\|` escape is preserved unchanged after the rewrite, and
   the status column read back afterward is the newly-flipped value, not a
   shifted one.
4. Do not change `table_utils.split_table_row`'s reader-side contract — it
   already documents and implements the `\|` convention; this story only
   brings the one non-conformant writer into line with it.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
```
Acceptance: green, including the new pipe-bearing-title round-trip test
(read-back status is `draft`, not a shifted column) and the
`_update_story_row_in_phase` escape-preservation test.

## Out of scope

- CER-222 / `flex_build.py`'s `_append_touches_entry` oracle-verification
  fix — that is INFRA-415, the phase's other independent write site.
- Any other unescaped-writer audit across the codebase beyond the two named
  sites in the phase Goal — this story fixes only `_append_to_phase`'s
  title-escaping gap.
- Changing `table_utils.split_table_row`'s reader contract or escaping
  convention itself — this story conforms the writer to the existing
  reader contract, not the other way around.
