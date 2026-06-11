"""Tests for ``_read_story_frontmatter`` flex_factor field (INFRA-160) and
``_query_story_cost_samples`` waterfall fallback (INFRA-171).

Run with:
    PATH=$HOME/.local/bin:$PATH uv run pytest \\
        tests/pairmode/test_flex_build_story_cost.py -x -q
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Ensure the pairmode scripts directory is on the path.
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts")
)

from flex_build import _query_story_cost_samples, _read_story_frontmatter  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_story(tmp_path: Path, frontmatter_extra: str = "") -> Path:
    """Write a minimal story file with optional extra frontmatter lines."""
    story_dir = tmp_path / "docs" / "stories" / "INFRA"
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / "INFRA-160.md"
    story_path.write_text(
        "---\n"
        "id: INFRA-160\n"
        "rail: INFRA\n"
        "status: planned\n"
        "phase: '63'\n"
        "primary_files: []\n"
        f"{frontmatter_extra}"
        "---\n\n## Ensures\n\n- OK\n",
        encoding="utf-8",
    )
    return story_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_flex_factor_absent_defaults_to_1(tmp_path: Path) -> None:
    """Story without flex_factor field returns flex_factor=1.0."""
    story_path = _write_story(tmp_path)
    fm = _read_story_frontmatter(story_path)
    assert "flex_factor" in fm
    assert fm["flex_factor"] == 1.0


def test_flex_factor_present_numeric_returned(tmp_path: Path) -> None:
    """Story with flex_factor: 1.3 returns flex_factor=1.3."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: 1.3\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["flex_factor"] == 1.3


def test_flex_factor_present_integer_coerced(tmp_path: Path) -> None:
    """Story with flex_factor: 2 (integer) returns flex_factor=2.0."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: 2\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["flex_factor"] == 2.0


def test_flex_factor_non_numeric_defaults_to_1(tmp_path: Path) -> None:
    """Non-numeric flex_factor value is treated as absent → 1.0."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: 'large'\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["flex_factor"] == 1.0


def test_flex_factor_null_defaults_to_1(tmp_path: Path) -> None:
    """Null flex_factor value defaults to 1.0."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: null\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["flex_factor"] == 1.0


def test_other_frontmatter_keys_preserved(tmp_path: Path) -> None:
    """Existing frontmatter keys are not disturbed by adding flex_factor."""
    story_path = _write_story(tmp_path, frontmatter_extra="flex_factor: 0.8\n")
    fm = _read_story_frontmatter(story_path)
    assert fm["id"] == "INFRA-160"
    assert fm["rail"] == "INFRA"
    assert fm["flex_factor"] == 0.8


# ---------------------------------------------------------------------------
# _query_story_cost_samples waterfall (INFRA-171)
# ---------------------------------------------------------------------------


_MIN = 3  # matches _COST_MIN_SAMPLE in flex_build.py


def _make_db(tmp_path: Path) -> Path:
    """Create an effort.db with the minimal schema."""
    db_path = tmp_path / "effort.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            rail TEXT,
            story_class TEXT,
            outcome TEXT,
            tokens_total INTEGER,
            agent_role TEXT NOT NULL DEFAULT 'builder',
            attempt_number INTEGER NOT NULL DEFAULT 1,
            ts TEXT NOT NULL DEFAULT '2026-01-01T00:00:00+00:00'
        )
    """)
    conn.commit()
    conn.close()
    return db_path


def _insert(
    db_path: Path,
    rail: str,
    story_class: str,
    outcome: str,
    tokens: int,
    n: int = 1,
) -> None:
    conn = sqlite3.connect(str(db_path))
    for i in range(n):
        conn.execute(
            "INSERT INTO attempts (story_id, rail, story_class, outcome, tokens_total) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"{rail}-{i:03d}", rail, story_class, outcome, tokens),
        )
    conn.commit()
    conn.close()


def test_waterfall_tier1_rail_specific(tmp_path: Path) -> None:
    """Tier 1: ≥ _COST_MIN_SAMPLE PASS rows for (rail, story_class) → tier='rail'."""
    db_path = _make_db(tmp_path)
    _insert(db_path, "INFRA", "code", "PASS", 10000, n=_MIN)

    rows, tier = _query_story_cost_samples(db_path, "INFRA", "code")
    assert tier == "rail"
    assert len(rows) == _MIN


def test_waterfall_tier2_all_rails(tmp_path: Path) -> None:
    """Tier 2: Tier 1 insufficient; all-rails same class ≥ _MIN → tier='all-rails'."""
    db_path = _make_db(tmp_path)
    # Different rail, same story_class → satisfies tier 2 but not tier 1
    _insert(db_path, "BUILD", "code", "PASS", 20000, n=_MIN)

    rows, tier = _query_story_cost_samples(db_path, "INFRA", "code")
    assert tier == "all-rails"
    assert len(rows) == _MIN


def test_waterfall_tier3_global(tmp_path: Path) -> None:
    """Tier 3: Tiers 1 and 2 insufficient; global PASS rows ≥ _MIN → tier='global'."""
    db_path = _make_db(tmp_path)
    # Different story_class → tier 2 (all-rails/methodology) has 0 rows
    # but tier 3 (global) has _MIN rows
    _insert(db_path, "BUILD", "code", "PASS", 30000, n=_MIN)

    rows, tier = _query_story_cost_samples(db_path, "INFRA", "methodology")
    assert tier == "global"
    assert len(rows) == _MIN


def test_waterfall_tier4_insufficient(tmp_path: Path) -> None:
    """Tier 4: all tiers insufficient → tier='insufficient'."""
    db_path = _make_db(tmp_path)
    # Only _MIN - 1 global PASS rows → insufficient
    _insert(db_path, "BUILD", "code", "PASS", 40000, n=_MIN - 1)

    rows, tier = _query_story_cost_samples(db_path, "INFRA", "code")
    assert tier == "insufficient"
    assert len(rows) == _MIN - 1


def test_waterfall_no_db(tmp_path: Path) -> None:
    """Missing db_path → tier='insufficient', empty rows."""
    rows, tier = _query_story_cost_samples(tmp_path / "no-such.db", "INFRA", "code")
    assert tier == "insufficient"
    assert rows == []
