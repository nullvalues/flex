"""
tests/pairmode/test_builder_worker.py — builder worker procedure tests (WORKER-005).

Coverage:
- The procedure file exists at skills/pairmode/skills/builder/procedure.md.
- The procedure content references only the four declared bounded inputs (DP1.3).
- Negative assertion: no accumulated-state references (effort.db, attempt_counter,
  context_current_tokens) appear as instructions to read.
- An injected BUILD-RESULT with outcome="PASS" parses correctly via worker_result.py.
- An injected BUILD-RESULT with outcome="FAIL" parses correctly via worker_result.py.
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
    _REPO_ROOT / "skills" / "pairmode" / "skills" / "builder" / "procedure.md"
)

# ---------------------------------------------------------------------------
# Bounded input constants (DP1.3)
# ---------------------------------------------------------------------------

# The four declared inputs the builder procedure is allowed to reference.
_ALLOWED_INPUTS = [
    "docs/stories",       # story spec
    "CLAUDE.md",          # project conventions
    "CLAUDE.build.md",    # build standards
    "phase",              # phase doc reference (generic - matches "phase doc")
]

# Accumulated-state sources that must NOT appear as read-instructions in the
# procedure. We check that these are not referenced as things the builder
# should actively fetch/read (as opposed to being mentioned as prohibitions).
# We detect the forbidden pattern by looking for the source name combined with
# an action verb suggesting the builder should read it.
_FORBIDDEN_ACCUMULATED_SOURCES = [
    "effort.db",
    "attempt_counter",
    "context_current_tokens",
    "phase-history",
    "prior-attempt transcript",
]


# ---------------------------------------------------------------------------
# File existence test
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

    def test_procedure_declares_story_spec_input(self):
        content = self._procedure_content()
        assert "docs/stories" in content, (
            "Procedure must declare the story spec (docs/stories/<RAIL>/<ID>.md) "
            "as a bounded input"
        )

    def test_procedure_declares_claude_md_input(self):
        content = self._procedure_content()
        assert "CLAUDE.md" in content, (
            "Procedure must declare CLAUDE.md as a bounded input"
        )

    def test_procedure_declares_claude_build_md_input(self):
        content = self._procedure_content()
        assert "CLAUDE.build.md" in content, (
            "Procedure must declare CLAUDE.build.md as a bounded input"
        )

    def test_procedure_declares_phase_doc_input(self):
        content = self._procedure_content()
        assert "phase" in content.lower(), (
            "Procedure must declare the phase doc as a bounded input"
        )

    def test_procedure_does_not_instruct_reading_effort_db(self):
        """effort.db is an accumulated-state source; must not be a read instruction."""
        content = self._procedure_content()
        lower = content.lower()
        # The word "effort.db" should not appear at all in the procedure.
        # It is not a bounded input and builders must not reference it.
        assert "effort.db" not in lower, (
            "Procedure must not reference effort.db — it is an accumulated-state source "
            "outside the DP1.3 bounded inputs"
        )

    def test_procedure_does_not_instruct_reading_attempt_counter(self):
        """attempt_counter.json is an accumulated-state source; must not appear."""
        content = self._procedure_content()
        lower = content.lower()
        assert "attempt_counter" not in lower, (
            "Procedure must not reference attempt_counter — it is an accumulated-state "
            "source outside the DP1.3 bounded inputs"
        )

    def test_procedure_does_not_instruct_reading_context_tokens(self):
        """context_current_tokens is an orchestrator-owned state key; must not appear."""
        content = self._procedure_content()
        lower = content.lower()
        assert "context_current_tokens" not in lower, (
            "Procedure must not reference context_current_tokens — it is an "
            "orchestrator-owned state key outside the DP1.3 bounded inputs"
        )

    def test_procedure_states_input_bound_property(self):
        """Procedure must explicitly state it is input-bound (DP1.3)."""
        content = self._procedure_content()
        # Accept either "DP1.3" or "input-bound" as sufficient signal.
        assert "DP1.3" in content or "input-bound" in content, (
            "Procedure must explicitly state the DP1.3 input-bound property"
        )

    def test_procedure_prohibits_accumulated_state(self):
        """Procedure must explicitly prohibit relying on accumulated state."""
        content = self._procedure_content()
        lower = content.lower()
        assert "accumulated" in lower or "must not" in lower, (
            "Procedure must include an explicit prohibition on accumulated state access"
        )


# ---------------------------------------------------------------------------
# BUILD-RESULT parse tests (no live API call)
# ---------------------------------------------------------------------------


class TestBuildResultParsing:
    """Injected BUILD-RESULT objects parse correctly via worker_result.py."""

    def test_parse_build_result_pass(self):
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "WORKER-005",
            "reason": "procedure.md created and tests pass",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == "BUILD-RESULT"
        assert result["outcome"] == "PASS"
        assert result["story_id"] == "WORKER-005"
        assert isinstance(result["reason"], str)

    def test_parse_build_result_fail(self):
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "FAIL",
            "story_id": "WORKER-005",
            "reason": "pytest failed with 3 errors; attempted two approaches",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == "BUILD-RESULT"
        assert result["outcome"] == "FAIL"
        assert result["story_id"] == "WORKER-005"

    def test_parse_build_result_pass_roundtrip(self):
        """PASS result serialises and re-parses to an equal object."""
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "WORKER-005",
            "reason": "story complete",
        }
        text = json.dumps(obj)
        first = parse_worker_result(text)
        second = parse_worker_result(json.dumps(first))
        assert first == second == obj

    def test_parse_build_result_fail_roundtrip(self):
        """FAIL result serialises and re-parses to an equal object."""
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "FAIL",
            "story_id": "WORKER-005",
            "reason": "BUILDER STUCK — pytest import error",
        }
        text = json.dumps(obj)
        first = parse_worker_result(text)
        second = parse_worker_result(json.dumps(first))
        assert first == second == obj

    def test_invalid_outcome_raises_value_error(self):
        """A BUILD-RESULT with an invalid outcome must raise ValueError."""
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "DONE",   # not a valid outcome
            "story_id": "WORKER-005",
            "reason": "old-style text result",
        }
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(json.dumps(obj))

    def test_missing_story_id_raises_value_error(self):
        """A BUILD-RESULT without story_id must raise ValueError."""
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "reason": "ok",
        }
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(json.dumps(obj))
