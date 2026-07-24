"""
tests/pairmode/test_loop_breaker_worker.py — loop-breaker worker procedure tests (WORKER-007).

Coverage:
- The procedure file exists at skills/pairmode/skills/loop-breaker/procedure.md.
- The procedure file has YAML frontmatter (starts with ---).
- Bounded inputs are declared: error string, file:line, prior approaches tried.
- Negative assertion: no accumulated-state references (effort.db, attempt_counter,
  context_current_tokens, phase-history) appear as read instructions.
- An injected ADVICE object parses correctly via worker_result.py.
- An ADVICE with missing required fields raises ValueError.
- No live API call is made.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from worker_result import parse_worker_result  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_PROCEDURE_PATH = (
    _REPO_ROOT / "skills" / "pairmode" / "skills" / "loop-breaker" / "procedure.md"
)

# ---------------------------------------------------------------------------
# File existence tests
# ---------------------------------------------------------------------------


class TestProcedureFileExists:
    def test_procedure_file_present(self):
        assert _PROCEDURE_PATH.exists(), (
            f"Procedure file not found at: {_PROCEDURE_PATH}"
        )

    def test_procedure_file_is_not_empty(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, "Procedure file is empty"

    def test_procedure_file_has_frontmatter(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert content.startswith("---"), (
            "Procedure file must begin with a YAML frontmatter block (---)"
        )


# ---------------------------------------------------------------------------
# Bounded input / negative assertion tests (DP1.3)
# ---------------------------------------------------------------------------


class TestBoundedInputs:
    """Assert the procedure references only declared bounded inputs."""

    def _procedure_content(self) -> str:
        return _PROCEDURE_PATH.read_text(encoding="utf-8")

    def test_procedure_declares_error_string_input(self):
        """Procedure must declare the error string as a bounded input."""
        content = self._procedure_content()
        lower = content.lower()
        assert "error" in lower, (
            "Procedure must declare the error string as a bounded input"
        )

    def test_procedure_declares_file_line_input(self):
        """Procedure must declare the file:line reference as a bounded input."""
        content = self._procedure_content()
        lower = content.lower()
        assert "file" in lower and ("line" in lower or "file:line" in lower), (
            "Procedure must declare the file:line reference as a bounded input"
        )

    def test_procedure_declares_prior_attempts_input(self):
        """Procedure must declare prior approaches tried as a bounded input."""
        content = self._procedure_content()
        lower = content.lower()
        assert "tried" in lower or "prior approach" in lower or "attempt" in lower, (
            "Procedure must declare the prior approaches tried as a bounded input"
        )

    def test_procedure_states_input_bound_property(self):
        """Procedure must explicitly state the DP1.3 input-bound property."""
        content = self._procedure_content()
        assert "DP1.3" in content or "input-bound" in content, (
            "Procedure must explicitly state the DP1.3 input-bound property"
        )

    def test_procedure_does_not_reference_effort_db(self):
        """effort.db is an accumulated-state source; must not appear as read instruction."""
        content = self._procedure_content()
        lower = content.lower()
        assert "effort.db" not in lower, (
            "Procedure must not reference effort.db — it is an accumulated-state source "
            "outside the DP1.3 bounded inputs"
        )

    def test_procedure_does_not_reference_attempt_counter(self):
        """attempt_counter is an accumulated-state source; must not appear."""
        content = self._procedure_content()
        lower = content.lower()
        assert "attempt_counter" not in lower, (
            "Procedure must not reference attempt_counter — it is an accumulated-state "
            "source outside the DP1.3 bounded inputs"
        )

    def test_procedure_does_not_reference_context_tokens(self):
        """context_current_tokens is orchestrator-owned state; must not appear."""
        content = self._procedure_content()
        lower = content.lower()
        assert "context_current_tokens" not in lower, (
            "Procedure must not reference context_current_tokens — it is an "
            "orchestrator-owned state key outside the DP1.3 bounded inputs"
        )

    def test_procedure_prohibits_prior_transcripts(self):
        """Procedure must prohibit relying on accumulated state beyond the scalar."""
        content = self._procedure_content()
        lower = content.lower()
        assert "must not" in lower or "do not" in lower, (
            "Procedure must include an explicit prohibition on accumulated state / "
            "transcripts beyond the scalar"
        )

    def test_procedure_restricts_to_single_approach(self):
        """Procedure must instruct proposing exactly one alternative approach."""
        content = self._procedure_content()
        lower = content.lower()
        assert "one" in lower and "approach" in lower, (
            "Procedure must instruct proposing exactly one alternative approach"
        )

    def test_procedure_prohibits_code_reproduction(self):
        """Procedure must prohibit reproducing the failing code."""
        content = self._procedure_content()
        lower = content.lower()
        assert "reproduce" in lower or "not implement" in lower or "do not implement" in lower, (
            "Procedure must explicitly prohibit code reproduction"
        )


# ---------------------------------------------------------------------------
# ADVICE parse tests (no live API call)
# ---------------------------------------------------------------------------


class TestAdviceParsing:
    """Injected ADVICE objects parse correctly via worker_result.py."""

    def test_parse_advice_basic(self):
        obj = {
            "type": "ADVICE",
            "approach": "Change the import in worker_result.py to use a relative path from __file__.",
            "rationale": "The root cause is a hardcoded absolute path that breaks when the repo is moved.",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == "ADVICE"
        assert isinstance(result["approach"], str)
        assert isinstance(result["rationale"], str)
        assert len(result["approach"]) > 0
        assert len(result["rationale"]) > 0

    def test_parse_advice_roundtrip(self):
        """ADVICE result serialises and re-parses to an equal object."""
        obj = {
            "type": "ADVICE",
            "approach": "Rewrite the path resolution in scope_guard.py to use Path(__file__).parent.",
            "rationale": "Both prior attempts used getcwd() which fails when the hook is called from a different working directory.",
        }
        text = json.dumps(obj)
        first = parse_worker_result(text)
        second = parse_worker_result(json.dumps(first))
        assert first == second == obj

    def test_parse_advice_missing_approach_raises(self):
        """ADVICE without 'approach' must raise ValueError."""
        obj = {
            "type": "ADVICE",
            "rationale": "The root cause is missing sys.path insertion.",
        }
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(json.dumps(obj))

    def test_parse_advice_missing_rationale_raises(self):
        """ADVICE without 'rationale' must raise ValueError."""
        obj = {
            "type": "ADVICE",
            "approach": "Add sys.path.insert before the import.",
        }
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(json.dumps(obj))

    def test_parse_advice_missing_type_raises(self):
        """A result without 'type' must raise ValueError."""
        obj = {
            "approach": "Something.",
            "rationale": "Because.",
        }
        with pytest.raises(ValueError, match="missing required field 'type'"):
            parse_worker_result(json.dumps(obj))

    def test_parse_advice_wrong_type_raises(self):
        """An object with type='UNKNOWN' must raise ValueError."""
        obj = {
            "type": "UNKNOWN",
            "approach": "Something.",
            "rationale": "Because.",
        }
        with pytest.raises(ValueError, match="unknown result type"):
            parse_worker_result(json.dumps(obj))

    def test_parse_advice_extra_fields_accepted(self):
        """Extra fields in ADVICE should not cause validation failure (forward-compatible)."""
        obj = {
            "type": "ADVICE",
            "approach": "Patch the file resolver.",
            "rationale": "Current resolver fails on symlinks.",
            "extra_field": "ignored",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == "ADVICE"
        assert result["approach"] == "Patch the file resolver."

    def test_advice_approach_and_rationale_are_strings(self):
        """Both 'approach' and 'rationale' must be strings in a valid ADVICE."""
        obj = {
            "type": "ADVICE",
            "approach": "Use Path(__file__).parent to locate the config file.",
            "rationale": "Both prior attempts assumed cwd was the repo root.",
        }
        result = parse_worker_result(json.dumps(obj))
        assert isinstance(result["approach"], str)
        assert isinstance(result["rationale"], str)
