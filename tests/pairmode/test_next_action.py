"""
tests/pairmode/test_next_action.py

Unit-tests for:
  - next_action.infer_position (RESOLVER-002)
  - next_action.resolve_next_action (RESOLVER-003)
  - flex_build.py next-action subcommand (RESOLVER-003)
  - flex_build.py module-level extraction functions:
      resolve_current_phase, read_attempt_count,
      check_stub_gate, check_schema_gate_result, check_auth_gate_result

All tests use synthetic durable state (tmp project trees) and never depend on
the real git log of this repo.  Where commit-authority checks are exercised,
the test injects a fake git log via monkeypatching.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from next_action import (  # noqa: E402
    OUTCOME_FAIL,
    OUTCOME_NONE,
    OUTCOME_PASS,
    infer_position,
    _check_phase_completion,
)
from flex_build import (  # noqa: E402
    resolve_current_phase,
    read_attempt_count,
    check_stub_gate,
    check_schema_gate_result,
    check_auth_gate_result,
)


# ---------------------------------------------------------------------------
# Project tree helpers
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


def _write_phase(
    project_dir: Path,
    phase_ref: str,
    stories: list[tuple[str, str]],  # [(story_id, status)]
) -> Path:
    """Write docs/phases/phase-{phase_ref}.md with a Stories table."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_path = phases_dir / f"phase-{phase_ref}.md"
    lines = [
        f"# Phase {phase_ref}\n\n",
        "## Stories\n\n",
        "| ID | Title | Status |\n",
        "|----|-------|--------|\n",
    ]
    for story_id, status in stories:
        lines.append(f"| {story_id} | A story | {status} |\n")
    phase_path.write_text("".join(lines), encoding="utf-8")
    return phase_path


def _write_story(
    project_dir: Path,
    story_id: str,
    *,
    story_class: str = "code",
    primary_files: list[str] | None = None,
    phase: str = "1",
    auth_gated: bool = False,
    schema_introduces: bool = False,
    stub: bool = False,
) -> Path:
    """Write a minimal story spec."""
    rail = story_id.split("-", 1)[0]
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"
    # Build YAML list for primary_files using indented-list format.
    pf_list = primary_files or []
    if pf_list:
        pf_yaml = "\nprimary_files:\n" + "".join(f"  - {f}\n" for f in pf_list)
    else:
        pf_yaml = "\nprimary_files: []\n"
    if stub:
        body = "See phase doc for details.\n"
    else:
        # Use >= 5 non-blank Ensures lines so needs_spec = False (RESOLVER-009).
        body = (
            "## Ensures\n\n"
            "- It works as designed.\n"
            "- All inputs are validated.\n"
            "- The output format is correct.\n"
            "- Tests pass.\n"
            "- No regressions introduced.\n"
        )
    content = (
        f"---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        f"status: planned\n"
        f"phase: '{phase}'\n"
        f"story_class: {story_class}\n"
        f"{pf_yaml}"
        f"auth_gated: {'true' if auth_gated else 'false'}\n"
        f"schema_introduces: {'true' if schema_introduces else 'false'}\n"
        f"---\n\n"
        f"{body}"
    )
    story_path.write_text(content, encoding="utf-8")
    return story_path


def _write_attempt_counter(project_dir: Path, story_id: str, count: int) -> None:
    """Write .companion/attempt_counter.json."""
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "attempt_counter.json").write_text(
        json.dumps({"story_id": story_id, "attempt_count": count}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tests — resolve_current_phase extraction
# ---------------------------------------------------------------------------


class TestResolveCurrentPhase:
    def test_returns_path_for_active_phase(self, tmp_path: Path) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")

        result = resolve_current_phase(tmp_path)
        assert result is not None
        assert result.name == "phase-1.md"

    def test_returns_none_when_all_complete(self, tmp_path: Path) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "complete")])
        _write_phase(tmp_path, "1", [("TEST-001", "complete")])
        _write_story(tmp_path, "TEST-001")

        result = resolve_current_phase(tmp_path)
        assert result is None

    def test_returns_none_when_no_phases_dir(self, tmp_path: Path) -> None:
        result = resolve_current_phase(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Tests — read_attempt_count extraction
# ---------------------------------------------------------------------------


class TestReadAttemptCount:
    def test_returns_zero_when_no_file(self, tmp_path: Path) -> None:
        assert read_attempt_count("TEST-001", tmp_path) == 0

    def test_returns_count_for_matching_story(self, tmp_path: Path) -> None:
        _write_attempt_counter(tmp_path, "TEST-001", 3)
        assert read_attempt_count("TEST-001", tmp_path) == 3

    def test_returns_zero_for_different_story(self, tmp_path: Path) -> None:
        _write_attempt_counter(tmp_path, "OTHER-002", 2)
        assert read_attempt_count("TEST-001", tmp_path) == 0

    def test_returns_zero_on_malformed_json(self, tmp_path: Path) -> None:
        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        (companion / "attempt_counter.json").write_text("not json", encoding="utf-8")
        assert read_attempt_count("TEST-001", tmp_path) == 0


# ---------------------------------------------------------------------------
# Tests — check_stub_gate extraction
# ---------------------------------------------------------------------------


class TestCheckStubGate:
    def test_ok_for_clean_story(self, tmp_path: Path) -> None:
        _write_story(tmp_path, "TEST-001", stub=False)
        result = check_stub_gate("TEST-001", tmp_path)
        assert result["ok"] is True
        assert result["missing"] is False

    def test_blocked_for_stub_story(self, tmp_path: Path) -> None:
        _write_story(tmp_path, "TEST-001", stub=True)
        result = check_stub_gate("TEST-001", tmp_path)
        assert result["ok"] is False
        assert result["missing"] is False
        assert len(result["reasons"]) > 0

    def test_missing_when_file_absent(self, tmp_path: Path) -> None:
        result = check_stub_gate("TEST-001", tmp_path)
        assert result["ok"] is False
        assert result["missing"] is True


# ---------------------------------------------------------------------------
# Tests — check_schema_gate_result extraction
# ---------------------------------------------------------------------------


class TestCheckSchemaGateResult:
    def test_ok_when_schema_introduces_false(self, tmp_path: Path) -> None:
        _write_story(tmp_path, "TEST-001", schema_introduces=False)
        result = check_schema_gate_result("TEST-001", tmp_path)
        assert result["ok"] is True

    def test_blocked_when_schema_introduces_and_no_surface(
        self, tmp_path: Path
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(
            tmp_path, "TEST-001", schema_introduces=True, phase="1"
        )
        result = check_schema_gate_result("TEST-001", tmp_path)
        assert result["ok"] is False
        assert "blocked_reason" in result

    def test_ok_when_schema_introduces_with_exception_phrase(
        self, tmp_path: Path
    ) -> None:
        rail = "TEST"
        story_dir = tmp_path / "docs" / "stories" / rail
        story_dir.mkdir(parents=True, exist_ok=True)
        story_path = story_dir / "TEST-001.md"
        story_path.write_text(
            "---\nid: TEST-001\nrail: TEST\nstatus: planned\nphase: '1'\n"
            "schema_introduces: true\nprimary_files: []\n---\n\n"
            "## Ensures\n\nThis is an append-only audit log table.\n",
            encoding="utf-8",
        )
        result = check_schema_gate_result("TEST-001", tmp_path)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Tests — check_auth_gate_result extraction
# ---------------------------------------------------------------------------


class TestCheckAuthGateResult:
    def test_ok_when_not_auth_gated(self, tmp_path: Path) -> None:
        _write_story(tmp_path, "TEST-001", auth_gated=False)
        result = check_auth_gate_result("TEST-001", tmp_path)
        assert result["ok"] is True

    def test_blocked_when_auth_gated_no_classification(
        self, tmp_path: Path
    ) -> None:
        _write_story(tmp_path, "TEST-001", auth_gated=True)
        # No architecture.md
        result = check_auth_gate_result("TEST-001", tmp_path)
        assert result["ok"] is False
        assert "blocked_reason" in result

    def test_ok_when_auth_gated_with_classification(
        self, tmp_path: Path
    ) -> None:
        _write_story(tmp_path, "TEST-001", auth_gated=True)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "architecture.md").write_text(
            "## Auth model\n\n**Classification:** RBAC\n",
            encoding="utf-8",
        )
        result = check_auth_gate_result("TEST-001", tmp_path)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Tests — infer_position (RESOLVER-002 core)
# ---------------------------------------------------------------------------


def _patch_git_log(monkeypatch: Any, log_output: str) -> None:
    """Patch next_story._git_log_oneline to return *log_output*."""
    import next_story as _ns  # type: ignore[import]
    monkeypatch.setattr(_ns, "_git_log_oneline", lambda _project_dir: log_output)


class TestInferPositionAllPhasesComplete:
    """All phases complete ⇒ Position reports no active phase."""

    def test_no_active_phase(self, tmp_path: Path, monkeypatch: Any) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "complete")])
        _write_phase(tmp_path, "1", [("TEST-001", "complete")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "abc123 story-TEST-001 complete\n")

        pos = infer_position(tmp_path)
        assert pos["active_phase_file"] is None
        assert pos["next_story_id"] is None
        assert pos["attempt_count"] == 0
        assert pos["builder_model"] is None
        assert pos["last_attempt_outcome"] == OUTCOME_NONE


class TestInferPositionActivePhase:
    """Active phase + unbuilt story + counter 0 ⇒ names the story, attempt 0, auto model."""

    def test_first_story_no_attempts(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", story_class="code", primary_files=["a.py"])
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["active_phase_file"] is not None
        assert pos["active_phase_file"].name == "phase-1.md"
        assert pos["next_story_id"] == "TEST-001"
        assert pos["attempt_count"] == 0
        assert pos["builder_model"] == "sonnet"
        assert pos["builder_model_reason"] == "auto-baseline"
        assert pos["last_attempt_outcome"] == OUTCOME_NONE


class TestResolveActivePhaseAnnotatedStatus:
    """Annotated ``complete (...)`` status rows must read as inactive (INFRA-225).

    Reproduces the ``aab`` phase-15 shape: an index row whose status carries a
    parenthetical suffix after ``complete``.  ``is_phase_inactive`` is an
    exact-membership test and would treat such a row as *active*; the ported
    ``startswith("complete")`` fallback in ``_resolve_active_phase`` must skip
    it so a genuinely later ``planned`` row is resolved as the active phase.
    """

    def test_annotated_complete_row_skipped_for_later_planned(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        annotated = (
            "complete (superseded — all 4 stories already implemented via "
            "later rebuild phases; confirmed 2026-07-07)"
        )
        _write_index(
            tmp_path,
            [
                ("15", "Phase 15", annotated),
                ("16", "Phase 16", "planned"),
            ],
        )
        _write_phase(tmp_path, "15", [("TEST-015", "complete")])
        _write_phase(tmp_path, "16", [("TEST-016", "planned")])
        _write_story(tmp_path, "TEST-016", story_class="code", primary_files=["a.py"])
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        # The annotated-complete phase-15 row must be skipped; the later planned
        # phase-16 row wins.
        assert pos["active_phase_file"] is not None
        assert pos["active_phase_file"].name == "phase-16.md"
        assert pos["next_story_id"] == "TEST-016"


class TestInferPositionPassOutcome:
    """A committed story-<ID> ⇒ outcome inferred PASS."""

    def test_commit_present_infers_pass(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned"), ("TEST-002", "planned")])
        _write_story(tmp_path, "TEST-001")
        _write_story(tmp_path, "TEST-002")
        # Counter indicates an attempt was made for TEST-002.
        _write_attempt_counter(tmp_path, "TEST-002", 1)
        # git log shows TEST-001 is committed; TEST-002 is the next unbuilt.
        _patch_git_log(monkeypatch, "abc123 story-TEST-001 committed\n")

        pos = infer_position(tmp_path)
        # next unbuilt is TEST-002
        assert pos["next_story_id"] == "TEST-002"
        # attempt_count is 1 and no commit for TEST-002 → FAIL
        assert pos["last_attempt_outcome"] == OUTCOME_FAIL


class TestInferPositionFailOutcome:
    """No commit + planned + counter advanced ⇒ outcome FAIL."""

    def test_no_commit_with_attempts_infers_fail(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _write_attempt_counter(tmp_path, "TEST-001", 2)
        # Empty git log — no commit.
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["next_story_id"] == "TEST-001"
        assert pos["attempt_count"] == 2
        assert pos["last_attempt_outcome"] == OUTCOME_FAIL
        # retry-upgrade because attempt_count >= 2 and story_class=code
        assert pos["builder_model"] == "opus"
        assert pos["builder_model_reason"] == "retry-upgrade"

    def test_fail_at_attempt_1_selects_next_attempt_model(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """CF-1 / CER-060 (DP7.2): on FAIL at attempt_count==1, infer_position
        selects the model at attempt_count + 1 (== 2) so the Position carries the
        retry tier (opus / retry-upgrade) rather than the attempt-1 model."""
        from model_selector import select_builder_model  # type: ignore[import]

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _write_attempt_counter(tmp_path, "TEST-001", 1)
        _patch_git_log(monkeypatch, "")  # no commit → FAIL

        pos = infer_position(tmp_path)
        assert pos["attempt_count"] == 1
        assert pos["last_attempt_outcome"] == OUTCOME_FAIL
        # Selected at attempt_count + 1 == 2.
        expected_model, expected_reason = select_builder_model(
            "code", [], [], attempt_number=2
        )
        assert pos["builder_model"] == expected_model == "opus"
        assert pos["builder_model_reason"] == expected_reason == "retry-upgrade"

    def test_first_launch_selects_attempt_1_model(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Regression guard: a none/first-launch Position (attempt_count == 0)
        selects the attempt-1 model — the FAIL +1 shift must not leak to Row 2."""
        from model_selector import select_builder_model  # type: ignore[import]

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["attempt_count"] == 0
        assert pos["last_attempt_outcome"] == OUTCOME_NONE
        expected_model, expected_reason = select_builder_model(
            "code", [], [], attempt_number=1
        )
        assert pos["builder_model"] == expected_model == "sonnet"
        assert pos["builder_model_reason"] == expected_reason == "auto-baseline"


class TestInferPositionGateBlocked:
    """A gate signalling blocked ⇒ Position carries that gate's blocked signal."""

    def test_stub_gate_blocked(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        # Stub story (delegation language, no ## Ensures).
        _write_story(tmp_path, "TEST-001", stub=True)
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["gate_stub"]["ok"] is False
        assert pos["gate_stub"]["blocked_reason"] != ""
        # Schema and auth gates pass for a non-schema, non-auth story.
        assert pos["gate_schema"]["ok"] is True
        assert pos["gate_auth"]["ok"] is True

    def test_auth_gate_blocked(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", auth_gated=True)
        # No architecture.md → auth gate blocked.
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["gate_auth"]["ok"] is False
        assert pos["gate_auth"]["blocked_reason"] != ""


class TestInferPositionExtractionsConsistency:
    """Extraction parity: module-level functions must be consistent with infer_position."""

    def test_resolve_current_phase_consistency(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        standalone = resolve_current_phase(tmp_path)
        pos = infer_position(tmp_path)
        assert pos["active_phase_file"] == standalone

    def test_read_attempt_count_consistency(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _write_attempt_counter(tmp_path, "TEST-001", 5)
        _patch_git_log(monkeypatch, "")

        standalone = read_attempt_count("TEST-001", tmp_path)
        pos = infer_position(tmp_path)
        assert pos["attempt_count"] == standalone == 5

    def test_gate_helper_consistency(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", stub=False, auth_gated=False)
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        standalone_stub = check_stub_gate("TEST-001", tmp_path)
        assert pos["gate_stub"]["ok"] == standalone_stub["ok"]

        standalone_auth = check_auth_gate_result("TEST-001", tmp_path)
        assert pos["gate_auth"]["ok"] == standalone_auth["ok"]


class TestInferPositionReadOnly:
    """infer_position must not write any files."""

    def test_no_new_files_written(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        # Capture the tree before.
        before = set(tmp_path.rglob("*"))
        infer_position(tmp_path)
        after = set(tmp_path.rglob("*"))

        new_files = after - before
        assert not new_files, f"infer_position wrote unexpected files: {new_files}"


# ---------------------------------------------------------------------------
# Import additions for RESOLVER-003 tests
# ---------------------------------------------------------------------------

from next_action import (  # noqa: E402
    OUTCOME_PASS,
    OUTCOME_FAIL,
    OUTCOME_NONE,
    resolve_next_action,
    validate_action,
    make_action,
    DONE,
    SPAWN_BUILDER,
    SPAWN_LOOP_BREAKER,
    SPAWN_GATE_WORKER,
    CHECKPOINT,
    CHECKPOINT_SECURITY,
    AWAIT_USER,
    route_gate_verdict,
)


# ---------------------------------------------------------------------------
# Helpers for state-machine tests
# ---------------------------------------------------------------------------


def _make_position(
    *,
    active_phase_file=None,
    next_story_id: "str | None" = None,
    attempt_count: int = 0,
    builder_model: "str | None" = "sonnet",
    builder_model_reason: "str | None" = "auto-baseline",
    gate_stub: "dict | None" = None,
    gate_schema: "dict | None" = None,
    gate_auth: "dict | None" = None,
    last_attempt_outcome: str = OUTCOME_NONE,
) -> dict:
    """Build a synthetic Position dict for state-machine tests."""
    _ok_gate = {"ok": True, "blocked_reason": ""}
    return {
        "active_phase_file": active_phase_file,
        "next_story_id": next_story_id,
        "next_story_file": None,
        "attempt_count": attempt_count,
        "builder_model": builder_model,
        "builder_model_reason": builder_model_reason,
        "gate_stub": gate_stub if gate_stub is not None else dict(_ok_gate),
        "gate_schema": gate_schema if gate_schema is not None else dict(_ok_gate),
        "gate_auth": gate_auth if gate_auth is not None else dict(_ok_gate),
        "last_attempt_outcome": last_attempt_outcome,
    }


# ---------------------------------------------------------------------------
# Tests — resolve_next_action state machine (RESOLVER-003)
# ---------------------------------------------------------------------------


class TestResolveNextActionDone:
    """Row 1: no active phase → done."""

    def test_done_when_no_active_phase(self, tmp_path: Any) -> None:
        pos = _make_position(active_phase_file=None)
        action = resolve_next_action(pos)
        assert action["action"] == DONE
        assert action["scalar"] == ""
        assert action["model"] is None
        assert action["reason"] == ""
        assert validate_action(action) == []


class TestResolveNextActionCheckpoint:
    """Row 9: active phase, no next story → checkpoint routing (RESOLVER-008)."""

    def test_checkpoint_when_phase_complete(self, tmp_path: Any) -> None:
        # RESOLVER-008: Row 9 now runs pre-checkpoint guards and emits the first
        # uncompleted checkpoint step.  Phase file has no Stories table →
        # phase-completion guard passes vacuously; CER backlog absent → passes;
        # gate_fn injected → passes.  checkpoint_step is empty → emits
        # checkpoint-security.
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_SECURITY
        assert action["scalar"] == ""
        assert action["model"] is None
        assert validate_action(action) == []

    def test_prior_phase_completed_sequence_no_longer_short_circuits_new_phase(
        self, tmp_path: Any
    ) -> None:
        """CER-066 regression: a prior phase's completed checkpoint sequence
        must not short-circuit a new phase's checkpoint to `done`.

        Before RESOLVER-017, ``_record_checkpoint_step`` never cleared
        ``state.json["checkpoint_step"]`` after recording the terminal
        ``checkpoint-tag`` step, so the list stayed at all four step names
        forever. A later phase reaching Row 9 (active phase, no next story)
        would then read that stale 4-item list and Row 9's read-only
        ``_remaining`` computation (unchanged by this story) would see no
        remaining steps and return ``done`` instead of ``checkpoint-security``.

        This test drives the real ``record-checkpoint-step`` CLI through a
        full sequence (simulating a prior phase's completed checkpoint),
        confirms the fixed write side leaves ``checkpoint_step == []``
        afterward, then feeds that (correctly reset) state into
        ``resolve_next_action`` for a new phase and asserts it returns
        ``checkpoint-security`` — not ``done``.
        """
        import json
        import subprocess
        import sys as _sys
        from pathlib import Path

        # Project layout with a real .companion/state.json, matching the
        # write-side CLI's expectations.
        project_dir = tmp_path / "sub" / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)
        state_path = companion / "state.json"
        state_path.write_text(json.dumps({"checkpoint_step": []}), encoding="utf-8")

        scripts_dir = (
            Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
        )

        for step in [
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
            "checkpoint-tag",
        ]:
            result = subprocess.run(
                [
                    _sys.executable,
                    str(scripts_dir / "flex_build.py"),
                    "record-checkpoint-step",
                    step,
                    "--project-dir",
                    str(project_dir),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr

        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["checkpoint_step"] == [], (
            "prior phase's checkpoint-tag did not reset checkpoint_step — "
            "stale carryover would short-circuit the next phase's checkpoint"
        )

        # A new phase reaches Row 9 with the now-correctly-reset checkpoint_step.
        phase_file = project_dir / "docs" / "phases" / "phase-2.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 2\n", encoding="utf-8")
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        pos["checkpoint_step"] = state["checkpoint_step"]

        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_SECURITY
        assert action["action"] != DONE
        assert validate_action(action) == []


class TestResolveNextActionSpawnBuilder:
    """Rows 2/5/8: various spawn-builder conditions."""

    def test_row_2_first_attempt_auto_model(self, tmp_path: Any) -> None:
        """Counter 0, auto model → spawn-builder attempt 1."""
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-001",
            attempt_count=0,
            builder_model="sonnet",
            builder_model_reason="auto-baseline",
            last_attempt_outcome=OUTCOME_NONE,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "TEST-001"
        assert action["model"] == "sonnet"
        assert action["reason"] == "auto-baseline"
        assert action["meta"]["attempt"] == 1
        assert validate_action(action) == []

    def test_row_5_second_attempt_retry_upgrade(self, tmp_path: Any) -> None:
        """Counter 1, FAIL → spawn-builder attempt 2 emits the Position's model.

        CF-1 / CER-060 (DP7.2): on FAIL, infer_position computes builder_model at
        the next attempt number, so the Position carries opus / retry-upgrade and
        Row 5 emits position.builder_model rather than hardcoding opus.
        """
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-002",
            attempt_count=1,
            builder_model="opus",
            builder_model_reason="retry-upgrade",
            last_attempt_outcome=OUTCOME_FAIL,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "TEST-002"
        assert action["model"] == "opus"
        assert action["reason"] == "retry-upgrade"
        assert action["meta"]["attempt"] == 2
        assert action["meta"]["fail_rung"] == "single-fail"
        assert validate_action(action) == []

    def test_row_5_emits_position_model_not_hardcoded(self, tmp_path: Any) -> None:
        """Row 5 sources the retry tier from the Position (DP7.2 single-source).

        A Position carrying a non-opus model on FAIL is emitted verbatim — proving
        Row 5 no longer hardcodes opus / retry-upgrade. The defensive fallback only
        applies when builder_model is None.
        """
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-002",
            attempt_count=1,
            builder_model="sonnet",
            builder_model_reason="sentinel-reason",
            last_attempt_outcome=OUTCOME_FAIL,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["model"] == "sonnet"
        assert action["reason"] == "sentinel-reason"

    def test_row_8_pass_more_stories(self, tmp_path: Any) -> None:
        """PASS outcome + more unbuilt stories → spawn-builder next story."""
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-003",
            attempt_count=1,
            builder_model="sonnet",
            builder_model_reason="auto-baseline",
            last_attempt_outcome=OUTCOME_PASS,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "TEST-003"
        assert action["meta"]["attempt"] == 1
        assert validate_action(action) == []


class TestResolveNextActionSpawnLoopBreaker:
    """Row 6: counter 2, FAIL → spawn-loop-breaker."""

    def test_row_6_double_fail(self, tmp_path: Any) -> None:
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-004",
            attempt_count=2,
            builder_model="opus",
            builder_model_reason="retry-upgrade",
            last_attempt_outcome=OUTCOME_FAIL,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_LOOP_BREAKER
        assert action["scalar"] == "TEST-004"
        assert action["model"] == "opus"
        assert action["meta"]["fail_rung"] == "double-fail"
        assert validate_action(action) == []


class TestResolveNextActionAwaitUser:
    """Rows 3/4/7: judgment-handoff → await-user."""

    def test_row_4_gate_stub_blocked(self, tmp_path: Any) -> None:
        """Pre-flight gate blocked → await-user reason gate-blocked:stub."""
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-005",
            gate_stub={"ok": False, "blocked_reason": "stub delegation detected"},
        )
        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["scalar"] == ""
        assert action["model"] is None
        assert action["reason"] == "gate-blocked:stub"
        assert action["meta"]["gate"] == "stub"
        assert validate_action(action) == []

    def test_row_3_prompted_upgrade(self, tmp_path: Any) -> None:
        """prompted-upgrade at counter 0 → await-user model-upgrade, suggested_model in meta."""
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-006",
            attempt_count=0,
            builder_model="opus",
            builder_model_reason="prompted-upgrade",
            last_attempt_outcome=OUTCOME_NONE,
        )
        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["reason"] == "model-upgrade"
        assert action["model"] is None
        assert action["meta"].get("suggested_model") == "opus"
        assert validate_action(action) == []

    def test_row_7_triple_fail_paused(self, tmp_path: Any) -> None:
        """Counter ≥ 3 FAIL → await-user build-paused."""
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-007",
            attempt_count=3,
            builder_model="opus",
            builder_model_reason="retry-upgrade",
            last_attempt_outcome=OUTCOME_FAIL,
        )
        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["reason"] == "build-paused"
        assert action["model"] is None
        assert validate_action(action) == []


class TestResolveNextActionWarnings:
    """Advisory signals appear in meta.warnings[] without changing the action."""

    def test_guardrail_warning_does_not_change_action(self, tmp_path: Any) -> None:
        """Guardrail-fired warning surfaces in meta.warnings[], does not block spawn."""
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-008",
            attempt_count=0,
            builder_model="sonnet",
            builder_model_reason="auto-baseline",
            last_attempt_outcome=OUTCOME_NONE,
        )
        # Without warning: spawns builder.
        action_no_warn = resolve_next_action(pos)
        assert action_no_warn["action"] == SPAWN_BUILDER

        # With guardrail-fired: still spawns builder, warning in meta.
        action_warn = resolve_next_action(pos, warnings=["guardrail-fired"])
        assert action_warn["action"] == SPAWN_BUILDER
        assert "guardrail-fired" in action_warn["meta"].get("warnings", [])
        assert validate_action(action_warn) == []

    def test_context_budget_warning_does_not_change_action(self, tmp_path: Any) -> None:
        """context-budget-exceeded advisory in meta.warnings[], action unchanged.

        RESOLVER-008: Row 9 now emits checkpoint-security (first checkpoint step).
        The warning still propagates to meta.warnings[] regardless of which action is emitted.
        """
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id=None,  # → checkpoint-security (all guards pass)
        )
        action = resolve_next_action(
            pos,
            warnings=["context-budget-exceeded"],
            gate_fn=lambda: True,
        )
        assert action["action"] == CHECKPOINT_SECURITY
        assert "context-budget-exceeded" in action["meta"].get("warnings", [])
        assert validate_action(action) == []


class TestResolveNextActionOutputValid:
    """All emitted actions pass validate_action."""

    def test_all_emitted_action_types_pass_validate(self, tmp_path: Any) -> None:
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")

        positions = [
            # done
            _make_position(),
            # checkpoint
            _make_position(active_phase_file=phase_file, next_story_id=None),
            # spawn-builder row 2
            _make_position(
                active_phase_file=phase_file,
                next_story_id="X-001",
                attempt_count=0,
                last_attempt_outcome=OUTCOME_NONE,
            ),
            # spawn-builder row 5
            _make_position(
                active_phase_file=phase_file,
                next_story_id="X-002",
                attempt_count=1,
                last_attempt_outcome=OUTCOME_FAIL,
            ),
            # spawn-loop-breaker row 6
            _make_position(
                active_phase_file=phase_file,
                next_story_id="X-003",
                attempt_count=2,
                last_attempt_outcome=OUTCOME_FAIL,
            ),
            # await-user gate-blocked
            _make_position(
                active_phase_file=phase_file,
                next_story_id="X-004",
                gate_stub={"ok": False, "blocked_reason": "stub"},
            ),
            # await-user model-upgrade
            _make_position(
                active_phase_file=phase_file,
                next_story_id="X-005",
                attempt_count=0,
                builder_model_reason="prompted-upgrade",
                last_attempt_outcome=OUTCOME_NONE,
            ),
            # await-user build-paused
            _make_position(
                active_phase_file=phase_file,
                next_story_id="X-006",
                attempt_count=3,
                last_attempt_outcome=OUTCOME_FAIL,
            ),
        ]
        for i, pos in enumerate(positions):
            action = resolve_next_action(pos)
            violations = validate_action(action)
            assert violations == [], (
                f"Position {i} produced invalid action {action['action']!r}: "
                + "; ".join(violations)
            )


# ---------------------------------------------------------------------------
# Tests — next-action CLI subcommand (RESOLVER-003)
# ---------------------------------------------------------------------------


class TestNextActionCLI:
    """Tests for the flex_build.py next-action subcommand."""

    def test_json_flag_emits_valid_action(self, tmp_path: Any, monkeypatch: Any) -> None:
        """--json emits a single JSON object that round-trips and validates."""
        from click.testing import CliRunner
        from skills.pairmode.scripts.flex_build import flex_build

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", story_class="code", primary_files=["a.py"])
        _patch_git_log(monkeypatch, "")

        runner = CliRunner()
        result = runner.invoke(
            flex_build,
            ["next-action", "--project-dir", str(tmp_path), "--json"],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        obj = json.loads(result.output.strip())
        assert isinstance(obj, dict)
        violations = validate_action(obj)
        assert violations == [], f"CLI JSON output failed validation: {violations}"
        # Round-trip
        assert json.loads(json.dumps(obj)) == obj

    def test_default_output_is_human_readable(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Default invocation prints a human-readable line (not JSON)."""
        from click.testing import CliRunner
        from skills.pairmode.scripts.flex_build import flex_build

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", story_class="code", primary_files=["a.py"])
        _patch_git_log(monkeypatch, "")

        runner = CliRunner()
        result = runner.invoke(
            flex_build,
            ["next-action", "--project-dir", str(tmp_path)],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        output = result.output.strip()
        # Human-readable line contains "action:"
        assert "action:" in output
        # Must not be a raw JSON object at the top level
        assert not output.startswith("{")

    def test_json_action_value_is_spawn_builder_for_new_story(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """For an unbuilt story with counter 0, JSON output has action=spawn-builder."""
        from click.testing import CliRunner
        from skills.pairmode.scripts.flex_build import flex_build

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", story_class="code", primary_files=["a.py"])
        _patch_git_log(monkeypatch, "")

        runner = CliRunner()
        result = runner.invoke(
            flex_build,
            ["next-action", "--project-dir", str(tmp_path), "--json"],
        )
        assert result.exit_code == 0
        obj = json.loads(result.output.strip())
        assert obj["action"] == "spawn-builder"
        assert obj["scalar"] == "TEST-001"

    def test_next_action_is_pure_read_no_files_written(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """next-action CLI must write no durable files."""
        from click.testing import CliRunner
        from skills.pairmode.scripts.flex_build import flex_build

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", story_class="code", primary_files=["a.py"])
        _patch_git_log(monkeypatch, "")

        before = set(tmp_path.rglob("*"))
        runner = CliRunner()
        runner.invoke(
            flex_build,
            ["next-action", "--project-dir", str(tmp_path), "--json"],
        )
        after = set(tmp_path.rglob("*"))
        new_files = after - before
        assert not new_files, f"next-action wrote unexpected files: {new_files}"


class TestNextActionCLISurfaceFreeze:
    """next-action command is present in the live CLI surface (addition, not removal)."""

    def test_next_action_command_present(self) -> None:
        """flex_build must expose a next-action command."""
        from skills.pairmode.scripts.flex_build import flex_build

        assert "next-action" in flex_build.commands, (
            "next-action command missing from flex_build CLI group"
        )


# ---------------------------------------------------------------------------
# Tests — RESOLVER-005: Row-4 DP2 split
# ---------------------------------------------------------------------------


def _make_phase_file(tmp_path: "Any") -> "Path":
    """Create a minimal phase file and return its Path."""
    phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
    phase_file.parent.mkdir(parents=True, exist_ok=True)
    phase_file.write_text("# Phase 1\n", encoding="utf-8")
    return phase_file


class TestResolveNextActionRow4Split:
    """Row 4 splits by DP2 boundary: stub → await-user; schema/auth → spawn-gate-worker."""

    def test_schema_tripped_emits_spawn_gate_worker(self, tmp_path: "Any") -> None:
        """schema blocked (stub clean) → spawn-gate-worker with scalar=story_id."""
        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-001",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": True, "blocked_reason": ""},
            gate_schema={"ok": False, "blocked_reason": "no management surface"},
            gate_auth={"ok": True, "blocked_reason": ""},
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_GATE_WORKER
        assert action["scalar"] == "RESOLVER-001"
        assert action["model"] is None
        assert validate_action(action) == []
        assert "schema" in action["meta"]["gates_tripped"]

    def test_auth_tripped_emits_spawn_gate_worker(self, tmp_path: "Any") -> None:
        """auth blocked (stub clean, schema ok) → spawn-gate-worker."""
        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-002",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": True, "blocked_reason": ""},
            gate_schema={"ok": True, "blocked_reason": ""},
            gate_auth={"ok": False, "blocked_reason": "no classification in architecture.md"},
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_GATE_WORKER
        assert action["scalar"] == "RESOLVER-002"
        assert action["model"] is None
        assert validate_action(action) == []
        assert "auth" in action["meta"]["gates_tripped"]

    def test_stub_tripped_emits_await_user_directly(self, tmp_path: "Any") -> None:
        """stub blocked → await-user with reason=gate-blocked:stub (no worker)."""
        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-003",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": False, "blocked_reason": "stub delegation detected"},
            gate_schema={"ok": True, "blocked_reason": ""},
            gate_auth={"ok": True, "blocked_reason": ""},
        )
        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["reason"] == "gate-blocked:stub"
        assert action["model"] is None
        assert validate_action(action) == []

    def test_no_gate_trips_falls_through_to_spawn_builder(self, tmp_path: "Any") -> None:
        """No gates tripped → falls through Row 2 → spawn-builder."""
        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-004",
            attempt_count=0,
            builder_model="sonnet",
            builder_model_reason="auto-baseline",
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": True, "blocked_reason": ""},
            gate_schema={"ok": True, "blocked_reason": ""},
            gate_auth={"ok": True, "blocked_reason": ""},
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "RESOLVER-004"
        assert validate_action(action) == []

    def test_spawn_gate_worker_validate_passes(self, tmp_path: "Any") -> None:
        """spawn-gate-worker with model=None passes validate_action."""
        action = make_action(SPAWN_GATE_WORKER, scalar="TEST-001", model=None, reason="test")
        assert validate_action(action) == []

    def test_spawn_gate_worker_with_model_fails_validate(self, tmp_path: "Any") -> None:
        """spawn-gate-worker must not carry a model; validate catches violations."""
        action = make_action(SPAWN_GATE_WORKER, scalar="TEST-001", model="sonnet", reason="test")
        violations = validate_action(action)
        assert len(violations) > 0
        assert any("model" in v for v in violations)


# ---------------------------------------------------------------------------
# Tests — RESOLVER-005: route_gate_verdict aggregation helper (DP3.2)
# ---------------------------------------------------------------------------


class TestRouteGateVerdict:
    """Injected-verdict routing via the aggregation helper (DP3.2 table)."""

    def test_single_block_emits_await_user(self) -> None:
        """{"schema": "block:..."} → await-user with reason containing gate-blocked."""
        verdict_map = {"schema": "block:missing management surface"}
        action = route_gate_verdict(verdict_map, "TEST-001")
        assert action["action"] == AWAIT_USER
        assert "gate-blocked" in action["reason"]
        assert "schema" in action["reason"]
        assert action["model"] is None
        assert validate_action(action) == []
        assert "schema" in action["meta"]["gate_block_reasons"]
        assert action["meta"]["gate_block_reasons"]["schema"] == "missing management surface"

    def test_any_block_wins_over_clean(self) -> None:
        """{"auth": "clean", "schema": "block:..."} → await-user (block wins)."""
        verdict_map = {"auth": "clean", "schema": "block:no surface story in phase"}
        action = route_gate_verdict(verdict_map, "TEST-002")
        assert action["action"] == AWAIT_USER
        assert "gate-blocked" in action["reason"]
        assert validate_action(action) == []

    def test_flag_emits_spawn_builder_with_warning(self) -> None:
        """{"auth": "flag:..."} → spawn-builder with flag reason in meta.warnings[]."""
        verdict_map = {"auth": "flag:auth check advisory only"}
        action = route_gate_verdict(verdict_map, "TEST-003")
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "TEST-003"
        warnings = action["meta"].get("warnings", [])
        assert any("gate-flag:auth" in w for w in warnings)
        assert validate_action(action) == []

    def test_all_clean_emits_spawn_builder(self) -> None:
        """{"schema": "clean", "auth": "clean"} → spawn-builder (proceed)."""
        verdict_map = {"schema": "clean", "auth": "clean"}
        action = route_gate_verdict(verdict_map, "TEST-004")
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "TEST-004"
        assert validate_action(action) == []

    def test_empty_verdict_map_emits_spawn_builder(self) -> None:
        """Empty map (no judged gates) → spawn-builder (all-clean path)."""
        action = route_gate_verdict({}, "TEST-005")
        assert action["action"] == SPAWN_BUILDER
        assert validate_action(action) == []

    def test_block_reason_carried_in_meta(self) -> None:
        """Block worker reason is accessible in meta.gate_block_reasons."""
        verdict_map = {"schema": "block:schema not resolved"}
        action = route_gate_verdict(verdict_map, "TEST-006")
        assert action["meta"]["gate_block_reasons"]["schema"] == "schema not resolved"


class TestCheckPhaseCompletionEscapedPipe:
    """INFRA-222 (CER-066 recurrence): `_check_phase_completion` must split
    Stories-table rows on unescaped pipes only, so a title cell containing an
    escaped pipe (e.g. `` `Task\\|Agent` ``) does not shred the row and shift
    the status read off its known schema position.
    """

    def test_escaped_pipe_in_title_complete(self, tmp_path: Any) -> None:
        phase_file = tmp_path / "phase-x.md"
        phase_file.write_text(
            "# Phase X\n\n"
            "## Stories\n\n"
            "| ID | Title | Status |\n"
            "|---|---|---|\n"
            "| INFRA-001 | Wire `Task\\|Agent` matcher | complete |\n",
            encoding="utf-8",
        )
        assert _check_phase_completion(phase_file) is True

    def test_escaped_pipe_in_title_planned(self, tmp_path: Any) -> None:
        phase_file = tmp_path / "phase-x.md"
        phase_file.write_text(
            "# Phase X\n\n"
            "## Stories\n\n"
            "| ID | Title | Status |\n"
            "|---|---|---|\n"
            "| INFRA-001 | Wire `Task\\|Agent` matcher | planned |\n",
            encoding="utf-8",
        )
        assert _check_phase_completion(phase_file) is False

    def test_multiple_escaped_pipes_in_title(self, tmp_path: Any) -> None:
        phase_file = tmp_path / "phase-x.md"
        phase_file.write_text(
            "# Phase X\n\n"
            "## Stories\n\n"
            "| ID | Title | Status |\n"
            "|---|---|---|\n"
            "| INFRA-002 | Register `Write\\|Edit\\|MultiEdit` block | complete |\n",
            encoding="utf-8",
        )
        assert _check_phase_completion(phase_file) is True

    def test_unaffected_rows_still_work(self, tmp_path: Any) -> None:
        phase_file = tmp_path / "phase-x.md"
        phase_file.write_text(
            "# Phase X\n\n"
            "## Stories\n\n"
            "| ID | Title | Status |\n"
            "|---|---|---|\n"
            "| INFRA-001 | Plain title | complete |\n"
            "| INFRA-002 | Another plain title | deferred |\n",
            encoding="utf-8",
        )
        assert _check_phase_completion(phase_file) is True

        phase_file.write_text(
            "# Phase X\n\n"
            "## Stories\n\n"
            "| ID | Title | Status |\n"
            "|---|---|---|\n"
            "| INFRA-001 | Plain title | complete |\n"
            "| INFRA-002 | Another plain title | planned |\n",
            encoding="utf-8",
        )
        assert _check_phase_completion(phase_file) is False

    def test_real_phase_95_live_hit(self, tmp_path: Any) -> None:
        """Regression against this story's own live-hit: phase-95.md's real
        Stories table has escaped-pipe titles on INFRA-208/INFRA-209, both
        `complete`. Pulled verbatim from the on-disk file (not hand-typed)
        so the fixture stays byte-identical to the actual triggering rows;
        INFRA-222's own row (this story, not yet complete while it is being
        built) is excluded — it is orthogonal to the escaped-pipe bug under
        test and would otherwise make this assertion depend on build-loop
        timing rather than the parsing fix.
        """
        phase_95_text = (
            _REPO_ROOT / "docs" / "phases" / "phase-95.md"
        ).read_text(encoding="utf-8")
        story_lines = [
            line
            for line in phase_95_text.splitlines()
            if line.strip().startswith("| INFRA-208")
            or line.strip().startswith("| INFRA-209")
        ]
        assert len(story_lines) == 2, "expected exactly INFRA-208 and INFRA-209 rows"

        phase_file = tmp_path / "phase-95-live-hit.md"
        phase_file.write_text(
            "# Phase 95\n\n"
            "## Stories\n\n"
            "| ID | Title | Status |\n"
            "|----|-------|--------|\n"
            + "\n".join(story_lines)
            + "\n",
            encoding="utf-8",
        )
        assert _check_phase_completion(phase_file) is True
