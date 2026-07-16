"""Tests for skills/pairmode/scripts/cold_read_guard.py (INFRA-196)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))

import cold_read_guard


def test_orchestrator_blocked_on_story_path(tmp_path):
    allowed, reason = cold_read_guard.check_path(
        "docs/stories/INFRA/INFRA-196.md", agent_type=None, project_dir=tmp_path
    )
    assert allowed is False
    assert "docs/stories" in reason


def test_orchestrator_blocked_on_agents_path(tmp_path):
    allowed, reason = cold_read_guard.check_path(
        ".claude/agents/builder.md", agent_type=None, project_dir=tmp_path
    )
    assert allowed is False
    assert ".claude/agents" in reason


def test_subagent_allowed_on_story_path(tmp_path):
    allowed, reason = cold_read_guard.check_path(
        "docs/stories/INFRA/INFRA-196.md", agent_type="general-purpose", project_dir=tmp_path
    )
    assert allowed is True
    assert "subagent" in reason


def test_subagent_allowed_on_agents_path(tmp_path):
    allowed, reason = cold_read_guard.check_path(
        ".claude/agents/builder.md", agent_type="builder", project_dir=tmp_path
    )
    assert allowed is True


def test_orchestrator_allowed_on_unrelated_path(tmp_path):
    allowed, reason = cold_read_guard.check_path(
        "docs/phases/phase-1.md", agent_type=None, project_dir=tmp_path
    )
    assert allowed is True


def test_orchestrator_allowed_on_readme(tmp_path):
    allowed, reason = cold_read_guard.check_path(
        "README.md", agent_type=None, project_dir=tmp_path
    )
    assert allowed is True


def test_path_traversal_escape_blocked_regardless_of_agent_type(tmp_path):
    allowed, reason = cold_read_guard.check_path(
        "../../etc/passwd", agent_type=None, project_dir=tmp_path
    )
    assert allowed is False
    assert "escapes" in reason

    allowed, reason = cold_read_guard.check_path(
        "../../etc/passwd", agent_type="builder", project_dir=tmp_path
    )
    # Subagent reads are unconditionally allowed without inspecting file_path.
    assert allowed is True


def test_absolute_path_within_project_under_stories_blocked(tmp_path):
    story_dir = tmp_path / "docs" / "stories" / "INFRA"
    story_dir.mkdir(parents=True)
    story_file = story_dir / "INFRA-196.md"
    story_file.write_text("x")
    allowed, reason = cold_read_guard.check_path(
        str(story_file), agent_type=None, project_dir=tmp_path
    )
    assert allowed is False


def test_malformed_project_dir_fails_open():
    allowed, reason = cold_read_guard.check_path(
        "docs/stories/INFRA/INFRA-196.md", agent_type=None, project_dir=12345
    )
    assert allowed is True
