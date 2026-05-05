"""effort_db.py — sqlite schema and helpers for pairmode effort tracking.

The database stores one row per agent invocation in a single ``attempts``
table.  No pricing data is stored: pricing is an optional, user-maintained
``pricing.json`` applied at report time only.

Public API
----------

- ``init_db(path)`` — create the schema (idempotent).
- ``insert_attempt(path, **fields)`` — append a row.  Raises ``ValueError`` if
  any required field (``story_id``, ``agent_role``, ``attempt_number``,
  ``ts``) is missing.
- ``query_by_story(path, story_id)`` / ``query_by_phase(path, phase)`` —
  return a list of dicts.
- ``resolve_effort_db_path(project_dir)`` — resolve the database path from
  ``.companion/state.json["effort_db_path"]``, defaulting to
  ``<project_dir>/.companion/effort.db``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_TABLE = """
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
    ts TEXT NOT NULL
);
"""

_SCHEMA_INDICES = (
    "CREATE INDEX IF NOT EXISTS idx_attempts_story ON attempts(story_id);",
    "CREATE INDEX IF NOT EXISTS idx_attempts_phase ON attempts(phase);",
    "CREATE INDEX IF NOT EXISTS idx_attempts_rail ON attempts(rail);",
)

# Columns in the order they are bound by ``insert_attempt``.  ``id`` is
# AUTOINCREMENT so it is omitted from the INSERT.
_INSERT_COLUMNS: tuple[str, ...] = (
    "story_id",
    "phase",
    "rail",
    "agent_role",
    "model",
    "attempt_number",
    "tokens_total",
    "tokens_in",
    "tokens_out",
    "cache_read_tokens",
    "cache_write_tokens",
    "tool_uses",
    "duration_ms",
    "outcome",
    "notes",
    "ts",
)

_REQUIRED_FIELDS: tuple[str, ...] = (
    "story_id",
    "agent_role",
    "attempt_number",
    "ts",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _depth_guard(path: Path) -> Path:
    """Resolve *path* and ensure it is not a suspiciously shallow location.

    Mirrors the project-dir depth guard pattern used elsewhere in pairmode
    (e.g. ``story_update.py``, ``phase_new.py``).  Applied to the database
    file path so we never accidentally open ``/effort.db`` or similar.
    """

    resolved = Path(path).resolve()
    if len(resolved.parts) < 3:
        raise ValueError(
            f"effort_db path too shallow: {resolved}"
        )
    return resolved


def resolve_effort_db_path(project_dir: Path) -> Path:
    """Resolve the effort-db file path for *project_dir*.

    Order of resolution:
    1. ``.companion/state.json["effort_db_path"]`` if present.
    2. Default: ``<project_dir>/.companion/effort.db``.

    Relative ``effort_db_path`` values are resolved against *project_dir*.
    """

    project_dir = Path(project_dir)
    state_path = project_dir / ".companion" / "state.json"
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        configured = data.get("effort_db_path")
        if configured:
            configured_path = Path(configured)
            if not configured_path.is_absolute():
                configured_path = project_dir / configured_path
            return configured_path

    return project_dir / ".companion" / "effort.db"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db(path: Path) -> None:
    """Create (or upgrade) the schema at *path*.  Idempotent.

    Creates the parent directory if it does not exist.
    """

    resolved = _depth_guard(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(resolved))
    try:
        cur = conn.cursor()
        cur.executescript(_SCHEMA_TABLE)
        for stmt in _SCHEMA_INDICES:
            cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def insert_attempt(path: Path, **fields: Any) -> int:
    """Insert a single attempt row into the database at *path*.

    Required fields: ``story_id``, ``agent_role``, ``attempt_number``, ``ts``.
    All other columns default to ``None`` if not supplied.  Unknown keyword
    arguments raise ``ValueError`` to catch typos at the call site.

    Returns the inserted ``id`` (rowid).
    """

    missing = [f for f in _REQUIRED_FIELDS if fields.get(f) in (None, "")]
    if missing:
        raise ValueError(
            f"insert_attempt missing required field(s): {', '.join(missing)}"
        )

    unknown = [k for k in fields if k not in _INSERT_COLUMNS]
    if unknown:
        raise ValueError(
            f"insert_attempt got unknown field(s): {', '.join(unknown)}"
        )

    resolved = _depth_guard(path)
    if not resolved.exists():
        # Calling insert before init is an error worth surfacing — but for
        # ergonomics we initialise on demand so the orchestrator does not
        # need a separate bootstrap step.
        init_db(resolved)

    values = tuple(fields.get(col) for col in _INSERT_COLUMNS)
    placeholders = ", ".join(["?"] * len(_INSERT_COLUMNS))
    columns_sql = ", ".join(_INSERT_COLUMNS)

    conn = sqlite3.connect(str(resolved))
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO attempts ({columns_sql}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _rows_to_dicts(cursor: sqlite3.Cursor, rows: Iterable[tuple]) -> list[dict]:
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def query_by_story(path: Path, story_id: str) -> list[dict]:
    """Return all attempts for *story_id*, oldest first by id."""

    resolved = _depth_guard(path)
    if not resolved.exists():
        return []

    conn = sqlite3.connect(str(resolved))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM attempts WHERE story_id = ? ORDER BY id ASC",
            (story_id,),
        )
        rows = cur.fetchall()
        return _rows_to_dicts(cur, rows)
    finally:
        conn.close()


def query_by_phase(path: Path, phase: str) -> list[dict]:
    """Return all attempts for *phase*, oldest first by id."""

    resolved = _depth_guard(path)
    if not resolved.exists():
        return []

    conn = sqlite3.connect(str(resolved))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM attempts WHERE phase = ? ORDER BY id ASC",
            (phase,),
        )
        rows = cur.fetchall()
        return _rows_to_dicts(cur, rows)
    finally:
        conn.close()


def query_all(path: Path) -> list[dict]:
    """Return every row, oldest first.  Convenience helper for tests/reports."""

    resolved = _depth_guard(path)
    if not resolved.exists():
        return []

    conn = sqlite3.connect(str(resolved))
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM attempts ORDER BY id ASC")
        rows = cur.fetchall()
        return _rows_to_dicts(cur, rows)
    finally:
        conn.close()
