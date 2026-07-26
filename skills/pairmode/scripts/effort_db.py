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
- ``next_attempt_number(path, story_id, agent_role)`` — the lifetime spawn
  ordinal for a ``(story_id, agent_role)`` pair, derived from the count of
  existing rows for that pair.  Never raises; returns ``1`` on any missing,
  unreadable, or corrupt database (INFRA-257).
- ``set_spawn_ref(path, row_id, agent_id, output_file)`` — sets the
  ``agent_id``/``output_file`` columns on one row (INFRA-258). Never raises;
  returns ``True``/``False``.
- ``pending_reconcilable(path, limit, *, max_age_days=None)`` — rows with
  ``(tokens_total IS NULL OR outcome IS NULL)`` and an ``output_file`` on
  file, newest first, capped at ``limit`` (INFRA-258; widened to the ``OR``
  shape by CER-091 defect 2/3, so a partially-backfilled row is reachable
  again). ``max_age_days`` is an opt-in age cutoff, off by default (CER-088)
  — only ``subagent_transcript.reconcile_pending_attempts``'s hook sweep
  passes it. Never raises; returns ``[]`` on failure.
- ``reconcile_attempt(path, row_id, **fields)`` — conditional ``UPDATE`` of
  the reconcilable columns (tokens/duration/outcome/notes/model) on one row,
  atomic over tokens *and* outcome and single-shot via
  ``WHERE (tokens_total IS NULL OR outcome IS NULL)`` (INFRA-258; made
  atomic/repairable by CER-091 defect 2). Never raises; returns
  ``True``/``False``.
- ``resolve_db_path_arg(project_dir, db_path)`` — single-sourced containment
  for an explicit ``--db-path`` CLI argument (CER-016); raises ``ValueError``
  on an escaping path rather than silently falling back.
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
    model_selection_reason TEXT,
    backend TEXT,
    agent_id TEXT,
    output_file TEXT
);
"""

# ALTER TABLE statements for columns added after initial schema creation.
# Each is wrapped in a try/except because SQLite does not support
# IF NOT EXISTS on ALTER TABLE.
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE attempts ADD COLUMN story_class TEXT",
    "ALTER TABLE attempts ADD COLUMN model_selection_reason TEXT",
    "ALTER TABLE attempts ADD COLUMN backend TEXT",
    # INFRA-258: spawn-ref columns for deferred (async-spawn) reconciliation.
    "ALTER TABLE attempts ADD COLUMN agent_id TEXT",
    "ALTER TABLE attempts ADD COLUMN output_file TEXT",
)

#: CER-091 defect 2: the pair of columns that must BOTH be present
#: (and non-None) in `reconcile_attempt`'s `fields` before any UPDATE runs.
#: Writing `tokens_total` alone (a row-344 shape) stranded the row outcome
#: permanently NULL, because the old single-shot guard (`tokens_total IS
#: NULL`) then made the row invisible to every future sweep.
_ATOMIC_RECONCILE_FIELDS: tuple[str, ...] = ("tokens_total", "outcome")

#: Fixed allow-list of columns `reconcile_attempt` may write. Never built
#: from caller-supplied keys (Instructions 3).
_RECONCILABLE_COLUMNS: tuple[str, ...] = (
    "tokens_total",
    "tokens_in",
    "tokens_out",
    "cache_read_tokens",
    "cache_write_tokens",
    "duration_ms",
    "outcome",
    "notes",
    "model",
)

_SCHEMA_INDICES = (
    "CREATE INDEX IF NOT EXISTS idx_attempts_story ON attempts(story_id);",
    "CREATE INDEX IF NOT EXISTS idx_attempts_phase ON attempts(phase);",
    "CREATE INDEX IF NOT EXISTS idx_attempts_rail ON attempts(rail);",
)

#: Indices that reference ALTER-added columns and therefore must be created
#: AFTER _MIGRATIONS has run (CER-088). Putting these in _SCHEMA_INDICES would
#: crash init_db on exactly the legacy (pre-INFRA-258) databases the migrations
#: exist to upgrade, because output_file does not exist yet at that point.
#:
#: The partial WHERE clause matches ``pending_reconcilable``'s predicate
#: EXACTLY, including the ``OR`` between ``tokens_total`` and ``outcome``
#: (widened by CER-091 defect 2/3, INFRA-264). SQLite only uses a partial
#: index when the query's WHERE clause implies the index's partial
#: condition; the original narrower ``tokens_total IS NULL`` predicate
#: (correct pre-INFRA-264) no longer covers the widened query and the
#: planner silently falls back to a full scan, defeating CER-088 without
#: raising anything. Keep this clause byte-for-byte in step with
#: ``pending_reconcilable``'s ``WHERE`` — a future edit to one without the
#: other reintroduces the same silent regression.
_POST_MIGRATION_INDICES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_attempts_pending "
    "ON attempts(id DESC) "
    "WHERE (tokens_total IS NULL OR outcome IS NULL) AND output_file IS NOT NULL;",
)

#: /tmp spawn-output files do not survive this long, so a pending row older
#: than this window can never reconcile — scanning for it on the hook-path
#: sweep is pure cost (CER-088). Opt-in only (see pending_reconcilable):
#: INFRA-264's pending-row diagnostic (if it landed) must keep seeing
#: permanently-pending rows, since surfacing them is its entire purpose.
PENDING_MAX_AGE_DAYS: int = 14

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
    "backend",
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
            try:
                configured_path = _depth_guard(configured_path)
            except ValueError:
                return project_dir / ".companion" / "effort.db"
            try:
                configured_path.resolve().relative_to(project_dir.resolve())
            except ValueError:
                # Path escapes project_dir — use default
                return project_dir / ".companion" / "effort.db"
            return configured_path

    return project_dir / ".companion" / "effort.db"


def resolve_db_path_arg(
    project_dir: Path, db_path: "str | Path | None"
) -> Path:
    """Single-source resolution for an explicit ``--db-path`` CLI argument
    (CER-016).

    When *db_path* is ``None``, delegates unchanged to
    ``resolve_effort_db_path(project_dir)`` — including its silent fallback
    for an escaping ``state.json`` value, which this function does not
    change (that asymmetry is deliberate; see below).

    When *db_path* is given: a relative value is joined to *project_dir*,
    then both ``_depth_guard`` and a containment check
    (``resolve().relative_to(Path(project_dir).resolve())``) are applied.
    Either guard failing raises ``ValueError`` naming the rejected path and
    *project_dir*.

    The asymmetry between the two branches is deliberate: an escaping
    ``state.json["effort_db_path"]`` falls back silently to the default
    (unchanged behaviour, see ``resolve_effort_db_path``) because a config
    value is project-owned and a silent default is recoverable, whereas an
    escaping *explicit* ``db_path`` argument raises, because an operator who
    named a specific file must not have their rows silently written
    somewhere else.
    """

    project_path = Path(project_dir)
    if db_path is None:
        return resolve_effort_db_path(project_path)

    candidate = Path(db_path)
    if not candidate.is_absolute():
        candidate = project_path / candidate

    try:
        guarded = _depth_guard(candidate)
    except ValueError as exc:
        raise ValueError(
            f"--db-path {candidate} rejected: {exc} (project_dir={project_path})"
        ) from exc

    try:
        guarded.resolve().relative_to(project_path.resolve())
    except ValueError as exc:
        raise ValueError(
            f"--db-path {candidate} escapes project_dir {project_path}"
        ) from exc

    return guarded


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
        # Post-migration indices reference ALTER-added columns (CER-088) and
        # so must run after the migration loop above, each in its own guard —
        # an ancient SQLite without partial-index support degrades to "no
        # index", never breaks init_db.
        for stmt in _POST_MIGRATION_INDICES:
            try:
                cur.execute(stmt)
            except sqlite3.OperationalError:
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


def next_attempt_number(path: Path, story_id: str, agent_role: str) -> int:
    """Return the lifetime spawn ordinal for the ``(story_id, agent_role)`` pair.

    Computed as ``COUNT(*)`` of existing ``attempts`` rows matching *story_id*
    and *agent_role*, plus one — the next row for this pair will therefore be
    number ``count + 1``. ``story_id`` and ``agent_role`` are always bound as
    SQL parameters, never interpolated into the query text.

    Never raises (INFRA-257): this helper is called from a hook path, so any
    failure — missing file, missing table, corrupt/non-sqlite file, or
    empty/``None`` inputs — degrades to ``1``, the honest default for an
    indistinguishable-from-empty history.
    """

    try:
        if not story_id or not agent_role:
            return 1

        resolved = _depth_guard(path)
        if not resolved.exists():
            return 1

        conn = sqlite3.connect(str(resolved))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM attempts WHERE story_id = ? AND agent_role = ?",
                (story_id, agent_role),
            )
            row = cur.fetchone()
            count = int(row[0]) if row else 0
            return count + 1
        finally:
            conn.close()
    except Exception:
        return 1


def set_spawn_ref(
    path: Path, row_id: int, agent_id: "str | None", output_file: "str | None"
) -> bool:
    """Set the ``agent_id``/``output_file`` columns on one row by id (INFRA-258).

    Both values are bound as SQL parameters. Returns ``True`` on a successful
    update, ``False`` on any failure — missing db, missing table, missing
    row, or any other error. Never raises.
    """

    try:
        resolved = _depth_guard(path)
        if not resolved.exists():
            return False

        conn = sqlite3.connect(str(resolved))
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE attempts SET agent_id = ?, output_file = ? WHERE id = ?",
                (agent_id, output_file, row_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except Exception:
        return False


def pending_reconcilable(
    path: Path, limit: int, *, max_age_days: "int | None" = None
) -> list[dict]:
    """Return up to *limit* rows still awaiting reconciliation (INFRA-258,
    CER-091 defect 2/3).

    Matches ``(tokens_total IS NULL OR outcome IS NULL) AND output_file IS
    NOT NULL``, ordered by ``id DESC``. The ``OR`` (widened from the
    original ``tokens_total IS NULL``) is what makes a partially-backfilled
    row — tokens set, outcome still NULL, the row-344 shape — reachable by a
    future sweep instead of permanently invisible. *limit* is caller-supplied
    and always bound as a parameter — this function never issues an
    unbounded query. Each dict carries at least ``id``, ``story_id``,
    ``agent_role``, ``output_file``, ``model``. Returns ``[]`` on any
    failure (missing db, missing table, corrupt file, non-positive limit).
    Never raises.

    *max_age_days* (CER-088) is an opt-in age cutoff, off by default. When it
    is a positive ``int``, only rows whose ``ts >= now - max_age_days`` are
    returned — bound as a SQL parameter, never interpolated. Anything else
    (``None``, ``0``, negative, a non-``int``) means "no cutoff", identical
    to today's behaviour. This is deliberately off by default at this shared
    query layer: INFRA-264's pending-row diagnostic (if it landed) must keep
    seeing permanently-pending rows, since surfacing them is its entire
    purpose. Only the hook sweep (``subagent_transcript.reconcile_pending_attempts``)
    opts in via an explicit ``max_age_days``.

    The lexicographic ``ts >= ?`` comparison is valid only because every
    writer stamps ``datetime.now(tz=timezone.utc).isoformat()`` — a
    differently-formatted ``ts`` would silently break the bound, and the
    failure would look like "reconciliation stopped working."
    """

    try:
        if not isinstance(limit, int) or limit <= 0:
            return []

        resolved = _depth_guard(path)
        if not resolved.exists():
            return []

        use_cutoff = isinstance(max_age_days, int) and not isinstance(
            max_age_days, bool
        ) and max_age_days > 0

        conn = sqlite3.connect(str(resolved))
        try:
            cur = conn.cursor()
            if use_cutoff:
                cutoff = (
                    datetime.now(timezone.utc) - timedelta(days=max_age_days)
                ).isoformat()
                cur.execute(
                    """
                    SELECT * FROM attempts
                     WHERE (tokens_total IS NULL OR outcome IS NULL)
                       AND output_file IS NOT NULL
                       AND ts >= ?
                     ORDER BY id DESC
                     LIMIT ?
                    """,
                    (cutoff, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM attempts
                     WHERE (tokens_total IS NULL OR outcome IS NULL)
                       AND output_file IS NOT NULL
                     ORDER BY id DESC
                     LIMIT ?
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
            return _rows_to_dicts(cur, rows)
        finally:
            conn.close()
    except Exception:
        return []


def reconcile_attempt(path: Path, row_id: int, **fields: Any) -> bool:
    """Conditionally update the reconcilable columns on one row (INFRA-258,
    CER-091 defect 2).

    Only ``tokens_total``, ``tokens_in``, ``tokens_out``, ``cache_read_tokens``,
    ``cache_write_tokens``, ``duration_ms``, ``outcome``, ``notes``, and
    ``model`` may be written — the ``SET`` clause is built from a fixed
    allow-list, never from caller-supplied keys. Unknown kwargs are silently
    ignored (not written). ``story_id``, ``agent_role``, ``attempt_number``,
    ``phase``, ``rail``, and ``ts`` are never touched.

    Atomic over tokens *and* outcome (CER-091 defect 2): both members of
    :data:`_ATOMIC_RECONCILE_FIELDS` must be present in *fields* and
    non-``None``, or this returns ``False`` and performs **no** ``UPDATE`` —
    writing ``tokens_total`` alone (without a resolvable ``outcome``) is
    exactly the shape that stranded effort.db row 344 permanently.

    The update is guarded with ``AND (tokens_total IS NULL OR outcome IS
    NULL)`` — single-shot on *fully reconciled*, not merely on
    ``tokens_total``. This is what makes an existing partial row (tokens
    set, outcome NULL) repairable by a later call while still making a
    double-bump on an already-fully-reconciled row impossible: once both
    columns are non-NULL, the guard excludes the row from every future
    call and every future ``pending_reconcilable`` scan alike. Returns
    ``True`` only when a row was actually updated. Never raises.
    """

    try:
        for required in _ATOMIC_RECONCILE_FIELDS:
            if required not in fields or fields[required] is None:
                return False

        columns = [col for col in _RECONCILABLE_COLUMNS if col in fields]
        if not columns:
            return False

        resolved = _depth_guard(path)
        if not resolved.exists():
            return False

        set_clause = ", ".join(f"{col} = ?" for col in columns)
        values = [fields[col] for col in columns]
        values.append(row_id)

        conn = sqlite3.connect(str(resolved))
        try:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE attempts SET {set_clause} "
                "WHERE id = ? AND (tokens_total IS NULL OR outcome IS NULL)",
                values,
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except Exception:
        return False


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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _cli_main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the exit code.

    Separated from the ``if __name__ == "__main__"`` block so that tests can
    call it directly (with mocked dependencies) without spawning a subprocess.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="effort_db CLI — pairmode effort tracking helpers"
    )
    subparsers = parser.add_subparsers(dest="command")

    gc_parser = subparsers.add_parser(
        "guardrail-check",
        help="Compare a builder attempt's token count against the rail median.",
    )
    gc_parser.add_argument("--story-id", required=True, help="Story ID (e.g. INFRA-118)")
    gc_parser.add_argument("--rail", required=True, help="Rail name (e.g. INFRA)")
    gc_parser.add_argument(
        "--tokens", required=True, type=int, help="Token count for the latest attempt"
    )
    gc_parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args(argv)

    if args.command == "guardrail-check":
        db_path = resolve_effort_db_path(Path(args.project_dir))
        result = check_guardrail(
            db_path,
            story_id=args.story_id,
            rail=args.rail,
            latest_tokens=args.tokens,
        )
        if result["fired"]:
            print(result["message"])
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(_cli_main())
