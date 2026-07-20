---
id: INFRA-211
rail: INFRA
title: Strip inline YAML comments from frontmatter list items in _parse_frontmatter
status: planned
phase: "HARNESS015-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/schema_validator.py
touches:
  - skills/pairmode/scripts/permission_scope.py
---

## Requires

- `schema_validator._parse_frontmatter()` (`skills/pairmode/scripts/schema_validator.py:40`)
  is a deliberately minimal, non-general YAML parser. Its block-sequence branch
  (`skills/pairmode/scripts/schema_validator.py:66-69`) appends
  `_YAML_LIST_ITEM_RE.match(line).group(1).strip()` verbatim — it does not strip
  a trailing `# ...` inline comment the way a real YAML parser would.
- Surfaced 2026-07-18 during an INFRA-202 build attempt: that story's frontmatter
  used inline-commented `touches` entries (a documented, encouraged pattern for
  explaining why a protected file is touched — see
  `docs/stories/INFRA/INFRA-202.md`'s `touches:` block), e.g.:
  ```yaml
  touches:
    - hooks/post_tool_use.py  # protected file — reason: ...
  ```
  `permission_scope.py::write_story_permissions()`
  (`skills/pairmode/scripts/permission_scope.py:29`) reads `touches` from
  `_parse_frontmatter()` and builds allow-rule strings directly from each raw
  entry (`skills/pairmode/scripts/permission_scope.py:58-69`), producing a
  malformed rule like `Edit(hooks/post_tool_use.py  # protected file — reason: ...)`
  instead of `Edit(hooks/post_tool_use.py)`. The malformed rule does not match
  the file path Claude Code's permission system checks against, so the
  intended unblock (`flex_build.py write-permissions --story-id <id>`) silently
  fails to grant usable access to protected files declared with an inline
  comment.
- Every other consumer of `_parse_frontmatter()`'s list fields (`primary_files`,
  `touches`, etc. — see call sites in `model_selector.py`, `record_attempt.py`,
  `story_resolver.py`, `index_integrity.py`, `flex_build.py`, `phase_new.py`,
  `pairmode_status.py`, `bootstrap.py`, `next_action.py`, `story_context.py`)
  is exposed to the same malformed-string risk for any frontmatter list item
  that carries an inline `#` comment.

## Ensures

- `_parse_frontmatter()`'s list-item branch strips a trailing inline comment
  from each block-sequence entry before appending it, using real-YAML-like
  semantics: a `#` is treated as a comment start only when preceded by
  whitespace (so `#` characters that are part of a legitimate unquoted value,
  e.g. a URL fragment or anchor, are not misparsed) — do not strip `#` that
  appears with no preceding whitespace.
- Quoted list items (`- "foo # bar"` / `- 'foo # bar'`) are exempt from
  comment-stripping — a `#` inside quotes is data, not a comment. Matching the
  existing scalar-value quote handling at
  `skills/pairmode/scripts/schema_validator.py:89-94` is sufficient (apply the
  same quote-strip-first, then comment-strip-only-if-unquoted order to list
  items).
- `permission_scope.py::write_story_permissions()` now produces clean
  `Edit(<path>)` / `Write(<path>)` rules for stories whose `touches`/
  `primary_files` entries carry inline comments — no code change needed in
  `permission_scope.py` itself if the fix lands in `_parse_frontmatter()`;
  confirm with a regression test at the `permission_scope.py` call site rather
  than only at the parser level.
- No existing frontmatter file's list-item values change under the fix
  (i.e. list items with no `#` in them parse identically to before).
- `tests/pairmode/` gets a unit test on `_parse_frontmatter()` covering: a
  plain list item, a list item with an inline `#` comment, a quoted list item
  containing a literal `#`, and a list item with `#` glued to non-whitespace
  content (must NOT be treated as a comment start).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

Edit the list-item branch of `_parse_frontmatter()`
(`skills/pairmode/scripts/schema_validator.py:66-69`). Before `.strip()`-ing
and appending `list_m.group(1)`, apply the same quote-handling used for scalar
values just below (`schema_validator.py:89-94`): if the trimmed value starts
and ends with matching quotes, strip them and treat the interior as literal
(no comment-stripping). Otherwise, split on a `#` that is preceded by
whitespace and take the portion before it, then `.strip()` the result.

Do not touch `permission_scope.py` logic itself — the fix belongs in the
shared parser so all fourteen-plus call sites benefit; `permission_scope.py`
is listed in `touches` only because its test coverage is where the
regression will be exercised end-to-end.

Do not change `_YAML_SCALAR_RE` / `_YAML_LIST_ITEM_RE` matching behavior for
non-comment lines, and do not attempt to support full YAML comment edge cases
(e.g. `#` inside flow-style `[a, b]` lists) — this parser explicitly only
supports block sequences and scalar values per its docstring.

## Tests

- New unit tests in `tests/pairmode/test_schema_validator.py` (or nearest
  existing test module for `_parse_frontmatter`) covering the four cases in
  Ensures above.
- Add or extend a `permission_scope.py` test asserting that a story fixture
  with an inline-commented `touches` entry produces a clean
  `Edit(<path>)`/`Write(<path>)` rule with no trailing comment text.
- Full suite: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.
