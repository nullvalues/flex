"""
Structural tests for hook scripts.

Covers:
- session_end.py: direct state.json write removed (STATE_PATH constant gone,
  state_path.write_text no longer present in the hook)
- session_end.py: four state fields now included in the pipe event payload
- exit_plan_mode.py: direct state.json write removed (already covered in
  test_pipe_isolation.py; duplicated here for co-location)
- stop.py / post_tool_use.py / session_end.py: PIPE_PATH validation against
  the system tempdir via the _resolve_pipe_path helper (CER-009).
"""
import importlib.util
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _read_hook_source(hook_name: str) -> str:
    """Read the source of a hook file relative to the repo root."""
    hook_path = REPO_ROOT / "hooks" / hook_name
    return hook_path.read_text(encoding="utf-8")


def _import_hook(hook_name: str):
    """Import a hook module dynamically by file path.

    Hooks live outside the python package layout (no __init__.py) so we use
    importlib's file-loader to bring them in for direct unit testing of
    helpers like ``_resolve_pipe_path``.
    """
    hook_path = REPO_ROOT / "hooks" / hook_name
    # Use a unique module name per import to avoid the module-cache returning
    # a stale copy from a previous test (the hook's module-level state.json
    # read runs once on import).
    mod_name = f"_hook_under_test_{hook_path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(mod_name, hook_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# ── session_end.py structural checks ─────────────────────────────────────────

def test_session_end_does_not_define_state_path_constant():
    """session_end.py must not define STATE_PATH (direct state write removed)."""
    source = _read_hook_source("session_end.py")
    assert "STATE_PATH" not in source, (
        "session_end.py still defines STATE_PATH — direct state write must be removed"
    )


def test_session_end_does_not_write_state_json_directly():
    """session_end.py must not call state_path.write_text (direct write removed)."""
    source = _read_hook_source("session_end.py")
    assert "state_path.write_text" not in source, (
        "session_end.py still calls state_path.write_text — direct state write must be removed"
    )


def test_session_end_includes_last_session_end_in_pipe_event():
    """session_end.py must emit last_session_end in the pipe event payload."""
    source = _read_hook_source("session_end.py")
    assert "last_session_end" in source, (
        "session_end.py does not contain 'last_session_end' — field must be in pipe event"
    )


def test_session_end_includes_last_session_closed_in_pipe_event():
    """session_end.py must emit last_session_closed in the pipe event payload."""
    source = _read_hook_source("session_end.py")
    assert "last_session_closed" in source, (
        "session_end.py does not contain 'last_session_closed' — field must be in pipe event"
    )


# ── _resolve_pipe_path validation (CER-009) ──────────────────────────────────
#
# Each of stop.py / post_tool_use.py / session_end.py exposes the same helper
# function `_resolve_pipe_path(raw_path) -> str | None` which validates that a
# pipe_path read from .companion/state.json resolves under tempfile.gettempdir().
# Out-of-bounds or malformed paths return None so the caller keeps the legacy
# "/tmp/companion.pipe" fallback.

HOOKS_WITH_PIPE_VALIDATION = [
    "stop.py",
    "post_tool_use.py",
    "session_end.py",
    "exit_plan_mode.py",
]


@pytest.mark.parametrize("hook_name", HOOKS_WITH_PIPE_VALIDATION)
def test_resolve_pipe_path_accepts_path_under_tempdir(hook_name, tmp_path, monkeypatch):
    """A pipe path that resolves under tempfile.gettempdir() is accepted."""
    # Use the test's tmp_path as gettempdir so we can write a real file under it.
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    candidate = tmp_path / "companion-abc12345.pipe"

    module = _import_hook(hook_name)
    # Reuse the test-time tempdir override inside the imported module.
    module.tempfile.gettempdir = lambda: str(tmp_path)  # type: ignore[attr-defined]

    result = module._resolve_pipe_path(str(candidate))
    assert result == str(candidate.resolve())


@pytest.mark.parametrize("hook_name", HOOKS_WITH_PIPE_VALIDATION)
def test_resolve_pipe_path_rejects_path_outside_tempdir(hook_name):
    """A pipe path outside tempfile.gettempdir() (e.g. /etc/passwd) returns None."""
    module = _import_hook(hook_name)
    # /etc is not under any system tempdir on supported platforms.
    assert module._resolve_pipe_path("/etc/passwd") is None


@pytest.mark.parametrize("hook_name", HOOKS_WITH_PIPE_VALIDATION)
def test_resolve_pipe_path_rejects_malformed_path(hook_name):
    """A malformed path string returns None (caller keeps fallback)."""
    module = _import_hook(hook_name)
    # NUL bytes are rejected by Path.resolve on every platform — exercises the
    # broad except in the helper.
    assert module._resolve_pipe_path("/tmp/\x00bad") is None


@pytest.mark.parametrize("hook_name", HOOKS_WITH_PIPE_VALIDATION)
def test_resolve_pipe_path_rejects_non_string_input(hook_name):
    """Non-string (e.g. int) inputs do not raise — they return None."""
    module = _import_hook(hook_name)
    # Path(int) raises TypeError; the helper's broad except must absorb it.
    assert module._resolve_pipe_path(12345) is None  # type: ignore[arg-type]


@pytest.mark.parametrize("hook_name", HOOKS_WITH_PIPE_VALIDATION)
def test_hook_source_contains_resolve_pipe_path(hook_name):
    """Every PIPE_PATH-validating hook must define the _resolve_pipe_path helper."""
    source = _read_hook_source(hook_name)
    assert "_resolve_pipe_path" in source, (
        f"{hook_name} is missing the _resolve_pipe_path helper required by CER-009"
    )
    assert "tempfile.gettempdir" in source, (
        f"{hook_name} must validate pipe_path against tempfile.gettempdir()"
    )


# ── exit_plan_mode.py PIPE_PATH containment (CER-020 / INFRA-068) ────────────
#
# These tests exercise the module-level state.json read in exit_plan_mode.py
# end-to-end: write a crafted .companion/state.json, import the hook, and
# inspect the resulting PIPE_PATH constant.


def _write_state_json(project_dir: Path, pipe_path_value):
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state_file = companion_dir / "state.json"
    import json as _json
    state_file.write_text(_json.dumps({"pipe_path": pipe_path_value}))
    return state_file


def test_exit_plan_mode_rejects_pipe_path_outside_tempdir(tmp_path, monkeypatch):
    """A state.json with pipe_path outside tempdir does NOT override PIPE_PATH."""
    # cwd switch so the hook's relative open(".companion/state.json") resolves
    # inside the test's tmp_path.
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_state_json(project_dir, "/etc/evil.pipe")

    monkeypatch.chdir(project_dir)
    module = _import_hook("exit_plan_mode.py")

    # The legacy fallback under the system tempdir must still be in force.
    assert module.PIPE_PATH != "/etc/evil.pipe"
    assert module.PIPE_PATH == os.path.join(tempfile.gettempdir(), "companion.pipe")


def test_exit_plan_mode_accepts_pipe_path_inside_tempdir(tmp_path, monkeypatch):
    """A state.json with pipe_path inside tempdir is accepted and overrides PIPE_PATH."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    # The candidate must live under the real system tempdir so the helper's
    # is_relative_to(tempfile.gettempdir()) check passes.
    real_tmp = Path(tempfile.gettempdir()).resolve()
    candidate = real_tmp / f"companion-test-{uuid.uuid4().hex}.pipe"
    _write_state_json(project_dir, str(candidate))

    monkeypatch.chdir(project_dir)
    module = _import_hook("exit_plan_mode.py")

    assert module.PIPE_PATH == str(candidate.resolve())


def test_exit_plan_mode_imports_and_runs_main_when_state_absent(tmp_path, monkeypatch):
    """Module imports and main() executes cleanly when .companion/state.json is absent."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    # No .companion/ directory or state.json at all.
    monkeypatch.chdir(project_dir)
    module = _import_hook("exit_plan_mode.py")

    # PIPE_PATH falls back to the system tempdir default.
    assert module.PIPE_PATH == os.path.join(tempfile.gettempdir(), "companion.pipe")

    # main() reads from stdin; provide invalid JSON so the early `except` path
    # returns without exercising the pipe write. The function must not raise.
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    module.main()
