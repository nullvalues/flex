"""Tests for skills/pairmode/scripts/effort_db.py."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from skills.pairmode.scripts import effort_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Standard ``.companion/effort.db`` location inside tmp_path."""

    return tmp_path / ".companion" / "effort.db"


def _required_fields(**overrides) -> dict:
    base = {
        "story_id": "INFRA-028",
        "agent_role": "builder",
        "attempt_number": 1,
        "ts": "2026-05-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_creates_attempts_table(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        assert db_path.exists()

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='attempts'"
            )
            assert cur.fetchone() is not None
        finally:
            conn.close()

    def test_creates_indices(self, db_path: Path) -> None:
        effort_db.init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='attempts'"
            )
            names = {row[0] for row in cur.fetchall()}
        finally:
            conn.close()

        assert "idx_attempts_story" in names
        assert "idx_attempts_phase" in names
        assert "idx_attempts_rail" in names

    def test_idempotent(self, db_path: Path) -> None:
        # Two consecutive init calls must not raise.
        effort_db.init_db(db_path)
        effort_db.init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM attempts")
            assert cur.fetchone()[0] == 0
        finally:
            conn.close()

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        # Parent dir does not exist yet — init_db must create it.
        nested = tmp_path / "deep" / "nested" / "effort.db"
        effort_db.init_db(nested)
        assert nested.exists()

    def test_depth_guard_rejects_shallow_paths(self) -> None:
        with pytest.raises(ValueError, match="too shallow"):
            effort_db.init_db(Path("/effort.db"))


# ---------------------------------------------------------------------------
# Insert / query roundtrip
# ---------------------------------------------------------------------------


class TestInsertAttempt:
    def test_roundtrip_minimal(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        rowid = effort_db.insert_attempt(db_path, **_required_fields())
        assert rowid >= 1

        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        row = rows[0]
        assert row["story_id"] == "INFRA-028"
        assert row["agent_role"] == "builder"
        assert row["attempt_number"] == 1
        assert row["ts"] == "2026-05-01T00:00:00+00:00"
        # Optional fields stay NULL.
        assert row["phase"] is None
        assert row["model"] is None
        assert row["tokens_total"] is None

    def test_roundtrip_full(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(
            db_path,
            **_required_fields(
                phase="22",
                rail="INFRA",
                model="claude-sonnet-4-6",
                tokens_total=12345,
                tokens_in=10000,
                tokens_out=2345,
                cache_read_tokens=500,
                cache_write_tokens=750,
                tool_uses=8,
                duration_ms=42000,
                outcome="PASS",
                notes="happy path",
            ),
        )

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

    def test_initialises_db_on_demand(self, db_path: Path) -> None:
        # Caller forgot to init — insert should still work.
        assert not db_path.exists()
        effort_db.insert_attempt(db_path, **_required_fields())
        assert db_path.exists()
        assert len(effort_db.query_by_story(db_path, "INFRA-028")) == 1

    @pytest.mark.parametrize(
        "field",
        ["story_id", "agent_role", "attempt_number", "ts"],
    )
    def test_missing_required_field_raises(self, db_path: Path, field: str) -> None:
        effort_db.init_db(db_path)
        fields = _required_fields()
        fields.pop(field)
        with pytest.raises(ValueError, match=field):
            effort_db.insert_attempt(db_path, **fields)

    def test_unknown_field_raises(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        with pytest.raises(ValueError, match="unknown"):
            effort_db.insert_attempt(
                db_path,
                **_required_fields(),
                bogus_column="oops",
            )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


class TestQuery:
    def test_query_by_story_filters_results(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-028"))
        effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-029"))
        effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-028", attempt_number=2))

        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert [r["attempt_number"] for r in rows] == [1, 2]

        other = effort_db.query_by_story(db_path, "INFRA-029")
        assert len(other) == 1

    def test_query_by_phase_filters_results(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(db_path, **_required_fields(phase="22"))
        effort_db.insert_attempt(db_path, **_required_fields(phase="21"))
        effort_db.insert_attempt(db_path, **_required_fields(phase="22", attempt_number=2))

        rows = effort_db.query_by_phase(db_path, "22")
        assert len(rows) == 2

    def test_query_returns_empty_when_db_missing(self, tmp_path: Path) -> None:
        # No init, no inserts — query should not raise.
        ghost = tmp_path / ".companion" / "effort.db"
        assert effort_db.query_by_story(ghost, "INFRA-028") == []
        assert effort_db.query_by_phase(ghost, "22") == []
        assert effort_db.query_all(ghost) == []


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestResolvePath:
    def test_default_path(self, tmp_path: Path) -> None:
        resolved = effort_db.resolve_effort_db_path(tmp_path)
        assert resolved == tmp_path / ".companion" / "effort.db"

    def test_state_json_override_relative(self, tmp_path: Path) -> None:
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"effort_db_path": "custom/effort.db"}),
            encoding="utf-8",
        )
        resolved = effort_db.resolve_effort_db_path(tmp_path)
        assert resolved == tmp_path / "custom" / "effort.db"

    def test_state_json_override_absolute(self, tmp_path: Path) -> None:
        target = tmp_path / "elsewhere" / "effort.db"
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"effort_db_path": str(target)}),
            encoding="utf-8",
        )
        resolved = effort_db.resolve_effort_db_path(tmp_path)
        assert resolved == target

    def test_state_json_invalid_falls_back_to_default(self, tmp_path: Path) -> None:
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("not json", encoding="utf-8")
        resolved = effort_db.resolve_effort_db_path(tmp_path)
        assert resolved == tmp_path / ".companion" / "effort.db"

    def test_path_within_project_dir_is_accepted(self, tmp_path: Path) -> None:
        """A configured path inside project_dir is returned as-is."""
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"effort_db_path": "custom/effort.db"}),
            encoding="utf-8",
        )
        resolved = effort_db.resolve_effort_db_path(tmp_path)
        assert resolved == (tmp_path / "custom" / "effort.db").resolve()
        # Must be inside project_dir
        resolved.relative_to(tmp_path.resolve())  # raises if outside

    def test_path_escaping_project_dir_falls_back_to_default(self, tmp_path: Path) -> None:
        """A configured path that escapes project_dir falls back to the default."""
        state_path = tmp_path / ".companion" / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"effort_db_path": "../../etc/passwd"}),
            encoding="utf-8",
        )
        resolved = effort_db.resolve_effort_db_path(tmp_path)
        assert resolved == tmp_path / ".companion" / "effort.db"


# ---------------------------------------------------------------------------
# Migration idempotency (INFRA-050)
# ---------------------------------------------------------------------------


class TestMigrationIdempotency:
    def test_double_init_does_not_raise(self, db_path: Path) -> None:
        """Running init_db twice on the same DB must not raise."""
        effort_db.init_db(db_path)
        effort_db.init_db(db_path)  # second call — migrations already applied

    def test_columns_present_after_single_init(self, db_path: Path) -> None:
        """story_class and model_selection_reason columns exist after init."""
        effort_db.init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(attempts)")
            col_names = {row[1] for row in cur.fetchall()}
        finally:
            conn.close()
        assert "story_class" in col_names
        assert "model_selection_reason" in col_names

    def test_columns_present_after_double_init(self, db_path: Path) -> None:
        """Columns still present (and no error) after two init calls."""
        effort_db.init_db(db_path)
        effort_db.init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(attempts)")
            col_names = {row[1] for row in cur.fetchall()}
        finally:
            conn.close()
        assert "story_class" in col_names
        assert "model_selection_reason" in col_names

    def test_migration_on_pre_existing_db_without_new_columns(self, db_path: Path) -> None:
        """Simulate a pre-INFRA-050 DB that lacks the new columns; init adds them."""
        # Create DB with the old schema (without the new columns).
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT NOT NULL,
                    phase TEXT,
                    rail TEXT,
                    agent_role TEXT NOT NULL,
                    model TEXT,
                    attempt_number INTEGER NOT NULL,
                    tokens_total INTEGER,
                    ts TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        # Running init_db must add the columns without raising.
        effort_db.init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(attempts)")
            col_names = {row[1] for row in cur.fetchall()}
        finally:
            conn.close()
        assert "story_class" in col_names
        assert "model_selection_reason" in col_names


# ---------------------------------------------------------------------------
# Round-trip: story_class and model_selection_reason via insert_attempt
# ---------------------------------------------------------------------------


class TestStoryClassAndReasonRoundtrip:
    def test_insert_and_read_story_class(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(
            db_path,
            **_required_fields(story_class="code"),
        )
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        assert rows[0]["story_class"] == "code"

    def test_insert_and_read_model_selection_reason(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(
            db_path,
            **_required_fields(model_selection_reason="auto-baseline"),
        )
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert rows[0]["model_selection_reason"] == "auto-baseline"

    def test_insert_and_read_both_new_fields(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(
            db_path,
            **_required_fields(
                story_class="doc",
                model_selection_reason="auto-downgrade",
            ),
        )
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert rows[0]["story_class"] == "doc"
        assert rows[0]["model_selection_reason"] == "auto-downgrade"

    def test_new_fields_default_to_none(self, db_path: Path) -> None:
        """Rows inserted without the new fields have NULL for both."""
        effort_db.init_db(db_path)
        effort_db.insert_attempt(db_path, **_required_fields())
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert rows[0]["story_class"] is None
        assert rows[0]["model_selection_reason"] is None

    def test_record_attempt_cli_writes_new_fields(self, tmp_path: Path) -> None:
        """record_attempt.py CLI round-trip for story_class and model_selection_reason."""
        # Set up minimal project layout
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir(parents=True)
        state_file = companion_dir / "state.json"
        state_file.write_text(
            json.dumps({"effort_tracking": True}), encoding="utf-8"
        )

        record_attempt_script = str(
            Path(__file__).parent.parent.parent
            / "skills"
            / "pairmode"
            / "scripts"
            / "record_attempt.py"
        )

        # Invoke via the same Python interpreter running the tests so that
        # the repo is on sys.path and the click CLI is importable.
        result = subprocess.run(
            [
                sys.executable,
                record_attempt_script,
                "--story-id",
                "INFRA-050",
                "--agent-role",
                "builder",
                "--attempt-number",
                "1",
                "--ts",
                "2026-05-06T00:00:00+00:00",
                "--story-class",
                "code",
                "--model-selection-reason",
                "prompted-upgrade",
                "--project-dir",
                str(tmp_path),
            ],
            check=True,
            capture_output=True,
            env={
                **__import__("os").environ,
                "PYTHONPATH": str(Path(__file__).parent.parent.parent),
            },
        )

        db_path = tmp_path / ".companion" / "effort.db"
        rows = effort_db.query_by_story(db_path, "INFRA-050")
        assert len(rows) == 1
        assert rows[0]["story_class"] == "code"
        assert rows[0]["model_selection_reason"] == "prompted-upgrade"


# ---------------------------------------------------------------------------
# Backend column tests (INFRA-123)
# ---------------------------------------------------------------------------


class TestBackendColumn:
    def test_backend_column_stored(self, db_path: Path) -> None:
        """Insert a row with backend='ollama'; assert it is stored and readable."""
        effort_db.init_db(db_path)
        effort_db.insert_attempt(
            db_path,
            **_required_fields(backend="ollama"),
        )
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        assert rows[0]["backend"] == "ollama"

    def test_backend_column_nullable(self, db_path: Path) -> None:
        """Insert a row without backend; assert no error and row is stored."""
        effort_db.init_db(db_path)
        effort_db.insert_attempt(db_path, **_required_fields())
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert len(rows) == 1
        assert rows[0]["backend"] is None


# ---------------------------------------------------------------------------
# CLI: guardrail-check subcommand (INFRA-118)
# ---------------------------------------------------------------------------


def _run_effort_db_cli(argv: list[str], mock_result: dict) -> tuple[int, str]:
    """Invoke effort_db._cli_main() in-process with a mocked check_guardrail.

    Returns (exit_code, stdout_text).
    """
    import io

    captured_stdout = io.StringIO()

    with patch(
        "skills.pairmode.scripts.effort_db.check_guardrail",
        return_value=mock_result,
    ), patch("sys.stdout", captured_stdout):
        exit_code = effort_db._cli_main(argv)

    return exit_code, captured_stdout.getvalue()


class TestNextAttemptNumber:
    """Tests for effort_db.next_attempt_number (INFRA-257)."""

    def test_empty_db_returns_one(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        assert effort_db.next_attempt_number(db_path, "INFRA-028", "builder") == 1

    def test_absent_db_returns_one(self, db_path: Path) -> None:
        assert not db_path.exists()
        assert effort_db.next_attempt_number(db_path, "INFRA-028", "builder") == 1

    def test_n_existing_rows_yields_n_plus_one(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        for i in range(3):
            effort_db.insert_attempt(
                db_path,
                **_required_fields(attempt_number=i + 1, ts=f"2026-05-01T0{i}:00:00+00:00"),
            )
        assert effort_db.next_attempt_number(db_path, "INFRA-028", "builder") == 4

    def test_different_agent_role_does_not_increment(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(db_path, **_required_fields(agent_role="builder"))
        assert effort_db.next_attempt_number(db_path, "INFRA-028", "reviewer") == 1

    def test_different_story_id_does_not_increment(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-028"))
        assert effort_db.next_attempt_number(db_path, "INFRA-029", "builder") == 1

    def test_corrupt_file_returns_one_no_exception(self, tmp_path: Path) -> None:
        corrupt_path = tmp_path / ".companion" / "effort.db"
        corrupt_path.parent.mkdir(parents=True, exist_ok=True)
        corrupt_path.write_text("this is not a sqlite file", encoding="utf-8")
        assert effort_db.next_attempt_number(corrupt_path, "INFRA-028", "builder") == 1

    def test_empty_story_id_returns_one(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        assert effort_db.next_attempt_number(db_path, "", "builder") == 1

    def test_empty_agent_role_returns_one(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        assert effort_db.next_attempt_number(db_path, "INFRA-028", "") == 1


# ---------------------------------------------------------------------------
# Spawn-ref columns and reconciliation helpers (INFRA-258)
# ---------------------------------------------------------------------------


class TestSpawnRefColumns:
    """agent_id / output_file schema (Ensures 1)."""

    def test_columns_present_after_init(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(attempts)")
            col_names = {row[1] for row in cur.fetchall()}
        finally:
            conn.close()
        assert "agent_id" in col_names
        assert "output_file" in col_names

    def test_migration_on_pre_existing_db_without_new_columns(self, db_path: Path) -> None:
        """Pre-INFRA-258 DB lacking the new columns; init adds them without raising."""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT NOT NULL,
                    phase TEXT,
                    rail TEXT,
                    agent_role TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    tokens_total INTEGER,
                    ts TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        effort_db.init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(attempts)")
            col_names = {row[1] for row in cur.fetchall()}
        finally:
            conn.close()
        assert "agent_id" in col_names
        assert "output_file" in col_names

    def test_double_init_is_noop_on_already_migrated_db(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.init_db(db_path)  # must not raise

    def test_insert_columns_not_extended(self, db_path: Path) -> None:
        """INFRA-288 (A1) supersedes INFRA-258 Ensures 2: agent_id/output_file
        are now insertable columns (accepted as kwargs, default NULL), while
        the required-field set is untouched and a truly unknown field still
        raises."""
        effort_db.init_db(db_path)
        assert "agent_id" in effort_db._INSERT_COLUMNS
        assert "output_file" in effort_db._INSERT_COLUMNS
        assert "agent_id" not in effort_db._REQUIRED_FIELDS
        assert "output_file" not in effort_db._REQUIRED_FIELDS
        assert "agent_id" not in effort_db._DERIVED_REQUIRED_FIELDS
        assert "output_file" not in effort_db._DERIVED_REQUIRED_FIELDS
        row_id = effort_db.insert_attempt(
            db_path, **_required_fields(), agent_id="a1", output_file="/tmp/x"
        )
        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert rows[0]["id"] == row_id
        assert rows[0]["agent_id"] == "a1"
        assert rows[0]["output_file"] == "/tmp/x"
        with pytest.raises(ValueError, match="unknown"):
            effort_db.insert_attempt(
                db_path, **_required_fields(), not_a_column="x"
            )


class TestSetSpawnRef:
    def test_sets_both_columns(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(db_path, **_required_fields())
        assert effort_db.set_spawn_ref(db_path, row_id, "agent-1", "/tmp/out.jsonl") is True

        rows = effort_db.query_by_story(db_path, "INFRA-028")
        assert rows[0]["agent_id"] == "agent-1"
        assert rows[0]["output_file"] == "/tmp/out.jsonl"

    def test_missing_db_returns_false(self, tmp_path: Path) -> None:
        ghost = tmp_path / ".companion" / "effort.db"
        assert effort_db.set_spawn_ref(ghost, 1, "a", "/tmp/x") is False

    def test_missing_row_returns_false(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        assert effort_db.set_spawn_ref(db_path, 999, "a", "/tmp/x") is False

    def test_never_raises_on_corrupt_file(self, tmp_path: Path) -> None:
        corrupt_path = tmp_path / ".companion" / "effort.db"
        corrupt_path.parent.mkdir(parents=True, exist_ok=True)
        corrupt_path.write_text("not a sqlite file", encoding="utf-8")
        assert effort_db.set_spawn_ref(corrupt_path, 1, "a", "/tmp/x") is False


class TestPendingReconcilable:
    def test_returns_rows_with_null_tokens_and_output_file(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        row_1 = effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-100"))
        effort_db.set_spawn_ref(db_path, row_1, "a1", "/tmp/out1.jsonl")
        # A completed row (tokens_total set) must NOT show up as pending.
        effort_db.insert_attempt(
            db_path, **_required_fields(story_id="INFRA-101", tokens_total=100)
        )

        rows = effort_db.pending_reconcilable(db_path, 10)
        assert len(rows) == 1
        assert rows[0]["id"] == row_1
        assert rows[0]["story_id"] == "INFRA-100"
        assert rows[0]["output_file"] == "/tmp/out1.jsonl"

    def test_excludes_rows_without_output_file(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt(db_path, **_required_fields())
        assert effort_db.pending_reconcilable(db_path, 10) == []

    def test_ordered_by_id_descending(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        for i in range(3):
            row_id = effort_db.insert_attempt(
                db_path, **_required_fields(story_id=f"INFRA-{200+i}")
            )
            effort_db.set_spawn_ref(db_path, row_id, f"a{i}", f"/tmp/out{i}.jsonl")

        rows = effort_db.pending_reconcilable(db_path, 10)
        ids = [r["id"] for r in rows]
        assert ids == sorted(ids, reverse=True)

    def test_capped_by_limit(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        for i in range(5):
            row_id = effort_db.insert_attempt(
                db_path, **_required_fields(story_id=f"INFRA-{300+i}")
            )
            effort_db.set_spawn_ref(db_path, row_id, f"a{i}", f"/tmp/out{i}.jsonl")

        rows = effort_db.pending_reconcilable(db_path, 2)
        assert len(rows) == 2

    def test_missing_db_returns_empty_list(self, tmp_path: Path) -> None:
        ghost = tmp_path / ".companion" / "effort.db"
        assert effort_db.pending_reconcilable(ghost, 5) == []

    def test_never_raises_on_corrupt_file(self, tmp_path: Path) -> None:
        corrupt_path = tmp_path / ".companion" / "effort.db"
        corrupt_path.parent.mkdir(parents=True, exist_ok=True)
        corrupt_path.write_text("not a sqlite file", encoding="utf-8")
        assert effort_db.pending_reconcilable(corrupt_path, 5) == []

    def test_returns_tokens_set_outcome_null_row_the_row_344_shape(
        self, db_path: Path
    ) -> None:
        """CER-091 defect 2/3: a row with tokens_total set but outcome still
        NULL (row 344's shape) must be returned so it is reachable again."""
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path, **_required_fields(story_id="INFRA-344", tokens_total=6597)
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", "/tmp/out-344.jsonl")

        rows = effort_db.pending_reconcilable(db_path, 10)
        assert len(rows) == 1
        assert rows[0]["id"] == row_id
        assert rows[0]["tokens_total"] == 6597
        assert rows[0]["outcome"] is None

    def test_omits_fully_reconciled_row(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path,
            **_required_fields(
                story_id="INFRA-345", tokens_total=100, outcome="PASS"
            ),
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", "/tmp/out-345.jsonl")

        assert effort_db.pending_reconcilable(db_path, 10) == []


class TestReconcileAttempt:
    def test_updates_reconcilable_columns_only(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(db_path, **_required_fields())
        effort_db.set_spawn_ref(db_path, row_id, "a1", "/tmp/out.jsonl")

        updated = effort_db.reconcile_attempt(
            db_path,
            row_id,
            tokens_total=1500,
            tokens_in=1000,
            tokens_out=500,
            cache_read_tokens=10,
            cache_write_tokens=20,
            duration_ms=4200,
            outcome="PASS",
            notes=None,
            model="claude-sonnet-5",
        )
        assert updated is True

        rows = effort_db.query_by_story(db_path, "INFRA-028")
        row = rows[0]
        assert row["tokens_total"] == 1500
        assert row["tokens_in"] == 1000
        assert row["tokens_out"] == 500
        assert row["cache_read_tokens"] == 10
        assert row["cache_write_tokens"] == 20
        assert row["duration_ms"] == 4200
        assert row["outcome"] == "PASS"
        assert row["model"] == "claude-sonnet-5"

    def test_never_writes_story_id_agent_role_attempt_number_or_ts(self, db_path: Path) -> None:
        """Ensures 5: attempt_number and ts must be byte-identical before/after."""
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path, **_required_fields(attempt_number=3, ts="2026-05-01T00:00:00+00:00")
        )
        before = effort_db.query_by_story(db_path, "INFRA-028")[0]

        effort_db.reconcile_attempt(
            db_path,
            row_id,
            tokens_total=100,
            outcome="PASS",
            story_id="INFRA-999",
            agent_role="reviewer",
            attempt_number=99,
            ts="2099-01-01T00:00:00+00:00",
        )

        after = effort_db.query_by_story(db_path, "INFRA-999")
        assert after == []  # story_id write attempt was ignored
        after_row = effort_db.query_by_story(db_path, "INFRA-028")[0]
        assert after_row["attempt_number"] == before["attempt_number"] == 3
        assert after_row["ts"] == before["ts"] == "2026-05-01T00:00:00+00:00"
        assert after_row["agent_role"] == "builder"
        assert after_row["tokens_total"] == 100

    def test_single_shot_second_call_is_noop(self, db_path: Path) -> None:
        """Ensures 5: a second reconciliation call for an already-reconciled
        row is a no-op returning False."""
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(db_path, **_required_fields())

        assert effort_db.reconcile_attempt(db_path, row_id, tokens_total=100, outcome="PASS") is True
        assert effort_db.reconcile_attempt(db_path, row_id, tokens_total=200, outcome="FAIL") is False

        row = effort_db.query_by_story(db_path, "INFRA-028")[0]
        assert row["tokens_total"] == 100  # unchanged by the second call

    def test_missing_row_returns_false(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        assert effort_db.reconcile_attempt(db_path, 999, tokens_total=100) is False

    def test_never_raises_on_corrupt_file(self, tmp_path: Path) -> None:
        corrupt_path = tmp_path / ".companion" / "effort.db"
        corrupt_path.parent.mkdir(parents=True, exist_ok=True)
        corrupt_path.write_text("not a sqlite file", encoding="utf-8")
        assert effort_db.reconcile_attempt(corrupt_path, 1, tokens_total=100) is False


class TestReconcileAttemptAtomic:
    """CER-091 defect 2: reconcile_attempt is atomic over tokens *and*
    outcome — writing tokens_total alone (the row-344 shape) must not
    commit, and the row must be repairable once outcome is later known."""

    def test_tokens_without_outcome_returns_false_and_leaves_row_unchanged(
        self, db_path: Path
    ) -> None:
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(db_path, **_required_fields())
        before = effort_db.query_by_story(db_path, "INFRA-028")[0]

        result = effort_db.reconcile_attempt(db_path, row_id, tokens_total=6597)
        assert result is False

        after = effort_db.query_by_story(db_path, "INFRA-028")[0]
        assert after == before
        assert after["tokens_total"] is None
        assert after["outcome"] is None

    def test_tokens_and_outcome_together_returns_true(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(db_path, **_required_fields())

        result = effort_db.reconcile_attempt(
            db_path, row_id, tokens_total=6597, outcome="ALIGNED"
        )
        assert result is True

        row = effort_db.query_by_story(db_path, "INFRA-028")[0]
        assert row["tokens_total"] == 6597
        assert row["outcome"] == "ALIGNED"

    def test_outcome_none_value_also_blocks_the_write(self, db_path: Path) -> None:
        """Presence of the key with a None value must not satisfy the
        atomic-pair requirement."""
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(db_path, **_required_fields())

        result = effort_db.reconcile_attempt(
            db_path, row_id, tokens_total=100, outcome=None
        )
        assert result is False
        row = effort_db.query_by_story(db_path, "INFRA-028")[0]
        assert row["tokens_total"] is None

    def test_partial_row_is_repairable_by_a_later_call(self, db_path: Path) -> None:
        """A row that already has tokens_total set (written before the
        atomic guard existed, or via a direct test seed) but outcome NULL
        must still be completable by a later call carrying both fields."""
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path, **_required_fields(tokens_total=6597)
        )

        # A repeat attempt to write tokens alone still cannot commit...
        assert effort_db.reconcile_attempt(db_path, row_id, tokens_total=7000) is False

        # ...but supplying the still-missing outcome alongside tokens does.
        assert (
            effort_db.reconcile_attempt(
                db_path, row_id, tokens_total=6597, outcome="ALIGNED"
            )
            is True
        )
        row = effort_db.query_by_story(db_path, "INFRA-028")[0]
        assert row["outcome"] == "ALIGNED"

        # Now fully reconciled — a further call is single-shot and a no-op.
        assert (
            effort_db.reconcile_attempt(
                db_path, row_id, tokens_total=1, outcome="PASS"
            )
            is False
        )


class TestGuardrailCheckCLI:
    def test_guardrail_check_cli_no_warning(self, tmp_path: Path) -> None:
        """No output and exit 0 when guardrail has not fired."""
        exit_code, stdout = _run_effort_db_cli(
            [
                "guardrail-check",
                "--story-id", "INFRA-118",
                "--rail", "INFRA",
                "--tokens", "5000",
                "--project-dir", str(tmp_path),
            ],
            mock_result={"fired": False, "message": ""},
        )
        assert exit_code == 0
        assert stdout == ""

    def test_guardrail_check_cli_with_warning(self, tmp_path: Path) -> None:
        """Warning message is printed and exit 0 when guardrail has fired."""
        warning_message = "effort guardrail: story exceeded 3x median"
        exit_code, stdout = _run_effort_db_cli(
            [
                "guardrail-check",
                "--story-id", "INFRA-118",
                "--rail", "INFRA",
                "--tokens", "99999",
                "--project-dir", str(tmp_path),
            ],
            mock_result={"fired": True, "message": warning_message},
        )
        assert exit_code == 0
        assert warning_message in stdout


# ---------------------------------------------------------------------------
# CER-088: idx_attempts_pending partial index, created post-migration
# ---------------------------------------------------------------------------


class TestPendingIndex:
    def test_idx_attempts_pending_exists_after_init(self, db_path: Path) -> None:
        """A1: the partial index exists after init_db on a fresh database."""
        effort_db.init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_attempts_pending'"
            )
            assert cur.fetchone() is not None
        finally:
            conn.close()

    def test_schema_indices_unchanged_at_three(self) -> None:
        """A2: _SCHEMA_INDICES still contains exactly its original three
        story_id/phase/rail statements — the new index is not among them."""
        assert len(effort_db._SCHEMA_INDICES) == 3
        joined = " ".join(effort_db._SCHEMA_INDICES)
        assert "idx_attempts_story" in joined
        assert "idx_attempts_phase" in joined
        assert "idx_attempts_rail" in joined
        assert "idx_attempts_pending" not in joined

    def test_pending_index_created_on_pre_infra_258_shaped_db(
        self, db_path: Path
    ) -> None:
        """A2: init_db on a table with no output_file/agent_id column must
        not raise, must add both columns, and must create the new index."""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                CREATE TABLE attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT NOT NULL,
                    phase TEXT,
                    rail TEXT,
                    agent_role TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    tokens_total INTEGER,
                    outcome TEXT,
                    ts TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        effort_db.init_db(db_path)  # must not raise

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(attempts)")
            col_names = {row[1] for row in cur.fetchall()}
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_attempts_pending'"
            )
            index_row = cur.fetchone()
        finally:
            conn.close()

        assert "agent_id" in col_names
        assert "output_file" in col_names
        assert index_row is not None

    def test_query_plan_uses_index_both_variants(self, db_path: Path) -> None:
        """A3: EXPLAIN QUERY PLAN for pending_reconcilable's statement (with
        and without the age cutoff) names idx_attempts_pending."""
        effort_db.init_db(db_path)
        row_1 = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-500",
            agent_role="builder",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
        )
        effort_db.set_spawn_ref(db_path, row_1, "a1", "/tmp/tasks/out1.output")
        effort_db.insert_attempt(
            db_path,
            story_id="INFRA-501",
            agent_role="builder",
            attempt_number=1,
            ts="2026-05-01T00:00:00+00:00",
            tokens_total=100,
            outcome="PASS",
        )

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT * FROM attempts
                 WHERE (tokens_total IS NULL OR outcome IS NULL)
                   AND output_file IS NOT NULL
                 ORDER BY id DESC
                 LIMIT ?
                """,
                (10,),
            )
            plan_no_cutoff = " ".join(str(r) for r in cur.fetchall())

            cur.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT * FROM attempts
                 WHERE (tokens_total IS NULL OR outcome IS NULL)
                   AND output_file IS NOT NULL
                   AND ts >= ?
                 ORDER BY id DESC
                 LIMIT ?
                """,
                ("2000-01-01T00:00:00+00:00", 10),
            )
            plan_with_cutoff = " ".join(str(r) for r in cur.fetchall())
        finally:
            conn.close()

        assert "idx_attempts_pending" in plan_no_cutoff
        assert "idx_attempts_pending" in plan_with_cutoff


class TestPendingReconcilableAgeCutoff:
    def test_default_returns_two_year_old_pending_row(self, db_path: Path) -> None:
        """A4: max_age_days=None (default) preserves today's behaviour — an
        ancient pending row is still returned."""
        effort_db.init_db(db_path)
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=730)
        ).isoformat()
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-510",
            agent_role="builder",
            attempt_number=1,
            ts=old_ts,
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", "/tmp/tasks/out.output")

        rows = effort_db.pending_reconcilable(db_path, 10)
        assert [r["id"] for r in rows] == [row_id]

    def test_max_age_days_excludes_old_row_keeps_recent(self, db_path: Path) -> None:
        """A4: max_age_days=14 excludes the two-year-old row but keeps a
        pending row stamped 'now'."""
        effort_db.init_db(db_path)
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=730)
        ).isoformat()
        old_row = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-511",
            agent_role="builder",
            attempt_number=1,
            ts=old_ts,
        )
        effort_db.set_spawn_ref(db_path, old_row, "a1", "/tmp/tasks/old.output")

        recent_ts = datetime.now(timezone.utc).isoformat()
        recent_row = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-512",
            agent_role="builder",
            attempt_number=1,
            ts=recent_ts,
        )
        effort_db.set_spawn_ref(db_path, recent_row, "a2", "/tmp/tasks/recent.output")

        rows = effort_db.pending_reconcilable(db_path, 10, max_age_days=14)
        assert [r["id"] for r in rows] == [recent_row]

    def test_cutoff_is_bound_parameter_not_interpolated(self, db_path: Path) -> None:
        """A4: a story_id containing SQL-meaningful characters must not
        break the cutoff-bearing query — proof the cutoff is parameterised."""
        effort_db.init_db(db_path)
        recent_ts = datetime.now(timezone.utc).isoformat()
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-513'; DROP TABLE attempts; --",
            agent_role="builder",
            attempt_number=1,
            ts=recent_ts,
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", "/tmp/tasks/x.output")

        rows = effort_db.pending_reconcilable(db_path, 10, max_age_days=14)
        assert [r["id"] for r in rows] == [row_id]

    @pytest.mark.parametrize("bad_value", [0, -1, "14", False])
    def test_non_positive_or_non_int_treated_as_no_cutoff(
        self, db_path: Path, bad_value
    ) -> None:
        """A5: 0, negative, string, and bool values are all "no cutoff",
        never an error — identical rows to max_age_days=None."""
        effort_db.init_db(db_path)
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=730)
        ).isoformat()
        row_id = effort_db.insert_attempt(
            db_path,
            story_id="INFRA-514",
            agent_role="builder",
            attempt_number=1,
            ts=old_ts,
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", "/tmp/tasks/y.output")

        rows = effort_db.pending_reconcilable(db_path, 10, max_age_days=bad_value)
        assert [r["id"] for r in rows] == [row_id]

    def test_never_raises_with_cutoff_on_corrupt_file(self, tmp_path: Path) -> None:
        corrupt_path = tmp_path / ".companion" / "effort.db"
        corrupt_path.parent.mkdir(parents=True, exist_ok=True)
        corrupt_path.write_text("not a sqlite file", encoding="utf-8")
        assert effort_db.pending_reconcilable(corrupt_path, 5, max_age_days=14) == []


# ---------------------------------------------------------------------------
# CER-016: single-sourced --db-path containment (resolve_db_path_arg)
# ---------------------------------------------------------------------------


class TestResolveDbPathArg:
    def test_none_returns_default(self, tmp_path: Path) -> None:
        """C5: None delegates unchanged to resolve_effort_db_path."""
        resolved = effort_db.resolve_db_path_arg(tmp_path, None)
        assert resolved == tmp_path / ".companion" / "effort.db"

    def test_relative_path_inside_project_is_accepted_and_absolute(
        self, tmp_path: Path
    ) -> None:
        resolved = effort_db.resolve_db_path_arg(tmp_path, "custom/effort.db")
        assert resolved.is_absolute()
        assert resolved == (tmp_path / "custom" / "effort.db").resolve()

    def test_absolute_path_outside_project_dir_raises(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.db"
        with pytest.raises(ValueError):
            effort_db.resolve_db_path_arg(tmp_path, outside)

    def test_relative_escape_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            effort_db.resolve_db_path_arg(tmp_path, "../../escape.db")

    def test_symlink_inside_project_pointing_outside_raises(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir(parents=True, exist_ok=True)

        link = project_dir / "escape_link.db"
        os.symlink(outside_dir / "effort.db", link)

        with pytest.raises(ValueError):
            effort_db.resolve_db_path_arg(project_dir, "escape_link.db")

    def test_shallow_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            effort_db.resolve_db_path_arg(tmp_path, "/x")

    def test_existing_resolve_effort_db_path_tests_still_pass_state_json_default(
        self, tmp_path: Path
    ) -> None:
        """C5: resolve_effort_db_path's own behaviour is untouched by this
        story — sanity check alongside the new resolver's tests."""
        resolved = effort_db.resolve_effort_db_path(tmp_path)
        assert resolved == tmp_path / ".companion" / "effort.db"


# ---------------------------------------------------------------------------
# CER-096, item A: WAL + busy_timeout concurrency configuration
# ---------------------------------------------------------------------------


class TestConnectConcurrencyConstants:
    def test_busy_timeout_ms_matches_seconds(self) -> None:
        """A1: the two constants must never drift apart."""
        assert effort_db.BUSY_TIMEOUT_MS == int(effort_db.BUSY_TIMEOUT_SECONDS * 1000)

    def test_only_one_sqlite3_connect_call_site(self) -> None:
        """A2: every connection in effort_db.py goes through _connect."""
        import subprocess as _subprocess

        module_path = Path(effort_db.__file__)
        out = _subprocess.run(
            ["grep", "-c", "sqlite3.connect", str(module_path)],
            capture_output=True,
            text=True,
        )
        assert out.stdout.strip() == "1"


class TestWalMode:
    def test_wal_enabled_and_persists(self, db_path: Path) -> None:
        """A3: WAL is a persisted database property, not per-connection."""
        effort_db.init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
        finally:
            conn.close()
        assert mode == "wal"

    def test_wal_failure_is_not_fatal(self, db_path: Path, monkeypatch) -> None:
        """A4: a WAL-pragma failure must not prevent schema creation."""
        real_connect = sqlite3.connect

        class _FailingWalConn:
            def __init__(self, real_conn):
                self._real = real_conn

            def execute(self, sql, *args, **kwargs):
                if "journal_mode" in sql:
                    raise sqlite3.OperationalError("cannot enable WAL")
                return self._real.execute(sql, *args, **kwargs)

            def __getattr__(self, item):
                return getattr(self._real, item)

        def _connect(*args, **kwargs):
            return _FailingWalConn(real_connect(*args, **kwargs))

        monkeypatch.setattr(sqlite3, "connect", _connect)

        effort_db.init_db(db_path)  # must not raise

        conn = real_connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='attempts'"
            )
            assert cur.fetchone() is not None
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# CER-096, item B: ensure_db — per-process init cache
# ---------------------------------------------------------------------------


class TestEnsureDb:
    def test_returns_resolved_path(self, db_path: Path) -> None:
        resolved = effort_db.ensure_db(db_path)
        assert resolved == db_path.resolve()
        assert db_path.exists()

    def test_second_call_same_spelling_does_not_reinit(
        self, db_path: Path, monkeypatch
    ) -> None:
        calls = {"n": 0}
        real_init_db = effort_db.init_db

        def _counting_init_db(path):
            calls["n"] += 1
            return real_init_db(path)

        monkeypatch.setattr(effort_db, "init_db", _counting_init_db)

        effort_db.ensure_db(db_path)
        effort_db.ensure_db(db_path)
        assert calls["n"] == 1

    def test_two_spellings_of_same_file_init_once(
        self, db_path: Path, monkeypatch
    ) -> None:
        """B2: cache is keyed by resolved path, not argument spelling."""
        calls = {"n": 0}
        real_init_db = effort_db.init_db

        def _counting_init_db(path):
            calls["n"] += 1
            return real_init_db(path)

        monkeypatch.setattr(effort_db, "init_db", _counting_init_db)

        alt_spelling = db_path.parent / "." / db_path.name
        effort_db.ensure_db(db_path)
        effort_db.ensure_db(alt_spelling)
        assert calls["n"] == 1

    def test_deleted_database_reinitialises(self, db_path: Path) -> None:
        """B3: the cache must not make a missing database permanently
        un-creatable."""
        effort_db.ensure_db(db_path)
        assert db_path.exists()
        db_path.unlink()
        assert not db_path.exists()

        effort_db.ensure_db(db_path)
        assert db_path.exists()

    def test_insert_attempt_bootstrap_still_works_unchanged(self, db_path: Path) -> None:
        """B5: insert_attempt's own on-demand init branch is untouched by
        ensure_db's existence."""
        assert not db_path.exists()
        row_id = effort_db.insert_attempt(db_path, **_required_fields())
        assert row_id == 1
        assert db_path.exists()


# ---------------------------------------------------------------------------
# CER-096, item C: atomic write-side attempt-number derivation
# ---------------------------------------------------------------------------


class TestInsertAttemptDerived:
    def test_first_row_gets_attempt_number_one(self, db_path: Path) -> None:
        row_id, attempt_number = effort_db.insert_attempt_derived(
            db_path,
            story_id="INFRA-600",
            agent_role="builder",
            ts="2026-07-26T00:00:00+00:00",
        )
        assert attempt_number == 1
        rows = effort_db.query_by_story(db_path, "INFRA-600")
        assert rows[0]["id"] == row_id
        assert rows[0]["attempt_number"] == 1

    def test_second_row_same_pair_gets_two(self, db_path: Path) -> None:
        effort_db.insert_attempt_derived(
            db_path, story_id="INFRA-601", agent_role="builder", ts="2026-07-26T00:00:00+00:00"
        )
        _, attempt_number = effort_db.insert_attempt_derived(
            db_path, story_id="INFRA-601", agent_role="builder", ts="2026-07-26T00:01:00+00:00"
        )
        assert attempt_number == 2

    def test_different_pair_does_not_increment(self, db_path: Path) -> None:
        effort_db.insert_attempt_derived(
            db_path, story_id="INFRA-602", agent_role="builder", ts="2026-07-26T00:00:00+00:00"
        )
        _, attempt_number = effort_db.insert_attempt_derived(
            db_path, story_id="INFRA-602", agent_role="reviewer", ts="2026-07-26T00:01:00+00:00"
        )
        assert attempt_number == 1

    def test_missing_required_field_raises(self, db_path: Path) -> None:
        with pytest.raises(ValueError, match="missing required"):
            effort_db.insert_attempt_derived(db_path, agent_role="builder", ts="2026-07-26T00:00:00+00:00")

    def test_attempt_number_kwarg_rejected(self, db_path: Path) -> None:
        """C1: attempt_number is derived, not accepted."""
        with pytest.raises(ValueError):
            effort_db.insert_attempt_derived(
                db_path,
                story_id="INFRA-603",
                agent_role="builder",
                ts="2026-07-26T00:00:00+00:00",
                attempt_number=5,
            )

    def test_unknown_field_raises(self, db_path: Path) -> None:
        with pytest.raises(ValueError, match="unknown"):
            effort_db.insert_attempt_derived(
                db_path,
                story_id="INFRA-604",
                agent_role="builder",
                ts="2026-07-26T00:00:00+00:00",
                bogus="x",
            )

    def test_historical_attempt_number_one_row_yields_two_next(
        self, db_path: Path
    ) -> None:
        """Instructions 3: a pre-INFRA-257 row (attempt_number=1, written by
        insert_attempt directly) makes the first derived value 2, not a
        collision with the existing row's ordinal."""
        effort_db.insert_attempt(
            db_path,
            **_required_fields(story_id="INFRA-605", attempt_number=1),
        )
        _, attempt_number = effort_db.insert_attempt_derived(
            db_path, story_id="INFRA-605", agent_role="builder", ts="2026-07-26T00:01:00+00:00"
        )
        assert attempt_number == 2


class TestInsertAttemptUnchanged:
    """C3: insert_attempt keeps its original name, signature, and contract."""

    def test_still_requires_attempt_number(self, db_path: Path) -> None:
        fields = _required_fields()
        del fields["attempt_number"]
        with pytest.raises(ValueError, match="missing required"):
            effort_db.insert_attempt(db_path, **fields)


class TestNextAttemptNumberAdvisoryDocstring:
    def test_docstring_mentions_advisory(self) -> None:
        """C7: next_attempt_number's docstring gains an advisory/read-only
        note pointing at insert_attempt_derived as the write path."""
        doc = effort_db.next_attempt_number.__doc__ or ""
        assert "advisory" in doc.lower()
        assert "insert_attempt_derived" in doc


# ---------------------------------------------------------------------------
# CER-096, item D: sweep ownership (output_prefix) and cursor (order)
# ---------------------------------------------------------------------------


class TestPendingReconcilableOwnership:
    def _seed_two_rows(self, db_path: Path) -> tuple[int, int]:
        effort_db.init_db(db_path)
        row_a = effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-700"))
        effort_db.set_spawn_ref(db_path, row_a, "a1", "/tmp/session-alpha/out1.output")
        row_b = effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-701"))
        effort_db.set_spawn_ref(db_path, row_b, "a2", "/tmp/session-beta/out2.output")
        return row_a, row_b

    def test_no_prefix_returns_both(self, db_path: Path) -> None:
        row_a, row_b = self._seed_two_rows(db_path)
        rows = effort_db.pending_reconcilable(db_path, 10)
        assert {r["id"] for r in rows} == {row_a, row_b}

    def test_prefix_matching_one_row_returns_only_that_row(self, db_path: Path) -> None:
        row_a, _row_b = self._seed_two_rows(db_path)
        rows = effort_db.pending_reconcilable(
            db_path, 10, output_prefix="/tmp/session-alpha/"
        )
        assert [r["id"] for r in rows] == [row_a]

    def test_prefix_matching_neither_returns_empty(self, db_path: Path) -> None:
        self._seed_two_rows(db_path)
        rows = effort_db.pending_reconcilable(
            db_path, 10, output_prefix="/tmp/session-gamma/"
        )
        assert rows == []

    def test_prefix_with_percent_does_not_widen_match(self, db_path: Path) -> None:
        """D1: a literal '%' in the prefix must be escaped, never treated as
        a SQL LIKE wildcard."""
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path, **_required_fields(story_id="INFRA-702")
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", "/tmp/weird%dir/out.output")

        # A prefix with a literal % that does NOT match the actual path
        # must not accidentally match via wildcard expansion.
        rows = effort_db.pending_reconcilable(
            db_path, 10, output_prefix="/tmp/other%dir/"
        )
        assert rows == []

        # But the exact literal prefix (with its % escaped) must match.
        rows = effort_db.pending_reconcilable(
            db_path, 10, output_prefix="/tmp/weird%dir/"
        )
        assert [r["id"] for r in rows] == [row_id]

    def test_empty_string_and_none_and_non_string_mean_no_filter(
        self, db_path: Path
    ) -> None:
        row_a, row_b = self._seed_two_rows(db_path)
        for bad in (None, "", 123):
            rows = effort_db.pending_reconcilable(db_path, 10, output_prefix=bad)
            assert {r["id"] for r in rows} == {row_a, row_b}


class TestPendingReconcilableOrder:
    def test_default_is_newest_first(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        ids = []
        for i in range(3):
            row_id = effort_db.insert_attempt(
                db_path, **_required_fields(story_id=f"INFRA-{800+i}")
            )
            effort_db.set_spawn_ref(db_path, row_id, f"a{i}", f"/tmp/out{i}.output")
            ids.append(row_id)

        rows = effort_db.pending_reconcilable(db_path, 10)
        assert [r["id"] for r in rows] == list(reversed(ids))

    def test_oldest_order(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        ids = []
        for i in range(3):
            row_id = effort_db.insert_attempt(
                db_path, **_required_fields(story_id=f"INFRA-{810+i}")
            )
            effort_db.set_spawn_ref(db_path, row_id, f"a{i}", f"/tmp/out{i}.output")
            ids.append(row_id)

        rows = effort_db.pending_reconcilable(db_path, 10, order="oldest")
        assert [r["id"] for r in rows] == ids

    def test_unrecognised_order_falls_back_to_newest(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        ids = []
        for i in range(2):
            row_id = effort_db.insert_attempt(
                db_path, **_required_fields(story_id=f"INFRA-{820+i}")
            )
            effort_db.set_spawn_ref(db_path, row_id, f"a{i}", f"/tmp/out{i}.output")
            ids.append(row_id)

        rows = effort_db.pending_reconcilable(db_path, 10, order="sideways")
        assert [r["id"] for r in rows] == list(reversed(ids))


# ---------------------------------------------------------------------------
# CER-097, item D3: sweep exclusion (exclude_output_prefixes)
# ---------------------------------------------------------------------------


class TestPendingReconcilableExclusion:
    def _seed_two_rows(self, db_path: Path) -> "tuple[int, int]":
        effort_db.init_db(db_path)
        row_a = effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-800"))
        effort_db.set_spawn_ref(db_path, row_a, "a1", "/tmp/session-alpha/out1.output")
        row_b = effort_db.insert_attempt(db_path, **_required_fields(story_id="INFRA-801"))
        effort_db.set_spawn_ref(db_path, row_b, "a2", "/tmp/session-beta/out2.output")
        return row_a, row_b

    def test_excluded_prefix_drops_only_that_row(self, db_path: Path) -> None:
        row_a, row_b = self._seed_two_rows(db_path)
        rows = effort_db.pending_reconcilable(
            db_path, 10, exclude_output_prefixes=("/tmp/session-beta/",)
        )
        assert [r["id"] for r in rows] == [row_a]

    def test_multiple_exclusions_are_all_applied(self, db_path: Path) -> None:
        self._seed_two_rows(db_path)
        rows = effort_db.pending_reconcilable(
            db_path,
            10,
            exclude_output_prefixes=["/tmp/session-alpha/", "/tmp/session-beta/"],
        )
        assert rows == []

    def test_none_empty_and_non_string_members_are_ignored(self, db_path: Path) -> None:
        row_a, row_b = self._seed_two_rows(db_path)
        for bad in (None, (), [], ("",), (123, None), "a string, not a sequence"):
            rows = effort_db.pending_reconcilable(
                db_path, 10, exclude_output_prefixes=bad
            )
            assert {r["id"] for r in rows} == {row_a, row_b}, bad

    def test_percent_in_excluded_prefix_is_escaped(self, db_path: Path) -> None:
        """D3: a literal '%' must never widen an exclusion into a blanket drop."""
        effort_db.init_db(db_path)
        row_id = effort_db.insert_attempt(
            db_path, **_required_fields(story_id="INFRA-802")
        )
        effort_db.set_spawn_ref(db_path, row_id, "a1", "/tmp/weird%dir/out.output")

        # A non-matching prefix containing '%' must not drop the row.
        rows = effort_db.pending_reconcilable(
            db_path, 10, exclude_output_prefixes=("/tmp/other%dir/",)
        )
        assert [r["id"] for r in rows] == [row_id]

        # The exact literal prefix does drop it.
        rows = effort_db.pending_reconcilable(
            db_path, 10, exclude_output_prefixes=("/tmp/weird%dir/",)
        )
        assert rows == []

    def test_both_filters_may_be_supplied_together(self, db_path: Path) -> None:
        row_a, _row_b = self._seed_two_rows(db_path)
        rows = effort_db.pending_reconcilable(
            db_path,
            10,
            output_prefix="/tmp/session-",
            exclude_output_prefixes=("/tmp/session-beta/",),
        )
        assert [r["id"] for r in rows] == [row_a]

    def test_order_and_max_age_still_work_alongside_exclusion(
        self, db_path: Path
    ) -> None:
        row_a, _row_b = self._seed_two_rows(db_path)
        rows = effort_db.pending_reconcilable(
            db_path,
            10,
            max_age_days=None,
            exclude_output_prefixes=("/tmp/session-beta/",),
            order="oldest",
        )
        assert [r["id"] for r in rows] == [row_a]

    def test_never_raises_on_a_missing_database(self, tmp_path: Path) -> None:
        missing = tmp_path / ".companion" / "nope.db"
        assert (
            effort_db.pending_reconcilable(
                missing, 10, exclude_output_prefixes=("/tmp/x/",)
            )
            == []
        )

    def test_sql_is_parameterised_not_interpolated(self, db_path: Path) -> None:
        """D3: the prefix is bound, never formatted into the query text."""
        row_a, row_b = self._seed_two_rows(db_path)
        rows = effort_db.pending_reconcilable(
            db_path, 10, exclude_output_prefixes=("' OR 1=1 --",)
        )
        assert {r["id"] for r in rows} == {row_a, row_b}


# ---------------------------------------------------------------------------
# INFRA-288 (CER-104): agent_id idempotency key — insert_or_update_attempt
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestInsertOrUpdateAttempt:
    def _derived_fields(self, **overrides) -> dict:
        base = {
            "story_id": "INFRA-288",
            "agent_role": "builder",
            "ts": _now_iso(),
        }
        base.update(overrides)
        return base

    # -- A1 -----------------------------------------------------------------

    def test_agent_id_and_output_file_are_insertable_columns(self) -> None:
        assert "agent_id" in effort_db._INSERT_COLUMNS
        assert "output_file" in effort_db._INSERT_COLUMNS
        for col in ("agent_id", "output_file"):
            assert col not in effort_db._REQUIRED_FIELDS
            assert col not in effort_db._DERIVED_REQUIRED_FIELDS

    def test_insert_attempt_derived_writes_agent_id(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        row_id, attempt_number = effort_db.insert_attempt_derived(
            db_path,
            story_id="S",
            agent_role="builder",
            ts="2026-07-28T00:00:00+00:00",
            agent_id="a-1",
        )
        assert attempt_number == 1
        rows = effort_db.query_by_story(db_path, "S")
        assert rows[0]["id"] == row_id
        assert rows[0]["agent_id"] == "a-1"

    def test_omitting_new_columns_writes_null(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_attempt_derived(db_path, **self._derived_fields())
        rows = effort_db.query_by_story(db_path, "INFRA-288")
        assert rows[0]["agent_id"] is None
        assert rows[0]["output_file"] is None

    # -- A2 -----------------------------------------------------------------

    def test_returns_row_id_attempt_number_deduped_triple(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        result = effort_db.insert_or_update_attempt(
            db_path, **self._derived_fields()
        )
        row_id, attempt_number, deduped = result
        assert isinstance(row_id, int)
        assert attempt_number == 1
        assert deduped is False

    def test_validation_matches_insert_attempt_derived(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        with pytest.raises(ValueError, match="missing required"):
            effort_db.insert_or_update_attempt(
                db_path, story_id="S", agent_role="builder"
            )
        with pytest.raises(ValueError, match="unknown"):
            effort_db.insert_or_update_attempt(
                db_path, **self._derived_fields(), not_a_column="x"
            )
        with pytest.raises(ValueError, match="unknown"):
            effort_db.insert_or_update_attempt(
                db_path, **self._derived_fields(), attempt_number=3
            )

    # -- A3 -----------------------------------------------------------------

    def test_insert_attempt_derived_signature_preserved(self, db_path: Path) -> None:
        """DP4: the old name keeps its two-tuple return."""
        effort_db.init_db(db_path)
        result = effort_db.insert_attempt_derived(
            db_path, **self._derived_fields()
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    # -- A4 / A5 ------------------------------------------------------------

    def test_match_updates_with_coalescing_semantics(self, db_path: Path) -> None:
        """A5: non-None overwrites, None leaves the existing value; one row."""
        effort_db.init_db(db_path)
        effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-x",
            **self._derived_fields(),
            agent_id="agent-x",
            model="haiku",
        )
        row_id, attempt_number, deduped = effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-x",
            **self._derived_fields(),
            agent_id="agent-x",
            model=None,
            outcome="PASS",
        )
        assert deduped is True
        assert attempt_number == 1
        rows = effort_db.query_by_story(db_path, "INFRA-288")
        assert len(rows) == 1
        assert rows[0]["id"] == row_id
        assert rows[0]["model"] == "haiku"  # None did NOT blank it
        assert rows[0]["outcome"] == "PASS"  # non-None overwrote

    def test_match_never_rederives_attempt_number_or_story_id(
        self, db_path: Path
    ) -> None:
        effort_db.init_db(db_path)
        # Seed unrelated attempts so a re-derivation would produce > 1.
        effort_db.insert_attempt_derived(db_path, **self._derived_fields())
        effort_db.insert_attempt_derived(db_path, **self._derived_fields())
        _rid, first_number, _ = effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-y",
            **self._derived_fields(),
            agent_id="agent-y",
        )
        rid2, second_number, deduped = effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-y",
            **self._derived_fields(story_id="OTHER-001"),
            agent_id="agent-y",
        )
        assert deduped is True
        assert second_number == first_number
        rows = [r for r in effort_db.query_all(db_path) if r["id"] == rid2]
        assert rows[0]["story_id"] == "INFRA-288"  # story_id never rewritten

    def test_stale_pending_row_outside_window_is_not_matched(
        self, db_path: Path
    ) -> None:
        """A4: the ts >= now - AGENT_DEDUPE_WINDOW_SECONDS bound is real."""
        effort_db.init_db(db_path)
        stale_ts = (
            datetime.now(timezone.utc)
            - timedelta(seconds=effort_db.AGENT_DEDUPE_WINDOW_SECONDS + 60)
        ).isoformat()
        effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-z",
            **self._derived_fields(ts=stale_ts),
            agent_id="agent-z",
        )
        _rid, _num, deduped = effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-z",
            **self._derived_fields(),
            agent_id="agent-z",
        )
        assert deduped is False
        assert len(effort_db.query_by_story(db_path, "INFRA-288")) == 2

    def test_window_constant_value(self) -> None:
        assert effort_db.AGENT_DEDUPE_WINDOW_SECONDS == 300

    # -- A6 -----------------------------------------------------------------

    def test_falsy_dedupe_agent_id_always_inserts(self, db_path: Path) -> None:
        effort_db.init_db(db_path)
        for dedupe in (None, ""):
            effort_db.insert_or_update_attempt(
                db_path,
                dedupe_agent_id=dedupe,
                **self._derived_fields(),
                agent_id="agent-q",
            )
        assert len(effort_db.query_by_story(db_path, "INFRA-288")) == 2

    def test_same_agent_id_different_role_inserts_two_rows(
        self, db_path: Path
    ) -> None:
        effort_db.init_db(db_path)
        effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-r",
            **self._derived_fields(agent_role="builder"),
            agent_id="agent-r",
        )
        _rid, _num, deduped = effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-r",
            **self._derived_fields(agent_role="reviewer"),
            agent_id="agent-r",
        )
        assert deduped is False
        assert len(effort_db.query_by_story(db_path, "INFRA-288")) == 2

    def test_completed_candidate_is_not_matched(self, db_path: Path) -> None:
        """A6: a row with tokens_total AND outcome both non-NULL is not
        pending, so a second call inserts."""
        effort_db.init_db(db_path)
        effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-s",
            **self._derived_fields(),
            agent_id="agent-s",
            tokens_total=100,
            outcome="PASS",
        )
        _rid, _num, deduped = effort_db.insert_or_update_attempt(
            db_path,
            dedupe_agent_id="agent-s",
            **self._derived_fields(),
            agent_id="agent-s",
        )
        assert deduped is False
        assert len(effort_db.query_by_story(db_path, "INFRA-288")) == 2
