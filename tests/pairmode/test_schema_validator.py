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
    VALID_MODEL_TIERS,
    _parse_frontmatter,
    _parse_flow_sequence,
    _valid_narrative_roles,
    FrontmatterError,
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


def test_draft_story_with_no_primary_files_key_validates(tmp_path):
    """Draft story with no primary_files key at all validates successfully (CER-006)."""
    content = """\
---
id: DRAFT-001
rail: DRAFT
title: Draft story without primary_files
status: draft
phase: "001"
---

## Requires
<!-- preconditions -->

## Ensures
<!-- assertions -->

## Instructions

## Tests
"""
    p = tmp_path / "DRAFT-001.md"
    p.write_text(content, encoding="utf-8")
    errors = validate_story_file(p)
    pf_errors = [e for e in errors if "primary_files" in e]
    assert pf_errors == [], f"Expected no primary_files errors for draft story, got: {pf_errors}"


def test_non_draft_story_with_no_primary_files_key_fails(tmp_path):
    """Non-draft story with no primary_files key fails validation (CER-006)."""
    content = """\
---
id: PLANNED-001
rail: PLANNED
title: Planned story without primary_files
status: planned
phase: "001"
---

## Requires
<!-- preconditions -->

## Ensures
<!-- assertions -->

## Instructions

## Tests
"""
    p = tmp_path / "PLANNED-001.md"
    p.write_text(content, encoding="utf-8")
    errors = validate_story_file(p)
    assert any("primary_files" in e for e in errors), (
        f"Expected primary_files error for non-draft story missing the key, got: {errors}"
    )


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


# ---------------------------------------------------------------------------
# Pointer-only and body-section enforcement tests (INFRA-187)
# ---------------------------------------------------------------------------

def _code_story_with_ensures(ensures_body: str, story_class: str = "code", status: str = "planned") -> str:
    """Return a story with ## Requires + ## Ensures whose body is *ensures_body*."""
    return textwrap.dedent(f"""\
        ---
        id: FEAT-010
        rail: FEAT
        title: Pointer-only test
        status: {status}
        phase: "083"
        story_class: {story_class}
        primary_files:
          - src/main.py
        ---

        ## Requires

        Prior story complete.

        ## Ensures

        {ensures_body}

        ## Instructions

        Do the thing.
    """)


def test_code_story_pointer_only_ensures_is_invalid(tmp_path):
    """code/planned story with pointer-only Ensures should produce a pointer-only error."""
    content = _code_story_with_ensures("See docs/phases/phase-83.md")
    p = _write(tmp_path, "FEAT-010.md", content)
    errors = validate_story_file(p)
    assert any("pointer-only" in e for e in errors), (
        f"Expected pointer-only error for code story, got: {errors}"
    )


def test_methodology_story_pointer_only_ensures_is_invalid(tmp_path):
    """methodology/planned story with pointer-only Ensures should produce a pointer-only error."""
    content = _code_story_with_ensures("See phase doc for details.", story_class="methodology")
    p = _write(tmp_path, "FEAT-010.md", content)
    errors = validate_story_file(p)
    assert any("pointer-only" in e for e in errors), (
        f"Expected pointer-only error for methodology story, got: {errors}"
    )


def test_code_story_ensures_with_real_assertion_is_valid(tmp_path):
    """code story with a real assertion in Ensures should not produce a pointer-only error."""
    content = _code_story_with_ensures("- File foo.py exists and contains the expected function.")
    p = _write(tmp_path, "FEAT-010.md", content)
    errors = validate_story_file(p)
    assert not any("pointer-only" in e for e in errors), (
        f"Expected no pointer-only error for story with real assertion, got: {errors}"
    )


def test_pointer_only_exempt_for_doc_class(tmp_path):
    """doc class story with pointer-only Ensures should not produce a pointer-only error."""
    content = _code_story_with_ensures("See docs/phases/phase-83.md", story_class="doc")
    p = _write(tmp_path, "FEAT-010.md", content)
    errors = validate_story_file(p)
    assert not any("pointer-only" in e for e in errors), (
        f"Expected no pointer-only error for doc class story, got: {errors}"
    )


def test_pointer_only_exempt_for_lesson_class(tmp_path):
    """lesson class story with pointer-only Ensures should not produce a pointer-only error."""
    content = _code_story_with_ensures("See docs/phases/phase-83.md", story_class="lesson")
    p = _write(tmp_path, "FEAT-010.md", content)
    errors = validate_story_file(p)
    assert not any("pointer-only" in e for e in errors), (
        f"Expected no pointer-only error for lesson class story, got: {errors}"
    )


def test_pointer_only_exempt_for_draft_status(tmp_path):
    """code/draft story with pointer-only Ensures should not produce a pointer-only error."""
    content = _code_story_with_ensures(
        "See docs/phases/phase-83.md",
        story_class="code",
        status="draft",
    ).replace("  - src/main.py\n", "")  # draft allows empty primary_files
    p = _write(tmp_path, "FEAT-010.md", content)
    errors = validate_story_file(p)
    assert not any("pointer-only" in e for e in errors), (
        f"Expected no pointer-only error for draft story, got: {errors}"
    )


def test_pointer_only_exempt_for_backlog_status(tmp_path):
    """code/backlog story with pointer-only Ensures should not produce a pointer-only error."""
    content = _code_story_with_ensures(
        "See docs/phases/phase-83.md",
        story_class="code",
        status="backlog",
    ).replace("  - src/main.py\n", "")  # backlog allows empty primary_files
    p = _write(tmp_path, "FEAT-010.md", content)
    errors = validate_story_file(p)
    assert not any("pointer-only" in e for e in errors), (
        f"Expected no pointer-only error for backlog story, got: {errors}"
    )


def _code_story_missing_acceptance_section(story_class: str = "code", status: str = "planned") -> str:
    """Return a story that has ## Requires but NO Ensures/Acceptance heading."""
    return textwrap.dedent(f"""\
        ---
        id: FEAT-011
        rail: FEAT
        title: Missing acceptance section
        status: {status}
        phase: "083"
        story_class: {story_class}
        primary_files:
          - src/main.py
        ---

        ## Requires

        Prior story complete.

        ## Instructions

        Do the thing.
    """)


def test_code_story_missing_acceptance_surface_is_invalid(tmp_path):
    """code/planned story with ## Requires but no Ensures/Acceptance heading is invalid."""
    content = _code_story_missing_acceptance_section(story_class="code", status="planned")
    p = _write(tmp_path, "FEAT-011.md", content)
    errors = validate_story_file(p)
    assert any("body section" in e for e in errors), (
        f"Expected body section error for code story missing acceptance, got: {errors}"
    )


def test_methodology_story_missing_acceptance_surface_is_invalid(tmp_path):
    """methodology/planned story with no Ensures/Acceptance heading is invalid."""
    content = _code_story_missing_acceptance_section(story_class="methodology", status="planned")
    p = _write(tmp_path, "FEAT-011.md", content)
    errors = validate_story_file(p)
    assert any("body section" in e for e in errors), (
        f"Expected body section error for methodology story missing acceptance, got: {errors}"
    )


def test_missing_acceptance_surface_exempt_for_draft(tmp_path):
    """draft story with no Ensures/Acceptance heading should not produce a body section error."""
    content = _code_story_missing_acceptance_section(
        story_class="code", status="draft"
    ).replace("  - src/main.py\n", "")  # draft allows empty primary_files
    p = _write(tmp_path, "FEAT-011.md", content)
    errors = validate_story_file(p)
    assert not any("body section" in e for e in errors), (
        f"Expected no body section error for draft story, got: {errors}"
    )


# ---------------------------------------------------------------------------
# test_gate field
# ---------------------------------------------------------------------------

_VALID_STORY_WITH_TEST_GATE = """\
    ---
    id: FEAT-001
    rail: FEAT
    title: Test gate story
    status: planned
    phase: "001"
    test_gate: {test_gate}
    primary_files:
      - src/main.py
    ---

    ## Acceptance criterion

    It works.
"""


class TestTestGateField:
    """test_gate frontmatter field validation."""

    def test_test_gate_absent_is_valid(self, tmp_path):
        """A story with no test_gate field is valid."""
        p = _write(tmp_path, "FEAT-001.md", VALID_STORY)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_test_gate_story_is_valid(self, tmp_path):
        """test_gate: story is a valid value."""
        content = _VALID_STORY_WITH_TEST_GATE.format(test_gate="story")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors for test_gate: story, got: {errors}"

    def test_test_gate_phase_checkpoint_is_valid(self, tmp_path):
        """test_gate: phase_checkpoint is a valid value."""
        content = _VALID_STORY_WITH_TEST_GATE.format(test_gate="phase_checkpoint")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors for test_gate: phase_checkpoint, got: {errors}"

    def test_test_gate_none_is_valid(self, tmp_path):
        """test_gate: none is a valid value."""
        content = _VALID_STORY_WITH_TEST_GATE.format(test_gate="none")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors for test_gate: none, got: {errors}"

    def test_test_gate_invalid_value_is_error(self, tmp_path):
        """test_gate: always is not a valid value — expect an Invalid test_gate error."""
        content = _VALID_STORY_WITH_TEST_GATE.format(test_gate="always")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert any("Invalid test_gate" in e for e in errors), (
            f"Expected 'Invalid test_gate' error, got: {errors}"
        )


# ---------------------------------------------------------------------------
# model: / reviewer_model: fields (INFRA-318)
# ---------------------------------------------------------------------------

_VALID_STORY_WITH_MODEL_FIELDS = """\
    ---
    id: FEAT-001
    rail: FEAT
    title: Model field story
    status: planned
    phase: "001"
    {model_line}
    {reviewer_model_line}
    primary_files:
      - src/main.py
    ---

    ## Acceptance criterion

    It works.
"""


def _model_fields_story(model: str = "", reviewer_model: str = "") -> str:
    model_line = f"model: {model}" if model else ""
    reviewer_model_line = f"reviewer_model: {reviewer_model}" if reviewer_model else ""
    return _VALID_STORY_WITH_MODEL_FIELDS.format(
        model_line=model_line, reviewer_model_line=reviewer_model_line
    )


class TestModelFields:
    """model: / reviewer_model: frontmatter field validation (INFRA-318)."""

    def test_model_absent_is_valid(self, tmp_path):
        """A story with neither field validates exactly as today (Ensures 1)."""
        p = _write(tmp_path, "FEAT-001.md", VALID_STORY)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors, got: {errors}"

    @pytest.mark.parametrize("tier", sorted(VALID_MODEL_TIERS))
    def test_model_valid_tier_is_valid(self, tmp_path, tier):
        content = _model_fields_story(model=tier)
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors for model: {tier}, got: {errors}"

    @pytest.mark.parametrize("tier", sorted(VALID_MODEL_TIERS))
    def test_reviewer_model_valid_tier_is_valid(self, tmp_path, tier):
        content = _model_fields_story(reviewer_model=tier)
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], (
            f"Expected no errors for reviewer_model: {tier}, got: {errors}"
        )

    def test_model_invalid_value_is_error(self, tmp_path):
        content = _model_fields_story(model="always")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert any("Invalid model" in e for e in errors), (
            f"Expected 'Invalid model' error, got: {errors}"
        )

    def test_reviewer_model_invalid_value_is_error(self, tmp_path):
        content = _model_fields_story(reviewer_model="always")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert any("Invalid reviewer_model" in e for e in errors), (
            f"Expected 'Invalid reviewer_model' error, got: {errors}"
        )

    def test_model_rejects_free_text(self, tmp_path):
        """Free-text model names must never validate (Requires 1: shared
        vocabulary constant, not free-text)."""
        content = _model_fields_story(model="claude-4-opus-20260101")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert any("Invalid model" in e for e in errors)

    def test_model_rejects_fable(self, tmp_path):
        """fable is the loop-breaker's escalation tier only — never a
        spec-time declarable choice."""
        content = _model_fields_story(model="fable")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert any("Invalid model" in e for e in errors)

    def test_model_and_reviewer_model_both_declared_is_valid(self, tmp_path):
        content = _model_fields_story(model="opus", reviewer_model="sonnet")
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# _parse_frontmatter — inline comment stripping on block-sequence list items
# (INFRA-211)
# ---------------------------------------------------------------------------

class TestParseFrontmatterListItemComments:
    """_parse_frontmatter() list-item inline-comment handling."""

    def _frontmatter(self, touches_block: str) -> str:
        return textwrap.dedent(
            f"""\
            ---
            id: FEAT-001
            rail: FEAT
            title: My first story
            status: planned
            phase: "001"
            touches:
            {touches_block}
            ---

            body
            """
        )

    def test_plain_list_item_unaffected(self):
        """A plain list item with no '#' parses identically to before."""
        text = self._frontmatter("  - src/main.py")
        result = _parse_frontmatter(text)
        assert result["touches"] == ["src/main.py"]

    def test_inline_comment_is_stripped(self):
        """A '#' preceded by whitespace starts a comment and is stripped."""
        text = self._frontmatter(
            "  - hooks/post_tool_use.py  # protected file — reason: needed"
        )
        result = _parse_frontmatter(text)
        assert result["touches"] == ["hooks/post_tool_use.py"]

    def test_quoted_list_item_with_literal_hash_is_exempt(self):
        """A '#' inside a quoted list item is literal data, not a comment."""
        text = self._frontmatter('  - "src/main.py # not-a-comment"')
        result = _parse_frontmatter(text)
        assert result["touches"] == ["src/main.py # not-a-comment"]

    def test_hash_glued_to_content_is_not_a_comment(self):
        """A '#' with no preceding whitespace is not treated as a comment start."""
        text = self._frontmatter("  - docs/notes.md#anchor-section")
        result = _parse_frontmatter(text)
        assert result["touches"] == ["docs/notes.md#anchor-section"]

    def test_no_change_when_no_hash_present(self):
        """Regression guard: list items without '#' are unaffected by the fix."""
        text = self._frontmatter("  - skills/pairmode/scripts/schema_validator.py")
        result = _parse_frontmatter(text)
        assert result["touches"] == ["skills/pairmode/scripts/schema_validator.py"]


# ---------------------------------------------------------------------------
# _parse_frontmatter — inline comment stripping on scalar values (CER-092 /
# INFRA-262). Extends the INFRA-211 list-item rule one line up to scalars.
# ---------------------------------------------------------------------------

class TestParseFrontmatterScalarComments:
    """_parse_frontmatter() scalar inline-comment handling."""

    def _fm(self, body: str) -> str:
        return f"---\n{body}\n---\n\nbody\n"

    def test_scalar_inline_comment_is_stripped(self):
        """A '#' preceded by whitespace starts a comment on a scalar value."""
        text = self._fm("id: FEAT-001  # some note")
        result = _parse_frontmatter(text)
        assert result["id"] == "FEAT-001"

    def test_scalar_comment_only_value_is_block_sequence_start(self):
        """Ensures 5: a scalar whose value is only a comment reduces to '' and
        starts a block sequence (touches == [])."""
        text = "---\ntouches:  # note\n---\n"
        result = _parse_frontmatter(text)
        assert result["touches"] == []

    def test_quoted_scalar_with_literal_hash_is_exempt(self):
        """Ensures 6: a wholly-quoted scalar containing a whitespace-preceded
        '#' is returned verbatim (quotes removed), not truncated."""
        text = self._fm('title: "Story contract sections — ## Requires / ## Ensures"')
        result = _parse_frontmatter(text)
        assert result["title"] == "Story contract sections — ## Requires / ## Ensures"

    def test_real_world_infra_074_title_not_truncated(self):
        """Ensures 6: parsing the real INFRA-074 story file yields the full,
        untruncated title."""
        path = Path(__file__).parent.parent.parent / "docs" / "stories" / "INFRA" / "INFRA-074.md"
        text = path.read_text(encoding="utf-8")
        result = _parse_frontmatter(text)
        assert result["title"] == "Story contract sections — ## Requires / ## Ensures"

    def test_hash_glued_to_scalar_content_is_not_a_comment(self):
        """A '#' with no preceding whitespace in a scalar value is literal data."""
        text = self._fm("id: ABC#1")
        result = _parse_frontmatter(text)
        assert result["id"] == "ABC#1"

    def test_no_change_to_scalar_without_hash(self):
        """Regression guard: scalar values without '#' are unaffected."""
        text = self._fm("id: FEAT-001")
        result = _parse_frontmatter(text)
        assert result["id"] == "FEAT-001"


# ---------------------------------------------------------------------------
# Flow-sequence frontmatter (INFRA-296 / CER-115)
# ---------------------------------------------------------------------------


def _flow_fm(line: str) -> str:
    """Wrap a single frontmatter *line* in a minimal frontmatter block."""
    return f"---\nid: FLOW-001\n{line}\n---\n\nbody\n"


def test_frontmatter_error_is_a_value_error():
    """A2: FrontmatterError subclasses ValueError so existing broad handlers
    (which already catch ValueError/Exception) stay loud."""
    assert issubclass(FrontmatterError, ValueError)


def test_flow_sequence_two_elements():
    """A3: `primary_files: [a.html, b.html]` parses to a two-element list."""
    result = _parse_frontmatter(_flow_fm("primary_files: [a.html, b.html]"))
    assert result["primary_files"] == ["a.html", "b.html"]


def test_flow_sequence_single_element():
    """A3: a one-element flow sequence parses to a one-element list."""
    result = _parse_frontmatter(_flow_fm("primary_files: [a.html]"))
    assert result["primary_files"] == ["a.html"]


def test_flow_sequence_quoted_and_padded_elements():
    """A3: surrounding whitespace and one matching quote pair are stripped."""
    result = _parse_frontmatter(_flow_fm("""touches: [ "a.html" , 'b/c.html' ]"""))
    assert result["touches"] == ["a.html", "b/c.html"]


def test_flow_sequence_with_trailing_inline_comment():
    """A3: the shared inline-comment rule runs before flow parsing."""
    result = _parse_frontmatter(_flow_fm("touches: [a.html, b.html]  # note"))
    assert result["touches"] == ["a.html", "b.html"]


def test_flow_sequence_trailing_comma_drops_empty_element():
    """A3: `[a.html, ]` yields one element — empty elements are dropped."""
    result = _parse_frontmatter(_flow_fm("touches: [a.html, ]"))
    assert result["touches"] == ["a.html"]


def test_flow_sequence_doubled_comma_drops_empty_element():
    """A3: `[a.html,, b.html]` yields two elements."""
    result = _parse_frontmatter(_flow_fm("touches: [a.html,, b.html]"))
    assert result["touches"] == ["a.html", "b.html"]


def test_cer_092_explicit_empty_flow_sequence_still_starts_block_sequence():
    """A4 (CER-092): `touches: []` still reaches the empty-list branch, not the
    new flow-sequence parser."""
    result = _parse_frontmatter(_flow_fm("touches: []"))
    assert result["touches"] == []


def test_cer_092_bare_key_still_starts_block_sequence():
    """A4 (CER-092): a bare `touches:` still parses to []."""
    result = _parse_frontmatter(_flow_fm("touches:"))
    assert result["touches"] == []


def test_cer_092_comment_only_value_still_starts_block_sequence():
    """A4 (CER-092): `touches:  # note` still reduces to '' and parses to []."""
    result = _parse_frontmatter(_flow_fm("touches:  # note"))
    assert result["touches"] == []


def test_flow_sequence_nested_is_refused():
    """A5/A6: a nested flow sequence raises rather than being half-parsed."""
    with pytest.raises(FrontmatterError) as exc:
        _parse_frontmatter(_flow_fm("touches: [a, [b]]"))
    assert "touches" in str(exc.value)
    assert "[a, [b]]" in str(exc.value)


def test_flow_sequence_unbalanced_open_is_refused():
    """A6: an unterminated flow sequence raises, naming key and raw value."""
    with pytest.raises(FrontmatterError) as exc:
        _parse_frontmatter(_flow_fm("primary_files: [a, b"))
    assert "primary_files" in str(exc.value)
    assert "[a, b" in str(exc.value)


def test_flow_sequence_trailing_junk_is_refused():
    """A6: content after the closing ']' raises, naming key and raw value."""
    with pytest.raises(FrontmatterError) as exc:
        _parse_frontmatter(_flow_fm("touches: [a, b]]"))
    assert "touches" in str(exc.value)
    assert "[a, b]]" in str(exc.value)


def test_flow_parser_ignores_value_not_opening_with_bracket():
    """A7: a ']'-containing title is unchanged — the guard is a startswith."""
    result = _parse_frontmatter(_flow_fm("title: Fix the [thing], loudly"))
    assert result["title"] == "Fix the [thing], loudly"


def test_flow_parser_ignores_quoted_scalar_with_comma():
    """A7: a quoted scalar containing a comma is unchanged."""
    result = _parse_frontmatter(_flow_fm('title: "a, b"'))
    assert result["title"] == "a, b"


def test_flow_parser_ignores_quoted_numeric_scalar():
    """A7: a quoted numeric-looking value is unchanged."""
    result = _parse_frontmatter(_flow_fm('phase: "113"'))
    assert result["phase"] == "113"


def test_parse_flow_sequence_returns_none_for_non_flow_value():
    """A1: the helper returns None (not [], not a raise) for a plain scalar."""
    assert _parse_flow_sequence("just a scalar") is None


# ---------------------------------------------------------------------------
# narrative_roles: field (INFRA-355)
# ---------------------------------------------------------------------------

_VALID_STORY_WITH_NARRATIVE_ROLES = """\
    ---
    id: FEAT-001
    rail: FEAT
    title: Narrative roles story
    status: planned
    phase: "001"
    primary_files:
      - src/main.py
    {narrative_roles_block}
    ---

    ## Acceptance criterion

    It works.
"""


def _narrative_roles_story(roles: list[str] | None = None) -> str:
    if roles is None:
        block = ""
    elif roles == []:
        block = "narrative_roles: []"
    else:
        lines = ["narrative_roles:"] + [f"  - {r}" for r in roles]
        block = "\n    ".join(lines)
    return _VALID_STORY_WITH_NARRATIVE_ROLES.format(narrative_roles_block=block)


class TestNarrativeRolesField:
    """narrative_roles: frontmatter field validation (INFRA-355)."""

    def test_ten_known_roles_defined(self):
        roles = _valid_narrative_roles()
        assert len(roles) == 10
        assert "OPERATOR" in roles
        assert "BUILDER" in roles
        assert "REVIEWER" in roles
        assert "SPEC-WRITER" in roles

    def test_absent_is_valid(self, tmp_path):
        """Absent narrative_roles: is valid — not every story is role-facing."""
        content = _narrative_roles_story(roles=None)
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_empty_list_is_valid(self, tmp_path):
        content = _narrative_roles_story(roles=[])
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_single_valid_role_is_valid(self, tmp_path):
        content = _narrative_roles_story(roles=["BUILDER"])
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_multiple_valid_roles_is_valid(self, tmp_path):
        content = _narrative_roles_story(roles=["BUILDER", "REVIEWER", "OPERATOR"])
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_unknown_role_is_error(self, tmp_path):
        content = _narrative_roles_story(roles=["NOT-A-REAL-ROLE"])
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert any("Invalid narrative_roles" in e for e in errors), (
            f"Expected 'Invalid narrative_roles' error, got: {errors}"
        )

    def test_unknown_role_among_valid_ones_is_error(self, tmp_path):
        content = _narrative_roles_story(roles=["BUILDER", "NOT-A-REAL-ROLE"])
        p = _write(tmp_path, "FEAT-001.md", content)
        errors = validate_story_file(p)
        assert any("Invalid narrative_roles" in e for e in errors)
