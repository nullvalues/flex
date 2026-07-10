---
id: INFRA-188
rail: INFRA
title: "Scope budget warning in check-story-scope"
status: complete
phase: "83"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build.py
---

## Requires

- `flex_build.py` subcommand `check-story-scope` (`cmd_check_story_scope`) exists, always exits 0, and implements heuristic scope rules.
- INFRA-186 may or may not be landed. If it has landed, Rule 3 (architecture.md hint) already exists; this story adds the scope budget rule after it. If it has not yet landed, add the scope budget rule after whichever rules currently exist.

## Ensures

- `flex_build.py check-story-scope RAIL-NNN` emits a message containing `"Scope budget: story declares N files"` (where N is the actual count) when `len(primary_files) + len(touches) > 8`.
- The message also contains `"consider splitting"`.
- When `len(primary_files) + len(touches) <= 8`, the scope budget message is NOT emitted.
- Exit code is 0 in all cases (informational, not blocking).
- `grep -n "Scope budget" skills/pairmode/scripts/flex_build.py` returns at least one match.

## Instructions

**1. Edit `cmd_check_story_scope` in `flex_build.py`.**

After all existing rules and before `sys.exit(0)`, add:

```python
# Scope budget warning.
total_declared = len(list(primary_files)) + len(list(touches))
if total_declared > 8:
    click.echo(
        f"Scope budget: story declares {total_declared} files — "
        f"consider splitting if stories are independently reviewable."
    )
```

The `primary_files` and `touches` variables are already parsed from the story frontmatter earlier in the function. Insert immediately before `sys.exit(0)`.

**2. No other changes to `flex_build.py`.**

## Tests

Add to `tests/pairmode/test_flex_build.py`:

- `test_scope_budget_warning_emitted_when_over_limit(tmp_path)` — story with 5 `primary_files` and 5 `touches` (10 total > 8); run `check-story-scope` via CliRunner; assert output contains `"Scope budget"` and `"10 files"` and `"consider splitting"`; assert exit code 0.
- `test_scope_budget_no_warning_at_limit(tmp_path)` — 4 `primary_files` + 4 `touches` = 8 total; assert output does NOT contain `"Scope budget"`.
- `test_scope_budget_no_warning_when_empty(tmp_path)` — both lists empty; assert no Scope budget message.
- `test_scope_budget_exit_code_zero(tmp_path)` — over-limit story; assert exit code 0.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build.py -x -q -k "scope_budget"
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
