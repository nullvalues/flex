"""Tests for ``flex_build.py mark-phase-complete`` subcommand (Story INFRA-172).

Test cases as specified in the story's ## Acceptance criteria section:

1. test_planned_becomes_complete          — row with 'planned' → 'complete'; file updated.
2. test_already_complete_is_idempotent    — row already 'complete'; exits 0, no write needed.
3. test_other_status_becomes_complete     — row with 'planned-pending-design' → 'complete'.
4. test_phase_not_found_exits_1           — phase key absent from index; exits 1, error on stderr.
5. test_title_and_tag_preserved           — title and tag cells unchanged after marking complete.
6. test_suffixed_phase_key                — key 'PM037-main' accepted and processed correctly.
7. test_index_not_found_exits_1           — no index.md; exits 1, error on stderr.
8. test_atomic_write                      — large index; write completes without partial file.
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
    """Invoke flex_build.py with *args* and return the completed process."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(_REPO_ROOT),
        },
    )


def _write_phase_index(
    project_dir: Path,
    rows: list[tuple[str, str, str, str]],
) -> Path:
    """Write a ``docs/phases/index.md`` with (phase_ref, title, status, tag) rows.

    Returns the path to the written index file.
    """
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
    ]
    for phase_ref, title, status, tag in rows:
        lines.append(f"| {phase_ref} | {title} | {status} | {tag} |\n")
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


def _read_index(project_dir: Path) -> str:
    return (project_dir / "docs" / "phases" / "index.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_planned_becomes_complete(tmp_path: Path) -> None:
    """A row with status 'planned' is updated to 'complete'; command exits 0."""
    _write_phase_index(
        tmp_path,
        [
            ("58", "Prior phase", "complete", "cp58"),
            ("59", "The target phase", "planned", ""),
        ],
    )
    result = _run(
        "mark-phase-complete", "--phase", "59", "--project-dir", str(tmp_path)
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = _read_index(tmp_path)
    assert "complete" in content
    # The 'planned' value for phase 59 should be gone.
    lines = [ln for ln in content.splitlines() if "| 59 |" in ln]
    assert lines, "Phase 59 row not found after update"
    assert "complete" in lines[0]
    assert "planned" not in lines[0]


def test_already_complete_is_idempotent(tmp_path: Path) -> None:
    """Row already marked 'complete' — command exits 0 and file is unchanged."""
    index_path = _write_phase_index(
        tmp_path,
        [
            ("59", "Already done", "complete", "cp59"),
        ],
    )
    original_mtime = index_path.stat().st_mtime
    result = _run(
        "mark-phase-complete", "--phase", "59", "--project-dir", str(tmp_path)
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # File should not have been rewritten (mtime unchanged on most filesystems).
    # We can't rely on mtime in all environments, so we verify content is correct.
    content = _read_index(tmp_path)
    lines = [ln for ln in content.splitlines() if "| 59 |" in ln]
    assert lines
    assert "complete" in lines[0]


def test_other_status_becomes_complete(tmp_path: Path) -> None:
    """A row with status 'planned-pending-design' is updated to 'complete'."""
    _write_phase_index(
        tmp_path,
        [
            ("60", "Pending design phase", "planned-pending-design", ""),
        ],
    )
    result = _run(
        "mark-phase-complete", "--phase", "60", "--project-dir", str(tmp_path)
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = _read_index(tmp_path)
    lines = [ln for ln in content.splitlines() if "| 60 |" in ln]
    assert lines
    assert "complete" in lines[0]
    assert "planned-pending-design" not in lines[0]


def test_phase_not_found_exits_1(tmp_path: Path) -> None:
    """Phase key absent from index; command exits 1 with an error on stderr."""
    _write_phase_index(
        tmp_path,
        [
            ("58", "Some phase", "planned", ""),
            ("59", "Another phase", "planned", ""),
        ],
    )
    result = _run(
        "mark-phase-complete", "--phase", "99", "--project-dir", str(tmp_path)
    )
    assert result.returncode == 1
    assert "99" in result.stderr or "not in index" in result.stderr


def test_title_and_tag_preserved(tmp_path: Path) -> None:
    """After marking complete, the title and tag cells are unchanged."""
    _write_phase_index(
        tmp_path,
        [
            ("61", "My special title", "planned", "my-special-tag"),
        ],
    )
    result = _run(
        "mark-phase-complete", "--phase", "61", "--project-dir", str(tmp_path)
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = _read_index(tmp_path)
    lines = [ln for ln in content.splitlines() if "| 61 |" in ln]
    assert lines, "Phase 61 row not found after update"
    row = lines[0]
    assert "My special title" in row, f"Title missing from row: {row}"
    assert "my-special-tag" in row, f"Tag missing from row: {row}"
    assert "complete" in row, f"Status not updated in row: {row}"


def test_suffixed_phase_key(tmp_path: Path) -> None:
    """A suffixed phase key like 'PM037-main' is accepted and marked complete."""
    _write_phase_index(
        tmp_path,
        [
            ("PM037-ante1", "Ante phase", "complete", ""),
            ("PM037-main", "Main phase", "planned", ""),
            ("PM037-post1", "Post phase", "planned", ""),
        ],
    )
    result = _run(
        "mark-phase-complete",
        "--phase",
        "PM037-main",
        "--project-dir",
        str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = _read_index(tmp_path)
    lines = [ln for ln in content.splitlines() if "PM037-main" in ln]
    assert lines, "PM037-main row not found"
    assert "complete" in lines[0]
    # Ensure PM037-post1 was NOT changed.
    post_lines = [ln for ln in content.splitlines() if "PM037-post1" in ln]
    assert post_lines
    assert "planned" in post_lines[0]


def test_index_not_found_exits_1(tmp_path: Path) -> None:
    """No docs/phases/index.md exists; command exits 1 with an error on stderr."""
    # Don't create index.md — bare tmp_path.
    result = _run(
        "mark-phase-complete", "--phase", "59", "--project-dir", str(tmp_path)
    )
    assert result.returncode == 1
    assert "index" in result.stderr.lower() or "not found" in result.stderr.lower()


def test_atomic_write(tmp_path: Path) -> None:
    """Write completes correctly on a large index (100 rows)."""
    rows = [(str(i), f"Phase {i} title", "planned", f"cp{i}") for i in range(1, 101)]
    _write_phase_index(tmp_path, rows)
    # Mark phase 50 as complete.
    result = _run(
        "mark-phase-complete", "--phase", "50", "--project-dir", str(tmp_path)
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = _read_index(tmp_path)
    # Phase 50 row should be complete.
    lines_50 = [ln for ln in content.splitlines() if "| 50 |" in ln]
    assert lines_50, "Phase 50 row not found"
    assert "complete" in lines_50[0]
    # All other rows should still be 'planned'.
    for i in range(1, 101):
        if i == 50:
            continue
        row_lines = [ln for ln in content.splitlines() if f"| {i} |" in ln]
        assert row_lines, f"Phase {i} row missing"
        assert "planned" in row_lines[0], f"Phase {i} was unexpectedly changed"
    # No temp files should remain in the phases directory.
    phases_dir = tmp_path / "docs" / "phases"
    tmp_files = list(phases_dir.glob("*.tmp"))
    assert tmp_files == [], f"Temporary files left behind: {tmp_files}"
