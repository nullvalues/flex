"""Tests for skills/pairmode/scripts/context_budget.py.

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_context_budget.py -x -q
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

# Ensure the pairmode scripts directory is on the path.
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts")
)

import context_budget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_transcript(path: Path, entries: list[dict]) -> None:
    """Write JSONL transcript with the given entries."""
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _assistant(input_tokens: int, cache_read: int, cache_create: int) -> dict:
    """Build an assistant transcript entry with the given usage tokens."""
    return {
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": 100,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
            }
        },
    }


def _create_effort_db(db_path: Path) -> None:
    """Create an empty attempts table matching the production schema."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT NOT NULL,
                phase TEXT,
                rail TEXT,
                agent_role TEXT NOT NULL,
                model TEXT,
                attempt_number INTEGER NOT NULL,
                tokens_total INTEGER,
                tokens_in INTEGER,
                tokens_out INTEGER,
                cache_read_tokens INTEGER,
                cache_write_tokens INTEGER,
                tool_uses INTEGER,
                duration_ms INTEGER,
                outcome TEXT,
                notes TEXT,
                ts TEXT NOT NULL,
                story_class TEXT,
                model_selection_reason TEXT,
                backend TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _insert_attempts(
    db_path: Path,
    phase: str,
    tokens_list: list[int | None],
    agent_role: str = "builder",
) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        for i, tokens in enumerate(tokens_list, start=1):
            conn.execute(
                """
                INSERT INTO attempts
                    (story_id, phase, rail, agent_role, attempt_number,
                     tokens_total, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"T-{i:03d}",
                    phase,
                    "TEST",
                    agent_role,
                    1,
                    tokens,
                    "2026-01-01T00:00:00+00:00",
                ),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# compute_context_tokens
# ---------------------------------------------------------------------------


def test_compute_context_tokens_single_assistant(tmp_path):
    """Single assistant message: returns sum of input+cache_read+cache_create."""
    transcript = tmp_path / "t.jsonl"
    _write_transcript(transcript, [_assistant(1000, 5000, 200)])
    assert context_budget.compute_context_tokens(str(transcript)) == 6200


def test_compute_context_tokens_last_turn_not_running_total(tmp_path):
    """Multiple assistant turns: returns the LAST turn's sum, not running total."""
    transcript = tmp_path / "t.jsonl"
    _write_transcript(
        transcript,
        [
            _assistant(500, 1000, 100),
            {"type": "user", "message": {"content": "hi"}},
            _assistant(800, 2000, 200),
            {"type": "user", "message": {"content": "hi again"}},
            _assistant(1200, 4000, 300),
        ],
    )
    # Last assistant turn: 1200 + 4000 + 300 = 5500
    assert context_budget.compute_context_tokens(str(transcript)) == 5500


def test_compute_context_tokens_missing_file(tmp_path):
    """Missing file: returns None."""
    assert context_budget.compute_context_tokens(str(tmp_path / "missing.jsonl")) is None


def test_compute_context_tokens_empty_file(tmp_path):
    """Empty file: returns None."""
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("", encoding="utf-8")
    assert context_budget.compute_context_tokens(str(transcript)) is None


def test_compute_context_tokens_assistant_without_usage(tmp_path):
    """Assistant turns with no usage object: returns None."""
    transcript = tmp_path / "t.jsonl"
    _write_transcript(
        transcript,
        [
            {"type": "assistant", "message": {"content": "no usage here"}},
            {"type": "assistant", "message": {}},
        ],
    )
    assert context_budget.compute_context_tokens(str(transcript)) is None


def test_compute_context_tokens_tail_read_is_fast(tmp_path):
    """Large transcript (>1MB): tail-read path returns under 100ms."""
    transcript = tmp_path / "big.jsonl"
    # Pad with user messages to inflate file size past 1MB.
    user_padding = {"type": "user", "message": {"content": "x" * 1000}}
    lines: list[dict] = []
    for _ in range(2000):  # ~2MB
        lines.append(user_padding)
    # Append the final assistant turn that should be the answer.
    lines.append(_assistant(1234, 5678, 90))
    _write_transcript(transcript, lines)
    # Confirm size really is large.
    assert transcript.stat().st_size > 1_000_000

    start = time.perf_counter()
    result = context_budget.compute_context_tokens(str(transcript))
    elapsed = time.perf_counter() - start

    assert result == 1234 + 5678 + 90
    assert elapsed < 0.1, f"tail read took {elapsed:.3f}s (>100ms)"


# ---------------------------------------------------------------------------
# estimate_next_step_tokens
# ---------------------------------------------------------------------------


def test_estimate_next_step_tokens_fewer_than_five(tmp_path):
    """<5 attempts in phase: returns seeded_default."""
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    _insert_attempts(db_path, phase="1", tokens_list=[10000, 20000, 30000])

    result = context_budget.estimate_next_step_tokens(db_path, "1", seeded_default=4242)
    assert result == 4242


def test_estimate_next_step_tokens_five_or_more(tmp_path):
    """>=5 attempts in phase: returns median(tokens_total)."""
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    _insert_attempts(
        db_path,
        phase="1",
        tokens_list=[10000, 20000, 30000, 40000, 50000],
    )
    # median of 10000,20000,30000,40000,50000 = 30000
    result = context_budget.estimate_next_step_tokens(db_path, "1", seeded_default=99999)
    assert result == 30000


def test_estimate_next_step_tokens_missing_db(tmp_path):
    """Missing db_path: returns seeded_default."""
    result = context_budget.estimate_next_step_tokens(
        tmp_path / "no-such.db", "1", seeded_default=7777
    )
    assert result == 7777


def test_estimate_next_step_tokens_none_db(tmp_path):
    """db_path=None: returns seeded_default."""
    result = context_budget.estimate_next_step_tokens(None, "1", seeded_default=8888)
    assert result == 8888


def test_estimate_next_step_tokens_none_phase(tmp_path):
    """phase=None: returns seeded_default."""
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    _insert_attempts(db_path, phase="1", tokens_list=[1, 2, 3, 4, 5, 6])
    result = context_budget.estimate_next_step_tokens(db_path, None, seeded_default=1234)
    assert result == 1234


# ---------------------------------------------------------------------------
# should_block
# ---------------------------------------------------------------------------


def test_should_block_under_ceiling_returns_false():
    """current 110k + expected 15k = 125k, ceiling = 120k * 1.10 = 132k. No block."""
    assert (
        context_budget.should_block(
            current_tokens=110_000,
            expected_next=15_000,
            threshold=120_000,
            overrun_pct=0.10,
            acknowledged_at=None,
        )
        is False
    )


def test_should_block_over_ceiling_returns_true():
    """current 120k + expected 15k = 135k > 132k ceiling. Block."""
    assert (
        context_budget.should_block(
            current_tokens=120_000,
            expected_next=15_000,
            threshold=120_000,
            overrun_pct=0.10,
            acknowledged_at=None,
        )
        is True
    )


def test_should_block_within_margin_after_ack_returns_false():
    """Acknowledged at 140k with 10k margin; current 140k -> no re-prompt."""
    assert (
        context_budget.should_block(
            current_tokens=140_000,
            expected_next=15_000,
            threshold=120_000,
            overrun_pct=0.10,
            acknowledged_at=140_000,
            reprompt_margin=10_000,
        )
        is False
    )


def test_should_block_crossed_margin_after_ack_returns_true():
    """Acknowledged at 140k with 10k margin; current 150k -> re-prompt."""
    assert (
        context_budget.should_block(
            current_tokens=150_000,
            expected_next=15_000,
            threshold=120_000,
            overrun_pct=0.10,
            acknowledged_at=140_000,
            reprompt_margin=10_000,
        )
        is True
    )


# ---------------------------------------------------------------------------
# render_alert_prompt
# ---------------------------------------------------------------------------


def test_render_alert_prompt_matches_fixture_byte_for_byte():
    """Render matches the fixture file byte-for-byte except for substitutions."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "context_budget_prompt.txt"
    )
    expected = (
        fixture_path.read_text(encoding="utf-8")
        .replace("[story RAIL-NNN]", "[story HOOKS-001]")
        .replace("[N]", "140,000")
        .replace("[T]", "120,000")
        .replace("[O]", "10%")
    )

    rendered = context_budget.render_alert_prompt(
        story_id="HOOKS-001",
        tokens=140_000,
        threshold=120_000,
        overrun_pct=0.10,
    )
    assert rendered == expected


def test_render_alert_prompt_story_id_falls_back_to_current():
    """story_id=None substitutes 'current' into the [story RAIL-NNN] slot."""
    rendered = context_budget.render_alert_prompt(
        story_id=None,
        tokens=100,
        threshold=200,
        overrun_pct=0.10,
    )
    assert "[story current]" in rendered


# ---------------------------------------------------------------------------
# decide — end-to-end
# ---------------------------------------------------------------------------


def _setup_project(
    tmp_path: Path,
    state: dict,
    attempt_tokens: list[int] | None = None,
    transcript_entries: list[dict] | None = None,
) -> tuple[Path, Path]:
    """Lay out a synthetic project with state.json, effort.db, and a transcript."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")

    if attempt_tokens is not None:
        db_path = companion / "effort.db"
        _create_effort_db(db_path)
        _insert_attempts(db_path, phase=str(state.get("current_phase", "1")),
                          tokens_list=attempt_tokens)

    transcript = tmp_path / "transcript.jsonl"
    if transcript_entries is not None:
        _write_transcript(transcript, transcript_entries)
    return tmp_path, transcript


def test_decide_returns_block_dict_when_over_ceiling(tmp_path):
    """End-to-end: returns the expected dict when budget exceeded."""
    project_dir, transcript = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "47",
            "current_story": "INFRA-127",
        },
        transcript_entries=[_assistant(100_000, 20_000, 5_000)],  # 125k
    )

    result = context_budget.decide(project_dir, str(transcript))
    assert result is not None
    assert result["block"] is True
    assert result["tokens"] == 125_000
    assert result["acknowledged_at"] == 125_000
    assert "CONTEXT BUDGET" in result["reason"]
    assert "INFRA-127" in result["reason"]


def test_decide_returns_none_when_acknowledged_within_margin(tmp_path):
    """End-to-end: returns None when acknowledged_at is recent enough."""
    project_dir, transcript = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "context_budget_acknowledged_at": 140_000,
            "current_phase": "47",
            "current_story": "INFRA-127",
        },
        transcript_entries=[_assistant(120_000, 20_000, 5_000)],  # 145k, < 150k
    )

    result = context_budget.decide(project_dir, str(transcript))
    assert result is None


def test_decide_returns_none_on_malformed_state(tmp_path):
    """Malformed state.json: returns None (degrade safely)."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text("{not json at all", encoding="utf-8")

    transcript = tmp_path / "transcript.jsonl"
    _write_transcript(transcript, [_assistant(100_000, 20_000, 5_000)])

    result = context_budget.decide(tmp_path, str(transcript))
    assert result is None
