"""Tests for flex_build.py set-context-tokens — per-story dict write (INFRA-180).

Covers the new context_story_tokens dict write behaviour added in INFRA-180.
The existing scalar write (context_current_tokens) tests live in
test_context_budget.py and are preserved there.

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
# context_story_tokens dict write
# ---------------------------------------------------------------------------


def test_active_story_dict_entry_written(tmp_path):
    """Active story + tokens → context_story_tokens[story_id] written."""
    project_dir = _setup_project(
        tmp_path,
        {
            "pairmode_version": "1.0",
            "current_story": {"id": "INFRA-180", "title": "test story"},
        },
    )
    result = _invoke(project_dir, 80_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    assert "context_story_tokens" in state
    entry = state["context_story_tokens"]["INFRA-180"]
    assert entry["tokens"] == 80_000
    assert "recorded_at" in entry


def test_no_active_story_dict_entry_not_written_stderr_note(tmp_path):
    """No active story → dict entry not written; note emitted to stderr."""
    project_dir = _setup_project(tmp_path, {"pairmode_version": "1.0"})
    result = _invoke(project_dir, 50_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    # Scalar write still happens
    assert state["context_current_tokens"] == 50_000
    # Dict NOT written when no active story
    assert "context_story_tokens" not in state
    # Stderr note present (CliRunner mixes stderr into output by default)
    assert "no active story" in result.output


def test_multiple_stories_accumulate_dict_grows(tmp_path):
    """Multiple stories accumulate — all entries preserved in dict."""
    project_dir = _setup_project(
        tmp_path,
        {
            "pairmode_version": "1.0",
            "current_story": {"id": "INFRA-180", "title": "first"},
        },
    )
    _invoke(project_dir, 40_000)

    # Switch story
    companion = project_dir / ".companion"
    state = json.loads((companion / "state.json").read_text())
    state["current_story"] = {"id": "INFRA-181", "title": "second"}
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")

    _invoke(project_dir, 60_000)

    state = _read_state(project_dir)
    assert "INFRA-180" in state["context_story_tokens"]
    assert "INFRA-181" in state["context_story_tokens"]
    assert state["context_story_tokens"]["INFRA-180"]["tokens"] == 40_000
    assert state["context_story_tokens"]["INFRA-181"]["tokens"] == 60_000


def test_overwrite_same_story_entry_updated(tmp_path):
    """Recording same story twice overwrites with new value (post-clear scenario)."""
    project_dir = _setup_project(
        tmp_path,
        {
            "pairmode_version": "1.0",
            "current_story": {"id": "INFRA-180", "title": "test"},
        },
    )
    _invoke(project_dir, 40_000)
    _invoke(project_dir, 55_000)

    state = _read_state(project_dir)
    assert state["context_story_tokens"]["INFRA-180"]["tokens"] == 55_000


def test_recorded_at_is_utc_iso8601(tmp_path):
    """recorded_at in context_story_tokens entry is a UTC ISO-8601 string."""
    project_dir = _setup_project(
        tmp_path,
        {
            "pairmode_version": "1.0",
            "current_story": {"id": "INFRA-180", "title": "test"},
        },
    )
    result = _invoke(project_dir, 70_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    recorded_at = state["context_story_tokens"]["INFRA-180"]["recorded_at"]
    parsed = datetime.fromisoformat(recorded_at)
    assert parsed.tzinfo is not None


def test_scalar_write_preserved_alongside_dict(tmp_path):
    """Both context_current_tokens (scalar) and context_story_tokens (dict) written."""
    project_dir = _setup_project(
        tmp_path,
        {
            "pairmode_version": "1.0",
            "current_story": {"id": "INFRA-180", "title": "test"},
        },
    )
    result = _invoke(project_dir, 45_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    assert state["context_current_tokens"] == 45_000
    assert state["context_story_tokens"]["INFRA-180"]["tokens"] == 45_000


def test_current_story_as_string_uses_string_as_key(tmp_path):
    """current_story as a plain string (legacy format) still writes the dict entry."""
    project_dir = _setup_project(
        tmp_path,
        {
            "pairmode_version": "1.0",
            "current_story": "INFRA-180",
        },
    )
    result = _invoke(project_dir, 30_000)
    assert result.exit_code == 0, result.output

    state = _read_state(project_dir)
    assert "INFRA-180" in state["context_story_tokens"]
    assert state["context_story_tokens"]["INFRA-180"]["tokens"] == 30_000
