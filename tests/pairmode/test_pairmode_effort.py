"""Tests for skills/pairmode/scripts/pairmode_effort.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts import effort_db
from skills.pairmode.scripts.pairmode_effort import cli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_attempt(db: Path, **overrides) -> None:
    base = {
        "story_id": "INFRA-100",
        "phase": "22",
        "rail": "INFRA",
        "agent_role": "builder",
        "model": "claude-sonnet-4-6",
        "attempt_number": 1,
        "tokens_total": 1000,
        "tokens_in": 800,
        "tokens_out": 200,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "duration_ms": 1000,
        "outcome": "PASS",
        "ts": "2026-05-01T00:00:00+00:00",
    }
    base.update(overrides)
    effort_db.insert_attempt(db, **base)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A project directory with a state.json that points at a seeded DB."""

    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state = {"effort_tracking": True}
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return tmp_path


@pytest.fixture
def seeded_db(project_dir: Path) -> Path:
    """Seed ~10 attempts across two stories, two rails, two models.

    Layout:
    - INFRA-100 / INFRA / sonnet : builder (attempt 1, PASS) +
                                   builder (attempt 2, PASS) +
                                   reviewer (attempt 1, PASS)
                                   -> rework case for INFRA-100
    - INFRA-100 / INFRA / opus   : reviewer (attempt 1, PASS)
    - BUILD-200 / BUILD / sonnet : builder (attempt 1, FAIL) +
                                   builder (attempt 1, PASS) [different ts] +
                                   reviewer (attempt 1, PASS)
    - BUILD-200 / BUILD / opus   : reviewer (attempt 1, FAIL) +
                                   reviewer (attempt 1, PASS)
    """

    db_path = project_dir / ".companion" / "effort.db"
    effort_db.init_db(db_path)

    # INFRA-100 sonnet builder, two attempts (rework).
    _seed_attempt(
        db_path,
        story_id="INFRA-100",
        rail="INFRA",
        model="claude-sonnet-4-6",
        agent_role="builder",
        attempt_number=1,
        tokens_total=1000,
        tokens_in=800,
        tokens_out=200,
        outcome="PASS",
    )
    _seed_attempt(
        db_path,
        story_id="INFRA-100",
        rail="INFRA",
        model="claude-sonnet-4-6",
        agent_role="builder",
        attempt_number=2,
        tokens_total=1500,
        tokens_in=1200,
        tokens_out=300,
        outcome="PASS",
    )
    _seed_attempt(
        db_path,
        story_id="INFRA-100",
        rail="INFRA",
        model="claude-sonnet-4-6",
        agent_role="reviewer",
        attempt_number=1,
        tokens_total=500,
        tokens_in=400,
        tokens_out=100,
        outcome="PASS",
    )
    _seed_attempt(
        db_path,
        story_id="INFRA-100",
        rail="INFRA",
        model="claude-opus-4-7",
        agent_role="reviewer",
        attempt_number=1,
        tokens_total=2000,
        tokens_in=1500,
        tokens_out=500,
        outcome="PASS",
    )

    # BUILD-200 sonnet
    _seed_attempt(
        db_path,
        story_id="BUILD-200",
        rail="BUILD",
        model="claude-sonnet-4-6",
        agent_role="builder",
        attempt_number=1,
        tokens_total=800,
        tokens_in=600,
        tokens_out=200,
        outcome="FAIL",
    )
    _seed_attempt(
        db_path,
        story_id="BUILD-200",
        rail="BUILD",
        model="claude-sonnet-4-6",
        agent_role="builder",
        attempt_number=1,
        tokens_total=900,
        tokens_in=700,
        tokens_out=200,
        outcome="PASS",
    )
    _seed_attempt(
        db_path,
        story_id="BUILD-200",
        rail="BUILD",
        model="claude-sonnet-4-6",
        agent_role="reviewer",
        attempt_number=1,
        tokens_total=600,
        tokens_in=500,
        tokens_out=100,
        outcome="PASS",
    )
    _seed_attempt(
        db_path,
        story_id="BUILD-200",
        rail="BUILD",
        model="claude-opus-4-7",
        agent_role="reviewer",
        attempt_number=1,
        tokens_total=1100,
        tokens_in=900,
        tokens_out=200,
        outcome="FAIL",
    )
    _seed_attempt(
        db_path,
        story_id="BUILD-200",
        rail="BUILD",
        model="claude-opus-4-7",
        agent_role="reviewer",
        attempt_number=1,
        tokens_total=1300,
        tokens_in=1000,
        tokens_out=300,
        outcome="PASS",
    )

    return db_path


@pytest.fixture
def pricing_file(tmp_path: Path) -> Path:
    """A small pricing.json suitable for projection tests."""

    pricing = {
        "claude-sonnet-4-6": {
            "input": 3.00,
            "output": 15.00,
            "cache_read": 0.30,
            "cache_write": 3.75,
        },
        "claude-opus-4-7": {
            "input": 15.00,
            "output": 75.00,
            "cache_read": 1.50,
            "cache_write": 18.75,
        },
    }
    p = tmp_path / "pricing.json"
    p.write_text(json.dumps(pricing), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# rollup
# ---------------------------------------------------------------------------


class TestRollup:
    def test_basic_text_output(self, project_dir: Path, seeded_db: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rollup", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # Both rails appear in output.
        assert "INFRA" in result.output
        assert "BUILD" in result.output
        # Both models appear.
        assert "claude-sonnet-4-6" in result.output
        assert "claude-opus-4-7" in result.output
        # Header columns present.
        assert "phase" in result.output
        assert "total_tokens" in result.output
        assert "attempts" in result.output

    def test_rail_filter_narrows_output(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rollup", "--rail", "INFRA", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "INFRA" in result.output
        # BUILD rail should be filtered out — verify via JSON to avoid header
        # confusion.
        result_json = runner.invoke(
            cli,
            [
                "rollup",
                "--rail",
                "INFRA",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result_json.exit_code == 0
        rows = json.loads(result_json.output)
        assert all(r["rail"] == "INFRA" for r in rows)
        assert rows  # non-empty

    def test_phase_filter(self, project_dir: Path, seeded_db: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rollup",
                "--phase",
                "22",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert rows
        assert all(r["phase"] == "22" for r in rows)

    def test_json_output_is_valid_list_of_dicts(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rollup", "--json", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)
        assert all("total_tokens" in r for r in rows)


# ---------------------------------------------------------------------------
# INFRA-309: non-build-role exclusion
# ---------------------------------------------------------------------------


class TestNonBuildRoleExclusion:
    """B4-B9, C10-C12: rollup/dollars exclude non-build roles; models retains
    and labels them."""

    def test_rollup_excludes_sidebar_bucket_and_retains_null_role(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        db_path = project_dir / ".companion" / "effort.db"
        # A NULL-role row (B5) with non-zero tokens. ``effort_db``'s live
        # schema constrains ``agent_role NOT NULL`` — no writer intentionally
        # omits it — but the rollup query still guards NULL defensively (a
        # NULL role is not a *known* non-build role), so this row is inserted
        # by rebuilding the table without that constraint, matching only what
        # this test needs to prove: the SQL predicate's ``agent_role IS
        # NULL OR ...`` branch retains such a row rather than silently
        # dropping it.
        con = sqlite3.connect(str(db_path))
        con.execute("ALTER TABLE attempts RENAME TO attempts_orig")
        con.execute("CREATE TABLE attempts AS SELECT * FROM attempts_orig")
        con.execute("DROP TABLE attempts_orig")
        con.execute(
            "INSERT INTO attempts "
            "(story_id, phase, rail, agent_role, model, attempt_number, "
            " tokens_total, tokens_in, tokens_out, ts) "
            "VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)",
            (
                "INFRA-100",
                "22",
                "INFRA",
                "claude-sonnet-4-6",
                1,
                42,
                40,
                2,
                "2026-05-01T00:00:00+00:00",
            ),
        )
        con.commit()
        con.close()
        # Sidebar-extraction rows: phase=NULL, rail=NULL, a distinct model.
        for _ in range(3):
            _seed_attempt(
                db_path,
                story_id="sidebar:no-story",
                phase=None,
                rail=None,
                model="llama3.1:8b",
                agent_role="sidebar-extractor",
                attempt_number=1,
                tokens_total=0,
                tokens_in=0,
                tokens_out=0,
                outcome=None,
            )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rollup", "--json", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        # No row carries the sidebar-only bucket's model.
        assert not any(r["model"] == "llama3.1:8b" for r in rows)
        # The NULL-role row survives (B5).
        null_role_rows = [r for r in rows if r["phase"] == "22" and r["rail"] == "INFRA"]
        assert sum(r["attempts"] for r in null_role_rows) >= 1

        # Text mode discloses the exclusion, naming all three roles.
        text_result = runner.invoke(
            cli,
            ["rollup", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "excluding non-build roles" in text_result.output
        assert "seed-miner" in text_result.output
        assert "seed-reconcile" in text_result.output
        assert "sidebar-extractor" in text_result.output

    def test_rollup_json_mode_has_no_disclosure_line(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rollup", "--json", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        # JSON mode stays a bare list — no disclosure text anywhere.
        assert "excluding non-build roles" not in result.output
        rows = json.loads(result.output)
        assert isinstance(rows, list)

    def test_rollup_dollars_exclusion_matches_token_exclusion(
        self,
        project_dir: Path,
        seeded_db: Path,
        pricing_file: Path,
    ) -> None:
        """B6: a (phase, rail, model) group shared by a build row and a
        non-build row must compute total_tokens and dollars_estimate over the
        same (filtered) row set."""

        db_path = project_dir / ".companion" / "effort.db"
        # Share the exact (phase, rail, model) triple with an existing build
        # row: INFRA-100 / INFRA / claude-sonnet-4-6, phase "22".
        _seed_attempt(
            db_path,
            story_id="sidebar:INFRA-100",
            phase="22",
            rail="INFRA",
            model="claude-sonnet-4-6",
            agent_role="sidebar-extractor",
            attempt_number=1,
            tokens_total=9000,
            tokens_in=9000,
            tokens_out=0,
            outcome=None,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rollup",
                "--dollars",
                str(pricing_file),
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        group = next(
            r
            for r in rows
            if r["phase"] == "22"
            and r["rail"] == "INFRA"
            and r["model"] == "claude-sonnet-4-6"
        )
        # total_tokens excludes the 9000-token sidebar row
        # (1000 + 1500 + 500 = 3000 tokens_total across the three build rows).
        assert group["total_tokens"] == 3000
        # dollars_estimate must be computed over that same excluded set, not
        # inflated by the sidebar row's 9000 input tokens.
        # Sonnet rate: input 3 USD/Mtok, output 15 USD/Mtok.
        # tokens_in 800+1200+400=2400; tokens_out 200+300+100=600.
        expected = (2400 * 3.00 + 600 * 15.00) / 1_000_000.0
        assert group["dollars_estimate"] == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# rework
# ---------------------------------------------------------------------------


class TestRework:
    def test_default_threshold_finds_rework_story(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rework", "--json", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        story_ids = {r["story_id"] for r in rows}
        # INFRA-100 had a builder attempt 2 — rework case.
        assert "INFRA-100" in story_ids
        # BUILD-200's max attempt_number is 1 — should be excluded with default threshold=1.
        assert "BUILD-200" not in story_ids

    def test_rework_text_output_has_columns(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rework", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "INFRA-100" in result.output
        assert "builder_tokens" in result.output
        assert "reviewer_tokens" in result.output

    def test_threshold_zero_includes_all_stories(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rework",
                "--threshold",
                "0",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        story_ids = {r["story_id"] for r in rows}
        assert "INFRA-100" in story_ids
        assert "BUILD-200" in story_ids


# ---------------------------------------------------------------------------
# expensive
# ---------------------------------------------------------------------------


class TestExpensive:
    def test_top_lists_stories_by_tokens(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["expensive", "--json", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert len(rows) == 2
        assert {r["story_id"] for r in rows} == {"INFRA-100", "BUILD-200"}
        # Sorted descending by total_tokens.
        assert rows[0]["total_tokens"] >= rows[1]["total_tokens"]
        # Role breakdown is present in JSON (dict form).
        for r in rows:
            assert isinstance(r["role_breakdown"], dict)
            assert "builder" in r["role_breakdown"] or "reviewer" in r["role_breakdown"]

    def test_top_n_limit(self, project_dir: Path, seeded_db: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "expensive",
                "--top",
                "1",
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert len(rows) == 1

    def test_text_output_contains_role_breakdown(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["expensive", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "INFRA-100" in result.output
        assert "BUILD-200" in result.output
        # Builder/reviewer breakdown rendered in text.
        assert "builder=" in result.output or "reviewer=" in result.output


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


class TestModels:
    def test_per_model_role_rows(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["models", "--json", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        # We expect rows for both models and both roles where data exists:
        # sonnet/builder, sonnet/reviewer, opus/reviewer.
        keys = {(r["model"], r["agent_role"]) for r in rows}
        assert ("claude-sonnet-4-6", "builder") in keys
        assert ("claude-sonnet-4-6", "reviewer") in keys
        assert ("claude-opus-4-7", "reviewer") in keys

    def test_pass_rate_calculated(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["models", "--json", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        opus_reviewer = next(
            r
            for r in rows
            if r["model"] == "claude-opus-4-7" and r["agent_role"] == "reviewer"
        )
        # Opus reviewer: 1 PASS + 1 FAIL on BUILD-200, 1 PASS on INFRA-100 = 2/3.
        assert opus_reviewer["attempts"] == 3
        assert opus_reviewer["pass_count"] == 2
        assert opus_reviewer["fail_count"] == 1
        assert opus_reviewer["pass_rate_pct"] == pytest.approx(66.67, abs=0.01)

    def test_text_output_has_columns(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["models", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "pass_rate_pct" in result.output
        assert "claude-sonnet-4-6" in result.output

    def test_role_class_labels_non_build_and_build_rows(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        """C10-C11: models retains every role and labels it; NULL role is
        classed 'build' (consistent with B5's don't-silently-reclassify
        rule)."""

        db_path = project_dir / ".companion" / "effort.db"
        _seed_attempt(
            db_path,
            story_id="sidebar:no-story",
            phase=None,
            rail=None,
            model="llama3.1:8b",
            agent_role="sidebar-extractor",
            attempt_number=1,
            tokens_total=0,
            tokens_in=0,
            tokens_out=0,
            outcome=None,
        )
        # Rebuild the ``attempts`` table without its live ``agent_role NOT
        # NULL`` constraint so a NULL-role row can be inserted directly — see
        # the equivalent rebuild in TestNonBuildRoleExclusion for why: no
        # writer intentionally omits agent_role, but the query must still
        # not silently reclassify a NULL role that it may encounter.
        con = sqlite3.connect(str(db_path))
        con.execute("ALTER TABLE attempts RENAME TO attempts_orig")
        con.execute("CREATE TABLE attempts AS SELECT * FROM attempts_orig")
        con.execute("DROP TABLE attempts_orig")
        con.execute(
            "INSERT INTO attempts "
            "(story_id, phase, rail, agent_role, model, attempt_number, "
            " tokens_total, tokens_in, tokens_out, ts) "
            "VALUES (?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?)",
            ("INFRA-100", "claude-sonnet-4-6", 1, 42, 40, 2, "2026-05-01T00:00:00+00:00"),
        )
        con.commit()
        con.close()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["models", "--json", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)

        sidebar_row = next(
            r for r in rows if r["agent_role"] == "sidebar-extractor"
        )
        assert sidebar_row["role_class"] == "non-build"

        builder_row = next(
            r
            for r in rows
            if r["agent_role"] == "builder" and r["model"] == "claude-sonnet-4-6"
        )
        assert builder_row["role_class"] == "build"

        null_role_row = next(r for r in rows if r["agent_role"] is None)
        assert null_role_row["role_class"] == "build"


# ---------------------------------------------------------------------------
# --dollars
# ---------------------------------------------------------------------------


class TestDollars:
    def test_rollup_with_dollars_adds_column(
        self,
        project_dir: Path,
        seeded_db: Path,
        pricing_file: Path,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rollup",
                "--dollars",
                str(pricing_file),
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert rows
        assert all("dollars_estimate" in r for r in rows)
        # Sonnet rates: input 3, output 15 USD/Mtok.
        # Find the sonnet/INFRA/22 row: total tokens_in across all sonnet/INFRA
        # builder+reviewer attempts is 800+1200+400 = 2400; tokens_out
        # 200+300+100 = 600. Dollars = (2400*3 + 600*15) / 1e6 = 16200/1e6.
        sonnet_infra = [
            r
            for r in rows
            if r["rail"] == "INFRA" and r["model"] == "claude-sonnet-4-6"
        ]
        assert sonnet_infra
        assert sonnet_infra[0]["dollars_estimate"] > 0

    def test_rework_with_dollars_adds_column(
        self,
        project_dir: Path,
        seeded_db: Path,
        pricing_file: Path,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rework",
                "--dollars",
                str(pricing_file),
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert rows
        assert all("dollars_estimate" in r for r in rows)
        assert all(r["dollars_estimate"] >= 0 for r in rows)

    def test_expensive_with_dollars_adds_column(
        self,
        project_dir: Path,
        seeded_db: Path,
        pricing_file: Path,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "expensive",
                "--dollars",
                str(pricing_file),
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert rows
        assert all("dollars_estimate" in r for r in rows)

    def test_models_with_dollars_adds_column(
        self,
        project_dir: Path,
        seeded_db: Path,
        pricing_file: Path,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "models",
                "--dollars",
                str(pricing_file),
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        assert rows
        assert all("dollars_estimate" in r for r in rows)

    def test_unknown_model_in_pricing_treated_as_zero(
        self,
        project_dir: Path,
        seeded_db: Path,
        tmp_path: Path,
    ) -> None:
        # Pricing file omits claude-opus-4-7 entirely.
        partial = tmp_path / "partial_pricing.json"
        partial.write_text(
            json.dumps(
                {
                    "claude-sonnet-4-6": {
                        "input": 3.00,
                        "output": 15.00,
                        "cache_read": 0.30,
                        "cache_write": 3.75,
                    }
                }
            ),
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rollup",
                "--dollars",
                str(partial),
                "--json",
                "--project-dir",
                str(project_dir),
            ],
            catch_exceptions=False,
        )
        # Should not crash; opus rows project to zero.
        assert result.exit_code == 0, result.output
        rows = json.loads(result.output)
        opus_rows = [r for r in rows if r["model"] == "claude-opus-4-7"]
        assert opus_rows
        assert all(r["dollars_estimate"] == 0 for r in opus_rows)

    def test_missing_dollars_file_errors(
        self,
        project_dir: Path,
        seeded_db: Path,
        tmp_path: Path,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rollup",
                "--dollars",
                str(tmp_path / "nonexistent.json"),
                "--project-dir",
                str(project_dir),
            ],
        )
        assert result.exit_code != 0
        # Friendly error mentions the missing file.
        combined = (result.output or "") + (
            getattr(result, "stderr", "") if hasattr(result, "stderr") else ""
        )
        # Click's mix_stderr default may merge streams — check either.
        assert "not found" in combined.lower() or result.exit_code == 2


# ---------------------------------------------------------------------------
# Empty / missing DB
# ---------------------------------------------------------------------------


class TestEmptyAndMissing:
    def test_missing_db_friendly_message(self, project_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rollup", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "no effort data" in result.output.lower()

    def test_empty_db_friendly_message(self, project_dir: Path) -> None:
        # Init an empty DB but no rows.
        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["rework", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "no effort data" in result.output.lower()

    def test_missing_db_all_subcommands(self, project_dir: Path) -> None:
        runner = CliRunner()
        for subcmd in ("rollup", "rework", "expensive", "models", "pending"):
            result = runner.invoke(
                cli,
                [subcmd, "--project-dir", str(project_dir)],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, (subcmd, result.output)
            assert "no effort data" in result.output.lower(), (subcmd, result.output)


# ---------------------------------------------------------------------------
# CER-016: --db-path containment (resolve_db_path_arg delegation)
# ---------------------------------------------------------------------------


class TestDbPathContainment:
    def test_escaping_db_path_exits_nonzero_and_creates_no_file(
        self, project_dir: Path
    ) -> None:
        """C6: an explicit --db-path escaping --project-dir must exit
        non-zero on every subcommand and must not create a database file
        outside project_dir."""
        escaping_db = project_dir.parent / "escape-effort.db"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rollup",
                "--project-dir", str(project_dir),
                "--db-path", str(escaping_db),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code != 0
        assert not escaping_db.exists()

    def test_relative_db_path_inside_project_still_works(
        self, project_dir: Path, seeded_db: Path
    ) -> None:
        """Sanity check alongside the escape test: a relative --db-path
        resolving inside project_dir behaves identically to before."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rollup",
                "--project-dir", str(project_dir),
                "--db-path", ".companion/effort.db",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# pending (CER-091 defect 3, E6)
# ---------------------------------------------------------------------------


class TestPending:
    def test_renders_reason_and_age_hours_for_seeded_pending_row(
        self, project_dir: Path
    ) -> None:
        import json as _json
        from datetime import datetime, timedelta, timezone

        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-343",
            agent_role="security-auditor",
            attempt_number=1,
            ts=old_ts,
        )
        # INFRA-287 (CER-101): classify_pending_reason now applies the same
        # containment rule as the sweep, so this fixture moved under a tasks/
        # component — a bare project-dir path would classify "uncontained"
        # instead of the "no-outcome" rendering this test pins.
        output_file = project_dir / "tasks" / "agent.output"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            _json.dumps({
                "type": "assistant",
                "message": {
                    "id": "msg_1",
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "no result json here"}],
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                },
            }) + "\n",
            encoding="utf-8",
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", str(output_file))

        db_before = db_path.read_bytes()
        mtime_before = db_path.stat().st_mtime

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["pending", "--project-dir", str(project_dir), "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        rows = _json.loads(result.output)
        assert len(rows) == 1
        row = rows[0]
        assert row["story_id"] == "INFRA-343"
        assert row["agent_role"] == "security-auditor"
        assert row["reason"] == "no-outcome"
        assert isinstance(row["age_hours"], (int, float))
        assert row["age_hours"] >= 4.9
        assert row["has_tokens"] is False
        assert row["has_outcome"] is False

        # Zero writes: the db file is byte-identical and its mtime unchanged.
        assert db_path.read_bytes() == db_before
        assert db_path.stat().st_mtime == mtime_before

    def test_text_output_includes_columns(self, project_dir: Path) -> None:
        db_path = project_dir / ".companion" / "effort.db"
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-344",
            agent_role="reviewer",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
        )
        # INFRA-287 (CER-101): a tasks/ component keeps this path well-placed
        # under the containment rule, so a nonexistent file still classifies
        # "file-missing" (an uncontained path now reports "uncontained").
        import os as _os
        import tempfile as _tempfile

        missing = _os.path.join(
            _tempfile.gettempdir(),
            "claude-1000", "-slug", "sess-1", "tasks", "does-not-exist.output",
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", missing)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["pending", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "reason" in result.output
        assert "file-missing" in result.output

    def test_excludes_fully_reconciled_rows(self, project_dir: Path, seeded_db: Path) -> None:
        """The seeded_db fixture's rows are all fully reconciled (tokens and
        outcome both set) — none should appear as pending."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["pending", "--project-dir", str(project_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "no effort data" in result.output.lower()
