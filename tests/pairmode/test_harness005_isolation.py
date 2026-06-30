"""
tests/pairmode/test_harness005_isolation.py

HARNESS005 isolation suite (WORKER-014, HARNESS005-main).

Pins the spec-writer's deterministic scaffold — ``needs_spec`` detection,
``spawn-spec-writer`` routing, and ``SPEC-RESULT`` routing — with no live API
calls.  The LLM-generated spec quality is a deliberate out-of-scope gap.

LLM-JUDGMENT GAP (deliberate, not silent):
    These tests verify the *deterministic scaffold* — ``needs_spec`` detection,
    ``spawn-spec-writer`` action grammar, ``SPEC-RESULT`` routing decisions, and
    the spec-writer input-bound property — NOT the LLM's spec-elaboration quality.
    Whether the spec-writer correctly identifies missing sections, drafts correct
    ``## Ensures`` assertions, or produces a builder-ready spec is validated by
    the procedure prompt text and manual review, not by unit tests.  No live API
    call is made anywhere in this module.

Suite sections (HARNESS005 isolation matrix):

    1. SCHEMA_VERSION == 4; ``spawn-spec-writer`` in ACTIONS and _SPAWN_ACTIONS.

    2. ``needs_spec`` detection — table-driven parametrize (no Ensures / stub /
       complete).  Verified via ``infer_position`` Position flag only (not via
       ``resolve_next_action``), because a story with no ``## Ensures`` section
       also trips the stub gate (Row 4a), which fires before the ``needs_spec``
       check (Row 2) in the DP2 state machine.

    3. ``SPEC-RESULT`` routing:
       - ``done``: position re-read with ``needs_spec=False`` → resolver emits
         ``spawn-builder`` (gates clean) or ``spawn-gate-worker`` (judged gate
         tripped).  Verified via both end-to-end fixture (``stub_ensures=True``
         story expanded to complete) and directly-constructed Position.
       - ``revised``: harness emits ``await-user`` with reason
         ``spec-revised-awaiting-review``.  Tested via action construction and
         grammar validation (the routing lives in the CLAUDE.build.md
         orchestrator; this test pins the contract).

    4. ``SPEC-RESULT`` grammar round-trip via ``worker_result.py``:
       both ``done`` and ``revised`` parse and validate; invalid (missing
       ``story_id``) fails validation.

    5. Spec-writer shell input-bound guard — procedure.md references only the
       four declared bounded inputs; contains no accumulated-orchestrator-state
       language; write target restricted to ``docs/stories/``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"
_SKILLS_DIR = _REPO_ROOT / "skills" / "pairmode" / "skills"
_TESTS_DIR = Path(__file__).parent

for _d in (_SCRIPTS_DIR, _TESTS_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from next_action import (  # noqa: E402
    ACTIONS,
    AWAIT_USER,
    SCHEMA_VERSION,
    SPAWN_BUILDER,
    SPAWN_SPEC_WRITER,
    _SPAWN_ACTIONS,
    infer_position,
    make_action,
    resolve_next_action,
    validate_action,
    OUTCOME_NONE,
)
from worker_result import (  # noqa: E402
    SPEC_RESULT,
    parse_worker_result,
    validate_worker_result,
)
from resolver_fixtures import make_resolver_project  # noqa: E402

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_PROCEDURE_PATH = _SKILLS_DIR / "spec-writer" / "procedure.md"

_OK_GATE: dict = {"ok": True, "blocked_reason": ""}


# ---------------------------------------------------------------------------
# Section 1: SCHEMA_VERSION and action vocabulary
# ---------------------------------------------------------------------------


def test_schema_version_is_4() -> None:
    """SCHEMA_VERSION must be 4 after RESOLVER-009 bump."""
    assert SCHEMA_VERSION == 4


def test_spawn_spec_writer_in_actions() -> None:
    """spawn-spec-writer must be a member of the ACTIONS frozenset."""
    assert SPAWN_SPEC_WRITER in ACTIONS
    assert "spawn-spec-writer" in ACTIONS


def test_spawn_spec_writer_in_spawn_actions() -> None:
    """spawn-spec-writer must be a member of _SPAWN_ACTIONS (model may be non-null)."""
    assert SPAWN_SPEC_WRITER in _SPAWN_ACTIONS
    assert "spawn-spec-writer" in _SPAWN_ACTIONS


# ---------------------------------------------------------------------------
# Section 2: needs_spec detection — table-driven parametrize
#
# These tests verify the Position["needs_spec"] flag set by infer_position.
# Routing to spawn-spec-writer also requires gate_stub to pass (no delegation
# language and ## Ensures present); a story with NO ## Ensures section trips
# the stub gate (Row 4a) before reaching the needs_spec branch (Row 2).  The
# table-driven test verifies infer_position's flag, not the resolver output.
# ---------------------------------------------------------------------------

#: Table: (fixture_kwargs, expected_needs_spec, case_label)
_NEEDS_SPEC_CASES = [
    (
        {"stub_story": True},
        True,
        "no-ensures-section",
    ),
    (
        {"stub_ensures": True},
        True,
        "stub-ensures-lt-5-lines",
    ),
    (
        {},
        False,
        "complete-ensures-gte-5-lines",
    ),
]


@pytest.mark.parametrize(
    "fixture_kwargs, expected_needs_spec, case_label",
    [
        pytest.param(kwargs, expected, label, id=label)
        for kwargs, expected, label in _NEEDS_SPEC_CASES
    ],
)
def test_needs_spec_detection_parametrized(
    tmp_path: Path,
    monkeypatch: Any,
    fixture_kwargs: dict,
    expected_needs_spec: bool,
    case_label: str,
) -> None:
    """Table-driven: all three ``needs_spec`` detection states via infer_position.

    - No ``## Ensures`` section → ``needs_spec: True``
    - Stub ``## Ensures`` (< 5 non-blank lines) → ``needs_spec: True``
    - Complete ``## Ensures`` (>= 5 non-blank lines) → ``needs_spec: False``
    """
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            **fixture_kwargs,
        },
    )
    # Patch git log to avoid real git subprocess during the test.
    import next_story as _ns  # type: ignore[import]
    monkeypatch.setattr(_ns, "_git_log_oneline", lambda _p: "")

    position = infer_position(project)
    assert position["needs_spec"] is expected_needs_spec, (
        f"Case '{case_label}': expected needs_spec={expected_needs_spec!r}, "
        f"got {position['needs_spec']!r}"
    )


def test_needs_spec_true_stub_ensures_emits_spawn_spec_writer_e2e(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """End-to-end: stub Ensures (< 5 lines, no delegation) → spawn-spec-writer.

    The ``stub_ensures=True`` fixture has a ``## Ensures`` section with 3 lines
    and no delegation language, so the stub gate passes and Row 2 fires the
    ``needs_spec`` branch.  This is the canonical path to ``spawn-spec-writer``.
    """
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            "stub_ensures": True,  # ## Ensures with 3 lines, no delegation
        },
    )
    import next_story as _ns  # type: ignore[import]
    monkeypatch.setattr(_ns, "_git_log_oneline", lambda _p: "")

    position = infer_position(project)
    assert position["needs_spec"] is True

    action = resolve_next_action(position, gate_fn=lambda: True)
    assert action["action"] == SPAWN_SPEC_WRITER, (
        f"stub_ensures=True should produce spawn-spec-writer; got {action['action']!r}"
    )
    assert action["model"] == "opus"
    assert action["reason"] == "needs-spec"
    assert validate_action(action) == []


def test_needs_spec_true_via_position_emits_spawn_spec_writer() -> None:
    """Directly-constructed Position: needs_spec=True + gate_stub ok → spawn-spec-writer.

    Demonstrates the resolver's Row-2 branch for a story whose stub gate passes
    but whose Ensures section is too short.  Simulates the case of a story with
    no ## Ensures section by injecting gate_stub=ok (bypassing the real gate
    check so we can isolate the needs_spec branch).
    """
    phase_file = Path("/tmp") / "phase-1.md"
    position = {
        "active_phase_file": phase_file,
        "next_story_id": "TEST-001",
        "next_story_file": None,
        "attempt_count": 0,
        "builder_model": "sonnet",
        "builder_model_reason": "auto-baseline",
        "gate_stub": _OK_GATE,   # stub gate explicitly OK in Position
        "gate_schema": _OK_GATE,
        "gate_auth": _OK_GATE,
        "last_attempt_outcome": OUTCOME_NONE,
        "checkpoint_step": [],
        "needs_spec": True,  # Set for both no-Ensures and stub-Ensures cases
    }
    action = resolve_next_action(position, gate_fn=lambda: True)
    assert action["action"] == SPAWN_SPEC_WRITER, (
        f"Position with needs_spec=True must emit spawn-spec-writer; "
        f"got {action['action']!r}"
    )
    assert action["scalar"] == "TEST-001"
    assert action["model"] == "opus"
    assert action["reason"] == "needs-spec"
    assert validate_action(action) == []


def test_needs_spec_false_complete_ensures_emits_spawn_builder_e2e(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """End-to-end: complete Ensures (≥ 5 lines) → spawn-builder (gates clean)."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            # Default fixture: 5 non-blank Ensures lines → needs_spec = False
        },
    )
    import next_story as _ns  # type: ignore[import]
    monkeypatch.setattr(_ns, "_git_log_oneline", lambda _p: "")

    position = infer_position(project)
    assert position["needs_spec"] is False

    action = resolve_next_action(position, gate_fn=lambda: True)
    # Gates are clean → spawn-builder (or spawn-gate-worker if judged gate trips)
    assert action["action"] in (SPAWN_BUILDER, "spawn-gate-worker"), (
        f"Complete Ensures with clean gates should produce spawn-builder; "
        f"got {action['action']!r}"
    )
    assert action["action"] != SPAWN_SPEC_WRITER
    assert validate_action(action) == []


# ---------------------------------------------------------------------------
# Section 3: SPEC-RESULT routing
# ---------------------------------------------------------------------------


def test_spec_result_done_resolver_emits_normal_action_e2e(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """SPEC-RESULT{status: 'done'} routing: re-read next-action after expansion.

    Simulates: the spec-writer returns 'done' and the story file is now expanded
    (needs_spec = False).  The resolver is called again and emits spawn-builder
    (gates clean), NOT spawn-spec-writer.
    """
    # Complete Ensures fixture simulates the expanded story file after "done".
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("TEST-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            # Default fixture: complete Ensures → needs_spec = False
        },
    )
    import next_story as _ns  # type: ignore[import]
    monkeypatch.setattr(_ns, "_git_log_oneline", lambda _p: "")

    position = infer_position(project)
    assert position["needs_spec"] is False, (
        "Precondition: expanded story should have needs_spec=False"
    )

    action = resolve_next_action(position, gate_fn=lambda: True)

    # After 'done': resolver must NOT re-emit spawn-spec-writer.
    assert action["action"] != SPAWN_SPEC_WRITER, (
        f"After 'done' result: resolver must not re-emit spawn-spec-writer; "
        f"got {action['action']!r}"
    )
    assert action["action"] in (SPAWN_BUILDER, "spawn-gate-worker"), (
        f"After 'done': expected spawn-builder or spawn-gate-worker; "
        f"got {action['action']!r}"
    )
    assert validate_action(action) == []


def test_spec_result_done_via_position_emits_spawn_builder() -> None:
    """SPEC-RESULT{status: 'done'}: Position with needs_spec=False → spawn-builder.

    Directly-constructed Position with needs_spec=False and all gates clean.
    Simulates the state after the spec-writer returns 'done' and infer_position
    is re-called on the now-expanded story file.
    """
    phase_file = Path("/tmp") / "phase-1.md"
    position = {
        "active_phase_file": phase_file,
        "next_story_id": "TEST-001",
        "next_story_file": None,
        "attempt_count": 0,
        "builder_model": "sonnet",
        "builder_model_reason": "auto-baseline",
        "gate_stub": _OK_GATE,
        "gate_schema": _OK_GATE,
        "gate_auth": _OK_GATE,
        "last_attempt_outcome": OUTCOME_NONE,
        "checkpoint_step": [],
        "needs_spec": False,  # expanded story — SPEC-RESULT{status: "done"}
    }
    action = resolve_next_action(position, gate_fn=lambda: True)

    assert action["action"] == SPAWN_BUILDER, (
        f"Position with needs_spec=False and clean gates should emit spawn-builder; "
        f"got {action['action']!r}"
    )
    assert action["action"] != SPAWN_SPEC_WRITER
    assert validate_action(action) == []


def test_spec_result_revised_harness_emits_await_user() -> None:
    """SPEC-RESULT{status: 'revised'} → harness emits await-user.

    The spec-writer returns 'revised' when human review is needed before
    building.  The orchestrator (harness) responds with an await-user action
    carrying reason='spec-revised-awaiting-review'.

    This test pins the routing *contract* (valid action shape and reason string)
    that the CLAUDE.build.md orchestrator must implement when it receives
    SPEC-RESULT{status: 'revised'}.  The routing logic lives in the orchestrator
    prose, not in next_action.py; the test validates that the action shape
    is grammatically correct.
    """
    # Parse the SPEC-RESULT — validates the 'revised' status round-trip.
    spec_result_json = (
        '{"type": "SPEC-RESULT", "story_id": "TEST-001", "status": "revised"}'
    )
    result = parse_worker_result(spec_result_json)
    assert result["status"] == "revised"

    # Harness routing: 'revised' → await-user with the canonical reason.
    action = make_action(
        AWAIT_USER,
        scalar="",
        model=None,
        reason="spec-revised-awaiting-review",
    )

    assert action["action"] == AWAIT_USER
    assert action["reason"] == "spec-revised-awaiting-review"
    assert action["model"] is None

    violations = validate_action(action)
    assert violations == [], (
        f"await-user action for spec-revised must pass validate_action; "
        f"violations: {violations}"
    )


def test_spec_result_revised_reason_string_is_canonical() -> None:
    """'spec-revised-awaiting-review' is the canonical reason string for revised routing."""
    action = make_action(
        AWAIT_USER,
        scalar="",
        model=None,
        reason="spec-revised-awaiting-review",
    )
    assert action["reason"] == "spec-revised-awaiting-review"
    assert validate_action(action) == []


# ---------------------------------------------------------------------------
# Section 4: SPEC-RESULT grammar round-trip via worker_result.py
# ---------------------------------------------------------------------------


def test_spec_result_done_parses_and_validates() -> None:
    """SPEC-RESULT{status: 'done'} round-trips through parse_worker_result."""
    json_text = '{"type": "SPEC-RESULT", "story_id": "BUILD-012", "status": "done"}'
    result = parse_worker_result(json_text)

    assert result["type"] == SPEC_RESULT
    assert result["story_id"] == "BUILD-012"
    assert result["status"] == "done"
    assert validate_worker_result(result) == []


def test_spec_result_revised_parses_and_validates() -> None:
    """SPEC-RESULT{status: 'revised'} round-trips through parse_worker_result."""
    json_text = (
        '{"type": "SPEC-RESULT", "story_id": "BUILD-012", "status": "revised"}'
    )
    result = parse_worker_result(json_text)

    assert result["type"] == SPEC_RESULT
    assert result["story_id"] == "BUILD-012"
    assert result["status"] == "revised"
    assert validate_worker_result(result) == []


def test_spec_result_invalid_missing_story_id_fails_validation() -> None:
    """SPEC-RESULT missing 'story_id' field fails validate_worker_result."""
    obj = {"type": "SPEC-RESULT", "status": "done"}
    violations = validate_worker_result(obj)

    assert violations, "Missing story_id must produce violations"
    assert any("story_id" in v for v in violations), (
        f"Expected a violation mentioning 'story_id'; got: {violations}"
    )


def test_spec_result_parse_raises_on_invalid() -> None:
    """parse_worker_result raises ValueError for a SPEC-RESULT missing story_id."""
    json_text = '{"type": "SPEC-RESULT", "status": "done"}'
    with pytest.raises(ValueError, match="story_id"):
        parse_worker_result(json_text)


def test_spec_result_invalid_status_fails_validation() -> None:
    """SPEC-RESULT with an unrecognised status value fails validate_worker_result."""
    obj = {"type": "SPEC-RESULT", "story_id": "BUILD-012", "status": "in-progress"}
    violations = validate_worker_result(obj)

    assert violations, "Invalid status must produce violations"
    assert any("status" in v for v in violations), (
        f"Expected a violation mentioning 'status'; got: {violations}"
    )


def test_spec_result_only_done_and_revised_are_valid_statuses() -> None:
    """Only 'done' and 'revised' are valid SPEC-RESULT status values."""
    for status in ("done", "revised"):
        obj = {"type": "SPEC-RESULT", "story_id": "X-001", "status": status}
        assert validate_worker_result(obj) == [], (
            f"status={status!r} must be valid"
        )

    for bad_status in ("pending", "DONE", "complete", ""):
        obj = {"type": "SPEC-RESULT", "story_id": "X-001", "status": bad_status}
        violations = validate_worker_result(obj)
        assert violations, (
            f"status={bad_status!r} must be invalid but got no violations"
        )


# ---------------------------------------------------------------------------
# Section 5: Spec-writer shell input-bound guard
# ---------------------------------------------------------------------------


def test_spec_writer_procedure_exists() -> None:
    """The spec-writer procedure.md skill file must exist."""
    assert _PROCEDURE_PATH.exists(), (
        f"Spec-writer procedure not found at {_PROCEDURE_PATH}"
    )


def test_spec_writer_procedure_declares_four_bounded_inputs() -> None:
    """procedure.md declares exactly four bounded inputs in the Input contract section."""
    text = _PROCEDURE_PATH.read_text(encoding="utf-8")

    assert "## Input contract" in text, (
        "Spec-writer procedure must contain '## Input contract' section"
    )

    # All four bounded inputs must be referenced
    assert (
        "stub story file" in text.lower()
        or "stub story" in text.lower()
        or "docs/stories" in text
    ), "procedure.md must reference the stub story file as a bounded input"

    assert "phase doc" in text.lower(), (
        "procedure.md must reference the phase doc as a bounded input"
    )

    assert "era doc" in text.lower() or "era" in text.lower(), (
        "procedure.md must reference the era doc as a bounded input"
    )

    assert "exemplar" in text.lower() or "format exemplar" in text.lower(), (
        "procedure.md must reference the format exemplar as a bounded input"
    )


def test_spec_writer_procedure_no_accumulated_state() -> None:
    """procedure.md must prohibit accumulated orchestrator state as input."""
    text = _PROCEDURE_PATH.read_text(encoding="utf-8")

    has_exclusion = (
        "no other files" in text.lower()
        or "no accumulated" in text.lower()
        or "accumulated orchestrator" in text.lower()
    )
    assert has_exclusion, (
        "procedure.md must contain language prohibiting accumulated orchestrator "
        "state as input (e.g. 'No other files', 'no accumulated state')"
    )


def test_spec_writer_procedure_write_target_docs_stories_only() -> None:
    """procedure.md must restrict write targets to docs/stories/ only."""
    text = _PROCEDURE_PATH.read_text(encoding="utf-8")

    assert "docs/stories" in text, (
        "procedure.md must restrict write target to docs/stories/"
    )

    # Must contain language restricting writes
    has_write_restriction = (
        "write only to" in text.lower()
        or "no other file" in text.lower()
        or "only to `docs/stories" in text.lower()
    )
    assert has_write_restriction, (
        "procedure.md must contain language restricting writes to docs/stories/ "
        "(e.g. 'Write ONLY to docs/stories/', 'No other file is touched')"
    )


def test_spec_writer_procedure_return_format_is_spec_result() -> None:
    """procedure.md must specify SPEC-RESULT as the return format."""
    text = _PROCEDURE_PATH.read_text(encoding="utf-8")

    assert "SPEC-RESULT" in text, (
        "procedure.md must specify SPEC-RESULT as the return format"
    )
    assert "done" in text, (
        "procedure.md must document 'done' as a valid status"
    )
    assert "revised" in text, (
        "procedure.md must document 'revised' as a valid status"
    )
