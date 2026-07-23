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
        """All four known step IDs are accepted and exit 0. checkpoint-tag, the
        terminal step, resets the list to [] instead of appending (CER-066);
        the other three steps append normally."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        result = _invoke(project_dir, step_id)
        assert result.exit_code == 0, result.output
        state = _read_state(project_dir)
        if step_id == "checkpoint-tag":
            assert state["checkpoint_step"] == []
        else:
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

    def test_sequential_appends_accumulate_then_reset_on_terminal_step(
        self, tmp_path: Path
    ) -> None:
        """Recording the full sequence accumulates non-terminal steps, then the
        terminal step (checkpoint-tag) resets the list to [] (CER-066)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        for step in [
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
        ]:
            result = _invoke(project_dir, step)
            assert result.exit_code == 0

        state = _read_state(project_dir)
        assert state["checkpoint_step"] == [
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
        ]

        result = _invoke(project_dir, "checkpoint-tag")
        assert result.exit_code == 0

        state = _read_state(project_dir)
        assert state["checkpoint_step"] == []

    def test_checkpoint_tag_marks_active_phase_complete_in_index(
        self, tmp_path: Path
    ) -> None:
        """INFRA-239: completing checkpoint-tag also flips the active phase's
        status cell to 'complete' in docs/phases/index.md, in the same CLI
        call — no separate mark-phase-complete invocation required."""
        project_dir = _setup_project(
            tmp_path,
            {
                "checkpoint_step": [
                    "checkpoint-security",
                    "checkpoint-intent",
                    "checkpoint-docs",
                ]
            },
        )
        phases_dir = project_dir / "docs" / "phases"
        phases_dir.mkdir(parents=True)
        index_path = phases_dir / "index.md"
        index_path.write_text(
            "# Index\n\n"
            "| Phase | Title | Status | Tag |\n"
            "|-------|-------|--------|-----|\n"
            "| 1 | First phase | planned | |\n",
            encoding="utf-8",
        )
        (phases_dir / "phase-1.md").write_text("# Phase 1\n", encoding="utf-8")

        result = _invoke(project_dir, "checkpoint-tag")
        assert result.exit_code == 0, result.output

        state = _read_state(project_dir)
        assert state["checkpoint_step"] == []

        index_text = index_path.read_text(encoding="utf-8")
        assert "| 1 | First phase | complete |" in index_text

    def test_non_terminal_steps_do_not_touch_index(self, tmp_path: Path) -> None:
        """checkpoint-security/intent/docs must not mark the phase complete —
        only the terminal checkpoint-tag step does."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        phases_dir = project_dir / "docs" / "phases"
        phases_dir.mkdir(parents=True)
        index_path = phases_dir / "index.md"
        original = (
            "# Index\n\n"
            "| Phase | Title | Status | Tag |\n"
            "|-------|-------|--------|-----|\n"
            "| 1 | First phase | planned | |\n"
        )
        index_path.write_text(original, encoding="utf-8")
        (phases_dir / "phase-1.md").write_text("# Phase 1\n", encoding="utf-8")

        for step in ["checkpoint-security", "checkpoint-intent", "checkpoint-docs"]:
            result = _invoke(project_dir, step)
            assert result.exit_code == 0, result.output

        assert index_path.read_text(encoding="utf-8") == original

    def test_checkpoint_tag_noop_when_no_index(self, tmp_path: Path) -> None:
        """No docs/phases/index.md present → checkpoint-tag still succeeds
        (the phase-complete write is a graceful no-op, not a hard failure)."""
        project_dir = _setup_project(
            tmp_path,
            {
                "checkpoint_step": [
                    "checkpoint-security",
                    "checkpoint-intent",
                    "checkpoint-docs",
                ]
            },
        )
        result = _invoke(project_dir, "checkpoint-tag")
        assert result.exit_code == 0, result.output
        state = _read_state(project_dir)
        assert state["checkpoint_step"] == []
        assert not (project_dir / "docs" / "phases" / "index.md").exists()

    def test_depth_guard_rejects_shallow_project_dir(self, tmp_path: Path) -> None:
        """A project_dir with fewer than 3 path components → exits non-zero (CER-061)."""
        runner = CliRunner()
        result = runner.invoke(
            flex_build,
            [
                "record-checkpoint-step",
                "checkpoint-security",
                "--project-dir",
                "/tmp",
            ],
        )
        assert result.exit_code != 0
