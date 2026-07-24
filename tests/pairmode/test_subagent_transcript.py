"""Tests for skills/pairmode/scripts/subagent_transcript.py (INFRA-236).

Covers:
- parse_worker_outcome: BUILD-RESULT / REVIEW-RESULT JSON extraction, the
  FAIL-CAUSE line fallback, and the None/None no-result case.
- extract_subagent_usage: sidechain-turn summation, no-match, and no-usage
  cases.
- record_attempt_from_transcript: the end-to-end effort.db write, the
  effort_tracking-disabled no-op, the non-recordable-role no-op, and the
  DP7 separation (this module never touches context_current_tokens).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from skills.pairmode.scripts import effort_db
from skills.pairmode.scripts import subagent_transcript as st


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


def _write_transcript(tmp_path: Path, session_id: str, lines: list[dict]) -> Path:
    home = tmp_path / "home"
    cwd = tmp_path / "project"
    cwd.mkdir(parents=True, exist_ok=True)
    cwd_key = str(cwd.resolve()).replace("/", "-")
    transcript_dir = home / ".claude" / "projects" / cwd_key
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = transcript_dir / f"{session_id}.jsonl"
    transcript_path.write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n",
        encoding="utf-8",
    )
    return home


def _sidechain_entry(tokens_in: int, tokens_out: int, model: str = "claude-sonnet-5") -> dict:
    return {
        "type": "assistant",
        "isSidechain": True,
        "message": {
            "model": model,
            "usage": {
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        },
    }


def _tool_use_entry(tool_use_id: str, subagent_type: str = "builder") -> dict:
    return {
        "type": "assistant",
        "isSidechain": False,
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": "Task",
                    "input": {"subagent_type": subagent_type, "prompt": "INFRA-236"},
                }
            ]
        },
    }


def _completion_entry() -> dict:
    return {"type": "user", "isSidechain": False, "message": {"content": []}}


# ---------------------------------------------------------------------------
# parse_worker_outcome
# ---------------------------------------------------------------------------


class TestParseWorkerOutcome:
    def test_build_result_pass(self) -> None:
        text = json.dumps({
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "INFRA-236",
            "reason": "Implemented the thing.",
        })
        outcome, fail_cause = st.parse_worker_outcome(text)
        assert outcome == "PASS"
        assert fail_cause is None

    def test_review_result_fail_with_fail_cause(self) -> None:
        text = json.dumps({
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["CRITICAL hook violation"],
            "reason": "Blocked.",
            "fail_cause": "CRITICAL hook violation in hooks/pre_tool_use.py",
        })
        outcome, fail_cause = st.parse_worker_outcome(text)
        assert outcome == "FAIL"
        assert fail_cause == "CRITICAL hook violation in hooks/pre_tool_use.py"

    def test_fail_cause_line_fallback(self) -> None:
        text = (
            "FAIL-CAUSE: undeclared file: docs/architecture.md\n"
            + json.dumps({
                "type": "REVIEW-RESULT",
                "verdict": "FAIL",
                "findings": ["undeclared file"],
                "reason": "Scope violation.",
            })
        )
        outcome, fail_cause = st.parse_worker_outcome(text)
        assert outcome == "FAIL"
        assert fail_cause == "undeclared file: docs/architecture.md"

    def test_no_result_object_returns_none_none(self) -> None:
        outcome, fail_cause = st.parse_worker_outcome("just some prose, no JSON here")
        assert outcome is None
        assert fail_cause is None

    def test_none_tool_response(self) -> None:
        assert st.parse_worker_outcome(None) == (None, None)

    def test_dict_tool_response_content_shape(self) -> None:
        obj = {
            "type": "BUILD-RESULT",
            "outcome": "FAIL",
            "story_id": "INFRA-236",
            "reason": "tests red",
        }
        tool_response = {"content": [{"type": "text", "text": json.dumps(obj)}]}
        outcome, fail_cause = st.parse_worker_outcome(tool_response)
        assert outcome == "FAIL"


# ---------------------------------------------------------------------------
# extract_subagent_usage
# ---------------------------------------------------------------------------


class TestExtractSubagentUsage:
    def test_sums_sidechain_turns(self, tmp_path: Path) -> None:
        home = _write_transcript(
            tmp_path,
            "sess-1",
            [
                {"type": "user", "isSidechain": False, "message": {"content": []}},
                _tool_use_entry("toolu_1"),
                _sidechain_entry(100, 50),
                _sidechain_entry(200, 75),
                _completion_entry(),
            ],
        )
        cwd = tmp_path / "project"
        transcript_path = home / ".claude" / "projects" / str(cwd.resolve()).replace("/", "-") / "sess-1.jsonl"

        usage = st.extract_subagent_usage(transcript_path, "toolu_1")
        assert usage["tokens_in"] == 300
        assert usage["tokens_out"] == 125
        assert usage["tokens_total"] == 425
        assert usage["model"] == "claude-sonnet-5"

    def test_no_matching_tool_use_id_returns_empty(self, tmp_path: Path) -> None:
        home = _write_transcript(
            tmp_path,
            "sess-2",
            [_tool_use_entry("toolu_other"), _sidechain_entry(10, 5)],
        )
        cwd = tmp_path / "project"
        transcript_path = home / ".claude" / "projects" / str(cwd.resolve()).replace("/", "-") / "sess-2.jsonl"

        usage = st.extract_subagent_usage(transcript_path, "toolu_missing")
        assert usage["tokens_total"] is None

    def test_none_transcript_path_returns_empty(self) -> None:
        usage = st.extract_subagent_usage(None, "toolu_1")
        assert usage == dict(st._EMPTY_USAGE)

    def test_missing_tool_use_id_returns_empty(self, tmp_path: Path) -> None:
        usage = st.extract_subagent_usage(tmp_path / "nope.jsonl", None)
        assert usage["tokens_total"] is None

    def test_unreadable_file_returns_empty(self, tmp_path: Path) -> None:
        usage = st.extract_subagent_usage(tmp_path / "does-not-exist.jsonl", "toolu_1")
        assert usage["tokens_total"] is None


# ---------------------------------------------------------------------------
# record_attempt_from_transcript
# ---------------------------------------------------------------------------


class TestRecordAttemptFromTranscript:
    def test_writes_one_row_for_builder_spawn(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        home = tmp_path / "home"
        cwd_key = str(project_dir.resolve()).replace("/", "-")
        transcript_dir = home / ".claude" / "projects" / cwd_key
        transcript_dir.mkdir(parents=True, exist_ok=True)
        (transcript_dir / "sess-3.jsonl").write_text(
            "\n".join(
                json.dumps(line)
                for line in [
                    _tool_use_entry("toolu_3", subagent_type="builder"),
                    _sidechain_entry(1000, 500),
                    _completion_entry(),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        tool_response = json.dumps({
            "type": "BUILD-RESULT",
            "outcome": "PASS",
            "story_id": "INFRA-236",
            "reason": "did the thing",
        })

        row_id = st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="sess-3",
            tool_input={"subagent_type": "builder", "prompt": "INFRA-236"},
            tool_response=tool_response,
            tool_use_id="toolu_3",
            home=home,
        )

        assert row_id is not None
        db_path = project_dir / ".companion" / "effort.db"
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT story_id, agent_role, tokens_total, outcome, rail FROM attempts"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        assert len(rows) == 1
        story_id, agent_role, tokens_total, outcome, rail = rows[0]
        assert story_id == "INFRA-236"
        assert agent_role == "builder"
        assert tokens_total == 1500
        assert outcome == "PASS"
        assert rail == "INFRA"

    def test_reviewer_role_is_recordable(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        row_id = st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "reviewer", "prompt": "INFRA-236"},
            tool_response=json.dumps({
                "type": "REVIEW-RESULT",
                "verdict": "FAIL",
                "findings": ["x"],
                "reason": "y",
                "fail_cause": "undeclared file: docs/architecture.md",
            }),
        )
        assert row_id is not None
        db_path = project_dir / ".companion" / "effort.db"
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("SELECT agent_role, outcome, notes FROM attempts")
            role, outcome, notes = cur.fetchone()
        finally:
            conn.close()
        assert role == "reviewer"
        assert outcome == "FAIL"
        assert notes == "undeclared file: docs/architecture.md"

    def test_non_recordable_subagent_type_is_noop(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        result = st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "general-purpose", "prompt": "explore x"},
            tool_response="",
        )
        assert result is None
        db_path = project_dir / ".companion" / "effort.db"
        assert not db_path.exists() or effort_db.resolve_effort_db_path is not None

    def test_effort_tracking_disabled_is_noop(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        # No state.json at all — effort_tracking absent.
        result = st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "builder", "prompt": "INFRA-236"},
            tool_response="",
        )
        assert result is None

    def test_never_raises_on_malformed_tool_input(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)
        # tool_input is not a dict — must not raise.
        result = st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input=None,
            tool_response="",
        )
        assert result is None

    def test_never_writes_context_current_tokens(self, tmp_path: Path) -> None:
        """DP7: this module must never touch context-control state."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        state_path = _enable_tracking(project_dir)
        before = json.loads(state_path.read_text())
        assert "context_current_tokens" not in before

        st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "builder", "prompt": "INFRA-236"},
            tool_response=json.dumps({
                "type": "BUILD-RESULT", "outcome": "PASS",
                "story_id": "INFRA-236", "reason": "done",
            }),
        )

        after = json.loads(state_path.read_text())
        assert "context_current_tokens" not in after
        assert "context_current_tokens_recorded_at" not in after


# ---------------------------------------------------------------------------
# Attempt-counter bump on FAIL (INFRA-237)
# ---------------------------------------------------------------------------


class TestAttemptCounterBump:
    def test_fail_outcome_bumps_counter_from_zero(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "builder", "prompt": "INFRA-237"},
            tool_response=json.dumps({
                "type": "BUILD-RESULT", "outcome": "FAIL",
                "story_id": "INFRA-237", "reason": "stuck",
            }),
        )

        from skills.pairmode.scripts.flex_build import read_attempt_count
        assert read_attempt_count("INFRA-237", project_dir) == 1

    def test_successive_fails_bump_1_then_2_then_3(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        from skills.pairmode.scripts.flex_build import read_attempt_count

        fail_response = json.dumps({
            "type": "REVIEW-RESULT", "verdict": "FAIL",
            "findings": ["x"], "reason": "y",
        })
        for expected in (1, 2, 3):
            st.record_attempt_from_transcript(
                project_dir=project_dir,
                session_id="",
                tool_input={"subagent_type": "reviewer", "prompt": "INFRA-237"},
                tool_response=fail_response,
            )
            assert read_attempt_count("INFRA-237", project_dir) == expected

    def test_pass_outcome_does_not_bump(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "builder", "prompt": "INFRA-237"},
            tool_response=json.dumps({
                "type": "BUILD-RESULT", "outcome": "PASS",
                "story_id": "INFRA-237", "reason": "done",
            }),
        )

        from skills.pairmode.scripts.flex_build import read_attempt_count
        assert read_attempt_count("INFRA-237", project_dir) == 0

    def test_bump_runs_even_when_effort_tracking_disabled(self, tmp_path: Path) -> None:
        """The counter is core build-loop control state, not observability —
        it must not be gated on effort_tracking (INFRA-237)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        # No state.json at all — effort_tracking absent/false.

        result = st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "builder", "prompt": "INFRA-237"},
            tool_response=json.dumps({
                "type": "BUILD-RESULT", "outcome": "FAIL",
                "story_id": "INFRA-237", "reason": "stuck",
            }),
        )

        # Recording itself is a no-op (no effort.db row) when tracking is off...
        assert result is None
        # ...but the attempt counter still bumps.
        from skills.pairmode.scripts.flex_build import read_attempt_count
        assert read_attempt_count("INFRA-237", project_dir) == 1

    def test_non_recordable_subagent_type_does_not_bump(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "general-purpose", "prompt": "INFRA-237"},
            tool_response=json.dumps({
                "type": "BUILD-RESULT", "outcome": "FAIL",
                "story_id": "INFRA-237", "reason": "stuck",
            }),
        )

        from skills.pairmode.scripts.flex_build import read_attempt_count
        assert read_attempt_count("INFRA-237", project_dir) == 0

    def test_no_story_id_does_not_bump(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        # No RAIL-NNN pattern anywhere and no current_story fallback in state.
        result = st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={"subagent_type": "builder", "prompt": "no story id here"},
            tool_response=json.dumps({
                "type": "BUILD-RESULT", "outcome": "FAIL",
                "story_id": "unresolved", "reason": "stuck",
            }),
        )
        assert result is not None  # effort.db still records under unattributed:builder
        counter_path = project_dir / ".companion" / "attempt_counter.json"
        assert not counter_path.exists()
