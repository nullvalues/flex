"""Tests for hooks/user_prompt_submit.py — user-turn sequence counter."""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "user_prompt_submit.py"


def _run_hook(stdin_payload: dict) -> subprocess.CompletedProcess:
    """Invoke the UserPromptSubmit hook with the given stdin JSON payload."""
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(stdin_payload),
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


def _read_state(state_path: Path) -> dict:
    return json.loads(state_path.read_text(encoding="utf-8"))


def test_user_prompt_submit_no_state_file_exits_cleanly(tmp_path):
    """No .companion/state.json → hook exits 0, no file created, empty stdout."""
    result = _run_hook({"cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout == ""
    assert not (tmp_path / ".companion" / "state.json").exists()


def test_user_prompt_submit_empty_payload_no_cwd(tmp_path):
    """Empty stdin object, no cwd, no state.json present → exits 0, no output."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="{}",
        capture_output=True,
        text=True,
        check=False,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_user_prompt_submit_increments_from_absent_key(tmp_path):
    """No context_budget_user_turn_seq key → after one invocation, key is 1."""
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _run_hook({"cwd": str(tmp_path)})
    assert result.returncode == 0
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 1


def test_user_prompt_submit_increments_monotonically(tmp_path):
    """Seeded context_budget_user_turn_seq: 5 → after one invocation, key is 6."""
    state_path = _write_state(
        tmp_path, {"pairmode_version": "0.1.0", "context_budget_user_turn_seq": 5}
    )
    result = _run_hook({"cwd": str(tmp_path)})
    assert result.returncode == 0
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 6


def test_user_prompt_submit_two_invocations_increment_twice(tmp_path):
    """Two invocations against the same state.json → counter reaches 2."""
    state_path = _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    _run_hook({"cwd": str(tmp_path)})
    _run_hook({"cwd": str(tmp_path)})
    state = _read_state(state_path)
    assert state["context_budget_user_turn_seq"] == 2


def test_user_prompt_submit_malformed_json_does_not_crash(tmp_path):
    """Malformed state.json → hook exits 0, file left unmodified."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state_path = companion_dir / "state.json"
    state_path.write_text("{not valid json", encoding="utf-8")
    result = _run_hook({"cwd": str(tmp_path)})
    assert result.returncode == 0
    assert state_path.read_text(encoding="utf-8") == "{not valid json"


def test_user_prompt_submit_never_emits_decision(tmp_path):
    """Valid state.json → hook stdout is empty; no decision payload of any kind."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _run_hook({"cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stdout == ""
    assert "decision" not in result.stdout
