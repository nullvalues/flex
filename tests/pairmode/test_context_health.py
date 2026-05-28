"""Tests for skills/pairmode/scripts/context_health.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from skills.pairmode.scripts import effort_db
from skills.pairmode.scripts import context_health


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Standard .companion/effort.db location inside tmp_path."""
    return tmp_path / ".companion" / "effort.db"


def _insert(db_path: Path, **overrides) -> int:
    """Insert a minimal attempts row, merging overrides into defaults."""
    base = {
        "story_id": "TEST-001",
        "agent_role": "reviewer",
        "attempt_number": 1,
        "ts": "2026-05-01T00:00:00+00:00",
        "outcome": "FAIL",
        "phase": "1",
        "tokens_out": 100,
        "tokens_total": None,
    }
    base.update(overrides)
    effort_db.init_db(db_path)
    return effort_db.insert_attempt(db_path, **base)


# ---------------------------------------------------------------------------
# phase_retry_burden
# ---------------------------------------------------------------------------


class TestPhaseRetryBurden:
    def test_returns_zero_when_db_absent(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such.db"
        assert context_health.phase_retry_burden(missing, "1") == 0

    def test_returns_zero_when_no_matching_rows(self, db_path: Path) -> None:
        # PASS outcome, not FAIL — should contribute nothing
        _insert(db_path, outcome="PASS", phase="1", tokens_out=500)
        assert context_health.phase_retry_burden(db_path, "1") == 0

    def test_sums_tokens_out(self, db_path: Path) -> None:
        _insert(db_path, phase="1", tokens_out=200)
        _insert(db_path, phase="1", tokens_out=300)
        assert context_health.phase_retry_burden(db_path, "1") == 500

    def test_uses_tokens_total_fallback(self, db_path: Path) -> None:
        # tokens_out is NULL, tokens_total = 1000 → estimate = 150
        _insert(db_path, phase="1", tokens_out=None, tokens_total=1000)
        assert context_health.phase_retry_burden(db_path, "1") == 150

    def test_skips_rows_with_no_token_columns(self, db_path: Path) -> None:
        # Both NULL — row should be excluded by the WHERE clause
        _insert(db_path, phase="1", tokens_out=None, tokens_total=None)
        assert context_health.phase_retry_burden(db_path, "1") == 0

    def test_ignores_builder_rows(self, db_path: Path) -> None:
        # builder role, outcome FAIL — should not count
        _insert(db_path, agent_role="builder", phase="1", tokens_out=400)
        assert context_health.phase_retry_burden(db_path, "1") == 0

    def test_isolates_by_phase(self, db_path: Path) -> None:
        _insert(db_path, phase="1", tokens_out=100)
        _insert(db_path, phase="2", tokens_out=999)
        assert context_health.phase_retry_burden(db_path, "1") == 100
        assert context_health.phase_retry_burden(db_path, "2") == 999


# ---------------------------------------------------------------------------
# rolling_phase_median
# ---------------------------------------------------------------------------


class TestRollingPhaseMedian:
    def test_returns_none_when_db_absent(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such.db"
        median, n = context_health.rolling_phase_median(missing, "5")
        assert median is None
        assert n == 0

    def test_returns_none_when_fewer_than_3_prior_phases(self, db_path: Path) -> None:
        # Only 2 prior phases exist
        _insert(db_path, phase="1", tokens_out=100)
        _insert(db_path, phase="2", tokens_out=200)
        median, n = context_health.rolling_phase_median(db_path, "3")
        assert median is None
        assert n == 0

    def test_computes_median_with_3_prior_phases(self, db_path: Path) -> None:
        _insert(db_path, phase="1", tokens_out=100)
        _insert(db_path, phase="2", tokens_out=200)
        _insert(db_path, phase="3", tokens_out=300)
        median, n = context_health.rolling_phase_median(db_path, "4")
        assert median == 200.0
        assert n == 3

    def test_zero_burden_phases_included(self, db_path: Path) -> None:
        # Phase "1" has PASS rows only → burden = 0
        _insert(db_path, phase="1", outcome="PASS", tokens_out=500)
        _insert(db_path, phase="2", tokens_out=200)
        _insert(db_path, phase="3", tokens_out=400)
        median, n = context_health.rolling_phase_median(db_path, "4")
        # burdens = [0, 200, 400] → median = 200
        assert median == 200.0
        assert n == 3

    def test_respects_lookback_phases_limit(self, db_path: Path) -> None:
        # Insert 5 phases; lookback=3 should use only the last 3
        for i in range(1, 6):
            _insert(db_path, phase=str(i), tokens_out=i * 100)
        # phases 1–4 are prior to phase "5"
        # last 3 of those: phases 2, 3, 4 → burdens 200, 300, 400
        median, n = context_health.rolling_phase_median(db_path, "5", lookback_phases=3)
        assert median == 300.0
        assert n == 3

    def test_excludes_current_phase(self, db_path: Path) -> None:
        _insert(db_path, phase="1", tokens_out=100)
        _insert(db_path, phase="2", tokens_out=200)
        _insert(db_path, phase="3", tokens_out=300)
        # Current phase has very high burden — should not affect median
        _insert(db_path, phase="4", tokens_out=999_999)
        median, n = context_health.rolling_phase_median(db_path, "4")
        assert median == 200.0
        assert n == 3


# ---------------------------------------------------------------------------
# check_context_health
# ---------------------------------------------------------------------------


class TestCheckContextHealth:
    def test_returns_insufficient_data_when_db_absent(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such.db"
        result = context_health.check_context_health(missing, "5")
        assert result["recommendation"] == "insufficient_data"
        assert result["phase"] == "5"
        assert result["retry_burden"] == 0
        assert result["phase_median"] is None
        assert result["ratio"] is None

    def test_all_keys_present(self, db_path: Path) -> None:
        result = context_health.check_context_health(db_path, "1")
        expected_keys = {
            "phase", "retry_burden", "phase_median", "ratio",
            "recommendation", "sample_size", "message",
        }
        assert set(result.keys()) == expected_keys

    def test_normal_recommendation(self, db_path: Path) -> None:
        # Prior phases each have 100 tokens → median = 100
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        # Current phase has 150 tokens → ratio = 1.5 < 2.0 → normal
        _insert(db_path, phase="4", tokens_out=150)
        result = context_health.check_context_health(db_path, "4")
        assert result["recommendation"] == "normal"
        assert result["ratio"] is not None
        assert result["ratio"] < 2.0

    def test_elevated_recommendation(self, db_path: Path) -> None:
        # Prior phases median = 100
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        # Current phase = 250 → ratio = 2.5 → elevated
        _insert(db_path, phase="4", tokens_out=250)
        result = context_health.check_context_health(db_path, "4")
        assert result["recommendation"] == "elevated"

    def test_high_recommendation(self, db_path: Path) -> None:
        # Prior phases median = 100
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        # Current phase = 500 → ratio = 5.0 → high
        _insert(db_path, phase="4", tokens_out=500)
        result = context_health.check_context_health(db_path, "4")
        assert result["recommendation"] == "high"

    def test_message_insufficient_data(self, db_path: Path) -> None:
        result = context_health.check_context_health(db_path, "1")
        assert "no data yet" in result["message"]
        assert "<3 prior phases recorded" in result["message"]

    def test_message_normal_contains_ratio(self, db_path: Path) -> None:
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        _insert(db_path, phase="4", tokens_out=150)
        result = context_health.check_context_health(db_path, "4")
        assert "normal" in result["message"]
        assert "×" in result["message"] or "x" in result["message"].lower()

    def test_message_elevated_contains_clear_suggestion(self, db_path: Path) -> None:
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        _insert(db_path, phase="4", tokens_out=250)
        result = context_health.check_context_health(db_path, "4")
        assert "ELEVATED" in result["message"]
        assert "/clear" in result["message"]

    def test_message_high_contains_recommend(self, db_path: Path) -> None:
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        _insert(db_path, phase="4", tokens_out=500)
        result = context_health.check_context_health(db_path, "4")
        assert "HIGH" in result["message"]
        assert "/clear" in result["message"]

    def test_check_context_health_zero_median(self, db_path: Path) -> None:
        """Zero-median case: all prior phases had only PASS reviewer rows.

        phase_median == 0.0, sample_size >= 3.  The ratio cannot be computed
        (ZeroDivisionError), so ratio must be None and recommendation must be
        "insufficient_data".  No exception must propagate.
        """
        # 3 prior phases, each with only PASS reviewer rows → burden = 0 each
        for i in range(1, 4):
            _insert(db_path, phase=str(i), outcome="PASS", tokens_out=500)
        # Current phase has some FAIL burden
        _insert(db_path, phase="4", tokens_out=300)
        result = context_health.check_context_health(db_path, "4")
        assert result["phase_median"] == 0.0
        assert result["ratio"] is None
        assert result["recommendation"] == "insufficient_data"
        # Must not raise — we already got here, so that condition is met


# ---------------------------------------------------------------------------
# CLI: context_health check subcommand (INFRA-118)
# ---------------------------------------------------------------------------


def _run_context_health_cli(argv: list[str], mock_result: dict) -> tuple[int, str]:
    """Invoke context_health._cli_main() in-process with a mocked check_context_health.

    Returns (exit_code, stdout_text).
    """
    import io

    captured_stdout = io.StringIO()

    with patch(
        "skills.pairmode.scripts.context_health.check_context_health",
        return_value=mock_result,
    ), patch("sys.stdout", captured_stdout):
        exit_code = context_health._cli_main(argv)

    return exit_code, captured_stdout.getvalue()


class TestContextHealthCLI:
    def test_context_health_cli_healthy(self, tmp_path: Path) -> None:
        """Exit 0 and message printed when recommendation is 'normal'."""
        exit_code, stdout = _run_context_health_cli(
            ["check", "--phase", "45", "--project-dir", str(tmp_path)],
            mock_result={"recommendation": "normal", "message": "context health: normal"},
        )
        assert exit_code == 0
        assert "context health: normal" in stdout

    def test_context_health_cli_unhealthy(self, tmp_path: Path) -> None:
        """Exit 1 and message printed when recommendation is 'elevated'."""
        exit_code, stdout = _run_context_health_cli(
            ["check", "--phase", "45", "--project-dir", str(tmp_path)],
            mock_result={
                "recommendation": "elevated",
                "message": "context health: elevated retry burden",
            },
        )
        assert exit_code == 1
        assert "context health: elevated retry burden" in stdout
