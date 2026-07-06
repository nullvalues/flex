---
id: INFRA-189
rail: INFRA
title: "test_gate frontmatter annotation for deferred whole-suite green"
status: planned
phase: "83"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/schema_validator.py
  - skills/pairmode/scripts/story_new.py
  - skills/pairmode/templates/agents/reviewer.md.j2
touches:
  - .claude/agents/reviewer.md
  - tests/pairmode/test_schema_validator.py
  - tests/pairmode/test_story_new.py
---

## Requires

- `schema_validator.py` defines `VALID_STORY_CLASSES` and validates frontmatter fields.
- `story_new.py` `_story_frontmatter` function emits frontmatter fields; the CLI uses click options.
- The reviewer template at `skills/pairmode/templates/agents/reviewer.md.j2` contains a test run section with `{{ test_command }}`.

## Ensures

- `grep -n "VALID_TEST_GATES\|test_gate" skills/pairmode/scripts/schema_validator.py` returns at least one match.
- `validate_story_file` returns a validation error when `test_gate` is present with a value not in `{"story", "phase_checkpoint", "none"}`.
- `validate_story_file` returns no error when `test_gate` is absent.
- `validate_story_file` returns no error for each of: `test_gate: story`, `test_gate: phase_checkpoint`, `test_gate: none`.
- `grep -n "\-\-test-gate\|test_gate" skills/pairmode/scripts/story_new.py` returns at least one match.
- When `story_new.py` is called with `--test-gate phase_checkpoint`, the generated story file contains `test_gate: phase_checkpoint` in its frontmatter.
- When called without `--test-gate`, `test_gate` is absent from the generated frontmatter.
- `grep -n "phase_checkpoint" skills/pairmode/templates/agents/reviewer.md.j2` returns at least one match describing the deferred-suite behavior.
- `grep -n "phase_checkpoint" .claude/agents/reviewer.md` returns at least one match (live reviewer updated).

## Instructions

**1. Edit `schema_validator.py` — add constant and validation.**

After `VALID_STORY_CLASSES` (around line 94), add:

```python
VALID_TEST_GATES = {"story", "phase_checkpoint", "none"}
```

In `validate_story_file`, after the `auth_gated` / `schema_introduces` checks, add:

```python
if "test_gate" in fm and fm["test_gate"] not in VALID_TEST_GATES:
    errors.append(
        f"Invalid test_gate '{fm['test_gate']}'; must be one of "
        f"{sorted(VALID_TEST_GATES)} when present"
    )
```

**2. Edit `story_new.py` — add `--test-gate` CLI option.**

Add a new click option to the `story_new` command:

```python
@click.option(
    "--test-gate",
    default=None,
    type=click.Choice(["story", "phase_checkpoint", "none"], case_sensitive=True),
    help="Optional test gate override. Omit to use default (story-level suite green).",
)
```

Update the `story_new` function signature to include `test_gate: str | None`.

Update `_story_frontmatter` to accept `test_gate: str | None = None`. When `test_gate is not None`, insert `test_gate: {test_gate}` into the frontmatter lines before `primary_files:`. Update the call in `story_new()` to pass `test_gate`.

Also update `create_story` (the programmatic API) to accept `test_gate: str | None = None` and forward it to `_story_frontmatter`.

**3. Edit `skills/pairmode/templates/agents/reviewer.md.j2` — extend test run section.**

In the `## Test run` section, after the test command block, add:

```markdown
**test_gate behaviour** — read the `test_gate` field from the story's frontmatter before running tests:

- `test_gate` absent or `test_gate: story` (default): run the full suite (`{{ test_command }}`). Whole-suite green required for PASS.
- `test_gate: phase_checkpoint`: run only tests whose file path or test name matches the story's primary module (derive from `primary_files` stems, e.g. `INFRA-189` with `schema_validator.py` → run `test_schema_validator`). Whole-suite green is deferred to the phase checkpoint; only story-related tests must pass. If no story-specific tests are identified, run the full suite.
- `test_gate: none`: skip the test run. Note: a `code` story with `test_gate: none` is a HIGH finding.
```

**4. Update `.claude/agents/reviewer.md` (live flex reviewer).**

Apply the equivalent `test_gate behaviour` block to the `## Test run` section of the live reviewer file.

## Tests

**In `tests/pairmode/test_schema_validator.py`**, add a `TestTestGateField` class:

- `test_test_gate_absent_is_valid(tmp_path)`
- `test_test_gate_story_is_valid(tmp_path)`
- `test_test_gate_phase_checkpoint_is_valid(tmp_path)`
- `test_test_gate_none_is_valid(tmp_path)`
- `test_test_gate_invalid_value_is_error(tmp_path)` — `test_gate: always`; assert errors contain `"Invalid test_gate"`.

**In `tests/pairmode/test_story_new.py`**, add:

- `test_story_new_with_test_gate_writes_field(tmp_path)` — call `create_story(..., test_gate="phase_checkpoint")`; assert `test_gate: phase_checkpoint` in frontmatter.
- `test_story_new_without_test_gate_omits_field(tmp_path)` — call `create_story(...)` without `test_gate`; assert `test_gate` absent from file.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_schema_validator.py tests/pairmode/test_story_new.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
