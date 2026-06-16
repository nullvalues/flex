"""Tests for skills/pairmode/scripts/context_budget.py.

INFRA-148: token-source contract changed from transcript JSONL tail-read to
``state.json["context_current_tokens"]``. All previous transcript fixtures are
replaced with state.json seeding.

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
    """Tier 1: per-phase ≥5 rows — per-phase median returned, not global.

    Phase "7" has 5 rows [10k..50k] → median 30k.
    Global also has those same rows but more in phase "99" — tie broken by
    phase-specific median still equaling 30k.
    """
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    # Phase 7: 5 rows → median 30k
    _insert_attempts(db_path, phase="7", tokens_list=[10000, 20000, 30000, 40000, 50000])
    # Other phase: adds noise to global
    _insert_attempts(db_path, phase="99", tokens_list=[100000, 200000])

    result = context_budget.estimate_next_step_tokens(db_path, "7", seeded_default=99999)
    # Per-phase median of [10k, 20k, 30k, 40k, 50k] = 30k
    assert result == 30000


def test_estimate_global_fallback_when_per_phase_insufficient(tmp_path):
    """Tier 2: per-phase < 5 rows, global ≥ 5 — global median returned.

    Phase "3" has only 2 rows.  Other phases supply the remaining rows so
    the global total is ≥ 5.
    """
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    # Phase 3: only 2 rows (not enough for tier 1)
    _insert_attempts(db_path, phase="3", tokens_list=[10000, 20000])
    # Other phases supply 3 more rows → global = 5
    _insert_attempts(db_path, phase="9", tokens_list=[30000, 40000, 50000])

    result = context_budget.estimate_next_step_tokens(db_path, "3", seeded_default=99999)
    # Global values: [10k, 20k, 30k, 40k, 50k] → median 30k
    assert result == 30000


def test_estimate_seeded_fallback_when_global_insufficient(tmp_path):
    """Tier 3: global < 5 rows — seeded_default returned."""
    db_path = tmp_path / "effort.db"
    _create_effort_db(db_path)
    # Only 3 rows total across all phases
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
    assert "set-context-tokens" in result["reason"]
    assert "session transcript or from state.json" in result["reason"]


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
# decide — CER-040 malformed state.json edge cases
# ---------------------------------------------------------------------------


def test_decide_no_state_file_passthrough(tmp_path):
    """`.companion/` directory exists but state.json is absent → None (fail-open)."""
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    # No state.json created — directory exists but file does not.
    result = context_budget.decide(tmp_path)
    assert result is None


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
    # Parseable as ISO 8601 (datetime.fromisoformat round-trips the value).
    recorded_at = state["context_current_tokens_recorded_at"]
    parsed = datetime.fromisoformat(recorded_at)
    assert parsed.tzinfo is not None


# ---------------------------------------------------------------------------
# decide — flex_factor parameter (INFRA-160)
# ---------------------------------------------------------------------------


def test_flex_factor_widens_ceiling(tmp_path):
    """flex_factor=1.5 widens the ceiling; 170000 tokens should be allowed.

    threshold=120000, overrun_pct=0.10, flex_factor=1.5
    ceiling = 120000 * 1.10 * 1.50 = 198000
    current=170000 + expected_step=1000 = 171000 < 198000 → allow (None).
    """
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
    """flex_factor=0.5 tightens the ceiling; 70000 tokens should be blocked.

    threshold=120000, overrun_pct=0.10, flex_factor=0.5
    ceiling = 120000 * 1.10 * 0.50 = 66000
    current=70000 + expected_step=1000 = 71000 > 66000 → block.
    """
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
    """flex_factor omitted (default 1.0) — same behaviour as before INFRA-160.

    threshold=120000, overrun_pct=0.10, flex_factor=1.0 (default)
    ceiling = 120000 * 1.10 = 132000
    current=125000 + expected_step=53000 = 178000 > 132000 → block.
    """
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
    """flex_factor=0 is clamped to 1.0 with a warning; behaviour is default.

    After clamping: ceiling = 120000 * 1.10 * 1.0 = 132000
    current=10000 + expected_step=1000 = 11000 < 132000 → allow (None).
    """
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
    # Clamped to 1.0 → normal ceiling → tokens well under → allow
    assert result is None
    captured = capsys.readouterr()
    assert "clamped to 1.0" in captured.err


def test_flex_factor_clamped_at_high(tmp_path, capsys):
    """flex_factor=10.0 is clamped to 5.0 with a warning.

    After clamping: ceiling = 120000 * 1.10 * 5.0 = 660000
    current=10000 + expected_step=1000 = 11000 < 660000 → allow (None).
    """
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
    """context_current_tokens=1 (as seeded by bootstrap) passes decide() without blocking.

    INFRA-174: _record_state seeds context_current_tokens=1 for new state files.
    This test verifies that decide() returns None (no block) when called with
    that minimal seeded value, confirming the first build step can proceed.
    """
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "context_budget_reprompt_margin": 10_000,
            "current_phase": "67",
            "current_story": "INFRA-174",
            # Value seeded by _record_state on a fresh bootstrap.
            # No recorded_at — staleness check skips absent timestamps.
            "context_current_tokens": 1,
        },
    )
    result = context_budget.decide(project_dir)
    # 1 + 53_000 = 53_001, ceiling = 120_000 * 1.10 = 132_000 → well under ceiling.
    assert result is None, f"Expected None but got: {result}"


# ---------------------------------------------------------------------------
# _derive_transcript_path (INFRA-179)
# ---------------------------------------------------------------------------


def test_derive_transcript_path_empty_session_id_returns_none(tmp_path):
    """Empty session_id returns None."""
    assert context_budget._derive_transcript_path(tmp_path, "") is None


def test_derive_transcript_path_none_session_id_returns_none(tmp_path):
    """None session_id returns None."""
    assert context_budget._derive_transcript_path(tmp_path, None) is None  # type: ignore[arg-type]


def test_derive_transcript_path_nonexistent_file_returns_none(tmp_path):
    """Valid session_id but file not on disk returns None."""
    result = context_budget._derive_transcript_path(
        tmp_path, "abc123", home=tmp_path
    )
    assert result is None


def test_derive_transcript_path_existing_file_returns_path(tmp_path):
    """Existing JSONL file: returns the correct Path."""
    sid = "test-session-id"
    cwd = Path("/a/b/c")
    cwd_key = str(cwd.resolve()).replace("/", "-")
    jsonl_dir = tmp_path / ".claude" / "projects" / cwd_key
    jsonl_dir.mkdir(parents=True)
    jsonl_file = jsonl_dir / f"{sid}.jsonl"
    jsonl_file.write_text("{}", encoding="utf-8")

    result = context_budget._derive_transcript_path(cwd, sid, home=tmp_path)
    assert result == jsonl_file


def test_derive_transcript_path_formula_key_transform(tmp_path):
    """Path key is cwd.resolve().replace('/', '-')."""
    sid = "abc"
    cwd = Path("/a/b/c")
    expected_key = "-a-b-c"
    jsonl_dir = tmp_path / ".claude" / "projects" / expected_key
    jsonl_dir.mkdir(parents=True)
    (jsonl_dir / f"{sid}.jsonl").write_text("{}", encoding="utf-8")

    result = context_budget._derive_transcript_path(cwd, sid, home=tmp_path)
    assert result is not None
    assert result.name == f"{sid}.jsonl"
    assert expected_key in str(result)


def test_derive_transcript_path_relative_cwd_resolved(tmp_path):
    """cwd='.' is resolved to an absolute path; no literal dot in key."""
    sid = "reltest"
    cwd = Path(".")
    cwd_key = str(cwd.resolve()).replace("/", "-")
    jsonl_dir = tmp_path / ".claude" / "projects" / cwd_key
    jsonl_dir.mkdir(parents=True)
    (jsonl_dir / f"{sid}.jsonl").write_text("{}", encoding="utf-8")

    result = context_budget._derive_transcript_path(cwd, sid, home=tmp_path)
    assert result is not None
    # The key must not contain a literal '.' as the first character
    # (it should be the absolute path transformed).
    assert "-." not in str(result.parent.name[:2])


# ---------------------------------------------------------------------------
# compute_context_tokens (INFRA-179)
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, entries: list) -> None:
    """Write a list of dicts as JSONL (one JSON object per line)."""
    lines = [json.dumps(e) for e in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_compute_context_tokens_valid_entry(tmp_path):
    """Valid JSONL with one assistant entry returns sum of usage fields."""
    jsonl = tmp_path / "session.jsonl"
    _write_jsonl(jsonl, [
        {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": 1000,
                    "cache_read_input_tokens": 500,
                    "cache_creation_input_tokens": 200,
                }
            },
        }
    ])
    result = context_budget.compute_context_tokens(jsonl)
    assert result == 1700


def test_compute_context_tokens_no_assistant_entry_returns_none(tmp_path):
    """Only user/tool_result entries in tail → None."""
    jsonl = tmp_path / "session.jsonl"
    _write_jsonl(jsonl, [
        {"type": "user", "message": {}},
        {"type": "tool_result", "content": "ok"},
    ])
    result = context_budget.compute_context_tokens(jsonl)
    assert result is None


def test_compute_context_tokens_assistant_missing_usage_returns_none(tmp_path):
    """Assistant entry with no 'usage' key → None."""
    jsonl = tmp_path / "session.jsonl"
    _write_jsonl(jsonl, [
        {"type": "assistant", "message": {"content": "hello"}},
    ])
    result = context_budget.compute_context_tokens(jsonl)
    assert result is None


def test_compute_context_tokens_missing_file_returns_none(tmp_path):
    """Path does not exist → None (no raise)."""
    result = context_budget.compute_context_tokens(tmp_path / "no-such.jsonl")
    assert result is None


def test_compute_context_tokens_malformed_lines_skipped(tmp_path):
    """Malformed lines before valid entry are skipped; valid entry found."""
    jsonl = tmp_path / "session.jsonl"
    lines = [
        "not json{{",
        "also not json",
        json.dumps({
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": 300,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            },
        }),
    ]
    jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = context_budget.compute_context_tokens(jsonl)
    assert result == 300


def test_compute_context_tokens_entry_beyond_50_lines_found(tmp_path):
    """Assistant entry at line 60 from end is found (tail is 100, not 50)."""
    jsonl = tmp_path / "session.jsonl"
    # Build 99 user lines + 1 assistant at position 40 from start of the 100-tail
    # (i.e., 60 lines from the end of a 99-line file — well within the 100-line tail).
    entries = [{"type": "user", "message": {}} for _ in range(59)]
    entries.append({
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": 9999,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            }
        },
    })
    entries.extend([{"type": "user", "message": {}} for _ in range(39)])
    assert len(entries) == 99
    _write_jsonl(jsonl, entries)
    result = context_budget.compute_context_tokens(jsonl)
    assert result == 9999


def test_compute_context_tokens_oserror_returns_none(tmp_path, monkeypatch):
    """OSError on open → None (no raise)."""
    jsonl = tmp_path / "session.jsonl"
    jsonl.write_text("{}", encoding="utf-8")

    original_read_text = Path.read_text

    def _raise_oserror(self, *args, **kwargs):
        if self == jsonl:
            raise OSError("simulated read failure")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _raise_oserror)
    result = context_budget.compute_context_tokens(jsonl)
    assert result is None


# ---------------------------------------------------------------------------
# read_current_tokens (INFRA-179)
# ---------------------------------------------------------------------------


def test_read_current_tokens_jsonl_succeeds(tmp_path):
    """Creates JSONL fixture; result matches JSONL sum."""
    sid = "readtest"
    cwd = tmp_path / "project"
    cwd.mkdir()
    cwd_key = str(cwd.resolve()).replace("/", "-")
    jsonl_dir = tmp_path / ".claude" / "projects" / cwd_key
    jsonl_dir.mkdir(parents=True)
    jsonl_file = jsonl_dir / f"{sid}.jsonl"
    _write_jsonl(jsonl_file, [
        {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": 2000,
                    "cache_read_input_tokens": 300,
                    "cache_creation_input_tokens": 100,
                }
            },
        }
    ])

    result = context_budget.read_current_tokens(
        project_dir=cwd, session_id=sid, home=tmp_path
    )
    assert result == 2400


def test_read_current_tokens_no_session_id_returns_none(tmp_path):
    """session_id='' → None."""
    result = context_budget.read_current_tokens(
        project_dir=tmp_path, session_id="", home=tmp_path
    )
    assert result is None


def test_read_current_tokens_jsonl_file_missing_returns_none(tmp_path):
    """Valid session_id but no JSONL file on disk → None."""
    result = context_budget.read_current_tokens(
        project_dir=tmp_path, session_id="nonexistent", home=tmp_path
    )
    assert result is None


# ---------------------------------------------------------------------------
# decide — updated message text and session_id kwarg (INFRA-179)
# ---------------------------------------------------------------------------


def test_decide_returns_check_required_message_updated(tmp_path):
    """CONTEXT CHECK REQUIRED message now mentions 'session transcript or from state.json'."""
    project_dir = _setup_project(
        tmp_path,
        state={
            "context_budget_threshold": 120_000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 53_000,
            "current_phase": "72",
            "current_story": "INFRA-179",
        },
    )
    result = context_budget.decide(project_dir)
    assert result is not None
    assert result["block"] is True
    assert "session transcript or from state.json" in result["reason"]
