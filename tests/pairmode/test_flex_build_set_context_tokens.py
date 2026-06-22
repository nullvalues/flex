"""Tests for flex_build.py set-context-tokens — scalar write only (INFRA-182).

INFRA-182: set-context-tokens writes the scalar context_current_tokens only.
The per-story dict (context_story_tokens) is no longer written — PostToolUse
handles automatic updates via JSONL reading.
set-context-tokens remains as a manual override / debugging escape hatch.

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_flex_build_set_context_tokens.py -x -q
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from click.testing import CliRunner

sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts")
)

from flex_build import flex_build  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke(project_dir: Path, tokens: int) -> "click.testing.Result":
    runner = CliRunner()
    return runner.invoke(
        flex_build,
        [
            "set-context-tokens",
            "--tokens",
            str(tokens),
            "--project-dir",
            str(project_dir),
        ],
    )


def _setup_project(tmp_path: Path, state: dict) -> Path:
    """Create a project with .companion/state.json and return the project dir."""
    project_dir = tmp_path / "sub" / "project"
    companion = project_dir / ".companion"
    companion.mkdir(parents=True)
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return project_dir


def _read_state(project_dir: Path) -> dict:
    return json.loads(
        (project_dir / ".companion" / "state.json").read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# Scalar write only (INFRA-182)
# ---------------------------------------------------------------------------


def test_scalar_write_with_active_story(tmp_path):
    """Even with an active story, only scalar is written — no dict entry."""
    project_dir = _setup_project(
        tmp_path,
        {
            "pairmode_version": "1.0",
            "current_story": {"id": "INFRA-182", "title": "test story"},
        },
    )
    result = _invoke(project_dir, 80_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    assert state["context_current_tokens"] == 80_000
    # INFRA-182: dict NOT written even with active story
    assert "context_story_tokens" not in state


def test_scalar_write_without_active_story(tmp_path):
    """No active story → scalar still written, no dict entry."""
    project_dir = _setup_project(tmp_path, {"pairmode_version": "1.0"})
    result = _invoke(project_dir, 50_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    assert state["context_current_tokens"] == 50_000
    assert "context_story_tokens" not in state


def test_recorded_at_written_alongside_scalar(tmp_path):
    """context_current_tokens_recorded_at written with the scalar."""
    project_dir = _setup_project(tmp_path, {"pairmode_version": "1.0"})
    result = _invoke(project_dir, 70_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    assert "context_current_tokens_recorded_at" in state
    recorded_at = state["context_current_tokens_recorded_at"]
    parsed = datetime.fromisoformat(recorded_at)
    assert parsed.tzinfo is not None


def test_overwrite_scalar_updated(tmp_path):
    """Recording twice overwrites the scalar with the new value."""
    project_dir = _setup_project(tmp_path, {"pairmode_version": "1.0"})
    _invoke(project_dir, 40_000)
    _invoke(project_dir, 55_000)

    state = _read_state(project_dir)
    assert state["context_current_tokens"] == 55_000


def test_other_state_preserved(tmp_path):
    """Existing state.json keys are preserved when scalar is updated."""
    project_dir = _setup_project(
        tmp_path,
        {
            "pairmode_version": "1.0",
            "context_budget_threshold": 120_000,
        },
    )
    result = _invoke(project_dir, 45_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    assert state["context_current_tokens"] == 45_000
    assert state["pairmode_version"] == "1.0"
    assert state["context_budget_threshold"] == 120_000
