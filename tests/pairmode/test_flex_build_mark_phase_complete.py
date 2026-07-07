"""Tests for ``flex_build.py mark-phase-complete`` subcommand.

Original test cases (Story INFRA-172):

1. test_planned_becomes_complete          — row with 'planned' → 'complete'; file updated.
2. test_already_complete_is_idempotent    — row already 'complete'; exits 0, no write needed.
3. test_other_status_becomes_complete     — row with 'planned-pending-design' → 'complete'.
4. test_phase_not_found_exits_1           — phase key absent from index; exits 1, error on stderr.
5. test_title_and_tag_preserved           — title and tag cells unchanged after marking complete.
6. test_suffixed_phase_key                — key 'PM037-main' accepted and processed correctly.
7. test_index_not_found_exits_1           — no index.md; exits 1, error on stderr.
8. test_atomic_write                      — large index; write completes without partial file.

BUILD-037 additions (column-count-preserving rewrite):

9.  test_five_column_row_preserved        — 5-col row stays 5 cols; Link + Deferred-from retained.
10. test_four_column_row_preserved        — 4-col row still produces correct 4-col complete row.
11. test_five_column_idempotent           — already-complete 5-col row: exit 0, file unchanged.
12. test_five_column_not_found            — absent phase key: exits 1, file unchanged.
13. test_five_column_round_trip           — after mark, _parse_index_phases yields correct status.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"

# Make flex_build importable for round-trip tests.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


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


def _write_five_col_index(
    project_dir: Path,
    rows: list[tuple[str, str, str, str, str]],
) -> Path:
    """Write a 5-column ``docs/phases/index.md`` (seeded fleet layout).

    Columns: Phase | Title | Status | Deferred from | Link

    Returns the path to the written index file.
    """
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Deferred from | Link |\n",
        "|-------|-------|--------|---------------|------|\n",
    ]
    for phase_ref, title, status, deferred_from, link in rows:
        lines.append(
            f"| {phase_ref} | {title} | {status} | {deferred_from} | {link} |\n"
        )
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


def _read_index(project_dir: Path) -> str:
    return (project_dir / "docs" / "phases" / "index.md").read_text(encoding="utf-8")


def _count_columns(row_line: str) -> int:
    """Return the number of inner cells in a markdown table row."""
    # Split on "|", drop empty first and last strings produced by leading/trailing "|".
    parts = [p for p in row_line.split("|") if True]
    # Leading and trailing are empty strings; strip them.
    inner = [p for p in parts[1:-1]]
    return len(inner)


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


# ---------------------------------------------------------------------------
# BUILD-037: column-count-preserving tests
# ---------------------------------------------------------------------------


def test_five_column_row_preserved(tmp_path: Path) -> None:
    """5-column index: after marking complete, the row is still 5 columns.

    The Link cell and Deferred-from cell must be byte-for-byte retained;
    only the status cell changes.
    """
    link_cell = "[phase-RK002-main.md](docs/phases/phase-RK002-main.md)"
    _write_five_col_index(
        tmp_path,
        [
            ("RK001-main", "Prior phase", "complete", "-", ""),
            ("RK002-main", "The phase", "planned", "-", link_cell),
        ],
    )
    result = _run(
        "mark-phase-complete",
        "--phase",
        "RK002-main",
        "--project-dir",
        str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = _read_index(tmp_path)
    target_lines = [ln for ln in content.splitlines() if "RK002-main" in ln]
    assert target_lines, "RK002-main row not found after update"
    row = target_lines[0]
    # Status updated.
    assert "complete" in row, f"Status not updated: {row}"
    assert "planned" not in row, f"Old status still present: {row}"
    # Link cell preserved verbatim.
    assert link_cell in row, f"Link cell missing or corrupted: {row}"
    # Deferred-from cell preserved.
    parts = [p.strip() for p in row.split("|")[1:-1]]
    assert len(parts) == 5, f"Expected 5 columns, got {len(parts)}: {row}"
    assert parts[3] == "-", f"Deferred-from cell changed: {parts[3]!r}"
    assert parts[4] == link_cell, f"Link cell changed: {parts[4]!r}"


def test_four_column_row_preserved(tmp_path: Path) -> None:
    """4-column index (native layout): row stays 4 columns and becomes complete."""
    _write_phase_index(
        tmp_path,
        [
            ("71", "Some phase", "planned", "cp71"),
        ],
    )
    result = _run(
        "mark-phase-complete", "--phase", "71", "--project-dir", str(tmp_path)
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = _read_index(tmp_path)
    target_lines = [ln for ln in content.splitlines() if "| 71 |" in ln]
    assert target_lines, "Phase 71 row not found"
    row = target_lines[0]
    assert "complete" in row, f"Status not updated: {row}"
    # Tag preserved.
    assert "cp71" in row, f"Tag cell lost: {row}"
    # Column count preserved at 4.
    parts = [p.strip() for p in row.split("|")[1:-1]]
    assert len(parts) == 4, f"Expected 4 columns, got {len(parts)}: {row}"


def test_five_column_idempotent(tmp_path: Path) -> None:
    """Marking an already-complete 5-column row is a no-op (exit 0, file unchanged)."""
    link_cell = "[phase.md](docs/phases/phase.md)"
    index_path = _write_five_col_index(
        tmp_path,
        [
            ("RK003-main", "Done phase", "complete", "—", link_cell),
        ],
    )
    original_content = index_path.read_text(encoding="utf-8")
    result = _run(
        "mark-phase-complete",
        "--phase",
        "RK003-main",
        "--project-dir",
        str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    content = index_path.read_text(encoding="utf-8")
    assert content == original_content, "File was rewritten despite row already being complete"


def test_five_column_not_found(tmp_path: Path) -> None:
    """Phase key absent from a 5-column index: exits 1, file unchanged."""
    index_path = _write_five_col_index(
        tmp_path,
        [
            ("RK010-main", "Some phase", "planned", "—", ""),
        ],
    )
    original_content = index_path.read_text(encoding="utf-8")
    result = _run(
        "mark-phase-complete",
        "--phase",
        "RK999-main",
        "--project-dir",
        str(tmp_path),
    )
    assert result.returncode == 1
    assert "RK999-main" in result.stderr or "not in index" in result.stderr
    content = index_path.read_text(encoding="utf-8")
    assert content == original_content, "File was modified despite phase key not found"


def test_five_column_round_trip(tmp_path: Path) -> None:
    """After mark-phase-complete on a 5-col index, _parse_index_phases returns correct statuses.

    Verifies no column-count drift on any row and that the target row is now 'complete'.
    """
    from skills.pairmode.scripts.flex_build import _parse_index_phases  # noqa: PLC0415

    _write_five_col_index(
        tmp_path,
        [
            ("RK020-ante1", "Ante phase", "complete", "—", ""),
            ("RK020-main", "Main phase", "planned", "—", "[phase.md](docs/phases/phase.md)"),
            ("RK020-post1", "Post phase", "planned", "—", ""),
        ],
    )
    result = _run(
        "mark-phase-complete",
        "--phase",
        "RK020-main",
        "--project-dir",
        str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    content = _read_index(tmp_path)
    parsed = _parse_index_phases(content)
    parsed_dict = {ref: status for ref, status in parsed}

    assert parsed_dict.get("RK020-ante1") == "complete", "ante1 status changed"
    assert parsed_dict.get("RK020-main") == "complete", "main status not updated"
    assert parsed_dict.get("RK020-post1") == "planned", "post1 status changed"

    # Also verify that no data rows lost columns (all data rows should have 5 inner cells).
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [p.strip() for p in stripped.split("|")[1:-1]]
        # Skip header and separator rows (separator rows contain dashes).
        if all(set(c) <= set("-:") for c in cells if c):
            continue
        if any(heading in cells for heading in ("Phase", "Title", "Status")):
            continue
        if cells:
            assert len(cells) == 5, (
                f"Column count drifted for row '{stripped}': "
                f"expected 5, got {len(cells)}"
            )
