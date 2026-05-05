"""Tests for skills/pairmode/scripts/record_attempt.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from skills.pairmode.scripts import effort_db
from skills.pairmode.scripts.record_attempt import record_attempt


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


def _required_args(project_dir: Path) -> list[str]:
    return [
        "--project-dir", str(project_dir),
        "--story-id", "INFRA-028",
        "--agent-role", "builder",
        "--attempt-number", "1",
    ]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_writes_row_with_all_flags(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path) + [
                "--phase", "22",
                "--rail", "INFRA",
                "--model", "claude-sonnet-4-6",
                "--tokens-total", "12345",
                "--tokens-in", "10000",
                "--tokens-out", "2345",
                "--cache-read-tokens", "500",
                "--cache-write-tokens", "750",
                "--tool-uses", "8",
                "--duration-ms", "42000",
                "--outcome", "PASS",
                "--notes", "happy path",
                "--ts", "2026-05-01T00:00:00+00:00",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        row = rows[0]
        assert row["phase"] == "22"
        assert row["rail"] == "INFRA"
        assert row["model"] == "claude-sonnet-4-6"
        assert row["tokens_total"] == 12345
        assert row["tokens_in"] == 10000
        assert row["tokens_out"] == 2345
        assert row["cache_read_tokens"] == 500
        assert row["cache_write_tokens"] == 750
        assert row["tool_uses"] == 8
        assert row["duration_ms"] == 42000
        assert row["outcome"] == "PASS"
        assert row["notes"] == "happy path"
        assert row["ts"] == "2026-05-01T00:00:00+00:00"

    def test_minimal_flags(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1

    def test_auto_fills_ts_when_omitted(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        ts = rows[0]["ts"]
        assert ts is not None
        # ISO-8601 with timezone (+00:00 for UTC).
        assert "+" in ts or "Z" in ts or "-" in ts[10:]
        # Must look like an ISO date-time.
        assert "T" in ts


# ---------------------------------------------------------------------------
# No-op when tracking disabled
# ---------------------------------------------------------------------------


class TestNoOp:
    def test_no_state_json(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "effort_tracking disabled" in result.stderr if hasattr(result, "stderr") else True
        # No DB written.
        assert not (tmp_path / ".companion" / "effort.db").exists()

    def test_state_json_present_but_flag_missing(self, tmp_path: Path) -> None:
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"pairmode_version": "0.1.0"}), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert not (tmp_path / ".companion" / "effort.db").exists()

    def test_flag_explicitly_false(self, tmp_path: Path) -> None:
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"effort_tracking": False}),
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert not (tmp_path / ".companion" / "effort.db").exists()


# ---------------------------------------------------------------------------
# Required flags
# ---------------------------------------------------------------------------


class TestRequiredFlags:
    def test_missing_story_id(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--project-dir", str(tmp_path),
                "--agent-role", "builder",
            ],
        )
        assert result.exit_code != 0
        assert "story-id" in result.output.lower() or "story_id" in result.output.lower()

    def test_missing_agent_role(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--project-dir", str(tmp_path),
                "--story-id", "INFRA-028",
            ],
        )
        assert result.exit_code != 0
        assert "agent-role" in result.output.lower() or "agent_role" in result.output.lower()


# ---------------------------------------------------------------------------
# DB path resolution
# ---------------------------------------------------------------------------


class TestDbPathResolution:
    def test_db_path_override(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        custom_db = tmp_path / "custom" / "effort.db"
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path) + ["--db-path", str(custom_db)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert custom_db.exists()
        assert not (tmp_path / ".companion" / "effort.db").exists()

    def test_state_json_effort_db_path_used(self, tmp_path: Path) -> None:
        custom_db = tmp_path / "alt" / "effort.db"
        _enable_tracking(tmp_path, effort_db_path=str(custom_db))

        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path),
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert custom_db.exists()


# ---------------------------------------------------------------------------
# Schema integrity
# ---------------------------------------------------------------------------


class TestSchemaSafety:
    def test_no_pricing_table_created(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        runner = CliRunner()
        runner.invoke(
            record_attempt,
            _required_args(tmp_path),
            catch_exceptions=False,
        )
        db_path = tmp_path / ".companion" / "effort.db"
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cur.fetchall()}
        finally:
            conn.close()
        assert "attempts" in tables
        assert "pricing" not in tables
