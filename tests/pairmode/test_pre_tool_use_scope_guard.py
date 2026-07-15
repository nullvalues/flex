"""Tests for hooks/pre_tool_use.py Edit/Write → scope_guard dispatch (INFRA-139).

These tests load the hook module in-process and patch sys.stdin/sys.stdout
to drive its `main()` function, mocking `scope_guard.check_path` to avoid
needing a real project tree.
"""
from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "pre_tool_use.py"
SCRIPTS_DIR = REPO_ROOT / "skills" / "pairmode" / "scripts"

# Put the pairmode scripts dir on sys.path so test bodies can
# `import scope_guard` / `import context_budget` to patch their attributes.
# The hook itself also inserts this path on module load.
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_hook_module():
    """Load hooks/pre_tool_use.py as a fresh module each call."""
    # Drop any cached copy so the hook re-imports cleanly each test.
    sys.modules.pop("pre_tool_use_hook_under_test", None)

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "pre_tool_use_hook_under_test", str(HOOK_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(stdin_payload: dict) -> tuple[int, str]:
    """Invoke hook.main() with crafted stdin; return (exit_code, stdout_text)."""
    hook = _load_hook_module()

    stdin_buf = io.StringIO(json.dumps(stdin_payload))
    stdout_buf = io.StringIO()

    exit_code = 0
    with patch.object(sys, "stdin", stdin_buf), patch.object(sys, "stdout", stdout_buf):
        try:
            hook.main()
        except SystemExit as e:
            exit_code = int(e.code) if e.code is not None else 0
    return exit_code, stdout_buf.getvalue()


# ---------------------------------------------------------------------------
# Test 1: Edit allowed → no block emitted
# ---------------------------------------------------------------------------


def test_edit_allowed_path_does_not_block(tmp_path):
    """check_path returning (True, 'allowed') produces no stdout output."""
    import scope_guard  # already on sys.path via _load_hook_module path setup

    with patch.object(scope_guard, "check_path", return_value=(True, "allowed")):
        exit_code, stdout = _run_main({
            "tool_name": "Edit",
            "tool_input": {"file_path": "foo.py"},
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    assert stdout.strip() == ""


# ---------------------------------------------------------------------------
# Test 2: Edit blocked → block JSON emitted
# ---------------------------------------------------------------------------


def test_edit_blocked_path_emits_block(tmp_path):
    """check_path returning (False, reason) emits a decision:block JSON payload."""
    import scope_guard

    with patch.object(scope_guard, "check_path", return_value=(False, "not in story scope")):
        exit_code, stdout = _run_main({
            "tool_name": "Edit",
            "tool_input": {"file_path": "foo.py"},
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    payload = json.loads(stdout.strip())
    assert payload == {"decision": "block", "reason": "not in story scope"}


# ---------------------------------------------------------------------------
# Test 3: Write blocked → block JSON emitted
# ---------------------------------------------------------------------------


def test_write_blocked_path_emits_block(tmp_path):
    """Same as Edit-blocked but for the Write tool name."""
    import scope_guard

    with patch.object(scope_guard, "check_path", return_value=(False, "not in story scope")):
        exit_code, stdout = _run_main({
            "tool_name": "Write",
            "tool_input": {"file_path": "bar.py"},
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    payload = json.loads(stdout.strip())
    assert payload == {"decision": "block", "reason": "not in story scope"}


# ---------------------------------------------------------------------------
# Test 4: scope_guard.check_path raises → fail open (no block)
# ---------------------------------------------------------------------------


def test_scope_guard_exception_fails_open(tmp_path):
    """If check_path raises, the hook must exit cleanly without blocking."""
    import scope_guard

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated scope_guard failure")

    with patch.object(scope_guard, "check_path", side_effect=_raise):
        exit_code, stdout = _run_main({
            "tool_name": "Edit",
            "tool_input": {"file_path": "foo.py"},
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    assert stdout.strip() == ""


# ---------------------------------------------------------------------------
# Test 5: Task branch unaffected — scope_guard.check_path is not called
# ---------------------------------------------------------------------------


def test_task_branch_unaffected(tmp_path):
    """A Task tool dispatch must not invoke scope_guard.check_path."""
    import scope_guard
    import context_budget

    # context_budget.decide returns a non-block result.
    with patch.object(context_budget, "decide", return_value=None) as mock_decide, \
         patch.object(scope_guard, "check_path") as mock_check:
        exit_code, stdout = _run_main({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "builder"},
            "cwd": str(tmp_path),
            "transcript_path": "",
        })

    assert exit_code == 0
    assert stdout.strip() == ""
    assert mock_check.called is False
    assert mock_decide.called is True


# ---------------------------------------------------------------------------
# Test 6: Unknown tool name exits cleanly
# ---------------------------------------------------------------------------


def test_unknown_tool_name_exits_cleanly(tmp_path):
    """tool_name=Bash (not Task/Edit/Write) exits 0 with no output."""
    import scope_guard
    import context_budget

    with patch.object(scope_guard, "check_path") as mock_check, \
         patch.object(context_budget, "decide") as mock_decide:
        exit_code, stdout = _run_main({
            "tool_name": "Bash",
            "cwd": str(tmp_path),
        })

    assert exit_code == 0
    assert stdout.strip() == ""
    assert mock_check.called is False
    assert mock_decide.called is False
