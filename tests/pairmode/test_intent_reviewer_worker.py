"""
tests/pairmode/test_intent_reviewer_worker.py — intent-reviewer worker tests (WORKER-009).

Coverage (WORKER-009 scope only):
- Procedure file exists at the canonical path and carries the expected sections.
- Bounded inputs (DP1.3 negative assertion): the procedure does NOT reference
  unbounded context sources as positive instructions.
- Injected REVIEW-RESULT{verdict: "ALIGNED"} parses via parse_worker_result.
- Injected REVIEW-RESULT{verdict: "FAIL", findings: ["MEDIUM: ..."]} parses.
- No live API call is made (pure parsing of injected payloads).
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

_PROCEDURE_PATH = (
    _REPO_ROOT
    / "skills"
    / "pairmode"
    / "skills"
    / "intent-reviewer"
    / "procedure.md"
)

# ---------------------------------------------------------------------------
# Procedure file existence and structure
# ---------------------------------------------------------------------------


class TestProcedureFileExists:
    def test_procedure_file_exists(self):
        assert _PROCEDURE_PATH.exists(), (
            f"Intent-reviewer procedure file not found at {_PROCEDURE_PATH}"
        )

    def test_procedure_file_is_not_empty(self):
        assert _PROCEDURE_PATH.stat().st_size > 0, (
            "Intent-reviewer procedure file is empty"
        )

    def test_procedure_file_has_frontmatter(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert content.startswith("---"), (
            "Intent-reviewer procedure file must begin with YAML frontmatter (---)"
        )

    def test_procedure_file_has_name_field(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "name:" in content, (
            "Intent-reviewer procedure file must have a name: field"
        )

    def test_procedure_file_has_shell_instruction(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "Shell instruction" in content, (
            "Intent-reviewer procedure file must contain the thin-shell instruction block"
        )

    def test_procedure_file_has_input_contract(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "Input contract" in content or "DP1.3" in content, (
            "Intent-reviewer procedure file must document the DP1.3 input-bound contract"
        )

    def test_procedure_documents_aligned_verdict(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "ALIGNED" in content, (
            "Intent-reviewer procedure must document the ALIGNED verdict format"
        )

    def test_procedure_documents_review_result_return(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "REVIEW-RESULT" in content, (
            "Intent-reviewer procedure must document the REVIEW-RESULT return format"
        )


# ---------------------------------------------------------------------------
# Bounded inputs (DP1.3 negative assertion)
# ---------------------------------------------------------------------------

#: Terms that would indicate unbounded context is being requested as a data
#: *source*. These must not appear as positive instructions in the procedure.
_UNBOUNDED_TERMS = [
    "effort.db",
    "attempt_counter.json",
]


class TestBoundedInputs:
    """The procedure must not instruct the worker to read unbounded context."""

    def _read_procedure(self) -> str:
        return _PROCEDURE_PATH.read_text(encoding="utf-8")

    @pytest.mark.parametrize("term", _UNBOUNDED_TERMS)
    def test_procedure_does_not_reference_unbounded_term(self, term: str):
        content = self._read_procedure()
        assert term not in content, (
            f"Intent-reviewer procedure references unbounded input source {term!r}. "
            f"Procedure must be bounded to the declared inputs (DP1.3)."
        )

    def test_procedure_lists_bounded_inputs(self):
        content = self._read_procedure()
        assert "phase doc" in content or "docs/phases" in content, (
            "Procedure must reference the phase doc (agreements input) as a bounded input"
        )
        assert "git diff" in content or "diff" in content, (
            "Procedure must reference the git diff as a bounded input"
        )
        assert "docs/stories" in content or "story spec" in content, (
            "Procedure must reference the story specs as a bounded input"
        )


# ---------------------------------------------------------------------------
# Injected REVIEW-RESULT parsing (no live API call)
# ---------------------------------------------------------------------------


class TestIntentReviewResultParsing:
    """Inject REVIEW-RESULT JSON and verify parse_worker_result accepts it."""

    def test_parse_aligned_result(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "ALIGNED",
            "findings": [],
            "reason": "Phase built as designed.",
        }
        result = parse_worker_result(json.dumps(payload))
        assert result["verdict"] == "ALIGNED"
        assert result["type"] == "REVIEW-RESULT"

    def test_validate_aligned_result_no_violations(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "ALIGNED",
            "findings": [],
            "reason": "Phase built as designed.",
        }
        assert validate_worker_result(payload) == []

    def test_parse_aligned_result_with_advisory_findings(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "ALIGNED",
            "findings": ["architecture.md § Hook architecture: add note about X"],
            "reason": "Phase built as designed; one advisory doc edit recommended.",
        }
        result = parse_worker_result(json.dumps(payload))
        assert result["verdict"] == "ALIGNED"
        assert result["findings"] == [
            "architecture.md § Hook architecture: add note about X"
        ]

    def test_parse_fail_result_with_findings(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["MEDIUM: cross-rail file touch not declared in touches"],
            "reason": "Blocking drift detected.",
        }
        result = parse_worker_result(json.dumps(payload))
        assert result["verdict"] == "FAIL"
        assert result["findings"] == [
            "MEDIUM: cross-rail file touch not declared in touches"
        ]

    def test_invalid_verdict_still_rejected(self):
        """A non-canonical verdict (e.g. MAYBE) must still be rejected."""
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "MAYBE",
            "findings": [],
            "reason": "unclear",
        }
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(json.dumps(payload))

    def test_no_live_api_call(self):
        """Parsing is pure: no network/SDK module is imported by worker_result."""
        import worker_result  # noqa: PLC0415

        source = Path(worker_result.__file__).read_text(encoding="utf-8")
        for forbidden in ("anthropic", "requests", "httpx", "urllib.request"):
            assert forbidden not in source, (
                f"worker_result.py must not reference {forbidden!r} (no live API call)"
            )
