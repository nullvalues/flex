"""Tests for pairmode_register.py — register/unregister/list-projects commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.pairmode_register import (
    register,
    unregister,
    list_projects,
    _depth_guard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _companion_dir_arg(tmp_path: Path) -> str:
    """Return the string companion dir path to pass via --companion-dir."""
    return str(tmp_path / ".companion")


def _state(tmp_path: Path) -> dict:
    """Read state.json from the isolated companion dir."""
    state_path = tmp_path / ".companion" / "state.json"
    return json.loads(state_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tests: register
# ---------------------------------------------------------------------------


def test_register_adds_path(tmp_path: Path) -> None:
    """register adds the resolved absolute path to registered_projects."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    result = runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])

    assert result.exit_code == 0, result.output
    state = _state(tmp_path)
    assert str(Path(project).resolve()) in state["registered_projects"]


def test_register_idempotent(tmp_path: Path) -> None:
    """register called twice with the same path prints 'already registered' and does not duplicate."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    result1 = runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])
    assert result1.exit_code == 0, result1.output

    result2 = runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])
    assert result2.exit_code == 0, result2.output
    assert "already registered" in result2.output

    state = _state(tmp_path)
    registered = state["registered_projects"]
    resolved_str = str(Path(project).resolve())
    assert registered.count(resolved_str) == 1, "path should appear exactly once"


# ---------------------------------------------------------------------------
# Tests: unregister
# ---------------------------------------------------------------------------


def test_unregister_removes_path(tmp_path: Path) -> None:
    """unregister removes a previously registered path."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    runner.invoke(register, ["--project-dir", project, "--companion-dir", cdir])

    result = runner.invoke(unregister, ["--project-dir", project, "--companion-dir", cdir])
    assert result.exit_code == 0, result.output

    state = _state(tmp_path)
    assert str(Path(project).resolve()) not in state.get("registered_projects", [])


def test_unregister_noop_when_not_registered(tmp_path: Path) -> None:
    """unregister is a no-op when the path is not present — prints 'not registered'."""
    runner = CliRunner()
    project = str(tmp_path / "a" / "b" / "myproject")
    cdir = _companion_dir_arg(tmp_path)

    result = runner.invoke(unregister, ["--project-dir", project, "--companion-dir", cdir])
    assert result.exit_code == 0, result.output
    assert "not registered" in result.output


# ---------------------------------------------------------------------------
# Tests: list-projects
# ---------------------------------------------------------------------------


def test_list_projects_empty(tmp_path: Path) -> None:
    """list-projects prints 'No projects registered.' when state is absent or empty."""
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)

    result = runner.invoke(list_projects, ["--companion-dir", cdir])
    assert result.exit_code == 0, result.output
    assert "No projects registered." in result.output


def test_list_projects_shows_all(tmp_path: Path) -> None:
    """list-projects prints all registered paths, one per line."""
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)

    project_a = str(tmp_path / "a" / "b" / "proj_a")
    project_b = str(tmp_path / "x" / "y" / "proj_b")

    runner.invoke(register, ["--project-dir", project_a, "--companion-dir", cdir])
    runner.invoke(register, ["--project-dir", project_b, "--companion-dir", cdir])

    result = runner.invoke(list_projects, ["--companion-dir", cdir])
    assert result.exit_code == 0, result.output

    output_lines = result.output.strip().splitlines()
    assert str(Path(project_a).resolve()) in output_lines
    assert str(Path(project_b).resolve()) in output_lines
    assert len(output_lines) == 2


# ---------------------------------------------------------------------------
# Tests: atomic write / JSON validity
# ---------------------------------------------------------------------------


def test_state_is_valid_json_after_operations(tmp_path: Path) -> None:
    """state.json is valid JSON after a register + unregister sequence."""
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)

    project_a = str(tmp_path / "a" / "b" / "proj_a")
    project_b = str(tmp_path / "x" / "y" / "proj_b")

    runner.invoke(register, ["--project-dir", project_a, "--companion-dir", cdir])
    runner.invoke(register, ["--project-dir", project_b, "--companion-dir", cdir])
    runner.invoke(unregister, ["--project-dir", project_a, "--companion-dir", cdir])

    state = _state(tmp_path)  # raises if not valid JSON
    assert isinstance(state, dict)
    remaining = state.get("registered_projects", [])
    assert str(Path(project_b).resolve()) in remaining
    assert str(Path(project_a).resolve()) not in remaining


# ---------------------------------------------------------------------------
# Tests: _depth_guard
# ---------------------------------------------------------------------------


def test_depth_guard_rejects_shallow_path(tmp_path: Path) -> None:
    """register exits with an error when the resolved project-dir has fewer than 3 parts."""
    runner = CliRunner()
    cdir = _companion_dir_arg(tmp_path)

    # /tmp has exactly 2 parts on Linux: ('/', 'tmp')
    result = runner.invoke(register, ["--project-dir", "/tmp", "--companion-dir", cdir])
    assert result.exit_code != 0
    assert "suspicious" in result.output or "suspicious" in (result.stderr or "")


def test_depth_guard_unit() -> None:
    """_depth_guard returns False for shallow paths and True for deep ones."""
    assert _depth_guard(Path("/tmp")) is False          # 2 parts: ('/', 'tmp')
    assert _depth_guard(Path("/a")) is False            # 2 parts: ('/', 'a')
    assert _depth_guard(Path("/a/b/c")) is True         # 4 parts
    assert _depth_guard(Path("/home/user/project")) is True  # 4 parts
