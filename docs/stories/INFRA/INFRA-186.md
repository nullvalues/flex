---
id: INFRA-186
rail: INFRA
title: "architecture.md template prompt in story_new.py and check-story-scope"
status: complete
phase: "83"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_story_new.py
  - tests/pairmode/test_flex_build.py
---

## Requires

- `story_new.py` function `_story_frontmatter` generates the `touches:` field as a bare key with no comment.
- `flex_build.py` subcommand `check-story-scope` (`cmd_check_story_scope`) exists, always exits 0, and implements heuristic rules (test co-location, template/live pair).
- `schema_validator.py` `_parse_frontmatter` strips trailing content after a colon on scalar fields — the inline comment on `touches:` will be ignored by the validator.

## Ensures

- The string `"docs/architecture.md"` appears in the output of `_story_frontmatter(...)` (the generated story frontmatter) as part of an inline comment on the `touches:` line.
- Running `story_new.py --rail TEST --title "foo" --story-class code` and reading the created file shows: the `touches:` line contains `# If this story changes any documented architecture, add docs/architecture.md to this list.`
- `grep -n "architecture.md" skills/pairmode/scripts/story_new.py` returns at least one match.
- `flex_build.py check-story-scope` emits the string `"Scope hint"` and `"docs/architecture.md"` when `story_class` is `code` and neither `primary_files` nor `touches` contains any path starting with `docs/`.
- When `story_class` is `methodology` or `doc`, the architecture hint is NOT emitted.
- When `touches` already contains a `docs/` path, the hint is NOT emitted.
- Exit code is 0 in all cases.

## Instructions

**1. Edit `story_new.py` — `_story_frontmatter` function.**

Locate the lines that append `"primary_files:"` and `"touches:"` to the frontmatter lines list. Change:

```python
lines += ["primary_files:", "touches:", "---"]
```

to:

```python
lines += [
    "primary_files:",
    "touches:  # If this story changes any documented architecture, add docs/architecture.md to this list.",
    "---",
]
```

This is a single-line change. `schema_validator.py`'s `_parse_frontmatter` uses `_YAML_SCALAR_RE` which strips trailing content after the colon — the comment is already ignored by validation. Verify by running the full test suite.

**2. Edit `flex_build.py` — `cmd_check_story_scope`.**

After the existing scope heuristic rules (test co-location rule, template/live pair rule), add a new rule before `sys.exit(0)`:

```python
# Rule: architecture.md prompt for code stories with no docs/ touches.
story_class = fm.get("story_class") or "code"
if story_class == "code":
    all_files = list(primary_files) + list(touches)
    has_docs_path = any(
        str(p).startswith("docs/") for p in all_files
    )
    if not has_docs_path:
        click.echo(
            "Scope hint: if this story affects documented architecture, "
            "add docs/architecture.md to touches."
        )
```

The `primary_files` and `touches` variables are already parsed earlier in `cmd_check_story_scope` from the story frontmatter. Insert this block before the final `sys.exit(0)`.

## Tests

**In `tests/pairmode/test_story_new.py`**, add:

- `test_story_frontmatter_touches_has_architecture_comment` — call `_story_frontmatter` (or `create_story` via tmp_path) with `story_class="code"` and assert the resulting frontmatter string contains `"docs/architecture.md"` on the `touches:` line.

**In `tests/pairmode/test_flex_build.py`**, add:

- `test_check_story_scope_code_no_docs_emits_architecture_hint(tmp_path)` — create a minimal story file with `story_class: code`, `primary_files: [skills/pairmode/scripts/foo.py]`, `touches: []`; run `check-story-scope` via CliRunner; assert output contains `"Scope hint"` and `"docs/architecture.md"`.
- `test_check_story_scope_code_with_docs_path_no_hint(tmp_path)` — same but `touches: [docs/architecture.md]`; assert output does NOT contain `"Scope hint"`.
- `test_check_story_scope_methodology_no_hint(tmp_path)` — `story_class: methodology`; assert output does NOT contain `"Scope hint"`.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py tests/pairmode/test_flex_build.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
