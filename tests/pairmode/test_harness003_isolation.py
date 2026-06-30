"""
tests/pairmode/test_harness003_isolation.py — HARNESS003 acceptance backbone
isolation suite (WORKER-010, HARNESS003-main).

LLM-judgment gap (deliberate, not silent):
    These tests verify the *deterministic scaffold* — worker result grammar
    round-trips, input-bound constraints for all five procedure skills, and
    next_action schema/vocabulary assertions — NOT the LLM's runtime judgment
    quality. Whether the builder writes good code or the reviewer correctly
    identifies a subtle CRITICAL finding is validated by the procedure prompt
    text and manual review, not by unit tests. No live API call is made
    anywhere in this module.

Suite sections (HARNESS003 isolation matrix):
    1. Grammar round-trip — worker_result_grammar.json fixture: every valid
       example for all four result types round-trips unchanged and validates;
       every invalid example yields a non-empty violation list.
    2. Input-bound guard — parametrized over all five procedure skills
       (builder, reviewer, loop-breaker, security-auditor, intent-reviewer);
       asserts absence of accumulated-state keywords and presence of the
       DP1.3 input-bound property declaration.
    3. Injected-result routing — BUILD-RESULT PASS/FAIL, REVIEW-RESULT
       PASS/FAIL, ADVICE: parse_worker_result returns the correct typed dict
       and validate_worker_result returns no violations.
    4. Schema version — next_action.SCHEMA_VERSION == 2 (WORKER-004 bump).
    5. Vocabulary completeness — spawn-reviewer, spawn-security-auditor,
       spawn-intent-reviewer are in next_action.ACTIONS and _SPAWN_ACTIONS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
_SKILLS_DIR = _REPO_ROOT / "skills" / "pairmode" / "skills"

for _d in (_SCRIPTS_DIR,):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from worker_result import (  # noqa: E402
    ADVICE,
    BUILD_RESULT,
    REVIEW_RESULT,
    parse_worker_result,
    validate_worker_result,
)
import next_action  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------

_GRAMMAR_FIXTURE = (
    Path(__file__).parent / "fixtures" / "worker_result_grammar.json"
)


def _load_grammar() -> dict:
    return json.loads(_GRAMMAR_FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Section 1 — Grammar round-trip (worker_result_grammar.json)
# ---------------------------------------------------------------------------


class TestGrammarRoundTrip:
    """Every valid fixture entry round-trips parse → serialize → parse unchanged."""

    @pytest.mark.parametrize(
        "result_type,entry",
        [
            (rt, entry)
            for rt, section in _load_grammar().items()
            for entry in section["valid"]
        ],
        ids=[
            f"valid-{rt}-{entry['label']}"
            for rt, section in _load_grammar().items()
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
            for rt, section in _load_grammar().items()
            for entry in section["valid"]
        ],
        ids=[
            f"roundtrip-{rt}-{entry['label']}"
            for rt, section in _load_grammar().items()
            for entry in section["valid"]
        ],
    )
    def test_valid_entry_json_roundtrip(self, result_type: str, entry: dict):
        original = entry["obj"]
        text = json.dumps(original)
        first = parse_worker_result(text)
        second = parse_worker_result(json.dumps(first))
        assert first == second == original, (
            f"[{result_type}] {entry['label']!r}: round-trip mismatch"
        )

    @pytest.mark.parametrize(
        "result_type,entry",
        [
            (rt, entry)
            for rt, section in _load_grammar().items()
            for entry in section["invalid"]
        ],
        ids=[
            f"invalid-{rt}-{entry['label']}"
            for rt, section in _load_grammar().items()
            for entry in section["invalid"]
        ],
    )
    def test_invalid_entry_has_violations(self, result_type: str, entry: dict):
        violations = validate_worker_result(entry["obj"])
        assert len(violations) >= 1, (
            f"[{result_type}] {entry['label']!r}: expected violations, got none"
        )


# ---------------------------------------------------------------------------
# Section 2 — Input-bound guard (parametrized over five procedure skills)
# ---------------------------------------------------------------------------

# Forbidden accumulated-state keywords that must not appear in any procedure
# as read instructions. These are keywords that would indicate the procedure
# is instructing the worker to fetch orchestrator-held state outside its
# declared bounded inputs.
#
# Customization note (story instructions): `state.json` is omitted from the
# common forbidden set because the reviewer and security-auditor procedures
# embed the CLAUDE.md review checklist (which legitimately documents how hooks
# read state.json); that mention is documentation, not an instruction to the
# worker to fetch state.json. The universal forbidden keywords below are those
# that have no legitimate documentation context in any procedure file.
_UNIVERSAL_FORBIDDEN = [
    "effort.db",
    "attempt_counter",
    "phase_history",
]

# Per-worker extra forbidden keyword checks. Empty means use only universal set.
_EXTRA_FORBIDDEN: dict[str, list[str]] = {
    "builder": [],
    "reviewer": [],
    "loop-breaker": [],
    "security-auditor": [],
    "intent-reviewer": [],
}

_WORKER_PROCEDURES = [
    ("builder", _SKILLS_DIR / "builder" / "procedure.md"),
    ("reviewer", _SKILLS_DIR / "reviewer" / "procedure.md"),
    ("loop-breaker", _SKILLS_DIR / "loop-breaker" / "procedure.md"),
    ("security-auditor", _SKILLS_DIR / "security-auditor" / "procedure.md"),
    ("intent-reviewer", _SKILLS_DIR / "intent-reviewer" / "procedure.md"),
]


class TestInputBoundGuard:
    """Per-worker input-bound guard: one parametrized test over five workers."""

    @pytest.mark.parametrize(
        "worker_name,procedure_path",
        _WORKER_PROCEDURES,
        ids=[w for w, _ in _WORKER_PROCEDURES],
    )
    def test_procedure_file_exists(self, worker_name: str, procedure_path: Path):
        assert procedure_path.exists(), (
            f"[{worker_name}] Procedure file not found at {procedure_path}"
        )
        assert procedure_path.stat().st_size > 0, (
            f"[{worker_name}] Procedure file is empty"
        )

    @pytest.mark.parametrize(
        "worker_name,procedure_path",
        _WORKER_PROCEDURES,
        ids=[w for w, _ in _WORKER_PROCEDURES],
    )
    def test_procedure_declares_input_bound_property(
        self, worker_name: str, procedure_path: Path
    ):
        """Each procedure must explicitly state the DP1.3 input-bound property."""
        content = procedure_path.read_text(encoding="utf-8")
        assert "DP1.3" in content or "input-bound" in content, (
            f"[{worker_name}] Procedure must declare the DP1.3 input-bound property"
        )

    @pytest.mark.parametrize(
        "worker_name,procedure_path,keyword",
        [
            (worker_name, procedure_path, kw)
            for worker_name, procedure_path in _WORKER_PROCEDURES
            for kw in _UNIVERSAL_FORBIDDEN + _EXTRA_FORBIDDEN.get(worker_name, [])
        ],
        ids=[
            f"{worker_name}-no-{kw.replace('.', '_')}"
            for worker_name, _ in _WORKER_PROCEDURES
            for kw in _UNIVERSAL_FORBIDDEN + _EXTRA_FORBIDDEN.get(worker_name, [])
        ],
    )
    def test_procedure_does_not_reference_forbidden_keyword(
        self, worker_name: str, procedure_path: Path, keyword: str
    ):
        """Procedure must not reference accumulated-state keywords as read instructions."""
        content = procedure_path.read_text(encoding="utf-8")
        assert keyword not in content, (
            f"[{worker_name}] Procedure must not reference '{keyword}' — "
            f"it is an accumulated-state source outside the DP1.3 bounded inputs. "
            f"File: {procedure_path}"
        )

    @pytest.mark.parametrize(
        "worker_name,procedure_path",
        _WORKER_PROCEDURES,
        ids=[w for w, _ in _WORKER_PROCEDURES],
    )
    def test_procedure_prohibits_accumulated_state(
        self, worker_name: str, procedure_path: Path
    ):
        """Each procedure must include an explicit prohibition on accumulated state."""
        content = procedure_path.read_text(encoding="utf-8")
        lower = content.lower()
        assert "accumulated" in lower or "must not" in lower, (
            f"[{worker_name}] Procedure must include an explicit prohibition "
            f"on accumulated state access"
        )

    @pytest.mark.parametrize(
        "worker_name,procedure_path",
        _WORKER_PROCEDURES,
        ids=[w for w, _ in _WORKER_PROCEDURES],
    )
    def test_procedure_does_not_reference_prior_attempt_transcript(
        self, worker_name: str, procedure_path: Path
    ):
        """Procedure must not instruct the worker to read prior-attempt transcripts.

        Prohibition clauses mention "transcript" in a "must not" context across
        multi-line sentences; this check uses a 5-line sliding window to detect
        whether every "transcript" mention is in a prohibition context.
        """
        content = procedure_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        _PROHIBITION_MARKERS = (
            "must not",
            "do not",
            "never",
            "not rely",
            "not request",
        )
        _WINDOW = 5  # lines of context on each side of the matched line

        for i, line in enumerate(lines):
            if "transcript" not in line.lower():
                continue
            # Gather surrounding context window
            lo = max(0, i - _WINDOW)
            hi = min(len(lines), i + _WINDOW + 1)
            window_text = " ".join(lines[lo:hi]).lower()
            is_prohibition = any(m in window_text for m in _PROHIBITION_MARKERS)
            assert is_prohibition, (
                f"[{worker_name}] Procedure references 'transcript' outside a "
                f"prohibition context at line {i + 1}:\n  {line.strip()}\n"
                f"File: {procedure_path}"
            )


# ---------------------------------------------------------------------------
# Section 3 — Injected-result routing
# ---------------------------------------------------------------------------


class TestInjectedResultRouting:
    """parse_worker_result returns the correct typed dict; validate returns no violations."""

    def test_build_result_pass(self):
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "WORKER-010",
            "reason": "all tests green",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == BUILD_RESULT
        assert result["outcome"] == "PASS"
        assert validate_worker_result(result) == []

    def test_build_result_fail(self):
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "FAIL",
            "story_id": "WORKER-010",
            "reason": "pytest reported 2 failures",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == BUILD_RESULT
        assert result["outcome"] == "FAIL"
        assert validate_worker_result(result) == []

    def test_review_result_pass(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "PASS",
            "findings": [],
            "reason": "diff matches all Ensures; tests green",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == REVIEW_RESULT
        assert result["verdict"] == "PASS"
        assert validate_worker_result(result) == []

    def test_review_result_fail(self):
        obj = {
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["SCHEMA_VERSION not bumped", "test file missing"],
            "reason": "two HIGH findings",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == REVIEW_RESULT
        assert result["verdict"] == "FAIL"
        assert isinstance(result["findings"], list)
        assert validate_worker_result(result) == []

    def test_advice_result(self):
        obj = {
            "type": "ADVICE",
            "approach": "Use a lazy import to break the circular dependency.",
            "rationale": "The import cycle is caused by eager top-level imports in worker_result.py.",
        }
        text = json.dumps(obj)
        result = parse_worker_result(text)
        assert result["type"] == ADVICE
        assert "approach" in result
        assert "rationale" in result
        assert validate_worker_result(result) == []

    @pytest.mark.parametrize(
        "obj",
        [
            {
                "type": "BUILD-RESULT",
                "outcome": "PASS",
                "story_id": "WORKER-010",
                "reason": "ok",
            },
            {
                "type": "BUILD-RESULT",
                "outcome": "FAIL",
                "story_id": "WORKER-010",
                "reason": "fail",
            },
            {
                "type": "REVIEW-RESULT",
                "verdict": "PASS",
                "findings": [],
                "reason": "ok",
            },
            {
                "type": "REVIEW-RESULT",
                "verdict": "FAIL",
                "findings": ["x"],
                "reason": "fail",
            },
            {
                "type": "ADVICE",
                "approach": "do X",
                "rationale": "because Y",
            },
        ],
        ids=["build-pass", "build-fail", "review-pass", "review-fail", "advice"],
    )
    def test_injected_result_roundtrip(self, obj: dict):
        """Each injected result type round-trips parse → serialize → parse unchanged."""
        text = json.dumps(obj)
        first = parse_worker_result(text)
        second = parse_worker_result(json.dumps(first))
        assert first == second == obj
        assert validate_worker_result(first) == []


# ---------------------------------------------------------------------------
# Section 4 — SCHEMA_VERSION == 2
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_schema_version_is_2(self):
        """SCHEMA_VERSION must equal 2 (WORKER-004 bump)."""
        assert next_action.SCHEMA_VERSION == 2, (
            f"Expected next_action.SCHEMA_VERSION == 2, got {next_action.SCHEMA_VERSION}"
        )


# ---------------------------------------------------------------------------
# Section 5 — New ACTIONS present in vocabulary and _SPAWN_ACTIONS
# ---------------------------------------------------------------------------


class TestNewActionsPresent:
    """spawn-reviewer, spawn-security-auditor, spawn-intent-reviewer must be wired."""

    _EXPECTED_IN_ACTIONS = [
        "spawn-reviewer",
        "spawn-security-auditor",
        "spawn-intent-reviewer",
    ]

    _EXPECTED_IN_SPAWN_ACTIONS = [
        "spawn-reviewer",
        "spawn-security-auditor",
        "spawn-intent-reviewer",
    ]

    @pytest.mark.parametrize("action", _EXPECTED_IN_ACTIONS)
    def test_action_in_ACTIONS(self, action: str):
        assert action in next_action.ACTIONS, (
            f"'{action}' missing from next_action.ACTIONS"
        )

    @pytest.mark.parametrize("action", _EXPECTED_IN_SPAWN_ACTIONS)
    def test_action_in_SPAWN_ACTIONS(self, action: str):
        assert action in next_action._SPAWN_ACTIONS, (
            f"'{action}' missing from next_action._SPAWN_ACTIONS"
        )
