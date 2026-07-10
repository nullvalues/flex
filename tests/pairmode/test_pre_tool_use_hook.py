"""Tests for hooks/pre_tool_use.py — thin PreToolUse delegate (INFRA-128).

INFRA-148: token-source contract changed from transcript JSONL parsing to
``state.json["context_current_tokens"]``. Transcript fixtures replaced with
state seeding.

INFRA-176 (CER-049): the dispatcher now accepts both ``Task`` and ``Agent``
as the agent-spawn tool name. Parametrized cases assert identical block/pass
behavior under either name.

All tests invoke the hook via subprocess.run to exercise the real script
end-to-end, matching the Claude Code hook execution contract.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

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


def _seed_state(tmp_path: Path, state: dict) -> None:
    """Write state.json to tmp_path/.companion/state.json."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: tool_name != "Task" → exit 0, empty stdout
# ---------------------------------------------------------------------------


def test_non_task_tool_exits_cleanly(tmp_path):
    """A hook call for a non-Task tool must exit 0 with empty stdout."""
    result = _run_hook({"tool_name": "Bash", "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# ---------------------------------------------------------------------------
# Test 2: agent-spawn tool + tokens below ceiling → exit 0, empty stdout
# Parametrized over Task / Agent (INFRA-176 / CER-049).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spawn_tool", ["Task", "Agent"])
def test_spawn_tool_no_block_exits_cleanly(tmp_path, spawn_tool):
    """Agent-spawn tool with current tokens under ceiling → exit 0, empty stdout."""
    _seed_state(
        tmp_path,
        {
            "context_budget_threshold": 1000,
            "context_budget_overrun_pct": 0.0,
            "expected_step_tokens": 100,
            "context_budget_reprompt_margin": 0,
            "context_current_tokens": 500,
        },
    )
    result = _run_hook({"tool_name": spawn_tool, "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# ---------------------------------------------------------------------------
# Test 3: agent-spawn tool + tokens above ceiling → stdout is block JSON
# Parametrized over Task / Agent (INFRA-176 / CER-049).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spawn_tool", ["Task", "Agent"])
def test_spawn_tool_block_emits_decision(tmp_path, spawn_tool):
    """Agent-spawn tool with current tokens above ceiling emits decision JSON."""
    _seed_state(
        tmp_path,
        {
            "context_budget_threshold": 1000,
            "context_budget_overrun_pct": 0.0,
            "expected_step_tokens": 100,
            "context_budget_reprompt_margin": 0,
            "context_current_tokens": 1200,
        },
    )
    result = _run_hook({"tool_name": spawn_tool, "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() != b""
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "reason" in payload
    assert len(payload["reason"]) > 0
    assert "CONTEXT BUDGET" in payload["reason"]


# ---------------------------------------------------------------------------
# Test 3b (INFRA-148): agent-spawn tool with no context_current_tokens
# in state.json → block with CONTEXT CHECK REQUIRED. Parametrized over
# Task / Agent (INFRA-176 / CER-049).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spawn_tool", ["Task", "Agent"])
def test_spawn_tool_block_when_no_context_tokens_recorded(tmp_path, spawn_tool):
    """state.json exists but lacks context_current_tokens → block CHECK REQUIRED."""
    _seed_state(
        tmp_path,
        {
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
        },
    )
    result = _run_hook({"tool_name": spawn_tool, "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() != b""
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "CONTEXT CHECK REQUIRED" in payload["reason"]


# ---------------------------------------------------------------------------
# Test 4: context_budget import failure → exit 0, empty stdout
# ---------------------------------------------------------------------------


def test_import_failure_degrades_safely(tmp_path):
    """If context_budget cannot be imported, the hook exits 0 with empty stdout."""
    import subprocess, os
    bad_scripts = tmp_path / "bad_scripts"
    bad_scripts.mkdir()
    (bad_scripts / "context_budget.py").write_text("raise ImportError('simulated failure')\n")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(bad_scripts)

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"tool_name": "Task", "cwd": str(tmp_path)}).encode(),
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
        input=json.dumps({"tool_name": "Task", "cwd": str(tmp_path)}).encode(),
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# ---------------------------------------------------------------------------
# Test 6: Performance — 100 runs where decide() returns None < 5 seconds total
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test 7 (INFRA-193): user-turn acknowledgment gate
# ---------------------------------------------------------------------------


def test_bare_retry_without_user_turn_blocks_again(tmp_path):
    """External-report repro: tokens over ceiling, acknowledged_at ==
    context_current_tokens, and no intervening UserPromptSubmit event
    (acknowledged_user_turn_seq == user_turn_seq) → still blocked, not
    silently suppressed.

    NOTE: overrun_pct and reprompt_margin are intentionally non-zero here —
    ``decide()``'s ``state.get(key, default) or default`` reads treat an
    explicit ``0``/``0.0`` in state.json as falsy and silently substitute
    the default, a pre-existing quirk unrelated to this story; using
    non-zero values keeps this test's assertions independent of that quirk.
    """
    _seed_state(
        tmp_path,
        {
            "context_budget_threshold": 1000,
            "context_budget_overrun_pct": 0.5,
            "expected_step_tokens": 10,
            "context_budget_reprompt_margin": 100,
            "context_current_tokens": 1600,
            "context_budget_acknowledged_at": 1600,
            "context_budget_user_turn_seq": 2,
            "context_budget_acknowledged_user_turn_seq": 2,
        },
    )
    result = _run_hook({"tool_name": "Task", "cwd": str(tmp_path)})
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"


def test_retry_after_user_prompt_submit_suppresses(tmp_path):
    """A genuine UserPromptSubmit event since the block (user_turn_seq
    incremented past acknowledged_user_turn_seq) with the token margin
    satisfied → suppressed (empty stdout)."""
    _seed_state(
        tmp_path,
        {
            "context_budget_threshold": 1000,
            "context_budget_overrun_pct": 0.5,
            "expected_step_tokens": 10,
            "context_budget_reprompt_margin": 100,
            "context_current_tokens": 1700,
            "context_budget_acknowledged_at": 1600,
            "context_budget_user_turn_seq": 3,
            "context_budget_acknowledged_user_turn_seq": 2,
        },
    )
    result = _run_hook({"tool_name": "Task", "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_performance_100_runs_under_5_seconds(tmp_path):
    """100 hook invocations (decide returns None) must complete in under 5 seconds."""
    # No state.json → decide returns None → pass-through.
    stdin_data = json.dumps({"tool_name": "Task", "cwd": str(tmp_path)}).encode()
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
    assert elapsed < 15.0, f"100 hook runs took {elapsed:.2f}s (limit: 15s)"
