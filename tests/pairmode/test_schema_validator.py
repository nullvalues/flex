"""Tests for skills/pairmode/scripts/schema_validator.py"""

import sys
from pathlib import Path
import tempfile
import textwrap

import pytest

# Allow import of sibling scripts without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))

from schema_validator import (
    validate_story_file,
    validate_era_file,
    validate_phase_manifest,
    VALID_STORY_CLASSES,
    DEFAULT_STORY_CLASS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Story file tests
# ---------------------------------------------------------------------------

VALID_STORY = """\
    ---
    id: FEAT-001
    rail: FEAT
    title: My first story
    status: planned
    phase: "001"
    primary_files:
      - src/main.py
    ---

    ## Acceptance criterion

    It works.

    ## Instructions

    Do the thing.

    ## Tests

    Run the tests.
"""

def test_valid_story_file(tmp_path):
    p = _write(tmp_path, "FEAT-001.md", VALID_STORY)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_story_missing_id(tmp_path):
    content = VALID_STORY.replace("id: FEAT-001\n", "")
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert any("id" in e for e in errors), f"Expected 'id' error, got: {errors}"


def test_story_missing_primary_files(tmp_path):
    # Remove the primary_files block entirely
    lines = textwrap.dedent(VALID_STORY).splitlines(keepends=True)
    filtered = [
        line for line in lines
        if "primary_files" not in line and "src/main.py" not in line
    ]
    p = _write(tmp_path, "story.md", "".join(filtered))
    errors = validate_story_file(p)
    assert any("primary_files" in e for e in errors), f"Expected 'primary_files' error, got: {errors}"


def test_story_invalid_status(tmp_path):
    content = VALID_STORY.replace("status: planned", "status: unknown-status")
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert any("status" in e.lower() for e in errors), f"Expected status error, got: {errors}"


def test_story_draft_empty_primary_files_allowed(tmp_path):
    """status: draft with empty primary_files must not produce an error."""
    content = (
        VALID_STORY
        .replace("status: planned", "status: draft")
        .replace("  - src/main.py\n", "")
    )
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert not any("primary_files" in e for e in errors), (
        f"Expected no primary_files error for draft story, got: {errors}"
    )


def test_story_backlog_empty_primary_files_allowed(tmp_path):
    """status: backlog with empty primary_files must not produce an error."""
    content = (
        VALID_STORY
        .replace("status: planned", "status: backlog")
        .replace("  - src/main.py\n", "")
    )
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert not any("primary_files" in e for e in errors), (
        f"Expected no primary_files error for backlog story, got: {errors}"
    )


def test_story_planned_empty_primary_files_errors(tmp_path):
    """status: planned with empty primary_files must produce an error."""
    content = VALID_STORY.replace("  - src/main.py\n", "")
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert any("primary_files" in e for e in errors), (
        f"Expected primary_files error for planned story, got: {errors}"
    )


def test_story_complete_with_primary_files_no_error(tmp_path):
    """status: complete with non-empty primary_files must not produce an error."""
    content = VALID_STORY.replace("status: planned", "status: complete")
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors for complete story with files, got: {errors}"


# ---------------------------------------------------------------------------
# story_class field tests
# ---------------------------------------------------------------------------

def test_story_class_absent_is_valid(tmp_path):
    """A story without story_class is valid — the field is optional."""
    p = _write(tmp_path, "story.md", VALID_STORY)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors when story_class is absent, got: {errors}"


def test_story_class_constants():
    """VALID_STORY_CLASSES contains exactly the four documented values."""
    assert VALID_STORY_CLASSES == {"code", "doc", "lesson", "methodology"}


def test_default_story_class_is_code():
    """DEFAULT_STORY_CLASS must be 'code'."""
    assert DEFAULT_STORY_CLASS == "code"


@pytest.mark.parametrize("cls", ["code", "doc", "lesson", "methodology"])
def test_story_class_valid_values(tmp_path, cls):
    """Each allowed story_class value passes validation."""
    content = VALID_STORY.replace(
        '    phase: "001"\n',
        f'    phase: "001"\n    story_class: {cls}\n',
    )
    p = _write(tmp_path, f"story-{cls}.md", content)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors for story_class={cls!r}, got: {errors}"


def test_story_class_invalid_value(tmp_path):
    """An unrecognised story_class value produces a validation error."""
    content = VALID_STORY.replace(
        '    phase: "001"\n',
        '    phase: "001"\n    story_class: unknown\n',
    )
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert any("story_class" in e for e in errors), (
        f"Expected story_class error for invalid value, got: {errors}"
    )


def test_story_class_error_message_lists_valid_values(tmp_path):
    """Error message for invalid story_class lists the allowed values."""
    content = VALID_STORY.replace(
        '    phase: "001"\n',
        '    phase: "001"\n    story_class: bad-value\n',
    )
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    story_class_errors = [e for e in errors if "story_class" in e]
    assert story_class_errors, "Expected at least one story_class error"
    # The error should mention the invalid value
    assert "bad-value" in story_class_errors[0]


# ---------------------------------------------------------------------------
# source field tests
# ---------------------------------------------------------------------------

def test_source_field_absent_is_valid(tmp_path):
    """A story without source is valid — the field is optional."""
    p = _write(tmp_path, "story.md", VALID_STORY)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors when source is absent, got: {errors}"


def test_source_field_present_with_value_is_valid(tmp_path):
    """A story with a non-empty source value passes validation."""
    content = VALID_STORY.replace(
        '    phase: "001"\n',
        '    phase: "001"\n    source: my-project\n',
    )
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors for valid source, got: {errors}"


def test_source_field_empty_string_is_invalid(tmp_path):
    """A story with an empty source value produces a validation error."""
    content = VALID_STORY.replace(
        '    phase: "001"\n',
        '    phase: "001"\n    source: \n',
    )
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert any("source" in e for e in errors), (
        f"Expected source error for empty value, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Body-section contract validation tests
# ---------------------------------------------------------------------------

VALID_STORY_NEW_FORMAT = """\
    ---
    id: FEAT-002
    rail: FEAT
    title: New contract format story
    status: draft
    phase: "001"
    primary_files:
    ---

    ## Requires
    <!-- preconditions -->

    ## Ensures
    <!-- assertions -->

    ## Instructions

    ## Tests
"""

VALID_STORY_BOTH_FORMATS = """\
    ---
    id: FEAT-003
    rail: FEAT
    title: Transition story
    status: draft
    phase: "001"
    primary_files:
    ---

    ## Acceptance criterion

    Legacy criterion.

    ## Requires
    <!-- preconditions -->

    ## Ensures
    <!-- assertions -->

    ## Instructions

    ## Tests
"""

INVALID_STORY_NO_CONTRACT = """\
    ---
    id: FEAT-004
    rail: FEAT
    title: Story missing contract sections
    status: draft
    phase: "001"
    primary_files:
    ---

    ## Instructions

    Do the thing.

    ## Tests

    Run the tests.
"""


def test_story_new_contract_format_validates(tmp_path):
    """Story with ## Requires and ## Ensures (new format) is valid."""
    p = _write(tmp_path, "FEAT-002.md", VALID_STORY_NEW_FORMAT)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors for new contract format, got: {errors}"


def test_story_legacy_format_validates(tmp_path):
    """Story with ## Acceptance criterion (legacy format) is valid."""
    p = _write(tmp_path, "FEAT-001.md", VALID_STORY)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors for legacy format, got: {errors}"


def test_story_both_formats_validates(tmp_path):
    """Story with both ## Acceptance criterion and ## Requires/## Ensures is valid."""
    p = _write(tmp_path, "FEAT-003.md", VALID_STORY_BOTH_FORMATS)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors when both formats present, got: {errors}"


def test_story_neither_format_is_invalid(tmp_path):
    """Story with neither ## Acceptance criterion nor ## Requires/## Ensures is invalid."""
    p = _write(tmp_path, "FEAT-004.md", INVALID_STORY_NO_CONTRACT)
    errors = validate_story_file(p)
    assert errors, "Expected at least one error when no contract section is present"
    assert any("Acceptance criterion" in e or "Requires" in e or "Ensures" in e for e in errors), (
        f"Expected error mentioning contract sections, got: {errors}"
    )


def test_story_with_only_requires_but_no_ensures_is_invalid(tmp_path):
    """Story with ## Requires but missing ## Ensures is invalid (both required for new format)."""
    content = textwrap.dedent(INVALID_STORY_NO_CONTRACT).replace(
        "## Instructions", "## Requires\n<!-- preconditions -->\n\n## Instructions"
    )
    p = _write(tmp_path, "partial.md", content)
    errors = validate_story_file(p)
    assert errors, "Expected error when ## Ensures is absent but ## Requires is present"


def test_story_with_only_ensures_but_no_requires_is_invalid(tmp_path):
    """Story with ## Ensures but missing ## Requires is invalid (both required for new format)."""
    content = textwrap.dedent(INVALID_STORY_NO_CONTRACT).replace(
        "## Instructions", "## Ensures\n<!-- assertions -->\n\n## Instructions"
    )
    p = _write(tmp_path, "partial.md", content)
    errors = validate_story_file(p)
    assert errors, "Expected error when ## Requires is absent but ## Ensures is present"


# ---------------------------------------------------------------------------
# Era file tests
# ---------------------------------------------------------------------------

VALID_ERA = """\
    ---
    id: "001"
    name: Foundation Era
    status: active
    ---

    ## Strategic intent

    Build the foundation.

    ## Rails

    | Rail | Primary domain |
    |------|----------------|
    | FEAT | Core features |

    ## Phases

    | Phase | Title |
    |-------|-------|
    | 001 | Kickoff |
"""


def test_valid_era_file(tmp_path):
    p = _write(tmp_path, "001-foundation.md", VALID_ERA)
    errors = validate_era_file(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_era_missing_status(tmp_path):
    # Dedent first so the replacement operates on the normalised text
    content = textwrap.dedent(VALID_ERA).replace("status: active\n", "")
    p = tmp_path / "era.md"
    p.write_text(content, encoding="utf-8")
    errors = validate_era_file(p)
    assert any("status" in e for e in errors), f"Expected 'status' error, got: {errors}"


# ---------------------------------------------------------------------------
# Phase manifest tests
# ---------------------------------------------------------------------------

VALID_PHASE_MANIFEST = """\
    ---
    era: "001"
    ---

    ## Goal

    Ship story 15.0.

    ## Stories

    | ID | Title | Status |
    |----|-------|--------|
    | FEAT-001 | My first story | planned |
"""


def test_valid_phase_manifest(tmp_path):
    p = _write(tmp_path, "phase-15.md", VALID_PHASE_MANIFEST)
    errors = validate_phase_manifest(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_phase_manifest_missing_era(tmp_path):
    # Dedent first so the replacement operates on the normalised text
    content = textwrap.dedent(VALID_PHASE_MANIFEST).replace('era: "001"\n', "")
    p = tmp_path / "phase.md"
    p.write_text(content, encoding="utf-8")
    errors = validate_phase_manifest(p)
    assert any("era" in e for e in errors), f"Expected 'era' error, got: {errors}"


# ---------------------------------------------------------------------------
# auth_gated and schema_introduces field tests
# ---------------------------------------------------------------------------

def _story_with_field(extra_field: str) -> str:
    """Return a valid story with an extra frontmatter field inserted after phase."""
    return VALID_STORY.replace(
        '    phase: "001"\n',
        f'    phase: "001"\n    {extra_field}\n',
    )


def test_story_validates_with_auth_gated_false(tmp_path):
    """auth_gated: false is accepted without errors."""
    p = _write(tmp_path, "story.md", _story_with_field("auth_gated: false"))
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_story_validates_with_auth_gated_true(tmp_path):
    """auth_gated: true is accepted without errors."""
    p = _write(tmp_path, "story.md", _story_with_field("auth_gated: true"))
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_story_validates_with_schema_introduces_false(tmp_path):
    """schema_introduces: false is accepted without errors."""
    p = _write(tmp_path, "story.md", _story_with_field("schema_introduces: false"))
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_story_validates_with_schema_introduces_true(tmp_path):
    """schema_introduces: true is accepted without errors."""
    p = _write(tmp_path, "story.md", _story_with_field("schema_introduces: true"))
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_story_validates_without_new_fields(tmp_path):
    """A story missing both auth_gated and schema_introduces passes (backwards compat)."""
    p = _write(tmp_path, "story.md", VALID_STORY)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors when new fields absent, got: {errors}"


def test_story_fails_validation_auth_gated_non_boolean(tmp_path):
    """auth_gated: yes (non-boolean string) emits a validation error."""
    p = _write(tmp_path, "story.md", _story_with_field("auth_gated: yes"))
    errors = validate_story_file(p)
    assert any("auth_gated" in e for e in errors), (
        f"Expected auth_gated error for non-boolean value, got: {errors}"
    )


def test_story_fails_validation_schema_introduces_non_boolean(tmp_path):
    """schema_introduces: 1 (non-boolean string) emits a validation error."""
    p = _write(tmp_path, "story.md", _story_with_field("schema_introduces: 1"))
    errors = validate_story_file(p)
    assert any("schema_introduces" in e for e in errors), (
        f"Expected schema_introduces error for non-boolean value, got: {errors}"
    )
