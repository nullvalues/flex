"""Effort recording for sidebar (companion-skill) LLM calls.

These tests cover the ``sidebar-extractor`` role introduced by INFRA-035.
The sidebar runs with ``disable-model-invocation: true`` so it cannot be
spawned as a subagent — recording must happen in-process via the
``effort_recorder`` helper, parameterised by the synthetic story_id
``sidebar:<current-story-id>`` (or ``sidebar:no-story`` when no story
context is set).
"""

from __future__ import annotations

import json
from pathlib import Path

from skills.pairmode.scripts import effort_db
from skills.pairmode.scripts.effort_recorder import record_effort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_tracking(project_dir: Path, **extra) -> Path:
    state_path = project_dir / ".companion" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"effort_tracking": True}
    payload.update(extra)
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    return state_path


def _fake_usage(input_tokens: int = 800, output_tokens: int = 200) -> dict:
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }


def _resolve_sidebar_story_id(current_story: dict | None) -> str:
    """Replicate the sidebar's story_id resolution rule, in test form."""
    if current_story and isinstance(current_story, dict):
        sid = current_story.get("id")
        if sid:
            return f"sidebar:{sid}"
    return "sidebar:no-story"


# ---------------------------------------------------------------------------
# sidebar-extractor with current_story set
# ---------------------------------------------------------------------------


class TestSidebarExtractorWithStory:
    def test_records_with_current_story_id(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        current_story = {"id": "INFRA-035", "title": "Effort recording", "set_at": "2026-05-01T00:00:00+00:00"}
        story_id = _resolve_sidebar_story_id(current_story)
        assert story_id == "sidebar:INFRA-035"

        record_effort(
            project_dir=tmp_path,
            story_id=story_id,
            agent_role="sidebar-extractor",
            model="claude-haiku-4-5-20251001",
            usage=_fake_usage(),
            attempt_number=1,
            outcome="PASS",
            notes="sidebar pipe-message LLM extraction",
        )

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, "sidebar:INFRA-035")
        assert len(rows) == 1
        row = rows[0]

        assert row["story_id"] == "sidebar:INFRA-035"
        assert row["agent_role"] == "sidebar-extractor"
        assert row["model"] == "claude-haiku-4-5-20251001"
        # phase/rail NULL for cross-skill rows
        assert row["phase"] is None
        assert row["rail"] is None
        assert row["tokens_in"] == 800
        assert row["tokens_out"] == 200
        assert row["tokens_total"] == 1000
        assert row["outcome"] == "PASS"


# ---------------------------------------------------------------------------
# sidebar-extractor without current_story
# ---------------------------------------------------------------------------


class TestSidebarExtractorNoStory:
    def test_falls_back_to_no_story_when_current_story_missing(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        story_id = _resolve_sidebar_story_id(None)
        assert story_id == "sidebar:no-story"

        record_effort(
            project_dir=tmp_path,
            story_id=story_id,
            agent_role="sidebar-extractor",
            model="claude-haiku-4-5-20251001",
            usage=_fake_usage(),
        )

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, "sidebar:no-story")
        assert len(rows) == 1
        assert rows[0]["agent_role"] == "sidebar-extractor"
        assert rows[0]["story_id"] == "sidebar:no-story"

    def test_falls_back_when_current_story_dict_has_no_id(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        story_id = _resolve_sidebar_story_id({"title": "Whatever"})  # no "id" key
        assert story_id == "sidebar:no-story"

        record_effort(
            project_dir=tmp_path,
            story_id=story_id,
            agent_role="sidebar-extractor",
            usage=_fake_usage(),
        )

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, "sidebar:no-story")
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# No-op behaviour (state missing / tracking off)
# ---------------------------------------------------------------------------


class TestNoOp:
    def test_no_state_json_silently_no_ops(self, tmp_path: Path) -> None:
        result = record_effort(
            project_dir=tmp_path,
            story_id="sidebar:INFRA-035",
            agent_role="sidebar-extractor",
            model="claude-haiku-4-5-20251001",
            usage=_fake_usage(),
        )
        assert result is None
        assert not (tmp_path / ".companion" / "effort.db").exists()

    def test_effort_tracking_disabled_no_ops(self, tmp_path: Path) -> None:
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"effort_tracking": False, "current_story": {"id": "INFRA-035"}}),
            encoding="utf-8",
        )

        result = record_effort(
            project_dir=tmp_path,
            story_id="sidebar:INFRA-035",
            agent_role="sidebar-extractor",
            usage=_fake_usage(),
        )
        assert result is None
        assert not (tmp_path / ".companion" / "effort.db").exists()


# ---------------------------------------------------------------------------
# Multiple sidebar calls accumulate as separate rows
# ---------------------------------------------------------------------------


class TestMultipleCalls:
    def test_multiple_sidebar_calls_record_separate_rows(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        story_id = "sidebar:INFRA-035"

        # Three pipe messages → three LLM calls → three rows.
        for i in range(3):
            record_effort(
                project_dir=tmp_path,
                story_id=story_id,
                agent_role="sidebar-extractor",
                model="claude-haiku-4-5-20251001",
                usage=_fake_usage(input_tokens=100 * (i + 1), output_tokens=50 * (i + 1)),
                attempt_number=1,
            )

        db_path = effort_db.resolve_effort_db_path(tmp_path)
        rows = effort_db.query_by_story(db_path, story_id)
        assert len(rows) == 3

        totals = sorted(r["tokens_total"] for r in rows)
        assert totals == [150, 300, 450]
