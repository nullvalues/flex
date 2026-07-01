"""
Tests for HARNESS-002: Dogfood flip — apply thin loop + retire agent templates.

Asserts deterministically:
- The live CLAUDE.build.md is <=40 non-blank lines (line-count gate).
- The live CLAUDE.build.md contains "next-action".
- skills/pairmode/templates/agents/builder.md.j2 does NOT exist (retired).
- .claude/agents/builder.md does NOT exist (retired rendered file).
- skills/pairmode/skills/builder/procedure.md DOES exist (the replacement).
"""
from pathlib import Path

import pytest


# Root of the flex-harness repo — two parents up from tests/pairmode/
REPO_ROOT = Path(__file__).parent.parent.parent

LIVE_BUILD_MD = REPO_ROOT / "CLAUDE.build.md"

# Old j2 template that must be removed
RETIRED_BUILDER_TEMPLATE = (
    REPO_ROOT / "skills" / "pairmode" / "templates" / "agents" / "builder.md.j2"
)

# Old rendered agent file that must be removed
RETIRED_BUILDER_AGENT = REPO_ROOT / ".claude" / "agents" / "builder.md"

# Replacement procedure skill that must exist
BUILDER_PROCEDURE = (
    REPO_ROOT / "skills" / "pairmode" / "skills" / "builder" / "procedure.md"
)


def test_live_build_md_non_blank_line_count() -> None:
    """Live CLAUDE.build.md must be <=40 non-blank lines after the flip."""
    assert LIVE_BUILD_MD.exists(), "CLAUDE.build.md does not exist"
    text = LIVE_BUILD_MD.read_text(encoding="utf-8")
    non_blank = [line for line in text.splitlines() if line.strip()]
    assert len(non_blank) <= 40, (
        f"Live CLAUDE.build.md has {len(non_blank)} non-blank lines (limit: 40).\n"
        + "\n".join(f"  {i+1}: {l}" for i, l in enumerate(non_blank))
    )


def test_live_build_md_contains_next_action() -> None:
    """Live CLAUDE.build.md must reference next-action (the resolver CLI)."""
    assert LIVE_BUILD_MD.exists(), "CLAUDE.build.md does not exist"
    text = LIVE_BUILD_MD.read_text(encoding="utf-8")
    assert "next-action" in text, "Live CLAUDE.build.md does not contain 'next-action'"


def test_retired_builder_template_absent() -> None:
    """skills/pairmode/templates/agents/builder.md.j2 must NOT exist after the flip."""
    assert not RETIRED_BUILDER_TEMPLATE.exists(), (
        f"Retired builder template still exists: {RETIRED_BUILDER_TEMPLATE}"
    )


def test_retired_builder_agent_absent() -> None:
    """.claude/agents/builder.md must NOT exist after the flip."""
    assert not RETIRED_BUILDER_AGENT.exists(), (
        f"Retired rendered builder agent still exists: {RETIRED_BUILDER_AGENT}"
    )


def test_builder_procedure_exists() -> None:
    """skills/pairmode/skills/builder/procedure.md MUST exist as the replacement."""
    assert BUILDER_PROCEDURE.exists(), (
        f"Builder procedure skill does not exist: {BUILDER_PROCEDURE}"
    )
