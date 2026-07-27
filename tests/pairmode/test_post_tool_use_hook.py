"""Tests for the INFRA-254 growth-recording addition to hooks/post_tool_use.py.

Distinct from tests/pairmode/test_post_tool_use.py (INFRA-182/INFRA-236 —
context_current_tokens + effort.db writer coverage). This file covers only
the new third delegated call (context_budget.record_step_growth) added by
INFRA-254: the context_step_growth_samples ring buffer and the live
expected_step_tokens re-derivation, wired end-to-end through the hook.

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_post_tool_use_hook.py -x -q
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "post_tool_use.py"


def _write_transcript(home: Path, cwd: Path, session_id: str, orchestrator_tokens: int) -> None:
    cwd_key = str(cwd.resolve()).replace("/", "-")
    transcript_dir = home / ".claude" / "projects" / cwd_key
    transcript_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        {
            "type": "assistant",
            "isSidechain": False,
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_abc",
                        "name": "Task",
                        "input": {"subagent_type": "builder", "prompt": "INFRA-254"},
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "isSidechain": False,
            "message": {
                "model": "claude-sonnet-5",
                "content": [{"type": "text", "text": "orchestrator turn"}],
                "usage": {
                    "input_tokens": orchestrator_tokens,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "output_tokens": 12,
                },
            },
        },
    ]
    (transcript_dir / f"{session_id}.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )


def _run_hook(tmp_path: Path, session_id: str, home: Path) -> "subprocess.CompletedProcess[bytes]":
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(
            {
                "tool_name": "Task",
                "session_id": session_id,
                "cwd": str(tmp_path),
                "tool_input": {"subagent_type": "builder", "prompt": "INFRA-254"},
                "tool_response": json.dumps(
                    {
                        "type": "BUILD-RESULT",
                        "outcome": "PASS",
                        "story_id": "INFRA-254",
                        "reason": "did the thing",
                    }
                ),
                "tool_use_id": "toolu_abc",
            }
        ).encode(),
        capture_output=True,
        cwd=str(tmp_path),
        env=env,
    )


class TestHookRemainsThinForGrowthRecording:
    def test_delegates_to_record_step_growth_not_inline(self) -> None:
        """No new inline ring-buffer/derivation logic in the hook body — it
        must delegate to context_budget.record_step_growth()."""
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "context_budget.record_step_growth(" in source
        assert "statistics.median" not in source
        assert "state[\"context_step_growth_samples\"]" not in source

    def test_still_exactly_the_documented_delegated_calls(self) -> None:
        source = HOOK_PATH.read_text(encoding="utf-8")
        assert "context_budget.read_current_tokens(" in source
        assert "subagent_transcript.record_attempt_from_transcript(" in source


class TestGrowthRecordingEndToEnd:
    def test_first_observation_writes_expected_step_tokens_default_no_samples(
        self, tmp_path: Path
    ) -> None:
        """First-ever PostToolUse observation: no previous context_current_tokens
        to diff against, so no ring-buffer sample is appended, but
        expected_step_tokens is still (re)written (seed/default tier)."""
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"effort_tracking": True}), encoding="utf-8")

        home = tmp_path / "home"
        _write_transcript(home, tmp_path, "sess-1", orchestrator_tokens=50_000)

        result = _run_hook(tmp_path, "sess-1", home)
        assert result.returncode == 0
        assert result.stdout.strip() == b""

        state = json.loads(state_path.read_text())
        assert state["context_current_tokens"] == 50_000
        # INFRA-285 (CER-097 C4): the ring buffer is pinned into this session's
        # entry on its FIRST write so a later write cannot re-inherit another
        # session's mirror. No SAMPLE was recorded — the buffer is empty.
        assert state["context_step_growth_samples"] == []
        assert state["expected_step_tokens"] == 5_000  # THIN_HARNESS_STEP_TOKENS default

    def test_second_observation_appends_growth_sample(self, tmp_path: Path) -> None:
        """A second PostToolUse observation with a fresh, larger token count
        appends the delta to the ring buffer."""
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"effort_tracking": True, "context_current_tokens": 50_000}),
            encoding="utf-8",
        )

        home = tmp_path / "home"
        _write_transcript(home, tmp_path, "sess-2", orchestrator_tokens=54_000)

        result = _run_hook(tmp_path, "sess-2", home)
        assert result.returncode == 0

        state = json.loads(state_path.read_text())
        assert state["context_current_tokens"] == 54_000
        assert state["context_step_growth_samples"] == [4_000]

    def test_non_positive_delta_is_not_appended(self, tmp_path: Path) -> None:
        """A same-or-lower token reading (e.g. re-read of an unchanged
        transcript) does not append a ring-buffer sample."""
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"effort_tracking": True, "context_current_tokens": 60_000}),
            encoding="utf-8",
        )

        home = tmp_path / "home"
        _write_transcript(home, tmp_path, "sess-3", orchestrator_tokens=60_000)

        result = _run_hook(tmp_path, "sess-3", home)
        assert result.returncode == 0

        state = json.loads(state_path.read_text())
        # INFRA-285 (CER-097 C4): key pinned, but no sample appended.
        assert state["context_step_growth_samples"] == []

    def test_never_blocks_and_never_touches_effort_db_write(self, tmp_path: Path) -> None:
        """Growth recording never blocks the hook and never interferes with
        the separate effort.db attempt-row write (INFRA-236)."""
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"effort_tracking": True}), encoding="utf-8")

        home = tmp_path / "home"
        _write_transcript(home, tmp_path, "sess-4", orchestrator_tokens=1_000)

        result = _run_hook(tmp_path, "sess-4", home)
        assert result.returncode == 0
        assert result.stdout.strip() == b""

        import sqlite3

        db_path = tmp_path / ".companion" / "effort.db"
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("SELECT story_id, agent_role, outcome FROM attempts")
            rows = cur.fetchall()
        finally:
            conn.close()
        assert rows == [("INFRA-254", "builder", "PASS")]


# ---------------------------------------------------------------------------
# CER-091 defect 1/E11: SendMessage is observed, never recorded
# ---------------------------------------------------------------------------


class TestSendMessageBranch:
    def test_sendmessage_logs_observed_and_writes_no_attempts_row(self, tmp_path: Path) -> None:
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"effort_tracking": True}), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps({
                "tool_name": "SendMessage",
                "session_id": "sess-sm",
                "cwd": str(tmp_path),
                "tool_input": {"prompt": "continue INFRA-264"},
                "tool_use_id": "toolu_sm",
            }).encode(),
            capture_output=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        assert result.stdout.strip() == b""

        log_path = tmp_path / ".companion" / "effort_recording.log"
        assert log_path.exists()
        entries = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
        assert entries[0]["decision"] == "observed:non-spawn-tool"
        assert entries[0]["tool_name"] == "SendMessage"

        db_path = tmp_path / ".companion" / "effort.db"
        assert not db_path.exists()
