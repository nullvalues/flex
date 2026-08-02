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
    _run_build_gate_subprocess,
)
from flex_build import (  # noqa: E402
    resolve_current_phase,
    read_attempt_count,
    check_stub_gate,
    check_schema_gate_result,
    check_auth_gate_result,
)
import effort_db  # noqa: E402


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
    model: str | None = None,
) -> Path:
    """Write a minimal story spec.

    ``model`` (INFRA-318): optional declared ``model:`` frontmatter value —
    omitted entirely when None, so existing callers get byte-identical output.
    """
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
    model_yaml = f"model: {model}\n" if model is not None else ""
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
        f"{model_yaml}"
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


class TestInferPositionDeclaredModelFloor:
    """INFRA-318: a story-declared `model:` frontmatter field reaches
    infer_position's builder_model/builder_model_reason end-to-end — proving
    the floor via a real story file on disk, not just at the
    `select_builder_model`/`apply_declared_model_floor` function layer."""

    def test_attempt_1_declared_model_is_override(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """A story declaring `model: opus` carries opus at attempt 1, even
        though the default selection for a low-complexity code story would
        be sonnet (Ensures 2)."""
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", model="opus")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["attempt_count"] == 0
        assert pos["last_attempt_outcome"] == OUTCOME_NONE
        assert pos["builder_model"] == "opus"
        assert pos["builder_model_reason"] == "story-declared"

    def test_attempt_1_declared_model_lower_is_also_override(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Lowering is equally an outright override at attempt 1 (asymmetric
        *approval flow* happens at spec-write time, not at dispatch time)."""
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", model="haiku")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["builder_model"] == "haiku"
        assert pos["builder_model_reason"] == "story-declared"

    def test_undeclared_story_is_byte_identical(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """No `model:` field → output unchanged from pre-INFRA-318 behaviour
        (Ensures 2/5)."""
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["builder_model"] == "sonnet"
        assert pos["builder_model_reason"] == "auto-baseline"

    def test_retry_never_downgrades_below_declared_floor(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """A story declaring `model: opus` and failing attempt 1 stays at
        opus on attempt 2 — retry-upgrade already meets/exceeds the floor,
        never downgrades below it (Ensures 2, Do-not clause)."""
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", model="opus")
        _write_attempt_counter(tmp_path, "TEST-001", 1)
        _patch_git_log(monkeypatch, "")  # no commit → FAIL

        pos = infer_position(tmp_path)
        assert pos["last_attempt_outcome"] == OUTCOME_FAIL
        assert pos["builder_model"] == "opus"

    def test_resolve_next_action_spawn_builder_carries_declared_floor(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """End-to-end: infer_position → resolve_next_action's emitted
        spawn-builder action.model actually carries the declared floor, not
        just Position's internal builder_model field."""
        from next_action import resolve_next_action, SPAWN_BUILDER  # type: ignore[import]

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", model="opus")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["model"] == "opus"
        assert action["reason"] == "story-declared"

    def test_resolve_next_action_undeclared_story_unaffected(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Same end-to-end path for an undeclared story — proves the floor
        machinery is a true no-op absent the field (Ensures 5)."""
        from next_action import resolve_next_action, SPAWN_BUILDER  # type: ignore[import]

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["model"] == "sonnet"
        assert action["reason"] == "auto-baseline"

    def test_invalid_declared_model_value_is_treated_as_undeclared(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """A story with an invalid model: value (should have failed schema
        validation upstream) is treated fail-safe as undeclared, never
        guessed at or crashed on."""
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001", model="claude-4-opus-20260101")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["builder_model"] == "sonnet"
        assert pos["builder_model_reason"] == "auto-baseline"


class TestInferPositionPerKeyEscalation:
    """INFRA-282 (CER-095.3), assertion 12: with attempt_counter.json holding
    entries for two stories, each story's Position escalates on its own
    count from the same file. No source change to next_action.py is
    required — it already passes the resolved story ID to
    read_attempt_count."""

    def test_two_stories_escalate_independently_from_the_same_file(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        from flex_build import write_attempt_count  # noqa: E402

        # Write the keyed counter file directly: A absent (0), B at 2.
        write_attempt_count("INFRA-283", 2, tmp_path)

        # Phase 1: story A (INFRA-282) is next, no commit yet → FAIL,
        # attempt_count resolved as 0 even though B has an entry in the
        # same file.
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("INFRA-282", "planned")])
        _write_story(tmp_path, "INFRA-282")
        _patch_git_log(monkeypatch, "")

        pos_a = infer_position(tmp_path)
        assert pos_a["next_story_id"] == "INFRA-282"
        assert pos_a["attempt_count"] == 0
        assert pos_a["last_attempt_outcome"] == OUTCOME_NONE

        # Confirm B's entry is untouched by resolving A's position.
        from flex_build import read_attempt_count as _rac
        assert _rac("INFRA-283", tmp_path) == 2

        # Phase 2: story B (INFRA-283) is next, no commit yet → FAIL,
        # attempt_count resolved as 2 from the same counter file.
        _write_index(
            tmp_path,
            [("1", "Phase 1", "complete"), ("2", "Phase 2", "active")],
        )
        _write_phase(tmp_path, "1", [("INFRA-282", "complete")])
        _write_phase(tmp_path, "2", [("INFRA-283", "planned")])
        _write_story(tmp_path, "INFRA-283", phase="2")
        _patch_git_log(monkeypatch, "")

        pos_b = infer_position(tmp_path)
        assert pos_b["next_story_id"] == "INFRA-283"
        assert pos_b["attempt_count"] == 2
        assert pos_b["last_attempt_outcome"] == OUTCOME_FAIL


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


def _write_claude_build_md(project_dir: Path, *, intent_review: "str | None" = None) -> Path:
    """Write a minimal CLAUDE.build.md with a Build standards line (INFRA-315)."""
    lines = ["# CLAUDE.build.md\n\n", "## Checkpoint\n\n"]
    if intent_review is not None:
        lines.append(
            f"**Build standards** test_command=`pytest` | test_dir=`tests/` | "
            f"protected_paths=`(none)` | domain_isolation_rule=`(none)` | "
            f"intent_review=`{intent_review}`\n"
        )
    else:
        lines.append(
            "**Build standards** test_command=`pytest` | test_dir=`tests/` | "
            "protected_paths=`(none)` | domain_isolation_rule=`(none)`\n"
        )
    path = project_dir / "CLAUDE.build.md"
    path.write_text("".join(lines), encoding="utf-8")
    return path


class TestInferPositionPreBuildIntentReview:
    """infer_position-level fixtures for INFRA-315 (Instructions 3):
    opted-in fresh, opted-out fresh, opted-in mid-phase."""

    def test_opted_in_fresh_phase(self, tmp_path: Path, monkeypatch: Any) -> None:
        _write_claude_build_md(tmp_path, intent_review="pre-build")
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(
            tmp_path, "1", [("TEST-001", "draft"), ("TEST-002", "planned")]
        )
        _write_story(tmp_path, "TEST-001")
        _write_story(tmp_path, "TEST-002")
        _patch_git_log(monkeypatch, "")  # no commits at all

        pos = infer_position(tmp_path)
        assert pos["intent_review_opt_in"] is True
        assert pos["phase_is_fresh"] is True
        assert pos["pre_build_intent_verdict"] is None

    def test_opted_out_fresh_phase(self, tmp_path: Path, monkeypatch: Any) -> None:
        """Absent the opt-in key, phase_is_fresh may still be True but
        opt-in is False — Row PBI in resolve_next_action never fires."""
        _write_claude_build_md(tmp_path, intent_review=None)
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "draft")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["intent_review_opt_in"] is False

    def test_opted_in_but_other_value_stays_opted_out(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Any value other than the literal 'pre-build' leaves opt-in False."""
        _write_claude_build_md(tmp_path, intent_review="checkpoint-only")
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "draft")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        assert pos["intent_review_opt_in"] is False

    def test_opted_in_mid_phase_not_fresh(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Ensures 3: a phase with >=1 complete/in-progress story is never
        fresh, opted-in or not."""
        _write_claude_build_md(tmp_path, intent_review="pre-build")
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(
            tmp_path, "1", [("TEST-001", "complete"), ("TEST-002", "planned")]
        )
        _write_story(tmp_path, "TEST-001")
        _write_story(tmp_path, "TEST-002")
        _patch_git_log(monkeypatch, "abc123 story(TEST-001): done\n")

        pos = infer_position(tmp_path)
        assert pos["intent_review_opt_in"] is True
        assert pos["phase_is_fresh"] is False

    def test_opted_in_mid_phase_via_commit_evidence_not_fresh(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """A story with commit evidence but a table status still 'planned'
        is still not fresh (INFRA-297 helpers reused, Requires 4)."""
        _write_claude_build_md(tmp_path, intent_review="pre-build")
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(
            tmp_path, "1", [("TEST-001", "planned"), ("TEST-002", "planned")]
        )
        _write_story(tmp_path, "TEST-001")
        _write_story(tmp_path, "TEST-002")
        _patch_git_log(monkeypatch, "abc123 story(TEST-001): done\n")

        pos = infer_position(tmp_path)
        assert pos["phase_is_fresh"] is False

    def test_pre_build_intent_verdict_read_from_state_json(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Requires 3: durable evidence lives in state.json, phase-keyed."""
        _write_claude_build_md(tmp_path, intent_review="pre-build")
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "draft")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        (companion / "state.json").write_text(
            json.dumps({"pre_build_intent_review": {"1": "ALIGNED"}}),
            encoding="utf-8",
        )

        pos = infer_position(tmp_path)
        assert pos["pre_build_intent_verdict"] == "ALIGNED"

    def test_pre_build_intent_verdict_is_phase_scoped(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """A later fresh phase (different key) re-fires — its own key holds
        no evidence even though a sibling phase's key does."""
        _write_claude_build_md(tmp_path, intent_review="pre-build")
        _write_index(tmp_path, [("2", "Phase 2", "active")])
        _write_phase(tmp_path, "2", [("TEST-010", "draft")])
        _write_story(tmp_path, "TEST-010")
        _patch_git_log(monkeypatch, "")

        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        (companion / "state.json").write_text(
            json.dumps({"pre_build_intent_review": {"1": "ALIGNED"}}),
            encoding="utf-8",
        )

        pos = infer_position(tmp_path)
        assert pos["pre_build_intent_verdict"] is None
        assert pos["phase_is_fresh"] is True


class TestPreBuildIntentReviewOnceOnlyRoundTrip:
    """Instructions 3: the once-only round-trip, end to end through
    infer_position + resolve_next_action + the record-intent-review CLI
    write (Requires 3: the resolver is stateless per invocation — a fresh
    process re-reads the same durable evidence and resolves consistently)."""

    def test_stateless_rerun_after_recording_verdict(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        from next_action import resolve_next_action  # type: ignore[import]
        from flex_build import cmd_record_intent_review  # type: ignore[import]
        from click.testing import CliRunner

        _write_claude_build_md(tmp_path, intent_review="pre-build")
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "draft")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        # First resolution: no verdict recorded yet → spawn-intent-reviewer.
        pos_before = infer_position(tmp_path)
        action_before = resolve_next_action(pos_before)
        assert action_before["action"] == SPAWN_INTENT_REVIEWER
        assert action_before["scalar"] == "1"

        # Record the verdict via the CLI (mirrors the orchestrator's call).
        runner = CliRunner()
        result = runner.invoke(
            cmd_record_intent_review,
            ["--phase-key", "1", "--verdict", "ALIGNED", "--project-dir", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output

        # A brand-new call to infer_position (simulating a fresh process /
        # a /clear boundary) must read the durable evidence and never
        # re-emit spawn-intent-reviewer for this phase.
        pos_after = infer_position(tmp_path)
        assert pos_after["pre_build_intent_verdict"] == "ALIGNED"
        action_after = resolve_next_action(pos_after)
        assert action_after["action"] == SPAWN_BUILDER
        assert action_after["scalar"] == "TEST-001"

    def test_recorded_fail_verdict_blocks_via_await_user(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        from next_action import resolve_next_action  # type: ignore[import]
        from flex_build import cmd_record_intent_review  # type: ignore[import]
        from click.testing import CliRunner

        _write_claude_build_md(tmp_path, intent_review="pre-build")
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "draft")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        runner = CliRunner()
        result = runner.invoke(
            cmd_record_intent_review,
            ["--phase-key", "1", "--verdict", "FAIL", "--project-dir", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output

        pos = infer_position(tmp_path)
        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["reason"] == "pre-build-intent-review-flagged"


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
    SPAWN_REVIEWER,
    SPAWN_INTENT_REVIEWER,
    CHECKPOINT,
    CHECKPOINT_SECURITY,
    CHECKPOINT_INTENT,
    CHECKPOINT_TAG,
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
    intent_review_opt_in: bool = False,
    phase_is_fresh: bool = False,
    pre_build_intent_verdict: "str | None" = None,
    gate_verdict: "dict[str, str] | None" = None,
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
        # INFRA-315
        "intent_review_opt_in": intent_review_opt_in,
        "phase_is_fresh": phase_is_fresh,
        "pre_build_intent_verdict": pre_build_intent_verdict,
        # INFRA-341
        "gate_verdict": gate_verdict,
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
        # checkpoint-security.  INFRA-340: checkpoint-security now resolves a
        # real model via select_security_auditor_model (default phase_class
        # "production" → opus) instead of hardcoding model=None.
        from pathlib import Path
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_SECURITY
        assert action["scalar"] == ""
        assert action["model"] == "opus"
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

    def test_tag_without_phase_complete_never_reemits_checkpoint_security(
        self, tmp_path: Any
    ) -> None:
        """INFRA-239 regression: reproduces the exact failure mode from the
        story Context.

        Before this fix, ``record-checkpoint-step checkpoint-tag`` reset
        ``state.json["checkpoint_step"]`` to ``[]`` (RESOLVER-017) but never
        flipped the phase's ``docs/phases/index.md`` row to ``complete``. The
        same phase would therefore re-resolve as active on the next
        ``next-action`` call, ``_check_phase_completion`` would pass
        vacuously (no unbuilt stories left), the checkpoint guards would
        pass, and — because ``checkpoint_step`` had just been reset to
        ``[]`` — the resolver would re-emit ``checkpoint-security`` for a
        phase that was already tagged, forever.

        This test drives the real ``record-checkpoint-step`` CLI through a
        full checkpoint sequence against a real ``docs/phases/index.md`` +
        phase file, then feeds the real (updated) durable state through
        ``infer_position`` + ``resolve_next_action`` and asserts the
        just-tagged phase is never re-selected as active — the resolver
        must emit ``done`` (no further phases in the index), never
        ``checkpoint-security`` again.
        """
        import subprocess
        import sys as _sys

        project_dir = tmp_path / "sub" / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)
        state_path = companion / "state.json"
        state_path.write_text(json.dumps({"checkpoint_step": []}), encoding="utf-8")

        _write_index(project_dir, [("1", "Only phase", "planned")])
        # No Stories table → phase-completion guard passes vacuously.
        (project_dir / "docs" / "phases" / "phase-1.md").write_text(
            "# Phase 1\n", encoding="utf-8"
        )

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

        # The checkpoint-tag step must have flipped the index row to complete.
        index_text = (
            project_dir / "docs" / "phases" / "index.md"
        ).read_text(encoding="utf-8")
        assert "| 1 | Only phase | complete |" in index_text

        # Feed the real, updated durable state through the real read-model —
        # not a synthetic position — so the phase-selection logic
        # (_resolve_active_phase) is exercised end to end.
        pos = infer_position(project_dir)
        assert pos["active_phase_file"] is None, (
            "the just-tagged phase re-resolved as active — index write "
            "did not take effect before the next resolver call"
        )

        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] != CHECKPOINT_SECURITY, (
            "checkpoint-security was re-emitted for the just-tagged phase "
            "(INFRA-239 regression)"
        )
        assert action["action"] == DONE
        assert validate_action(action) == []

    def test_tag_without_phase_complete_advances_to_next_phase(
        self, tmp_path: Any
    ) -> None:
        """Same regression as above, but with a second phase still planned:
        next-action must advance to the next phase's first action, never
        re-emit checkpoint-security for the just-tagged phase.

        Two planned rows both present with files is exactly the multi-
        candidate condition INFRA-265 (CER-077) requires an explicit
        ``--phase-key`` for at the checkpoint-tag write — this test passes
        it, matching the mandated ``CLAUDE.build.md`` loop path (A12)."""
        import subprocess
        import sys as _sys

        project_dir = tmp_path / "sub" / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)
        state_path = companion / "state.json"
        state_path.write_text(json.dumps({"checkpoint_step": []}), encoding="utf-8")

        _write_index(
            project_dir,
            [
                ("1", "First phase", "planned"),
                ("2", "Second phase", "planned"),
            ],
        )
        (project_dir / "docs" / "phases" / "phase-1.md").write_text(
            "# Phase 1\n", encoding="utf-8"
        )
        _write_phase(project_dir, "2", [("TEST-900", "planned")])
        _write_story(project_dir, "TEST-900", phase="2")

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
                    "--phase-key",
                    "1",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr

        pos = infer_position(project_dir)
        assert pos["active_phase_file"] is not None
        assert Path(pos["active_phase_file"]).name == "phase-2.md", (
            "resolver did not advance past the just-tagged phase 1"
        )

        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] != CHECKPOINT_SECURITY
        assert action["action"] != DONE

    def test_cer_083_stamp_mismatch_ignores_stale_checkpoint_step(
        self, tmp_path: Any
    ) -> None:
        """CER-083 regression: a checkpoint_step list stamped for a *prior*
        phase must not be honoured for a newly-active phase.

        This is the exact live incident (cp99→phase-100, 2026-07-24): phase
        1's checkpoint_step held the three gate steps under
        ``checkpoint_phase="1"``; phase 1 is then marked complete and phase 2
        becomes active with no unbuilt stories. Reading the stale list
        verbatim would let the resolver resolve straight to
        ``checkpoint-tag`` for phase 2, silently skipping its gates. Asserts
        the resolver instead re-starts the checkpoint sequence at
        ``checkpoint-security``.
        """
        import subprocess
        import sys as _sys

        project_dir = tmp_path / "sub" / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)
        state_path = companion / "state.json"
        state_path.write_text(json.dumps({"checkpoint_step": []}), encoding="utf-8")

        # Phase 1 active (planned) with no Stories table (vacuous completion)
        # so record-checkpoint-step's phase resolution lands on phase 1.
        _write_index(
            project_dir,
            [
                ("1", "First phase", "planned"),
                ("2", "Second phase", "planned"),
            ],
        )
        (project_dir / "docs" / "phases" / "phase-1.md").write_text(
            "# Phase 1\n", encoding="utf-8"
        )

        scripts_dir = (
            Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
        )

        for step in ["checkpoint-security", "checkpoint-intent", "checkpoint-docs"]:
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
        assert state["checkpoint_phase"] == "1"
        assert state["checkpoint_step"] == [
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
        ]

        # Phase 1 is now complete (as if checkpoint-tag had run at some
        # earlier point without the phase-stamp fix); phase 2 has no
        # unbuilt stories, so it resolves active vacuously.
        _write_index(
            project_dir,
            [
                ("1", "First phase", "complete"),
                ("2", "Second phase", "planned"),
            ],
        )
        (project_dir / "docs" / "phases" / "phase-2.md").write_text(
            "# Phase 2\n", encoding="utf-8"
        )

        pos = infer_position(project_dir)
        assert Path(pos["active_phase_file"]).name == "phase-2.md"
        assert pos["checkpoint_step"] == [], (
            "the stale phase-1-stamped checkpoint_step was honoured for "
            "phase 2 — CER-083 regression"
        )

        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_SECURITY
        assert action["action"] != CHECKPOINT_TAG
        assert validate_action(action) == []

    def test_stamp_matching_active_phase_still_yields_checkpoint_tag(
        self, tmp_path: Any
    ) -> None:
        """A checkpoint_step list stamped with the *active* phase's own key
        is a genuine mid-checkpoint resume and must not be discarded."""
        import subprocess
        import sys as _sys

        project_dir = tmp_path / "sub" / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)
        state_path = companion / "state.json"
        state_path.write_text(json.dumps({"checkpoint_step": []}), encoding="utf-8")

        _write_index(project_dir, [("1", "Only phase", "planned")])
        (project_dir / "docs" / "phases" / "phase-1.md").write_text(
            "# Phase 1\n", encoding="utf-8"
        )

        scripts_dir = (
            Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
        )

        for step in ["checkpoint-security", "checkpoint-intent", "checkpoint-docs"]:
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
        assert state["checkpoint_phase"] == "1"

        pos = infer_position(project_dir)
        assert Path(pos["active_phase_file"]).name == "phase-1.md"
        assert pos["checkpoint_step"] == [
            "checkpoint-security",
            "checkpoint-intent",
            "checkpoint-docs",
        ], "a stamp matching the active phase must not clear the stored list"

        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_TAG
        assert validate_action(action) == []

    def test_unstamped_state_file_honours_stored_list_unchanged(
        self, tmp_path: Any
    ) -> None:
        """Backward compatibility: a state.json predating this story (no
        ``checkpoint_phase`` key at all) must keep resuming correctly —
        the stored ``checkpoint_step`` list is exposed unchanged."""
        project_dir = tmp_path / "sub" / "project"
        companion = project_dir / ".companion"
        companion.mkdir(parents=True)
        state_path = companion / "state.json"
        state_path.write_text(
            json.dumps({"checkpoint_step": ["checkpoint-security"]}),
            encoding="utf-8",
        )

        _write_index(project_dir, [("1", "Only phase", "planned")])
        (project_dir / "docs" / "phases" / "phase-1.md").write_text(
            "# Phase 1\n", encoding="utf-8"
        )

        pos = infer_position(project_dir)
        assert pos["checkpoint_step"] == ["checkpoint-security"]


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


class TestResolveNextActionPreBuildIntentReview:
    """Row PBI (INFRA-315): pre-build intent review, resolver-emitted, opt-in.

    Story fixtures (Instructions 3): opted-in fresh, opted-out fresh, opted-in
    mid-phase, plus the once-only round-trip.
    """

    def _phase_file(self, tmp_path: Path, name: str = "1") -> Path:
        phase_file = tmp_path / "docs" / "phases" / f"phase-{name}.md"
        phase_file.parent.mkdir(parents=True, exist_ok=True)
        phase_file.write_text("# Phase\n", encoding="utf-8")
        return phase_file

    def test_opted_in_fresh_no_verdict_spawns_intent_reviewer(
        self, tmp_path: Path
    ) -> None:
        """Ensures 1: opted-in + fresh + no attempts → spawn-intent-reviewer,
        scalar=phase key, model=null, reason names pre-build intent review."""
        phase_file = self._phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-001",
            attempt_count=0,
            builder_model="sonnet",
            builder_model_reason="auto-baseline",
            last_attempt_outcome=OUTCOME_NONE,
            intent_review_opt_in=True,
            phase_is_fresh=True,
            pre_build_intent_verdict=None,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_INTENT_REVIEWER
        assert action["scalar"] == "1"
        assert action["model"] is None
        assert "pre-build" in action["reason"]
        assert validate_action(action) == []

    def test_opted_out_fresh_byte_identical_to_baseline(self, tmp_path: Path) -> None:
        """Ensures 1: without the opt-in, output is byte-identical to the
        pre-INFRA-315 Row 2 resolution for the same fixture."""
        phase_file = self._phase_file(tmp_path)
        base_kwargs = dict(
            active_phase_file=phase_file,
            next_story_id="TEST-001",
            attempt_count=0,
            builder_model="sonnet",
            builder_model_reason="auto-baseline",
            last_attempt_outcome=OUTCOME_NONE,
        )
        pos_opted_out = _make_position(
            **base_kwargs,
            intent_review_opt_in=False,
            phase_is_fresh=True,
            pre_build_intent_verdict=None,
        )
        pos_no_flags = _make_position(**base_kwargs)
        action_opted_out = resolve_next_action(pos_opted_out)
        action_no_flags = resolve_next_action(pos_no_flags)
        assert action_opted_out == action_no_flags
        assert action_opted_out["action"] == SPAWN_BUILDER

    def test_opted_in_but_not_fresh_never_fires(self, tmp_path: Path) -> None:
        """Ensures 3: never mid-phase — phase_is_fresh False means the row
        never fires even when opted in, regardless of verdict state."""
        phase_file = self._phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-002",
            attempt_count=0,
            builder_model="sonnet",
            builder_model_reason="auto-baseline",
            last_attempt_outcome=OUTCOME_NONE,
            intent_review_opt_in=True,
            phase_is_fresh=False,
            pre_build_intent_verdict=None,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER

    def test_recorded_aligned_verdict_falls_through_to_spawn_builder(
        self, tmp_path: Path
    ) -> None:
        """Ensures 2: after the review outcome (ALIGNED) is recorded, the same
        fixture resolves to spawn-builder — the emission fires once."""
        phase_file = self._phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-001",
            attempt_count=0,
            builder_model="sonnet",
            builder_model_reason="auto-baseline",
            last_attempt_outcome=OUTCOME_NONE,
            intent_review_opt_in=True,
            phase_is_fresh=True,
            pre_build_intent_verdict="ALIGNED",
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "TEST-001"

    def test_recorded_pass_verdict_also_falls_through(self, tmp_path: Path) -> None:
        phase_file = self._phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-001",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            intent_review_opt_in=True,
            phase_is_fresh=True,
            pre_build_intent_verdict="PASS",
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER

    def test_recorded_fail_verdict_routes_to_await_user(self, tmp_path: Path) -> None:
        """Ensures 4: verdict routing is advisory-block, not silent — a FAIL/
        flag verdict routes to await-user (spec drift is an operator decision)."""
        phase_file = self._phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-001",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            intent_review_opt_in=True,
            phase_is_fresh=True,
            pre_build_intent_verdict="FAIL",
        )
        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["reason"] == "pre-build-intent-review-flagged"
        assert action["meta"]["pre_build_intent_verdict"] == "FAIL"
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
        assert action["model"] == "fable"
        assert action["meta"]["fail_rung"] == "double-fail"
        assert validate_action(action) == []

    def test_row_6_double_fail_surfaces_recorded_fail_cause(
        self, tmp_path: Any
    ) -> None:
        """INFRA-328: a recorded FAIL-attempt fail_cause is surfaced in reason."""
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        effort_db.insert_attempt(
            db_path,
            story_id="TEST-005",
            agent_role="builder",
            attempt_number=1,
            ts="2026-07-29T00:00:00+00:00",
            outcome=OUTCOME_FAIL,
            notes="FAIL-CAUSE: undeclared file write, skills/pairmode/scripts/foo.py:42",
        )
        effort_db.insert_attempt(
            db_path,
            story_id="TEST-005",
            agent_role="builder",
            attempt_number=2,
            ts="2026-07-29T01:00:00+00:00",
            outcome=OUTCOME_FAIL,
            notes="FAIL-CAUSE: test regression, tests/pairmode/test_foo.py:10",
        )

        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-005",
            attempt_count=2,
            builder_model="opus",
            builder_model_reason="retry-upgrade",
            last_attempt_outcome=OUTCOME_FAIL,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_LOOP_BREAKER
        assert action["scalar"] == "TEST-005"
        assert (
            action["reason"]
            == "FAIL-CAUSE: test regression, tests/pairmode/test_foo.py:10"
        )
        assert validate_action(action) == []

    def test_row_6_double_fail_no_recorded_fail_cause_falls_back_empty(
        self, tmp_path: Any
    ) -> None:
        """INFRA-328: no effort.db / no FAIL rows / no notes → reason="" (fail-open)."""
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")

        # No effort.db at all — the pre-INFRA-328 default behaviour.
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="TEST-006",
            attempt_count=2,
            builder_model="opus",
            builder_model_reason="retry-upgrade",
            last_attempt_outcome=OUTCOME_FAIL,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_LOOP_BREAKER
        assert action["scalar"] == "TEST-006"
        assert action["reason"] == ""
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


class TestResolveNextActionNeverEmitsSpawnReviewer:
    """CER-074 invariant: resolve_next_action never emits spawn-reviewer.

    The reviewer dispatch is intra-cycle — the orchestrator dispatches the
    reviewer itself inside the same spawn-builder iteration (one next-action
    poll per story). SPAWN_REVIEWER stays in ACTIONS/_SPAWN_ACTIONS for
    orchestrator dispatch, but no resolver code path may construct it. This
    test pins that invariant across every distinct position shape so a
    future story cannot quietly start emitting it without noticing the
    one-iteration-per-story contract (see docs/agreements/HARNESS003-main.md
    and docs/architecture.md § Pairmode build loop).
    """

    @pytest.mark.parametrize(
        "shape",
        [
            "no-active-phase",
            "first-attempt",
            "post-fail-retry",
            "escalated-retry",
            "gate-blocked",
            "checkpoint-sequence",
        ],
    )
    def test_resolver_never_emits_spawn_reviewer(
        self, shape: str, tmp_path: Any
    ) -> None:
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")

        if shape == "no-active-phase":
            # No active story / phase complete: everything done.
            pos = _make_position(active_phase_file=None)
            action = resolve_next_action(pos)
        elif shape == "first-attempt":
            pos = _make_position(
                active_phase_file=phase_file,
                next_story_id="TEST-074",
                attempt_count=0,
                last_attempt_outcome=OUTCOME_NONE,
            )
            action = resolve_next_action(pos)
        elif shape == "post-fail-retry":
            # attempt_count 1, no story commit → FAIL inference, retry.
            pos = _make_position(
                active_phase_file=phase_file,
                next_story_id="TEST-074",
                attempt_count=1,
                builder_model="opus",
                builder_model_reason="retry-upgrade",
                last_attempt_outcome=OUTCOME_FAIL,
            )
            action = resolve_next_action(pos)
        elif shape == "escalated-retry":
            pos = _make_position(
                active_phase_file=phase_file,
                next_story_id="TEST-074",
                attempt_count=2,
                builder_model="opus",
                builder_model_reason="retry-upgrade",
                last_attempt_outcome=OUTCOME_FAIL,
            )
            action = resolve_next_action(pos)
        elif shape == "gate-blocked":
            pos = _make_position(
                active_phase_file=phase_file,
                next_story_id="TEST-074",
                gate_stub={"ok": False, "blocked_reason": "stub detected"},
            )
            action = resolve_next_action(pos)
        else:  # checkpoint-sequence
            pos = _make_position(
                active_phase_file=phase_file, next_story_id=None
            )
            action = resolve_next_action(pos, gate_fn=lambda: True)

        assert action["action"] != SPAWN_REVIEWER, (
            f"resolve_next_action emitted spawn-reviewer for shape {shape!r} — "
            "the CER-074 one-iteration-per-story contract forbids a "
            "resolver-emitted reviewer dispatch"
        )
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

    def test_infra265_two_active_rows_exits_2_no_traceback(self, tmp_path: Any) -> None:
        """INFRA-265 (CER-077, A11): a two-'active' index makes infer_position
        raise AmbiguousActivePhaseError; the next-action --json CLI catches it
        at the boundary and exits 2 without a traceback.

        Uses the bare ``flex_build`` module (imported via the sys.path
        bootstrap at the top of this file) rather than the dotted
        ``skills.pairmode.scripts.flex_build`` path — ``next_action.py``'s
        lazy import of ``AmbiguousActivePhaseError`` resolves against the
        bare module, and the two import paths produce distinct module
        objects (and therefore distinct exception classes) under pytest's
        import machinery."""
        from click.testing import CliRunner
        from flex_build import flex_build

        _write_index(
            tmp_path,
            [
                ("1", "First phase", "active"),
                ("2", "Second phase", "active"),
            ],
        )
        (tmp_path / "docs" / "phases" / "phase-1.md").write_text(
            "# Phase 1\n", encoding="utf-8"
        )
        (tmp_path / "docs" / "phases" / "phase-2.md").write_text(
            "# Phase 2\n", encoding="utf-8"
        )

        runner = CliRunner()
        result = runner.invoke(
            flex_build,
            ["next-action", "--project-dir", str(tmp_path), "--json"],
        )
        assert result.exit_code == 2, result.output
        assert "1" in result.output
        assert "2" in result.output
        assert "Traceback (most recent call last)" not in result.output


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

    def test_gate_worker_model_meta_keys_absent(self, tmp_path: "Any") -> None:
        """INFRA-340: no gate-worker model selector is called from Row 4b —
        the two advisory meta keys INFRA-333 added are absent under any
        phase_class, not merely falsy."""
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True, exist_ok=True)
        phase_file.write_text(
            "---\nphase_class: docs-only\n---\n# Phase 1\n", encoding="utf-8"
        )
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-005A",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": True, "blocked_reason": ""},
            gate_schema={"ok": False, "blocked_reason": "no management surface"},
            gate_auth={"ok": True, "blocked_reason": ""},
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_GATE_WORKER
        assert action["model"] is None
        assert "gate_worker_model" not in action["meta"]
        assert "gate_worker_model_reason" not in action["meta"]
        assert validate_action(action) == []


# ---------------------------------------------------------------------------
# Tests — INFRA-341: Row 4b consumes a recorded gate verdict (livelock fix)
# ---------------------------------------------------------------------------


class TestResolveNextActionRow4bGateVerdict:
    """Row 4b: once a gate verdict is recorded, route_gate_verdict's DP3.2
    aggregation resolves the action instead of re-emitting
    spawn-gate-worker (closes the INFRA-331 livelock, F8)."""

    def test_no_verdict_recorded_still_spawns_gate_worker(
        self, tmp_path: "Any"
    ) -> None:
        """Unchanged behavior: judged-tripped + gate_verdict None → spawn
        the worker, exactly as before this story."""
        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-010",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": True, "blocked_reason": ""},
            gate_schema={"ok": False, "blocked_reason": "no management surface"},
            gate_auth={"ok": True, "blocked_reason": ""},
            gate_verdict=None,
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_GATE_WORKER
        assert action["scalar"] == "RESOLVER-010"
        assert validate_action(action) == []

    def test_recorded_block_verdict_routes_to_await_user(
        self, tmp_path: "Any"
    ) -> None:
        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-011",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": True, "blocked_reason": ""},
            gate_schema={"ok": False, "blocked_reason": "no management surface"},
            gate_auth={"ok": True, "blocked_reason": ""},
            gate_verdict={
                "schema": "block:no-management-surface",
                "auth": "clean",
                "stub": "clean",
            },
        )
        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["reason"].startswith("gate-blocked:")
        assert "schema" in action["reason"]
        assert validate_action(action) == []

    def test_recorded_clean_verdict_routes_to_spawn_builder(
        self, tmp_path: "Any"
    ) -> None:
        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-012",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": True, "blocked_reason": ""},
            gate_schema={"ok": False, "blocked_reason": "no management surface"},
            gate_auth={"ok": True, "blocked_reason": ""},
            gate_verdict={"schema": "clean", "auth": "clean", "stub": "clean"},
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "RESOLVER-012"
        assert validate_action(action) == []

    def test_recorded_verdict_carries_gates_tripped_meta(
        self, tmp_path: "Any"
    ) -> None:
        """route_gate_verdict is called with the same gates_tripped/
        gate_reasons meta Row 4b already builds, not a bare dict."""
        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-013",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
            gate_stub={"ok": True, "blocked_reason": ""},
            gate_schema={"ok": False, "blocked_reason": "no management surface"},
            gate_auth={"ok": False, "blocked_reason": "no classification"},
            gate_verdict={"schema": "clean", "auth": "clean", "stub": "clean"},
        )
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert sorted(action["meta"]["gates_tripped"]) == ["auth", "schema"]
        assert "gate_reasons" in action["meta"]


# ---------------------------------------------------------------------------
# Tests — INFRA-341: record-gate-verdict CLI round-trip (livelock fix)
# ---------------------------------------------------------------------------


class TestGateVerdictOnceOnlyRoundTrip:
    """The once-only round-trip, end to end through infer_position +
    resolve_next_action + the record-gate-verdict CLI write (mirrors
    TestPreBuildIntentReviewOnceOnlyRoundTrip's pattern for the pre-build
    intent-review verdict). Reviewer negative check (e): proves the
    livelock is closed via a real fresh-process re-read, not merely that
    the helper functions are importable."""

    def test_stateless_rerun_after_recording_block_verdict(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        from next_action import resolve_next_action  # type: ignore[import]
        from flex_build import cmd_record_gate_verdict  # type: ignore[import]
        from click.testing import CliRunner

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-341A", "draft")])
        _write_story(tmp_path, "TEST-341A", schema_introduces=True)
        _patch_git_log(monkeypatch, "")

        # First resolution: no verdict recorded yet → spawn-gate-worker.
        pos_before = infer_position(tmp_path)
        assert pos_before["gate_verdict"] is None
        action_before = resolve_next_action(pos_before)
        assert action_before["action"] == SPAWN_GATE_WORKER
        assert action_before["scalar"] == "TEST-341A"

        # Record the worker's (real, two-key) verdict via the CLI (mirrors
        # the orchestrator piping the worker's stdout to the CLI's stdin).
        runner = CliRunner()
        result = runner.invoke(
            cmd_record_gate_verdict,
            ["--story-id", "TEST-341A", "--project-dir", str(tmp_path)],
            input=json.dumps(
                {"schema": "block:no-management-surface", "auth": "clean"}
            ),
        )
        assert result.exit_code == 0, result.output

        # A brand-new call to infer_position (simulating a fresh process / a
        # /clear boundary) must read the durable evidence and resolve to
        # await-user instead of re-emitting spawn-gate-worker again — this
        # is the livelock fix itself, not just a helper-function unit test.
        pos_after = infer_position(tmp_path)
        assert pos_after["gate_verdict"] == {
            "schema": "block:no-management-surface",
            "auth": "clean",
            "stub": "clean",
        }
        action_after = resolve_next_action(pos_after)
        assert action_after["action"] == AWAIT_USER
        assert action_after["reason"].startswith("gate-blocked:")

    def test_stateless_rerun_after_recording_clean_verdict(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        from next_action import resolve_next_action  # type: ignore[import]
        from flex_build import cmd_record_gate_verdict  # type: ignore[import]
        from click.testing import CliRunner

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-341B", "draft")])
        _write_story(tmp_path, "TEST-341B", schema_introduces=True)
        _patch_git_log(monkeypatch, "")

        pos_before = infer_position(tmp_path)
        action_before = resolve_next_action(pos_before)
        assert action_before["action"] == SPAWN_GATE_WORKER

        runner = CliRunner()
        result = runner.invoke(
            cmd_record_gate_verdict,
            ["--story-id", "TEST-341B", "--project-dir", str(tmp_path)],
            input=json.dumps({"schema": "clean", "auth": "clean"}),
        )
        assert result.exit_code == 0, result.output

        pos_after = infer_position(tmp_path)
        action_after = resolve_next_action(pos_after)
        assert action_after["action"] == SPAWN_BUILDER
        assert action_after["scalar"] == "TEST-341B"


class TestRecordGateVerdictStubInjection:
    """record-gate-verdict's CLI-boundary stub-default-injection (Ensures 3):
    a real gate-worker's raw two-key stdout must not fail-close via
    parse_worker_verdict_json's 3-key requirement."""

    def test_missing_stub_key_defaults_to_clean(self, tmp_path: Path) -> None:
        from flex_build import cmd_record_gate_verdict  # type: ignore[import]
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cmd_record_gate_verdict,
            ["--story-id", "TEST-341C", "--project-dir", str(tmp_path)],
            input=json.dumps({"schema": "clean", "auth": "block:no-owner-check"}),
        )
        assert result.exit_code == 0, result.output
        state = json.loads(
            (tmp_path / ".companion" / "state.json").read_text(encoding="utf-8")
        )
        assert state["gate_verdict"]["TEST-341C"] == {
            "schema": "clean",
            "auth": "block:no-owner-check",
            "stub": "clean",
        }

    def test_explicit_non_clean_stub_is_not_overridden(self, tmp_path: Path) -> None:
        from flex_build import cmd_record_gate_verdict  # type: ignore[import]
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cmd_record_gate_verdict,
            ["--story-id", "TEST-341D", "--project-dir", str(tmp_path)],
            input=json.dumps(
                {"schema": "clean", "auth": "clean", "stub": "block:stub-detected"}
            ),
        )
        assert result.exit_code == 0, result.output
        state = json.loads(
            (tmp_path / ".companion" / "state.json").read_text(encoding="utf-8")
        )
        assert state["gate_verdict"]["TEST-341D"]["stub"] == "block:stub-detected"

    def test_malformed_json_fail_closes_but_exits_zero(self, tmp_path: Path) -> None:
        from flex_build import cmd_record_gate_verdict  # type: ignore[import]
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cmd_record_gate_verdict,
            ["--story-id", "TEST-341E", "--project-dir", str(tmp_path)],
            input="not json at all",
        )
        assert result.exit_code == 0, result.output
        state = json.loads(
            (tmp_path / ".companion" / "state.json").read_text(encoding="utf-8")
        )
        assert state["gate_verdict"]["TEST-341E"] == {
            "schema": "block:malformed-verdict",
            "auth": "block:malformed-verdict",
            "stub": "block:malformed-verdict",
        }


# ---------------------------------------------------------------------------
# Tests — INFRA-333: Row 9 checkpoint-docs model wiring
# ---------------------------------------------------------------------------


class TestCheckpointDocsModelWiring:
    def test_checkpoint_docs_step_carries_selected_model(self, tmp_path: "Any") -> None:
        """When checkpoint-docs is the next uncompleted step, its model is
        resolved via select_docs_reviewer_model instead of staying None."""
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True, exist_ok=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        pos["checkpoint_step"] = ["checkpoint-security", "checkpoint-intent"]
        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == "checkpoint-docs"
        # default phase_class ("production") → sonnet, non-production-class
        assert action["model"] == "sonnet"
        assert action["reason"] == ""
        assert validate_action(action) == []

    def test_checkpoint_docs_model_varies_with_pre_pr_phase_class(
        self, tmp_path: "Any"
    ) -> None:
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True, exist_ok=True)
        phase_file.write_text(
            "---\nphase_class: pre-pr\n---\n# Phase 1\n", encoding="utf-8"
        )
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        pos["checkpoint_step"] = ["checkpoint-security", "checkpoint-intent"]
        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == "checkpoint-docs"
        assert action["model"] == "opus"
        assert validate_action(action) == []

    def test_checkpoint_security_step_resolves_selected_model(
        self, tmp_path: "Any"
    ) -> None:
        """INFRA-340: checkpoint-security resolves a real model via
        select_security_auditor_model instead of hardcoding model=None."""
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True, exist_ok=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_SECURITY
        # default phase_class ("production") → opus, production-class
        assert action["model"] == "opus"
        assert validate_action(action) == []

    def test_checkpoint_security_model_varies_with_docs_only_phase_class(
        self, tmp_path: "Any"
    ) -> None:
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True, exist_ok=True)
        phase_file.write_text(
            "---\nphase_class: docs-only\n---\n# Phase 1\n", encoding="utf-8"
        )
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_SECURITY
        assert action["model"] == "sonnet"
        assert validate_action(action) == []

    def test_checkpoint_intent_step_resolves_selected_model(
        self, tmp_path: "Any"
    ) -> None:
        """INFRA-340: checkpoint-intent resolves a real model via
        select_intent_reviewer_model instead of hardcoding model=None."""
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True, exist_ok=True)
        phase_file.write_text("# Phase 1\n", encoding="utf-8")
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        pos["checkpoint_step"] = ["checkpoint-security"]
        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_INTENT
        # default phase_class ("production") → sonnet, non-production-class
        assert action["model"] == "sonnet"
        assert validate_action(action) == []

    def test_checkpoint_intent_model_varies_with_pre_pr_phase_class(
        self, tmp_path: "Any"
    ) -> None:
        phase_file = tmp_path / "docs" / "phases" / "phase-1.md"
        phase_file.parent.mkdir(parents=True, exist_ok=True)
        phase_file.write_text(
            "---\nphase_class: pre-pr\n---\n# Phase 1\n", encoding="utf-8"
        )
        pos = _make_position(active_phase_file=phase_file, next_story_id=None)
        pos["checkpoint_step"] = ["checkpoint-security"]
        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] == CHECKPOINT_INTENT
        assert action["model"] == "opus"
        assert validate_action(action) == []


# ---------------------------------------------------------------------------
# Tests — INFRA-333: Row 2 spawn-spec-writer model wiring
# ---------------------------------------------------------------------------


class TestSpawnSpecWriterModelWiring:
    def test_needs_spec_resolves_opus_via_selector(self, tmp_path: "Any") -> None:
        """Row 2's spawn-spec-writer now calls select_spec_writer_model instead
        of hardcoding model="opus" — the resolved value is unchanged (opus)."""
        from next_action import SPAWN_SPEC_WRITER  # type: ignore[import]

        phase_file = _make_phase_file(tmp_path)
        pos = _make_position(
            active_phase_file=phase_file,
            next_story_id="RESOLVER-009",
            attempt_count=0,
            last_attempt_outcome=OUTCOME_NONE,
        )
        pos["needs_spec"] = True
        pos["story_class"] = "doc"
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_SPEC_WRITER
        assert action["model"] == "opus"
        assert action["reason"] == "needs-spec"
        assert validate_action(action) == []


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


# ---------------------------------------------------------------------------
# _run_build_gate_subprocess — config-driven test_command (INFRA-230 / CER-072)
# ---------------------------------------------------------------------------


class TestRunBuildGateSubprocess:
    """Build gate honors ``.companion/pairmode_context.json``'s ``test_command``.

    Regression coverage for CER-072: the guard hardcoded flex-only
    ``uv run pytest tests/pairmode/`` and returned gate-red in every fleet
    project that lacks that directory.  These tests use trivial always-pass
    (``true``) / always-fail (``false``) shell commands to stay fast and
    dependency-free.
    """

    @staticmethod
    def _write_context(project_dir: Path, test_command: object) -> None:
        companion = project_dir / ".companion"
        companion.mkdir(parents=True, exist_ok=True)
        (companion / "pairmode_context.json").write_text(
            json.dumps({"test_command": test_command}),
            encoding="utf-8",
        )

    def test_config_passing_command_gate_green(self, tmp_path: Path) -> None:
        """(a) pairmode_context.json + passing test_command → gate green."""
        self._write_context(tmp_path, "true")
        assert _run_build_gate_subprocess(tmp_path) is True

    def test_config_failing_command_gate_red(self, tmp_path: Path) -> None:
        """(b) pairmode_context.json + failing test_command → gate red.

        Confirms the fix does NOT turn the guard into an unconditional advisory
        pass: a command that genuinely ran and exited non-zero reports red.
        """
        self._write_context(tmp_path, "false")
        assert _run_build_gate_subprocess(tmp_path) is False

    def test_no_context_falls_back_to_pytest(self, tmp_path: Path) -> None:
        """(c) no pairmode_context.json → falls back to hardcoded pytest.

        Asserts the fallback runs the exact historical command (list form,
        no shell) via a mocked ``subprocess.run`` so the existing flex-harness
        gate behavior is provably unchanged.
        """
        assert not (tmp_path / ".companion" / "pairmode_context.json").exists()

        captured: dict = {}

        def _fake_run(*args, **kwargs):
            captured["cmd"] = args[0]
            captured["shell"] = kwargs.get("shell", False)

            class _R:
                returncode = 0

            return _R()

        with mock.patch("subprocess.run", side_effect=_fake_run):
            result = _run_build_gate_subprocess(tmp_path)

        assert result is True
        assert captured["cmd"] == [
            "uv",
            "run",
            "pytest",
            "tests/pairmode/",
            "-q",
            "--tb=no",
        ]
        assert captured["shell"] is False

    def test_malformed_context_falls_back_to_pytest(self, tmp_path: Path) -> None:
        """(d) malformed/empty test_command → falls back to pytest, no crash."""
        companion = tmp_path / ".companion"
        companion.mkdir(parents=True, exist_ok=True)

        captured: dict = {}

        def _fake_run(*args, **kwargs):
            captured["cmd"] = args[0]
            captured["shell"] = kwargs.get("shell", False)

            class _R:
                returncode = 0

            return _R()

        # invalid JSON
        (companion / "pairmode_context.json").write_text("{not json", encoding="utf-8")
        with mock.patch("subprocess.run", side_effect=_fake_run):
            assert _run_build_gate_subprocess(tmp_path) is True
        assert captured["cmd"][0] == "uv" and captured["shell"] is False

        # missing test_command field
        (companion / "pairmode_context.json").write_text("{}", encoding="utf-8")
        captured.clear()
        with mock.patch("subprocess.run", side_effect=_fake_run):
            assert _run_build_gate_subprocess(tmp_path) is True
        assert captured["cmd"][0] == "uv" and captured["shell"] is False

        # blank test_command
        self._write_context(tmp_path, "   ")
        captured.clear()
        with mock.patch("subprocess.run", side_effect=_fake_run):
            assert _run_build_gate_subprocess(tmp_path) is True
        assert captured["cmd"][0] == "uv" and captured["shell"] is False


# ---------------------------------------------------------------------------
# Resolver-level integration coverage for the attempt-counter write path
# (INFRA-237). Drives bump_attempt_count (the real writer used by
# subagent_transcript.record_attempt_from_transcript on builder/reviewer
# FAIL) end-to-end through infer_position + resolve_next_action, rather than
# a synthetic Position dict — proves the write path and the resolver's read
# path actually agree.
# ---------------------------------------------------------------------------


class TestAttemptCounterWritePathIntegration:
    def test_two_consecutive_fails_route_to_spawn_loop_breaker(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        from flex_build import bump_attempt_count  # type: ignore[import]

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-237", "planned")])
        _write_story(tmp_path, "TEST-237", story_class="code")
        _patch_git_log(monkeypatch, "")  # no commit — story never landed

        # Simulate a builder/reviewer FAIL twice, exactly as
        # subagent_transcript.record_attempt_from_transcript does.
        assert bump_attempt_count("TEST-237", tmp_path) == 1
        assert bump_attempt_count("TEST-237", tmp_path) == 2

        pos = infer_position(tmp_path)
        assert pos["attempt_count"] == 2
        assert pos["last_attempt_outcome"] == OUTCOME_FAIL

        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_LOOP_BREAKER
        assert action["scalar"] == "TEST-237"
        assert validate_action(action) == []

    def test_three_consecutive_fails_route_to_await_user_build_paused(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        from flex_build import bump_attempt_count  # type: ignore[import]

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-238", "planned")])
        _write_story(tmp_path, "TEST-238", story_class="code")
        _patch_git_log(monkeypatch, "")

        for expected in (1, 2, 3):
            assert bump_attempt_count("TEST-238", tmp_path) == expected

        pos = infer_position(tmp_path)
        assert pos["attempt_count"] == 3
        assert pos["last_attempt_outcome"] == OUTCOME_FAIL

        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["reason"] == "build-paused"
        assert validate_action(action) == []

    def test_merge_clears_counter_so_next_story_starts_fresh(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """A cleared counter (post-merge) does not leak a stale FAIL count
        onto the next story: once ``find_next_story`` advances past the
        landed commit, the next story's own (unwritten) counter reads 0 —
        fresh first-launch (Row 2), not a carried-over retry tier."""
        from flex_build import bump_attempt_count, clear_attempt_count  # type: ignore[import]

        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(
            tmp_path, "1", [("TEST-239", "planned"), ("TEST-240", "planned")]
        )
        _write_story(tmp_path, "TEST-239", story_class="code")
        _write_story(tmp_path, "TEST-240", story_class="code")

        # TEST-239 failed once, then landed (merge-story-worktree clears it).
        bump_attempt_count("TEST-239", tmp_path)
        counter_path = tmp_path / ".companion" / "attempt_counter.json"
        assert counter_path.exists()
        clear_attempt_count(tmp_path)
        assert not counter_path.exists()
        _patch_git_log(monkeypatch, "abc123 story-TEST-239 committed\n")

        pos = infer_position(tmp_path)
        assert pos["next_story_id"] == "TEST-240"
        assert pos["attempt_count"] == 0
        assert pos["last_attempt_outcome"] == OUTCOME_NONE

        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "TEST-240"
        assert action["meta"]["attempt"] == 1


# ---------------------------------------------------------------------------
# Tests — claimed-story resolver support (CER-095.1, INFRA-280)
# ---------------------------------------------------------------------------


class TestInferPositionClaimedStories:
    """A6: the three claim keys are present on every Position."""

    def test_keys_present_with_no_active_phase(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        # No docs/phases at all → active_phase_file is None.
        pos = infer_position(tmp_path)
        assert pos["active_phase_file"] is None
        assert pos["claimed_stories"] == []
        assert pos["claimed_skipped"] == []
        assert pos["all_stories_claimed"] is False

    def test_keys_present_and_populated_with_active_phase(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(
            tmp_path, "1", [("TEST-001", "planned"), ("TEST-002", "planned")]
        )
        _write_story(tmp_path, "TEST-001")
        _write_story(tmp_path, "TEST-002")
        _patch_git_log(monkeypatch, "")

        wt_root = tmp_path / ".pairmode-worktrees"
        (wt_root / "TEST-001").mkdir(parents=True)

        pos = infer_position(tmp_path)
        assert pos["claimed_stories"] == ["TEST-001"]
        assert pos["next_story_id"] == "TEST-002"
        assert pos["claimed_skipped"] == ["TEST-001"]
        assert pos["all_stories_claimed"] is False


class TestInferPositionAllStoriesClaimed:
    """A7: "all remaining claimed" is distinguished from "phase complete"."""

    def test_all_remaining_claimed_sets_flag_true(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        (tmp_path / ".pairmode-worktrees" / "TEST-001").mkdir(parents=True)

        pos = infer_position(tmp_path)
        assert pos["next_story_id"] is None
        assert pos["all_stories_claimed"] is True
        assert pos["claimed_stories"] == ["TEST-001"]
        assert pos["claimed_skipped"] == ["TEST-001"]

    def test_genuinely_complete_phase_leaves_flag_false(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "complete")])
        _write_phase(tmp_path, "1", [("TEST-001", "complete")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "abc123 story-TEST-001 complete\n")

        pos = infer_position(tmp_path)
        assert pos["next_story_id"] is None
        assert pos["all_stories_claimed"] is False
        assert pos["claimed_stories"] == []


class TestResolveNextActionAllStoriesClaimed:
    """A8: the resolver refuses to checkpoint a phase that is still building."""

    def test_await_user_all_stories_claimed_before_row_9(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")
        (tmp_path / ".pairmode-worktrees" / "TEST-001").mkdir(parents=True)

        pos = infer_position(tmp_path)

        def _guard_should_not_fire(*_a: Any, **_kw: Any) -> dict:
            raise AssertionError(
                "check_checkpoint_guards must not be called when "
                "all_stories_claimed is True"
            )

        import next_action as _na  # type: ignore[import]

        monkeypatch.setattr(_na, "check_checkpoint_guards", _guard_should_not_fire)

        action = resolve_next_action(pos)
        assert action["action"] == AWAIT_USER
        assert action["scalar"] == ""
        assert action["model"] is None
        assert action["reason"] == "all-stories-claimed"
        assert action["meta"]["claimed_stories"] == ["TEST-001"]
        assert validate_action(action) == []

    def test_row_9_checkpoint_still_fires_when_nothing_claimed(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """Sanity check: with no claims, Row 9's normal checkpoint routing
        (not all-stories-claimed) is what fires."""
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "complete")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "abc123 story-TEST-001 complete\n")

        pos = infer_position(tmp_path)
        assert pos["all_stories_claimed"] is False

        action = resolve_next_action(pos, gate_fn=lambda: True)
        assert action["action"] != AWAIT_USER or action["reason"] != "all-stories-claimed"


class TestNextActionThreePollSequence:
    """A9: consecutive polls offer different stories as claims accrue."""

    def test_offer_a_then_b_then_await_user(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(
            tmp_path, "1", [("TEST-101", "planned"), ("TEST-102", "planned")]
        )
        _write_story(tmp_path, "TEST-101")
        _write_story(tmp_path, "TEST-102")
        _patch_git_log(monkeypatch, "")

        # Poll 1 — nothing claimed, A is offered.
        pos1 = infer_position(tmp_path)
        action1 = resolve_next_action(pos1)
        assert action1["action"] == SPAWN_BUILDER
        assert action1["scalar"] == "TEST-101"
        assert "claimed_skipped" not in action1["meta"]

        # Claim A (simulating create-story-worktree).
        (tmp_path / ".pairmode-worktrees" / "TEST-101").mkdir(parents=True)

        # Poll 2 — A is claimed, B is offered, claimed_skipped names A.
        pos2 = infer_position(tmp_path)
        action2 = resolve_next_action(pos2)
        assert action2["action"] == SPAWN_BUILDER
        assert action2["scalar"] == "TEST-102"
        assert action2["meta"]["claimed_skipped"] == ["TEST-101"]

        # Claim B too.
        (tmp_path / ".pairmode-worktrees" / "TEST-102").mkdir(parents=True)

        # Poll 3 — everything claimed → await-user/all-stories-claimed.
        pos3 = infer_position(tmp_path)
        action3 = resolve_next_action(pos3)
        assert action3["action"] == AWAIT_USER
        assert action3["reason"] == "all-stories-claimed"
        assert action3["meta"]["claimed_stories"] == ["TEST-101", "TEST-102"]


class TestResolveNextActionClaimedSkippedMeta:
    """A10: spawn actions surface claimed_skipped when non-empty, omit it
    when empty."""

    def test_meta_absent_when_nothing_claimed(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(tmp_path, "1", [("TEST-001", "planned")])
        _write_story(tmp_path, "TEST-001")
        _patch_git_log(monkeypatch, "")

        pos = infer_position(tmp_path)
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert "claimed_skipped" not in action["meta"]

    def test_meta_present_when_a_story_was_skipped(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        _write_index(tmp_path, [("1", "Phase 1", "active")])
        _write_phase(
            tmp_path, "1", [("TEST-001", "planned"), ("TEST-002", "planned")]
        )
        _write_story(tmp_path, "TEST-001")
        _write_story(tmp_path, "TEST-002")
        _patch_git_log(monkeypatch, "")
        (tmp_path / ".pairmode-worktrees" / "TEST-001").mkdir(parents=True)

        pos = infer_position(tmp_path)
        action = resolve_next_action(pos)
        assert action["action"] == SPAWN_BUILDER
        assert action["scalar"] == "TEST-002"
        assert action["meta"]["claimed_skipped"] == ["TEST-001"]


# ---------------------------------------------------------------------------
# INFRA-297 (CER-069/B4) — _check_cer_do_now splits on unescaped pipes only,
# and keeps its index-shifting `if c.strip()` filter verbatim.
# ---------------------------------------------------------------------------


class TestCheckCerDoNowEscapedPipe:
    """A Do Now row whose finding cell contains a literal ``\\|`` must be
    classified identically to the same row without one: the escaped pipe is
    cell content, not a column boundary.

    The ``if c.strip()`` filter is load-bearing here — it drops the empty
    cells produced by the leading/trailing pipes, so ``cols[0]`` is the ID
    cell for both the header test and ``cer.is_placeholder_row`` (INFRA-294).
    """

    _HEADER = (
        "# CER Backlog\n\n"
        "## Do Now\n\n"
        "| ID | Finding | Source | Date | Phase |\n"
        "|----|---------|--------|------|-------|\n"
    )

    def _write(self, tmp_path: Path, rows: str) -> Path:
        cer_dir = tmp_path / "docs" / "cer"
        cer_dir.mkdir(parents=True, exist_ok=True)
        (cer_dir / "backlog.md").write_text(
            self._HEADER + rows + "\n## Do Later\n\n", encoding="utf-8"
        )
        return tmp_path

    def test_unresolved_row_with_escaped_pipe_still_fails(self, tmp_path: Path) -> None:
        from next_action import _check_cer_do_now

        self._write(
            tmp_path,
            "| CER-999 | Naive split shreds Edit\\|Write titles"
            " | cold-eyes | 2026-01-01 | 113 |\n\n",
        )
        assert _check_cer_do_now(tmp_path) is False

    def test_resolved_row_with_escaped_pipe_still_passes(self, tmp_path: Path) -> None:
        from next_action import _check_cer_do_now

        self._write(
            tmp_path,
            "| CER-999 | Naive split shreds Edit\\|Write titles."
            " **RESOLVED (INFRA-297)** | cold-eyes | 2026-01-01 | 113 |\n\n",
        )
        assert _check_cer_do_now(tmp_path) is True

    def test_classification_identical_with_and_without_escaped_pipe(
        self, tmp_path: Path
    ) -> None:
        from next_action import _check_cer_do_now

        plain = tmp_path / "plain"
        escaped = tmp_path / "escaped"
        self._write(
            plain,
            "| CER-999 | Edit or Write titles | cold-eyes | 2026-01-01 | 113 |\n\n",
        )
        self._write(
            escaped,
            "| CER-999 | Edit\\|Write titles | cold-eyes | 2026-01-01 | 113 |\n\n",
        )
        assert _check_cer_do_now(escaped) == _check_cer_do_now(plain) is False

    def test_placeholder_row_still_exempted(self, tmp_path: Path) -> None:
        from next_action import _check_cer_do_now

        self._write(tmp_path, "| — | *(none)* | — | — | — |\n\n")
        assert _check_cer_do_now(tmp_path) is True

    def test_header_row_still_detected(self, tmp_path: Path) -> None:
        """The header test reads cols[0] from the filtered list; with only a
        header and separator present the guard passes."""
        from next_action import _check_cer_do_now

        self._write(tmp_path, "\n")
        assert _check_cer_do_now(tmp_path) is True


# ---------------------------------------------------------------------------
# INFRA-322 (CER-130) — _check_cer_do_now consumes the anchored,
# case-insensitive cer.is_resolution_marked grammar.
# ---------------------------------------------------------------------------


class TestCheckCerDoNowResolutionMarkerGrammar:
    """The membership test is now a call to ``cer.is_resolution_marked``
    (INFRA-322). Both defect directions of CER-130 get a regression test
    here: a title-case marker that a bare case-sensitive substring test
    would never match (direction 1), and prose containing the letters
    ``RESOLVED``/``UNRESOLVED`` mid-clause that a bare substring test would
    incorrectly match (direction 2).
    """

    _HEADER = (
        "# CER Backlog\n\n"
        "## Do Now\n\n"
        "| ID | Finding | Source | Date | Phase |\n"
        "|----|---------|--------|------|-------|\n"
    )

    def _write(self, tmp_path: Path, rows: str) -> Path:
        cer_dir = tmp_path / "docs" / "cer"
        cer_dir.mkdir(parents=True, exist_ok=True)
        (cer_dir / "backlog.md").write_text(
            self._HEADER + rows + "\n## Do Later\n\n", encoding="utf-8"
        )
        return tmp_path

    def test_cer_do_now_passes_on_title_case_resolved_row(
        self, tmp_path: Path
    ) -> None:
        """CER-130 direction-1 regression test.

        The old expression was
        ``"RESOLVED" not in stripped and "SUPERSEDED" not in stripped``.
        This row contains no uppercase ``RESOLVED`` and no ``SUPERSEDED``
        substring at all, so the old expression would classify it
        unresolved — permanently blocking a consuming repo's checkpoint.
        """
        from next_action import _check_cer_do_now

        row = "| CER-999 | A finding. Resolved cp-34 — INFRA-1 | src | 2026-01-01 | 34 |\n\n"
        self._write(tmp_path, row)
        assert "RESOLVED" not in row
        assert "SUPERSEDED" not in row
        assert _check_cer_do_now(tmp_path) is True

    def test_cer_do_now_fails_on_unresolved_row(self, tmp_path: Path) -> None:
        """CER-130 direction-2 regression test."""
        from next_action import _check_cer_do_now

        self._write(
            tmp_path,
            "| CER-999 | UNRESOLVED naming gap between … | src | 2026-01-01 | 1 |\n\n",
        )
        assert _check_cer_do_now(tmp_path) is False

    def test_cer_do_now_fails_on_aspirational_resolution_prose(
        self, tmp_path: Path
    ) -> None:
        from next_action import _check_cer_do_now

        self._write(
            tmp_path,
            "| CER-999 | the fix direction is documented; this SHOULD BE"
            " RESOLVED before the 0.4 tag | src | 2026-01-01 | 1 |\n\n",
        )
        assert _check_cer_do_now(tmp_path) is False

    def test_cer_do_now_passes_on_superseded_row(self, tmp_path: Path) -> None:
        from next_action import _check_cer_do_now

        self._write(
            tmp_path,
            "| CER-999 | A finding. **SUPERSEDED by CER-9** | src | 2026-01-01 | 1 |\n\n",
        )
        assert _check_cer_do_now(tmp_path) is True

    def test_cer_do_now_fails_when_any_row_is_unmarked(self, tmp_path: Path) -> None:
        """The guard is all-rows-must-be-marked, not any-row."""
        from next_action import _check_cer_do_now

        self._write(
            tmp_path,
            "| CER-998 | A finding. **RESOLVED Phase 1** | src | 2026-01-01 | 1 |\n\n"
            "| CER-999 | A still-open finding | src | 2026-01-01 | 1 |\n\n",
        )
        assert _check_cer_do_now(tmp_path) is False

    def test_placeholder_row_exempted_before_resolution_test(
        self, tmp_path: Path
    ) -> None:
        from next_action import _check_cer_do_now

        self._write(tmp_path, "| — | *(none)* | — | — | — |\n\n")
        assert _check_cer_do_now(tmp_path) is True

    def test_placeholder_row_is_not_itself_resolution_marked(self) -> None:
        """Proves the exemption, not the grammar, is what carries the
        placeholder row: if the ordering in ``_check_cer_do_now`` ever
        inverted (resolution test before the placeholder exemption), a
        fresh repo's first checkpoint would start failing again."""
        from cer import is_resolution_marked

        assert is_resolution_marked("— | *(none)* | — | — | —") is False


def test_live_backlog_do_now_classification_parity() -> None:
    """Parity test (INFRA-322 § F4): every non-placeholder ``## Do Now`` row
    in flex's own live ``docs/cer/backlog.md`` is classified identically by
    the new anchored grammar and by the old bare-substring expression it
    replaced (verified at spec time: 14 rows, zero divergence). Reads the
    repo's own backlog by path and skips cleanly if the file is absent, so
    it cannot fail in a consuming checkout.
    """
    from cer import is_placeholder_row, is_resolution_marked
    from table_utils import split_table_row

    repo_root = Path(__file__).parent.parent.parent
    backlog_path = repo_root / "docs" / "cer" / "backlog.md"
    if not backlog_path.exists():
        pytest.skip("docs/cer/backlog.md not present in this checkout")

    text = backlog_path.read_text(encoding="utf-8")
    in_do_now = False
    checked_any = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Do Now"):
            in_do_now = True
            continue
        if in_do_now and stripped.startswith("## "):
            break
        if in_do_now and stripped.startswith("|"):
            if "---" in stripped:
                continue
            cols = [c.strip() for c in split_table_row(stripped) if c.strip()]
            if not cols or cols[0].lower() in ("id", "finding"):
                continue
            if is_placeholder_row(cols):
                continue
            old_result = "RESOLVED" in stripped or "SUPERSEDED" in stripped
            new_result = is_resolution_marked(stripped)
            assert old_result == new_result, (
                f"classification diverged on row: {stripped!r}"
            )
            checked_any = True
    assert checked_any, "expected at least one non-placeholder Do Now row"
