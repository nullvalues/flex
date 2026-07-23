"""
Structural tests for hook scripts.

Covers:
- session_end.py: direct state.json write removed (STATE_PATH constant gone,
  state_path.write_text no longer present in the hook)
- session_end.py: four state fields now included in the pipe event payload
- exit_plan_mode.py: direct state.json write removed (already covered in
  test_pipe_isolation.py; duplicated here for co-location)
- stop.py / session_end.py / exit_plan_mode.py: PIPE_PATH is the single
  hardcoded convention post_tool_use.py already used
  (``os.path.join(tempfile.gettempdir(), "companion.pipe")``); the
  ``pipe_path`` state.json key and its per-hook ``_resolve_pipe_path``
  validation helper were retired (INFRA-238) — the key was deleted by
  ``pairmode_migrate.py``'s ``to-030`` step and every hook that still read it
  was reading dead state.
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


# ── PIPE_PATH standardization (INFRA-238) ─────────────────────────────────────
#
# stop.py / session_end.py / exit_plan_mode.py previously each defined their
# own `_resolve_pipe_path(raw_path)` helper and read a `pipe_path` key out of
# `.companion/state.json` to override PIPE_PATH at import time. That key was
# deleted by `pairmode_migrate.py`'s `to-030` step, so every read was already
# dead — INFRA-238 retired the helper and the state read from all three
# hooks, standardizing on the single hardcoded convention post_tool_use.py
# established: `os.path.join(tempfile.gettempdir(), "companion.pipe")`.

HOOKS_WITH_STANDARDIZED_PIPE_PATH = [
    "stop.py",
    "session_end.py",
    "exit_plan_mode.py",
    "post_tool_use.py",
]


@pytest.mark.parametrize("hook_name", HOOKS_WITH_STANDARDIZED_PIPE_PATH)
def test_hook_pipe_path_is_hardcoded_tempdir_convention(hook_name):
    """Every listed hook's PIPE_PATH is the single hardcoded convention,
    independent of any state.json content."""
    module = _import_hook(hook_name)
    assert module.PIPE_PATH == os.path.join(tempfile.gettempdir(), "companion.pipe")


@pytest.mark.parametrize("hook_name", HOOKS_WITH_STANDARDIZED_PIPE_PATH)
def test_hook_source_does_not_read_pipe_path_key(hook_name):
    """No hook may read the retired `pipe_path` state.json key any longer.

    Prose comments are allowed to mention the retired key by name (for
    context); only the actual dict-access patterns are checked.
    """
    source = _read_hook_source(hook_name)
    forbidden = [
        '"pipe_path"]',
        "'pipe_path']",
        'get("pipe_path")',
        "get('pipe_path')",
    ]
    hits = [pattern for pattern in forbidden if pattern in source]
    assert not hits, (
        f"{hook_name} still reads the retired 'pipe_path' state.json key: {hits}"
    )


@pytest.mark.parametrize("hook_name", ["stop.py", "session_end.py", "exit_plan_mode.py"])
def test_hook_source_does_not_define_resolve_pipe_path(hook_name):
    """The per-hook `_resolve_pipe_path` validation helper was retired along
    with the state.json `pipe_path` key it validated."""
    source = _read_hook_source(hook_name)
    assert "_resolve_pipe_path" not in source, (
        f"{hook_name} still defines the retired _resolve_pipe_path helper"
    )


def test_exit_plan_mode_imports_and_runs_main_when_state_absent(tmp_path, monkeypatch):
    """Module imports and main() executes cleanly when .companion/state.json is absent."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    # No .companion/ directory or state.json at all.
    monkeypatch.chdir(project_dir)
    module = _import_hook("exit_plan_mode.py")

    assert module.PIPE_PATH == os.path.join(tempfile.gettempdir(), "companion.pipe")

    # main() reads from stdin; provide invalid JSON so the early `except` path
    # returns without exercising the pipe write. The function must not raise.
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    module.main()
