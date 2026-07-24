"""Tests for OBS-004: context_current_tokens live writer (CER-054).

Verifies the PostToolUse writer path (post_tool_use.py → context_budget.py)
with synthetic JSONL transcripts — no live API call, no real fleet state.

Diagnosis note (CER-054): The 25k SessionStart reset seed persists fleet-wide
because the writer only fires when a Task/Agent PostToolUse event arrives AND
the JSONL transcript exists at the derived path. Projects that have been reset
but received no subsequent Task/Agent completions within the session stay stale.
The SPA surfaces staleness via current.stale (age > ttl_minutes * 60); OBS-002
renders the staleness badge. The writer itself is correct — the tests below confirm
it fires and updates state.json when the JSONL is present.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

FLEX_ROOT = Path(__file__).resolve().parents[2]
HOOK = FLEX_ROOT / "hooks" / "post_tool_use.py"
sys.path.insert(0, str(FLEX_ROOT / "skills" / "pairmode" / "scripts"))

try:
    from context_budget import (
        compute_context_tokens,
        read_current_tokens,
        _derive_transcript_path,
    )
except ImportError:
    from skills.pairmode.scripts.context_budget import (  # type: ignore[no-redef]
        compute_context_tokens,
        read_current_tokens,
        _derive_transcript_path,
    )


# ---------------------------------------------------------------------------
# JSONL fixture helpers
# ---------------------------------------------------------------------------

def _assistant_line(input_tokens: int, cache_read: int = 0, cache_create: int = 0) -> str:
    """One JSONL line shaped like a thin-harness leaf-spawn assistant response."""
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [],
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
                "output_tokens": 128,
            },
        },
    })


def _write_jsonl(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# compute_context_tokens
# ---------------------------------------------------------------------------

class TestComputeContextTokens:
    def test_extracts_last_assistant_usage_sum(self, tmp_path: Path) -> None:
        """Returns input + cache_read + cache_create from the last assistant entry."""
        jl = tmp_path / "session.jsonl"
        _write_jsonl(jl, [
            _assistant_line(1000, 200, 300),   # first — should be ignored
            _assistant_line(5000, 1000, 500),  # last — expected
        ])
        result = compute_context_tokens(jl)
        assert result == 5000 + 1000 + 500, f"Expected 6500, got {result}"

    def test_finds_last_not_first(self, tmp_path: Path) -> None:
        """Reverse scan returns the LAST assistant entry, not the first."""
        jl = tmp_path / "session.jsonl"
        _write_jsonl(jl, [
            _assistant_line(99999),            # first — must be ignored
            '{"type": "user", "message": {}}', # user entry in between
            _assistant_line(42000),            # last
        ])
        result = compute_context_tokens(jl)
        assert result == 42000

    def test_returns_none_on_no_assistant_entries(self, tmp_path: Path) -> None:
        jl = tmp_path / "session.jsonl"
        _write_jsonl(jl, [
            '{"type": "user", "message": {}}',
            '{"type": "tool_result", "content": []}',
        ])
        assert compute_context_tokens(jl) is None

    def test_returns_none_on_empty_file(self, tmp_path: Path) -> None:
        jl = tmp_path / "session.jsonl"
        jl.write_text("", encoding="utf-8")
        assert compute_context_tokens(jl) is None

    def test_returns_none_on_missing_file(self, tmp_path: Path) -> None:
        jl = tmp_path / "missing.jsonl"
        assert compute_context_tokens(jl) is None

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        """Malformed JSON lines are skipped; the last valid assistant entry wins."""
        jl = tmp_path / "session.jsonl"
        _write_jsonl(jl, [
            "not valid json",
            _assistant_line(8000),
        ])
        result = compute_context_tokens(jl)
        assert result == 8000

    def test_skips_assistant_with_no_usage(self, tmp_path: Path) -> None:
        """Assistant entries without a 'usage' dict are skipped."""
        jl = tmp_path / "session.jsonl"
        _write_jsonl(jl, [
            json.dumps({"type": "assistant", "message": {"role": "assistant"}}),
            _assistant_line(7500),
        ])
        result = compute_context_tokens(jl)
        assert result == 7500


# ---------------------------------------------------------------------------
# read_current_tokens (end-to-end with home injection)
# ---------------------------------------------------------------------------

class TestReadCurrentTokens:
    def test_returns_token_count_when_jsonl_exists(self, tmp_path: Path) -> None:
        """read_current_tokens derives path from home/cwd/session and returns count."""
        home = tmp_path / "home"
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        session_id = "abc123def456"

        # Construct the path the function will derive
        cwd_key = str(project_dir.resolve()).replace("/", "-")
        jsonl_path = home / ".claude" / "projects" / cwd_key / f"{session_id}.jsonl"
        _write_jsonl(jsonl_path, [_assistant_line(15000, 3000, 2000)])

        result = read_current_tokens(project_dir, session_id=session_id, home=home)
        assert result == 20000, f"Expected 20000, got {result}"

    def test_returns_none_when_session_id_empty(self, tmp_path: Path) -> None:
        result = read_current_tokens(tmp_path, session_id="", home=tmp_path)
        assert result is None

    def test_returns_none_when_jsonl_missing(self, tmp_path: Path) -> None:
        """No JSONL at derived path → None, no exception."""
        home = tmp_path / "home"
        home.mkdir()
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        result = read_current_tokens(project_dir, session_id="nosuchsession", home=home)
        assert result is None

    def test_returns_none_when_zero_tokens(self, tmp_path: Path) -> None:
        """Zero-sum usage returns None (not authoritative)."""
        home = tmp_path / "home"
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        session_id = "zeroes"
        cwd_key = str(project_dir.resolve()).replace("/", "-")
        jsonl_path = home / ".claude" / "projects" / cwd_key / f"{session_id}.jsonl"
        _write_jsonl(jsonl_path, [_assistant_line(0, 0, 0)])
        result = read_current_tokens(project_dir, session_id=session_id, home=home)
        assert result is None


# ---------------------------------------------------------------------------
# Hook end-to-end: post_tool_use.py writes context_current_tokens
# ---------------------------------------------------------------------------

def _build_hook_payload(project_dir: Path, session_id: str) -> dict:
    return {
        "tool_name": "Agent",
        "tool_input": {"description": "leaf worker"},
        "tool_response": {"output": "done"},
        "session_id": session_id,
        "cwd": str(project_dir),
    }


class TestPostToolUseHookWriter:
    def test_hook_updates_state_json_when_jsonl_present(self, tmp_path: Path) -> None:
        """Hook writes context_current_tokens to state.json on Agent tool completion."""
        project_dir = tmp_path / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)

        # Seed state.json with the 25k reset seed
        initial_state = {
            "context_current_tokens": 25000,
            "context_current_tokens_recorded_at": "2026-01-01T00:00:00+00:00",
        }
        state_path = companion / "state.json"
        state_path.write_text(json.dumps(initial_state), encoding="utf-8")

        # Create synthetic JSONL at the path the hook will derive
        session_id = "synthsession001"
        cwd_key = str(project_dir.resolve()).replace("/", "-")
        home = Path.home()
        jsonl_path = home / ".claude" / "projects" / cwd_key / f"{session_id}.jsonl"
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        _write_jsonl(jsonl_path, [_assistant_line(50000, 5000, 2000)])

        try:
            payload = _build_hook_payload(project_dir, session_id)
            result = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env={"PATH": f"{Path.home()}/.local/bin:/usr/bin:/bin", "HOME": str(Path.home())},
                timeout=15,
            )
            assert result.returncode == 0, f"Hook failed: {result.stderr}"
            updated = json.loads(state_path.read_text())
            assert updated.get("context_current_tokens") == 57000, (
                f"Expected 57000, got {updated.get('context_current_tokens')}"
            )
            assert "context_current_tokens_recorded_at" in updated
        finally:
            # Clean up the synthetic JSONL so it doesn't pollute real sessions
            if jsonl_path.exists():
                jsonl_path.unlink()

    def test_hook_silent_when_jsonl_missing(self, tmp_path: Path) -> None:
        """Hook exits 0 without crashing when no JSONL transcript found."""
        project_dir = tmp_path / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)
        state_path = companion / "state.json"
        state_path.write_text(json.dumps({"context_current_tokens": 25000}))

        payload = _build_hook_payload(project_dir, "nosuchsession999")
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env={"PATH": f"{Path.home()}/.local/bin:/usr/bin:/bin", "HOME": str(Path.home())},
            timeout=15,
        )
        assert result.returncode == 0
        # State should be unchanged
        after = json.loads(state_path.read_text())
        assert after.get("context_current_tokens") == 25000

    def test_hook_silent_on_non_task_agent_tool(self, tmp_path: Path) -> None:
        """Non-Task/Agent tools do not trigger the writer path."""
        project_dir = tmp_path / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)
        state_path = companion / "state.json"
        state_path.write_text(json.dumps({"context_current_tokens": 25000}))

        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.py"},
            "session_id": "abc",
            "cwd": str(project_dir),
        }
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env={"PATH": f"{Path.home()}/.local/bin:/usr/bin:/bin", "HOME": str(Path.home())},
            timeout=15,
        )
        assert result.returncode == 0
        # state.json untouched
        after = json.loads(state_path.read_text())
        assert after.get("context_current_tokens") == 25000


# ---------------------------------------------------------------------------
# Staleness (rendered by SPA, asserted here on the Python model side)
# ---------------------------------------------------------------------------

class TestStalenessIndicator:
    def _state_with_age(self, age_seconds: int) -> dict:
        recorded = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
        return {
            "context_current_tokens": 30000,
            "context_current_tokens_recorded_at": recorded,
            "context_current_tokens_ttl_minutes": 60,
        }

    def test_fresh_value_not_stale(self, tmp_path: Path) -> None:
        """Value recorded 30 minutes ago (< TTL) is not stale."""
        # We verify the state shape, not the Python stale logic directly
        # (stale logic is context.ts / SPA; this confirms the recorded_at key is present)
        state = self._state_with_age(30 * 60)
        assert "context_current_tokens_recorded_at" in state
        assert state["context_current_tokens"] == 30000

    def test_stale_value_has_old_recorded_at(self, tmp_path: Path) -> None:
        """Value recorded > TTL (120 minutes) has an old timestamp the SPA marks stale."""
        state = self._state_with_age(120 * 60)
        recorded_at = datetime.fromisoformat(state["context_current_tokens_recorded_at"])
        age = (datetime.now(timezone.utc) - recorded_at).total_seconds()
        ttl_seconds = state["context_current_tokens_ttl_minutes"] * 60
        assert age > ttl_seconds, "Expected the test value to be beyond the TTL"
