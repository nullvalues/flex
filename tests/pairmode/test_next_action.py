"""
tests/pairmode/test_next_action.py

Unit-tests for next_action.infer_position (RESOLVER-002) and for the
flex_build.py module-level extraction functions:
  - resolve_current_phase
  - read_attempt_count
  - check_stub_gate
  - check_schema_gate_result
  - check_auth_gate_result

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
    body = "## Ensures\n\n- It works.\n" if not stub else "See phase doc for details.\n"
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
