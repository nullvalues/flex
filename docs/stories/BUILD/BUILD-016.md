---
id: BUILD-016
rail: BUILD
title: Bootstrap era strategic intent prompt
status: complete
phase: "52"
story_class: code
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_bootstrap.py
---

# BUILD-016 — Bootstrap era strategic intent prompt

## Background

`bootstrap.py` creates `docs/eras/001-initial.md` as part of the project
scaffold, but passes `_(fill in)_` as the strategic intent. There is no
interactive prompt for it — the bootstrap flow collects project name, stack,
ideology convictions, value hierarchy, and constraints, but leaves the era's
most important field blank.

The era's strategic intent is the one-paragraph answer to "what is this era
trying to accomplish?" — the same question the Plan subagent (BUILD-015) will
read to understand where a new phase fits. A blank placeholder at bootstrap
means every downstream project needs a manual edit before the spec workflow
is useful.

## Ensures

- `bootstrap.py` interactive flow prompts for era strategic intent after
  collecting the project name and before (or alongside) the ideology questions.
  Prompt text: `"Era strategic intent — what is this project's initial era
  trying to accomplish?\nEnter a sentence or two, or press Enter to fill in
  later"`.
- The entered text (or empty string) is passed to `_build_era_001_content()`
  and written into the `## Strategic intent` section of `docs/eras/001-initial.md`.
- `--yes` / non-interactive mode: skips the prompt; strategic intent remains
  `_(fill in)_` (existing behaviour preserved for CI).
- `_build_era_001_content(project_name, rails, strategic_intent="")` signature
  updated; empty string produces `_(fill in)_` placeholder as before.
- Existing tests continue to pass; new test covers the prompted-intent path.

## Out of scope

- Changing the era file format or adding new fields.
- Retroactively updating era files on existing projects (manual edit).

## Instructions

### 1. Update `_build_era_001_content` signature

```python
def _build_era_001_content(
    project_name: str,
    rails: list[str],
    strategic_intent: str = "",
) -> str:
```

In the `strategic_intent` section, replace the hardcoded `_(fill in)_` with:

```python
intent_body = strategic_intent.strip() if strategic_intent.strip() else "_(fill in)_"
strategic_intent_section = f"\n## Strategic intent\n\n{intent_body}\n"
```

### 2. Add prompt to the bootstrap interactive flow

In the main `bootstrap()` command, after collecting `project_name` and before
the ideology block, add:

```python
if yes:
    era_intent = ""
else:
    era_intent = click.prompt(
        "\nEra strategic intent\n"
        "What is this project's initial era trying to accomplish?\n"
        "Enter a sentence or two, or press Enter to fill in later",
        default="",
        show_default=False,
    ).strip()
```

Store `era_intent` in the context dict passed to `_initialize_rails()`.

### 3. Thread `era_intent` through to `_build_era_001_content`

Update `_initialize_rails(context, ...)` to read `context.get("era_intent", "")`
and pass it to `_build_era_001_content(project_name, confirmed_rails, era_intent)`.

## Tests

`tests/pairmode/test_bootstrap.py` (extend):

1. `test_era_strategic_intent_written` — invoke `_build_era_001_content` with
   a non-empty `strategic_intent`; assert it appears verbatim in the output
   under `## Strategic intent`.
2. `test_era_strategic_intent_empty_gives_placeholder` — invoke with
   `strategic_intent=""`; assert output contains `_(fill in)_`.
3. `test_bootstrap_yes_mode_leaves_placeholder` — run `_initialize_rails` with
   `yes=True`; assert created era file contains `_(fill in)_`.
