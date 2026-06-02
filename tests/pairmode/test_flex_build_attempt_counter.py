"""Tests for ``flex_build.py`` attempt-counter subcommands (Story BUILD-022).

Subcommands under test:
  write-attempt-count  — persist {story_id, attempt_count} to .companion/attempt_counter.json
  read-attempt-count   — print persisted count (0 on absent/mismatch/malformed)
  clear-attempt-count  — delete the counter file; silent no-op when absent

Tests follow the pattern in ``tests/pairmode/test_flex_build_current_phase.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"

_STORY_ID = "BUILD-022"
_OTHER_STORY_ID = "INFRA-135"


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


def _counter_path(project_dir: Path) -> Path:
    return project_dir / ".companion" / "attempt_counter.json"


# ---------------------------------------------------------------------------
# Tests — write-attempt-count
# ---------------------------------------------------------------------------


def test_write_attempt_count_creates_file_with_expected_shape(tmp_path: Path) -> None:
    """write-attempt-count creates the file with the correct JSON shape."""
    # Create .companion/ so the depth guard (3+ path parts) passes.
    companion = tmp_path / ".companion"
    companion.mkdir()

    result = _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "2",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    counter_file = _counter_path(tmp_path)
    assert counter_file.exists()
    data = json.loads(counter_file.read_text(encoding="utf-8"))
    assert data == {"story_id": _STORY_ID, "attempt_count": 2}


def test_write_attempt_count_creates_companion_dir(tmp_path: Path) -> None:
    """write-attempt-count creates .companion/ when it does not exist."""
    assert not (tmp_path / ".companion").exists()

    result = _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "1",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert _counter_path(tmp_path).exists()


def test_write_attempt_count_overwrites_existing_file(tmp_path: Path) -> None:
    """write-attempt-count with count=3 overwrites an earlier count=1 file."""
    _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "1",
        "--project-dir", str(tmp_path),
    )

    result = _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "3",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    data = json.loads(_counter_path(tmp_path).read_text(encoding="utf-8"))
    assert data["attempt_count"] == 3


# ---------------------------------------------------------------------------
# Tests — read-attempt-count
# ---------------------------------------------------------------------------


def test_read_attempt_count_returns_persisted_value(tmp_path: Path) -> None:
    """read-attempt-count prints the stored integer when story_id matches."""
    _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "2",
        "--project-dir", str(tmp_path),
    )

    result = _run(
        "read-attempt-count",
        "--story-id", _STORY_ID,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "2"


def test_read_attempt_count_missing_file_returns_zero(tmp_path: Path) -> None:
    """read-attempt-count prints 0 and exits 0 when no counter file exists."""
    result = _run(
        "read-attempt-count",
        "--story-id", _STORY_ID,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "0"


def test_read_attempt_count_mismatched_story_returns_zero(tmp_path: Path) -> None:
    """read-attempt-count prints 0 when story_id in file differs from requested."""
    _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "2",
        "--project-dir", str(tmp_path),
    )

    result = _run(
        "read-attempt-count",
        "--story-id", _OTHER_STORY_ID,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "0"


def test_read_attempt_count_malformed_file_returns_zero(tmp_path: Path) -> None:
    """read-attempt-count prints 0 when counter file contains non-JSON garbage."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    _counter_path(tmp_path).write_text("this is not json {{{{", encoding="utf-8")

    result = _run(
        "read-attempt-count",
        "--story-id", _STORY_ID,
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == "0"


# ---------------------------------------------------------------------------
# Tests — clear-attempt-count
# ---------------------------------------------------------------------------


def test_clear_attempt_count_removes_file(tmp_path: Path) -> None:
    """clear-attempt-count deletes the counter file when it exists."""
    _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "2",
        "--project-dir", str(tmp_path),
    )
    assert _counter_path(tmp_path).exists()

    result = _run("clear-attempt-count", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not _counter_path(tmp_path).exists()


def test_clear_attempt_count_missing_file_noop(tmp_path: Path) -> None:
    """clear-attempt-count exits 0 silently when no counter file exists."""
    assert not _counter_path(tmp_path).exists()

    result = _run("clear-attempt-count", "--project-dir", str(tmp_path))
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout == ""
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# Tests — gitignore coverage
# ---------------------------------------------------------------------------


def test_attempt_counter_path_is_gitignored(tmp_path: Path) -> None:
    """The counter file path is covered by the .companion/ rule in .gitignore."""
    # Use the actual repo directory where git is initialized, so
    # `git check-ignore` can resolve the .gitignore rules properly.
    proc = subprocess.run(
        ["git", "check-ignore", "-q", ".companion/attempt_counter.json"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
    )
    assert proc.returncode == 0, (
        ".companion/attempt_counter.json is NOT covered by .gitignore"
    )


# ---------------------------------------------------------------------------
# Tests — depth guard
# ---------------------------------------------------------------------------


def test_write_attempt_count_depth_guard(tmp_path: Path) -> None:
    """A --project-dir that resolves to fewer than 3 path components is rejected."""
    result = _run(
        "write-attempt-count",
        "--story-id", _STORY_ID,
        "--count", "1",
        "--project-dir", "/",
    )
    assert result.returncode == 1
    assert "depth guard" in result.stderr.lower() or "too shallow" in result.stderr.lower()
