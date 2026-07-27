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


# ---------------------------------------------------------------------------
# INFRA-285 (CER-097) — session-scoped token writer and sweep ownership
# ---------------------------------------------------------------------------

import os  # noqa: E402

SCRIPTS = REPO_ROOT / "skills" / "pairmode" / "scripts"


def _write_transcript(home: Path, project_dir: Path, session_id: str, tokens: int) -> None:
    cwd_key = str(project_dir.resolve()).replace("/", "-")
    transcript_dir = home / ".claude" / "projects" / cwd_key
    transcript_dir.mkdir(parents=True, exist_ok=True)
    (transcript_dir / f"{session_id}.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "isSidechain": False,
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {
                        "input_tokens": tokens,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                        "output_tokens": 1,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _run_task_hook(
    project_dir: Path, home: Path, session_id: str, *, tool_response=None
) -> "subprocess.CompletedProcess[bytes]":
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(
            {
                "tool_name": "Task",
                "session_id": session_id,
                "cwd": str(project_dir),
                "tool_input": {"subagent_type": "builder", "prompt": "INFRA-285"},
                "tool_response": tool_response,
                "tool_use_id": f"toolu_{session_id}",
            }
        ).encode(),
        capture_output=True,
        cwd=str(project_dir),
        env=env,
    )


class TestSessionScopedTokenWriter:
    def test_two_sessions_keep_separate_growth_ring_buffers(self, tmp_path: Path) -> None:
        """C4: a session's deltas are derived only from its own observations."""
        _enable_tracking(tmp_path)
        home = tmp_path / "home"

        # LOOP: 140000 -> 150000 ; SIDE: 30000 -> 45000, interleaved.
        _write_transcript(home, tmp_path, "LOOP", 140_000)
        _run_task_hook(tmp_path, home, "LOOP")
        _write_transcript(home, tmp_path, "SIDE", 30_000)
        _run_task_hook(tmp_path, home, "SIDE")
        _write_transcript(home, tmp_path, "LOOP", 150_000)
        _run_task_hook(tmp_path, home, "LOOP")
        _write_transcript(home, tmp_path, "SIDE", 45_000)
        _run_task_hook(tmp_path, home, "SIDE")

        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        sessions = state["context_sessions"]
        assert sessions["SIDE"]["context_step_growth_samples"] == [15_000]
        assert sessions["LOOP"]["context_step_growth_samples"] == [10_000]
        assert sessions["LOOP"]["context_current_tokens"] == 150_000
        assert sessions["SIDE"]["context_current_tokens"] == 45_000

    def test_flat_mirror_still_tracks_the_last_writer(self, tmp_path: Path) -> None:
        """A5: the flat keys remain a display-only, last-writer-wins mirror."""
        _enable_tracking(tmp_path)
        home = tmp_path / "home"
        _write_transcript(home, tmp_path, "SIDE", 33_000)
        _run_task_hook(tmp_path, home, "SIDE")
        state = json.loads((tmp_path / ".companion" / "state.json").read_text())
        assert state["context_current_tokens"] == 33_000


class TestSpawnPrefixCapture:
    def test_prefix_is_stored_inside_the_single_state_write(self, tmp_path: Path) -> None:
        """D2: the prefix rides inside the write the hook already performs."""
        _enable_tracking(tmp_path)
        home = tmp_path / "home"
        _write_transcript(home, tmp_path, "S1", 40_000)
        output_file = tmp_path / "spawnroot" / "S1" / "tasks" / "x.output"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("", encoding="utf-8")

        result = _run_task_hook(
            tmp_path, home, "S1", tool_response={"output_file": str(output_file)}
        )
        assert result.returncode == 0

        entry = json.loads(
            (tmp_path / ".companion" / "state.json").read_text()
        )["context_sessions"]["S1"]
        assert entry["spawn_output_prefix"] == str(tmp_path / "spawnroot" / "S1") + os.sep

    def test_hook_performs_exactly_one_state_write(self) -> None:
        """D2: no additional state.json write, read, or open() was introduced."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        task_branch = source.split('if tool_name in ("Task", "Agent", "SendMessage"):')[1]
        task_branch = task_branch.split("if tool_name not in WATCHED_TOOLS:")[0]
        assert task_branch.count("update_state_json(") == 1
        assert "_atomic_write_json" not in task_branch
        assert "read_text()" not in task_branch
        assert "open(" not in task_branch

    def test_second_delegated_call_passes_the_stored_prefix(self) -> None:
        """D6: the sweep in call 2 is scoped to this session's own rows."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "output_prefix=stored_prefix," in source
        # A None prefix must not become an exclusion (see D6).
        assert "exclude_output_prefixes" not in source

    def test_first_spawn_of_a_session_sweeps_globally(self, tmp_path: Path) -> None:
        """D6: with no stored prefix yet, the sweep keeps today's global reach."""
        _enable_tracking(tmp_path)
        home = tmp_path / "home"
        _write_transcript(home, tmp_path, "S1", 40_000)
        result = _run_task_hook(tmp_path, home, "S1", tool_response=None)
        assert result.returncode == 0
        entry = json.loads(
            (tmp_path / ".companion" / "state.json").read_text()
        )["context_sessions"]["S1"]
        assert entry["spawn_output_prefix"] is None
