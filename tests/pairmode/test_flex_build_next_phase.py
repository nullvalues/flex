"""Tests for ``flex_build.py next-phase`` subcommand (Story INFRA-152).

Six test cases as specified in the story's ## Acceptance criteria section:

1. test_next_phase_integer_key        — integer keys; --after 59 → 60, exit 0.
2. test_next_phase_suffix_key         — suffix keys; --after RD077-main → RD077-post1, exit 0.
3. test_next_phase_last_row           — matched row is last; stdout empty, exit 1.
4. test_next_phase_not_in_index       — phase not in index; stdout empty, exit 1.
5. test_next_phase_no_index_file      — no index.md; stdout empty, exit 1.
6. test_next_phase_skips_complete_rows — status is irrelevant; next row returned regardless.
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


def _write_phase_index(project_dir: Path, rows: list[tuple[str, str]]) -> Path:
    """Write a ``docs/phases/index.md`` with (phase_ref, status) rows."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
    ]
    for phase_ref, status in rows:
        lines.append(f"| {phase_ref} | Some title | {status} | |\n")
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_next_phase_integer_key(tmp_path: Path) -> None:
    """Index has rows 58, 59, 60; --after 59 prints '60' and exits 0."""
    _write_phase_index(
        tmp_path,
        [
            ("58", "planned"),
            ("59", "planned"),
            ("60", "planned"),
        ],
    )
    result = _run("next-phase", "--after", "59", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "60"


def test_next_phase_suffix_key(tmp_path: Path) -> None:
    """Index has suffix-keyed rows; --after RD077-main prints 'RD077-post1' and exits 0."""
    _write_phase_index(
        tmp_path,
        [
            ("RD077-ante1", "planned"),
            ("RD077-main", "planned"),
            ("RD077-post1", "planned"),
        ],
    )
    result = _run("next-phase", "--after", "RD077-main", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "RD077-post1"


def test_next_phase_last_row(tmp_path: Path) -> None:
    """Matched row is the last in the index; stdout empty, exits 1."""
    _write_phase_index(
        tmp_path,
        [
            ("58", "planned"),
            ("59", "planned"),
        ],
    )
    result = _run("next-phase", "--after", "59", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert result.stdout.strip() == ""


def test_next_phase_not_in_index(tmp_path: Path) -> None:
    """Phase 99 is not in an index with rows 58, 59; stdout empty, exits 1."""
    _write_phase_index(
        tmp_path,
        [
            ("58", "planned"),
            ("59", "planned"),
        ],
    )
    result = _run("next-phase", "--after", "99", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert result.stdout.strip() == ""


def test_next_phase_no_index_file(tmp_path: Path) -> None:
    """No docs/phases/index.md exists; stdout empty, exits 1."""
    # Ensure no index.md is created — just use a bare tmp_path.
    result = _run("next-phase", "--after", "59", "--project-dir", str(tmp_path))
    assert result.returncode == 1
    assert result.stdout.strip() == ""


def test_next_phase_skips_complete_rows(tmp_path: Path) -> None:
    """Status is ignored — next row after '59 complete' is '60 planned', exits 0."""
    _write_phase_index(
        tmp_path,
        [
            ("58", "complete"),
            ("59", "complete"),
            ("60", "planned"),
        ],
    )
    result = _run("next-phase", "--after", "59", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "60"
