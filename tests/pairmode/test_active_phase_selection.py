"""Tests for _resolve_active_phase — first non-inactive wins (RESOLVER-014).

These tests drive ``_resolve_active_phase`` via a tmp_path project tree that
contains a minimal ``docs/phases/index.md`` and phase stub files.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from next_action import _resolve_active_phase  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_index(project_dir: Path, rows: list[tuple[str, str, str]]) -> None:
    """Write docs/phases/index.md with (phase_ref, title, status) rows."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
    ]
    for phase_ref, title, status in rows:
        lines.append(f"| {phase_ref} | {title} | {status} | |\n")
    (phases_dir / "index.md").write_text("".join(lines), encoding="utf-8")


def _stub_phase(project_dir: Path, phase_ref: str) -> Path:
    """Create an empty phase stub file; return its path."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    p = phases_dir / f"phase-{phase_ref}.md"
    p.write_text(f"# {phase_ref}\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_first_planned_wins_when_two_planned(tmp_path: Path) -> None:
    """A=complete, B=planned, C=planned → returns B's phase file."""
    _write_index(
        tmp_path,
        [
            ("phase-A", "Phase A", "complete"),
            ("phase-B", "Phase B", "planned"),
            ("phase-C", "Phase C", "planned"),
        ],
    )
    _stub_phase(tmp_path, "phase-A")
    b = _stub_phase(tmp_path, "phase-B")
    _stub_phase(tmp_path, "phase-C")

    result = _resolve_active_phase(tmp_path)
    assert result == b


def test_skips_deferred_returns_next_planned(tmp_path: Path) -> None:
    """A=complete, B=deferred, C=planned → returns C."""
    _write_index(
        tmp_path,
        [
            ("phase-A", "Phase A", "complete"),
            ("phase-B", "Phase B", "deferred"),
            ("phase-C", "Phase C", "planned"),
        ],
    )
    _stub_phase(tmp_path, "phase-A")
    _stub_phase(tmp_path, "phase-B")
    c = _stub_phase(tmp_path, "phase-C")

    result = _resolve_active_phase(tmp_path)
    assert result == c


def test_skips_backlog_returns_next_planned(tmp_path: Path) -> None:
    """A=complete, B=backlog, C=planned → returns C."""
    _write_index(
        tmp_path,
        [
            ("phase-A", "Phase A", "complete"),
            ("phase-B", "Phase B", "backlog"),
            ("phase-C", "Phase C", "planned"),
        ],
    )
    _stub_phase(tmp_path, "phase-A")
    _stub_phase(tmp_path, "phase-B")
    c = _stub_phase(tmp_path, "phase-C")

    result = _resolve_active_phase(tmp_path)
    assert result == c


def test_all_complete_returns_none(tmp_path: Path) -> None:
    """All phases complete → returns None."""
    _write_index(
        tmp_path,
        [
            ("phase-A", "Phase A", "complete"),
            ("phase-B", "Phase B", "complete"),
            ("phase-C", "Phase C", "complete"),
        ],
    )
    _stub_phase(tmp_path, "phase-A")
    _stub_phase(tmp_path, "phase-B")
    _stub_phase(tmp_path, "phase-C")

    result = _resolve_active_phase(tmp_path)
    assert result is None


def test_single_planned_returns_it(tmp_path: Path) -> None:
    """Single planned phase → returns it."""
    _write_index(
        tmp_path,
        [
            ("phase-X", "Phase X", "planned"),
        ],
    )
    x = _stub_phase(tmp_path, "phase-X")

    result = _resolve_active_phase(tmp_path)
    assert result == x
