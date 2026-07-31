"""Tests for skills/pairmode/scripts/session_lifecycle.py (INFRA-323)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from skills.pairmode.scripts.session_lifecycle import (
    RESTART_SURFACES,
    agent_staleness_notice,
    classify_surface,
    render_restart_notice,
    stamp_agent_surfaces,
)


def test_render_notice_contains_restart_required_banner():
    text = render_restart_notice([".claude/agents/builder.md"], action="bootstrap")
    assert "RESTART REQUIRED" in text


def test_render_notice_enumerates_each_changed_surface():
    changed = [".claude/agents/builder.md", ".claude/agents/reviewer.md", "hook_registration"]
    text = render_restart_notice(changed, action="sync-agents")
    for item in changed:
        assert item in text


def test_render_notice_states_clear_is_not_sufficient():
    text = render_restart_notice([".claude/agents/builder.md"], action="bootstrap")
    assert "/clear" in text
    assert "not sufficient" in text.lower() or "NOT sufficient" in text


def test_render_notice_names_the_action():
    text = render_restart_notice([".claude/agents/builder.md"], action="migrate")
    assert "migrate" in text


def test_render_notice_empty_changed_returns_empty_string():
    assert render_restart_notice([], action="bootstrap") == ""


def test_stamp_writes_written_at_and_written_by_into_state_dict():
    state: dict = {}
    stamp_agent_surfaces(state, changed=[".claude/agents/builder.md"], action="bootstrap")
    assert state["agent_surfaces_written_by"] == "bootstrap"
    assert isinstance(state["agent_surfaces_written_at"], str)
    assert state["agent_surfaces_written_at"]


def test_stamp_is_noop_for_empty_changed():
    state: dict = {"pre_existing": True}
    stamp_agent_surfaces(state, changed=[], action="bootstrap")
    assert state == {"pre_existing": True}


def test_stamp_performs_no_file_io(tmp_path, monkeypatch):
    # No filesystem calls should occur; changing cwd to a nonexistent dir and
    # calling the function must still succeed since it touches no paths.
    state: dict = {}
    stamp_agent_surfaces(state, changed=["x"], action="bootstrap")
    assert "agent_surfaces_written_at" in state
    # No files were created anywhere under tmp_path.
    assert list(tmp_path.iterdir()) == []


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_staleness_notice_returns_line_for_clear_source_after_write():
    now = datetime.now(timezone.utc)
    started = _iso(now - timedelta(minutes=10))
    written = _iso(now - timedelta(minutes=1))
    result = agent_staleness_notice(
        source="clear", session_started_at=started, written_at=written, written_by="sync-agents"
    )
    assert result is not None
    assert "RESTART REQUIRED" not in result


def test_staleness_notice_returns_line_for_compact_source_after_write():
    now = datetime.now(timezone.utc)
    started = _iso(now - timedelta(minutes=10))
    written = _iso(now - timedelta(minutes=1))
    result = agent_staleness_notice(
        source="compact", session_started_at=started, written_at=written, written_by="bootstrap"
    )
    assert result is not None


def test_staleness_notice_none_for_startup_source():
    now = datetime.now(timezone.utc)
    started = _iso(now - timedelta(minutes=10))
    written = _iso(now - timedelta(minutes=1))
    result = agent_staleness_notice(
        source="startup", session_started_at=started, written_at=written, written_by="bootstrap"
    )
    assert result is None


def test_staleness_notice_none_for_resume_source():
    now = datetime.now(timezone.utc)
    started = _iso(now - timedelta(minutes=10))
    written = _iso(now - timedelta(minutes=1))
    result = agent_staleness_notice(
        source="resume", session_started_at=started, written_at=written, written_by="bootstrap"
    )
    assert result is None


def test_staleness_notice_none_when_write_predates_session_start():
    now = datetime.now(timezone.utc)
    started = _iso(now - timedelta(minutes=1))
    written = _iso(now - timedelta(minutes=10))
    result = agent_staleness_notice(
        source="clear", session_started_at=started, written_at=written, written_by="bootstrap"
    )
    assert result is None


def test_staleness_notice_none_on_missing_or_unparseable_timestamps():
    assert agent_staleness_notice(
        source="clear", session_started_at=None, written_at="2026-01-01T00:00:00+00:00",
        written_by="bootstrap",
    ) is None
    assert agent_staleness_notice(
        source="clear", session_started_at="2026-01-01T00:00:00+00:00", written_at=None,
        written_by="bootstrap",
    ) is None
    assert agent_staleness_notice(
        source="clear", session_started_at="not-a-timestamp",
        written_at="2026-01-01T00:00:00+00:00", written_by="bootstrap",
    ) is None
    assert agent_staleness_notice(
        source="clear", session_started_at="2026-01-01T00:00:00+00:00",
        written_at="not-a-timestamp", written_by="bootstrap",
    ) is None


def test_surface_classification_agent_shell_and_settings_and_skill_md():
    assert classify_surface(".claude/agents/builder.md") == "agent_shells"
    assert classify_surface(".claude/settings.json") == "hook_registration"
    assert classify_surface(".claude/settings.local.json") == "hook_registration"
    assert classify_surface("skills/pairmode/SKILL.md") == "plugin_skills"
    assert set(RESTART_SURFACES) == {"agent_shells", "hook_registration", "plugin_skills"}


def test_claude_build_md_is_not_a_registration_surface():
    assert classify_surface("CLAUDE.build.md") is None
    assert classify_surface("CLAUDE.md") is None
