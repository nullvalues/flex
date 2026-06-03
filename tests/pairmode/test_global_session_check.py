"""Tests for skills/pairmode/scripts/global_session_check.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "skills" / "pairmode" / "scripts" / "global_session_check.py"


def _run(cwd: Path) -> subprocess.CompletedProcess:
    """Run global_session_check.py with *cwd* as the working directory."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env={**__import__("os").environ, "FLEX_DIR": str(REPO_ROOT)},
    )


def _write_companion(cwd: Path, state: dict | None = None, ctx: dict | None = None) -> None:
    companion = cwd / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    if state is not None:
        (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")
    if ctx is not None:
        (companion / "pairmode_context.json").write_text(json.dumps(ctx), encoding="utf-8")


def _write_era(cwd: Path, era_id: str, status: str = "active") -> None:
    eras_dir = cwd / "docs" / "eras"
    eras_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\nid: \"{era_id}\"\nname: Test era\nstatus: {status}\n---\n"
    (eras_dir / f"{era_id}-test.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Non-pairmode project
# ---------------------------------------------------------------------------


def test_non_pairmode_soft_prompt(tmp_path):
    """A project with no pairmode markers → soft prompt text on stdout."""
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Pairmode not configured" in result.stdout
    assert "/flex:pairmode bootstrap" in result.stdout
    assert "Skip this" in result.stdout


# ---------------------------------------------------------------------------
# Pairmode project — story present
# ---------------------------------------------------------------------------


def test_pairmode_with_active_story(tmp_path):
    """Pairmode project with active story → status block includes story id."""
    _write_companion(
        tmp_path,
        state={
            "pairmode_version": "0.2.0",
            "current_story": {"id": "INFRA-042", "title": "test story"},
        },
        ctx={"project_name": "myproject"},
    )
    _write_era(tmp_path, "001")
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Pairmode active" in result.stdout
    assert "INFRA-042" in result.stdout
    assert "test story" in result.stdout


# ---------------------------------------------------------------------------
# Pairmode project — no story set
# ---------------------------------------------------------------------------


def test_pairmode_no_story(tmp_path):
    """Pairmode project with no current_story → 'none set' in output."""
    _write_companion(
        tmp_path,
        state={"pairmode_version": "0.2.0"},
        ctx={"project_name": "myproject"},
    )
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "Pairmode active" in result.stdout
    assert "none set" in result.stdout


# ---------------------------------------------------------------------------
# Helpers: fake flex dir with versioned SKILL.md
# ---------------------------------------------------------------------------


def _make_fake_flex(base: Path, version: str) -> Path:
    """Create a minimal fake flex directory with a SKILL.md containing *version*."""
    flex_dir = base / "fake_flex"
    skill_dir = flex_dir / "skills" / "pairmode"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: flex:pairmode\n---\n\npairmode_version: {version}\n",
        encoding="utf-8",
    )
    return flex_dir


# ---------------------------------------------------------------------------
# Canon sync status — flex found, versions match
# ---------------------------------------------------------------------------


def test_canon_sync_up_to_date(tmp_path):
    """flex found and versions match → 'up to date' in Canon sync line."""
    fake_flex = _make_fake_flex(tmp_path, "1.2.3")
    project = tmp_path / "project"
    project.mkdir()
    _write_companion(
        project,
        state={"pairmode_version": "1.2.3"},
        ctx={"project_name": "synctest"},
    )

    import os
    env = {**os.environ, "FLEX_DIR": str(fake_flex)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(project),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0
    assert "up to date" in result.stdout


# ---------------------------------------------------------------------------
# Canon sync status — flex found, versions differ
# ---------------------------------------------------------------------------


def test_canon_sync_behind(tmp_path):
    """flex found but project version is older → 'behind canon' in output."""
    fake_flex = _make_fake_flex(tmp_path, "9.9.9")
    project = tmp_path / "project"
    project.mkdir()
    _write_companion(
        project,
        state={"pairmode_version": "0.0.1"},
        ctx={"project_name": "behindtest"},
    )

    import os
    env = {**os.environ, "FLEX_DIR": str(fake_flex)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(project),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0
    assert "behind canon" in result.stdout


# ---------------------------------------------------------------------------
# Canon sync status — flex not found (unit test via direct import)
# ---------------------------------------------------------------------------


def test_canon_sync_flex_not_found(tmp_path, monkeypatch):
    """When _find_flex_dir returns None → canon sync message includes 'Set FLEX_DIR'."""
    import sys as _sys

    # Ensure the scripts dir is on the path so we can import the module.
    scripts_dir = str(REPO_ROOT / "skills" / "pairmode" / "scripts")
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)

    from skills.pairmode.scripts import global_session_check as gsc

    project = tmp_path / "project"
    project.mkdir()
    _write_companion(
        project,
        state={"pairmode_version": "0.2.0"},
        ctx={"project_name": "noflex"},
    )

    # Monkeypatch _find_flex_dir to return None
    monkeypatch.setattr(gsc, "_find_flex_dir", lambda: None)

    status = gsc._canon_sync_status(project)
    assert "Set FLEX_DIR" in status


# ---------------------------------------------------------------------------
# Graceful handling — git tag lookup failure
# ---------------------------------------------------------------------------


def test_git_tag_failure_graceful(tmp_path):
    """Exception during git describe → output still present, exit 0."""
    # Use a fake flex with a known version
    fake_flex = _make_fake_flex(tmp_path, "0.2.0")
    project = tmp_path / "project"
    project.mkdir()
    _write_companion(
        project,
        state={"pairmode_version": "0.2.0"},
        ctx={"project_name": "tagtest"},
    )

    # project dir is not a git repo → git describe will fail gracefully
    import os
    env = {**os.environ, "FLEX_DIR": str(fake_flex)}

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(project),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0
    # Status block should still be present even though git tag lookup failed
    assert "Pairmode active" in result.stdout
    # Last tag line should show the dash fallback
    assert "Last tag" in result.stdout
    assert "—" in result.stdout
