"""
tests/pairmode/test_gate_verdict.py — round-trip and validation tests for gate_verdict.py
(WORKER-001).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Resolve the scripts directory relative to this test file so the import works
# regardless of how pytest is invoked.
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from gate_verdict import (  # noqa: E402
    JUDGED_GATES,
    VERBS,
    parse_verdict,
    validate_verdict_map,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gate_verdict_grammar.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

def test_verbs_contains_expected():
    assert VERBS == frozenset({"clean", "block", "flag"})


def test_judged_gates_contains_expected():
    assert JUDGED_GATES == frozenset({"schema", "auth"})


def test_stub_is_not_a_judged_gate():
    assert "stub" not in JUDGED_GATES


# ---------------------------------------------------------------------------
# parse_verdict tests
# ---------------------------------------------------------------------------

def test_parse_clean():
    verb, reason = parse_verdict("clean")
    assert verb == "clean"
    assert reason == ""


def test_parse_block_simple():
    verb, reason = parse_verdict("block:introduces sessions table")
    assert verb == "block"
    assert reason == "introduces sessions table"


def test_parse_flag_simple():
    verb, reason = parse_verdict("flag:no Classification in architecture.md")
    assert verb == "flag"
    assert reason == "no Classification in architecture.md"


def test_parse_reason_with_colons():
    """The split is on the first colon only; colons inside the reason survive."""
    raw = "flag:missing UI story: see phase doc section 3: step 2"
    verb, reason = parse_verdict(raw)
    assert verb == "flag"
    assert reason == "missing UI story: see phase doc section 3: step 2"


def test_parse_round_trip_clean():
    raw = "clean"
    verb, reason = parse_verdict(raw)
    reconstructed = verb if not reason else f"{verb}:{reason}"
    assert reconstructed == raw


def test_parse_round_trip_block():
    raw = "block:introduces sessions table, no mgmt UI story in phase"
    verb, reason = parse_verdict(raw)
    reconstructed = f"{verb}:{reason}"
    assert reconstructed == raw


def test_parse_round_trip_flag_with_colons():
    raw = "flag:missing UI story: see phase doc section 3: step 2"
    verb, reason = parse_verdict(raw)
    reconstructed = f"{verb}:{reason}"
    assert reconstructed == raw


def test_parse_raises_on_empty_string():
    with pytest.raises(ValueError):
        parse_verdict("")


def test_parse_raises_on_non_string():
    with pytest.raises((ValueError, AttributeError)):
        parse_verdict(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_verdict_map tests — unit level
# ---------------------------------------------------------------------------

def test_validate_all_clean():
    violations = validate_verdict_map({"auth": "clean", "schema": "clean"})
    assert violations == []


def test_validate_block_with_reason():
    violations = validate_verdict_map(
        {"schema": "block:introduces sessions table, no mgmt UI story in phase"}
    )
    assert violations == []


def test_validate_flag_with_reason():
    violations = validate_verdict_map(
        {"auth": "flag:story sets auth_gated but no Classification recorded"}
    )
    assert violations == []


def test_validate_empty_map():
    violations = validate_verdict_map({})
    assert violations == []


def test_validate_unknown_gate_key():
    violations = validate_verdict_map({"stub": "clean"})
    assert len(violations) >= 1
    assert any("unknown gate key" in v for v in violations)


def test_validate_unknown_verb():
    violations = validate_verdict_map({"schema": "warn:something"})
    assert len(violations) >= 1
    assert any("unknown verb" in v for v in violations)


def test_validate_block_empty_reason():
    violations = validate_verdict_map({"schema": "block:"})
    assert len(violations) >= 1
    assert any("requires a non-empty reason" in v for v in violations)


def test_validate_flag_empty_reason():
    violations = validate_verdict_map({"auth": "flag:"})
    assert len(violations) >= 1
    assert any("requires a non-empty reason" in v for v in violations)


def test_validate_clean_with_payload():
    violations = validate_verdict_map({"auth": "clean:should not have a payload"})
    assert len(violations) >= 1
    assert any("must carry no reason payload" in v for v in violations)


def test_validate_non_dict_input():
    violations = validate_verdict_map(["schema", "clean"])  # type: ignore[arg-type]
    assert len(violations) >= 1


# ---------------------------------------------------------------------------
# Fixture-driven round-trip tests
# ---------------------------------------------------------------------------

class TestValidFixtures:
    """Every valid fixture entry must parse, re-serialise, and survive json round-trip."""

    fixture = _load_fixture()

    @pytest.mark.parametrize(
        "entry",
        _load_fixture()["valid"],
        ids=[e["label"] for e in _load_fixture()["valid"]],
    )
    def test_valid_entry_has_no_violations(self, entry):
        violations = validate_verdict_map(entry["map"])
        assert violations == [], (
            f"Expected no violations for {entry['label']!r}, got: {violations}"
        )

    @pytest.mark.parametrize(
        "entry",
        _load_fixture()["valid"],
        ids=[e["label"] for e in _load_fixture()["valid"]],
    )
    def test_valid_entry_round_trips_json(self, entry):
        original = entry["map"]
        serialised = json.dumps(original)
        restored = json.loads(serialised)
        assert restored == original, (
            f"JSON round-trip failed for {entry['label']!r}"
        )

    @pytest.mark.parametrize(
        "entry",
        _load_fixture()["valid"],
        ids=[e["label"] for e in _load_fixture()["valid"]],
    )
    def test_valid_entry_parse_round_trips_values(self, entry):
        """Each verdict string in the map must parse and reconstruct identically."""
        for gate, verdict_str in entry["map"].items():
            verb, reason = parse_verdict(verdict_str)
            reconstructed = verb if not reason else f"{verb}:{reason}"
            assert reconstructed == verdict_str, (
                f"parse round-trip failed for gate={gate!r} "
                f"verdict={verdict_str!r} in {entry['label']!r}: "
                f"got {reconstructed!r}"
            )


class TestInvalidFixtures:
    """Every invalid fixture entry must yield a non-empty violation list."""

    @pytest.mark.parametrize(
        "entry",
        _load_fixture()["invalid"],
        ids=[e["label"] for e in _load_fixture()["invalid"]],
    )
    def test_invalid_entry_has_violations(self, entry):
        violations = validate_verdict_map(entry["map"])
        assert len(violations) >= 1, (
            f"Expected violations for {entry['label']!r}, got none"
        )

    @pytest.mark.parametrize(
        "entry",
        [e for e in _load_fixture()["invalid"] if "expected_violation_substring" in e],
        ids=[
            e["label"]
            for e in _load_fixture()["invalid"]
            if "expected_violation_substring" in e
        ],
    )
    def test_invalid_entry_violation_message(self, entry):
        violations = validate_verdict_map(entry["map"])
        substring = entry["expected_violation_substring"]
        assert any(substring in v for v in violations), (
            f"Expected violation containing {substring!r} for {entry['label']!r}, "
            f"got: {violations}"
        )

    @pytest.mark.parametrize(
        "entry",
        [e for e in _load_fixture()["invalid"] if "expected_violation_count_min" in e],
        ids=[
            e["label"]
            for e in _load_fixture()["invalid"]
            if "expected_violation_count_min" in e
        ],
    )
    def test_invalid_entry_minimum_violation_count(self, entry):
        violations = validate_verdict_map(entry["map"])
        min_count = entry["expected_violation_count_min"]
        assert len(violations) >= min_count, (
            f"Expected at least {min_count} violation(s) for {entry['label']!r}, "
            f"got {len(violations)}: {violations}"
        )
