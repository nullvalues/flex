"""
tests/pairmode/test_checkpoint_docs_worker.py — checkpoint docs-review worker tests (WORKER-011).

Coverage (WORKER-011 scope only):
- Procedure file exists at the canonical path and carries the expected sections.
- Bounded inputs (DP1.3 negative assertion): the procedure does NOT reference
  unbounded context sources as positive instructions.
- Injected REVIEW-RESULT{verdict: "PASS"} parses via parse_worker_result.
- Injected REVIEW-RESULT{verdict: "FAIL", findings: ["Story INFRA-164 shows backlog
  in phase doc but planned on disk"]} parses.
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
    / "checkpoint-docs"
    / "procedure.md"
)

# ---------------------------------------------------------------------------
# Procedure file existence and structure
# ---------------------------------------------------------------------------


class TestProcedureFileExists:
    def test_procedure_file_exists(self):
        assert _PROCEDURE_PATH.exists(), (
            f"Checkpoint-docs procedure file not found at {_PROCEDURE_PATH}"
        )

    def test_procedure_file_is_not_empty(self):
        assert _PROCEDURE_PATH.stat().st_size > 0, (
            "Checkpoint-docs procedure file is empty"
        )

    def test_procedure_file_has_frontmatter(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert content.startswith("---"), (
            "Checkpoint-docs procedure file must begin with YAML frontmatter (---)"
        )

    def test_procedure_file_has_name_field(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "name:" in content, (
            "Checkpoint-docs procedure file must have a name: field"
        )

    def test_procedure_file_has_shell_instruction(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "Shell instruction" in content, (
            "Checkpoint-docs procedure file must contain the thin-shell instruction block"
        )

    def test_procedure_file_has_input_contract(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "Input contract" in content or "DP1.3" in content, (
            "Checkpoint-docs procedure file must document the DP1.3 input-bound contract"
        )

    def test_procedure_documents_review_result_return(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert "REVIEW-RESULT" in content, (
            "Checkpoint-docs procedure must document the REVIEW-RESULT return format"
        )

    def test_procedure_documents_pass_verdict(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert '"PASS"' in content or "PASS" in content, (
            "Checkpoint-docs procedure must document the PASS verdict"
        )

    def test_procedure_documents_fail_verdict(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        assert '"FAIL"' in content or "FAIL" in content, (
            "Checkpoint-docs procedure must document the FAIL verdict"
        )

    def test_procedure_has_checklist_items(self):
        content = _PROCEDURE_PATH.read_text(encoding="utf-8")
        # Procedure must have at least 5 checklist items (numbered list)
        import re
        numbered_items = re.findall(r"^\d+\.", content, re.MULTILINE)
        assert len(numbered_items) >= 5, (
            f"Checkpoint-docs procedure must have at least 5 checklist items; "
            f"found {len(numbered_items)}"
        )


# ---------------------------------------------------------------------------
# Bounded inputs (DP1.3 negative assertion)
# ---------------------------------------------------------------------------

#: Terms that would indicate unbounded context is being requested as a data
#: *source*. These must not appear as positive instructions in the procedure.
_UNBOUNDED_TERMS = [
    "effort.db",
    "attempt_counter.json",
    "prior-attempt transcript",
]


class TestBoundedInputs:
    """The procedure must not instruct the worker to read unbounded context."""

    def _read_procedure(self) -> str:
        return _PROCEDURE_PATH.read_text(encoding="utf-8")

    @pytest.mark.parametrize("term", _UNBOUNDED_TERMS)
    def test_procedure_does_not_reference_unbounded_term(self, term: str):
        content = self._read_procedure()
        assert term not in content, (
            f"Checkpoint-docs procedure references unbounded input source {term!r}. "
            f"Procedure must be bounded to the declared inputs (DP1.3)."
        )

    def test_procedure_lists_phase_doc_as_bounded_input(self):
        content = self._read_procedure()
        assert "phase doc" in content or "docs/phases" in content, (
            "Procedure must reference the phase doc as a bounded input"
        )

    def test_procedure_lists_architecture_md_as_bounded_input(self):
        content = self._read_procedure()
        assert "docs/architecture.md" in content or "architecture.md" in content, (
            "Procedure must reference docs/architecture.md as a bounded input"
        )

    def test_procedure_lists_cer_backlog_as_bounded_input(self):
        content = self._read_procedure()
        assert "docs/cer/backlog.md" in content or "cer/backlog" in content, (
            "Procedure must reference the CER backlog as a bounded input"
        )


# ---------------------------------------------------------------------------
# Injected REVIEW-RESULT parsing (no live API call)
# ---------------------------------------------------------------------------


class TestCheckpointDocsResultParsing:
    """Inject REVIEW-RESULT JSON and verify parse_worker_result accepts it."""

    def test_parse_pass_result(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "All documentation is current for phase HARNESS004-main.",
        }
        result = parse_worker_result(json.dumps(payload))
        assert result["verdict"] == "PASS"
        assert result["type"] == "REVIEW-RESULT"

    def test_validate_pass_result_no_violations(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "All documentation is current for phase HARNESS004-main.",
        }
        assert validate_worker_result(payload) == []

    def test_parse_fail_result_with_story_status_mismatch(self):
        """Story that shows backlog in phase doc but planned on disk."""
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": [
                "Story INFRA-164 shows backlog in phase doc but planned on disk"
            ],
            "reason": "Story status mismatch detected; documentation is not current.",
        }
        result = parse_worker_result(json.dumps(payload))
        assert result["verdict"] == "FAIL"
        assert result["type"] == "REVIEW-RESULT"
        assert result["findings"] == [
            "Story INFRA-164 shows backlog in phase doc but planned on disk"
        ]

    def test_validate_fail_result_no_violations(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": [
                "Story INFRA-164 shows backlog in phase doc but planned on disk"
            ],
            "reason": "Story status mismatch detected; documentation is not current.",
        }
        assert validate_worker_result(payload) == []

    def test_parse_fail_result_multiple_findings(self):
        payload = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": [
                "Story INFRA-164 shows backlog in phase doc but planned on disk",
                "CER Do Now contains unresolved item: CER-042",
            ],
            "reason": "Two documentation gaps found.",
        }
        result = parse_worker_result(json.dumps(payload))
        assert result["verdict"] == "FAIL"
        assert len(result["findings"]) == 2

    def test_invalid_verdict_rejected(self):
        """A non-canonical verdict must be rejected."""
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
