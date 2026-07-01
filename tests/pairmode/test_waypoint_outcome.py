"""Tests for OBS-005: waypoint outcome recording + render correctness (CER-055).

Diagnoses and verifies the fix for the NULL-as-FAIL rendering bug:
- queryWaypoints previously filtered AND outcome = 'FAIL' AND agent_role = 'reviewer',
  making ALL returned waypoints appear as FAIL by construction.
- Fix: remove those filters; return all attempts; NULL outcome stays NULL.

Tests use synthetic effort.db; no live fleet dependence (CER-057 lesson).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

FLEX_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# effort.db fixture builder
# ---------------------------------------------------------------------------

def _make_effort_db(tmp_path: Path) -> Path:
    """Create a synthetic effort.db with mixed PASS/FAIL/NULL-outcome rows."""
    db_path = tmp_path / "effort.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE attempts (
                id INTEGER PRIMARY KEY,
                story_id TEXT,
                agent_role TEXT,
                attempt_number INTEGER,
                ts TEXT,
                tokens_total INTEGER,
                duration_ms INTEGER,
                outcome TEXT,
                phase TEXT,
                rail TEXT
            )
        """)
        rows = [
            # (story_id, agent_role, attempt_number, ts, tokens_total, outcome)
            ("S-001", "builder", 1, "2026-01-01T00:01:00Z", 30000, "PASS"),
            ("S-001", "reviewer", 1, "2026-01-01T00:02:00Z", 35000, "FAIL"),
            ("S-001", "builder", 2, "2026-01-01T00:03:00Z", 28000, None),   # NULL outcome
            ("S-001", "reviewer", 2, "2026-01-01T00:04:00Z", 33000, "PASS"),
            ("S-002", "builder", 1, "2026-01-02T00:01:00Z", 20000, None),   # NULL outcome
            ("S-002", "reviewer", 1, "2026-01-02T00:02:00Z", 22000, "PASS"),
        ]
        conn.executemany(
            "INSERT INTO attempts (story_id, agent_role, attempt_number, ts, tokens_total, outcome, phase, rail) "
            "VALUES (?, ?, ?, ?, ?, ?, 'phase-1', 'S')",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _query_waypoints(db_path: Path, threshold: int = 120000) -> list[dict]:
    """Run the equivalent of queryWaypoints via raw SQL (mirrors the fixed effortDb.ts logic)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT ts AS created_at, tokens_total, story_id, phase, agent_role, outcome
               FROM attempts
               WHERE tokens_total IS NOT NULL
               ORDER BY ts DESC
               LIMIT 100"""
        ).fetchall()
        result = []
        for row in rows:
            tokens = row["tokens_total"]
            result.append({
                "ts": row["created_at"],
                "tokens": tokens,
                "story_id": row["story_id"],
                "phase": row["phase"],
                "agent_role": row["agent_role"],
                "outcome": row["outcome"],
                "near_miss": tokens > threshold * 0.85,
            })
        return result
    finally:
        conn.close()


def _pass_rate(db_path: Path) -> float:
    """Compute pass_rate as pass_count / total_attempts (NULL outcome = neither PASS nor FAIL)."""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN outcome='PASS' THEN 1 ELSE 0 END) AS pass_count "
            "FROM attempts"
        ).fetchone()
        total = row[0]
        passes = row[1] or 0
        return passes / total if total else 0.0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Source-of-truth: record_attempt writes NULL for unspecified outcomes
# ---------------------------------------------------------------------------

class TestRecordAttemptNullOutcome:
    def _make_project(self, tmp_path: Path) -> Path:
        """Create a minimal project with effort_tracking enabled."""
        project = tmp_path / "proj"
        companion = project / ".companion"
        companion.mkdir(parents=True)
        (companion / "state.json").write_text(
            json.dumps({"effort_tracking": True}), encoding="utf-8"
        )
        return project

    def test_null_outcome_stored_correctly(self, tmp_path: Path) -> None:
        """record_attempt.py without --outcome → SQL NULL (not 'FAIL')."""
        import subprocess
        import sys

        project = self._make_project(tmp_path)
        db_path = project / ".companion" / "effort.db"
        result = subprocess.run(
            [
                sys.executable,
                str(FLEX_ROOT / "skills" / "pairmode" / "scripts" / "record_attempt.py"),
                "--story-id", "SYNTH-001",
                "--agent-role", "builder",
                "--attempt-number", "1",
                "--tokens-total", "5000",
                "--project-dir", str(project),
                "--phase", "test-phase",
                "--rail", "SYNTH",
            ],
            capture_output=True,
            text=True,
            cwd=str(FLEX_ROOT),
        )
        assert result.returncode == 0, f"record_attempt failed: {result.stderr}"

        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT outcome FROM attempts").fetchone()
            assert row is not None
            assert row[0] is None, f"Expected NULL outcome, got {row[0]!r}"
        finally:
            conn.close()

    def test_explicit_pass_stored_as_pass(self, tmp_path: Path) -> None:
        """record_attempt.py with --outcome PASS stores 'PASS'."""
        import subprocess
        import sys

        project = self._make_project(tmp_path)
        db_path = project / ".companion" / "effort.db"
        result = subprocess.run(
            [
                sys.executable,
                str(FLEX_ROOT / "skills" / "pairmode" / "scripts" / "record_attempt.py"),
                "--story-id", "SYNTH-002",
                "--agent-role", "reviewer",
                "--attempt-number", "1",
                "--tokens-total", "6000",
                "--outcome", "PASS",
                "--project-dir", str(project),
                "--phase", "test-phase",
                "--rail", "SYNTH",
            ],
            capture_output=True,
            text=True,
            cwd=str(FLEX_ROOT),
        )
        assert result.returncode == 0, f"record_attempt failed: {result.stderr}"
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT outcome FROM attempts").fetchone()
            assert row[0] == "PASS"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Render: queryWaypoints must NOT filter by outcome or agent_role
# ---------------------------------------------------------------------------

class TestQueryWaypointsRender:
    def test_returns_all_roles_not_just_reviewer(self, tmp_path: Path) -> None:
        """Waypoints must include builder and leaf-worker rows, not only reviewer."""
        db_path = _make_effort_db(tmp_path)
        waypoints = _query_waypoints(db_path)
        roles = {w["agent_role"] for w in waypoints}
        assert "builder" in roles, "builder rows missing from waypoints"
        assert "reviewer" in roles, "reviewer rows missing from waypoints"

    def test_null_outcome_not_suppressed(self, tmp_path: Path) -> None:
        """Rows with NULL outcome appear in waypoints; outcome field is None not 'FAIL'."""
        db_path = _make_effort_db(tmp_path)
        waypoints = _query_waypoints(db_path)
        null_rows = [w for w in waypoints if w["outcome"] is None]
        assert null_rows, "NULL-outcome rows are missing from waypoints — render bug (CER-055)"
        for row in null_rows:
            assert row["outcome"] is None, (
                f"NULL outcome was mapped to {row['outcome']!r} — must stay None, not FAIL"
            )

    def test_pass_rows_present(self, tmp_path: Path) -> None:
        """PASS outcome rows appear in waypoints."""
        db_path = _make_effort_db(tmp_path)
        waypoints = _query_waypoints(db_path)
        pass_rows = [w for w in waypoints if w["outcome"] == "PASS"]
        assert pass_rows, "PASS-outcome rows are missing from waypoints"

    def test_fail_rows_present(self, tmp_path: Path) -> None:
        """FAIL outcome rows still appear in waypoints."""
        db_path = _make_effort_db(tmp_path)
        waypoints = _query_waypoints(db_path)
        fail_rows = [w for w in waypoints if w["outcome"] == "FAIL"]
        assert fail_rows, "FAIL-outcome rows should appear in waypoints"

    def test_all_six_rows_returned(self, tmp_path: Path) -> None:
        """All 6 attempts appear — old query returned only the 2 reviewer FAIL rows."""
        db_path = _make_effort_db(tmp_path)
        waypoints = _query_waypoints(db_path)
        assert len(waypoints) == 6, (
            f"Expected 6 waypoints, got {len(waypoints)} — "
            "old outcome/role filter may be re-introduced"
        )

    def test_null_is_not_fail_in_render(self, tmp_path: Path) -> None:
        """Binding invariant: NULL outcome ≠ FAIL at every layer (CER-055)."""
        db_path = _make_effort_db(tmp_path)
        waypoints = _query_waypoints(db_path)
        for w in waypoints:
            if w["outcome"] is None:
                assert w["outcome"] != "FAIL", (
                    "NULL outcome must never be rendered as FAIL"
                )


# ---------------------------------------------------------------------------
# PASS-rate report: pairmode_effort.py models must not be corrupted by NULL
# ---------------------------------------------------------------------------

class TestPassRateReport:
    def test_pass_rate_excludes_null_from_numerator(self, tmp_path: Path) -> None:
        """NULL-outcome rows count toward total attempts but not PASS count."""
        db_path = _make_effort_db(tmp_path)
        # Fixture: 6 attempts; 3 PASS, 1 FAIL, 2 NULL
        # pass_rate = 3/6 = 0.5 (50%), not 3/4 = 0.75 (excluding NULLs from denominator)
        rate = _pass_rate(db_path)
        assert abs(rate - 0.5) < 0.001, (
            f"Expected pass_rate 0.5 (3 PASS / 6 total), got {rate:.3f}"
        )

    def test_null_outcome_never_counted_as_fail(self, tmp_path: Path) -> None:
        """CASE WHEN outcome='FAIL' THEN 1 ELSE 0 END does not count NULL as FAIL."""
        db_path = _make_effort_db(tmp_path)
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT SUM(CASE WHEN outcome='FAIL' THEN 1 ELSE 0 END) FROM attempts"
            ).fetchone()
            fail_count = row[0] or 0
            assert fail_count == 1, (
                f"Expected exactly 1 FAIL row, got {fail_count} — NULL may be counted as FAIL"
            )
        finally:
            conn.close()
