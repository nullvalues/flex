"""
tests/pairmode/test_checkpoint_step.py

Tests for RESOLVER-007: checkpoint_step Position field and checkpoint action vocabulary.

Coverage:
- infer_position reads state.json["checkpoint_step"] and includes it as
  position["checkpoint_step"] (list[str], defaults to []).
- SCHEMA_VERSION == 3.
- New checkpoint actions are in ACTIONS; monolithic "checkpoint" is not.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = (
    Path(__file__).parent.parent.parent
    / "skills"
    / "pairmode"
    / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from next_action import (  # noqa: E402
    ACTIONS,
    AWAIT_USER,
    CHECKPOINT,
    CHECKPOINT_DOCS,
    CHECKPOINT_INTENT,
    CHECKPOINT_SECURITY,
    CHECKPOINT_TAG,
    SCHEMA_VERSION,
    infer_position,
)


# ---------------------------------------------------------------------------
# Fixtures: synthetic project state (minimal — only what infer_position reads)
# ---------------------------------------------------------------------------


def _write_minimal_project(tmp_path: Path, state_overrides: dict | None = None) -> Path:
    """Write a minimal synthetic project tree with a complete phase and no next story.

    This forces Row 9 (next_story_id=None) so infer_position returns quickly
    without needing to resolve story frontmatter.  We only need to verify the
    checkpoint_step field in the returned Position dict.
    """
    project = tmp_path / "project"
    project.mkdir()

    # Minimal git repo (infer_position calls _git_log_oneline internally).
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(project), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(project), check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=str(project), check=True)
    (project / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(project), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=str(project), check=True)

    # Phase index with one active phase.
    phases_dir = project / "docs" / "phases"
    phases_dir.mkdir(parents=True)
    (phases_dir / "index.md").write_text(
        "# Phase Index\n\n"
        "| Phase | Title | Status | Tag |\n"
        "|-------|-------|--------|-----|\n"
        "| 1 | Test Phase | active | |\n",
        encoding="utf-8",
    )
    # Phase manifest with no unbuilt stories (so next_story_id is None).
    (phases_dir / "phase-1.md").write_text(
        "# Phase 1\n\n## Stories\n\n| ID | Title | Status |\n|----|-------|--------|\n",
        encoding="utf-8",
    )

    # .companion directory and state.json.
    companion = project / ".companion"
    companion.mkdir()
    state: dict = {"pairmode_version": "1.0"}
    if state_overrides is not None:
        state.update(state_overrides)
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")

    return project


# ---------------------------------------------------------------------------
# Tests: checkpoint_step in Position
# ---------------------------------------------------------------------------


class TestCheckpointStepInPosition:
    def test_empty_checkpoint_step_list(self, tmp_path: Path) -> None:
        """state.json with checkpoint_step: [] → position["checkpoint_step"] == []."""
        project = _write_minimal_project(tmp_path, {"checkpoint_step": []})
        pos = infer_position(project)
        assert "checkpoint_step" in pos
        assert pos["checkpoint_step"] == []

    def test_nonempty_checkpoint_step_list(self, tmp_path: Path) -> None:
        """state.json with checkpoint_step: ["checkpoint-security"] → Position reflects it."""
        project = _write_minimal_project(
            tmp_path, {"checkpoint_step": ["checkpoint-security"]}
        )
        pos = infer_position(project)
        assert pos["checkpoint_step"] == ["checkpoint-security"]

    def test_multiple_checkpoint_steps(self, tmp_path: Path) -> None:
        """Multiple completed steps are preserved in order."""
        steps = ["checkpoint-security", "checkpoint-intent"]
        project = _write_minimal_project(tmp_path, {"checkpoint_step": steps})
        pos = infer_position(project)
        assert pos["checkpoint_step"] == steps

    def test_missing_checkpoint_step_key_defaults_to_empty(self, tmp_path: Path) -> None:
        """state.json with no checkpoint_step key → position["checkpoint_step"] == []."""
        project = _write_minimal_project(tmp_path, {})  # no checkpoint_step key
        pos = infer_position(project)
        assert "checkpoint_step" in pos
        assert pos["checkpoint_step"] == []

    def test_checkpoint_step_is_list_not_none(self, tmp_path: Path) -> None:
        """checkpoint_step is always a list, never None."""
        project = _write_minimal_project(tmp_path, {})
        pos = infer_position(project)
        assert isinstance(pos["checkpoint_step"], list)


# ---------------------------------------------------------------------------
# Tests: SCHEMA_VERSION and action vocabulary
# ---------------------------------------------------------------------------


class TestKeyedCheckpointStepsInPosition:
    """INFRA-283 (CER-095.4): infer_position prefers state.json["checkpoint_steps"]
    (a dict[phase_key, list[step_id]]) as the authority, keyed by the active
    phase's own key. Legacy behaviour, including the CER-083 stale-stamp
    rule, survives on the legacy fallback path."""

    def test_keyed_record_read_for_active_phase(self, tmp_path: Path) -> None:
        """Assertion 14: keyed record present -> position["checkpoint_step"]
        is the active phase's own entry."""
        project = _write_minimal_project(
            tmp_path,
            {"checkpoint_steps": {"1": ["checkpoint-security", "checkpoint-intent"]}},
        )
        pos = infer_position(project)
        assert pos["checkpoint_step"] == ["checkpoint-security", "checkpoint-intent"]

    def test_two_phases_resolve_independently(self, tmp_path: Path) -> None:
        """Assertion 15: with {"1": [...], "105": []} recorded and the active
        phase file naming "1", position["checkpoint_step"] reflects "1"'s
        own list regardless of what checkpoint_phase (if present) names."""
        project = _write_minimal_project(
            tmp_path,
            {
                "checkpoint_steps": {"1": ["checkpoint-security"], "105": []},
                "checkpoint_phase": "105",
            },
        )
        pos = infer_position(project)
        assert pos["checkpoint_step"] == ["checkpoint-security"]

    def test_keyed_record_present_but_active_phase_absent_yields_empty(
        self, tmp_path: Path
    ) -> None:
        """Assertion 14: the active phase has no entry in the keyed record
        -> []."""
        project = _write_minimal_project(
            tmp_path, {"checkpoint_steps": {"105": ["checkpoint-security"]}}
        )
        pos = infer_position(project)
        assert pos["checkpoint_step"] == []

    def test_legacy_cer083_stale_stamp_still_clears_on_mismatch(
        self, tmp_path: Path
    ) -> None:
        """Assertion 16: no keyed record present -> the original cp99 ->
        phase-100 scenario still clears on a stamp mismatch (unchanged
        legacy fallback behaviour)."""
        project = _write_minimal_project(
            tmp_path,
            {
                "checkpoint_step": ["checkpoint-security", "checkpoint-intent"],
                "checkpoint_phase": "99",
            },
        )
        pos = infer_position(project)
        assert pos["checkpoint_step"] == []

    def test_legacy_matching_stamp_is_honoured(self, tmp_path: Path) -> None:
        """No keyed record; stamp matches the active phase key -> the stored
        list is trusted (legacy path, unchanged)."""
        project = _write_minimal_project(
            tmp_path,
            {"checkpoint_step": ["checkpoint-security"], "checkpoint_phase": "1"},
        )
        pos = infer_position(project)
        assert pos["checkpoint_step"] == ["checkpoint-security"]

    def test_malformed_state_json_yields_empty_list(self, tmp_path: Path) -> None:
        """Assertion 17: an unreadable/malformed state.json still yields []
        and infer_position never raises."""
        project = _write_minimal_project(tmp_path, {})
        (project / ".companion" / "state.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        pos = infer_position(project)
        assert pos["checkpoint_step"] == []


class TestCheckpointActionVocabulary:
    def test_schema_version_is_4(self) -> None:
        """SCHEMA_VERSION must be 6 after the INFRA-339 pause-context removal bump."""
        assert SCHEMA_VERSION == 6

    def test_checkpoint_security_in_actions(self) -> None:
        assert CHECKPOINT_SECURITY == "checkpoint-security"
        assert "checkpoint-security" in ACTIONS

    def test_checkpoint_intent_in_actions(self) -> None:
        assert CHECKPOINT_INTENT == "checkpoint-intent"
        assert "checkpoint-intent" in ACTIONS

    def test_checkpoint_docs_in_actions(self) -> None:
        assert CHECKPOINT_DOCS == "checkpoint-docs"
        assert "checkpoint-docs" in ACTIONS

    def test_checkpoint_tag_in_actions(self) -> None:
        assert CHECKPOINT_TAG == "checkpoint-tag"
        assert "checkpoint-tag" in ACTIONS

    def test_monolithic_checkpoint_not_in_actions(self) -> None:
        """RESOLVER-007 removed the monolithic 'checkpoint' action from ACTIONS."""
        assert CHECKPOINT == "checkpoint"
        assert "checkpoint" not in ACTIONS
