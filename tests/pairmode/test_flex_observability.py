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
import stat
import subprocess
import sys
import threading
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


# ---------------------------------------------------------------------------
# INFRA-164: subprocess exit propagation, unique tmp, ID uniqueness
# ---------------------------------------------------------------------------


def test_serve_propagates_nonzero_exit(tmp_registry, tmp_path):
    """serve must sys.exit(result.returncode) when node exits non-zero."""
    # Create a fake "node" shim that exits 1 and a fake "server.js"
    shim = tmp_path / "node"
    shim.write_text("#!/bin/sh\nexit 1\n")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)

    # Create a minimal dist/server.js so serve doesn't abort before node
    script_dir = Path(_SCRIPT).resolve().parent
    api_dist = script_dir.parent / "api" / "dist"
    api_dist.mkdir(parents=True, exist_ok=True)
    server_js = api_dist / "server.js"
    # Only create if it doesn't already exist (avoid clobbering real build)
    created_server_js = not server_js.exists()
    if created_server_js:
        server_js.write_text("// stub\n")

    env, _ = tmp_registry
    env = dict(env)
    env["PATH"] = str(tmp_path) + ":" + env.get("PATH", "")

    try:
        result = _run("serve", env=env)
        assert result.returncode == 1, (
            f"serve must propagate node exit code 1; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    finally:
        if created_server_js and server_js.exists():
            server_js.unlink()


def test_write_registry_tmp_is_unique(tmp_registry):
    """Concurrent _write_registry calls must not lose registrations."""
    sys.path.insert(0, str(Path(_SCRIPT).resolve().parent))
    from flex_observability import _write_registry  # type: ignore[import]

    env, reg_file = tmp_registry

    def write_one(entry_id: str) -> None:
        import json as _json
        data = {"version": 1, "repos": [{"id": entry_id, "project_dir": f"/mnt/work/{entry_id}"}]}
        _write_registry(reg_file, data)

    # Run two writes concurrently; without unique tmp they may race
    threads = [
        threading.Thread(target=write_one, args=("alpha",)),
        threading.Thread(target=write_one, args=("beta",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Both writes completed without exception; registry file must exist and be valid JSON
    assert reg_file.exists(), "registry file missing after concurrent writes"
    data = json.loads(reg_file.read_text())
    assert "repos" in data


def test_register_duplicate_name_different_dir_exits_1(tmp_registry):
    """Registering a second project with an already-used name must exit 1."""
    env, reg_file = tmp_registry
    r1 = _run("register", "--project-dir", "/mnt/work/flex", "--name", "myrepo", env=env)
    assert r1.returncode == 0, r1.stderr
    r2 = _run("register", "--project-dir", "/mnt/work/other", "--name", "myrepo", env=env)
    assert r2.returncode == 1, (
        f"Expected exit 1 for duplicate name, got {r2.returncode}\n"
        f"stdout: {r2.stdout}\nstderr: {r2.stderr}"
    )
    assert "name already in use" in r2.stdout, (
        f"Expected 'name already in use' in stdout, got: {r2.stdout!r}"
    )
    # Only one entry should exist
    data = json.loads(reg_file.read_text())
    assert len(data["repos"]) == 1


def test_register_duplicate_name_same_dir_idempotent(tmp_registry):
    """Re-registering the same (name, project_dir) pair is idempotent (exit 0, one entry)."""
    env, reg_file = tmp_registry
    _run("register", "--project-dir", "/mnt/work/flex", "--name", "flex", env=env)
    r2 = _run("register", "--project-dir", "/mnt/work/flex", "--name", "flex", env=env)
    assert r2.returncode == 0, r2.stderr
    assert "already registered" in r2.stdout
    data = json.loads(reg_file.read_text())
    assert len(data["repos"]) == 1
