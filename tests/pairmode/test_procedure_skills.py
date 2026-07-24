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
