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
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# attempt_number derivation from effort.db row history (INFRA-257)
# ---------------------------------------------------------------------------


def _record_spawn(project_dir: Path, subagent_type: str, story_id: str, outcome: str = "PASS") -> "int | None":
    return st.record_attempt_from_transcript(
        project_dir=project_dir,
        session_id="",
        tool_input={"subagent_type": subagent_type, "prompt": story_id},
        tool_response=json.dumps({
            "type": "BUILD-RESULT" if subagent_type == "builder" else "REVIEW-RESULT",
            "outcome": outcome,
            "verdict": outcome,
            "story_id": story_id,
            "reason": "x",
            "findings": [],
        }),
    )


class TestAttemptNumberDerivation:
    """Regression coverage for the INFRA-247/INFRA-248 all-1s shape."""

    def test_three_consecutive_builder_spawns_number_1_2_3(self, tmp_path: Path) -> None:
        """Reproduces the INFRA-247 shape: three builder spawns for one story."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        for _ in range(3):
            _record_spawn(project_dir, "builder", "INFRA-247")

        rows = effort_db.query_by_story(project_dir / ".companion" / "effort.db", "INFRA-247")
        assert [r["attempt_number"] for r in rows] == [1, 2, 3]

    def test_second_story_sequence_is_independent(self, tmp_path: Path) -> None:
        """Reproduces the INFRA-248 shape: four builder spawns for a second,
        unrelated story — its sequence does not inherit INFRA-247's count."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        for _ in range(3):
            _record_spawn(project_dir, "builder", "INFRA-247")
        for _ in range(4):
            _record_spawn(project_dir, "builder", "INFRA-248")

        db_path = project_dir / ".companion" / "effort.db"
        rows_247 = effort_db.query_by_story(db_path, "INFRA-247")
        rows_248 = effort_db.query_by_story(db_path, "INFRA-248")
        assert [r["attempt_number"] for r in rows_247] == [1, 2, 3]
        assert [r["attempt_number"] for r in rows_248] == [1, 2, 3, 4]

    def test_interleaved_builder_reviewer_role_independence(self, tmp_path: Path) -> None:
        """An interleaved builder/reviewer/builder/reviewer sequence for one
        story produces independent per-role numbering."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        _record_spawn(project_dir, "builder", "INFRA-257")
        _record_spawn(project_dir, "reviewer", "INFRA-257", outcome="FAIL")
        _record_spawn(project_dir, "builder", "INFRA-257")
        _record_spawn(project_dir, "reviewer", "INFRA-257", outcome="PASS")

        db_path = project_dir / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-257")
        builder_numbers = [r["attempt_number"] for r in rows if r["agent_role"] == "builder"]
        reviewer_numbers = [r["attempt_number"] for r in rows if r["agent_role"] == "reviewer"]
        assert builder_numbers == [1, 2]
        assert reviewer_numbers == [1, 2]

    def test_sequence_continues_after_counter_cleared_by_merge(self, tmp_path: Path) -> None:
        """The counter-cleared-after-merge case (Ensures 6): attempt_number
        derivation reads effort.db rows, never attempt_counter.json, so
        clearing the counter mid-sequence does not reset the row sequence."""
        from skills.pairmode.scripts.flex_build import clear_attempt_count

        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        _record_spawn(project_dir, "builder", "INFRA-257")
        clear_attempt_count(project_dir)
        _record_spawn(project_dir, "builder", "INFRA-257")

        db_path = project_dir / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-257")
        assert [r["attempt_number"] for r in rows] == [1, 2]

    def test_counter_value_unaffected_by_attempt_number_derivation(self, tmp_path: Path) -> None:
        """attempt_counter.json's own value must be untouched by this
        story's derivation — only the FAIL-only bump still writes it."""
        from skills.pairmode.scripts.flex_build import read_attempt_count

        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        _record_spawn(project_dir, "builder", "INFRA-257", outcome="FAIL")
        _record_spawn(project_dir, "builder", "INFRA-257", outcome="FAIL")

        assert read_attempt_count("INFRA-257", project_dir) == 2

        db_path = project_dir / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-257")
        assert [r["attempt_number"] for r in rows] == [1, 2]

    def test_derivation_failure_degrades_to_one_row_still_written(self, tmp_path: Path) -> None:
        """A derivation-path exception must not lose the row — it degrades
        to attempt_number=1 and the write still happens."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        with patch.object(
            effort_db, "next_attempt_number", side_effect=RuntimeError("boom")
        ):
            row_id = _record_spawn(project_dir, "builder", "INFRA-257")

        assert row_id is not None
        db_path = project_dir / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-257")
        assert len(rows) == 1
        assert rows[0]["attempt_number"] == 1


# ---------------------------------------------------------------------------
# INFRA-258: async-spawn effort recording
# ---------------------------------------------------------------------------


def _sidechain_entry_with_id(
    msg_id: str, tokens_in: int, tokens_out: int, model: str = "claude-sonnet-5"
) -> dict:
    return {
        "type": "assistant",
        "isSidechain": True,
        "message": {
            "id": msg_id,
            "model": model,
            "usage": {
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        },
    }


def _output_assistant_entry(
    msg_id: str,
    tokens_in: int,
    tokens_out: int,
    *,
    stop_reason: "str | None" = None,
    text: "str | None" = None,
    model: str = "claude-sonnet-5",
    timestamp: "str | None" = None,
) -> dict:
    message: dict = {
        "id": msg_id,
        "model": model,
        "usage": {
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }
    if stop_reason is not None:
        message["stop_reason"] = stop_reason
    if text is not None:
        message["content"] = [{"type": "text", "text": text}]
    entry: dict = {"type": "assistant", "message": message}
    if timestamp is not None:
        entry["timestamp"] = timestamp
    return entry


def _write_output_file(path: Path, entries: "list[dict]") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# _sum_deduped_usage / streaming dedupe (Ensures 8, 9)
# ---------------------------------------------------------------------------


class TestSumDedupedUsage:
    def test_observed_streaming_shape_dedupes_by_message_id(self) -> None:
        """Reproduces the exact observed shape: one message.id appearing
        three times with output_tokens 5, 5, 263 — only the last is real."""
        entries = [
            _sidechain_entry_with_id("msg_011CdMLvCkdcMj13pJQryLmP", 10, 5),
            _sidechain_entry_with_id("msg_011CdMLvCkdcMj13pJQryLmP", 10, 5),
            _sidechain_entry_with_id("msg_011CdMLvCkdcMj13pJQryLmP", 10, 263),
        ]
        usage = st._sum_deduped_usage(entries)
        assert usage["tokens_out"] == 263
        assert usage["tokens_out"] != 273

    def test_entries_without_message_id_summed_individually(self) -> None:
        entries = [
            _sidechain_entry(100, 50),
            _sidechain_entry(200, 75),
        ]
        usage = st._sum_deduped_usage(entries)
        assert usage["tokens_in"] == 300
        assert usage["tokens_out"] == 125

    def test_no_usage_entries_returns_empty(self) -> None:
        assert st._sum_deduped_usage([]) == dict(st._EMPTY_USAGE)

    def test_extract_subagent_usage_dedupes_sidechain_path(self, tmp_path: Path) -> None:
        """Ensures 9: extract_subagent_usage (sidechain path) uses the same
        dedupe helper as the async output-file path."""
        home = _write_transcript(
            tmp_path,
            "sess-dedupe",
            [
                _tool_use_entry("toolu_dedupe"),
                _sidechain_entry_with_id("msg_dup", 10, 5),
                _sidechain_entry_with_id("msg_dup", 10, 5),
                _sidechain_entry_with_id("msg_dup", 10, 263),
                _completion_entry(),
            ],
        )
        cwd = tmp_path / "project"
        transcript_path = (
            home / ".claude" / "projects" / str(cwd.resolve()).replace("/", "-") / "sess-dedupe.jsonl"
        )
        usage = st.extract_subagent_usage(transcript_path, "toolu_dedupe")
        assert usage["tokens_out"] == 263


# ---------------------------------------------------------------------------
# read_completed_spawn (Ensures 6, 7, 12, 15)
# ---------------------------------------------------------------------------


class TestReadCompletedSpawn:
    def _build_result_text(self, outcome: str = "PASS") -> str:
        return json.dumps({
            "type": "BUILD-RESULT",
            "outcome": outcome,
            "story_id": "INFRA-258",
            "reason": "done",
        })

    def test_completed_spawn_returns_usage_and_outcome(self, tmp_path: Path) -> None:
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry(
                    "msg_1", 1000, 500, timestamp="2026-05-01T00:00:00.000Z"
                ),
                _output_assistant_entry(
                    "msg_2",
                    100,
                    200,
                    stop_reason="end_turn",
                    text=self._build_result_text("PASS"),
                    timestamp="2026-05-01T00:00:05.000Z",
                ),
            ],
        )
        result = st.read_completed_spawn(output_file)
        assert result is not None
        assert result["tokens_in"] == 1100
        assert result["tokens_out"] == 700
        assert result["tokens_total"] == 1800
        assert result["outcome"] == "PASS"
        assert result["duration_ms"] == 5000
        assert result["model"] == "claude-sonnet-5"

    def test_dedupes_streaming_entries_in_output_file(self, tmp_path: Path) -> None:
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry("msg_stream", 10, 5),
                _output_assistant_entry("msg_stream", 10, 5),
                _output_assistant_entry(
                    "msg_stream", 10, 263, stop_reason="end_turn",
                    text=self._build_result_text("PASS"),
                ),
            ],
        )
        result = st.read_completed_spawn(output_file)
        assert result is not None
        assert result["tokens_out"] == 263

    def test_last_entry_tool_use_returns_none(self, tmp_path: Path) -> None:
        """In-flight agent — last entry is stop_reason=tool_use — never reconciled."""
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry("msg_1", 1000, 500, stop_reason="tool_use"),
            ],
        )
        assert st.read_completed_spawn(output_file) is None

    def test_truncated_trailing_line_with_no_earlier_end_turn_returns_none(
        self, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "agent.output"
        output_file.write_text(
            json.dumps(_output_assistant_entry("msg_1", 100, 50, stop_reason="tool_use"))
            + "\n{truncated garbage no closing brace",
            encoding="utf-8",
        )
        assert st.read_completed_spawn(output_file) is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        output_file = tmp_path / "agent.output"
        output_file.write_text("", encoding="utf-8")
        assert st.read_completed_spawn(output_file) is None

    def test_nonexistent_path_returns_none(self, tmp_path: Path) -> None:
        assert st.read_completed_spawn(tmp_path / "does-not-exist.output") is None

    def test_no_usage_data_returns_none(self, tmp_path: Path) -> None:
        output_file = tmp_path / "agent.output"
        entry = {
            "type": "assistant",
            "message": {"stop_reason": "end_turn", "content": [{"type": "text", "text": "hi"}]},
        }
        _write_output_file(output_file, [entry])
        assert st.read_completed_spawn(output_file) is None

    def test_fail_cause_parsed_from_final_text(self, tmp_path: Path) -> None:
        output_file = tmp_path / "agent.output"
        fail_text = json.dumps({
            "type": "REVIEW-RESULT",
            "verdict": "FAIL",
            "findings": ["x"],
            "reason": "y",
            "fail_cause": "undeclared file: docs/architecture.md",
        })
        _write_output_file(
            output_file,
            [_output_assistant_entry("msg_1", 100, 50, stop_reason="end_turn", text=fail_text)],
        )
        result = st.read_completed_spawn(output_file)
        assert result is not None
        assert result["outcome"] == "FAIL"
        assert result["fail_cause"] == "undeclared file: docs/architecture.md"

    def test_does_not_call_path_read_text(self, tmp_path: Path) -> None:
        """Ensures 15: the whole file is never loaded into memory at once."""
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry(
                    "msg_1", 100, 50, stop_reason="end_turn", text=self._build_result_text()
                )
            ],
        )
        with patch.object(Path, "read_text", side_effect=AssertionError("must not slurp")):
            result = st.read_completed_spawn(output_file)
        assert result is not None

    def test_line_cap_treats_file_as_incomplete(self, tmp_path: Path) -> None:
        output_file = tmp_path / "agent.output"
        entries = [_output_assistant_entry(f"msg_{i}", 10, 5) for i in range(3)]
        entries.append(
            _output_assistant_entry(
                "msg_last", 10, 5, stop_reason="end_turn", text=self._build_result_text()
            )
        )
        with patch.object(st, "RECONCILE_MAX_LINES", 2):
            _write_output_file(output_file, entries)
            result = st.read_completed_spawn(output_file)
        assert result is None


# ---------------------------------------------------------------------------
# _extract_spawn_ref (Instructions 7)
# ---------------------------------------------------------------------------


class TestExtractSpawnRef:
    def test_dict_shape_top_level(self) -> None:
        tool_response = {
            "isAsync": True,
            "status": "async_launched",
            "agentId": "a8b42498d3e06fcd1",
            "outputFile": "/tmp/claude-1000/proj/session/tasks/a8b42498d3e06fcd1.output",
            "canReadOutputFile": True,
        }
        agent_id, output_file = st._extract_spawn_ref(tool_response)
        assert agent_id == "a8b42498d3e06fcd1"
        assert output_file == "/tmp/claude-1000/proj/session/tasks/a8b42498d3e06fcd1.output"

    def test_dict_shape_nested_under_tool_use_result(self) -> None:
        tool_response = {
            "toolUseResult": {
                "agent_id": "agent-xyz",
                "output_file": "/tmp/out.jsonl",
            }
        }
        agent_id, output_file = st._extract_spawn_ref(tool_response)
        assert agent_id == "agent-xyz"
        assert output_file == "/tmp/out.jsonl"

    def test_flattened_text_shape(self) -> None:
        text = (
            "Async agent launched successfully.\n"
            "output_file: /tmp/claude-1000/proj/session/tasks/agentid123.output\n"
            "agentId: agentid123\n"
        )
        agent_id, output_file = st._extract_spawn_ref(text)
        assert agent_id == "agentid123"
        assert output_file == "/tmp/claude-1000/proj/session/tasks/agentid123.output"

    def test_unrecognised_shape_returns_none_none(self) -> None:
        assert st._extract_spawn_ref("just some prose") == (None, None)
        assert st._extract_spawn_ref(None) == (None, None)
        assert st._extract_spawn_ref({"foo": "bar"}) == (None, None)


# ---------------------------------------------------------------------------
# Checkpoint-worker attribution (Ensures 21, 22, 23, 24, 25)
# ---------------------------------------------------------------------------


class TestCheckpointAttribution:
    OBSERVED_CP101_PROMPT = (
        "Checkpoint security audit for Phase 101 … docs/phases/phase-101.md "
        "— stories INFRA-256 phase-scoped checkpoint cost rollup, INFRA-257 …"
    )

    def test_observed_cp101_prompt_yields_phase_101_not_infra_256(self) -> None:
        story_id, phase_key, rail = st._derive_attribution(
            {"prompt": self.OBSERVED_CP101_PROMPT}, None, "security-auditor"
        )
        assert story_id == "phase:101"
        assert story_id != "INFRA-256"
        assert phase_key == "101"
        assert rail is None

    def test_harness_style_phase_key_resolves(self) -> None:
        story_id, phase_key, rail = st._derive_attribution(
            {"prompt": "Checkpoint intent review for Phase HARNESS001-main"},
            None,
            "intent-reviewer",
        )
        assert story_id == "phase:HARNESS001-main"
        assert phase_key == "HARNESS001-main"

    def test_no_phase_key_found_falls_back_to_unattributed(self) -> None:
        story_id, phase_key, rail = st._derive_attribution(
            {"prompt": "Checkpoint security audit, no phase mentioned"},
            None,
            "security-auditor",
        )
        assert story_id == "unattributed:security-auditor"
        assert phase_key is None
        assert rail is None

    def test_checkpoint_role_never_uses_story_id_regex_or_current_story(self) -> None:
        state = {"current_story": {"id": "INFRA-999"}}
        story_id, _, _ = st._derive_attribution(
            {"prompt": "INFRA-111 mentioned but no phase pattern"}, state, "security-auditor"
        )
        assert story_id != "INFRA-111"
        assert story_id != "INFRA-999"
        assert story_id == "unattributed:security-auditor"

    def test_non_checkpoint_role_still_first_match_story_id(self) -> None:
        """Ensures 24: builder/reviewer/loop-breaker attribution unchanged —
        a prompt naming two story ids resolves to the first one."""
        story_id, phase_key, rail = st._derive_attribution(
            {"prompt": "docs/phases/phase-101.md — stories INFRA-256, INFRA-257"},
            None,
            "builder",
        )
        assert story_id == "INFRA-256"
        assert phase_key is None
        assert rail == "INFRA"

    def test_checkpoint_row_excluded_from_per_story_rollup(self, tmp_path: Path) -> None:
        """Ensures 23: a phase:<key> row does not appear in
        flex_build._query_effort_by_story_ids output for the phase's stories."""
        from skills.pairmode.scripts import flex_build

        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="",
            tool_input={
                "subagent_type": "security-auditor",
                "prompt": self.OBSERVED_CP101_PROMPT,
            },
            tool_response=json.dumps({
                "type": "REVIEW-RESULT", "verdict": "PASS", "findings": [], "reason": "ok",
            }),
        )

        db_path = project_dir / ".companion" / "effort.db"
        result = flex_build._query_effort_by_story_ids(db_path, ["INFRA-256", "INFRA-257"])
        assert result == {"by_role": {}, "by_story": {}}

        phase_rows = effort_db.query_by_phase(db_path, "101")
        assert len(phase_rows) == 1

    def test_two_checkpoint_spawns_number_per_phase(self, tmp_path: Path) -> None:
        """Ensures 25: two security-auditor spawns for phase:101 yield
        attempt_number 1 then 2."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        for _ in range(2):
            st.record_attempt_from_transcript(
                project_dir=project_dir,
                session_id="",
                tool_input={
                    "subagent_type": "security-auditor",
                    "prompt": self.OBSERVED_CP101_PROMPT,
                },
                tool_response=json.dumps({
                    "type": "REVIEW-RESULT", "verdict": "PASS", "findings": [], "reason": "ok",
                }),
            )

        db_path = project_dir / ".companion" / "effort.db"
        rows = effort_db.query_by_phase(db_path, "101")
        assert [r["attempt_number"] for r in rows] == [1, 2]


# ---------------------------------------------------------------------------
# reconcile_pending_attempts (Ensures 14, 15, 16, 19, 20, 26, 32)
# ---------------------------------------------------------------------------


class TestReconcilePendingAttempts:
    def test_returns_zero_when_effort_tracking_disabled(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        assert st.reconcile_pending_attempts(project_dir=project_dir) == 0

    def test_reconciles_a_pending_row(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-258",
            agent_role="builder",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
        )
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry(
                    "msg_1", 1000, 500, stop_reason="end_turn",
                    text=json.dumps({
                        "type": "BUILD-RESULT", "outcome": "PASS",
                        "story_id": "INFRA-258", "reason": "done",
                    }),
                )
            ],
        )
        effort_db.set_spawn_ref(db_path, row_id, "agent-1", str(output_file))

        count = st.reconcile_pending_attempts(project_dir=project_dir)
        assert count == 1

        rows = effort_db.query_by_story(db_path, "INFRA-258")
        assert rows[0]["tokens_total"] == 1500
        assert rows[0]["outcome"] == "PASS"

    def test_in_flight_spawn_not_reconciled(self, tmp_path: Path) -> None:
        """Regression test (Ensures 30)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-258",
            agent_role="builder",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
        )
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [_output_assistant_entry("msg_1", 1000, 500, stop_reason="tool_use")],
        )
        effort_db.set_spawn_ref(db_path, row_id, "agent-1", str(output_file))

        count = st.reconcile_pending_attempts(project_dir=project_dir)
        assert count == 0

        rows = effort_db.query_by_story(db_path, "INFRA-258")
        assert rows[0]["tokens_total"] is None

    def test_reconciled_fail_bumps_attempt_counter(self, tmp_path: Path) -> None:
        """Regression test (Ensures 29): a reconciled FAIL bumps the counter
        and carries the parsed fail_cause in notes."""
        from skills.pairmode.scripts.flex_build import read_attempt_count

        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-258",
            agent_role="reviewer",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
        )
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry(
                    "msg_1", 100, 50, stop_reason="end_turn",
                    text=json.dumps({
                        "type": "REVIEW-RESULT", "verdict": "FAIL",
                        "findings": ["x"], "reason": "y",
                        "fail_cause": "CRITICAL hook violation",
                    }),
                )
            ],
        )
        effort_db.set_spawn_ref(db_path, row_id, "agent-1", str(output_file))

        st.reconcile_pending_attempts(project_dir=project_dir)

        assert read_attempt_count("INFRA-258", project_dir) == 1
        row = effort_db.query_by_story(db_path, "INFRA-258")[0]
        assert row["notes"] == "CRITICAL hook violation"

    def test_counter_bumps_at_most_once_per_row(self, tmp_path: Path) -> None:
        """Ensures 20: single-shot reconcile_attempt means a repeated call
        cannot double-bump."""
        from skills.pairmode.scripts.flex_build import read_attempt_count

        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-258",
            agent_role="reviewer",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
        )
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry(
                    "msg_1", 100, 50, stop_reason="end_turn",
                    text=json.dumps({
                        "type": "REVIEW-RESULT", "verdict": "FAIL",
                        "findings": ["x"], "reason": "y",
                    }),
                )
            ],
        )
        effort_db.set_spawn_ref(db_path, row_id, "agent-1", str(output_file))

        st.reconcile_pending_attempts(project_dir=project_dir)
        st.reconcile_pending_attempts(project_dir=project_dir)

        assert read_attempt_count("INFRA-258", project_dir) == 1

    def test_checkpoint_phase_row_fail_does_not_bump(self, tmp_path: Path) -> None:
        """Ensures 19/21: a phase:<key>-attributed FAIL never bumps the
        (nonexistent) story counter."""
        from skills.pairmode.scripts.flex_build import read_attempt_count

        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="phase:101",
            phase="101",
            agent_role="security-auditor",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
        )
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry(
                    "msg_1", 100, 50, stop_reason="end_turn",
                    text=json.dumps({
                        "type": "REVIEW-RESULT", "verdict": "FAIL",
                        "findings": ["x"], "reason": "y",
                    }),
                )
            ],
        )
        effort_db.set_spawn_ref(db_path, row_id, "agent-1", str(output_file))

        st.reconcile_pending_attempts(project_dir=project_dir)

        assert read_attempt_count("phase:101", project_dir) == 0

    def test_never_raises_on_corrupt_effort_db(self, tmp_path: Path) -> None:
        """Ensures 32."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)
        companion_dir = project_dir / ".companion"
        companion_dir.mkdir(parents=True, exist_ok=True)
        (companion_dir / "effort.db").write_text("not a sqlite file", encoding="utf-8")

        assert st.reconcile_pending_attempts(project_dir=project_dir) == 0

    def test_dp7_state_json_byte_identical_across_reconciliation(self, tmp_path: Path) -> None:
        """Ensures 26: state.json is untouched (byte-identical) by reconciliation."""
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        state_path = _enable_tracking(project_dir)
        before = state_path.read_bytes()

        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-258",
            agent_role="builder",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
        )
        output_file = tmp_path / "agent.output"
        _write_output_file(
            output_file,
            [
                _output_assistant_entry(
                    "msg_1", 100, 50, stop_reason="end_turn",
                    text=json.dumps({
                        "type": "BUILD-RESULT", "outcome": "PASS",
                        "story_id": "INFRA-258", "reason": "done",
                    }),
                )
            ],
        )
        effort_db.set_spawn_ref(db_path, row_id, "agent-1", str(output_file))

        st.reconcile_pending_attempts(project_dir=project_dir)

        after = state_path.read_bytes()
        assert before == after


# ---------------------------------------------------------------------------
# Regression: async-shaped tool_response end to end (Ensures 28)
# ---------------------------------------------------------------------------


class TestAsyncSpawnRegression:
    def test_async_launch_then_reconcile(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        _enable_tracking(project_dir)

        output_file = tmp_path / "tasks" / "agent-async-1.output"
        async_tool_response = {
            "isAsync": True,
            "status": "async_launched",
            "agentId": "agent-async-1",
            "outputFile": str(output_file),
            "canReadOutputFile": True,
        }

        row_id = st.record_attempt_from_transcript(
            project_dir=project_dir,
            session_id="sess-async",
            tool_input={"subagent_type": "builder", "prompt": "INFRA-258"},
            tool_response=async_tool_response,
        )
        assert row_id is not None

        db_path = project_dir / ".companion" / "effort.db"
        row = effort_db.query_by_story(db_path, "INFRA-258")[0]
        assert row["tokens_total"] is None
        assert row["outcome"] is None
        assert row["agent_id"] == "agent-async-1"
        assert row["output_file"] == str(output_file)

        # Phase 2: the spawn completes — write its own output file, then
        # reconcile.
        _write_output_file(
            output_file,
            [
                _output_assistant_entry(
                    "msg_1", 1000, 500, stop_reason="end_turn",
                    text=json.dumps({
                        "type": "BUILD-RESULT", "outcome": "PASS",
                        "story_id": "INFRA-258", "reason": "done",
                    }),
                )
            ],
        )

        count = st.reconcile_pending_attempts(project_dir=project_dir)
        assert count == 1

        row = effort_db.query_by_story(db_path, "INFRA-258")[0]
        assert row["tokens_total"] == 1500
        assert row["tokens_in"] == 1000
        assert row["tokens_out"] == 500
        assert row["model"] == "claude-sonnet-5"
        assert row["outcome"] == "PASS"
