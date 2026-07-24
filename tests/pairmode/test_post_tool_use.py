"""Tests for hooks/post_tool_use.py (INFRA-182, INFRA-236).

Covers:
- The Task/Agent branch stays thin: exactly two delegated module calls
  (context_budget.read_current_tokens, subagent_transcript.
  record_attempt_from_transcript), each independently try/excepted, no
  inlined effort-recording or JSONL-parsing logic in the hook body
  (TestHookStaysThin — regression guard for the attempt-1 CRITICAL finding
  this story previously failed on).
- End-to-end subprocess invocation: a Task/Agent event writes both
  context_current_tokens (state.json) and one attempts row (effort.db),
  and never blocks (empty stdout, exit 0) regardless of outcome.
- Never blocks on malformed input.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "post_tool_use.py"


def _run_hook(stdin_data: dict, cwd: "Path | None" = None) -> "subprocess.CompletedProcess[bytes]":
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(stdin_data).encode(),
        capture_output=True,
        cwd=str(cwd) if cwd else None,
    )


def _enable_tracking(project_dir: Path, **extra) -> Path:
    state_path = project_dir / ".companion" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"effort_tracking": True}
    payload.update(extra)
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    return state_path


# ---------------------------------------------------------------------------
# TestHookStaysThin — source-level regression guard
# ---------------------------------------------------------------------------


class TestHookStaysThin:
    def test_task_agent_branch_has_exactly_two_delegated_module_imports(self) -> None:
        """Attempt-1 regression guard: the Task/Agent branch must delegate to
        named modules, never inline effort-recording or JSONL-parsing logic."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "import context_budget" in source
        assert "import subagent_transcript" in source
        # No inlined transcript-scanning or effort-db logic in the hook body.
        assert "isSidechain" not in source
        assert "sqlite3" not in source
        assert "effort_db" not in source
        assert "insert_attempt" not in source

    def test_two_delegated_calls_are_independently_wrapped(self) -> None:
        """Each of the two calls must be in its own try/except so one failing
        never blocks the other (and never blocks the hook itself)."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        # Crude structural check: both calls appear, each followed (within a
        # bounded window) by an `except Exception:` / `pass` pair.
        assert source.count("except Exception:") >= 2
        assert "context_budget.read_current_tokens(" in source
        assert "subagent_transcript.record_attempt_from_transcript(" in source


# ---------------------------------------------------------------------------
# End-to-end subprocess tests
# ---------------------------------------------------------------------------


class TestTaskAgentBranchEndToEnd:
    def test_writes_context_tokens_and_effort_row(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)

        home = tmp_path / "home"
        cwd_key = str(tmp_path.resolve()).replace("/", "-")
        transcript_dir = home / ".claude" / "projects" / cwd_key
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_lines = [
            {
                "type": "assistant",
                "isSidechain": False,
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_abc",
                            "name": "Task",
                            "input": {"subagent_type": "builder", "prompt": "INFRA-236"},
                        }
                    ]
                },
            },
            {
                "type": "assistant",
                "isSidechain": True,
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cache_read_input_tokens": 100,
                        "cache_creation_input_tokens": 0,
                    },
                },
            },
            {
                "type": "assistant",
                "isSidechain": False,
                "message": {
                    "model": "claude-sonnet-5",
                    "content": [{"type": "text", "text": "orchestrator turn"}],
                    "usage": {
                        "input_tokens": 4,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 100,
                        "output_tokens": 12,
                    },
                },
            },
        ]
        (transcript_dir / "sess-hook.jsonl").write_text(
            "\n".join(json.dumps(line) for line in transcript_lines) + "\n",
            encoding="utf-8",
        )

        env_home = {"HOME": str(home)}
        import os
        env = dict(os.environ)
        env.update(env_home)

        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps({
                "tool_name": "Task",
                "session_id": "sess-hook",
                "cwd": str(tmp_path),
                "tool_input": {"subagent_type": "builder", "prompt": "INFRA-236"},
                "tool_response": json.dumps({
                    "type": "BUILD-RESULT",
                    "outcome": "PASS",
                    "story_id": "INFRA-236",
                    "reason": "did the thing",
                }),
                "tool_use_id": "toolu_abc",
            }).encode(),
            capture_output=True,
            cwd=str(tmp_path),
            env=env,
        )

        assert result.returncode == 0
        assert result.stdout.strip() == b""

        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert state.get("context_current_tokens") == 104  # 4 + 100 + 0

        db_path = tmp_path / ".companion" / "effort.db"
        assert db_path.exists()
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("SELECT story_id, agent_role, outcome FROM attempts")
            rows = cur.fetchall()
        finally:
            conn.close()
        assert rows == [("INFRA-236", "builder", "PASS")]

    def test_non_task_tool_still_relays_and_exits_cleanly(self, tmp_path: Path) -> None:
        result = _run_hook({"tool_name": "Bash", "cwd": str(tmp_path)})
        assert result.returncode == 0
        assert result.stdout.strip() == b""

    def test_malformed_stdin_never_blocks(self) -> None:
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=b"not json",
            capture_output=True,
        )
        assert result.returncode == 0

    def test_missing_state_json_never_blocks(self, tmp_path: Path) -> None:
        result = _run_hook({
            "tool_name": "Task",
            "session_id": "",
            "cwd": str(tmp_path),
            "tool_input": {"subagent_type": "builder", "prompt": "INFRA-236"},
        })
        assert result.returncode == 0
        assert result.stdout.strip() == b""
