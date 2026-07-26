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


# ---------------------------------------------------------------------------
# INFRA-265 (CER-077) — explicit --phase-key precedence chain
# ---------------------------------------------------------------------------


def _write_index(project_dir: Path, rows: list[tuple[str, str, str]]) -> Path:
    """Write docs/phases/index.md with (phase_ref, title, status) rows."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
    ]
    for phase_ref, title, status in rows:
        lines.append(f"| {phase_ref} | {title} | {status} | |\n")
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


def _write_phase_file(project_dir: Path, phase_ref: str) -> Path:
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_path = phases_dir / f"phase-{phase_ref}.md"
    phase_path.write_text(f"# Phase {phase_ref}\n", encoding="utf-8")
    return phase_path


def _invoke_with_phase_key(
    project_dir: Path, step_id: str, phase_key: str | None
) -> "click.testing.Result":
    runner = CliRunner()
    args = ["record-checkpoint-step", step_id, "--project-dir", str(project_dir)]
    if phase_key is not None:
        args += ["--phase-key", phase_key]
    return runner.invoke(flex_build, args)


class TestPhaseKeyPrecedence:
    """INFRA-265 (CER-077): --phase-key + stamp + re-derivation precedence."""

    def test_a1_help_lists_phase_key_flag(self) -> None:
        """--help output names --phase-key (A1)."""
        runner = CliRunner()
        result = runner.invoke(flex_build, ["record-checkpoint-step", "--help"])
        assert result.exit_code == 0, result.output
        assert "--phase-key" in result.output

    def test_a1_no_flag_invocation_still_works(self, tmp_path: Path) -> None:
        """Invoking without --phase-key remains a valid call — every existing
        fleet call site keeps working (A1)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        result = _invoke(project_dir, "checkpoint-security")
        assert result.exit_code == 0, result.output

    def test_a2_unknown_phase_key_rejected_before_any_write(
        self, tmp_path: Path
    ) -> None:
        """--phase-key naming a row absent from the index → exit 2, no write
        to state.json or docs/phases/index.md (A2)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        index_path = _write_index(project_dir, [("1", "Only phase", "planned")])
        _write_phase_file(project_dir, "1")

        state_path = project_dir / ".companion" / "state.json"
        state_before = state_path.read_bytes()
        index_before = index_path.read_bytes()

        result = _invoke_with_phase_key(project_dir, "checkpoint-tag", "99")
        assert result.exit_code == 2, result.output
        assert "99" in result.output
        assert "--phase-key" in result.output

        assert state_path.read_bytes() == state_before
        assert index_path.read_bytes() == index_before

    def test_a4_disagreeing_explicit_key_and_stamp_is_an_error(
        self, tmp_path: Path
    ) -> None:
        """An explicit --phase-key that disagrees with a non-empty
        state.json checkpoint_phase stamp → exit 2, no write, both values
        named on stderr (A4)."""
        project_dir = _setup_project(
            tmp_path, {"checkpoint_step": [], "checkpoint_phase": "1"}
        )
        index_path = _write_index(
            project_dir,
            [("1", "First phase", "planned"), ("2", "Second phase", "planned")],
        )
        _write_phase_file(project_dir, "1")
        _write_phase_file(project_dir, "2")

        state_path = project_dir / ".companion" / "state.json"
        state_before = state_path.read_bytes()
        index_before = index_path.read_bytes()

        result = _invoke_with_phase_key(project_dir, "checkpoint-tag", "2")
        assert result.exit_code == 2, result.output
        assert "1" in result.output
        assert "2" in result.output

        assert state_path.read_bytes() == state_before
        assert index_path.read_bytes() == index_before

    def test_a5_five_planned_row_index_no_flag_exits_2_byte_identical(
        self, tmp_path: Path
    ) -> None:
        """The live current-repo layout: phase 103 complete, 104-108 all
        planned, all five phase files present, no checkpoint_phase stamp.
        checkpoint-tag with no --phase-key must exit 2, flip nothing, and
        write nothing (A5, half 1)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        rows = [("103", "Done", "complete")] + [
            (str(n), f"Phase {n}", "planned") for n in range(104, 109)
        ]
        index_path = _write_index(project_dir, rows)
        for n in [103, 104, 105, 106, 107, 108]:
            _write_phase_file(project_dir, str(n))

        state_path = project_dir / ".companion" / "state.json"
        state_before = state_path.read_bytes()
        index_before = index_path.read_bytes()

        result = _invoke_with_phase_key(project_dir, "checkpoint-tag", None)
        assert result.exit_code == 2, result.output
        for n in range(104, 109):
            assert str(n) in result.output

        assert state_path.read_bytes() == state_before, "state.json was written on the exit-2 path"
        assert index_path.read_bytes() == index_before, "index.md was written on the exit-2 path"

    def test_a5_five_planned_row_index_with_phase_key_succeeds(
        self, tmp_path: Path
    ) -> None:
        """Same fixture as above, with --phase-key 104: exits 0, only the
        104 row flips to complete, 105-108 stay planned, checkpoint_step
        resets to [] and checkpoint_phase resets to "" (A5, half 2)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        rows = [("103", "Done", "complete")] + [
            (str(n), f"Phase {n}", "planned") for n in range(104, 109)
        ]
        index_path = _write_index(project_dir, rows)
        for n in [103, 104, 105, 106, 107, 108]:
            _write_phase_file(project_dir, str(n))

        result = _invoke_with_phase_key(project_dir, "checkpoint-tag", "104")
        assert result.exit_code == 0, result.output

        index_text = index_path.read_text(encoding="utf-8")
        assert "| 104 | Phase 104 | complete |" in index_text
        for n in [105, 106, 107, 108]:
            assert f"| {n} | Phase {n} | planned |" in index_text

        state = _read_state(project_dir)
        assert state["checkpoint_step"] == []
        assert state["checkpoint_phase"] == ""

    def test_a6_full_sequence_with_phase_key_then_bare_tag(
        self, tmp_path: Path
    ) -> None:
        """The mandated loop path: three gate steps recorded with
        --phase-key 104, then checkpoint-tag with no flag. The INFRA-260
        stamp (set by the gate steps) is consumed, so no re-derivation is
        needed and none occurs (A6)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        rows = [("103", "Done", "complete")] + [
            (str(n), f"Phase {n}", "planned") for n in range(104, 109)
        ]
        index_path = _write_index(project_dir, rows)
        for n in [103, 104, 105, 106, 107, 108]:
            _write_phase_file(project_dir, str(n))

        for step in ["checkpoint-security", "checkpoint-intent", "checkpoint-docs"]:
            result = _invoke_with_phase_key(project_dir, step, "104")
            assert result.exit_code == 0, result.output

        result = _invoke_with_phase_key(project_dir, "checkpoint-tag", None)
        assert result.exit_code == 0, result.output

        index_text = index_path.read_text(encoding="utf-8")
        assert "| 104 | Phase 104 | complete |" in index_text

        state = _read_state(project_dir)
        assert state["checkpoint_step"] == []
        assert state["checkpoint_phase"] == ""

    def test_a8_non_terminal_ambiguous_step_warns_and_continues(
        self, tmp_path: Path
    ) -> None:
        """A non-terminal step with no --phase-key and an ambiguous index
        exits 0, stamps checkpoint_phase == "", and warns on stderr — never
        an error (A8)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        _write_index(
            project_dir,
            [("1", "First phase", "planned"), ("2", "Second phase", "planned")],
        )
        _write_phase_file(project_dir, "1")
        _write_phase_file(project_dir, "2")

        result = _invoke_with_phase_key(project_dir, "checkpoint-security", None)
        assert result.exit_code == 0, result.output
        assert "1" in result.output and "2" in result.output

        state = _read_state(project_dir)
        assert state["checkpoint_phase"] == ""
        assert state["checkpoint_step"] == ["checkpoint-security"]

    def test_a8_non_terminal_step_with_explicit_phase_key_stamps_it(
        self, tmp_path: Path
    ) -> None:
        """A non-terminal step with --phase-key K stamps checkpoint_phase
        == K even when the index is otherwise ambiguous (A8)."""
        project_dir = _setup_project(tmp_path, {"checkpoint_step": []})
        _write_index(
            project_dir,
            [("1", "First phase", "planned"), ("2", "Second phase", "planned")],
        )
        _write_phase_file(project_dir, "1")
        _write_phase_file(project_dir, "2")

        result = _invoke_with_phase_key(project_dir, "checkpoint-security", "2")
        assert result.exit_code == 0, result.output

        state = _read_state(project_dir)
        assert state["checkpoint_phase"] == "2"
