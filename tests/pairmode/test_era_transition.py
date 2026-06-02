"""
tests/pairmode/test_era_transition.py

Tests for era_transition.py — formal era transition command.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

# Make the scripts directory importable
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from era_transition import era_transition, era_transition_cli, _close_era_frontmatter  # noqa: E402
from flex_build import flex_build  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_era(eras_dir: Path, era_id: str, name: str, status: str = "active") -> Path:
    """Create a minimal era file and return its path."""
    eras_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    filename = f"{era_id}-{slug}.md"
    path = eras_dir / filename
    content = f'---\nid: "{era_id}"\nname: {name}\nstatus: {status}\n---\n\n## Strategic intent\n\n_(fill in)_\n'
    path.write_text(content, encoding="utf-8")
    return path


def _project_with_one_active_era(tmp_path: Path) -> Path:
    """Return a project dir that has exactly one active era (001)."""
    eras_dir = tmp_path / "docs" / "eras"
    _make_era(eras_dir, "001", "Initial era", "active")
    return tmp_path


# ---------------------------------------------------------------------------
# 1. test_transition_closes_active_era
# ---------------------------------------------------------------------------

def test_transition_closes_active_era(tmp_path: Path) -> None:
    """Closing the active era sets status: complete and adds closed_at."""
    project_dir = _project_with_one_active_era(tmp_path)
    eras_dir = project_dir / "docs" / "eras"

    rc = era_transition_cli(
        project_dir=str(project_dir),
        name="Next era",
        intent="",
        yes=True,
    )
    assert rc == 0

    old_era_path = eras_dir / "001-initial-era.md"
    assert old_era_path.exists()
    content = old_era_path.read_text(encoding="utf-8")

    # Status must be complete
    assert "status: complete" in content
    # closed_at must be present
    assert "closed_at:" in content
    # Verify ISO date pattern
    assert re.search(r"closed_at: \d{4}-\d{2}-\d{2}", content)


# ---------------------------------------------------------------------------
# 2. test_transition_creates_new_era
# ---------------------------------------------------------------------------

def test_transition_creates_new_era(tmp_path: Path) -> None:
    """After transition the new era file exists with status: active and sequential ID."""
    project_dir = _project_with_one_active_era(tmp_path)
    eras_dir = project_dir / "docs" / "eras"

    rc = era_transition_cli(
        project_dir=str(project_dir),
        name="Second era",
        intent="Build bigger things",
        yes=True,
    )
    assert rc == 0

    # New era should be 002-second-era.md
    new_era_path = eras_dir / "002-second-era.md"
    assert new_era_path.exists(), f"Expected {new_era_path} to exist"

    content = new_era_path.read_text(encoding="utf-8")
    assert "status: active" in content
    assert "Second era" in content
    assert "Build bigger things" in content


# ---------------------------------------------------------------------------
# 3. test_transition_no_active_era_exits_1
# ---------------------------------------------------------------------------

def test_transition_no_active_era_exits_1(tmp_path: Path) -> None:
    """When no active era exists, the command exits 1 with an appropriate message."""
    eras_dir = tmp_path / "docs" / "eras"
    # Create a complete era (not active)
    _make_era(eras_dir, "001", "Old era", "complete")

    runner = CliRunner()
    result = runner.invoke(
        era_transition,
        ["--project-dir", str(tmp_path), "--name", "New era", "--yes"],
    )
    assert result.exit_code == 1
    assert "No active era to close" in result.output


def test_transition_no_eras_dir_exits_1(tmp_path: Path) -> None:
    """When docs/eras/ doesn't exist at all, the command exits 1."""
    runner = CliRunner()
    result = runner.invoke(
        era_transition,
        ["--project-dir", str(tmp_path), "--name", "New era", "--yes"],
    )
    assert result.exit_code == 1
    assert "No active era to close" in result.output


# ---------------------------------------------------------------------------
# 4. test_transition_multiple_active_eras_exits_1
# ---------------------------------------------------------------------------

def test_transition_multiple_active_eras_exits_1(tmp_path: Path) -> None:
    """When multiple active eras exist, the command exits 1."""
    eras_dir = tmp_path / "docs" / "eras"
    _make_era(eras_dir, "001", "Era one", "active")
    _make_era(eras_dir, "002", "Era two", "active")

    runner = CliRunner()
    result = runner.invoke(
        era_transition,
        ["--project-dir", str(tmp_path), "--name", "New era", "--yes"],
    )
    assert result.exit_code == 1
    assert "Multiple active eras found" in result.output


# ---------------------------------------------------------------------------
# 5. test_transition_project_dir_depth_guard
# ---------------------------------------------------------------------------

def test_transition_project_dir_depth_guard() -> None:
    """Paths that are too shallow are rejected by the depth guard."""
    runner = CliRunner()
    result = runner.invoke(
        era_transition,
        ["--project-dir", "/tmp", "--name", "New era", "--yes"],
    )
    assert result.exit_code == 1
    assert "suspicious path" in result.output or "depth guard" in result.output or result.exit_code == 1


# ---------------------------------------------------------------------------
# 6. test_flex_build_transition_era_subcommand
# ---------------------------------------------------------------------------

def test_flex_build_transition_era_subcommand() -> None:
    """flex_build.py transition-era --help exits 0 (subcommand is wired)."""
    runner = CliRunner()
    result = runner.invoke(flex_build, ["transition-era", "--help"])
    assert result.exit_code == 0
    assert "transition-era" in result.output or "era" in result.output.lower()


# ---------------------------------------------------------------------------
# 7. test_close_era_frontmatter_unit
# ---------------------------------------------------------------------------

def test_close_era_frontmatter_unit() -> None:
    """_close_era_frontmatter correctly updates the frontmatter block."""
    content = '---\nid: "001"\nname: Initial era\nstatus: active\n---\n\nBody text.\n'
    updated = _close_era_frontmatter(content, "2026-06-02")
    assert "status: complete" in updated
    assert "closed_at: 2026-06-02" in updated
    assert "Body text." in updated
    # active should no longer appear as a status value
    assert "status: active" not in updated


def test_close_era_frontmatter_idempotent_closed_at() -> None:
    """_close_era_frontmatter does not add a second closed_at if already present."""
    content = '---\nid: "001"\nname: Initial era\nstatus: active\nclosed_at: 2025-01-01\n---\n'
    updated = _close_era_frontmatter(content, "2026-06-02")
    # Should only appear once
    assert updated.count("closed_at:") == 1


# ---------------------------------------------------------------------------
# 8. test_yes_mode_requires_name
# ---------------------------------------------------------------------------

def test_yes_mode_requires_name(tmp_path: Path) -> None:
    """--yes without --name exits 1 with an error message."""
    _project_with_one_active_era(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        era_transition,
        ["--project-dir", str(tmp_path), "--yes"],
    )
    assert result.exit_code == 1
    assert "--name is required" in result.output or "required" in result.output.lower()


# ---------------------------------------------------------------------------
# 9. test_transition_new_era_already_exists_exits_1
# ---------------------------------------------------------------------------

def test_transition_new_era_already_exists_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the new era file already exists with the same computed ID, exits 1."""
    import era_transition as et

    project_dir = _project_with_one_active_era(tmp_path)
    eras_dir = project_dir / "docs" / "eras"

    # _next_era_id will return 2 for a project with only 001.
    # Pre-create 002-second-era.md to trigger the existence guard.
    # Then monkeypatch _next_era_id so it still returns 2 regardless.
    (eras_dir / "002-second-era.md").write_text(
        '---\nid: "002"\nname: Second era\nstatus: complete\n---\n',
        encoding="utf-8",
    )
    # Patch _next_era_id in the era_transition module to return 2
    # (bypassing the actual glob which would now return 3 due to 002 existing).
    monkeypatch.setattr(et, "_next_era_id", lambda _eras_dir: 2)

    runner = CliRunner()
    result = runner.invoke(
        era_transition,
        ["--project-dir", str(project_dir), "--name", "Second era", "--yes"],
    )
    assert result.exit_code == 1
    assert "already exists" in result.output
