"""Tests for INFRA-240: procedure skills must not hardcode flex-specific
per-project literals (test command, test-directory convention, protected-file
list). These facts must live in the rendered CLAUDE.build.md Build standards
section instead, so a downstream fleet project bootstrapped onto pairmode 0.3
inherits a builder/reviewer that checks its own conventions, not flex's.
"""

from __future__ import annotations

import pathlib

import pytest


REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
BUILDER_PROCEDURE = REPO_ROOT / "skills" / "pairmode" / "skills" / "builder" / "procedure.md"
REVIEWER_PROCEDURE = REPO_ROOT / "skills" / "pairmode" / "skills" / "reviewer" / "procedure.md"

# Flex-specific literals that must never appear verbatim in a procedure skill.
# These are per-project-varying facts (INFRA-240) -- procedure skills must
# reference the rendered CLAUDE.build.md Build standards section instead.
FORBIDDEN_LITERALS = [
    "tests/pairmode/",
    "-x -q",
    "skills/seed/scripts/",
    "skills/companion/scripts/sidebar.py",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
]


@pytest.fixture(params=[BUILDER_PROCEDURE, REVIEWER_PROCEDURE], ids=["builder", "reviewer"])
def procedure_text(request) -> str:
    path: pathlib.Path = request.param
    assert path.exists(), f"expected procedure file to exist: {path}"
    return path.read_text(encoding="utf-8")


class TestNoHardcodedFlexLiterals:
    @pytest.mark.parametrize("literal", FORBIDDEN_LITERALS)
    def test_literal_absent(self, procedure_text: str, literal: str):
        assert literal not in procedure_text, (
            f"found flex-specific literal {literal!r} hardcoded in a procedure skill "
            "-- per-project facts (test command, test-directory convention, "
            "protected-file list) must be read from the project's rendered "
            "CLAUDE.build.md Build standards section instead (INFRA-240)."
        )


class TestProcedureSkillsReferenceBuildStandards:
    """Both procedure skills must point to CLAUDE.build.md's Build standards
    section as the source of the per-project facts they no longer hardcode."""

    def test_builder_references_build_standards_section(self):
        text = BUILDER_PROCEDURE.read_text(encoding="utf-8")
        assert "Build standards" in text
        assert "CLAUDE.build.md" in text

    def test_reviewer_references_build_standards_section(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert "Build standards" in text
        assert "CLAUDE.build.md" in text

    def test_reviewer_input_contract_lists_claude_build_md(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        contract_start = text.index("## Input contract")
        contract_end = text.index("\n---\n", contract_start)
        contract_section = text[contract_start:contract_end]
        assert "`CLAUDE.build.md`" in contract_section


SECURITY_AUDITOR_PROCEDURE = (
    REPO_ROOT / "skills" / "pairmode" / "skills" / "security-auditor" / "procedure.md"
)

# The four data-flow sub-check labels (INFRA-290). Both cold-eyes procedures
# must use this exact vocabulary so they cannot drift into two different
# names for the same defect class.
DATA_FLOW_LABELS = [
    "written-never-read",
    "required-never-written",
    "duplicate state",
    "half-implementation",
]


class TestDataFlowChecks:
    """INFRA-290: the four data-flow checks (derived from CER-101..104) must
    exist in both cold-eyes procedure skills, with the same four labels, and
    each input contract must carry its narrow search-authorisation entry."""

    @pytest.mark.parametrize("label", DATA_FLOW_LABELS)
    def test_label_in_reviewer_procedure(self, label: str):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert label in text, f"reviewer procedure missing data-flow label {label!r}"

    @pytest.mark.parametrize("label", DATA_FLOW_LABELS)
    def test_label_in_security_auditor_procedure(self, label: str):
        text = SECURITY_AUDITOR_PROCEDURE.read_text(encoding="utf-8")
        assert label in text, (
            f"security-auditor procedure missing data-flow label {label!r}"
        )

    def test_reviewer_has_item_13(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert "### 13. DATA FLOW" in text

    def test_security_auditor_has_check_7(self):
        text = SECURITY_AUDITOR_PROCEDURE.read_text(encoding="utf-8")
        assert "### 7. DATA-FLOW INTEGRITY" in text

    def test_reviewer_input_contract_gained_entry_9(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        contract_start = text.index("## Input contract")
        contract_end = text.index("\n---\n", contract_start)
        contract_section = text[contract_start:contract_end]
        assert "9. Targeted repository searches" in contract_section
        # The widening is bounded: loop runtime state stays off-limits.
        assert "state.json" in contract_section
        assert "effort database" in contract_section

    def test_security_auditor_input_contract_gained_entry_4(self):
        text = SECURITY_AUDITOR_PROCEDURE.read_text(encoding="utf-8")
        contract_start = text.index("## Input contract")
        contract_end = text.index("\n---\n", contract_start)
        contract_section = text[contract_start:contract_end]
        assert "4. Targeted repository searches" in contract_section
        assert "state.json" in contract_section
        assert "effort database" in contract_section

    def test_reviewer_item_13_cites_forcing_function(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        item_start = text.index("### 13. DATA FLOW")
        item_end = text.index("## Review output format", item_start)
        item = text[item_start:item_end]
        assert "CER-101" in item
        assert "CER-104" in item

    def test_reviewer_item_13_report_line_format(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert "DATA FLOW: <identifier> — writers: <file:line,...> — readers: <file:line,...>" in text
