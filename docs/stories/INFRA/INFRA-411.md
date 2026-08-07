---
id: INFRA-411
rail: INFRA
title: Fix story_new.py writer/reader escaping mismatch (CER-213)
status: complete
phase: "141"
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

`story_new.py`'s `_yaml_block_scalar` (CER-167/CER-211) escapes any non-plain
`primary_files:`/`touches:` entry via `json.dumps`, which assumes a
`yaml.safe_load`-style reader that unescapes backslash sequences (`\"`, `\\`,
`\n`, `\t`, `\uXXXX`). The project's only story-frontmatter reader,
`schema_validator._parse_frontmatter` via `_strip_inline_comment`, strips one
matching pair of outer quote characters *literally* and never unescapes
anything. So a quoted value with an embedded quote character, a real tab, or
a real newline is silently corrupted on read — a regression versus
pre-INFRA-409 behaviour for the quote/tab cases (CER-213). This story reworks
the writer to escape for the reader that actually exists.

## Requires

None — the bug is isolated to `story_new.py`'s own writer helper and its own
test suite.

## Ensures

- `_yaml_block_scalar` still emits a value bare, unchanged, when the existing
  `is_plain` check (leading-indicator char, `": "`, trailing `:`,
  embedded newline/tab, leading/trailing whitespace, `" #"`) says it is safe
  to do so — this behaviour is unchanged from today.
- For a non-plain value containing no real newline: `_yaml_block_scalar`
  wraps it in a single matching pair of quote characters — `"` when the value
  contains no `"`, else `'` when the value contains no `'` — with the value's
  own bytes emitted *literally inside the quotes, with no backslash
  escaping*. Forbidden proxy: continuing to run the value through
  `json.dumps` (or any other escaping scheme) before quoting it, since
  `_strip_inline_comment` never unescapes on read and any backslash sequence
  written that way is returned to the caller unchanged (as literal backslash
  + letter), not as the character it was meant to represent.
- For every value in the above bullet — including one containing a real tab
  character — `schema_validator._parse_frontmatter` (the real reader, not
  `yaml.safe_load`/`json.loads`) recovers the exact original value,
  byte-for-byte, when the emitted line is round-tripped through it as a
  `primary_files:`/`touches:` list item.
- For a value containing *both* `"` and `'` (no quote character is available
  to wrap it in that isn't also present as data), and for a value containing
  a real newline (structurally unrepresentable as a single frontmatter line
  under this project's line-based reader, regardless of quoting):
  `_yaml_block_scalar` raises `ValueError` with a message naming the
  unrepresentable value, rather than emitting something that would silently
  corrupt on read. Forbidden proxy: falling back to `json.dumps` escaping (or
  any other silent "best effort" encoding) for these two cases instead of
  raising — that is exactly the corruption this story closes.
- `tests/pairmode/test_story_new.py`'s `TestYamlBlockScalarQuoting` class
  round-trips every case through the real writer
  (`_yaml_block_scalar`/`_story_frontmatter`) and the real reader
  (`schema_validator._parse_frontmatter`, via this file's existing
  `_read_story_frontmatter` helper) — not `json.loads`/`yaml.safe_load` — and
  covers: a plain value (bare, unchanged); a value needing quoting with
  neither quote character present (colon-space case); a value containing one
  quote character only (wrapped in the other); a value containing a real tab
  (round-trips exactly); a value containing both quote characters (raises
  `ValueError`); a value containing a real newline (raises `ValueError`).

## Instructions

1. In `skills/pairmode/scripts/story_new.py`, rewrite `_yaml_block_scalar`'s
   non-plain branch (currently `return json.dumps(value)`):
   - If `"\n" in value`: `raise ValueError(...)` naming the value and stating
     that an embedded newline cannot be represented as a single frontmatter
     line by this project's reader.
   - Else if `'"' not in value`: wrap in double quotes and return the value
     literally between them (`f'"{value}"'`), no escaping.
   - Else if `"'" not in value`: wrap in single quotes and return the value
     literally between them (`f"'{value}'"`), no escaping.
   - Else (both quote characters present): `raise ValueError(...)` naming the
     value and stating that no single quote character in this reader's
     literal-strip scheme can wrap it.
   - The existing `is_plain` check and its `return value` branch are
     unchanged. `json` no longer needs to be imported by this module if
     `_yaml_block_scalar` was its only caller — check and remove the now-dead
     `import json` only if nothing else in the file uses it (the test file's
     own `import json` usage is separate and covered by step 3 below).
2. Update the module docstring on `_yaml_block_scalar` to describe the new
   literal-quoting/raise behaviour in place of the `json.dumps` description
   (the current docstring's "via `json.dumps`" paragraph is now false).
3. Rework `tests/pairmode/test_story_new.py`'s `TestYamlBlockScalarQuoting`
   class (and its `_round_trip` helper) to use the real reader as the
   round-trip oracle instead of `json.loads`:
   - Replace `_round_trip`'s `json.loads(emitted)` branch with a call through
     `schema_validator._parse_frontmatter` (or this file's existing
     `_read_story_frontmatter`/`_story_frontmatter` helpers, whichever the
     surrounding tests in this file already use) on a minimal frontmatter
     block containing the emitted line as a `primary_files:` list item.
   - `test_value_with_embedded_newline_is_quoted_and_round_trips` and
     `test_touches_entry_with_newline_round_trips_through_frontmatter`
     currently assert a newline value round-trips; per Ensures above this is
     now a raise, not a round-trip — rewrite both as
     `pytest.raises(ValueError)` cases (rename to drop "round_trips" from the
     name if the new assertion no longer round-trips anything).
   - `test_forbidden_proxy_value_not_altered`'s value
     (`'  leading/trailing spaces and a " quote  '`) contains `"` but not
     `'`; update its assertion to expect single-quote wrapping and route the
     round-trip through the real reader.
   - Add one new case for a value containing a real tab character
     (e.g. `"a\tb.py"`) asserting it round-trips exactly through the real
     writer+reader pair — this is the regression CER-213 exists to close.
   - Add one new case for a value containing both `"` and `'`
     (e.g. `\"\"\"it's a \\"test\\"\"\"\"` — any value with both characters
     present) asserting `_yaml_block_scalar` raises `ValueError`.
   - Any other test in this class or file that asserts on the specific
     `json.dumps`-escaped shape of an emitted value (rather than only on
     round-trip correctness) needs its assertion updated to the new literal
     quoting shape.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
```
Acceptance: green, including the reworked `TestYamlBlockScalarQuoting` class
and its new tab/both-quote-characters cases.

## Out of scope

- Changing `schema_validator._parse_frontmatter`/`_strip_inline_comment`
  itself to become an unescaping reader (e.g. adopting real YAML
  escape-sequence semantics) — this story fixes the writer to match the
  reader that exists today, not the reader to match the writer's old
  assumptions.
- The `title:` scalar's own `#`-quoting branch in `story_new.py` (CER-092) —
  untouched by this story, as the phase goal notes.
- Any other caller of `json.dumps` elsewhere in the codebase for a purpose
  unrelated to `primary_files:`/`touches:` frontmatter emission.
