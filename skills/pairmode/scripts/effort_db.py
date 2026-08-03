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
- ``ensure_db(path)`` — run ``init_db`` at most once per process per
  resolved path (CER-096, item B). Use this instead of ``init_db`` on any
  per-recording hot path.
- ``insert_attempt_derived(path, **fields)`` — like ``insert_attempt`` but
  derives ``attempt_number`` atomically on the write side, inside the same
  transaction as the insert (CER-096, item C). Returns
  ``(row_id, attempt_number)``.

Every connection this module opens goes through the module-private
``_connect`` helper, which sets ``busy_timeout``/``synchronous`` pragmas;
``init_db`` additionally enables WAL, once, persistently (CER-096, item A).
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

#: INFRA-348: columns removed from the live schema because they have zero
#: readers anywhere (CER-153). Dropped idempotently by
#: :func:`_drop_columns_if_present`, run from :func:`init_db` *after*
#: ``_MIGRATIONS`` — an existing pre-INFRA-348 database is upgraded in
#: place, never recreated empty (Ensures 8).
_DROP_COLUMNS: tuple[str, ...] = ("tool_uses",)

#: Minimum SQLite version exposing ``ALTER TABLE ... DROP COLUMN``
#: (released 3.35.0). Below this, ``_drop_columns_if_present`` falls back to
#: a create-new-table / copy-surviving-columns / swap rebuild that keeps the
#: table's name and every surviving row's values intact.
_MIN_SQLITE_DROP_COLUMN: tuple[int, int, int] = (3, 35, 0)

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

#: CER-096: concurrency configuration shared by every connection this module
#: opens (see ``_connect``). ``BUSY_TIMEOUT_SECONDS`` covers Python's own
#: connect-time ``timeout=`` lock wait; ``BUSY_TIMEOUT_MS`` covers
#: SQLite's internal ``PRAGMA busy_timeout`` — different mechanisms, both
#: needed under parallel-build contention. A test asserts the two cannot
#: drift apart.
BUSY_TIMEOUT_SECONDS: float = 15.0
BUSY_TIMEOUT_MS: int = 15000

#: INFRA-288 (CER-104): recency window for the ``agent_id`` idempotency
#: match in :func:`insert_or_update_attempt`. Deliberately tight — the
#: duplicate this defends against is a doubled hook registration firing the
#: same recording milliseconds apart, so a wide window buys nothing and
#: risks collapsing two genuinely distinct spawns that happen to share a
#: recycled agent id. Paired with the same
#: ``(tokens_total IS NULL OR outcome IS NULL)`` pending predicate
#: ``pending_reconcilable`` uses, so the deduped pair leaves exactly one
#: row and it is the row the reconciliation sweep already matches.
AGENT_DEDUPE_WINDOW_SECONDS = 300

#: INFRA-309 (CER-107 correction): ``agent_role`` values that record real
#: token cost but are not pairmode build-loop attempts. These are exactly the
#: three non-build-loop roles documented in ``record_attempt.py``'s
#: ``--agent-role`` list (``:74-75``) — ``sidebar-extractor``
#: (``skills/companion/scripts/sidebar.py``), ``seed-miner``
#: (``skills/seed/scripts/mine_sessions.py``), and ``seed-reconcile``
#: (``skills/seed/scripts/reconcile.py`` / ``effort_recorder.py``). Their rows
#: are *deliberately retained* in ``attempts`` — the token cost they record is
#: real, and deleting the write would trade permanent loss of cost data for a
#: cosmetic fix to a read path. This constant exists for **read-side**
#: cross-role aggregation only: it is never consulted by a writer, and it is
#: complementary to — not a substitute for —
#: ``subagent_transcript.RECORDABLE_SUBAGENT_ROLES``, which governs a
#: different question (what ``subagent_transcript`` records in the first
#: place). Every reader that aggregates *across* roles (rollups, baseline
#: seeding, the observability SPA's summary counters) excludes these roles;
#: readers that are already role-keyed (``models``, ``_query_effort_by_role``)
#: retain and label them instead. See ``docs/architecture.md`` § Effort
#: tracking.
NON_BUILD_ROLES: frozenset[str] = frozenset({
    "sidebar-extractor",
    "seed-miner",
    "seed-reconcile",
})

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
    "duration_ms",
    "outcome",
    "notes",
    "ts",
    "story_class",
    "model_selection_reason",
    "backend",
    # INFRA-288 (CER-104): the INFRA-258 spawn-ref columns become insertable
    # so the write path can stamp them in the same statement as the row —
    # they are deliberately NOT added to _REQUIRED_FIELDS or
    # _DERIVED_REQUIRED_FIELDS, so every existing caller that omits them
    # still writes NULL.
    "agent_id",
    "output_file",
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


def _connect(resolved: Path) -> sqlite3.Connection:
    """Open effort.db with the concurrency configuration (CER-096).

    ``timeout=`` covers Python's own lock wait; ``PRAGMA busy_timeout``
    covers SQLite's internal one — they are different mechanisms and both
    are needed. WAL itself is set once, persistently, by init_db — NOT
    here. Setting ``journal_mode = WAL`` is a *persistent database
    property*, not a per-connection setting, so re-issuing it on every
    connect (the "set it everywhere to be safe" reflex) would cost a
    pragma round-trip on every call for zero benefit.
    """
    conn = sqlite3.connect(str(resolved), timeout=BUSY_TIMEOUT_SECONDS)
    try:
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.Error:
        pass
    return conn


def _drop_columns_if_present(cur: sqlite3.Cursor, columns: "tuple[str, ...]") -> None:
    """Idempotently drop *columns* from the ``attempts`` table if present
    (INFRA-348, Ensures 1/8).

    A no-op when none of *columns* exist on the table (running this twice,
    or against a fresh post-story database that never had the column, is
    always safe). Prefers ``ALTER TABLE ... DROP COLUMN`` on SQLite >=
    :data:`_MIN_SQLITE_DROP_COLUMN`. On an older runtime, falls back to a
    create-new-table / copy-surviving-columns / swap rebuild that keeps the
    table's own name (so ``readers/effortDb.ts``'s SQL keeps resolving) and
    every surviving column's values for every surviving row untouched.
    Never raises — a failure here must not break ``init_db``.
    """
    try:
        cur.execute("PRAGMA table_info(attempts)")
        existing_cols = [row[1] for row in cur.fetchall()]
    except sqlite3.OperationalError:
        return

    present = [c for c in columns if c in existing_cols]
    if not present:
        return

    if sqlite3.sqlite_version_info >= _MIN_SQLITE_DROP_COLUMN:
        for col in present:
            try:
                cur.execute(f"ALTER TABLE attempts DROP COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        return

    # Fallback rebuild for SQLite older than 3.35.0 (no DROP COLUMN support).
    try:
        surviving = [c for c in existing_cols if c not in present]
        surviving_sql = ", ".join(surviving)
        cur.execute("ALTER TABLE attempts RENAME TO attempts_pre_drop_348")
        cur.executescript(_SCHEMA_TABLE)
        cur.execute(
            f"INSERT INTO attempts ({surviving_sql}) "
            f"SELECT {surviving_sql} FROM attempts_pre_drop_348"
        )
        cur.execute("DROP TABLE attempts_pre_drop_348")
    except sqlite3.OperationalError:
        pass


def init_db(path: Path) -> None:
    """Create (or upgrade) the schema at *path*.  Idempotent.

    Creates the parent directory if it does not exist.

    Also runs any pending column-addition migrations (``_MIGRATIONS``) and
    then any pending column *removals* (``_DROP_COLUMNS``, INFRA-348). Each
    step is wrapped in a try/except ``OperationalError`` so that running
    ``init_db`` twice on an existing database is always safe.
    """

    resolved = _depth_guard(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect(resolved)
    try:
        # WAL is persistent database state (set once here, not in
        # _connect — see that function's docstring). Tolerate failure: a
        # filesystem that cannot support WAL (e.g. some network mounts)
        # must leave the database usable in its default journal mode, not
        # raise (CER-096).
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:
            pass
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
        # INFRA-348: drop zero-reader columns from an existing (pre-story)
        # database. Runs after the additive migrations above and before the
        # post-migration indices below, since none of those indices
        # reference a dropped column.
        _drop_columns_if_present(cur, _DROP_COLUMNS)
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


#: CER-096: per-process cache of resolved db paths that have already run
#: ``init_db`` this process. Deliberately process-local and unbounded — a
#: process opens a handful of distinct effort.db files at most, and a
#: bounded cache would need eviction logic that could re-introduce the
#: very cost (repeated per-recording DDL) this cache exists to remove.
_INITIALISED: "set[str]" = set()


def ensure_db(path: Path) -> Path:
    """Resolve *path* and run :func:`init_db` at most once per process
    per resolved path (CER-096, item B).

    ``init_db`` runs a ``CREATE TABLE IF NOT EXISTS``, three index
    creations, five ``ALTER TABLE`` migrations, and a post-migration
    index, all inside one write transaction. Doing that before *every*
    recording (the pre-CER-096 shape) maximised the window a write lock
    was held under parallel spawns for a bootstrap that only ever needs
    to happen once. This cache makes it happen once.

    The cache is keyed by the *resolved* path string, not the caller's
    argument spelling, and is consulted together with
    ``resolved.exists()`` — a cached path whose file has since been
    deleted (test teardown, an operator ``rm``) must re-initialise, or
    the cache would turn a recoverable state into a permanently broken
    one. Never raises for a path ``init_db`` would accept.
    """

    resolved = _depth_guard(path)
    key = str(resolved)
    if key not in _INITIALISED or not resolved.exists():
        init_db(resolved)
        _INITIALISED.add(key)
    return resolved


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

    conn = _connect(resolved)
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


#: Required fields for :func:`insert_attempt_derived` — like
#: ``_REQUIRED_FIELDS`` but WITHOUT ``attempt_number``, which this function
#: derives rather than accepts.
_DERIVED_REQUIRED_FIELDS: "tuple[str, ...]" = ("story_id", "agent_role", "ts")


def insert_or_update_attempt(
    path: Path, *, dedupe_agent_id: "str | None" = None, **fields: Any
) -> "tuple[int, int, bool]":
    """Insert a derived-ordinal row, or update the live pending row a doubled
    hook invocation already wrote (INFRA-288, CER-104).

    With *dedupe_agent_id* ``None`` (or empty), behaviour is byte-for-byte
    :func:`insert_attempt_derived`'s pre-INFRA-288 behaviour: requires
    ``story_id``, ``agent_role`` and ``ts`` — but explicitly NOT
    ``attempt_number``, which this function computes. All other columns
    behave exactly as in :func:`insert_attempt` (default ``None``, unknown
    keys raise ``ValueError``). Returns ``(row_id, attempt_number, False)``.

    With *dedupe_agent_id* a non-empty string, the value becomes an
    idempotency key: a live pending row (``tokens_total IS NULL OR outcome
    IS NULL`` — the same predicate ``pending_reconcilable`` uses) with the
    same ``agent_id``/``agent_role`` and a ``ts`` within
    :data:`AGENT_DEDUPE_WINDOW_SECONDS` is *updated* instead of a new row
    being inserted, and ``(matched_row_id, existing_attempt_number, True)``
    is returned. The update coalesces: for every column in
    ``_INSERT_COLUMNS`` except ``attempt_number`` and ``story_id``, a
    supplied non-``None`` value overwrites and ``None`` leaves the existing
    value untouched — the second hook invocation is not more authoritative
    than the first, so it must never blank a value the first wrote.
    ``attempt_number`` is never re-derived on the update path and
    ``story_id`` is never rewritten.

    The match query runs *inside* the same ``BEGIN IMMEDIATE`` transaction
    as the write. A SELECT outside the transaction would be exactly the
    read-then-write race CER-096 item C removed from the attempt-ordinal
    derivation: two hook processes 15–30 ms apart would both miss and both
    insert. Inside the write lock, the second writer observes the first
    writer's committed row and updates it.

    Best-effort by design (CER-104): a spawn whose ``tool_response``
    carries no recoverable agent id yields ``dedupe_agent_id=None`` here
    and therefore still produces today's double row under a doubled hook
    registration. The merged-hook-view detection and bootstrap skip
    (``hook_view.py``, INFRA-288 § B) is the primary cure — removing the
    duplicate registration itself; this idempotency key is defence in
    depth, not a guarantee that duplicates are impossible.

    The derivation and the insert happen inside a single ``BEGIN
    IMMEDIATE`` transaction, as one ``INSERT ... SELECT`` statement, so the
    read of the current max ordinal and the write of the new row occupy
    the same write lock — nothing else can observe or race the value in
    between. ``story_id``/``agent_role`` are bound as SQL parameters in
    both the SELECT column list's filter and the outer INSERT, never
    interpolated.

    ``COALESCE(MAX(attempt_number), 0) + 1`` — not ``COUNT(*) + 1`` — is
    deliberate: ``COUNT(*)`` re-derives an ordinal that a deleted row, or a
    historical ``attempt_number = 1`` row (see below), would make collide,
    whereas ``MAX`` is monotone over whatever rows are actually present.
    Rows written before INFRA-257 all carry ``attempt_number = 1``, so the
    first derived value for such a pair will be ``2`` — that is correct;
    no backfill is performed.
    """

    missing = [f for f in _DERIVED_REQUIRED_FIELDS if fields.get(f) in (None, "")]
    if missing:
        raise ValueError(
            f"insert_attempt_derived missing required field(s): {', '.join(missing)}"
        )

    unknown = [
        k for k in fields if k not in _INSERT_COLUMNS or k == "attempt_number"
    ]
    if unknown:
        raise ValueError(
            f"insert_attempt_derived got unknown field(s): {', '.join(unknown)}"
        )

    resolved = _depth_guard(path)
    if not resolved.exists():
        init_db(resolved)

    story_id = fields["story_id"]
    agent_role = fields["agent_role"]

    # Build the SELECT list from _INSERT_COLUMNS so a future column
    # addition cannot silently misalign the derived expression's position
    # with attempt_number's position in the INSERT column list.
    select_parts: list[str] = []
    values: list[Any] = []
    for col in _INSERT_COLUMNS:
        if col == "attempt_number":
            select_parts.append("COALESCE(MAX(attempt_number), 0) + 1")
        else:
            select_parts.append("?")
            values.append(fields.get(col))
    values.append(story_id)
    values.append(agent_role)

    columns_sql = ", ".join(_INSERT_COLUMNS)
    select_sql = ", ".join(select_parts)
    sql = (
        f"INSERT INTO attempts ({columns_sql}) "
        f"SELECT {select_sql} FROM attempts "
        "WHERE story_id = ? AND agent_role = ?"
    )

    use_dedupe = isinstance(dedupe_agent_id, str) and dedupe_agent_id != ""

    conn = _connect(resolved)
    try:
        # isolation_level=None puts the connection in autocommit mode so
        # our own BEGIN IMMEDIATE (rather than sqlite3's implicit
        # deferred BEGIN) is what actually takes the write lock — that is
        # what makes the read of MAX(attempt_number) and the INSERT
        # atomic together (and, when deduping, makes the match lookup and
        # the write atomic together — see the docstring).
        conn.isolation_level = None
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            if use_dedupe:
                # The lexicographic ``ts >= ?`` bound is valid only because
                # every writer stamps datetime.now(tz=timezone.utc).isoformat()
                # — a differently-formatted ``ts`` silently breaks the bound
                # (same warning as pending_reconcilable's cutoff).
                dedupe_cutoff = (
                    datetime.now(timezone.utc)
                    - timedelta(seconds=AGENT_DEDUPE_WINDOW_SECONDS)
                ).isoformat()
                match = cur.execute(
                    "SELECT id, attempt_number FROM attempts"
                    " WHERE agent_id = ?"
                    "   AND agent_role = ?"
                    "   AND (tokens_total IS NULL OR outcome IS NULL)"
                    "   AND ts >= ?"
                    " ORDER BY id ASC LIMIT 1",
                    (dedupe_agent_id, agent_role, dedupe_cutoff),
                ).fetchone()
                if match is not None:
                    matched_id = int(match[0])
                    existing_attempt_number = int(match[1])
                    # Coalescing SET list, built only from the fixed
                    # _INSERT_COLUMNS allow-list (never caller keys):
                    # non-None overwrites, None leaves the existing value.
                    set_parts: list[str] = []
                    set_values: list[Any] = []
                    for col in _INSERT_COLUMNS:
                        if col in ("attempt_number", "story_id"):
                            continue
                        value = fields.get(col)
                        if value is None:
                            continue
                        set_parts.append(f"{col} = ?")
                        set_values.append(value)
                    if set_parts:
                        cur.execute(
                            f"UPDATE attempts SET {', '.join(set_parts)}"
                            " WHERE id = ?",
                            (*set_values, matched_id),
                        )
                    conn.commit()
                    return matched_id, existing_attempt_number, True
            cur.execute(sql, values)
            attempt_number = cur.execute(
                "SELECT attempt_number FROM attempts WHERE id = ?",
                (cur.lastrowid,),
            ).fetchone()[0]
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return int(cur.lastrowid), int(attempt_number), False
    finally:
        conn.close()


def insert_attempt_derived(path: Path, **fields: Any) -> "tuple[int, int]":
    """Insert a row whose ``attempt_number`` is derived atomically on the
    write side (CER-096, item C).

    Since INFRA-288 this is a compatibility delegation to
    :func:`insert_or_update_attempt` with ``dedupe_agent_id=None`` — the
    signature and the ``(row_id, attempt_number)`` return are unchanged
    (Era 003 DP4 additive-until-flip contract); see the delegate's
    docstring for the full semantics.
    """

    row_id, attempt_number, _deduped = insert_or_update_attempt(
        path, dedupe_agent_id=None, **fields
    )
    return row_id, attempt_number


def _rows_to_dicts(cursor: sqlite3.Cursor, rows: Iterable[tuple]) -> list[dict]:
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def query_by_story(path: Path, story_id: str) -> list[dict]:
    """Return all attempts for *story_id*, oldest first by id."""

    resolved = _depth_guard(path)
    if not resolved.exists():
        return []

    conn = _connect(resolved)
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

    conn = _connect(resolved)
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

        conn = _connect(resolved)
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


#: The only two accepted ``order`` values for :func:`pending_reconcilable`
#: (CER-096, item D2). The ``ORDER BY`` clause is always selected from this
#: literal mapping in Python — the caller-supplied *order* value is never
#: string-formatted into the SQL, so an unexpected value cannot inject a
#: clause; it just falls back to "newest".
_PENDING_ORDER_CLAUSES: "dict[str, str]" = {
    "newest": "ORDER BY id DESC",
    "oldest": "ORDER BY id ASC",
}


def _escape_like_prefix(prefix: str) -> str:
    """Escape ``%``, ``_`` and ``\\`` in *prefix* for a ``LIKE ... ESCAPE '\\'``
    clause, so an ownership prefix can never accidentally widen the filter
    it exists to narrow (CER-096, item D1)."""

    return (
        prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


def pending_reconcilable(
    path: Path,
    limit: int,
    *,
    max_age_days: "int | None" = None,
    output_prefix: "str | None" = None,
    exclude_output_prefixes: "tuple[str, ...] | list[str] | None" = None,
    order: str = "newest",
) -> list[dict]:
    """Return up to *limit* rows still awaiting reconciliation (INFRA-258,
    CER-091 defect 2/3; ownership/ordering added CER-096 item D).

    Matches ``(tokens_total IS NULL OR outcome IS NULL) AND output_file IS
    NOT NULL``. The ``OR`` (widened from the original ``tokens_total IS
    NULL``) is what makes a partially-backfilled row — tokens set, outcome
    still NULL, the row-344 shape — reachable by a future sweep instead of
    permanently invisible. *limit* is caller-supplied and always bound as a
    parameter — this function never issues an unbounded query. Each dict
    carries at least ``id``, ``story_id``, ``agent_role``, ``output_file``,
    ``model``. Returns ``[]`` on any failure (missing db, missing table,
    corrupt file, non-positive limit). Never raises.

    *max_age_days* (CER-088) is an opt-in age cutoff, off by default. When it
    is a positive ``int``, only rows whose ``ts >= now - max_age_days`` are
    returned — bound as a SQL parameter, never interpolated. Anything else
    (``None``, ``0``, negative, a non-``int``) means "no cutoff", identical
    to today's behaviour. This is deliberately off by default at this shared
    query layer: INFRA-264's pending-row diagnostic (if it landed) must keep
    seeing permanently-pending rows, since surfacing them is its entire
    purpose. Only the hook sweep (``subagent_transcript.reconcile_pending_attempts``)
    opts in via an explicit ``max_age_days``.

    *output_prefix* (CER-096, item D1) is an opt-in ownership filter. When
    it is a non-empty string, the query adds
    ``AND output_file LIKE ? || '%' ESCAPE '\\'`` with the prefix bound as a
    parameter (never interpolated) and ``%``/``_``/``\\`` in the prefix
    escaped, so a prefix that happens to contain a wildcard character
    cannot silently widen an ownership filter into matching rows it should
    not. Anything else (``None``, ``""``, a non-``string``) means "no
    ownership filter" — byte-identical to pre-CER-096 behaviour. Deriving a
    real session-scoped prefix is INFRA-285's (CER-097's) job; this
    function only exposes the mechanism.

    *exclude_output_prefixes* (CER-097, item D3) is the opposite filter, and the
    two may be supplied together. Each non-empty string member contributes
    ``AND (output_file IS NULL OR output_file NOT LIKE ? ESCAPE '\\')`` with
    ``_escape_like_prefix(prefix) + '%'`` bound as a parameter — never
    interpolated into the query text, and escaped through the same single
    routine as the inclusive filter so the two can never disagree about what a
    literal ``%`` means. ``None``, an empty sequence, and non-string members are
    ignored rather than errors.

    The ``output_file IS NULL OR`` disjunct is required, not defensive:
    ``NOT LIKE`` against a ``NULL`` yields ``NULL``, which SQLite treats as
    false, so without it every row whose ``output_file`` has not been set yet
    would be silently dropped from the sweep.

    The two directions exist because the two call sites own different things:
    ``record_attempt_from_transcript``'s PostToolUse sweep runs *inside* a
    session that just spawned, where an inclusive own-prefix filter is correct
    and cheapest; ``hooks/session_start.py``'s sweep must still collect orphan
    rows from *dead* sessions (the rows INFRA-258 built it for) and so can only
    exclude the live ones.

    *order* (CER-096, item D2) selects ``"newest"`` (``ORDER BY id DESC``,
    the default and pre-CER-096 behaviour) or ``"oldest"``
    (``ORDER BY id ASC``). Any other value falls back to ``"newest"``
    without raising — the clause is chosen from a fixed two-entry mapping,
    never string-formatted from the parameter.

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

        use_prefix = isinstance(output_prefix, str) and output_prefix != ""

        where_fragments = [
            "(tokens_total IS NULL OR outcome IS NULL)",
            "output_file IS NOT NULL",
        ]
        params: list[Any] = []

        if use_cutoff:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=max_age_days)
            ).isoformat()
            where_fragments.append("ts >= ?")
            params.append(cutoff)

        if use_prefix:
            where_fragments.append("output_file LIKE ? || '%' ESCAPE '\\'")
            params.append(_escape_like_prefix(output_prefix))

        if isinstance(exclude_output_prefixes, (tuple, list)):
            for excluded in exclude_output_prefixes:
                if not isinstance(excluded, str) or excluded == "":
                    continue
                where_fragments.append(
                    "(output_file IS NULL OR output_file NOT LIKE ? ESCAPE '\\')"
                )
                params.append(_escape_like_prefix(excluded) + "%")

        order_clause = _PENDING_ORDER_CLAUSES.get(order, _PENDING_ORDER_CLAUSES["newest"])
        where_sql = " AND ".join(where_fragments)
        params.append(limit)

        conn = _connect(resolved)
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM attempts WHERE {where_sql} {order_clause} LIMIT ?",
                params,
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

        conn = _connect(resolved)
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

    conn = _connect(resolved)
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

    conn = _connect(resolved)
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
