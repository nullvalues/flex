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
    """INFRA-321: check_context_health's return shape is now two explicitly
    tracked sub-objects (``orchestrator`` / ``story_spend``), with the
    top-level ``recommendation``/``message`` sourced from the orchestrator
    track only. Assertions on the old flat ``{retry_burden, ratio,
    recommendation, message}`` shape are retargeted onto ``story_spend``
    below, each naming INFRA-321.
    """

    def test_returns_insufficient_data_when_db_absent(self, tmp_path: Path) -> None:
        missing = tmp_path / "no_such.db"
        result = context_health.check_context_health(missing, "5", state={})
        assert result["recommendation"] == "insufficient_data"
        assert result["phase"] == "5"
        assert result["story_spend"]["retry_burden"] == 0
        assert result["story_spend"]["phase_median"] is None
        assert result["story_spend"]["ratio"] is None

    def test_all_keys_present(self, db_path: Path) -> None:
        result = context_health.check_context_health(db_path, "1", state={})
        expected_keys = {"phase", "orchestrator", "story_spend", "recommendation", "message"}
        assert set(result.keys()) == expected_keys
        expected_spend_keys = {
            "track", "retry_burden", "phase_median", "ratio",
            "sample_size", "informational", "message",
        }
        assert set(result["story_spend"].keys()) == expected_spend_keys

    def test_top_level_recommendation_is_orchestrator_recommendation_by_identity(
        self, db_path: Path
    ) -> None:
        """INFRA-321 § B3: high retry churn does not affect the top-level
        recommendation — only the (empty, insufficient_data) orchestrator does.
        """
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        _insert(db_path, phase="4", tokens_out=500)  # would be "high" churn
        result = context_health.check_context_health(db_path, "4", state={})
        assert result["story_spend"]["ratio"] == 5.0
        assert result["recommendation"] is result["orchestrator"]["recommendation"]
        assert result["recommendation"] == "insufficient_data"  # empty state

    def test_story_spend_churn_normal(self, db_path: Path) -> None:
        """INFRA-321: retargeted from the old test_normal_recommendation."""
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        _insert(db_path, phase="4", tokens_out=150)
        result = context_health.check_context_health(db_path, "4", state={})
        assert "normal" in result["story_spend"]["message"]
        assert result["story_spend"]["ratio"] < 2.0

    def test_story_spend_churn_elevated(self, db_path: Path) -> None:
        """INFRA-321: retargeted from the old test_elevated_recommendation."""
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        _insert(db_path, phase="4", tokens_out=250)
        result = context_health.check_context_health(db_path, "4", state={})
        assert "ELEVATED" in result["story_spend"]["message"]

    def test_story_spend_churn_high(self, db_path: Path) -> None:
        """INFRA-321: retargeted from the old test_high_recommendation."""
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        _insert(db_path, phase="4", tokens_out=500)
        result = context_health.check_context_health(db_path, "4", state={})
        assert "HIGH" in result["story_spend"]["message"]

    def test_story_spend_message_insufficient_data(self, db_path: Path) -> None:
        """INFRA-321: retargeted from the old test_message_insufficient_data."""
        result = context_health.check_context_health(db_path, "1", state={})
        assert "no data yet" in result["story_spend"]["message"]
        assert "<3 prior phases recorded" in result["story_spend"]["message"]

    def test_story_spend_message_normal_contains_ratio(self, db_path: Path) -> None:
        """INFRA-321: retargeted from the old test_message_normal_contains_ratio."""
        for i in range(1, 4):
            _insert(db_path, phase=str(i), tokens_out=100)
        _insert(db_path, phase="4", tokens_out=150)
        result = context_health.check_context_health(db_path, "4", state={})
        msg = result["story_spend"]["message"]
        assert "normal" in msg
        assert "×" in msg or "x" in msg.lower()

    def test_story_spend_message_contains_no_clear_advice(self, db_path: Path) -> None:
        """INFRA-321 § B4: '/clear' advice must appear nowhere in the
        story-spend message across normal/elevated/high retry-burden fixtures
        — retargeted from the old test_message_elevated/high_* tests, which
        used to assert '/clear' WAS present. That was the mis-attribution.
        """
        fixtures = [150, 250, 500]  # normal, elevated, high
        for tokens in fixtures:
            for i in range(1, 4):
                _insert(db_path, phase=f"p{tokens}-{i}", tokens_out=100)
            _insert(db_path, phase=f"cur{tokens}", tokens_out=tokens)
            result = context_health.check_context_health(db_path, f"cur{tokens}", state={})
            msg = result["story_spend"]["message"]
            assert "/clear" not in msg
            assert "consider /clear" not in msg
            assert "recommend /clear" not in msg

    def test_check_context_health_zero_median(self, db_path: Path) -> None:
        """Zero-median case: all prior phases had only PASS reviewer rows.

        phase_median == 0.0, sample_size >= 3.  The ratio cannot be computed
        (ZeroDivisionError), so ratio must be None and story-spend churn must
        be "insufficient_data". No exception must propagate.
        """
        # 3 prior phases, each with only PASS reviewer rows → burden = 0 each
        for i in range(1, 4):
            _insert(db_path, phase=str(i), outcome="PASS", tokens_out=500)
        # Current phase has some FAIL burden
        _insert(db_path, phase="4", tokens_out=300)
        result = context_health.check_context_health(db_path, "4", state={})
        assert result["story_spend"]["phase_median"] == 0.0
        assert result["story_spend"]["ratio"] is None
        assert "no data yet" in result["story_spend"]["message"]
        # Must not raise — we already got here, so that condition is met


# ---------------------------------------------------------------------------
# orchestrator_headroom (INFRA-321 § B1/B2)
# ---------------------------------------------------------------------------


class TestOrchestratorHeadroom:
    def test_opens_no_database(self) -> None:
        """§ B2: a monkeypatched sqlite3.connect that raises must never be hit."""
        import sqlite3 as _sqlite3
        from unittest.mock import patch as _patch

        state = {"context_current_tokens": 50000}
        with _patch.object(_sqlite3, "connect", side_effect=AssertionError("must not connect")):
            result = context_health.orchestrator_headroom(state)
        assert result["track"] == "orchestrator-window"
        assert result["tokens"] == 50000

    def test_recommendation_bands(self) -> None:
        # ceiling = 130000 * 1.10 = 143000; expected_step_tokens default 5000
        base_state = {
            "context_budget_threshold": 130000,
            "context_budget_overrun_pct": 0.10,
            "expected_step_tokens": 5000,
        }
        # >= 3 steps remaining → normal
        normal = dict(base_state, context_current_tokens=100000)
        assert context_health.orchestrator_headroom(normal)["recommendation"] == "normal"
        # 1 <= steps < 3 → elevated
        elevated = dict(base_state, context_current_tokens=136000)
        assert context_health.orchestrator_headroom(elevated)["recommendation"] == "elevated"
        # < 1 step → high
        high = dict(base_state, context_current_tokens=142000)
        assert context_health.orchestrator_headroom(high)["recommendation"] == "high"

    def test_stale_is_insufficient_data(self) -> None:
        state = {
            "context_current_tokens": 100000,
            "context_current_tokens_recorded_at": "2026-01-01T00:00:00+00:00",
            "context_session_reset_at": "2026-06-01T00:00:00+00:00",
        }
        result = context_health.orchestrator_headroom(state)
        assert result["stale"] is True
        assert result["recommendation"] == "insufficient_data"

    def test_no_tokens_is_insufficient_data(self) -> None:
        result = context_health.orchestrator_headroom({})
        assert result["tokens"] is None
        assert result["recommendation"] == "insufficient_data"

    def test_never_raises_on_malformed_state(self) -> None:
        result = context_health.orchestrator_headroom(None)  # type: ignore[arg-type]
        assert result["recommendation"] == "insufficient_data"


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
