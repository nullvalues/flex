"""Tests for ``flex_build.py current-phase`` subcommand (Story BUILD-011).

Four tests as specified in the story's ## Tests section:

1. test_current_phase_from_index       — index has one active phase; path returned.
2. test_current_phase_all_complete     — all phases complete; exit 1.
3. test_current_phase_fallback_no_index — no index; phase file with unbuilt story.
4. test_current_phase_project_dir_depth_guard — path traversal rejected.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess:
    """Invoke flex_build.py with *args*; return the completed process."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(_REPO_ROOT),
        },
    )


def _write_phase_index(project_dir: Path, rows: list[tuple[str, str, str]]) -> Path:
    """Write a ``docs/phases/index.md`` with the given Phase / Title / Status rows."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
    ]
    for phase_ref, title, status in rows:
        lines.append(f"| {phase_ref} | {title} | {status} | |\n")
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


def _write_phase_file(project_dir: Path, phase_num: int, story_id: str) -> Path:
    """Write a minimal phase file with one ``planned`` story in the Stories table."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_path = phases_dir / f"phase-{phase_num}.md"
    content = (
        f"# Phase {phase_num}\n\n"
        "## Stories\n\n"
        "| ID | Title | Status |\n"
        "|----|-------|--------|\n"
        f"| {story_id} | A story | planned |\n"
    )
    phase_path.write_text(content, encoding="utf-8")
    return phase_path


def _write_story_file(project_dir: Path, story_id: str) -> Path:
    """Write a minimal story file so ``resolve_story`` can find it."""
    rail = story_id.split("-", 1)[0]
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"
    story_path.write_text(
        f"---\nid: {story_id}\nrail: {rail}\nstatus: planned\n"
        "phase: '1'\nprimary_files: []\n---\n\n## Ensures\n\n- It works.\n",
        encoding="utf-8",
    )
    return story_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_current_phase_from_index(tmp_path: Path) -> None:
    """Index has one active (planned) phase; command returns its path and exits 0."""
    _write_phase_index(
        tmp_path,
        [
            ("1", "Foundation", "complete"),
            ("2", "Active phase", "planned"),
        ],
    )
    _write_phase_file(tmp_path, 2, "RAIL-001")
    _write_story_file(tmp_path, "RAIL-001")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "phase-2.md" in result.stdout.strip()


def test_current_phase_all_complete(tmp_path: Path) -> None:
    """All phases are complete; command exits 1 with an informative message."""
    _write_phase_index(
        tmp_path,
        [
            ("1", "Foundation", "complete"),
            ("2", "More work", "complete"),
        ],
    )
    # Phase files exist but everything in the index is complete.
    _write_phase_file(tmp_path, 1, "RAIL-001")
    _write_phase_file(tmp_path, 2, "RAIL-002")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    # Error message goes to stderr.
    assert "all stories complete" in result.stderr.lower()


def test_current_phase_fallback_no_index(tmp_path: Path) -> None:
    """No index file; command scans phase files directly and finds one with an unbuilt story."""
    # No index.md — only a phase file with a planned story.
    _write_phase_file(tmp_path, 7, "FEAT-010")
    _write_story_file(tmp_path, "FEAT-010")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "phase-7.md" in result.stdout.strip()


def test_current_phase_project_dir_depth_guard(tmp_path: Path) -> None:
    """A --project-dir that resolves to fewer than 3 path components is rejected."""
    # The depth guard rejects paths like "/" or "/tmp" (fewer than 3 parts).
    result = _run("current-phase", "--project-dir", "/")
    assert result.returncode == 1
    assert "depth guard" in result.stderr.lower() or "too shallow" in result.stderr.lower()


# ---------------------------------------------------------------------------
# BUILD-036 — first-incomplete selection + status classification
# ---------------------------------------------------------------------------


def _write_phase_index_4col(
    project_dir: Path, rows: list[tuple[str, str, str]]
) -> Path:
    """Write a 4-column ``docs/phases/index.md`` (Phase | Title | Status | Tag)."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
    ]
    for phase_ref, title, status in rows:
        lines.append(f"| {phase_ref} | {title} | {status} | |\n")
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


def _write_phase_index_5col(
    project_dir: Path, rows: list[tuple[str, str, str]]
) -> Path:
    """Write a 5-column seeded ``docs/phases/index.md`` (Phase | Title | Status | Deferred from | Link)."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Deferred from | Link |\n",
        "|-------|-------|--------|---------------|------|\n",
    ]
    for phase_ref, title, status in rows:
        lines.append(f"| {phase_ref} | {title} | {status} | | |\n")
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


def test_build036_first_of_two_active_phases(tmp_path: Path) -> None:
    """Two planned phases both with files → first in index order is returned."""
    _write_phase_index_4col(
        tmp_path,
        [
            ("10", "First active", "planned"),
            ("20", "Second active", "planned"),
        ],
    )
    _write_phase_file(tmp_path, 10, "RAIL-010")
    _write_phase_file(tmp_path, 20, "RAIL-020")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "phase-10.md" in result.stdout.strip()
    assert "phase-20.md" not in result.stdout.strip()


def test_build036_earlier_file_wins_over_fileless_later(tmp_path: Path) -> None:
    """Active phase with a file is returned even when a later planned phase has no file."""
    _write_phase_index_4col(
        tmp_path,
        [
            ("5", "Has file", "planned"),
            ("99", "No file yet", "planned"),
        ],
    )
    # Only phase-5.md exists; phase-99.md does NOT.
    _write_phase_file(tmp_path, 5, "RAIL-005")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "phase-5.md" in result.stdout.strip()


def test_build036_deferred_row_is_skipped(tmp_path: Path) -> None:
    """A deferred row is never returned even when it is the only non-complete row."""
    _write_phase_index_4col(
        tmp_path,
        [
            ("3", "Done", "complete"),
            ("64", "Deferred phase", "deferred"),
        ],
    )
    # Provide the file so the guard does not mask a missing-file scenario.
    _write_phase_file(tmp_path, 64, "RAIL-064")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert "all stories complete" in result.stderr.lower()


def test_build036_complete_partial_is_terminal(tmp_path: Path) -> None:
    """``complete (partial)`` is treated as terminal, not active."""
    _write_phase_index_4col(
        tmp_path,
        [
            ("23", "Partial done", "complete (partial)"),
        ],
    )
    _write_phase_file(tmp_path, 23, "RAIL-023")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert "all stories complete" in result.stderr.lower()


def test_build036_single_active_phase_resolves(tmp_path: Path) -> None:
    """Regression: a single normal active phase still resolves correctly."""
    _write_phase_index_4col(
        tmp_path,
        [
            ("7", "Active", "in-progress"),
        ],
    )
    _write_phase_file(tmp_path, 7, "RAIL-007")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "phase-7.md" in result.stdout.strip()


def test_release008_deferred_then_planned_fileless_returns_next_existing(
    tmp_path: Path,
) -> None:
    """RELEASE-008 fold regression: deferred row followed by a planned-fileless row.

    A ``deferred`` row is skipped (inactive), the following ``planned`` row has no
    phase file (fileless guard keeps scanning), and the first active row after
    the deferred entry whose file exists is returned.
    """
    _write_phase_index_4col(
        tmp_path,
        [
            ("1", "Done", "complete"),
            ("64", "Parked", "deferred"),
            ("70", "Planned but fileless", "planned"),
            ("71", "Planned with file", "planned"),
        ],
    )
    # phase-64.md exists but is deferred; phase-70.md does NOT exist;
    # phase-71.md exists and must be the one returned.
    _write_phase_file(tmp_path, 64, "RAIL-064")
    _write_phase_file(tmp_path, 71, "RAIL-071")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "phase-71.md" in result.stdout.strip()
    assert "phase-64.md" not in result.stdout.strip()
    assert "phase-70.md" not in result.stdout.strip()


def test_build036_five_column_layout(tmp_path: Path) -> None:
    """5-column seeded layout resolves identically to 4-column layout."""
    _write_phase_index_5col(
        tmp_path,
        [
            ("11", "Complete", "complete"),
            ("12", "Active 5col", "planned"),
        ],
    )
    _write_phase_file(tmp_path, 12, "RAIL-012")

    result = _run("current-phase", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "phase-12.md" in result.stdout.strip()
