"""Tests for hooks/subagent_stop.py — the SubagentStop relay (INFRA-298,
CER-114).

Mirrors tests/pairmode/test_session_start_hook.py's shape: module-level
REPO_ROOT/HOOK_PATH, a _run_hook(cwd, payload) helper invoking
subprocess.run([sys.executable, HOOK_PATH], input=..., cwd=..., ...), and a
_write_state helper.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "subagent_stop.py"

SCRIPTS = REPO_ROOT / "skills" / "pairmode" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import effort_db  # noqa: E402


def _run_hook(cwd: Path, payload: "dict | str | None") -> subprocess.CompletedProcess:
    if payload is None:
        raw = ""
    elif isinstance(payload, str):
        raw = payload
    else:
        raw = json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        cwd=str(cwd),
        input=raw,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_state(cwd: Path, state: dict) -> Path:
    companion_dir = cwd / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _build_result_json(outcome: str = "PASS") -> str:
    return json.dumps({
        "type": "BUILD-RESULT", "outcome": outcome,
        "story_id": "INFRA-298", "reason": "done",
    })


# ---------------------------------------------------------------------------
# 1-5: shape/no-op contract
# ---------------------------------------------------------------------------


def test_no_state_json_exits_zero_no_output(tmp_path: Path) -> None:
    result = _run_hook(tmp_path, {"agent_id": "a1"})
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert not (tmp_path / ".companion" / "effort.db").exists()


def test_state_without_pairmode_version_exits_zero_no_write(tmp_path: Path) -> None:
    _write_state(tmp_path, {"effort_tracking": True})
    result = _run_hook(tmp_path, {"agent_id": "a1"})
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert not (tmp_path / ".companion" / "effort.db").exists()


def test_effort_tracking_false_exits_zero_no_reconcile(tmp_path: Path) -> None:
    _write_state(tmp_path, {"pairmode_version": "0.1.0", "effort_tracking": False})
    result = _run_hook(tmp_path, {"agent_id": "a1"})
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert not (tmp_path / ".companion" / "effort.db").exists()


def test_malformed_stdin_exits_zero_no_traceback(tmp_path: Path) -> None:
    _write_state(tmp_path, {"pairmode_version": "0.1.0", "effort_tracking": True})
    result = _run_hook(tmp_path, "{not json")
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.strip() == ""


def test_empty_stdin_exits_zero(tmp_path: Path) -> None:
    _write_state(tmp_path, {"pairmode_version": "0.1.0", "effort_tracking": True})
    result = _run_hook(tmp_path, "")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_non_dict_stdin_root_exits_zero(tmp_path: Path) -> None:
    _write_state(tmp_path, {"pairmode_version": "0.1.0", "effort_tracking": True})
    result = _run_hook(tmp_path, "[1, 2, 3]")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_tty_stdin_exits_zero_no_output(tmp_path: Path) -> None:
    """No stdin piped — invoked directly, mirroring a tty read."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0", "effort_tracking": True})
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        cwd=str(tmp_path),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# 6: end-to-end reconcile against a fixture project
# ---------------------------------------------------------------------------


def test_well_formed_payload_reconciles_matching_pending_row(tmp_path: Path) -> None:
    _write_state(tmp_path, {"pairmode_version": "0.1.0", "effort_tracking": True})

    db_path = tmp_path / ".companion" / "effort.db"
    effort_db.init_db(db_path)
    output_file = tmp_path / "tasks" / "agent.output"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps({
            "type": "assistant",
            "message": {
                "id": "msg_1",
                "model": "claude-sonnet-5",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": _build_result_json("PASS")}],
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        }) + "\n",
        encoding="utf-8",
    )
    row_id = effort_db.insert_attempt(
        db_path,
        story_id="INFRA-298",
        agent_role="builder",
        attempt_number=1,
        ts=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    )
    effort_db.set_spawn_ref(db_path, row_id, "agent-hook-1", str(output_file))

    result = _run_hook(
        tmp_path,
        {
            "agent_id": "agent-hook-1",
            "cwd": str(tmp_path),
            "hook_event_name": "SubagentStop",
            "last_assistant_message": "no grammar in the payload — forces file fallback",
        },
    )

    assert result.returncode == 0
    assert result.stdout.strip() == ""

    rows = effort_db.query_by_story(db_path, "INFRA-298")
    assert rows[0]["outcome"] == "PASS"
    assert rows[0]["tokens_total"] == 150


# ---------------------------------------------------------------------------
# 7: thinness assertions on the hook source
# ---------------------------------------------------------------------------


def _hook_source() -> str:
    return HOOK_PATH.read_text(encoding="utf-8")


def test_hook_makes_exactly_one_call_into_subagent_transcript() -> None:
    """Thinness: exactly one call into subagent_transcript, parsed from the
    AST so prose mentions in the module docstring/comments (which also name
    ``subagent_transcript.reconcile_one`` for a human reader) do not inflate
    the count."""
    import ast

    tree = ast.parse(_hook_source())
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subagent_transcript"
    ]
    assert len(calls) == 1
    assert calls[0].func.attr == "reconcile_one"


def test_hook_does_not_import_effort_db() -> None:
    source = _hook_source()
    assert "import effort_db" not in source
    assert "effort_db." not in source


def test_hook_never_writes_a_file() -> None:
    source = _hook_source()
    assert "write_text(" not in source
    assert "open(" not in source


def test_hook_never_prints() -> None:
    source = _hook_source()
    assert "print(" not in source


def test_hook_has_shebang_and_main_guard() -> None:
    source = _hook_source()
    assert source.startswith("#!/usr/bin/env python3")
    assert '__name__ == "__main__"' in source
