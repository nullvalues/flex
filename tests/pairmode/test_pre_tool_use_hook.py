"""Tests for hooks/pre_tool_use.py — thin PreToolUse delegate (INFRA-128).

All tests invoke the hook via subprocess.run to exercise the real script
end-to-end, matching the Claude Code hook execution contract.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "pre_tool_use.py"


def _run_hook(stdin_data: dict, cwd: Path | None = None) -> "subprocess.CompletedProcess[bytes]":  # noqa: F821
    """Run the hook with the given stdin JSON and return the completed process."""
    import subprocess
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(stdin_data).encode(),
        capture_output=True,
        cwd=str(cwd) if cwd else None,
    )


# ---------------------------------------------------------------------------
# Test 1: tool_name != "Task" → exit 0, empty stdout
# ---------------------------------------------------------------------------


def test_non_task_tool_exits_cleanly(tmp_path):
    """A hook call for a non-Task tool must exit 0 with empty stdout."""
    result = _run_hook({"tool_name": "Bash", "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# ---------------------------------------------------------------------------
# Test 2: tool_name == "Task" + decide() returns None → exit 0, empty stdout
# ---------------------------------------------------------------------------


def test_task_tool_no_block_exits_cleanly(tmp_path):
    """Task tool with decide() returning None → exit 0, empty stdout."""
    # No state.json → decide() returns None (state is absent → returns None).
    result = _run_hook({
        "tool_name": "Task",
        "cwd": str(tmp_path),
        "transcript_path": "",
    })
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# ---------------------------------------------------------------------------
# Test 3: tool_name == "Task" + decide() returns block → stdout is block JSON
# ---------------------------------------------------------------------------


def test_task_tool_block_emits_decision(tmp_path):
    """Task tool with decide() returning a block payload emits decision JSON."""
    # Write a state.json that will trigger a block:
    # current_tokens > threshold * 1.1 + expected_step_tokens forces a block.
    companion = tmp_path / ".companion"
    companion.mkdir()
    state = {
        "context_budget_threshold": 1000,
        "context_budget_overrun_pct": 0.0,
        "expected_step_tokens": 100,
        "context_budget_reprompt_margin": 0,
    }
    (companion / "state.json").write_text(json.dumps(state))

    # Write a transcript that reports 1200 input tokens (> 1000 + 100 = 1100).
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": 1200,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        }
    }) + "\n")

    result = _run_hook({
        "tool_name": "Task",
        "cwd": str(tmp_path),
        "transcript_path": str(transcript),
    })
    assert result.returncode == 0
    assert result.stdout.strip() != b""
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "reason" in payload
    assert len(payload["reason"]) > 0


# ---------------------------------------------------------------------------
# Test 4: context_budget import failure → exit 0, empty stdout
# ---------------------------------------------------------------------------


def test_import_failure_degrades_safely(tmp_path):
    """If context_budget cannot be imported, the hook exits 0 with empty stdout."""
    # Pass a cwd that has no scripts dir reachable via PLUGIN_ROOT — the hook
    # inserts PLUGIN_ROOT/skills/pairmode/scripts. We poison sys.modules by
    # passing cwd pointing at a tmpdir (no state.json so decide would return
    # None anyway), but we need to simulate the import actually failing.
    # Strategy: point cwd at a dir where no .companion/state.json exists AND
    # temporarily rename the module to simulate import failure by running the
    # hook with PYTHONPATH cleared and the scripts dir hidden.
    #
    # Simpler: run hook with tool_name=Task and a cwd that is a completely
    # different temp dir, then monkeypatch context_budget out via a wrapper
    # script. Actually, the cleanest approach per the spec is to call via
    # subprocess and rely on the hook's own try/except to absorb the error.
    # We simulate by writing a broken context_budget.py in a temp scripts dir
    # that raises on import, and we can't easily inject that via subprocess.
    #
    # Best approach: create a minimal wrapper that inserts a bad path and then
    # imports the hook. Instead, we test the degrade behavior by running the
    # real hook with an invalid PLUGIN_ROOT override — we can't do that without
    # modifying the hook. The spec says "simulate by temporarily removing the
    # scripts dir from sys.path before calling" — but that only works in-process.
    #
    # Per spec: call via subprocess.run. So we create a bad context_budget.py
    # in a temp dir and prepend that to sys.path by setting PYTHONPATH so the
    # hook picks it up before the real scripts dir. The real PLUGIN_ROOT insert
    # happens in the hook but PYTHONPATH is checked first by Python.
    import subprocess, os
    bad_scripts = tmp_path / "bad_scripts"
    bad_scripts.mkdir()
    (bad_scripts / "context_budget.py").write_text("raise ImportError('simulated failure')\n")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(bad_scripts)

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"tool_name": "Task", "cwd": str(tmp_path), "transcript_path": ""}).encode(),
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# ---------------------------------------------------------------------------
# Test 5: decide() raises → exit 0, empty stdout
# ---------------------------------------------------------------------------


def test_decide_raises_degrades_safely(tmp_path):
    """If decide() raises an exception, the hook exits 0 with empty stdout."""
    import subprocess, os
    bad_scripts = tmp_path / "bad_scripts"
    bad_scripts.mkdir()
    # context_budget imports fine but decide() raises.
    (bad_scripts / "context_budget.py").write_text(
        "def decide(*args, **kwargs):\n    raise RuntimeError('simulated error')\n"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(bad_scripts)

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"tool_name": "Task", "cwd": str(tmp_path), "transcript_path": ""}).encode(),
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# ---------------------------------------------------------------------------
# Test 6: Performance — 100 runs where decide() returns None < 5 seconds total
# ---------------------------------------------------------------------------


def test_performance_100_runs_under_5_seconds(tmp_path):
    """100 hook invocations (decide returns None) must complete in under 5 seconds."""
    # No state.json → decide returns None → pass-through.
    stdin_data = json.dumps({"tool_name": "Task", "cwd": str(tmp_path), "transcript_path": ""}).encode()
    import subprocess
    start = time.monotonic()
    for _ in range(100):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=stdin_data,
            capture_output=True,
        )
        assert result.returncode == 0
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"100 hook runs took {elapsed:.2f}s (limit: 5s)"
