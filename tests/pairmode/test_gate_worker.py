"""
test_gate_worker.py — scaffold-presence and content-shape tests for the
WORKER-002 gate worker deliverable.

Judgment gap (DP8.2):
    These tests verify the *presence and shape* of the required instructions,
    not the LLM's runtime judgment quality. Whether the worker correctly
    downgrades a spurious schema block or confirms a genuine auth block is
    validated by the procedure prompt text + manual review (DP8.2), not by
    unit tests. No live API calls are made anywhere in this module.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_FILE = REPO_ROOT / "skills" / "pairmode" / "gate_worker" / "SKILL.md"
SHELL_TEMPLATE = (
    REPO_ROOT / "skills" / "pairmode" / "templates" / "agents" / "gate-worker.md.j2"
)
CLAUDE_BUILD_MD = REPO_ROOT / "CLAUDE.build.md"

# Add scripts dir to path so we can import gate_verdict
_SCRIPTS_DIR = REPO_ROOT / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from gate_verdict import validate_verdict_map  # noqa: E402


# ---------------------------------------------------------------------------
# Scaffold presence
# ---------------------------------------------------------------------------


def test_skill_file_exists():
    """The procedure skill exists at its declared path."""
    assert SKILL_FILE.exists(), f"Missing: {SKILL_FILE}"


def test_shell_template_exists():
    """The agent shell template exists at its declared path."""
    assert SHELL_TEMPLATE.exists(), f"Missing: {SHELL_TEMPLATE}"


# ---------------------------------------------------------------------------
# Shell is thin
# ---------------------------------------------------------------------------


def test_shell_contains_no_inline_schema_introduces():
    """The shell must not contain inline schema_introduces logic."""
    text = SHELL_TEMPLATE.read_text()
    assert "schema_introduces" not in text, (
        "gate-worker.md.j2 contains 'schema_introduces' — "
        "gate detection logic must live in SKILL.md, not in the shell."
    )


def test_shell_contains_no_inline_auth_gated():
    """The shell must not contain inline auth_gated logic."""
    text = SHELL_TEMPLATE.read_text()
    assert "auth_gated" not in text, (
        "gate-worker.md.j2 contains 'auth_gated' — "
        "gate detection logic must live in SKILL.md, not in the shell."
    )


def test_shell_delegates_to_skill():
    """The shell body must reference the SKILL.md path (delegation directive)."""
    text = SHELL_TEMPLATE.read_text()
    assert "gate_worker/SKILL.md" in text or "gate_worker" in text, (
        "gate-worker.md.j2 does not delegate to the gate_worker skill."
    )


def test_shell_has_no_check_cli_invocations():
    """
    The shell must not invoke check-* CLIs directly; that is the procedure's job.
    The shell is thin — it loads the procedure and returns the verdict.
    """
    text = SHELL_TEMPLATE.read_text()
    # The shell may mention the CLIs in passing (e.g. description), but must not
    # contain `check-schema-gate` or `check-auth-gate` as inline instructions.
    for cli in ("check-schema-gate", "check-auth-gate", "check-stub"):
        assert cli not in text, (
            f"gate-worker.md.j2 contains '{cli}' inline — "
            f"CLI invocation belongs in SKILL.md, not in the shell."
        )


# ---------------------------------------------------------------------------
# Procedure content assertions
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL_FILE.read_text()


def test_procedure_names_check_stub(skill_text: str):
    """Procedure must name the check-stub CLI."""
    assert "check-stub" in skill_text, "SKILL.md does not mention 'check-stub'."


def test_procedure_names_check_schema_gate(skill_text: str):
    """Procedure must name the check-schema-gate CLI."""
    assert "check-schema-gate" in skill_text, (
        "SKILL.md does not mention 'check-schema-gate'."
    )


def test_procedure_names_check_auth_gate(skill_text: str):
    """Procedure must name the check-auth-gate CLI."""
    assert "check-auth-gate" in skill_text, (
        "SKILL.md does not mention 'check-auth-gate'."
    )


def test_procedure_names_schema_and_auth_judgment_scope(skill_text: str):
    """Procedure must declare that it judges schema and auth."""
    assert "schema" in skill_text, "SKILL.md does not mention 'schema' gate."
    assert "auth" in skill_text, "SKILL.md does not mention 'auth' gate."


def test_procedure_encodes_stub_is_mechanical(skill_text: str):
    """Procedure must state that stub is mechanical and not its concern."""
    # Look for both "stub" and "mechanical" appearing in the text
    assert "stub" in skill_text, "SKILL.md does not mention 'stub'."
    assert "mechanical" in skill_text.lower(), (
        "SKILL.md does not describe stub as mechanical."
    )


def test_procedure_encodes_scope_context_advisory(skill_text: str):
    """Procedure must state that scope/context are advisory only."""
    text_lower = skill_text.lower()
    assert "advisory" in text_lower, (
        "SKILL.md does not use the word 'advisory' for scope/context handling."
    )


def test_procedure_encodes_dp22_downgrade_direction(skill_text: str):
    """Procedure must encode DP2.2: downgrade to clean or confirm with block:<reason>."""
    assert "downgrade" in skill_text.lower() or "clean" in skill_text, (
        "SKILL.md does not encode DP2.2 downgrade direction."
    )
    assert "confirm" in skill_text.lower() or "block:" in skill_text, (
        "SKILL.md does not encode DP2.2 confirm direction."
    )


def test_procedure_encodes_no_false_negative_caveat(skill_text: str):
    """Procedure must state that false-negative detection is out of scope."""
    text_lower = skill_text.lower()
    assert "false-negative" in text_lower or "false negative" in text_lower, (
        "SKILL.md does not mention the no-false-negative caveat."
    )


def test_procedure_encodes_dp13_input_bound_constraint(skill_text: str):
    """Procedure must encode DP1.3: only reads signal inputs + single story + diff."""
    text_lower = skill_text.lower()
    # Must mention the input-bound restriction
    has_input_bound = (
        "input-bound" in text_lower
        or "dp1.3" in text_lower
        or "must not request" in text_lower
        or "must not rely on accumulated" in text_lower
        or ("only" in text_lower and "signal" in text_lower)
    )
    assert has_input_bound, (
        "SKILL.md does not encode the DP1.3 input-bound constraint "
        "(worker reads only signal inputs + single story + diff)."
    )


# ---------------------------------------------------------------------------
# Example verdict validates against gate_verdict.py
# ---------------------------------------------------------------------------


# Concrete example verdict maps embedded in the procedure
EXAMPLE_VERDICTS = [
    {"schema": "clean", "auth": "clean"},
    {
        "schema": "clean",
        "auth": "block:auth_gated story is missing the required Classification line in docs/architecture.md",
    },
    {
        "schema": "flag:schema_introduces=true but no management surface found; confirm exception applies before proceeding"
    },
    {
        "schema": "block:schema_introduces=true with no management UI story in phase and no documented exception",
        "auth": "block:auth_gated=true but docs/architecture.md has no Classification entry",
    },
]


@pytest.mark.parametrize("verdict_map", EXAMPLE_VERDICTS)
def test_example_verdict_validates(verdict_map: dict):
    """Every embedded example verdict must pass gate_verdict.validate_verdict_map."""
    violations = validate_verdict_map(verdict_map)
    assert violations == [], (
        f"Example verdict {verdict_map!r} failed validation: {violations}"
    )


# ---------------------------------------------------------------------------
# CLAUDE.build.md unchanged
# ---------------------------------------------------------------------------


def test_claude_build_md_does_not_reference_gate_worker():
    """
    The gate worker is advisory-only (wiring is HARNESS006).
    CLAUDE.build.md must not reference gate-worker or spawn-gate-worker.
    """
    if not CLAUDE_BUILD_MD.exists():
        pytest.skip("CLAUDE.build.md not present in this checkout")
    text = CLAUDE_BUILD_MD.read_text()
    assert "gate-worker" not in text, (
        "CLAUDE.build.md references 'gate-worker' — the flip is HARNESS006, not this story."
    )
    assert "spawn-gate-worker" not in text, (
        "CLAUDE.build.md references 'spawn-gate-worker' — the flip is HARNESS006."
    )
