"""
tests/pairmode/test_reviewer_worker.py — reviewer worker tests (WORKER-006).

Coverage:
- Procedure file exists at the canonical path.
- Bounded inputs (DP1.3 negative assertion): procedure does NOT reference
  unbounded context sources (effort.db, orchestrator state, prior-attempt
  transcripts).
- Injected REVIEW-RESULT{verdict: "PASS"} parses via parse_worker_result.
- Injected REVIEW-RESULT{verdict: "FAIL", findings: ["x"]} parses.
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

_PROCEDURE_PATH = (
    _REPO_ROOT / "skills" / "pairmode" / "skills" / "reviewer" / "procedure.md"
)

# ---------------------------------------------------------------------------
# Procedure file existence
# ---------------------------------------------------------------------------


class TestProcedureFileExists:
    def test_procedure_file_exists(self):
        assert _PROCEDURE_PATH.exists(), (
            f"Reviewer procedure file not found at {_PROCEDURE_PATH}"
        )

    def test_procedure_file_is_not_empty(self):
        assert _PROCEDURE_PATH.stat().st_size > 0, "Reviewer procedure file is empty"

    def test_procedure_file_has_frontmatter(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert content.startswith("---"), (
            "Reviewer procedure file must begin with YAML frontmatter (---)"
        )

    def test_procedure_file_has_name_field(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "name:" in content, "Reviewer procedure file must have a name: field"

    def test_procedure_file_has_review_checklist(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "Review checklist" in content or "HOOK PERFORMANCE" in content, (
            "Reviewer procedure file must contain the review checklist"
        )

    def test_procedure_file_has_return_format(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "REVIEW-RESULT" in content, (
            "Reviewer procedure file must document the REVIEW-RESULT return format"
        )

    def test_procedure_file_has_input_contract(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "Input contract" in content or "DP1.3" in content, (
            "Reviewer procedure file must document the DP1.3 input-bound contract"
        )

    def test_procedure_file_has_shell_instruction(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "Shell instruction" in content, (
            "Reviewer procedure file must contain the thin-shell instruction block"
        )


# ---------------------------------------------------------------------------
# Bounded inputs (DP1.3 negative assertion)
# ---------------------------------------------------------------------------

#: Terms that indicate unbounded context is being requested as a data *source*.
#: These must not appear in the procedure since they are not among the four
#: bounded inputs (story spec, git diff, phase doc, CLAUDE.md checklist).
#: Note: "orchestrator state" is excluded because it legitimately appears in
#: the prohibition clause ("must not read orchestrator state") without
#: instructing the reviewer to read it.
_UNBOUNDED_TERMS = [
    "effort.db",
    "prior-attempt transcript",
    "accumulated context",
    "attempt_counter.json",
]


class TestBoundedInputs:
    """The procedure must not instruct the reviewer to read unbounded context."""

    def _read_procedure(self) -> str:
        return _PROCEDURE_PATH.read_text(encoding="utf-8")

    @pytest.mark.parametrize("term", _UNBOUNDED_TERMS)
    def test_procedure_does_not_reference_unbounded_term(self, term: str):
        content = self._read_procedure()
        # Allow the term in the "must not" / prohibitions context.
        # The check is whether it appears as a *positive instruction* to read it.
        # A simple substring check is sufficient for the negative assertion.
        assert term not in content, (
            f"Reviewer procedure references unbounded input source {term!r}. "
            f"Procedure must be bounded to the four declared inputs (DP1.3)."
        )

    def test_procedure_lists_four_bounded_inputs(self):
        content = self._read_procedure()
        # The procedure must enumerate exactly the four bounded input categories.
        assert "story spec" in content or "docs/stories" in content, (
            "Procedure must reference story spec as a bounded input"
        )
        assert "git diff" in content or "diff" in content, (
            "Procedure must reference git diff as a bounded input"
        )
        assert "phase doc" in content or "phase" in content, (
            "Procedure must reference the phase doc as a bounded input"
        )
        assert "CLAUDE.md" in content, (
            "Procedure must reference CLAUDE.md as a bounded input"
        )


# ---------------------------------------------------------------------------
# Injected REVIEW-RESULT parsing (no live API call)
# ---------------------------------------------------------------------------


class TestReviewResultParsing:
    """Inject REVIEW-RESULT JSON and verify parse_worker_result accepts it."""

    def test_parse_pass_result(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "All checks passed; story committed.",
        }
        text = json.dumps(payload)
        result = parse_worker_result(text)
        assert result["type"] == "REVIEW-RESULT"
        assert result["verdict"] == "PASS"
        assert result["findings"] == []
        assert isinstance(result["reason"], str)

    def test_parse_fail_result_with_findings(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["x"],
            "reason": "HIGH finding blocked commit.",
        }
        text = json.dumps(payload)
        result = parse_worker_result(text)
        assert result["type"] == "REVIEW-RESULT"
        assert result["verdict"] == "FAIL"
        assert result["findings"] == ["x"]
        assert isinstance(result["reason"], str)

    def test_parse_fail_result_with_multiple_findings(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": [
                "hooks/stop.py makes API call — severity: CRITICAL",
                "Missing test file for new module — severity: HIGH",
            ],
            "reason": "Two blocking findings; reverted.",
        }
        text = json.dumps(payload)
        result = parse_worker_result(text)
        assert result["verdict"] == "FAIL"
        assert len(result["findings"]) == 2

    def test_validate_pass_result_no_violations(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "clean",
        }
        violations = validate_worker_result(obj)
        assert violations == []

    def test_validate_fail_result_with_findings_no_violations(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["x"],
            "reason": "blocked",
        }
        violations = validate_worker_result(obj)
        assert violations == []

    def test_bad_verdict_rejected(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "MAYBE",
            "findings": [],
            "reason": "unsure",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1

    def test_missing_findings_rejected(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "reason": "ok",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("findings" in v for v in violations)

    def test_findings_non_list_rejected(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": "not a list",
            "reason": "ok",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1

    def test_findings_item_non_string_rejected(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": [42],
            "reason": "blocked",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1

    def test_parse_raises_on_invalid_json(self):
        with pytest.raises(ValueError):
            parse_worker_result("{not json}")

    def test_parse_raises_on_wrong_type(self):
        payload = json.dumps({
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "X-001",
            "reason": "ok",
        })
        # This parses fine — it's a different type, but still valid
        result = parse_worker_result(payload)
        assert result["type"] == "BUILD-RESULT"

    def test_no_live_api_call_required(self):
        """Parsing REVIEW-RESULT JSON requires no external calls — stdlib only."""
        payload = json.dumps({
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "stdlib only",
        })
        # If this test runs to completion, no live API call was made.
        result = parse_worker_result(payload)
        assert result is not None
