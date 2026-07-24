"""
tests/pairmode/test_checkpoint_routing.py

Tests for the pre-checkpoint guards and checkpoint step sequencing
introduced in RESOLVER-008.

Covers all six acceptance assertions from the story spec:
  1. Pre-guard failure (incomplete stories)
     → await-user:checkpoint-guard-failed:phase-incomplete
  2. Pre-guard pass (all complete, CER clear, gate green) + no checkpoint_step
     → checkpoint-security
  3. checkpoint_step: ["checkpoint-security"]
     → checkpoint-intent
  4. checkpoint_step: ["checkpoint-security", "checkpoint-intent"]
     → checkpoint-docs
  5. checkpoint_step: ["checkpoint-security", "checkpoint-intent", "checkpoint-docs"]
     → checkpoint-tag  (model=None enforced)
  6. All four steps done
     → done

All tests inject ``gate_fn=lambda: True`` so the live pytest subprocess is
never run.  The CER backlog file is absent in all fixtures (passes vacuously).
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
    AWAIT_USER,
    CHECKPOINT_DOCS,
    CHECKPOINT_INTENT,
    CHECKPOINT_SECURITY,
    CHECKPOINT_TAG,
    DONE,
    OUTCOME_NONE,
    check_checkpoint_guards,
    make_action,
    resolve_next_action,
    validate_action,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_OK_GATE: dict = {"ok": True, "blocked_reason": ""}


def _make_phase_file(
    tmp_path: Path,
    stories_and_statuses: "list[tuple[str, str]]",
) -> Path:
    """Write a minimal phase-1.md with a Stories table and return its path."""
    phases_dir = tmp_path / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Phase 1\n\n",
        "## Stories\n\n",
        "| ID | Title | Status |\n",
        "|----|-------|--------|\n",
    ]
    for story_id, status in stories_and_statuses:
        lines.append(f"| {story_id} | A story | {status} |\n")

    phase_file = phases_dir / "phase-1.md"
    phase_file.write_text("".join(lines), encoding="utf-8")
    return phase_file


def _make_position(phase_file: "Path | None", checkpoint_step: "list[str] | None" = None) -> dict:
    """Return a minimal Position dict for the checkpoint (next_story_id=None) path."""
    return {
        "active_phase_file": phase_file,
        "next_story_id": None,
        "attempt_count": 0,
        "builder_model": None,
        "builder_model_reason": None,
        "gate_stub": _OK_GATE,
        "gate_schema": _OK_GATE,
        "gate_auth": _OK_GATE,
        "last_attempt_outcome": OUTCOME_NONE,
        "checkpoint_step": checkpoint_step or [],
    }


# ---------------------------------------------------------------------------
# 1. Pre-guard failure: incomplete stories → phase-incomplete
# ---------------------------------------------------------------------------


def test_pre_guard_phase_incomplete(tmp_path: Path) -> None:
    """Phase has a 'planned' story → guard fails with phase-incomplete."""
    phase_file = _make_phase_file(
        tmp_path,
        [("RESOLVER-001", "planned")],
    )
    position = _make_position(phase_file, checkpoint_step=[])

    action = resolve_next_action(position, gate_fn=lambda: True)

    assert action["action"] == AWAIT_USER, (
        f"Expected await-user on phase-incomplete guard failure, got {action['action']!r}"
    )
    assert action["reason"] == "checkpoint-guard-failed:phase-incomplete", (
        f"Unexpected reason: {action['reason']!r}"
    )
    assert action["model"] is None
    violations = validate_action(action)
    assert violations == [], f"action failed schema validation: {violations}"


# ---------------------------------------------------------------------------
# 2-6. Step sequencing — all guards pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "checkpoint_step,expected_action,expected_model",
    [
        # 2: no steps done → checkpoint-security
        (
            [],
            CHECKPOINT_SECURITY,
            None,
        ),
        # 3: first step done → checkpoint-intent
        (
            [CHECKPOINT_SECURITY],
            CHECKPOINT_INTENT,
            None,
        ),
        # 4: first two done → checkpoint-docs
        (
            [CHECKPOINT_SECURITY, CHECKPOINT_INTENT],
            CHECKPOINT_DOCS,
            None,
        ),
        # 5: first three done → checkpoint-tag (model must be None)
        (
            [CHECKPOINT_SECURITY, CHECKPOINT_INTENT, CHECKPOINT_DOCS],
            CHECKPOINT_TAG,
            None,
        ),
        # 6: all four done → done
        (
            [CHECKPOINT_SECURITY, CHECKPOINT_INTENT, CHECKPOINT_DOCS, CHECKPOINT_TAG],
            DONE,
            None,
        ),
    ],
    ids=[
        "no-steps-done-checkpoint-security",
        "one-step-done-checkpoint-intent",
        "two-steps-done-checkpoint-docs",
        "three-steps-done-checkpoint-tag",
        "all-steps-done-done",
    ],
)
def test_checkpoint_step_sequencing(
    tmp_path: Path,
    checkpoint_step: "list[str]",
    expected_action: str,
    expected_model: "str | None",
) -> None:
    """Guards pass + varying checkpoint_step → correct next action."""
    # Phase with all stories complete so the phase-completion guard passes.
    phase_file = _make_phase_file(
        tmp_path,
        [("RESOLVER-001", "complete")],
    )
    position = _make_position(phase_file, checkpoint_step=checkpoint_step)

    action = resolve_next_action(position, gate_fn=lambda: True)

    assert action["action"] == expected_action, (
        f"checkpoint_step={checkpoint_step!r}: "
        f"expected action={expected_action!r}, got {action['action']!r}. "
        f"Full action: {action}"
    )
    assert action["model"] == expected_model, (
        f"checkpoint_step={checkpoint_step!r}: "
        f"expected model={expected_model!r}, got {action['model']!r}"
    )

    # Every emitted action must pass schema validation.
    violations = validate_action(action)
    assert violations == [], (
        f"checkpoint_step={checkpoint_step!r}: action failed schema validation: "
        + "; ".join(violations)
    )


# ---------------------------------------------------------------------------
# checkpoint-tag: explicit model=None assertion (story Ensures)
# ---------------------------------------------------------------------------


def test_checkpoint_tag_model_is_none(tmp_path: Path) -> None:
    """checkpoint-tag must carry model=None (it is not a spawn action)."""
    phase_file = _make_phase_file(
        tmp_path,
        [("RESOLVER-001", "complete")],
    )
    position = _make_position(
        phase_file,
        checkpoint_step=[CHECKPOINT_SECURITY, CHECKPOINT_INTENT, CHECKPOINT_DOCS],
    )

    action = resolve_next_action(position, gate_fn=lambda: True)

    assert action["action"] == CHECKPOINT_TAG
    assert action["model"] is None, (
        f"checkpoint-tag must have model=None; got {action['model']!r}"
    )
    assert validate_action(action) == []


# ---------------------------------------------------------------------------
# check_checkpoint_guards: direct unit tests
# ---------------------------------------------------------------------------


def test_check_guards_all_pass(tmp_path: Path) -> None:
    """All three guards pass → {"ok": True}."""
    phase_file = _make_phase_file(tmp_path, [("T-001", "complete")])
    result = check_checkpoint_guards(tmp_path, phase_file, gate_fn=lambda: True)
    assert result == {"ok": True}


def test_check_guards_phase_incomplete_direct(tmp_path: Path) -> None:
    """Phase-completion guard fails directly via check_checkpoint_guards."""
    phase_file = _make_phase_file(tmp_path, [("T-001", "planned")])
    result = check_checkpoint_guards(tmp_path, phase_file, gate_fn=lambda: True)
    assert result == {"ok": False, "failed_guard": "phase-incomplete"}


def test_check_guards_cer_do_now_unresolved(tmp_path: Path) -> None:
    """CER Do Now guard fails when backlog has an unresolved row."""
    phase_file = _make_phase_file(tmp_path, [("T-001", "complete")])

    # Write a CER backlog with one unresolved Do Now row.
    cer_dir = tmp_path / "docs" / "cer"
    cer_dir.mkdir(parents=True, exist_ok=True)
    (cer_dir / "backlog.md").write_text(
        "# CER Backlog\n\n"
        "## Do Now\n\n"
        "| ID | Finding | Source | Date | Phase |\n"
        "|----|---------|--------|------|-------|\n"
        "| CER-999 | An unresolved finding | some-source | 2026-01-01 | 1 |\n\n"
        "## Do Later\n\n"
        "| ID | Finding | Source | Date | Phase |\n",
        encoding="utf-8",
    )

    result = check_checkpoint_guards(tmp_path, phase_file, gate_fn=lambda: True)
    assert result == {"ok": False, "failed_guard": "cer-do-now"}


def test_check_guards_cer_do_now_all_resolved(tmp_path: Path) -> None:
    """CER Do Now guard passes when all rows are RESOLVED."""
    phase_file = _make_phase_file(tmp_path, [("T-001", "complete")])

    cer_dir = tmp_path / "docs" / "cer"
    cer_dir.mkdir(parents=True, exist_ok=True)
    (cer_dir / "backlog.md").write_text(
        "# CER Backlog\n\n"
        "## Do Now\n\n"
        "| ID | Finding | Source | Date | Phase |\n"
        "|----|---------|--------|------|-------|\n"
        "| CER-999 | A finding. **RESOLVED Phase 1** | source | 2026-01-01 | 1 |\n\n"
        "## Do Later\n\n",
        encoding="utf-8",
    )

    result = check_checkpoint_guards(tmp_path, phase_file, gate_fn=lambda: True)
    assert result == {"ok": True}


def test_check_guards_build_gate_fails(tmp_path: Path) -> None:
    """Build gate guard fails when gate_fn returns False."""
    phase_file = _make_phase_file(tmp_path, [("T-001", "complete")])
    result = check_checkpoint_guards(tmp_path, phase_file, gate_fn=lambda: False)
    assert result == {"ok": False, "failed_guard": "build-gate"}


def test_check_guards_absent_cer_file_passes(tmp_path: Path) -> None:
    """CER backlog absent → guard passes (fail-open)."""
    phase_file = _make_phase_file(tmp_path, [("T-001", "complete")])
    # No docs/cer/backlog.md created.
    result = check_checkpoint_guards(tmp_path, phase_file, gate_fn=lambda: True)
    assert result == {"ok": True}


def test_check_guards_deferred_stories_pass(tmp_path: Path) -> None:
    """'deferred' story status is treated as complete for the phase guard."""
    phase_file = _make_phase_file(
        tmp_path,
        [("T-001", "complete"), ("T-002", "deferred")],
    )
    result = check_checkpoint_guards(tmp_path, phase_file, gate_fn=lambda: True)
    assert result == {"ok": True}
