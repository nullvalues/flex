"""Tests for the ``validate-rebalance`` subcommand in pairmode_effort.py.

Covers:
- Each recommendation category (insufficient data, confirmed, consider upgrading,
  consider further downgrade, monitor)
- Decision-quality section when model_selection_reason column is present
- Decision-quality section gracefully omitted when column is absent
- --json output structure
- Threshold overrides via CLI flags
- Empty / missing DB
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts import effort_db
from skills.pairmode.scripts.pairmode_effort import (
    _load_thresholds,
    _recommend_cell,
    cli,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed(db: Path, **overrides) -> None:
    """Insert a single attempt row with sensible defaults."""
    base = {
        "story_id": "TEST-001",
        "phase": "24",
        "rail": "TEST",
        "agent_role": "reviewer",
        "model": "claude-sonnet-4-6",
        "attempt_number": 1,
        "tokens_total": 1000,
        "tokens_in": 800,
        "tokens_out": 200,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "tool_uses": 1,
        "duration_ms": 500,
        "outcome": "PASS",
        "ts": "2026-05-01T00:00:00+00:00",
    }
    base.update(overrides)
    effort_db.insert_attempt(db, **base)


def _add_story_class_column(db: Path) -> None:
    """Add story_class and model_selection_reason columns (simulates INFRA-050)."""
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.cursor()
        # Check and add story_class
        cur.execute("PRAGMA table_info(attempts)")
        cols = [row[1] for row in cur.fetchall()]
        if "story_class" not in cols:
            cur.execute("ALTER TABLE attempts ADD COLUMN story_class TEXT")
        if "model_selection_reason" not in cols:
            cur.execute(
                "ALTER TABLE attempts ADD COLUMN model_selection_reason TEXT"
            )
        conn.commit()
    finally:
        conn.close()


def _set_column(db: Path, row_id: int, column: str, value: str | None) -> None:
    """Update a single column on a specific row by rowid."""
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            f"UPDATE attempts SET {column} = ? WHERE id = ?",
            (value, row_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    (companion / "state.json").write_text(
        json.dumps({"effort_tracking": True}), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def empty_db(project_dir: Path) -> Path:
    db = project_dir / ".companion" / "effort.db"
    effort_db.init_db(db)
    return db


# ---------------------------------------------------------------------------
# Unit tests for _recommend_cell
# ---------------------------------------------------------------------------


class TestRecommendCell:
    """Unit tests for the recommendation function."""

    def _thresholds(self) -> dict:
        return _load_thresholds({})

    def test_insufficient_data(self) -> None:
        rec = _recommend_cell(
            sample_size=3,
            pass_rate=1.0,
            median_tokens=1000,
            opus_median_tokens=None,
            thresholds=self._thresholds(),
        )
        assert rec == "insufficient data"

    def test_confirmed_no_opus_baseline(self) -> None:
        rec = _recommend_cell(
            sample_size=10,
            pass_rate=0.96,
            median_tokens=1000,
            opus_median_tokens=None,
            thresholds=self._thresholds(),
        )
        assert rec == "rebalance confirmed for this cell"

    def test_confirmed_with_opus_baseline_within_ratio(self) -> None:
        rec = _recommend_cell(
            sample_size=10,
            pass_rate=0.96,
            median_tokens=1200,
            opus_median_tokens=1000,
            thresholds=self._thresholds(),
        )
        assert rec == "rebalance confirmed for this cell"

    def test_consider_upgrading(self) -> None:
        rec = _recommend_cell(
            sample_size=10,
            pass_rate=0.70,
            median_tokens=1000,
            opus_median_tokens=None,
            thresholds=self._thresholds(),
        )
        assert rec == "consider upgrading this cell to opus"

    def test_monitor_mid_range(self) -> None:
        # pass rate between 80% and 95% — neither confirmed nor upgrade
        rec = _recommend_cell(
            sample_size=10,
            pass_rate=0.87,
            median_tokens=1000,
            opus_median_tokens=None,
            thresholds=self._thresholds(),
        )
        assert rec == "monitor — insufficient evidence"

    def test_custom_threshold_min_sample(self) -> None:
        thresholds = self._thresholds()
        thresholds["min_sample"] = 2
        rec = _recommend_cell(
            sample_size=2,
            pass_rate=0.99,
            median_tokens=500,
            opus_median_tokens=None,
            thresholds=thresholds,
        )
        assert rec == "rebalance confirmed for this cell"

    def test_custom_threshold_pass_rate_upgrade(self) -> None:
        thresholds = self._thresholds()
        thresholds["pass_rate_upgrade"] = 0.90
        rec = _recommend_cell(
            sample_size=10,
            pass_rate=0.85,
            median_tokens=500,
            opus_median_tokens=None,
            thresholds=thresholds,
        )
        assert rec == "consider upgrading this cell to opus"


# ---------------------------------------------------------------------------
# Integration tests via CLI
# ---------------------------------------------------------------------------


class TestValidateRebalanceEmptyAndMissing:
    def test_missing_db_shows_no_data(self, project_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["validate-rebalance", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "no effort data" in result.output.lower()

    def test_empty_db_shows_no_data(self, project_dir: Path, empty_db: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["validate-rebalance", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "no effort data" in result.output.lower()


class TestValidateRebalanceBasicOutput:
    """Check that the subcommand runs and emits expected structure."""

    @pytest.fixture
    def db_with_data(self, project_dir: Path) -> Path:
        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        # 6 rows of sonnet reviewer PASS — enough for "confirmed"
        for i in range(6):
            _seed(
                db,
                story_id=f"INFRA-{100 + i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000 + i * 100,
                outcome="PASS",
            )
        return db

    def test_text_output_has_section_header(
        self, project_dir: Path, db_with_data: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["validate-rebalance", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "Section 1" in result.output
        assert "recommendation" in result.output

    def test_json_output_structure(
        self, project_dir: Path, db_with_data: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["section"] == "validate-rebalance"
        assert "thresholds" in data
        assert "cell_analysis" in data
        assert "decision_quality" in data
        assert isinstance(data["cell_analysis"], list)
        assert len(data["cell_analysis"]) > 0

    def test_cell_row_fields(
        self, project_dir: Path, db_with_data: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        cell = data["cell_analysis"][0]
        for field in (
            "agent_role",
            "model",
            "sample_size",
            "pass_count",
            "pass_rate_pct",
            "median_tokens",
            "recommendation",
        ):
            assert field in cell, f"missing field: {field}"


class TestValidateRebalanceRecommendations:
    """Integration tests that drive each recommendation category."""

    def _make_db(self, project_dir: Path) -> Path:
        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        return db

    def test_insufficient_data_recommendation(self, project_dir: Path) -> None:
        db = self._make_db(project_dir)
        # Only 3 rows — below the default min_sample of 5.
        for i in range(3):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="PASS",
            )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        cell = data["cell_analysis"][0]
        assert cell["recommendation"] == "insufficient data"

    def test_confirmed_recommendation(self, project_dir: Path) -> None:
        db = self._make_db(project_dir)
        # 7 rows all PASS → 100% pass rate → confirmed.
        for i in range(7):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="PASS",
            )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        cell = data["cell_analysis"][0]
        assert cell["recommendation"] == "rebalance confirmed for this cell"

    def test_consider_upgrading_recommendation(self, project_dir: Path) -> None:
        db = self._make_db(project_dir)
        # 10 rows: 7 FAIL + 3 PASS = 30% pass rate → < 80% → upgrade.
        for i in range(7):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="FAIL",
            )
        for i in range(7, 10):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="PASS",
            )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        cell = data["cell_analysis"][0]
        assert cell["recommendation"] == "consider upgrading this cell to opus"

    def test_consider_further_downgrade_recommendation(
        self, project_dir: Path
    ) -> None:
        db = self._make_db(project_dir)
        # Sonnet reviewer: 8 PASS / 8 total = 100% pass, lower tokens (500).
        for i in range(8):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=500,
                outcome="PASS",
            )
        # Opus reviewer: 7 PASS / 8 total = 87.5% pass, higher tokens (2000).
        for i in range(8, 16):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-opus-4-7",
                tokens_total=2000,
                outcome="PASS" if i < 15 else "FAIL",
            )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        # Find the sonnet cell.
        sonnet_cells = [
            c
            for c in data["cell_analysis"]
            if "sonnet" in (c["model"] or "").lower()
        ]
        assert sonnet_cells, "no sonnet cell found"
        assert sonnet_cells[0]["recommendation"] == "consider further downgrade"

    def test_monitor_recommendation(self, project_dir: Path) -> None:
        db = self._make_db(project_dir)
        # 10 rows: 85% pass rate — between 80% and 95%.
        for i in range(8):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="PASS",
            )
        for i in range(8, 10):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="FAIL",
            )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        cell = data["cell_analysis"][0]
        assert cell["recommendation"] == "monitor — insufficient evidence"


class TestValidateRebalanceThresholdFlags:
    """CLI threshold override flags are respected."""

    @pytest.fixture
    def db_3rows(self, project_dir: Path) -> Path:
        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        for i in range(3):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="PASS",
            )
        return db

    def test_min_sample_override_unlocks_recommendation(
        self, project_dir: Path, db_3rows: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--min-sample",
                "2",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        assert data["thresholds"]["min_sample"] == 2.0
        # 3 rows, min sample = 2, 100% pass → confirmed
        cell = data["cell_analysis"][0]
        assert cell["recommendation"] == "rebalance confirmed for this cell"

    def test_pass_rate_upgrade_threshold_override(
        self, project_dir: Path, db_3rows: Path
    ) -> None:
        # With pass_rate_upgrade = 0.0, a 100% pass rate is never < threshold.
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--min-sample",
                "2",
                "--pass-rate-upgrade",
                "0.0",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        assert data["thresholds"]["pass_rate_upgrade"] == 0.0


class TestValidateRebalanceDecisionQuality:
    """Section 2: decision quality with and without model_selection_reason column."""

    def _make_db_with_reason(self, project_dir: Path) -> Path:
        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        _add_story_class_column(db)

        # Seed rows with model_selection_reason.
        for i in range(5):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="builder",
                model="claude-sonnet-4-6",
                tokens_total=1000 + i * 50,
                outcome="PASS",
            )
        for i in range(5, 10):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="builder",
                model="claude-opus-4-7",
                tokens_total=2000 + i * 100,
                outcome="PASS",
            )

        # Set model_selection_reason on all rows.
        conn = sqlite3.connect(str(db))
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM attempts")
            ids = [row[0] for row in cur.fetchall()]
            for row_id in ids[:5]:
                cur.execute(
                    "UPDATE attempts SET model_selection_reason = ? WHERE id = ?",
                    ("auto-baseline", row_id),
                )
            for row_id in ids[5:]:
                cur.execute(
                    "UPDATE attempts SET model_selection_reason = ? WHERE id = ?",
                    ("prompted-upgrade", row_id),
                )
            conn.commit()
        finally:
            conn.close()

        return db

    def test_section2_present_when_column_exists(
        self, project_dir: Path
    ) -> None:
        db = self._make_db_with_reason(project_dir)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        dq = data["decision_quality"]
        assert isinstance(dq, list)
        assert len(dq) > 0
        # Check expected fields.
        for row in dq:
            assert "model_selection_reason" in row
            assert "count" in row
            assert "pct_of_total" in row
            assert "pass_rate_pct" in row
            assert "avg_cost_usd" in row
            assert "efficiency_ratio" in row

    def test_section2_has_auto_baseline_and_prompted_upgrade(
        self, project_dir: Path
    ) -> None:
        db = self._make_db_with_reason(project_dir)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        reasons = {r["model_selection_reason"] for r in data["decision_quality"]}
        assert "auto-baseline" in reasons
        assert "prompted-upgrade" in reasons

    def test_section2_pct_of_total_sums_to_100(
        self, project_dir: Path
    ) -> None:
        db = self._make_db_with_reason(project_dir)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        total_pct = sum(r["pct_of_total"] for r in data["decision_quality"])
        assert abs(total_pct - 100.0) < 0.1

    def test_section2_omitted_when_column_absent(
        self, project_dir: Path
    ) -> None:
        # Use a plain DB without story_class / model_selection_reason columns.
        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        for i in range(5):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                outcome="PASS",
            )
        runner = CliRunner()
        # JSON mode: decision_quality should be empty list.
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        assert data["decision_quality"] == []

    def test_section2_omitted_text_mode(self, project_dir: Path) -> None:
        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        for i in range(5):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                outcome="PASS",
            )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["validate-rebalance", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        # Text output says section 2 is omitted.
        assert "Section 2" not in result.output or "omitted" in result.output.lower()

    def test_section2_text_mode_shows_when_present(
        self, project_dir: Path
    ) -> None:
        self._make_db_with_reason(project_dir)
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["validate-rebalance", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "Section 2" in result.output

    def test_auto_baseline_efficiency_ratio_is_one(
        self, project_dir: Path
    ) -> None:
        """auto-baseline row has efficiency_ratio = 1.0 (or None if no cost)."""
        db = self._make_db_with_reason(project_dir)
        # Provide pricing so costs are non-zero.
        pricing_file = project_dir / "pricing.json"
        pricing_file.write_text(
            json.dumps(
                {
                    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
                    "claude-opus-4-7": {"input": 15.0, "output": 75.0},
                }
            ),
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--dollars",
                str(pricing_file),
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        baseline = next(
            r
            for r in data["decision_quality"]
            if r["model_selection_reason"] == "auto-baseline"
        )
        assert baseline["efficiency_ratio"] == pytest.approx(1.0, abs=0.01)


class TestValidateRebalanceStoryClassGrouping:
    """When story_class column is present, cells are grouped by it."""

    def test_story_class_appears_in_cell_rows(self, project_dir: Path) -> None:
        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        _add_story_class_column(db)

        for i in range(5):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="PASS",
            )
        # Set story_class on all rows.
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("UPDATE attempts SET story_class = 'code'")
            conn.commit()
        finally:
            conn.close()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        cells = data["cell_analysis"]
        assert all(c["story_class"] == "code" for c in cells)

    def test_story_class_null_without_column(self, project_dir: Path) -> None:
        """Without story_class column all cells show story_class=None."""
        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        for i in range(5):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                outcome="PASS",
            )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        cells = data["cell_analysis"]
        assert all(c["story_class"] is None for c in cells)


class TestValidateRebalanceStateThresholds:
    """Thresholds from state.json are applied."""

    def test_state_thresholds_override_defaults(self, project_dir: Path) -> None:
        # Write custom thresholds into state.json.
        companion = project_dir / ".companion"
        state = {
            "effort_tracking": True,
            "effort_validation_thresholds": {
                "min_sample": 2,
                "pass_rate_confirmed": 0.80,
                "pass_rate_upgrade": 0.50,
            },
        }
        (companion / "state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        db = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db)
        # 3 rows, 2 PASS = 66.7% — below default confirmed (0.95) but above custom (0.80).
        for i in range(2):
            _seed(
                db,
                story_id=f"INFRA-{i}",
                agent_role="reviewer",
                model="claude-sonnet-4-6",
                tokens_total=1000,
                outcome="PASS",
            )
        _seed(
            db,
            story_id="INFRA-2",
            agent_role="reviewer",
            model="claude-sonnet-4-6",
            tokens_total=1000,
            outcome="FAIL",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "validate-rebalance",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # With min_sample=2 and pass_rate_confirmed=0.80, 3 rows at 66.7%
        # should be "monitor" (above upgrade threshold of 0.50, below confirmed 0.80).
        cell = data["cell_analysis"][0]
        assert cell["recommendation"] == "monitor — insufficient evidence"
        assert data["thresholds"]["min_sample"] == 2.0
        assert data["thresholds"]["pass_rate_confirmed"] == 0.80
