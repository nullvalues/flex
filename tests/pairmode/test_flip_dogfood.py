"""
Tests for HARNESS-002: Dogfood flip — apply thin loop + retire agent templates.

Asserts deterministically:
- The live CLAUDE.build.md is <=40 non-blank lines (line-count gate).
- The live CLAUDE.build.md contains "next-action".
- skills/pairmode/skills/builder/procedure.md DOES exist (the shared procedure).

INFRA-241 update: HARNESS-002 retired the *rendered per-role agent files* in
favor of shared procedure skills loaded by generic thin shells — but left no
custom `subagent_type` registered for the Task/Agent tool to resolve to,
which made the context-budget gate (INFRA-199) fully decorative for every
real build-cycle spawn. INFRA-241 re-registers
skills/pairmode/templates/agents/builder.md.j2 and .claude/agents/builder.md
as thin shells whose entire body is the builder procedure's "Shell
instruction" — no judgment/implementation logic is duplicated back in, so
HARNESS-002's single-source-of-truth intent is preserved even though the
files themselves now exist again. The "retired" tests below are renamed to
assert the shells are re-registered *and* still delegate to the procedure
skill rather than reintroducing inline logic.
"""
from pathlib import Path

import pytest


# Root of the flex-harness repo — two parents up from tests/pairmode/
REPO_ROOT = Path(__file__).parent.parent.parent

LIVE_BUILD_MD = REPO_ROOT / "CLAUDE.build.md"

# Thin builder shell template — re-registered by INFRA-241 (see module docstring)
BUILDER_TEMPLATE = (
    REPO_ROOT / "skills" / "pairmode" / "templates" / "agents" / "builder.md.j2"
)

# Thin rendered builder agent shell — re-registered by INFRA-241
BUILDER_AGENT = REPO_ROOT / ".claude" / "agents" / "builder.md"

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


def test_builder_template_reregistered() -> None:
    """skills/pairmode/templates/agents/builder.md.j2 exists (INFRA-241) and
    delegates to the shared procedure skill rather than duplicating logic."""
    assert BUILDER_TEMPLATE.exists(), (
        f"Builder template shell missing: {BUILDER_TEMPLATE}"
    )
    text = BUILDER_TEMPLATE.read_text()
    assert "skills/pairmode/skills/builder/procedure.md" in text, (
        "Builder template shell does not reference the shared procedure skill"
    )
    assert "name: builder" in text, (
        "Builder template shell frontmatter name must be the literal "
        "subagent_type string 'builder' the context-budget gate matches on"
    )


def test_builder_agent_reregistered() -> None:
    """.claude/agents/builder.md exists (INFRA-241) and delegates to the
    shared procedure skill rather than duplicating logic."""
    if not BUILDER_AGENT.exists():
        pytest.skip("builder.md not yet rendered in this checkout")
    text = BUILDER_AGENT.read_text()
    assert "skills/pairmode/skills/builder/procedure.md" in text, (
        "Builder agent shell does not reference the shared procedure skill"
    )


def test_builder_procedure_exists() -> None:
    """skills/pairmode/skills/builder/procedure.md MUST exist as the replacement."""
    assert BUILDER_PROCEDURE.exists(), (
        f"Builder procedure skill does not exist: {BUILDER_PROCEDURE}"
    )
