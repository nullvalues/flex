"""
tests/pairmode/test_worker_result.py — round-trip and validation tests for
worker_result.py (WORKER-004).

Coverage:
- Type constants and RESULT_TYPES set.
- validate_worker_result: valid objects produce no violations; invalid objects
  produce at least one violation with the expected substring.
- parse_worker_result: valid JSON round-trips (parse → serialize → re-parse ==
  original); invalid JSON / invalid objects raise ValueError.
- Fixture-driven: every valid/invalid example in worker_result_grammar.json is
  exercised.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = (
    Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from worker_result import (  # noqa: E402
    ADVICE,
    BUILD_RESULT,
    RESULT_TYPES,
    REVIEW_RESULT,
    SPEC_RESULT,
    parse_worker_result,
    validate_worker_result,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worker_result_grammar.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------


class TestConstants:
    def test_build_result_constant(self):
        assert BUILD_RESULT == "BUILD-RESULT"

    def test_review_result_constant(self):
        assert REVIEW_RESULT == "REVIEW-RESULT"

    def test_advice_constant(self):
        assert ADVICE == "ADVICE"

    def test_spec_result_constant(self):
        assert SPEC_RESULT == "SPEC-RESULT"

    def test_result_types_contains_all_four(self):
        assert RESULT_TYPES == frozenset(
            {"BUILD-RESULT", "REVIEW-RESULT", "ADVICE", "SPEC-RESULT"}
        )


# ---------------------------------------------------------------------------
# validate_worker_result — unit-level
# ---------------------------------------------------------------------------


class TestValidateWorkerResult:
    # -- valid cases --

    def test_valid_build_pass(self):
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "WORKER-004",
            "reason": "tests green",
        }
        assert validate_worker_result(obj) == []

    def test_valid_build_fail(self):
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "FAIL",
            "story_id": "WORKER-003",
            "reason": "3 test failures",
        }
        assert validate_worker_result(obj) == []

    def test_valid_review_pass_empty_findings(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "diff matches spec",
        }
        assert validate_worker_result(obj) == []

    def test_valid_review_fail_with_findings(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["missing test file"],
            "reason": "HIGH finding blocks",
        }
        assert validate_worker_result(obj) == []

    def test_valid_advice(self):
        obj = {
            "type": "ADVICE",
            "approach": "Use lazy imports",
            "rationale": "Avoids circular import",
        }
        assert validate_worker_result(obj) == []

    def test_valid_spec_result_done(self):
        obj = {
            "type": "SPEC-RESULT",
            "story_id": "RESOLVER-009",
            "status": "done",
        }
        assert validate_worker_result(obj) == []

    def test_valid_spec_result_revised(self):
        obj = {
            "type": "SPEC-RESULT",
            "story_id": "WORKER-009",
            "status": "revised",
        }
        assert validate_worker_result(obj) == []

    def test_extra_fields_are_tolerated(self):
        """Forward-compatibility: extra fields do not produce violations."""
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "WORKER-004",
            "reason": "ok",
            "future_field": "ignored",
        }
        assert validate_worker_result(obj) == []

    # -- invalid cases --

    def test_non_dict_input(self):
        violations = validate_worker_result("not a dict")  # type: ignore[arg-type]
        assert len(violations) >= 1
        assert any("dict" in v for v in violations)

    def test_missing_type_field(self):
        violations = validate_worker_result({"outcome": "PASS"})
        assert len(violations) >= 1
        assert any("'type'" in v for v in violations)

    def test_unknown_type_value(self):
        violations = validate_worker_result({"type": "UNKNOWN-TYPE"})
        assert len(violations) >= 1
        assert any("unknown result type" in v for v in violations)

    def test_build_result_missing_outcome(self):
        obj = {"type": "BUILD-RESULT", "story_id": "WORKER-004", "reason": "x"}
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("'outcome'" in v for v in violations)

    def test_build_result_bad_outcome(self):
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "UNKNOWN",
            "story_id": "WORKER-004",
            "reason": "x",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("must be one of" in v for v in violations)

    def test_review_result_missing_verdict(self):
        obj = {
            "type": "REVIEW-RESULT",
            "findings": [],
            "reason": "x",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("'verdict'" in v for v in violations)

    def test_review_result_bad_verdict(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "MAYBE",
            "findings": [],
            "reason": "x",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("must be one of" in v for v in violations)

    def test_review_result_findings_not_a_list(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": "should be list",
            "reason": "x",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("must be a list" in v for v in violations)

    def test_review_result_findings_item_not_string(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [42],
            "reason": "x",
        }
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("must be a string" in v for v in violations)

    def test_advice_missing_approach(self):
        obj = {"type": "ADVICE", "rationale": "because"}
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("'approach'" in v for v in violations)

    def test_advice_missing_rationale(self):
        obj = {"type": "ADVICE", "approach": "do this"}
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("'rationale'" in v for v in violations)

    def test_spec_result_missing_status(self):
        obj = {"type": "SPEC-RESULT", "story_id": "X-001"}
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("'status'" in v for v in violations)

    def test_spec_result_bad_status(self):
        obj = {"type": "SPEC-RESULT", "story_id": "X-001", "status": "pending"}
        violations = validate_worker_result(obj)
        assert len(violations) >= 1
        assert any("must be one of" in v for v in violations)


# ---------------------------------------------------------------------------
# parse_worker_result — round-trip and error tests
# ---------------------------------------------------------------------------


class TestParseWorkerResult:
    def _roundtrip(self, obj: dict) -> dict:
        """Serialize obj to JSON text, then parse it back."""
        text = json.dumps(obj)
        return parse_worker_result(text)

    def test_parse_build_pass_roundtrip(self):
        original = {
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "WORKER-004",
            "reason": "all tests green",
        }
        restored = self._roundtrip(original)
        assert restored == original

    def test_parse_review_fail_roundtrip(self):
        original = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["missing test", "schema version wrong"],
            "reason": "two HIGH findings",
        }
        restored = self._roundtrip(original)
        assert restored == original

    def test_parse_advice_roundtrip(self):
        original = {
            "type": "ADVICE",
            "approach": "Use a dispatch table",
            "rationale": "Cleaner extension path",
        }
        restored = self._roundtrip(original)
        assert restored == original

    def test_parse_spec_result_roundtrip(self):
        original = {
            "type": "SPEC-RESULT",
            "story_id": "RESOLVER-009",
            "status": "done",
        }
        restored = self._roundtrip(original)
        assert restored == original

    def test_parse_raises_on_invalid_json(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            parse_worker_result("{not valid json}")

    def test_parse_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            parse_worker_result("")

    def test_parse_raises_on_non_string_input(self):
        with pytest.raises(ValueError):
            parse_worker_result(None)  # type: ignore[arg-type]

    def test_parse_raises_on_valid_json_but_bad_schema(self):
        text = json.dumps({"type": "BUILD-RESULT", "outcome": "NOPE"})
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(text)

    def test_parse_raises_on_unknown_type(self):
        text = json.dumps({"type": "MYSTERY"})
        with pytest.raises(ValueError, match="validation"):
            parse_worker_result(text)

    def test_parse_roundtrip_does_not_mutate_input(self):
        """Parsing a round-tripped object must yield an equal object."""
        original = {
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "WORKER-004",
            "reason": "ok",
        }
        text = json.dumps(original)
        first_parse = parse_worker_result(text)
        # Serialize the parse result and parse again — must still be equal.
        re_serialised = json.dumps(first_parse)
        second_parse = parse_worker_result(re_serialised)
        assert first_parse == second_parse == original


# ---------------------------------------------------------------------------
# Fixture-driven tests
# ---------------------------------------------------------------------------


class TestValidFixtures:
    """Every valid fixture entry must produce no violations and round-trip cleanly."""

    fixture = _load_fixture()

    @pytest.mark.parametrize(
        "result_type,entry",
        [
            (rt, entry)
            for rt, section in _load_fixture().items()
            for entry in section["valid"]
        ],
        ids=[
            f"{rt}-{entry['label']}"
            for rt, section in _load_fixture().items()
            for entry in section["valid"]
        ],
    )
    def test_valid_entry_no_violations(self, result_type: str, entry: dict):
        violations = validate_worker_result(entry["obj"])
        assert violations == [], (
            f"[{result_type}] {entry['label']!r}: unexpected violations: {violations}"
        )

    @pytest.mark.parametrize(
        "result_type,entry",
        [
            (rt, entry)
            for rt, section in _load_fixture().items()
            for entry in section["valid"]
        ],
        ids=[
            f"{rt}-{entry['label']}"
            for rt, section in _load_fixture().items()
            for entry in section["valid"]
        ],
    )
    def test_valid_entry_json_roundtrip(self, result_type: str, entry: dict):
        original = entry["obj"]
        text = json.dumps(original)
        restored = parse_worker_result(text)
        re_text = json.dumps(restored)
        re_restored = parse_worker_result(re_text)
        assert restored == re_restored == original, (
            f"[{result_type}] {entry['label']!r}: round-trip mismatch"
        )


class TestInvalidFixtures:
    """Every invalid fixture entry must produce at least one violation."""

    @pytest.mark.parametrize(
        "result_type,entry",
        [
            (rt, entry)
            for rt, section in _load_fixture().items()
            for entry in section["invalid"]
        ],
        ids=[
            f"{rt}-{entry['label']}"
            for rt, section in _load_fixture().items()
            for entry in section["invalid"]
        ],
    )
    def test_invalid_entry_has_violations(self, result_type: str, entry: dict):
        violations = validate_worker_result(entry["obj"])
        assert len(violations) >= 1, (
            f"[{result_type}] {entry['label']!r}: expected violations, got none"
        )

    @pytest.mark.parametrize(
        "result_type,entry",
        [
            (rt, entry)
            for rt, section in _load_fixture().items()
            for entry in section["invalid"]
            if "expected_violation_substring" in entry
        ],
        ids=[
            f"{rt}-{entry['label']}"
            for rt, section in _load_fixture().items()
            for entry in section["invalid"]
            if "expected_violation_substring" in entry
        ],
    )
    def test_invalid_entry_violation_message(self, result_type: str, entry: dict):
        violations = validate_worker_result(entry["obj"])
        substring = entry["expected_violation_substring"]
        assert any(substring in v for v in violations), (
            f"[{result_type}] {entry['label']!r}: expected violation containing "
            f"{substring!r}, got: {violations}"
        )
