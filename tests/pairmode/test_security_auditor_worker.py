"""
tests/pairmode/test_security_auditor_worker.py — security-auditor worker tests (WORKER-008).

Coverage:
- Procedure file exists at skills/pairmode/skills/security-auditor/procedure.md.
- Bounded inputs (DP1.3): procedure declares the diff, the story spec, and hooks/
  as its three bounded inputs.
- Negative assertion: no accumulated-state references (effort.db, attempt_counter,
  context_current_tokens) appear as read instructions in the procedure.
- Injected REVIEW-RESULT{verdict: "PASS"} parses correctly via worker_result.py.
- Injected REVIEW-RESULT{verdict: "FAIL", findings: ["CRITICAL: ..."]} parses.
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

from worker_result import parse_worker_result, validate_worker_result  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_PROCEDURE_PATH = (
    _REPO_ROOT
    / "skills"
    / "pairmode"
    / "skills"
    / "security-auditor"
    / "procedure.md"
)

# ---------------------------------------------------------------------------
# Procedure file existence
# ---------------------------------------------------------------------------


class TestProcedureFileExists:
    def test_procedure_file_exists(self):
        assert _PROCEDURE_PATH.exists(), (
            f"Security-auditor procedure file not found at {_PROCEDURE_PATH}"
        )

    def test_procedure_file_is_not_empty(self):
        assert _PROCEDURE_PATH.stat().st_size > 0, (
            "Security-auditor procedure file is empty"
        )

    def test_procedure_file_has_frontmatter(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert content.startswith("---"), (
            "Security-auditor procedure file must begin with YAML frontmatter (---)"
        )

    def test_procedure_file_has_name_field(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "name:" in content, (
            "Security-auditor procedure file must have a name: field in frontmatter"
        )


# ---------------------------------------------------------------------------
# Bounded input tests (DP1.3)
# ---------------------------------------------------------------------------


class TestBoundedInputs:
    """Assert the procedure references only the three declared bounded inputs."""

    def _content(self) -> str:
        return _PROCEDURE_PATH.read_text(encoding="utf-8")

    def test_procedure_declares_diff_input(self):
        """Procedure must reference the diff as a bounded input."""
        content = self._content()
        assert "diff" in content.lower(), (
            "Security-auditor procedure must declare the diff as a bounded input"
        )

    def test_procedure_declares_story_spec_input(self):
        """Procedure must reference the story spec as a bounded input."""
        content = self._content()
        assert "docs/stories" in content or "story spec" in content.lower(), (
            "Security-auditor procedure must declare the story spec as a bounded input"
        )

    def test_procedure_declares_hooks_dir_input(self):
        """Procedure must reference hooks/ as a bounded input."""
        content = self._content()
        assert "hooks/" in content or "hooks" in content.lower(), (
            "Security-auditor procedure must declare the hooks/ directory as a bounded input"
        )

    def test_procedure_states_input_bound_property(self):
        """Procedure must explicitly state the DP1.3 input-bound property."""
        content = self._content()
        assert "DP1.3" in content or "input-bound" in content, (
            "Procedure must explicitly state the DP1.3 input-bound property"
        )

    def test_procedure_prohibits_accumulated_state(self):
        """Procedure must explicitly prohibit accumulated state access."""
        content = self._content()
        lower = content.lower()
        assert "accumulated" in lower or "must not" in lower, (
            "Procedure must include an explicit prohibition on accumulated state access"
        )

    def test_procedure_does_not_reference_effort_db(self):
        """effort.db is an accumulated-state source; must not be a read instruction."""
        content = self._content()
        assert "effort.db" not in content.lower(), (
            "Security-auditor procedure must not reference effort.db — "
            "it is an accumulated-state source outside the DP1.3 bounded inputs"
        )

    def test_procedure_does_not_reference_attempt_counter(self):
        """attempt_counter is an orchestrator-managed resource; must not appear."""
        content = self._content()
        assert "attempt_counter" not in content.lower(), (
            "Security-auditor procedure must not reference attempt_counter — "
            "it is an accumulated-state source outside the DP1.3 bounded inputs"
        )

    def test_procedure_does_not_reference_context_current_tokens(self):
        """context_current_tokens is an orchestrator-owned state key; must not appear."""
        content = self._content()
        assert "context_current_tokens" not in content.lower(), (
            "Security-auditor procedure must not reference context_current_tokens — "
            "it is an orchestrator-owned state key outside the DP1.3 bounded inputs"
        )


# ---------------------------------------------------------------------------
# Security checklist coverage tests
# ---------------------------------------------------------------------------


class TestSecurityChecklistCoverage:
    """Assert the procedure covers the five required security check areas."""

    def _content(self) -> str:
        return _PROCEDURE_PATH.read_text(encoding="utf-8")

    def test_procedure_covers_hook_performance(self):
        content = self._content()
        assert "hook" in content.lower() and "performance" in content.lower() or (
            "hook" in content.lower() and "relay" in content.lower()
        ), "Procedure must cover hook performance / thin relay check"

    def test_procedure_covers_pipe_contract(self):
        content = self._content()
        assert "pipe" in content.lower(), (
            "Procedure must cover the pipe contract check"
        )

    def test_procedure_covers_spec_safety(self):
        content = self._content()
        assert "spec" in content.lower(), (
            "Procedure must cover the spec safety check"
        )

    def test_procedure_covers_credential_exposure(self):
        content = self._content()
        lower = content.lower()
        assert "credential" in lower or "key exposure" in lower or "sk-ant" in lower, (
            "Procedure must cover credential/key exposure check"
        )

    def test_procedure_covers_path_traversal(self):
        content = self._content()
        assert "path traversal" in content.lower() or "traversal" in content.lower(), (
            "Procedure must cover the path traversal check"
        )

    def test_procedure_uses_pass_fail_output_format(self):
        """Procedure must reference the PASS / FAIL — [check name] output format."""
        content = self._content()
        assert "PASS" in content and "FAIL" in content, (
            "Procedure must include PASS / FAIL output format language"
        )

    def test_procedure_uses_severity_classification(self):
        """Procedure must use CRITICAL/HIGH/MEDIUM/LOW severity scale."""
        content = self._content()
        assert "CRITICAL" in content and "HIGH" in content, (
            "Procedure must use CRITICAL/HIGH severity classification"
        )


# ---------------------------------------------------------------------------
# REVIEW-RESULT parse tests (no live API call)
# ---------------------------------------------------------------------------


class TestReviewResultParsing:
    """Injected REVIEW-RESULT objects parse correctly via worker_result.py."""

    def test_parse_review_result_pass(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "Security audit passed — no CRITICAL or HIGH findings.",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == "REVIEW-RESULT"
        assert result["verdict"] == "PASS"
        assert result["findings"] == []
        assert isinstance(result["reason"], str)

    def test_parse_review_result_fail_with_critical_finding(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["CRITICAL: hooks/stop.py imports from skills/ — layer violation"],
            "reason": "Security audit FAIL — CRITICAL layer violation in hooks/stop.py.",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == "REVIEW-RESULT"
        assert result["verdict"] == "FAIL"
        assert len(result["findings"]) == 1
        assert result["findings"][0].startswith("CRITICAL:")

    def test_parse_review_result_fail_multiple_findings(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": [
                "CRITICAL: hooks/pre_tool_use.py makes API call",
                "HIGH: skills/pairmode/scripts/foo.py uses hardcoded absolute path",
            ],
            "reason": "Security audit FAIL — 1 CRITICAL and 1 HIGH finding.",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["verdict"] == "FAIL"
        assert len(result["findings"]) == 2

    def test_parse_review_result_pass_roundtrip(self):
        """PASS result serialises and re-parses to an equal object."""
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "Security audit complete — clean.",
        }
        text = json.dumps(obj)
        first = parse_worker_result(text)
        second = parse_worker_result(json.dumps(first))
        assert first == second == obj

    def test_parse_review_result_fail_roundtrip(self):
        """FAIL result serialises and re-parses to an equal object."""
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["CRITICAL: credential exposed in logs"],
            "reason": "Security audit FAIL — credential exposure.",
        }
        text = json.dumps(obj)
        first = parse_worker_result(text)
        second = parse_worker_result(json.dumps(first))
        assert first == second == obj

    def test_invalid_verdict_raises_value_error(self):
        """A REVIEW-RESULT with an invalid verdict must raise ValueError."""
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "MAYBE",
            "findings": [],
            "reason": "unclear",
        }
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(json.dumps(obj))

    def test_missing_findings_raises_value_error(self):
        """A REVIEW-RESULT without findings must raise ValueError."""
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "reason": "ok",
        }
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(json.dumps(obj))

    def test_findings_must_be_list_of_strings(self):
        """REVIEW-RESULT with findings as a non-list must raise ValueError."""
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": "CRITICAL: bad thing",
            "reason": "bad",
        }
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(json.dumps(obj))


# ---------------------------------------------------------------------------
# Spawn-action vocabulary registration
# ---------------------------------------------------------------------------


class TestSpawnActionVocabulary:
    """Assert spawn-security-auditor is in ACTIONS and _SPAWN_ACTIONS."""

    def _load_next_action(self):
        _next_action_dir = _REPO_ROOT / "skills" / "pairmode" / "scripts"
        if str(_next_action_dir) not in sys.path:
            sys.path.insert(0, str(_next_action_dir))
        import importlib
        import next_action
        importlib.reload(next_action)
        return next_action

    def test_spawn_security_auditor_in_actions(self):
        na = self._load_next_action()
        assert "spawn-security-auditor" in na.ACTIONS, (
            "spawn-security-auditor must be in ACTIONS (next_action.py)"
        )

    def test_spawn_security_auditor_in_spawn_actions(self):
        na = self._load_next_action()
        assert "spawn-security-auditor" in na._SPAWN_ACTIONS, (
            "spawn-security-auditor must be in _SPAWN_ACTIONS (next_action.py) "
            "so that model may be non-null"
        )
