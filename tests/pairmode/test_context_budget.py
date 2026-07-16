"""Tests for skills/pairmode/scripts/context_budget.py.

INFRA-182: PostToolUse is the writer, PreToolUse is the reader.
- Restored _derive_transcript_path, compute_context_tokens, read_current_tokens.
- compute_context_tokens uses full reverse scan (no fixed-line tail).
- decide() reads context_current_tokens from state.json only; blocks hard
  when absent or stale (recorded_at < context_session_reset_at).
- Removed per-story dict logic (_is_entry_fresh, _read_story_token_entry).

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_context_budget.py -x -q
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from click.testing import CliRunner

# Ensure the pairmode scripts directory is on the path.
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts")
)

import context_budget  # noqa: E402
from flex_build import flex_build  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _setup_project(
    tmp_path: Path,
    state: dict,
    attempt_tokens: list[int] | None = None,
) -> Path:
    """Lay out a synthetic project with state.json and an optional effort.db."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")

    if attempt_tokens is not None:
        db_path = companion / "effort.db"
        _create_effort_db(db_path)
        _insert_attempts(
            db_path,
            phase=str(state.get("current_phase", "1")),
            tokens_list=attempt_tokens,
        )

    return tmp_path


def _make_jsonl(entries: list[dict]) -> str:
    """Serialize a list of dicts as JSONL."""
    return "\n".join(json.dumps(e) for e in entries) + "\n"


def _assistant_entry(
    input_tokens: int = 10000,
    cache_read: int = 0,
    cache_create: int = 0,
) -> dict:
    """Build a minimal assistant JSONL entry with usage."""
    return {
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
            }
        },
    }


# ---------------------------------------------------------------------------
# _derive_transcript_path
# ---------------------------------------------------------------------------


def test_derive_transcript_path_empty_session_id(tmp_path):
    """Empty session_id returns None."""
    result = context_budget._derive_transcript_path(tmp_path, "", home=tmp_path)
    assert result is None


def test_derive_transcript_path_none_session_id(tmp_path):
    """None session_id returns None."""
    result = context_budget._derive_transcript_path(tmp_path, None, home=tmp_path)  # type: ignore[arg-type]
    assert result is None


def test_derive_transcript_path_missing_file(tmp_path):
    """Non-existent JSONL file returns None (fail-open)."""
    result = context_budget._derive_transcript_path(
        tmp_path, "abc123", home=tmp_path
    )
    assert result is None


def test_derive_transcript_path_existing_file(tmp_path):
    """Existing JSONL file returns the path."""
    cwd = tmp_path / "myproject"
    cwd.mkdir()
    cwd_key = str(cwd.resolve()).replace("/", "-")
    jsonl_dir = tmp_path / ".claude" / "projects" / cwd_key
    jsonl_dir.mkdir(parents=True)
    jsonl_file = jsonl_dir / "session123.jsonl"
    jsonl_file.write_text("{}\n", encoding="utf-8")

    result = context_budget._derive_transcript_path(
        cwd, "session123", home=tmp_path
    )
    assert result == jsonl_file


# ---------------------------------------------------------------------------
# compute_context_tokens
# ---------------------------------------------------------------------------


def test_compute_context_tokens_returns_none_for_missing_file(tmp_path):
    """Missing file returns None."""
    result = context_budget.compute_context_tokens(tmp_path / "no-such.jsonl")
    assert result is None


def test_compute_context_tokens_returns_none_for_empty_file(tmp_path):
    """Empty file returns None."""
    f = tmp_path / "empty.jsonl"
    f.write_text("", encoding="utf-8")
    assert context_budget.compute_context_tokens(f) is None


def test_compute_context_tokens_finds_last_assistant_entry(tmp_path):
    """Returns usage sum from the LAST assistant entry."""
    f = tmp_path / "t.jsonl"
    f.write_text(
        _make_jsonl([
            _assistant_entry(input_tokens=5000),
            {"type": "human", "message": {}},
            _assistant_entry(input_tokens=10000, cache_read=2000),
        ]),
        encoding="utf-8",
    )
    result = context_budget.compute_context_tokens(f)
    assert result == 12000  # 10000 + 2000 from last entry


def test_compute_context_tokens_skips_non_assistant_entries(tmp_path):
    """Non-assistant entries are skipped."""
    f = tmp_path / "t.jsonl"
    f.write_text(
        _make_jsonl([
            {"type": "human", "message": {"usage": {"input_tokens": 99}}},
            _assistant_entry(input_tokens=7777),
        ]),
        encoding="utf-8",
    )
    result = context_budget.compute_context_tokens(f)
    assert result == 7777


def test_compute_context_tokens_sums_all_cache_fields(tmp_path):
    """input_tokens + cache_read + cache_create are all summed."""
    f = tmp_path / "t.jsonl"
    f.write_text(
        _make_jsonl([
            _assistant_entry(input_tokens=1000, cache_read=500, cache_create=200),
        ]),
        encoding="utf-8",
    )
    result = context_budget.compute_context_tokens(f)
    assert result == 1700


def test_compute_context_tokens_finds_entry_beyond_100_lines_within_500_bound(tmp_path):
    """Bounded scan finds assistant entry when it is beyond 100 lines but within 500 lines from end.

    INFRA-183: compute_context_tokens uses a 500-line tail (bounded scan).
    This test creates a file where the assistant entry is at line 1 and there
    are 150 non-assistant lines after it (151 lines total). All 151 lines fall
    within the 500-line tail so the entry must be found.
    """
    f = tmp_path / "long.jsonl"
    entries = [_assistant_entry(input_tokens=42000)]
    # Add 150 human entries after the assistant entry
    entries += [{"type": "human", "message": {}} for _ in range(150)]
    f.write_text(_make_jsonl(entries), encoding="utf-8")
    result = context_budget.compute_context_tokens(f)
    assert result == 42000


def test_compute_context_tokens_skips_malformed_json(tmp_path):
    """Malformed JSON lines are skipped; valid entry is found."""
    f = tmp_path / "t.jsonl"
    content = "not json\n" + json.dumps(_assistant_entry(input_tokens=3000)) + "\n"
    f.write_text(content, encoding="utf-8")
    result = context_budget.compute_context_tokens(f)
    assert result == 3000


# ---------------------------------------------------------------------------
# read_current_tokens
# ---------------------------------------------------------------------------


def test_read_current_tokens_empty_session_id(tmp_path):
    """Empty session_id returns None."""
    assert context_budget.read_current_tokens(tmp_path, session_id="") is None


def test_read_current_tokens_missing_transcript(tmp_path):
    """Missing transcript returns None."""
    assert context_budget.read_current_tokens(tmp_path, session_id="nosuch", home=tmp_path) is None


def test_read_current_tokens_valid_transcript(tmp_path):
    """Valid transcript returns token count."""
    cwd = tmp_path / "proj"
    cwd.mkdir()
    cwd_key = str(cwd.resolve()).replace("/", "-")
    jsonl_dir = tmp_path / ".claude" / "projects" / cwd_key
    jsonl_dir.mkdir(parents=True)
    jsonl_file = jsonl_dir / "sess.jsonl"
    jsonl_file.write_text(
        _make_jsonl([_assistant_entry(input_tokens=55000)]),
        encoding="utf-8",
    )
    result = context_budget.read_current_tokens(cwd, session_id="sess", home=tmp_path)
    assert result == 55000


# ---------------------------------------------------------------------------
# read_context_tokens_from_state
# ---------------------------------------------------------------------------


def test_read_context_tokens_from_state_present_int():
    """Key present with a valid positive int returns that int."""
    assert (
        context_budget.read_context_tokens_from_state(
            {"context_current_tokens": 125_000}
        )
        == 125_000
    )


def test_read_context_tokens_from_state_present_numeric_string():
    """Key present as numeric string is coerced to int."""
    assert (
        context_budget.read_context_tokens_from_state(
            {"context_current_tokens": "9999"}
        )
        == 9999
    )


def test_read_context_tokens_from_state_absent_returns_none():
    """Key absent returns None."""
    assert context_budget.read_context_tokens_from_state({}) is None


def test_read_context_tokens_from_state_zero_returns_none():
    """Zero is treated as invalid (no recorded count)."""
    assert (
        context_budget.read_context_tokens_from_state({"context_current_tokens": 0})
        is None
    )


def test_read_context_tokens_from_state_negative_returns_none():
    """Negative values are invalid."""
    assert (
        context_budget.read_context_tokens_from_state(
            {"context_current_tokens": -50}
        )
        is None
    )


def test_read_context_tokens_from_state_non_numeric_returns_none():
    """Non-numeric value returns None."""
    assert (
        context_budget.read_context_tokens_from_state(
            {"context_current_tokens": "not a number"}
        )
        is None
    )


def test_read_context_tokens_from_state_non_dict_returns_none():
    """A non-dict argument returns None."""
    assert context_budget.read_context_tokens_from_state(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# read_context_tokens_from_state — CER-041 staleness handling
# ---------------------------------------------------------------------------


def test_read_context_tokens_fresh():
    """recorded_at 10 minutes ago under default TTL=60 → returns the value."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    recorded_at = (now - timedelta(minutes=10)).isoformat()
    state = {
        "context_current_tokens": 50_000,
        "context_current_tokens_recorded_at": recorded_at,
    }
    assert (
        context_budget.read_context_tokens_from_state(state, _now=now) == 50_000
    )


def test_read_context_tokens_stale():
    """recorded_at 90 minutes ago under default TTL=60 → returns None."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    recorded_at = (now - timedelta(minutes=90)).isoformat()
    state = {
        "context_current_tokens": 50_000,
        "context_current_tokens_recorded_at": recorded_at,
    }
    assert context_budget.read_context_tokens_from_state(state, _now=now) is None


def test_read_context_tokens_no_recorded_at():
    """recorded_at absent → TTL not enforced; returns the value."""
    state = {"context_current_tokens": 50_000}
    assert (
        context_budget.read_context_tokens_from_state(state) == 50_000
    )


def test_read_context_tokens_unparseable_recorded_at():
    """recorded_at not parseable → staleness skipped; returns the value."""
    state = {
        "context_current_tokens": 50_000,
        "context_current_tokens_recorded_at": "not-a-date",
    }
    assert (
        context_budget.read_context_tokens_from_state(state) == 50_000
    )


def test_read_context_tokens_custom_ttl():
    """recorded_at 30 minutes ago under custom TTL=20 → stale; returns None."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    recorded_at = (now - timedelta(minutes=30)).isoformat()
    state = {
        "context_current_tokens": 50_000,
        "context_current_tokens_recorded_at": recorded_at,
        "context_current_tokens_ttl_minutes": 20,
    }
    assert context_budget.read_context_tokens_from_state(state, _now=now) is None


# ---------------------------------------------------------------------------
# estimate_next_step_tokens (unchanged from prior implementation)
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


def test_estimate_next_step_tokens_none_phase_global_fallback(tmp_path):
    """phase=None skips Tier 1; if global rows >=5 the global median is used.

    INFRA-171: phase=None no longer short-circuits to seeded_default when
    global data is available.
    """
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    _insert_attempts(db_path, phase="1", tokens_list=[10, 20, 30, 40, 50, 60])
    # Median of [10, 20, 30, 40, 50, 60] = 35
    result = context_budget.estimate_next_step_tokens(db_path, None, seeded_default=1234)
    assert result == 35


def test_estimate_next_step_tokens_none_phase_seeded_fallback_when_insufficient(tmp_path):
    """phase=None with < 5 global rows falls back to seeded_default."""
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    _insert_attempts(db_path, phase="1", tokens_list=[1, 2, 3])
    result = context_budget.estimate_next_step_tokens(db_path, None, seeded_default=1234)
    assert result == 1234


# ---------------------------------------------------------------------------
# estimate_next_step_tokens — INFRA-171 waterfall tests
# ---------------------------------------------------------------------------


def test_estimate_per_phase_wins_when_sufficient(tmp_path):
    """Tier 1: per-phase ≥5 rows — per-phase median returned, not global."""
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    _insert_attempts(db_path, phase="7", tokens_list=[10000, 20000, 30000, 40000, 50000])
    _insert_attempts(db_path, phase="99", tokens_list=[100000, 200000])

    result = context_budget.estimate_next_step_tokens(db_path, "7", seeded_default=99999)
    assert result == 30000


def test_estimate_global_fallback_when_per_phase_insufficient(tmp_path):
    """Tier 2: per-phase < 5 rows, global ≥ 5 — global median returned."""
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    _insert_attempts(db_path, phase="3", tokens_list=[10000, 20000])
    _insert_attempts(db_path, phase="9", tokens_list=[30000, 40000, 50000])

    result = context_budget.estimate_next_step_tokens(db_path, "3", seeded_default=99999)
    assert result == 30000


def test_estimate_seeded_fallback_when_global_insufficient(tmp_path):
    """Tier 3: global < 5 rows — seeded_default returned."""
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    _insert_attempts(db_path, phase="1", tokens_list=[10000, 20000])
    _insert_attempts(db_path, phase="2", tokens_list=[30000])

    result = context_budget.estimate_next_step_tokens(db_path, "1", seeded_default=5555)
    assert result == 5555


# ---------------------------------------------------------------------------
# should_block (pure decision, unchanged)
# ---------------------------------------------------------------------------


def test_should_block_under_ceiling_returns_false():
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
# should_block — INFRA-193 user-turn acknowledgment gate
# ---------------------------------------------------------------------------


def test_should_block_bare_retry_without_user_turn_stays_blocked():
    """Exact self-clearing repro: current_tokens == acknowledged_at and no
    intervening UserPromptSubmit event → still blocked."""
    assert (
        context_budget.should_block(
            current_tokens=140_000,
            expected_next=15_000,
            threshold=120_000,
            overrun_pct=0.10,
            acknowledged_at=140_000,
            reprompt_margin=0,
            user_turn_seq=3,
            acknowledged_user_turn_seq=3,
        )
        is True
    )


def test_should_block_suppresses_after_genuine_user_turn():
    """A genuine UserPromptSubmit event since the block (user_turn_seq
    incremented) plus the token margin satisfied → suppressed (False)."""
    assert (
        context_budget.should_block(
            current_tokens=150_000,
            expected_next=15_000,
            threshold=120_000,
            overrun_pct=0.10,
            acknowledged_at=140_000,
            reprompt_margin=10_000,
            user_turn_seq=4,
            acknowledged_user_turn_seq=3,
        )
        is False
    )


def test_should_block_acknowledged_user_turn_seq_none_is_backward_compatible():
    """acknowledged_user_turn_seq=None (pre-INFRA-192 state.json) does not
    itself force a block when the token condition alone would have
    suppressed under the pre-INFRA-193 contract (current_tokens within the
    reprompt margin of acknowledged_at)."""
    assert (
        context_budget.should_block(
            current_tokens=145_000,
            expected_next=15_000,
            threshold=120_000,
            overrun_pct=0.10,
            acknowledged_at=140_000,
            reprompt_margin=10_000,
            user_turn_seq=0,
            acknowledged_user_turn_seq=None,
        )
        is False
    )


# ---------------------------------------------------------------------------
# render_alert_prompt — now takes expected_next
# ---------------------------------------------------------------------------


def test_render_alert_prompt_matches_fixture_with_substitutions():
    """Render substitutes every placeholder including the new [E] and [R]."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "context_budget_prompt.txt"
    )
    threshold = 120_000
    overrun_pct = 0.10
    tokens = 140_000
    expected_next = 17_500
    ceiling = int(threshold * (1.0 + overrun_pct))
    remaining = ceiling - tokens

    expected = (
        fixture_path.read_text(encoding="utf-8")
        .replace("[story RAIL-NNN]", "[story HOOKS-001]")
        .replace("[N]", f"{tokens:,}")
        .replace("[T]", f"{threshold:,}")
        .replace("[O]", f"{overrun_pct:.0%}")
        .replace("[E]", f"{expected_next:,}")
        .replace("[R]", f"{remaining:,}")
    )

    rendered = context_budget.render_alert_prompt(
        story_id="HOOKS-001",
        tokens=tokens,
        threshold=threshold,
        overrun_pct=overrun_pct,
        expected_next=expected_next,
    )
    assert rendered == expected


def test_render_alert_prompt_story_id_falls_back_to_current():
    """story_id=None substitutes 'current' into the [story RAIL-NNN] slot."""
    rendered = context_budget.render_alert_prompt(
        story_id=None,
        tokens=100,
        threshold=200,
        overrun_pct=0.10,
        expected_next=50,
    )
    assert "[story current]" in rendered


def test_render_alert_prompt_substitutes_expected_next_and_remaining():
    """Both [E] and [R] are substituted with computed values."""
    rendered = context_budget.render_alert_prompt(
        story_id="INFRA-148",
        tokens=130_000,
        threshold=120_000,
        overrun_pct=0.10,
        expected_next=12_345,
    )
    # ceiling = 132,000; remaining = 132,000 - 130,000 = 2,000
    assert "12,345 tokens" in rendered
    assert "2,000 tokens remaining" in rendered


# ---------------------------------------------------------------------------
# decide — state.json contract
# ---------------------------------------------------------------------------


def test_decide_returns_block_when_over_ceiling(tmp_path):
    """state.json reports tokens above ceiling → block dict with prompt."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "47",
            "current_story": "INFRA-127",
            "context_current_tokens": 125_000,
        },
    )

    result = context_budget.decide(project_dir)
    assert result is not None
    assert result["block"] is True
    assert result["tokens"] == 125_000
    assert result["acknowledged_at"] == 125_000
    assert "CONTEXT BUDGET" in result["reason"]
    assert "INFRA-127" in result["reason"]


def test_decide_returns_none_when_under_ceiling(tmp_path):
    """state.json reports tokens well under ceiling → pass through (None)."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "47",
            "current_story": "INFRA-148",
            "context_current_tokens": 10_000,
        },
    )

    result = context_budget.decide(project_dir)
    assert result is None


def test_decide_returns_check_required_when_tokens_absent(tmp_path):
    """state.json with no context_current_tokens → block with CONTEXT CHECK REQUIRED."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "current_phase": "58",
            "current_story": "INFRA-148",
        },
    )

    result = context_budget.decide(project_dir)
    assert result is not None
    assert result["block"] is True
    assert result["tokens"] == 0
    assert result["acknowledged_at"] == 0
    assert "CONTEXT CHECK REQUIRED" in result["reason"]


def test_decide_returns_none_when_acknowledged_within_margin(tmp_path):
    """Already-acknowledged budget within reprompt margin → None."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "context_budget_acknowledged_at": 140_000,
            "current_phase": "47",
            "current_story": "INFRA-127",
            "context_current_tokens": 145_000,
        },
    )

    result = context_budget.decide(project_dir)
    assert result is None


def test_decide_returns_none_on_malformed_state(tmp_path):
    """Malformed state.json: _read_state returns {} → CONTEXT CHECK REQUIRED block."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text("{not json at all", encoding="utf-8")

    result = context_budget.decide(tmp_path)
    assert result is not None
    assert result["block"] is True
    assert "CONTEXT CHECK REQUIRED" in result["reason"]


def test_decide_returns_none_when_state_absent(tmp_path):
    """No .companion/state.json: pass through (non-pairmode project)."""
    result = context_budget.decide(tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# decide — INFRA-193 user-turn acknowledgment gate
# ---------------------------------------------------------------------------


def test_decide_block_dict_includes_user_turn_seq_at_block(tmp_path):
    """Block dict includes user_turn_seq_at_block matching state's current seq."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "85",
            "current_story": "INFRA-193",
            "context_current_tokens": 125_000,
            "context_budget_user_turn_seq": 7,
        },
    )
    result = context_budget.decide(project_dir)
    assert result is not None
    assert result["block"] is True
    assert result["user_turn_seq_at_block"] == 7


def test_decide_is_read_only_does_not_write_user_turn_ack(tmp_path):
    """decide() never writes context_budget_acknowledged_user_turn_seq (D11)."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "85",
            "current_story": "INFRA-193",
            "context_current_tokens": 125_000,
            "context_budget_user_turn_seq": 7,
        },
    )
    result = context_budget.decide(project_dir)
    assert result is not None
    state_on_disk = json.loads(
        (project_dir / ".companion" / "state.json").read_text(encoding="utf-8")
    )
    assert "context_budget_acknowledged_user_turn_seq" not in state_on_disk


# ---------------------------------------------------------------------------
# decide — CER-040 malformed state.json edge cases
# ---------------------------------------------------------------------------


def test_decide_no_state_file_with_companion_dir_context_check_required(tmp_path):
    """`.companion/` directory exists but state.json is absent → CONTEXT CHECK REQUIRED.

    CER-040: a pairmode project (has .companion/) with a missing state.json should
    surface the gate as needing attention, not silently pass.
    """
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    result = context_budget.decide(tmp_path)
    assert result is not None
    assert result["block"] is True
    assert "CONTEXT CHECK REQUIRED" in result["reason"]


def test_decide_malformed_state_file_context_check_required(tmp_path):
    """state.json exists with invalid JSON → block=True with CONTEXT CHECK REQUIRED."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text("not json{{", encoding="utf-8")

    result = context_budget.decide(tmp_path)
    assert result is not None
    assert result["block"] is True
    assert "CONTEXT CHECK REQUIRED" in result["reason"]


def test_decide_non_dict_state_file_context_check_required(tmp_path):
    """state.json exists with valid JSON but non-dict root → block=True with CONTEXT CHECK REQUIRED."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    result = context_budget.decide(tmp_path)
    assert result is not None
    assert result["block"] is True
    assert "CONTEXT CHECK REQUIRED" in result["reason"]


# ---------------------------------------------------------------------------
# decide — staleness check (INFRA-182)
# ---------------------------------------------------------------------------


def test_decide_blocks_when_recorded_at_before_session_reset(tmp_path):
    """context_current_tokens_recorded_at < context_session_reset_at → CONTEXT CHECK REQUIRED.

    INFRA-182: strict less-than staleness check. If recorded_at predates the
    last session reset, the count is stale and must be refreshed.
    """
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "current_phase": "74",
            "context_current_tokens": 50_000,
            # recorded_at BEFORE session reset
            "context_current_tokens_recorded_at": "2026-06-22T10:00:00+00:00",
            "context_session_reset_at": "2026-06-22T11:00:00+00:00",
        },
    )
    result = context_budget.decide(project_dir)
    assert result is not None
    assert result["block"] is True
    assert "CONTEXT CHECK REQUIRED" in result["reason"]


def test_decide_proceeds_when_recorded_at_equals_session_reset(tmp_path):
    """recorded_at == context_session_reset_at → NOT stale (baseline case).

    The SessionStart hook sets both to the same timestamp on /clear.
    Equal means the baseline was just written — treat as fresh.
    """
    ts = "2026-06-22T11:00:00+00:00"
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "current_phase": "74",
            "context_current_tokens": 25_000,
            "context_current_tokens_recorded_at": ts,
            "context_session_reset_at": ts,
        },
    )
    result = context_budget.decide(project_dir)
    # 25_000 + 1_000 = 26_000 < 132_000 → under budget → None
    assert result is None


def test_decide_proceeds_when_recorded_at_after_session_reset(tmp_path):
    """recorded_at > context_session_reset_at → fresh, no block from staleness."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "current_phase": "74",
            "context_current_tokens": 25_000,
            "context_current_tokens_recorded_at": "2026-06-22T12:00:00+00:00",
            "context_session_reset_at": "2026-06-22T11:00:00+00:00",
        },
    )
    result = context_budget.decide(project_dir)
    assert result is None


def test_decide_proceeds_when_no_session_reset_at(tmp_path):
    """context_session_reset_at absent → fail-open, no staleness block."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "current_phase": "74",
            "context_current_tokens": 25_000,
            "context_current_tokens_recorded_at": "2026-06-22T10:00:00+00:00",
            # No context_session_reset_at
        },
    )
    result = context_budget.decide(project_dir)
    assert result is None


def test_decide_blocks_when_tokens_absent_from_state(tmp_path):
    """No context_current_tokens → CONTEXT CHECK REQUIRED (independent of staleness)."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "current_phase": "74",
            "context_session_reset_at": "2026-06-22T11:00:00+00:00",
            # No context_current_tokens
        },
    )
    result = context_budget.decide(project_dir)
    assert result is not None
    assert result["block"] is True
    assert "CONTEXT CHECK REQUIRED" in result["reason"]


# ---------------------------------------------------------------------------
# set-context-tokens CLI
# ---------------------------------------------------------------------------


def _invoke_set_context_tokens(project_dir: Path, tokens: int):
    runner = CliRunner()
    return runner.invoke(
        flex_build,
        [
            "set-context-tokens",
            "--tokens",
            str(tokens),
            "--project-dir",
            str(project_dir),
        ],
    )


def test_set_context_tokens_writes_state(tmp_path):
    """Writes context_current_tokens to .companion/state.json."""
    project_dir = tmp_path / "sub" / "project"
    project_dir.mkdir(parents=True)

    result = _invoke_set_context_tokens(project_dir, 87_500)
    assert result.exit_code == 0, result.output
    assert "recorded 87,500 tokens" in result.output

    state_path = project_dir / ".companion" / "state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["context_current_tokens"] == 87_500


def test_set_context_tokens_preserves_existing_state(tmp_path):
    """An existing state.json with other keys is preserved and merged."""
    project_dir = tmp_path / "sub" / "project"
    companion = project_dir / ".companion"
    companion.mkdir(parents=True)
    (companion / "state.json").write_text(
        json.dumps({"pairmode_version": "1.0", "current_story": "INFRA-148"}),
        encoding="utf-8",
    )

    result = _invoke_set_context_tokens(project_dir, 42_000)
    assert result.exit_code == 0, result.output

    state = json.loads((companion / "state.json").read_text(encoding="utf-8"))
    assert state["context_current_tokens"] == 42_000
    assert state["pairmode_version"] == "1.0"
    assert state["current_story"] == "INFRA-148"


def test_set_context_tokens_rejects_zero(tmp_path):
    """--tokens 0 exits non-zero and does not touch state.json."""
    project_dir = tmp_path / "sub" / "project"
    project_dir.mkdir(parents=True)

    result = _invoke_set_context_tokens(project_dir, 0)
    assert result.exit_code != 0
    assert "must be > 0" in result.output
    assert not (project_dir / ".companion" / "state.json").exists()


def test_set_context_tokens_rejects_negative(tmp_path):
    """--tokens -1 exits non-zero and does not touch state.json."""
    project_dir = tmp_path / "sub" / "project"
    project_dir.mkdir(parents=True)

    result = _invoke_set_context_tokens(project_dir, -1)
    assert result.exit_code != 0
    assert "must be > 0" in result.output
    assert not (project_dir / ".companion" / "state.json").exists()


def test_set_context_tokens_does_not_touch_acknowledged_at(tmp_path):
    """Recording a new token count does not clear context_budget_acknowledged_at."""
    project_dir = tmp_path / "sub" / "project"
    companion = project_dir / ".companion"
    companion.mkdir(parents=True)
    (companion / "state.json").write_text(
        json.dumps({"context_budget_acknowledged_at": 130_000}),
        encoding="utf-8",
    )

    result = _invoke_set_context_tokens(project_dir, 95_000)
    assert result.exit_code == 0, result.output

    state = json.loads((companion / "state.json").read_text(encoding="utf-8"))
    assert state["context_current_tokens"] == 95_000
    assert state["context_budget_acknowledged_at"] == 130_000


def test_set_context_tokens_writes_recorded_at(tmp_path):
    """CER-041: writes context_current_tokens_recorded_at alongside tokens."""
    project_dir = tmp_path / "sub" / "project"
    project_dir.mkdir(parents=True)

    result = _invoke_set_context_tokens(project_dir, 42_000)
    assert result.exit_code == 0, result.output

    state = json.loads(
        (project_dir / ".companion" / "state.json").read_text(encoding="utf-8")
    )
    assert "context_current_tokens_recorded_at" in state
    recorded_at = state["context_current_tokens_recorded_at"]
    parsed = datetime.fromisoformat(recorded_at)
    assert parsed.tzinfo is not None


def test_set_context_tokens_does_not_write_context_story_tokens(tmp_path):
    """INFRA-182: set-context-tokens writes scalar only, not context_story_tokens dict."""
    project_dir = tmp_path / "sub" / "project"
    companion = project_dir / ".companion"
    companion.mkdir(parents=True)
    (companion / "state.json").write_text(
        json.dumps({"current_story": {"id": "INFRA-182", "title": "test"}}),
        encoding="utf-8",
    )

    result = _invoke_set_context_tokens(project_dir, 50_000)
    assert result.exit_code == 0, result.output

    state = json.loads((companion / "state.json").read_text(encoding="utf-8"))
    assert state["context_current_tokens"] == 50_000
    assert "context_story_tokens" not in state


# ---------------------------------------------------------------------------
# decide — flex_factor parameter (INFRA-160)
# ---------------------------------------------------------------------------


def test_flex_factor_widens_ceiling(tmp_path):
    """flex_factor=1.5 widens the ceiling; 170000 tokens should be allowed."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "63",
            "current_story": "INFRA-160",
            "context_current_tokens": 170_000,
        },
    )
    result = context_budget.decide(project_dir, flex_factor=1.5)
    assert result is None


def test_flex_factor_tightens_ceiling(tmp_path):
    """flex_factor=0.5 tightens the ceiling; 70000 tokens should be blocked."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "63",
            "current_story": "INFRA-160",
            "context_current_tokens": 70_000,
        },
    )
    result = context_budget.decide(project_dir, flex_factor=0.5)
    assert result is not None
    assert result["block"] is True


def test_flex_factor_default_unchanged(tmp_path):
    """flex_factor omitted (default 1.0) — same behaviour as before INFRA-160."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "63",
            "current_story": "INFRA-160",
            "context_current_tokens": 125_000,
        },
    )
    result = context_budget.decide(project_dir)
    assert result is not None
    assert result["block"] is True


def test_flex_factor_clamped_at_zero(tmp_path, capsys):
    """flex_factor=0 is clamped to 1.0 with a warning; behaviour is default."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "63",
            "current_story": "INFRA-160",
            "context_current_tokens": 10_000,
        },
    )
    result = context_budget.decide(project_dir, flex_factor=0)
    assert result is None
    captured = capsys.readouterr()
    assert "clamped to 1.0" in captured.err


def test_flex_factor_clamped_at_high(tmp_path, capsys):
    """flex_factor=10.0 is clamped to 5.0 with a warning."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "63",
            "current_story": "INFRA-160",
            "context_current_tokens": 10_000,
        },
    )
    result = context_budget.decide(project_dir, flex_factor=10.0)
    assert result is None
    captured = capsys.readouterr()
    assert "clamped to 5.0" in captured.err


# INFRA-174: fresh bootstrap state (context_current_tokens=1) passes decide()
# ---------------------------------------------------------------------------


def test_decide_passes_with_bootstrap_seeded_tokens(tmp_path):
    """context_current_tokens=1 (as seeded by bootstrap) passes decide() without blocking."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "67",
            "current_story": "INFRA-174",
            "context_current_tokens": 1,
        },
    )
    result = context_budget.decide(project_dir)
    assert result is None, f"Expected None but got: {result}"


# ---------------------------------------------------------------------------
# INFRA-183 security remediation tests
# ---------------------------------------------------------------------------


def test_derive_transcript_path_returns_none_for_traversal_session_id(tmp_path):
    """_derive_transcript_path returns None for session_id containing ../ traversal.

    INFRA-183: containment check via Path.resolve().is_relative_to() must
    reject any session_id that, after path construction and resolution, lands
    outside ~/.claude/.
    """
    # Create a fake home with a .claude dir so the containment check can run
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".claude").mkdir()

    # A session_id with .. that would try to escape ~/.claude/
    traversal_session_id = "../../../etc/passwd"
    result = context_budget._derive_transcript_path(
        tmp_path / "project", traversal_session_id, home=fake_home
    )
    assert result is None, (
        f"Expected None for traversal session_id, got {result!r}"
    )


def test_compute_context_tokens_finds_entry_at_line_450(tmp_path):
    """compute_context_tokens finds assistant entry at line 450 (within 500-line bound).

    INFRA-183: 500-line tail regression guard. An assistant entry at line 450
    (from the start, with 50 non-assistant lines following it) is within the
    last 500 lines and must be found.
    """
    f = tmp_path / "t.jsonl"
    # Build a file: 449 human entries, then the target assistant entry, then 50 human entries
    entries = [{"type": "human", "message": {}} for _ in range(449)]
    entries.append(_assistant_entry(input_tokens=45000))
    entries += [{"type": "human", "message": {}} for _ in range(50)]
    # Total: 500 lines — assistant is at position 450 (1-indexed), exactly in the tail
    f.write_text(_make_jsonl(entries), encoding="utf-8")
    result = context_budget.compute_context_tokens(f)
    assert result == 45000, f"Expected 45000, got {result!r}"


def test_compute_context_tokens_does_not_find_entry_beyond_500_line_bound(tmp_path):
    """compute_context_tokens does NOT find assistant entry placed only at line 600.

    INFRA-183: 500-line tail bound guard. An assistant entry at line 1 (from the
    start) with 600 non-assistant lines following it is outside the last 500 lines
    and must NOT be found.
    """
    f = tmp_path / "t.jsonl"
    # The assistant entry is first; then 600 human lines follow
    entries = [_assistant_entry(input_tokens=99000)]
    entries += [{"type": "human", "message": {}} for _ in range(600)]
    # Total: 601 lines; assistant is at line 1, which is > 500 from the end
    f.write_text(_make_jsonl(entries), encoding="utf-8")
    result = context_budget.compute_context_tokens(f)
    # The bounded tail (last 500 lines) contains only human entries → None
    assert result is None, (
        f"Expected None (assistant outside 500-line bound), got {result!r}"
    )


# ---------------------------------------------------------------------------
# INFRA-165: NaN clamp + render_alert_prompt factored ceiling
# ---------------------------------------------------------------------------


def test_flex_factor_nan_clamped(tmp_path):
    """decide() with flex_factor=NaN must clamp to 1.0 and print a warning (INFRA-165)."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "context_budget_reprompt_margin": 10_000,
            "context_current_tokens": 10_000,
        },
    )
    import io
    captured = io.StringIO()
    import sys as _sys
    old_stderr = _sys.stderr
    _sys.stderr = captured
    try:
        result = context_budget.decide(project_dir, flex_factor=float("nan"))
    finally:
        _sys.stderr = old_stderr

    assert result is None, (
        "NaN flex_factor clamped to 1.0; 10k tokens well under 132k ceiling → should pass"
    )
    assert "NaN" in captured.getvalue(), (
        f"Expected NaN warning on stderr; got: {captured.getvalue()!r}"
    )


def test_render_alert_prompt_factored_ceiling(tmp_path):
    """render_alert_prompt uses ceiling = threshold * (1+overrun) * flex_factor (INFRA-165).

    With threshold=120000, overrun=0.10, flex_factor=0.5:
        ceiling = int(120000 * 1.10 * 0.5) = 66000
        remaining = 66000 - 70000 = -4000
    """
    result = context_budget.render_alert_prompt(
        story_id="S",
        tokens=70000,
        threshold=120000,
        overrun_pct=0.10,
        expected_next=1000,
        flex_factor=0.5,
    )
    assert "-4,000" in result or "-4000" in result, (
        f"Expected remaining -4000 in prompt (factored ceiling=66000 − tokens=70000); "
        f"got: {result!r}"
    )
    # Confirm un-factored ceiling (132000) is NOT used as the cutoff
    assert "62,000" not in result and "62000" not in result, (
        "Un-factored remaining (132k-70k=62k) found — ceiling is not being factored"
    )


def test_decide_alert_uses_factored_ceiling(tmp_path):
    """decide() block prompt contains factored [R] when flex_factor < 1.0 (INFRA-165).

    threshold=120000, overrun=0.10, flex_factor=0.5 → ceiling=66000.
    current_tokens=70000 > ceiling → blocked; [R] = 66000-70000 = -4000.
    """
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 1_000,
            "context_budget_reprompt_margin": 10_000,
            "context_current_tokens": 70_000,
        },
    )
    result = context_budget.decide(project_dir, flex_factor=0.5)
    assert result is not None, (
        "70k tokens > factored ceiling (66k); decide should block"
    )
    assert result["block"] is True
    output = result.get("reason", "")
    assert "-4,000" in output or "-4000" in output, (
        f"Factored [R] (-4000) not found in block prompt; got: {output!r}"
    )


# ---------------------------------------------------------------------------
# INFRA-203: CER-040 — decide() pairmode-aware fail-closed
# ---------------------------------------------------------------------------


def test_decide_companion_dir_absent_state_absent_returns_none(tmp_path):
    """No .companion/ directory → non-pairmode project → decide() returns None.

    CER-040: absence of .companion/ means this is not a pairmode project;
    decide() must fail-open (return None).
    """
    # tmp_path has no .companion/ at all
    result = context_budget.decide(tmp_path)
    assert result is None


def test_decide_companion_dir_present_state_absent_returns_check_required(tmp_path):
    """`.companion/` present but state.json absent → CONTEXT CHECK REQUIRED.

    CER-040: pairmode project (has .companion/) with missing state.json should
    surface the gate as needing attention, not silently pass.
    """
    (tmp_path / ".companion").mkdir(parents=True)
    result = context_budget.decide(tmp_path)
    assert result is not None
    assert result["block"] is True
    assert "CONTEXT CHECK REQUIRED" in result["reason"]


# ---------------------------------------------------------------------------
# INFRA-203: CER-041 — recorded_at TTL staleness
# ---------------------------------------------------------------------------


def test_read_context_tokens_stale_at_exactly_60_minutes(tmp_path):
    """recorded_at exactly 60 minutes old is NOT stale (boundary: age > TTL, not >=)."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    recorded_at = (now - timedelta(minutes=60)).isoformat()
    state = {
        "context_current_tokens": 50_000,
        "context_current_tokens_recorded_at": recorded_at,
    }
    # age_minutes == ttl_minutes (60 == 60) → NOT stale (>) → value returned
    assert context_budget.read_context_tokens_from_state(state, _now=now) == 50_000


def test_read_context_tokens_stale_at_61_minutes(tmp_path):
    """recorded_at 61 minutes old is stale → returns None."""
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    recorded_at = (now - timedelta(minutes=61)).isoformat()
    state = {
        "context_current_tokens": 50_000,
        "context_current_tokens_recorded_at": recorded_at,
    }
    assert context_budget.read_context_tokens_from_state(state, _now=now) is None


def test_read_context_tokens_backward_compat_no_recorded_at():
    """recorded_at absent → TTL not enforced; value returned (backward-compat).

    CER-041: existing state.json files without context_current_tokens_recorded_at
    must continue to work as before.
    """
    state = {"context_current_tokens": 77_777}
    assert context_budget.read_context_tokens_from_state(state) == 77_777


# ---------------------------------------------------------------------------
# INFRA-203: CER-051 — session_id traversal guard in _derive_transcript_path
# ---------------------------------------------------------------------------


def test_derive_transcript_path_rejects_session_id_with_slash(tmp_path):
    """_derive_transcript_path returns None for session_id containing '/'.

    CER-051: slash in session_id could be used to escape the transcript directory.
    """
    result = context_budget._derive_transcript_path(
        tmp_path / "proj", "abc/def", home=tmp_path
    )
    assert result is None


def test_derive_transcript_path_rejects_session_id_with_dotdot(tmp_path):
    """_derive_transcript_path returns None for session_id containing '..'.

    CER-051: '..' in session_id could be used for path traversal.
    """
    result = context_budget._derive_transcript_path(
        tmp_path / "proj", "abc..def", home=tmp_path
    )
    assert result is None


def test_derive_transcript_path_rejects_dotdot_slash(tmp_path):
    """_derive_transcript_path returns None for session_id with '../' traversal.

    CER-051: combined '..' and '/' must both be rejected.
    """
    result = context_budget._derive_transcript_path(
        tmp_path / "proj", "../../../etc/passwd", home=tmp_path
    )
    assert result is None
