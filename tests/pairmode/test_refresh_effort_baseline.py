"""Tests for skills/pairmode/scripts/refresh_effort_baseline.py.

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_refresh_effort_baseline.py -x -q
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import sys
from pathlib import Path

from click.testing import CliRunner

# Ensure the pairmode scripts directory is on the path.
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts")
)

from refresh_effort_baseline import main as refresh_main


def _create_effort_db_with_rows(
    companion_dir: Path,
    rows: list[tuple[str, int]],  # (agent_role, tokens_total)
) -> Path:
    db_path = companion_dir / "effort.db"
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
        for i, (role, tokens) in enumerate(rows, start=1):
            conn.execute(
                """
                INSERT INTO attempts
                    (story_id, phase, rail, agent_role, attempt_number,
                     tokens_total, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"T-{i:03d}",
                    "1",
                    "TEST",
                    role,
                    1,
                    tokens,
                    "2026-01-01T00:00:00+00:00",
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _make_project(tmp_path: Path, name: str, rows: list[tuple[str, int]]) -> Path:
    project_dir = tmp_path / name
    companion = project_dir / ".companion"
    companion.mkdir(parents=True)
    _create_effort_db_with_rows(companion, rows)
    return project_dir


# ---------------------------------------------------------------------------
# Test 1: single project, 10 builder attempts
# ---------------------------------------------------------------------------


def test_single_project_builder_aggregation(tmp_path):
    """CLI against a single tempdir effort.db with 10 builder attempts."""
    token_values = [10_000, 20_000, 30_000, 40_000, 50_000,
                    60_000, 70_000, 80_000, 90_000, 100_000]
    rows = [("builder", t) for t in token_values]
    project_dir = _make_project(tmp_path, "proj1", rows)
    output = tmp_path / "out.json"

    runner = CliRunner()
    result = runner.invoke(
        refresh_main,
        [
            "--project-dirs", str(project_dir),
            "--output", str(output),
            "--generated-at", "2026-05-29T00:00:00Z",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    data = json.loads(output.read_text())
    assert data["by_role"]["builder"]["n"] == 10
    assert data["by_role"]["builder"]["median"] == int(statistics.median(token_values))


# ---------------------------------------------------------------------------
# Test 2: two projects, aggregate n is sum; median computed across union
# ---------------------------------------------------------------------------


def test_two_projects_aggregate_n_and_union_median(tmp_path):
    """Two effort.dbs: aggregate n is the sum; median across the union."""
    rows_a = [("builder", t) for t in [10_000, 20_000, 30_000, 40_000, 50_000]]
    rows_b = [("builder", t) for t in [60_000, 70_000, 80_000, 90_000, 100_000]]
    project_a = _make_project(tmp_path, "proj_a", rows_a)
    project_b = _make_project(tmp_path, "proj_b", rows_b)
    output = tmp_path / "out.json"

    runner = CliRunner()
    result = runner.invoke(
        refresh_main,
        [
            "--project-dirs", str(project_a),
            "--project-dirs", str(project_b),
            "--output", str(output),
            "--generated-at", "2026-05-29T00:00:00Z",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    data = json.loads(output.read_text())
    assert data["by_role"]["builder"]["n"] == 10
    union = [10_000, 20_000, 30_000, 40_000, 50_000,
             60_000, 70_000, 80_000, 90_000, 100_000]
    assert data["by_role"]["builder"]["median"] == int(statistics.median(union))


# ---------------------------------------------------------------------------
# Test 3: missing path silently skipped
# ---------------------------------------------------------------------------


def test_missing_path_silently_skipped(tmp_path):
    """A missing project path is silently skipped; the run succeeds."""
    rows = [("builder", t) for t in [10_000, 20_000, 30_000, 40_000, 50_000]]
    real_project = _make_project(tmp_path, "real", rows)
    ghost_project = tmp_path / "ghost"  # never created
    output = tmp_path / "out.json"

    runner = CliRunner()
    result = runner.invoke(
        refresh_main,
        [
            "--project-dirs", str(real_project),
            "--project-dirs", str(ghost_project),
            "--output", str(output),
            "--generated-at", "2026-05-29T00:00:00Z",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    data = json.loads(output.read_text())
    assert data["by_role"]["builder"]["n"] == 5
    assert "ghost" not in data["source_projects"]
    assert "real" in data["source_projects"]


# ---------------------------------------------------------------------------
# Test 4: byte-identical output across two runs (idempotent)
# ---------------------------------------------------------------------------


def test_idempotent_byte_identical_output(tmp_path):
    """Two runs with the same input produce byte-identical output."""
    rows_a = [("builder", t) for t in [10_000, 20_000, 30_000, 40_000, 50_000]]
    rows_b = [("reviewer", t) for t in [15_000, 25_000, 35_000, 45_000, 55_000]]
    project_a = _make_project(tmp_path, "proj_a", rows_a)
    project_b = _make_project(tmp_path, "proj_b", rows_b)

    output_1 = tmp_path / "out1.json"
    output_2 = tmp_path / "out2.json"

    runner = CliRunner()
    # Reverse arg order between the two runs to also test source_projects sorting.
    runner.invoke(
        refresh_main,
        [
            "--project-dirs", str(project_a),
            "--project-dirs", str(project_b),
            "--output", str(output_1),
            "--generated-at", "2026-05-29T00:00:00Z",
        ],
        catch_exceptions=False,
    )
    runner.invoke(
        refresh_main,
        [
            "--project-dirs", str(project_b),
            "--project-dirs", str(project_a),
            "--output", str(output_2),
            "--generated-at", "2026-05-29T00:00:00Z",
        ],
        catch_exceptions=False,
    )

    assert output_1.read_bytes() == output_2.read_bytes()
