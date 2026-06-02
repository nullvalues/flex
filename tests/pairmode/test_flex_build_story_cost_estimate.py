"""Tests for ``flex_build.py story-cost-estimate`` subcommand (INFRA-135).

Follows the subprocess pattern from test_flex_build_current_phase.py and the
DB seeding pattern from test_effort_db.py.

Tests:
1. test_estimate_returns_median_when_sufficient_samples
2. test_estimate_insufficient_data_when_fewer_than_three_rows
3. test_estimate_insufficient_data_when_no_db
4. test_estimate_ignores_fail_rows
5. test_estimate_ignores_null_tokens_total
6. test_estimate_segregates_by_story_class
7. test_estimate_segregates_by_rail
8. test_estimate_falls_back_to_story_class_code_when_frontmatter_missing
9. test_estimate_depth_guard
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from skills.pairmode.scripts import effort_db

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPT = _REPO_ROOT / "skills" / "pairmode" / "scripts" / "flex_build.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args: str) -> subprocess.CompletedProcess:
    """Invoke flex_build.py with *args*; return the completed process."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(_REPO_ROOT),
        },
    )


def _seed_db(
    db_path: Path,
    rail: str,
    story_class: str,
    outcome: str,
    tokens_total: int | None,
    n: int,
) -> None:
    """Insert ``n`` rows with the given (rail, story_class, outcome, tokens_total)."""
    effort_db.init_db(db_path)
    for i in range(n):
        effort_db.insert_attempt(
            db_path,
            story_id=f"{rail}-{100 + i:03d}",
            agent_role="builder",
            attempt_number=1,
            ts="2026-01-01T00:00:00+00:00",
            rail=rail,
            story_class=story_class,
            outcome=outcome,
            tokens_total=tokens_total,
        )


def _companion_dir(project_dir: Path) -> Path:
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    return companion


def _enable_tracking(project_dir: Path) -> None:
    companion = _companion_dir(project_dir)
    state = {"effort_tracking": True}
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_story_file(project_dir: Path, story_id: str, rail: str, story_class: str) -> Path:
    """Write a minimal story file with frontmatter so flex_build can read it."""
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"
    story_path.write_text(
        f"---\nid: {story_id}\nrail: {rail}\nstory_class: {story_class}\n"
        "status: planned\nphase: '53'\nprimary_files: []\n---\n\n## Ensures\n\n- OK\n",
        encoding="utf-8",
    )
    return story_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_estimate_returns_median_when_sufficient_samples(tmp_path: Path) -> None:
    """5 PASS rows produce a median estimate."""
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"

    # Seed 5 rows with distinct token counts so median is deterministic.
    tokens = [10000, 20000, 30000, 40000, 50000]
    effort_db.init_db(db_path)
    for i, t in enumerate(tokens):
        effort_db.insert_attempt(
            db_path,
            story_id=f"BUILD-{200 + i:03d}",
            agent_role="builder",
            attempt_number=1,
            ts="2026-01-01T00:00:00+00:00",
            rail="BUILD",
            story_class="methodology",
            outcome="PASS",
            tokens_total=t,
        )

    _write_story_file(tmp_path, "BUILD-999", "BUILD", "methodology")

    result = _run(
        "story-cost-estimate",
        "--story-id", "BUILD-999",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout.strip()
    # Median of [10000, 20000, 30000, 40000, 50000] = 30000
    assert out == "estimate: 30000 tokens (median of 5 PASS attempts on BUILD/methodology)", out


def test_estimate_insufficient_data_when_fewer_than_three_rows(tmp_path: Path) -> None:
    """2 PASS rows produce an 'insufficient data' message."""
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"
    _seed_db(db_path, "BUILD", "methodology", "PASS", 25000, 2)
    _write_story_file(tmp_path, "BUILD-999", "BUILD", "methodology")

    result = _run(
        "story-cost-estimate",
        "--story-id", "BUILD-999",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout.strip()
    assert "insufficient data" in out
    assert "(2 PASS attempts on BUILD/methodology)" in out, out


def test_estimate_insufficient_data_when_no_db(tmp_path: Path) -> None:
    """No .companion/ directory → insufficient data (0 attempts), exit 0."""
    # No .companion/ created — depth guard needs at least 3 path components;
    # tmp_path already satisfies that.
    _write_story_file(tmp_path, "BUILD-999", "BUILD", "code")

    result = _run(
        "story-cost-estimate",
        "--story-id", "BUILD-999",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout.strip()
    assert "insufficient data" in out
    assert "(0 PASS attempts on BUILD/code)" in out, out


def test_estimate_ignores_fail_rows(tmp_path: Path) -> None:
    """3 FAIL rows produce insufficient data — only PASS rows count."""
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"
    _seed_db(db_path, "BUILD", "code", "FAIL", 30000, 3)
    _write_story_file(tmp_path, "BUILD-999", "BUILD", "code")

    result = _run(
        "story-cost-estimate",
        "--story-id", "BUILD-999",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout.strip()
    assert "insufficient data" in out, out


def test_estimate_ignores_null_tokens_total(tmp_path: Path) -> None:
    """3 PASS rows with NULL tokens_total produce insufficient data."""
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"
    _seed_db(db_path, "BUILD", "code", "PASS", None, 3)
    _write_story_file(tmp_path, "BUILD-999", "BUILD", "code")

    result = _run(
        "story-cost-estimate",
        "--story-id", "BUILD-999",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout.strip()
    assert "insufficient data" in out, out


def test_estimate_segregates_by_story_class(tmp_path: Path) -> None:
    """5 PASS rows for (BUILD, code) don't satisfy (BUILD, methodology)."""
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"
    _seed_db(db_path, "BUILD", "code", "PASS", 20000, 5)

    # Story file declares methodology
    _write_story_file(tmp_path, "BUILD-999", "BUILD", "methodology")

    result = _run(
        "story-cost-estimate",
        "--story-id", "BUILD-999",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout.strip()
    assert "insufficient data" in out, out


def test_estimate_segregates_by_rail(tmp_path: Path) -> None:
    """5 PASS rows for (BUILD, code) don't satisfy (INFRA, code)."""
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"
    _seed_db(db_path, "BUILD", "code", "PASS", 20000, 5)

    # Story file declares INFRA rail
    _write_story_file(tmp_path, "INFRA-999", "INFRA", "code")

    result = _run(
        "story-cost-estimate",
        "--story-id", "INFRA-999",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout.strip()
    assert "insufficient data" in out, out


def test_estimate_falls_back_to_story_class_code_when_frontmatter_missing(
    tmp_path: Path,
) -> None:
    """When the story file is absent, story_class defaults to 'code'."""
    _enable_tracking(tmp_path)
    db_path = tmp_path / ".companion" / "effort.db"

    # Seed 5 PASS rows for (INFRA, code) — the expected default
    _seed_db(db_path, "INFRA", "code", "PASS", 40000, 5)

    # Do NOT write a story file — frontmatter is unavailable
    result = _run(
        "story-cost-estimate",
        "--story-id", "INFRA-999",
        "--project-dir", str(tmp_path),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    out = result.stdout.strip()
    # Should have found 5 PASS rows for (INFRA, code) — not insufficient data
    assert "insufficient data" not in out, (
        f"Expected a numeric estimate but got: {out}"
    )
    assert "INFRA/code" in out, out


def test_estimate_depth_guard(tmp_path: Path) -> None:
    """--project-dir with fewer than 3 path components is rejected (exit 1)."""
    result = _run(
        "story-cost-estimate",
        "--story-id", "INFRA-135",
        "--project-dir", "/",
    )
    assert result.returncode == 1
    assert "depth guard" in result.stderr.lower() or "too shallow" in result.stderr.lower(), (
        f"Expected depth guard error, got stderr: {result.stderr}"
    )
