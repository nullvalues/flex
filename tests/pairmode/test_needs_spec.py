"""
tests/pairmode/test_needs_spec.py

Tests for the ``needs_spec`` Position flag and ``spawn-spec-writer`` action
introduced by RESOLVER-009.

Coverage:
- ``_count_ensures_nonblank_lines`` helper: absent section, stub (< 5 lines),
  complete (>= 5 lines).
- ``infer_position`` sets ``needs_spec = True`` for stub/absent Ensures and
  ``needs_spec = False`` for a complete Ensures.
- ``resolve_next_action`` emits ``spawn-spec-writer`` when ``needs_spec = True``
  (at attempt_count 0, all gates clear, auto model).
- ``resolve_next_action`` proceeds to ``spawn-builder`` when ``needs_spec = False``.
- ``SCHEMA_VERSION == 4``.
- ``"spawn-spec-writer"`` is a member of both ``ACTIONS`` and ``_SPAWN_ACTIONS``.
- Emitted ``spawn-spec-writer`` action passes ``validate_action``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Import wiring
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).parent
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
for _d in (_TESTS_DIR, _SCRIPTS_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from next_action import (  # noqa: E402
    ACTIONS,
    SCHEMA_VERSION,
    SPAWN_BUILDER,
    SPAWN_SPEC_WRITER,
    _count_ensures_nonblank_lines,
    _SPAWN_ACTIONS,
    infer_position,
    make_action,
    resolve_next_action,
    validate_action,
    OUTCOME_NONE,
    OUTCOME_FAIL,
)

from resolver_fixtures import make_resolver_project  # noqa: E402


# ---------------------------------------------------------------------------
# Grammar constants assertions
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
# _count_ensures_nonblank_lines unit tests
# ---------------------------------------------------------------------------


def test_count_ensures_absent_returns_none() -> None:
    """No ## Ensures section → returns None."""
    text = "# My Story\n\nSee phase doc for details.\n"
    assert _count_ensures_nonblank_lines(text) is None


def test_count_ensures_empty_section_returns_zero() -> None:
    """## Ensures section with no content lines → returns 0."""
    text = "# My Story\n\n## Ensures\n\n## Instructions\n\nDo stuff.\n"
    assert _count_ensures_nonblank_lines(text) == 0


def test_count_ensures_three_lines_stub() -> None:
    """Stub ## Ensures with 3 non-blank lines."""
    text = (
        "# My Story\n\n"
        "## Ensures\n\n"
        "- Line 1.\n"
        "- Line 2.\n"
        "- Line 3.\n"
    )
    assert _count_ensures_nonblank_lines(text) == 3


def test_count_ensures_five_lines_complete() -> None:
    """Complete ## Ensures with 5 non-blank lines."""
    text = (
        "# My Story\n\n"
        "## Ensures\n\n"
        "- Line 1.\n"
        "- Line 2.\n"
        "- Line 3.\n"
        "- Line 4.\n"
        "- Line 5.\n"
    )
    assert _count_ensures_nonblank_lines(text) == 5


def test_count_ensures_blank_lines_not_counted() -> None:
    """Blank lines between items are not counted."""
    text = (
        "## Ensures\n\n"
        "- Line 1.\n"
        "\n"
        "- Line 2.\n"
        "\n"
        "- Line 3.\n"
    )
    # Only 3 non-blank lines despite blank lines between
    assert _count_ensures_nonblank_lines(text) == 3


def test_count_ensures_stops_at_next_heading() -> None:
    """Stops counting at the next ## heading."""
    text = (
        "## Ensures\n\n"
        "- A.\n"
        "- B.\n"
        "## Instructions\n\n"
        "- C.\n"
        "- D.\n"
        "- E.\n"
    )
    # Only 2 lines in Ensures (before ## Instructions)
    assert _count_ensures_nonblank_lines(text) == 2


def test_count_ensures_does_not_look_at_instructions() -> None:
    """## Instructions section content is not counted."""
    text = (
        "## Ensures\n\n"
        "- One.\n"
        "## Instructions\n\n"
        "- alpha.\n- beta.\n- gamma.\n- delta.\n- epsilon.\n"
    )
    assert _count_ensures_nonblank_lines(text) == 1


# ---------------------------------------------------------------------------
# infer_position: needs_spec flag
# ---------------------------------------------------------------------------


def _patch_git_log(monkeypatch: Any, log_output: str) -> None:
    """Replace next_story._git_log_oneline to return a fixed string."""
    import next_story as _ns  # type: ignore[import]
    monkeypatch.setattr(_ns, "_git_log_oneline", lambda _p: log_output)


def test_infer_position_needs_spec_true_no_ensures(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Story with no ## Ensures section → needs_spec = True."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("RESOLVER-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            "stub_story": True,  # no ## Ensures at all
        },
    )
    _patch_git_log(monkeypatch, "")
    position = infer_position(project)
    assert position["needs_spec"] is True


def test_infer_position_needs_spec_true_stub_ensures(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Story with ## Ensures containing < 5 non-blank lines → needs_spec = True."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("RESOLVER-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            "stub_ensures": True,  # ## Ensures with only 3 lines
        },
    )
    _patch_git_log(monkeypatch, "")
    position = infer_position(project)
    assert position["needs_spec"] is True


def test_infer_position_needs_spec_false_complete_ensures(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Story with ## Ensures containing >= 5 non-blank lines → needs_spec = False."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("RESOLVER-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            # Default fixture body has 5 non-blank Ensures lines
        },
    )
    _patch_git_log(monkeypatch, "")
    position = infer_position(project)
    assert position["needs_spec"] is False


def test_infer_position_needs_spec_false_when_no_story(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """When there is no next story (phase complete), needs_spec = False."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("RESOLVER-001", "complete", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": ["feat(story-RESOLVER-001): done"],
        },
    )
    # Use real git log (commit was seeded)
    position = infer_position(project)
    assert position["next_story_id"] is None
    assert position["needs_spec"] is False


# ---------------------------------------------------------------------------
# resolve_next_action: spawn-spec-writer emission
# ---------------------------------------------------------------------------


def test_resolve_emits_spawn_spec_writer_when_needs_spec_true(
    tmp_path: Path,
) -> None:
    """When needs_spec = True, resolver emits spawn-spec-writer."""
    phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
    phase_file.parent.mkdir(parents=True, exist_ok=True)
    phase_file.write_text("# Phase 1\n", encoding="utf-8")

    _ok_gate = {"ok": True, "blocked_reason": ""}
    position = {
        "active_phase_file": phase_file,
        "next_story_id": "RESOLVER-001",
        "next_story_file": None,
        "attempt_count": 0,
        "builder_model": "sonnet",
        "builder_model_reason": "auto-baseline",
        "gate_stub": _ok_gate,
        "gate_schema": _ok_gate,
        "gate_auth": _ok_gate,
        "last_attempt_outcome": OUTCOME_NONE,
        "checkpoint_step": [],
        "needs_spec": True,
    }
    action = resolve_next_action(position, gate_fn=lambda: True)
    assert action["action"] == SPAWN_SPEC_WRITER, (
        f"Expected spawn-spec-writer, got {action['action']!r}. Full action: {action}"
    )
    assert action["scalar"] == "RESOLVER-001"
    assert action["model"] == "opus"
    assert action["reason"] == "needs-spec"
    violations = validate_action(action)
    assert violations == [], f"Action schema violations: {violations}"


def test_resolve_emits_spawn_builder_when_needs_spec_false(
    tmp_path: Path,
) -> None:
    """When needs_spec = False, resolver proceeds to spawn-builder as before."""
    phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
    phase_file.parent.mkdir(parents=True, exist_ok=True)
    phase_file.write_text("# Phase 1\n", encoding="utf-8")

    _ok_gate = {"ok": True, "blocked_reason": ""}
    position = {
        "active_phase_file": phase_file,
        "next_story_id": "RESOLVER-001",
        "next_story_file": None,
        "attempt_count": 0,
        "builder_model": "sonnet",
        "builder_model_reason": "auto-baseline",
        "gate_stub": _ok_gate,
        "gate_schema": _ok_gate,
        "gate_auth": _ok_gate,
        "last_attempt_outcome": OUTCOME_NONE,
        "checkpoint_step": [],
        "needs_spec": False,
    }
    action = resolve_next_action(position, gate_fn=lambda: True)
    assert action["action"] == SPAWN_BUILDER, (
        f"Expected spawn-builder, got {action['action']!r}"
    )
    assert action["scalar"] == "RESOLVER-001"
    assert action["meta"]["attempt"] == 1
    violations = validate_action(action)
    assert violations == [], f"Action schema violations: {violations}"


def test_resolve_spawn_spec_writer_action_passes_validate(tmp_path: Path) -> None:
    """A spawn-spec-writer action produced by make_action passes validate_action."""
    action = make_action(
        SPAWN_SPEC_WRITER,
        scalar="RESOLVER-001",
        model="opus",
        reason="needs-spec",
    )
    violations = validate_action(action)
    assert violations == [], f"Unexpected violations: {violations}"
    assert action["meta"]["schema_version"] == 4


# ---------------------------------------------------------------------------
# End-to-end: infer_position + resolve_next_action via fixture
# ---------------------------------------------------------------------------


def test_e2e_stub_ensures_3lines_emits_spawn_spec_writer(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """End-to-end: story with 3-line ## Ensures → resolver emits spawn-spec-writer.

    Uses stub_ensures=True (3 non-blank Ensures lines, no delegation language)
    so the stub gate does NOT fire.  Only the needs_spec branch fires (Row 2).
    """
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("RESOLVER-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            "stub_ensures": True,
        },
    )
    _patch_git_log(monkeypatch, "")
    position = infer_position(project)
    assert position["needs_spec"] is True
    action = resolve_next_action(position, gate_fn=lambda: True)
    assert action["action"] == SPAWN_SPEC_WRITER
    assert action["model"] == "opus"
    assert action["reason"] == "needs-spec"
    assert validate_action(action) == []


def test_e2e_stub_ensures_emits_spawn_spec_writer(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """End-to-end: story with stub ## Ensures (3 lines) → resolver emits spawn-spec-writer."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("RESOLVER-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            "stub_ensures": True,
        },
    )
    _patch_git_log(monkeypatch, "")
    position = infer_position(project)
    action = resolve_next_action(position, gate_fn=lambda: True)
    assert action["action"] == SPAWN_SPEC_WRITER
    assert action["model"] == "opus"
    assert validate_action(action) == []


def test_e2e_complete_ensures_emits_spawn_builder(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """End-to-end: story with complete ## Ensures (>= 5 lines) → spawn-builder."""
    project = make_resolver_project(
        tmp_path,
        {
            "phase_status": "active",
            "stories": [("RESOLVER-001", "planned", "code", ["a.py"])],
            "attempt_count": 0,
            "git_commits": [],
            # Default fixture body has 5 non-blank Ensures lines
        },
    )
    _patch_git_log(monkeypatch, "")
    position = infer_position(project)
    action = resolve_next_action(position, gate_fn=lambda: True)
    assert action["action"] == SPAWN_BUILDER
    assert action["meta"]["attempt"] == 1
    assert validate_action(action) == []
