"""
Tests for skills/observability/scripts/flex_observability.py

Uses subprocess to invoke the CLI directly so we exercise the full Click entry
point (including sys.exit codes) without needing to mock Click internals.

Registry path is overridden via FLEX_OBS_REGISTRY_PATH env var so tests never
touch ~/.config/flex-observability/registry.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).parent.parent.parent / "skills" / "observability" / "scripts" / "flex_observability.py"
)


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def tmp_registry(tmp_path):
    """Return an env dict that redirects the registry to a tmp file."""
    reg_file = tmp_path / "registry.json"
    env = os.environ.copy()
    env["FLEX_OBS_REGISTRY_PATH"] = str(reg_file)
    return env, reg_file


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


def test_register_adds_entry(tmp_registry):
    env, reg_file = tmp_registry
    result = _run("register", "--project-dir", "/mnt/work/flex", env=env)
    assert result.returncode == 0, result.stderr
    data = json.loads(reg_file.read_text())
    assert len(data["repos"]) == 1
    entry = data["repos"][0]
    assert entry["id"] == "flex"
    assert entry["project_dir"] == "/mnt/work/flex"


def test_register_idempotent(tmp_registry):
    env, reg_file = tmp_registry
    _run("register", "--project-dir", "/mnt/work/flex", env=env)
    result = _run("register", "--project-dir", "/mnt/work/flex", env=env)
    assert result.returncode == 0
    assert "already registered" in result.stdout
    data = json.loads(reg_file.read_text())
    assert len(data["repos"]) == 1


def test_register_depth_guard(tmp_registry):
    env, _ = tmp_registry
    result = _run("register", "--project-dir", "/a/b", env=env)
    assert result.returncode == 1


def test_register_custom_name_and_color(tmp_registry):
    env, reg_file = tmp_registry
    result = _run(
        "register",
        "--project-dir", "/mnt/work/flex",
        "--name", "myrepo",
        "--color", "#aabbcc",
        env=env,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(reg_file.read_text())
    entry = data["repos"][0]
    assert entry["id"] == "myrepo"
    assert entry["color"] == "#aabbcc"


# ---------------------------------------------------------------------------
# unregister
# ---------------------------------------------------------------------------


def test_unregister_removes_entry(tmp_registry):
    env, reg_file = tmp_registry
    _run("register", "--project-dir", "/mnt/work/flex", env=env)
    result = _run("unregister", "--project-dir", "/mnt/work/flex", env=env)
    assert result.returncode == 0, result.stderr
    data = json.loads(reg_file.read_text())
    assert data["repos"] == []


def test_unregister_not_registered(tmp_registry):
    env, _ = tmp_registry
    result = _run("unregister", "--project-dir", "/mnt/work/flex", env=env)
    assert result.returncode == 0
    assert "not registered" in result.stdout


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_empty(tmp_registry):
    env, _ = tmp_registry
    result = _run("list", env=env)
    assert result.returncode == 0
    assert "No repos registered." in result.stdout


def test_list_shows_entries(tmp_registry):
    env, _ = tmp_registry
    _run("register", "--project-dir", "/mnt/work/flex", "--name", "flex", env=env)
    _run("register", "--project-dir", "/mnt/work/forqsite", "--name", "forqsite", env=env)
    result = _run("list", env=env)
    assert result.returncode == 0
    assert "flex" in result.stdout
    assert "/mnt/work/flex" in result.stdout
    assert "forqsite" in result.stdout
    assert "/mnt/work/forqsite" in result.stdout
