"""Tests for effort_db.check_guardrail() — INFRA-034 real-time guardrail.

The guardrail is a non-blocking, informational mid-loop check.  It compares a
just-completed builder attempt's tokens against the rail's recent median PASS
cost and returns a structured result.  These tests exercise the firing
threshold, the configurable multiplier, the insufficient-sample early exit,
the PASS-only filter, and the lookback-days filter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from skills.pairmode.scripts import effort_db


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / ".companion" / "effort.db"


def _now_iso(offset_days: int = 0) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(days=offset_days)
    ).isoformat()


def _seed(
    db_path: Path,
    *,
    rail: str,
    tokens_total: int,
    agent_role: str = "builder",
    outcome: str | None = "PASS",
    offset_days: int = 0,
    story_id: str | None = None,
    attempt_number: int = 1,
) -> None:
    """Insert one attempt row at *offset_days* before now."""

    effort_db.insert_attempt(
        db_path,
        story_id=story_id or f"{rail}-001",
        agent_role=agent_role,
        attempt_number=attempt_number,
        ts=_now_iso(offset_days=offset_days),
        rail=rail,
        outcome=outcome,
        tokens_total=tokens_total,
        phase="22",
        model="claude-sonnet-4-6",
    )


# ---------------------------------------------------------------------------
# Threshold and message
# ---------------------------------------------------------------------------


class TestThreshold:
    def test_latest_above_threshold_fires(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        # Three PASS-builder rows around 10k tokens → median ~ 10k.
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens)

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=40_000,  # 4x median > 3x threshold
        )

        assert result["fired"] is True
        assert result["rail"] == "INFRA"
        assert result["sample_size"] == 3
        assert result["median"] == 10_000
        assert result["multiplier"] == 3.0
        assert result["threshold"] == 30_000
        assert result["latest"] == 40_000
        assert result["message"] is not None
        # Message should reference the rail, median, threshold, and story.
        assert "INFRA" in result["message"]
        assert "INFRA-099" in result["message"]
        assert "10,000" in result["message"]
        assert "30,000" in result["message"]
        assert "40,000" in result["message"]

    def test_latest_below_threshold_does_not_fire(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens)

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=15_000,  # below 30k threshold
        )

        assert result["fired"] is False
        assert result["message"] is None
        # Median and threshold are still populated for observability.
        assert result["median"] == 10_000
        assert result["threshold"] == 30_000
        assert result["sample_size"] == 3

    def test_latest_at_threshold_does_not_fire(self, db_path: Path) -> None:
        # Exactly at threshold (not strictly greater) — should not fire.
        effort_db.init_db(db_path)
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens)

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=30_000,
        )

        assert result["fired"] is False
        assert result["message"] is None


# ---------------------------------------------------------------------------
# Insufficient sample
# ---------------------------------------------------------------------------


class TestInsufficientSample:
    def test_zero_rows_returns_no_fire(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=999_999,
        )
        assert result["fired"] is False
        assert result["message"] is None
        assert result["median"] is None
        assert result["sample_size"] == 0

    def test_two_rows_below_minimum_returns_no_fire(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        for tokens in (5_000, 5_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens)

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=999_999,
        )
        assert result["fired"] is False
        assert result["message"] is None
        assert result["sample_size"] == 2
        # Median stays None when sample is insufficient.
        assert result["median"] is None

    def test_missing_db_returns_no_fire(self, tmp_path: Path) -> None:
        ghost = tmp_path / ".companion" / "effort.db"
        result = effort_db.check_guardrail(
            ghost,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=999_999,
        )
        assert result["fired"] is False
        assert result["message"] is None
        assert result["sample_size"] == 0


# ---------------------------------------------------------------------------
# Configurable multiplier
# ---------------------------------------------------------------------------


class TestMultiplier:
    def test_lower_multiplier_fires_earlier(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens)

        # latest=22k vs median 10k → 2.2x.  Default 3x does NOT fire.
        default_result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=22_000,
        )
        assert default_result["fired"] is False
        assert default_result["threshold"] == 30_000

        # With multiplier=2.0, threshold becomes 20k → 22k DOES fire.
        tight_result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=22_000,
            multiplier=2.0,
        )
        assert tight_result["fired"] is True
        assert tight_result["multiplier"] == 2.0
        assert tight_result["threshold"] == 20_000


# ---------------------------------------------------------------------------
# PASS-only filter
# ---------------------------------------------------------------------------


class TestPassOnlyFilter:
    def test_fail_and_null_outcome_excluded_from_median(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        # Three PASS rows around 10k.
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens, outcome="PASS")
        # Inflate the data with FAIL and NULL-outcome rows that would skew the
        # median upward if they were counted.
        _seed(db_path, rail="INFRA", tokens_total=500_000, outcome="FAIL")
        _seed(db_path, rail="INFRA", tokens_total=500_000, outcome=None)

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=40_000,
        )

        assert result["sample_size"] == 3
        assert result["median"] == 10_000
        assert result["threshold"] == 30_000
        assert result["fired"] is True

    def test_reviewer_rows_excluded(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        # Builder rows (low cost) — these define the baseline.
        for tokens in (9_000, 10_000, 11_000):
            _seed(
                db_path,
                rail="INFRA",
                tokens_total=tokens,
                agent_role="builder",
                outcome="PASS",
            )
        # Reviewer rows (would inflate median if counted).
        for _ in range(5):
            _seed(
                db_path,
                rail="INFRA",
                tokens_total=999_999,
                agent_role="reviewer",
                outcome="PASS",
            )

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=40_000,
        )

        assert result["sample_size"] == 3
        assert result["median"] == 10_000
        assert result["fired"] is True

    def test_other_rail_rows_excluded(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens)
        # AUDIT rail rows must not contribute to the INFRA median.
        for _ in range(5):
            _seed(db_path, rail="AUDIT", tokens_total=999_999)

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=40_000,
        )

        assert result["sample_size"] == 3
        assert result["median"] == 10_000


# ---------------------------------------------------------------------------
# Lookback window
# ---------------------------------------------------------------------------


class TestLookbackDays:
    def test_old_rows_excluded(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        # Three rows older than the default 30-day window.
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens, offset_days=60)

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=999_999,
        )
        # Sample is empty after lookback filter → no fire.
        assert result["sample_size"] == 0
        assert result["fired"] is False
        assert result["median"] is None

    def test_recent_rows_within_lookback_counted(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        # Three recent rows (within the 30-day default window).
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens, offset_days=5)

        result = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=40_000,
        )
        assert result["sample_size"] == 3
        assert result["fired"] is True

    def test_custom_lookback_window(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        # Mix of old (40-day) and recent (5-day) rows.
        for tokens in (9_000, 10_000, 11_000):
            _seed(db_path, rail="INFRA", tokens_total=tokens, offset_days=40)
        _seed(db_path, rail="INFRA", tokens_total=50_000, offset_days=5)

        # 7-day window — only the single recent row counts → insufficient sample.
        narrow = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=99_000,
            lookback_days=7,
        )
        assert narrow["sample_size"] == 1
        assert narrow["fired"] is False

        # 90-day window pulls in the older rows too → sample of 4.
        wide = effort_db.check_guardrail(
            db_path,
            story_id="INFRA-099",
            rail="INFRA",
            latest_tokens=99_000,
            lookback_days=90,
        )
        assert wide["sample_size"] == 4
