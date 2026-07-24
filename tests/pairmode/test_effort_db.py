"""Tests for skills/pairmode/scripts/effort_db.py."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
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
        """Ensures 2: insert_attempt's required-field set is untouched — passing
        agent_id/output_file as insert_attempt kwargs must still raise unknown-field."""
        effort_db.init_db(db_path)
        with pytest.raises(ValueError, match="unknown"):
            effort_db.insert_attempt(
                db_path, **_required_fields(), agent_id="a1", output_file="/tmp/x"
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

        assert effort_db.reconcile_attempt(db_path, row_id, tokens_total=100) is True
        assert effort_db.reconcile_attempt(db_path, row_id, tokens_total=200) is False

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
