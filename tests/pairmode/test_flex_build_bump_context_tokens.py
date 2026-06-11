"""Tests for `flex_build.py bump-context-tokens` (INFRA-169).

Run via:
    PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_bump_context_tokens.py -v
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

# Ensure skills scripts are importable
_SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "pairmode" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from flex_build import flex_build  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path, state: dict | None = None) -> Path:
    """Create a minimal project with optional .companion/state.json."""
    companion = tmp_path / ".companion"
    companion.mkdir()
    if state is not None:
        (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return tmp_path


def _read_state(project: Path) -> dict:
    return json.loads((project / ".companion" / "state.json").read_text(encoding="utf-8"))


def _run(args: list[str]) -> object:
    runner = CliRunner()
    return runner.invoke(flex_build, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_bump_adds_to_existing(tmp_path):
    """state has context_current_tokens: 25000; bump --cost 38000 → 63000."""
    project = _make_project(tmp_path, {"context_current_tokens": 25000})
    result = _run(["bump-context-tokens", "--cost", "38000", "--project-dir", str(project)])
    assert result.exit_code == 0
    assert _read_state(project)["context_current_tokens"] == 63000


def test_bump_from_absent(tmp_path):
    """No context_current_tokens key; bump --cost 38000 → 38000."""
    project = _make_project(tmp_path, {"other_key": "value"})
    result = _run(["bump-context-tokens", "--cost", "38000", "--project-dir", str(project)])
    assert result.exit_code == 0
    assert _read_state(project)["context_current_tokens"] == 38000


def test_bump_from_zero(tmp_path):
    """context_current_tokens: 0; bump --cost 38000 → 38000."""
    project = _make_project(tmp_path, {"context_current_tokens": 0})
    result = _run(["bump-context-tokens", "--cost", "38000", "--project-dir", str(project)])
    assert result.exit_code == 0
    assert _read_state(project)["context_current_tokens"] == 38000


def test_bump_updates_recorded_at(tmp_path):
    """After bump, context_current_tokens_recorded_at is present and parseable as UTC ISO-8601."""
    project = _make_project(tmp_path, {})
    result = _run(["bump-context-tokens", "--cost", "10000", "--project-dir", str(project)])
    assert result.exit_code == 0
    state = _read_state(project)
    recorded_at = state.get("context_current_tokens_recorded_at")
    assert recorded_at is not None
    # Must parse as UTC ISO-8601
    dt = datetime.fromisoformat(recorded_at)
    assert dt.tzinfo is not None


def test_bump_zero_cost_exits_1(tmp_path):
    """--cost 0 exits 1, state unchanged."""
    initial = {"context_current_tokens": 5000}
    project = _make_project(tmp_path, initial)
    runner = CliRunner()
    result = runner.invoke(flex_build, ["bump-context-tokens", "--cost", "0", "--project-dir", str(project)])
    assert result.exit_code == 1
    # State must be unchanged
    assert _read_state(project)["context_current_tokens"] == 5000


def test_bump_negative_cost_exits_1(tmp_path):
    """--cost -1 exits 1, state unchanged."""
    initial = {"context_current_tokens": 5000}
    project = _make_project(tmp_path, initial)
    runner = CliRunner()
    result = runner.invoke(flex_build, ["bump-context-tokens", "--cost", "-1", "--project-dir", str(project)])
    assert result.exit_code == 1
    assert _read_state(project)["context_current_tokens"] == 5000


def test_bump_no_state_json_noop(tmp_path):
    """state.json absent; exits 0, no file created."""
    # tmp_path has no .companion directory at all — simulate entirely absent project
    # We pass a project dir where state.json doesn't exist
    companion = tmp_path / ".companion"
    companion.mkdir()
    # Do NOT write state.json
    result = _run(["bump-context-tokens", "--cost", "10000", "--project-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert not (companion / "state.json").exists()


def test_bump_accumulated(tmp_path):
    """Two consecutive bumps of 30000 each from absent → 60000."""
    project = _make_project(tmp_path, {})
    _run(["bump-context-tokens", "--cost", "30000", "--project-dir", str(project)])
    _run(["bump-context-tokens", "--cost", "30000", "--project-dir", str(project)])
    assert _read_state(project)["context_current_tokens"] == 60000


def test_bump_resets_ttl(tmp_path):
    """bump updates recorded_at to within 5 seconds of now."""
    project = _make_project(tmp_path, {})
    before = datetime.now(timezone.utc)
    result = _run(["bump-context-tokens", "--cost", "1000", "--project-dir", str(project)])
    after = datetime.now(timezone.utc)
    assert result.exit_code == 0
    state = _read_state(project)
    recorded_at = datetime.fromisoformat(state["context_current_tokens_recorded_at"])
    # Ensure recorded_at is within the window (with 5 second tolerance)
    assert before - timedelta(seconds=1) <= recorded_at <= after + timedelta(seconds=5)
