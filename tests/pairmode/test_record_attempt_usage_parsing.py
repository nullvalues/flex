"""Tests for ``record_attempt.py --usage-block`` pipeline integrity (INFRA-135).

Verifies that the ``<usage>`` block shape documented in ``CLAUDE.build.md``
Step 1 round-trips every field into the correct ``effort.db`` column.

Tests:
1. test_usage_block_full_round_trip — all documented fields present;
   assert each lands in the correct DB column.
2. test_usage_block_missing_optional_cache_fields_writes_null — omit
   cache_read_tokens and cache_write_tokens; assert those DB columns NULL.
3. test_explicit_flag_overrides_usage_block — fixture has total_tokens: 100;
   invoke with --tokens-total 999; assert DB row has tokens_total = 999.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts import effort_db
from skills.pairmode.scripts.record_attempt import record_attempt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_tracking(project_dir: Path) -> Path:
    state_path = project_dir / ".companion" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"effort_tracking": True}), encoding="utf-8")
    return state_path


def _required_args(project_dir: Path) -> list[str]:
    return [
        "--project-dir", str(project_dir),
        "--story-id", "INFRA-135",
        "--agent-role", "builder",
        "--attempt-number", "1",
    ]


def _fetch_row(db_path: Path, story_id: str = "INFRA-135") -> dict | None:
    rows = effort_db.query_by_story(db_path, story_id)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# The documented <usage> block shape from CLAUDE.build.md Step 1
# (XML tag format as parsed by record_attempt.py)
# ---------------------------------------------------------------------------

# Full block — all documented fields present.
_USAGE_BLOCK_FULL = """\
<usage>
<total_tokens>38000</total_tokens>
<input_tokens>30000</input_tokens>
<output_tokens>8000</output_tokens>
<cache_read_tokens>1500</cache_read_tokens>
<cache_write_tokens>2500</cache_write_tokens>
<tool_uses>11</tool_uses>
<duration_ms>187000</duration_ms>
</usage>
"""

# Block with cache fields omitted.
_USAGE_BLOCK_NO_CACHE = """\
<usage>
<total_tokens>20000</total_tokens>
<input_tokens>16000</input_tokens>
<output_tokens>4000</output_tokens>
<tool_uses>7</tool_uses>
<duration_ms>95000</duration_ms>
</usage>
"""

# Block where total_tokens is 100 — used for the override test.
_USAGE_BLOCK_TOTAL_100 = """\
<usage>
<total_tokens>100</total_tokens>
<input_tokens>80</input_tokens>
<output_tokens>20</output_tokens>
<cache_read_tokens>5</cache_read_tokens>
<cache_write_tokens>10</cache_write_tokens>
<tool_uses>2</tool_uses>
<duration_ms>3000</duration_ms>
</usage>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_usage_block_full_round_trip(tmp_path: Path) -> None:
    """All documented <usage> fields round-trip into the correct DB columns."""
    _enable_tracking(tmp_path)

    usage_file = tmp_path / "usage_full.xml"
    usage_file.write_text(_USAGE_BLOCK_FULL, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        record_attempt,
        _required_args(tmp_path) + ["--usage-block", str(usage_file)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    db_path = tmp_path / ".companion" / "effort.db"
    row = _fetch_row(db_path)
    assert row is not None, "Expected one row in effort.db"

    # Every documented field must land in the correct column.
    assert row["tokens_total"] == 38000, f"tokens_total={row['tokens_total']}"
    assert row["tokens_in"] == 30000, f"tokens_in={row['tokens_in']}"
    assert row["tokens_out"] == 8000, f"tokens_out={row['tokens_out']}"
    assert row["cache_read_tokens"] == 1500, f"cache_read_tokens={row['cache_read_tokens']}"
    assert row["cache_write_tokens"] == 2500, f"cache_write_tokens={row['cache_write_tokens']}"
    assert row["tool_uses"] == 11, f"tool_uses={row['tool_uses']}"
    assert row["duration_ms"] == 187000, f"duration_ms={row['duration_ms']}"


def test_usage_block_missing_optional_cache_fields_writes_null(tmp_path: Path) -> None:
    """Omitting cache_read_tokens/cache_write_tokens leaves those DB columns NULL."""
    _enable_tracking(tmp_path)

    usage_file = tmp_path / "usage_no_cache.xml"
    usage_file.write_text(_USAGE_BLOCK_NO_CACHE, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        record_attempt,
        _required_args(tmp_path) + ["--usage-block", str(usage_file)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    # Read the raw DB to confirm NULL (not 0) for the missing cache columns.
    db_path = tmp_path / ".companion" / "effort.db"
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT tokens_total, tokens_in, tokens_out, "
            "cache_read_tokens, cache_write_tokens, tool_uses, duration_ms "
            "FROM attempts WHERE story_id = 'INFRA-135'"
        )
        db_row = cur.fetchone()
    finally:
        conn.close()

    assert db_row is not None
    tokens_total, tokens_in, tokens_out, cache_read, cache_write, tool_uses, duration_ms = db_row

    assert tokens_total == 20000
    assert tokens_in == 16000
    assert tokens_out == 4000
    assert cache_read is None, f"Expected NULL for cache_read_tokens, got {cache_read}"
    assert cache_write is None, f"Expected NULL for cache_write_tokens, got {cache_write}"
    assert tool_uses == 7
    assert duration_ms == 95000


def test_explicit_flag_overrides_usage_block(tmp_path: Path) -> None:
    """--tokens-total 999 takes precedence over total_tokens: 100 in the <usage> block."""
    _enable_tracking(tmp_path)

    usage_file = tmp_path / "usage_100.xml"
    usage_file.write_text(_USAGE_BLOCK_TOTAL_100, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        record_attempt,
        _required_args(tmp_path) + [
            "--usage-block", str(usage_file),
            "--tokens-total", "999",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    db_path = tmp_path / ".companion" / "effort.db"
    row = _fetch_row(db_path)
    assert row is not None
    # Explicit flag (999) wins over the block value (100).
    assert row["tokens_total"] == 999, (
        f"Expected tokens_total=999 (explicit flag), got {row['tokens_total']}"
    )
    # Other fields from the usage block should still be applied.
    assert row["tokens_in"] == 80
    assert row["tokens_out"] == 20
    assert row["cache_read_tokens"] == 5
    assert row["cache_write_tokens"] == 10
    assert row["tool_uses"] == 2
    assert row["duration_ms"] == 3000
