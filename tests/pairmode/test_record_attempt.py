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


# ---------------------------------------------------------------------------
# --story-file flag
# ---------------------------------------------------------------------------

_STORY_FRONTMATTER = """\
---
id: INFRA-051
rail: INFRA
phase: 25
story_class: methodology
title: test story
status: planned
primary_files:
  - skills/pairmode/scripts/record_attempt.py
touches:
  - CLAUDE.build.md
---

Story body here.
"""

_STORY_FRONTMATTER_NO_CLASS = """\
---
id: INFRA-052
rail: INFRA
phase: 25
title: test story no class
status: planned
primary_files:
  - skills/pairmode/scripts/record_attempt.py
touches: []
---

Story body here.
"""

_STORY_FRONTMATTER_NO_ID = """\
---
rail: INFRA
phase: 25
story_class: code
title: test story missing id
status: planned
primary_files: []
touches: []
---

Body.
"""


def _write_story(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestStoryFile:
    def test_populates_phase_rail_story_class_story_id(self, tmp_path: Path) -> None:
        """--story-file auto-fills phase, rail, story_class, story_id from frontmatter."""
        _enable_tracking(tmp_path)
        story_path = _write_story(tmp_path / "story.md", _STORY_FRONTMATTER)

        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--project-dir", str(tmp_path),
                "--story-file", str(story_path),
                "--agent-role", "builder",
                "--attempt-number", "1",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-051")
        assert len(rows) == 1
        row = rows[0]
        assert row["story_id"] == "INFRA-051"
        assert row["phase"] == "25"
        assert row["rail"] == "INFRA"
        assert row["story_class"] == "methodology"

    def test_explicit_flags_override_frontmatter(self, tmp_path: Path) -> None:
        """Explicit flags take precedence over auto-filled frontmatter values."""
        _enable_tracking(tmp_path)
        story_path = _write_story(tmp_path / "story.md", _STORY_FRONTMATTER)

        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--project-dir", str(tmp_path),
                "--story-file", str(story_path),
                "--story-id", "OVERRIDE-001",
                "--phase", "99",
                "--rail", "OVERRIDE",
                "--story-class", "doc",
                "--agent-role", "builder",
                "--attempt-number", "1",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "OVERRIDE-001")
        assert len(rows) == 1
        row = rows[0]
        assert row["story_id"] == "OVERRIDE-001"
        assert row["phase"] == "99"
        assert row["rail"] == "OVERRIDE"
        assert row["story_class"] == "doc"

    def test_missing_story_file_exits_nonzero(self, tmp_path: Path) -> None:
        """--story-file pointing to a nonexistent file exits non-zero."""
        _enable_tracking(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--project-dir", str(tmp_path),
                "--story-file", str(tmp_path / "does_not_exist.md"),
                "--agent-role", "builder",
                "--attempt-number", "1",
            ],
        )
        assert result.exit_code != 0

    def test_frontmatter_missing_id_exits_nonzero(self, tmp_path: Path) -> None:
        """Frontmatter without 'id' field (and no --story-id) exits non-zero."""
        _enable_tracking(tmp_path)
        story_path = _write_story(tmp_path / "story_no_id.md", _STORY_FRONTMATTER_NO_ID)

        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--project-dir", str(tmp_path),
                "--story-file", str(story_path),
                "--agent-role", "builder",
                "--attempt-number", "1",
            ],
        )
        assert result.exit_code != 0

    def test_no_story_class_field_defaults_to_code(self, tmp_path: Path) -> None:
        """When frontmatter has no story_class field, story_class defaults to 'code'."""
        _enable_tracking(tmp_path)
        story_path = _write_story(tmp_path / "story_no_class.md", _STORY_FRONTMATTER_NO_CLASS)

        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--project-dir", str(tmp_path),
                "--story-file", str(story_path),
                "--agent-role", "builder",
                "--attempt-number", "1",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-052")
        assert len(rows) == 1
        assert rows[0]["story_class"] == "code"


# ---------------------------------------------------------------------------
# Outcome normalisation
# ---------------------------------------------------------------------------


_STORY_FRONTMATTER_NORM = """\
---
id: {story_id}
phase: '38'
rail: INFRA
story_class: code
title: normalisation test story
status: planned
primary_files: []
touches: []
---

# Story
"""


def _make_project_norm(tmp_path: Path) -> Path:
    companion = tmp_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state = {
        "effort_tracking": True,
        "effort_db_path": ".companion/effort.db",
    }
    (companion / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return tmp_path


def _make_story_norm(project: Path, story_id: str) -> Path:
    story_dir = project / "docs" / "stories" / "INFRA"
    story_dir.mkdir(parents=True, exist_ok=True)
    story_file = story_dir / f"{story_id}.md"
    story_file.write_text(
        _STORY_FRONTMATTER_NORM.format(story_id=story_id),
        encoding="utf-8",
    )
    return story_file


def _fetch_outcome_norm(project: Path, story_id: str) -> str | None:
    db = project / ".companion" / "effort.db"
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT outcome FROM attempts WHERE story_id = ?", (story_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


class TestOutcomeNormalisation:
    def test_lowercase_pass_stored_as_uppercase(self, tmp_path: Path) -> None:
        project = _make_project_norm(tmp_path)
        story = _make_story_norm(project, "INFRA-001")
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--story-file", str(story),
                "--agent-role", "builder",
                "--outcome", "pass",
                "--project-dir", str(project),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert _fetch_outcome_norm(project, "INFRA-001") == "PASS"

    def test_uppercase_fail_unchanged(self, tmp_path: Path) -> None:
        project = _make_project_norm(tmp_path)
        story = _make_story_norm(project, "INFRA-002")
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--story-file", str(story),
                "--agent-role", "reviewer",
                "--outcome", "FAIL",
                "--project-dir", str(project),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert _fetch_outcome_norm(project, "INFRA-002") == "FAIL"

    def test_none_outcome_stored_as_null(self, tmp_path: Path) -> None:
        project = _make_project_norm(tmp_path)
        story = _make_story_norm(project, "INFRA-003")
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            [
                "--story-file", str(story),
                "--agent-role", "builder",
                "--project-dir", str(project),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert _fetch_outcome_norm(project, "INFRA-003") is None


# ---------------------------------------------------------------------------
# fail_cause → --notes contract (INFRA-236)
#
# subagent_transcript.record_attempt_from_transcript() parses the
# REVIEW-RESULT JSON's fail_cause field (worker_result.py) and passes it as
# --notes when calling effort_recorder.record_effort(), which shares the
# same underlying effort_db write path as this CLI's --notes flag. This
# class documents/pins that contract at the record_attempt.py layer: a
# reviewer FAIL's fail_cause text round-trips into effort.db's notes column
# exactly like any other --notes value.
# ---------------------------------------------------------------------------


class TestFailCauseContract:
    def test_fail_cause_text_round_trips_as_notes(self, tmp_path: Path) -> None:
        _enable_tracking(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path) + [
                "--agent-role", "reviewer",
                "--outcome", "FAIL",
                "--notes", "CRITICAL hook violation in hooks/pre_tool_use.py",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        row = rows[0]
        assert row["outcome"] == "FAIL"
        assert row["notes"] == "CRITICAL hook violation in hooks/pre_tool_use.py"

    def test_pass_outcome_has_no_notes_when_omitted(self, tmp_path: Path) -> None:
        """A PASS attempt (no fail_cause) must leave notes NULL, not empty string."""
        _enable_tracking(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path) + [
                "--agent-role", "builder",
                "--outcome", "PASS",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        assert rows[0]["notes"] is None


# ---------------------------------------------------------------------------
# --usage-block flag
# ---------------------------------------------------------------------------

_USAGE_BLOCK = """\
<usage>
<total_tokens>5000</total_tokens>
<input_tokens>4000</input_tokens>
<output_tokens>1000</output_tokens>
<cache_read_tokens>200</cache_read_tokens>
<cache_write_tokens>300</cache_write_tokens>
<tool_uses>5</tool_uses>
<duration_ms>12000</duration_ms>
</usage>
"""


class TestUsageBlock:
    def test_usage_block_from_string(self, tmp_path: Path) -> None:
        """Tokens written to DB match values parsed from <usage> block in file."""
        _enable_tracking(tmp_path)
        usage_file = tmp_path / "usage.xml"
        usage_file.write_text(_USAGE_BLOCK, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path) + ["--usage-block", str(usage_file)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        row = rows[0]
        assert row["tokens_total"] == 5000
        assert row["tokens_in"] == 4000
        assert row["tokens_out"] == 1000
        assert row["cache_read_tokens"] == 200
        assert row["cache_write_tokens"] == 300
        assert row["tool_uses"] == 5
        assert row["duration_ms"] == 12000

    def test_explicit_flag_overrides_usage_block(self, tmp_path: Path) -> None:
        """An explicit --tokens-total flag takes precedence over the parsed block value."""
        _enable_tracking(tmp_path)
        usage_file = tmp_path / "usage.xml"
        usage_file.write_text(_USAGE_BLOCK, encoding="utf-8")

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
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        # Explicit flag overrides the block value (5000)
        assert rows[0]["tokens_total"] == 999

    def test_usage_block_missing_graceful(self, tmp_path: Path) -> None:
        """File with no <usage> tags produces a warning but exits 0."""
        _enable_tracking(tmp_path)
        no_usage_file = tmp_path / "no_usage.txt"
        no_usage_file.write_text("nothing here\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            record_attempt,
            _required_args(tmp_path) + ["--usage-block", str(no_usage_file)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
