"""Tests for flex_build.py record-checkpoint-step (RESOLVER-012).

Coverage:
- Valid step_id appended to empty checkpoint_step list.
- Valid step_id when list already contains it (idempotent, no write, exits 0).
- Invalid step_id → command exits non-zero, state.json unchanged.
- All four known step IDs are accepted: checkpoint-security, checkpoint-intent,
  checkpoint-docs, checkpoint-tag.
- Creates checkpoint_step key if missing from state.json.

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_record_checkpoint_step.py -x -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts")
)

from flex_build import flex_build  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _invoke(project_dir: Path, step_id: str) -> "click.testing.Result":
    runner = CliRunner()
    return runner.invoke(
        flex_build,
        [
            "record-checkpoint-step",
            step_id,
            "--project-dir",
            str(project_dir),
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecordCheckpointStep:
    def test_valid_step_appended_to_empty_list(self, tmp_path: Path) -> None:
        """Valid step_id appended to empty checkpoint_step → exits 0, list updated."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        result = _invoke(project_dir, "checkpoint-security")
        assert result.exit_code == 0, result.output
        state = _read_state(project_dir)
        assert state["checkpoint_step"] == ["checkpoint-security"]

    def test_idempotent_step_already_present(self, tmp_path: Path) -> None:
        """step_id already in list → exits 0, no write (state unchanged)."""
        project_dir = _setup_project(
            tmp_path, {"checkpoint_step": ["checkpoint-security"]}
        )
        # Read mtime before the call.
        state_path = project_dir / ".companion" / "state.json"
        mtime_before = state_path.stat().st_mtime_ns

        result = _invoke(project_dir, "checkpoint-security")
        assert result.exit_code == 0, result.output

        mtime_after = state_path.stat().st_mtime_ns
        assert mtime_before == mtime_after, "state.json was written despite idempotent call"
        state = _read_state(project_dir)
        assert state["checkpoint_step"] == ["checkpoint-security"]

    def test_invalid_step_id_exits_nonzero(self, tmp_path: Path) -> None:
        """Unknown step_id → exits non-zero, state.json unchanged."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        state_path = project_dir / ".companion" / "state.json"
        mtime_before = state_path.stat().st_mtime_ns

        result = _invoke(project_dir, "checkpoint-unknown")
        assert result.exit_code != 0

        mtime_after = state_path.stat().st_mtime_ns
        assert mtime_before == mtime_after, "state.json was mutated on invalid step_id"
        state = _read_state(project_dir)
        assert state["checkpoint_step"] == []

    @pytest.mark.parametrize(
        "step_id",
        [
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
            "checkpoint-tag",
        ],
    )
    def test_all_four_step_ids_accepted(self, tmp_path: Path, step_id: str) -> None:
        """All four known step IDs are accepted (exit 0, appended)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        result = _invoke(project_dir, step_id)
        assert result.exit_code == 0, result.output
        state = _read_state(project_dir)
        assert step_id in state["checkpoint_step"]

    def test_creates_checkpoint_step_key_when_missing(self, tmp_path: Path) -> None:
        """checkpoint_step key absent from state.json → created with [step_id]."""
        project_dir = _setup_project(tmp_path, {"pairmode_version": "1.0"})
        result = _invoke(project_dir, "checkpoint-intent")
        assert result.exit_code == 0, result.output
        state = _read_state(project_dir)
        assert "checkpoint_step" in state
        assert state["checkpoint_step"] == ["checkpoint-intent"]

    def test_other_state_keys_preserved(self, tmp_path: Path) -> None:
        """Existing state.json keys are not touched during append."""
        project_dir = _setup_project(
            tmp_path,
            {
                "pairmode_version": "1.0",
                "context_budget_threshold": 120_000,
                "checkpoint_step": [],
            },
        )
        result = _invoke(project_dir, "checkpoint-docs")
        assert result.exit_code == 0, result.output
        state = _read_state(project_dir)
        assert state["pairmode_version"] == "1.0"
        assert state["context_budget_threshold"] == 120_000
        assert state["checkpoint_step"] == ["checkpoint-docs"]

    def test_sequential_appends_accumulate(self, tmp_path: Path) -> None:
        """Multiple sequential calls build up the list in order."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        for step in [
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
            "checkpoint-tag",
        ]:
            result = _invoke(project_dir, step)
            assert result.exit_code == 0

        state = _read_state(project_dir)
        assert state["checkpoint_step"] == [
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
            "checkpoint-tag",
        ]
