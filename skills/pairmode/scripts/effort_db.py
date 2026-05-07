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
- ``check_guardrail(path, ...)`` — informational mid-loop guardrail that
  compares a just-completed builder attempt's tokens against the rail's
  recent median.  Returns a dict; never raises on missing data.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
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
    ts TEXT NOT NULL,
    story_class TEXT,
    model_selection_reason TEXT
);
"""

# ALTER TABLE statements for columns added after initial schema creation.
# Each is wrapped in a try/except because SQLite does not support
# IF NOT EXISTS on ALTER TABLE.
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE attempts ADD COLUMN story_class TEXT",
    "ALTER TABLE attempts ADD COLUMN model_selection_reason TEXT",
)

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
    "story_class",
    "model_selection_reason",
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

    Also runs any pending column-addition migrations (``_MIGRATIONS``).
    Each migration is wrapped in a try/except ``OperationalError`` so that
    running ``init_db`` twice on an existing database is always safe.
    """

    resolved = _depth_guard(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(resolved))
    try:
        cur = conn.cursor()
        cur.executescript(_SCHEMA_TABLE)
        for stmt in _SCHEMA_INDICES:
            cur.execute(stmt)
        # Apply additive column migrations idempotently.
        for migration in _MIGRATIONS:
            try:
                cur.execute(migration)
            except sqlite3.OperationalError:
                # Column already exists — safe to ignore.
                pass
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


# ---------------------------------------------------------------------------
# Real-time guardrail (INFRA-034)
# ---------------------------------------------------------------------------


_MIN_SAMPLE_SIZE = 3


def check_guardrail(
    db_path: Path,
    *,
    story_id: str,
    rail: str,
    latest_tokens: int,
    multiplier: float = 3.0,
    lookback_days: int = 30,
) -> dict:
    """Compare *latest_tokens* against the rail's recent median PASS-builder cost.

    Queries ``attempts`` for rows with ``agent_role='builder'``, ``rail=<rail>``,
    ``outcome='PASS'``, and ``ts`` within the last *lookback_days* days.
    Computes the median of the resulting ``tokens_total`` values (NULL/zero
    excluded) and compares ``latest_tokens`` against ``multiplier × median``.

    Returns a dict with the following keys:

    - ``fired`` (bool) — True if ``latest_tokens`` exceeded the threshold.
    - ``rail`` (str) — the rail queried.
    - ``median`` (int | None) — the median token count, or None if insufficient
      sample.
    - ``multiplier`` (float) — the multiplier used.
    - ``threshold`` (int | None) — ``int(median * multiplier)`` when fired or
      computable, else None.
    - ``latest`` (int) — the latest attempt's tokens (echoed back).
    - ``sample_size`` (int) — number of PASS-builder rows that informed the
      median.
    - ``message`` (str | None) — multi-line stderr-ready warning if fired,
      else None.

    The guardrail is informational only.  Insufficient sample (< 3 PASS-builder
    rows for the rail in the lookback window) returns early with
    ``fired=False`` and ``message=None`` — this avoids false positives on new
    rails.  Missing database also returns the insufficient-sample shape
    without raising.
    """

    resolved = _depth_guard(db_path)

    # Build the structured "no fire / no data" shell once; we mutate it as we
    # learn more.  This keeps every early-exit branch consistent.
    result: dict = {
        "fired": False,
        "rail": rail,
        "median": None,
        "multiplier": float(multiplier),
        "threshold": None,
        "latest": int(latest_tokens),
        "sample_size": 0,
        "message": None,
    }

    if not resolved.exists():
        return result

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=lookback_days)
    ).isoformat()

    conn = sqlite3.connect(str(resolved))
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tokens_total
              FROM attempts
             WHERE agent_role = 'builder'
               AND rail = ?
               AND outcome = 'PASS'
               AND ts >= ?
               AND tokens_total IS NOT NULL
               AND tokens_total > 0
            """,
            (rail, cutoff),
        )
        token_values = [int(row[0]) for row in cur.fetchall()]
    finally:
        conn.close()

    result["sample_size"] = len(token_values)

    if len(token_values) < _MIN_SAMPLE_SIZE:
        # Insufficient data — do not fire.  Median stays None so callers can
        # tell the difference between "no signal" and "below threshold".
        return result

    median_value = statistics.median(token_values)
    # statistics.median returns float for even-length samples; coerce to int
    # so the dict shape is stable for downstream consumers.
    median_int = int(median_value)
    threshold_int = int(median_value * float(multiplier))

    result["median"] = median_int
    result["threshold"] = threshold_int

    if int(latest_tokens) > threshold_int:
        result["fired"] = True
        ratio = (int(latest_tokens) / median_value) if median_value else 0.0
        result["message"] = (
            "[effort guardrail] Builder attempt exceeded "
            f"{float(multiplier):.1f}x rail median.\n"
            f"  story:        {story_id}\n"
            f"  rail:         {rail}\n"
            f"  latest:       {int(latest_tokens):,} tokens\n"
            f"  rail median:  {median_int:,} tokens "
            f"(n={len(token_values)}, last {lookback_days}d)\n"
            f"  threshold:    {threshold_int:,} tokens "
            f"({float(multiplier):.1f}x median)\n"
            f"  ratio:        {ratio:.2f}x median\n"
            "  suggestion:   pause and consult the user before spawning the "
            "reviewer; consider splitting the story or verifying scope."
        )

    return result
