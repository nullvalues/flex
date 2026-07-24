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
    result = _run_hook({
        "tool_name": spawn_tool,
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    })
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
    result = _run_hook({
        "tool_name": spawn_tool,
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    })
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
    result = _run_hook({
        "tool_name": spawn_tool,
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    })
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
        input=json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "builder"},
            "cwd": str(tmp_path),
        }).encode(),
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
        input=json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "builder"},
            "cwd": str(tmp_path),
        }).encode(),
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
    result = _run_hook({
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    })
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
    result = _run_hook({
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    })
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# ---------------------------------------------------------------------------
# Test 8 (INFRA-196): Read dispatch → cold_read_guard.check_path
# ---------------------------------------------------------------------------


def test_read_orchestrator_story_path_blocks(tmp_path):
    """Read of docs/stories/** with no agent_type key (orchestrator) blocks."""
    result = _run_hook({
        "tool_name": "Read",
        "tool_input": {"file_path": "docs/stories/INFRA/INFRA-196.md"},
        "cwd": str(tmp_path),
    })
    assert result.returncode == 0
    assert result.stdout.strip() != b""
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "reason" in payload


def test_read_subagent_story_path_allowed(tmp_path):
    """Read of docs/stories/** WITH an agent_type key (subagent) does not block."""
    result = _run_hook({
        "tool_name": "Read",
        "tool_input": {"file_path": "docs/stories/INFRA/INFRA-196.md"},
        "cwd": str(tmp_path),
        "agent_type": "builder",
    })
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_read_unrelated_path_allowed(tmp_path):
    """Read of an unrelated path never blocks, agent_type absent or not."""
    result = _run_hook({
        "tool_name": "Read",
        "tool_input": {"file_path": "docs/phases/phase-1.md"},
        "cwd": str(tmp_path),
    })
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_performance_100_runs_under_5_seconds(tmp_path):
    """100 hook invocations (decide returns None) must complete in under 5 seconds."""
    # No state.json → decide returns None → pass-through.
    stdin_data = json.dumps({
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    }).encode()
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


# ---------------------------------------------------------------------------
# Test 9 (INFRA-199): subagent_type allowlist gate on the Task/Agent branch.
# ---------------------------------------------------------------------------


_OVER_CEILING_STATE = {
    "context_budget_threshold": 1000,
    "context_budget_overrun_pct": 0.0,
    "expected_step_tokens": 100,
    "context_budget_reprompt_margin": 0,
    "context_current_tokens": 1200,
}


@pytest.mark.parametrize(
    "subagent_type",
    ["builder", "loop-breaker", "security-auditor", "intent-reviewer"],
)
def test_allowlisted_subagent_type_still_gates(tmp_path, subagent_type):
    """Each build-cycle subagent type over the ceiling still emits a block."""
    _seed_state(tmp_path, dict(_OVER_CEILING_STATE))
    result = _run_hook({
        "tool_name": "Task",
        "tool_input": {"subagent_type": subagent_type},
        "cwd": str(tmp_path),
    })
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "CONTEXT BUDGET" in payload["reason"]


@pytest.mark.parametrize("spawn_tool", ["Task", "Agent"])
def test_allowlisted_subagent_type_gates_under_both_tool_names(tmp_path, spawn_tool):
    """An allowlisted subagent_type gates identically under Task and Agent."""
    _seed_state(tmp_path, dict(_OVER_CEILING_STATE))
    result = _run_hook({
        "tool_name": spawn_tool,
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    })
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"


@pytest.mark.parametrize(
    "tool_input",
    [
        {"subagent_type": "general-purpose"},
        {"subagent_type": "Plan"},
        {"subagent_type": "Explore"},
        {},  # subagent_type absent entirely
    ],
)
def test_non_allowlisted_subagent_type_passes_through_without_calling_decide(
    tmp_path, tool_input
):
    """Non-build-cycle spawns over the ceiling do NOT block, do NOT call
    context_budget.decide (proven via a stub whose decide raises), and do NOT
    write the acknowledgment keys to state.json."""
    import subprocess, os

    _seed_state(tmp_path, dict(_OVER_CEILING_STATE))

    # Spy stub: if the branch ever imports+calls decide(), it raises. Because
    # the branch short-circuits on the subagent_type check before importing,
    # decide() is never reached — so stdout is empty and no exception path runs.
    spy_scripts = tmp_path / "spy_scripts"
    spy_scripts.mkdir()
    (spy_scripts / "context_budget.py").write_text(
        "def decide(*args, **kwargs):\n"
        "    raise AssertionError('decide must not be called for non-allowlisted subagent_type')\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(spy_scripts)

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({
            "tool_name": "Task",
            "tool_input": tool_input,
            "cwd": str(tmp_path),
        }).encode(),
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b""

    state = json.loads((tmp_path / ".companion" / "state.json").read_text())
    assert "context_budget_acknowledged_at" not in state
    assert "context_budget_acknowledged_user_turn_seq" not in state


# ---------------------------------------------------------------------------
# Test (INFRA-246): `reviewer` is exempt from the context-budget gate — it is
# the build loop's mandatory, deterministic next step, not a discretionary
# spawn, so it must never be blocked regardless of the state of
# context_current_tokens.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state",
    [
        # missing context_current_tokens entirely
        {
            "context_budget_threshold": 1000,
            "context_budget_overrun_pct": 0.0,
            "expected_step_tokens": 100,
            "context_budget_reprompt_margin": 0,
        },
        # over-ceiling context_current_tokens (would block a "builder" spawn
        # under this identical state, per _OVER_CEILING_STATE above)
        dict(_OVER_CEILING_STATE),
    ],
    ids=["missing-tokens", "over-ceiling-tokens"],
)
def test_reviewer_subagent_type_never_gated(tmp_path, state):
    """A "reviewer" spawn always passes through (sys.exit(0), empty stdout,
    no block), regardless of context_current_tokens state — missing or
    over-ceiling. Proven via a spy stub whose decide() raises: a passing test
    with empty stdout confirms the branch short-circuited before import, the
    same pattern used by
    test_non_allowlisted_subagent_type_passes_through_without_calling_decide.
    Also asserts the acknowledgment keys are never written to state.json."""
    import subprocess, os

    _seed_state(tmp_path, state)

    spy_scripts = tmp_path / "spy_scripts_reviewer"
    spy_scripts.mkdir()
    (spy_scripts / "context_budget.py").write_text(
        "def decide(*args, **kwargs):\n"
        "    raise AssertionError('decide must not be called for reviewer spawns')\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(spy_scripts)

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({
            "tool_name": "Task",
            "tool_input": {"subagent_type": "reviewer"},
            "cwd": str(tmp_path),
        }).encode(),
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b""

    state_after = json.loads((tmp_path / ".companion" / "state.json").read_text())
    assert "context_budget_acknowledged_at" not in state_after
    assert "context_budget_acknowledged_user_turn_seq" not in state_after


# ---------------------------------------------------------------------------
# Test: RELEASE-020 — the current story's flex_factor is threaded through to
# decide(), exercised via the hook's real entry point (not by calling
# decide() directly with the factor pre-supplied).
# ---------------------------------------------------------------------------


def _seed_story(tmp_path: Path, story_id: str, flex_factor: float) -> None:
    """Write a minimal story spec with the given flex_factor and mark it
    current in state.json (current_story is stored as {"id": ...} per
    story_context.py)."""
    rail = story_id.split("-", 1)[0]
    stories_dir = tmp_path / "docs" / "stories" / rail
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / f"{story_id}.md").write_text(
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        "title: Test story\n"
        "status: in_progress\n"
        f"flex_factor: {flex_factor}\n"
        "---\n\n## Ensures\n",
        encoding="utf-8",
    )


def test_flex_factor_raises_ceiling_and_avoids_block(tmp_path):
    """A story with flex_factor=2.0 raises the effective ceiling enough that
    a token count which would block under the default (1.0) factor passes
    instead — exercised through the hook's real entry point."""
    state = {
        "context_budget_threshold": 1000,
        "context_budget_overrun_pct": 0.0,
        "expected_step_tokens": 100,
        "context_budget_reprompt_margin": 0,
        "context_current_tokens": 1200,
        "current_story": {"id": "RELF-001"},
    }
    _seed_state(tmp_path, state)
    _seed_story(tmp_path, "RELF-001", flex_factor=2.0)

    result = _run_hook({
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    })
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_flex_factor_absent_story_still_blocks_at_default_ceiling(tmp_path):
    """Control case: the same over-ceiling state WITHOUT a current story
    (or with flex_factor unset) still blocks exactly as before — the
    no-override path is unchanged."""
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
    result = _run_hook({
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(tmp_path),
    })
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
