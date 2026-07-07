---
id: INFRA-187
rail: INFRA
title: "Body-section enforcement: non-pointer Ensures required for code and methodology stories"
status: planned
phase: "83"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/schema_validator.py
touches:
  - tests/pairmode/test_schema_validator.py
---

## Requires

- `validate_story_file` in `schema_validator.py` checks for `## Acceptance criterion` OR both `## Requires` and `## Ensures`. It does not inspect body section content.
- `VALID_STORY_CLASSES = {"code", "doc", "lesson", "methodology"}` is defined in `schema_validator.py`.
- `VALID_STORY_STATUSES` includes `"draft"` and `"backlog"`.

## Ensures

- `validate_story_file` returns a validation error containing `"pointer-only"` when a `code` or `methodology` story's Ensures/Acceptance section consists solely of a line matching `See (docs|phase)` (case-insensitive).
- `validate_story_file` returns no `pointer-only` error when the Ensures section contains at least one non-pointer assertion line.
- `validate_story_file` returns no error for `story_class: doc` or `story_class: lesson` regardless of body content.
- `validate_story_file` returns no error for stories with `status: draft` or `status: backlog` regardless of story_class.
- `validate_story_file` returns a validation error containing `"body section"` when a `code` or `methodology` story (not draft/backlog) has none of `## Ensures`, `## Acceptance criteria`, or `## Acceptance` present.
- The existing test suite passes without modification.
- `grep -n "_POINTER_ONLY_RE\|pointer.only" skills/pairmode/scripts/schema_validator.py` returns at least one match.

## Instructions

**1. Add constants to `schema_validator.py` after the existing regex constants (around line 27).**

```python
_POINTER_ONLY_RE = re.compile(
    r"^\s*See\s+(docs|phase)",
    re.IGNORECASE | re.MULTILINE,
)

_SECTION_BODY_RE = re.compile(
    r"^##\s+(?:Ensures|Acceptance criteria|Acceptance criterion|Acceptance)\s*\n(.*?)(?=^##|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
```

**2. Extend `validate_story_file` with body-section enforcement.**

Insert the new check after the existing acceptance-surface check (after the `if not has_acceptance_criterion and not (has_requires and has_ensures):` block). The logic:

```python
story_class = fm.get("story_class") or DEFAULT_STORY_CLASS
status = fm.get("status", "")
_ENFORCED_CLASSES = {"code", "methodology"}
_EXEMPT_STATUSES = {"draft", "backlog"}

if story_class in _ENFORCED_CLASSES and status not in _EXEMPT_STATUSES:
    has_body_section = any([
        "## Ensures" in text,
        "## Acceptance criteria" in text,
        "## Acceptance criterion" in text,
        "## Acceptance" in text,
    ])
    if not has_body_section:
        errors.append(
            f"Story class '{story_class}' requires at least one of "
            "## Ensures, ## Acceptance criteria, or ## Acceptance "
            "(body section missing for non-draft story)"
        )
    else:
        section_bodies = _SECTION_BODY_RE.findall(text)
        if section_bodies:
            all_pointer = all(
                _POINTER_ONLY_RE.search(body) and not any(
                    line.strip() and not _POINTER_ONLY_RE.match(line)
                    for line in body.splitlines()
                )
                for body in section_bodies
            )
            if all_pointer:
                errors.append(
                    f"Story class '{story_class}': ## Ensures / ## Acceptance "
                    "section is pointer-only (contains only 'See docs/phase' "
                    "delegation). Add binary-verifiable assertions. "
                    "(pointer-only section is not a valid acceptance surface)"
                )
```

Note: the error message contains both `"body section"` and `"pointer-only"` to satisfy both Ensures assertions.

**3. No changes to `_parse_frontmatter`, `validate_era_file`, or `validate_phase_manifest`.**

## Tests

Add to `tests/pairmode/test_schema_validator.py`:

**Pointer-only rejection:**
- `test_code_story_pointer_only_ensures_is_invalid(tmp_path)` — `code`/`planned` story with `## Ensures\nSee docs/phases/phase-83.md`; assert errors contain `"pointer-only"`.
- `test_methodology_story_pointer_only_ensures_is_invalid(tmp_path)` — same with `story_class: methodology`.
- `test_code_story_ensures_with_real_assertion_is_valid(tmp_path)` — `## Ensures\n- File foo.py exists`; assert no pointer-only error.
- `test_pointer_only_exempt_for_doc_class(tmp_path)` — `story_class: doc`, pointer-only Ensures; assert no error.
- `test_pointer_only_exempt_for_lesson_class(tmp_path)` — `story_class: lesson`, pointer-only Ensures; assert no error.
- `test_pointer_only_exempt_for_draft_status(tmp_path)` — `story_class: code`, `status: draft`, pointer-only Ensures; assert no error.
- `test_pointer_only_exempt_for_backlog_status(tmp_path)` — `story_class: code`, `status: backlog`, pointer-only Ensures; assert no error.

**Missing body section:**
- `test_code_story_missing_acceptance_surface_is_invalid(tmp_path)` — `story_class: code`, `status: planned`, body has `## Requires` but no Ensures/Acceptance heading; assert errors contain `"body section"`.
- `test_methodology_story_missing_acceptance_surface_is_invalid(tmp_path)` — same with `methodology`.
- `test_missing_acceptance_surface_exempt_for_draft(tmp_path)` — `status: draft`; assert no body-section error.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_schema_validator.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
