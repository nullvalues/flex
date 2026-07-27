---
id: INFRA-284
rail: INFRA
title: "effort.db concurrency: WAL, busy_timeout, atomic attempt-number derivation, sweep ownership and cursor (CER-096)"
status: draft
phase: "109"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/effort_recorder.py
  - skills/pairmode/scripts/subagent_transcript.py
touches:
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_effort_concurrency.py
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-284.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 109 restores the intended capability of **one orchestrator running parallel
story builds**. Every other story in the phase makes a piece of *coordination*
state story- or phase-keyed. This story makes the **effort ledger** survive the
same concurrency, because `effort.db` is the one shared mutable resource that
every parallel worker writes to at the same moments — PostToolUse fires once per
spawn, and under parallel builds several spawns land inside the same few hundred
milliseconds.

CER-096 (MEDIUM, from the 2026-07-25 parallel-build concurrency audit) names four
defects, all of which are invisible under a serial loop and all of which produce
**silent** damage under a parallel one:

**A — no concurrency configuration.** Every `sqlite3.connect` in
`effort_db.py` (eleven sites, `init_db` through `check_guardrail`) opens the
database in the default rollback-journal mode with the default busy handling. In
rollback-journal mode a writer blocks *readers*, not just other writers. When the
5-second default busy window expires SQLite raises `OperationalError`, and both
recording paths swallow it — `effort_recorder.record_effort`'s
`except Exception` (`effort_recorder.py:186-192`) and
`subagent_transcript.record_attempt_from_transcript`'s equivalent. The row is
simply never written. The failure mode is not an error the operator sees; it is a
build whose effort history has holes.

**B — `init_db` on every recording.** `record_effort` calls
`_effort_db.init_db(db_path)` before every `insert_attempt`
(`effort_recorder.py:164-166`). `init_db` runs a `CREATE TABLE IF NOT EXISTS`, three
index creations, five `ALTER TABLE` migrations and a post-migration index, all
inside a write transaction — on a path that only ever needs to do that once. Under
parallel spawns this maximises the window in which one process holds the write
lock, turning a schema-bootstrap convenience into the dominant source of
contention.

**C — the attempt-number derivation is a read-then-write race.**
`effort_db.next_attempt_number` (`effort_db.py:430-464`) issues a `COUNT(*)` and
the caller then passes the result into a *separate* `insert_attempt` call
(`subagent_transcript.py:1356-1382`). Nothing spans the two. The code's own
comment concedes this — "the era's serial (no-nested-spawning) build loop makes
the resulting race a non-issue" (`subagent_transcript.py:1348-1355`) — and
`docs/architecture.md:2459-2468` records the same reasoning as an accepted
tradeoff. That premise is exactly what this phase removes. Two concurrent spawns
for the same `(story_id, agent_role)` now read the same count and write the same
`attempt_number`, and duplicate ordinals corrupt every per-attempt view in the
observability SPA and the escalation-ladder reads that count them.

**D — the reconcile sweep has no ownership and no cursor.**
`reconcile_pending_attempts` fetches `RECONCILE_MAX_ROWS = 5` pending rows
`ORDER BY id DESC` (`effort_db.pending_reconcilable`, `effort_db.py:498-575`)
across the whole table. Two problems compound under parallelism: the sweep
touches rows belonging to *other* in-flight workers (and, per CER-097, other
sessions), and with more than five genuinely pending rows the newest five are
re-examined on every sweep while the older ones are never reached again. The
CER-088 age cutoff added in INFRA-266 hides permanently-stale rows from the sweep
but does nothing for the live middle band: a busy parallel build can hold ten or
more legitimately-pending rows, and the oldest of them starve until they age out
and are lost.

**Scope boundary against the neighbouring stories.** INFRA-282 keys
`.companion/attempt_counter.json` — the *failure* counter that drives the retry
ladder — and is a different number in a different file from this story's
`attempts.attempt_number` ordinal. INFRA-285 (CER-097) owns *session* identity:
which session a hook belongs to, session-scoped context accounting, and the
advisory `state.json` lock. This story therefore builds the ownership *mechanism*
in the query layer and leaves the wiring of a real session identity to INFRA-285,
which is the story that will know what to pass. INFRA-286 owns the prose in
`docs/architecture.md` that this phase's changes obsolete, including the
serialism tradeoff paragraph at `docs/architecture.md:2459-2468`; per the phase
doc's § Ordering, this story must not rewrite it.

## Requires

- **INFRA-264 and INFRA-266 are complete and merged to `main`**, and this story's
  worktree is cut from a `HEAD` containing both. They edited the same three files
  for recording-semantics and cost/containment defects. Verify before building:
  `git log --oneline --grep 'INFRA-266' -1` returns a commit reachable from
  `HEAD`. The line numbers in this spec are anchors from that state, not
  coordinates — re-read each function before editing it.
- `skills/pairmode/scripts/effort_db.py` exposes `_depth_guard`,
  `resolve_effort_db_path`, `resolve_db_path_arg`, `init_db`, `insert_attempt`,
  `next_attempt_number`, `set_spawn_ref`, `pending_reconcilable`,
  `reconcile_attempt`, `query_by_story`, `query_by_phase`, `query_all`,
  `check_guardrail`, and the module constants `_SCHEMA_TABLE`, `_MIGRATIONS`,
  `_SCHEMA_INDICES`, `_POST_MIGRATION_INDICES`, `_INSERT_COLUMNS`,
  `_REQUIRED_FIELDS`, `PENDING_MAX_AGE_DAYS`.
- `skills/pairmode/scripts/effort_recorder.py` exposes `record_effort` with an
  `attempt_number: int = 1` keyword and a `log_fn` keyword.
- `skills/pairmode/scripts/subagent_transcript.py` exposes
  `record_attempt_from_transcript`, `reconcile_pending_attempts`,
  `RECONCILE_MAX_ROWS = 5`, `RECONCILE_MAX_AGE_DAYS`, `QUIESCENT_AGE_SECONDS`.
- `docs/cer/backlog.md` contains a `CER-096` row whose `Phase` cell reads `109`.
- The three `attempts` writers all stamp `ts` as
  `datetime.now(tz=timezone.utc).isoformat()` (unchanged from INFRA-266).
- No sibling phase-109 story is being built concurrently in the same worktree.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command.

### A — WAL and busy_timeout on every effort_db connection

**A1. A single connection helper exists.** `effort_db.py` defines
`_connect(resolved: Path) -> sqlite3.Connection` which calls
`sqlite3.connect(str(resolved), timeout=BUSY_TIMEOUT_SECONDS)`, then executes
`PRAGMA busy_timeout = <BUSY_TIMEOUT_MS>` and `PRAGMA synchronous = NORMAL` on
the new connection, and returns it. `BUSY_TIMEOUT_SECONDS: float = 15.0` and
`BUSY_TIMEOUT_MS: int = 15000` are module-level constants defined next to
`PENDING_MAX_AGE_DAYS`, and `BUSY_TIMEOUT_MS == int(BUSY_TIMEOUT_SECONDS * 1000)`
is asserted by a test so the two cannot drift. (`spec-preflight` warns that
`BUSY_TIMEOUT_SECONDS` and `BUSY_TIMEOUT_MS` have no definition in the source
tree — intentional: this story creates them. Its `WAL` and `NORMAL` warnings are
false positives: those are SQLite pragma *values*, not named constants.)

**A2. Every connection in `effort_db.py` goes through it.**
`grep -c 'sqlite3.connect' skills/pairmode/scripts/effort_db.py` returns `1`, and
that one occurrence is inside `_connect`. No other function in the file calls
`sqlite3.connect` directly.

**A3. WAL is enabled once, by `init_db`, and persists.** `init_db` executes
`PRAGMA journal_mode = WAL` and tolerates failure (a filesystem that cannot
support WAL must leave the database usable, not raise). A test asserts that after
`effort_db.init_db(db_path)`, a fresh independent
`sqlite3.connect(db_path).execute("PRAGMA journal_mode").fetchone()[0].lower()`
returns `"wal"` — i.e. the mode is a persisted database property, not a
per-connection setting.

**A4. A WAL failure is not fatal.** A test monkeypatches the journal-mode
statement (or points `init_db` at a database where the pragma raises
`sqlite3.OperationalError`) and asserts `init_db` returns normally and the schema
is still created.

**A5. Concurrent readers and writers do not raise.** A test in
`tests/pairmode/test_effort_concurrency.py` opens a long-lived *read* connection
that has an open cursor over `attempts`, and while it is open calls
`effort_db.insert_attempt` — asserting the insert succeeds and the row is
readable afterwards. Under the pre-change rollback-journal configuration this is
the shape that produced `database is locked`.

**A6. Contention is retried, not lost.** A test spawns `N = 8`
`threading.Thread`s (or `concurrent.futures.ThreadPoolExecutor` workers), each
inserting 5 rows via `effort_db.insert_attempt` against the same database file
with `check_same_thread` handled by opening a connection per call (which
`_connect` already does). After joining, `len(effort_db.query_all(db_path)) == 40`
and no exception was raised in any worker. The test must fail if `_connect`'s
`busy_timeout` is removed.

### B — `init_db` runs once per process, per database

**B1. A per-process init cache exists.** `effort_db.py` defines a module-level
`_INITIALISED: set[str]` and a public `ensure_db(path: Path) -> Path` which
resolves the path via `_depth_guard`, calls `init_db` only when the resolved
string is not already in `_INITIALISED` **or** the file does not exist, and
returns the resolved path. `ensure_db` never raises for a path `init_db` would
accept.

**B2. The cache is keyed by resolved path, not by argument.** A test calls
`ensure_db` twice with two different spellings of the same file (e.g. `db_path`
and `db_path.parent / "." / db_path.name`) and asserts `init_db` was invoked
exactly once, by monkeypatching `effort_db.init_db` with a counting wrapper.

**B3. A deleted database re-initialises.** A test calls `ensure_db`, unlinks the
file, calls `ensure_db` again, and asserts the schema exists afterwards — the
cache must not make a missing database permanently un-creatable.

**B4. `record_effort` uses `ensure_db`.**
`grep -n 'init_db' skills/pairmode/scripts/effort_recorder.py` returns nothing;
the call at `effort_recorder.py:164-166` is `_effort_db.ensure_db(...)`. A test
records two attempts in one process and asserts `init_db` ran once.

**B5. `insert_attempt`'s on-demand bootstrap is preserved.**
`insert_attempt`'s existing "initialise on demand if the file does not exist"
branch still exists and still works — a test that calls `insert_attempt` against
a never-initialised path still passes unchanged.

### C — atomic, write-side attempt-number derivation

**C1. A single-statement derivation exists.** `effort_db.py` defines
`insert_attempt_derived(path: Path, **fields: Any) -> "tuple[int, int]"` which
requires `story_id`, `agent_role` and `ts` (but **not** `attempt_number`), and
inside one `BEGIN IMMEDIATE` transaction executes a single `INSERT ... SELECT`
whose `attempt_number` expression is
`COALESCE(MAX(attempt_number), 0) + 1` over `attempts` filtered by the same
`story_id` and `agent_role` — both bound as SQL parameters, never interpolated.
It returns `(row_id, attempt_number)`.

**C2. The derivation is atomic under concurrency.** A test in
`test_effort_concurrency.py` runs 10 threads, each calling
`insert_attempt_derived` for the *same* `(story_id, agent_role)` pair, then
asserts `sorted(r["attempt_number"] for r in rows) == list(range(1, 11))` — no
duplicates, no gaps. This test is the acceptance criterion for CER-096's
"atomic write-side attempt-number derivation" and must fail if the
implementation is changed back to a read-then-write pair.

**C3. `insert_attempt` is unchanged.** The existing `insert_attempt` keeps its
signature, its `_REQUIRED_FIELDS` validation (`attempt_number` still required),
its unknown-field `ValueError`, and its return type. Every existing test in
`tests/pairmode/test_effort_db.py` that exercises it passes by its original name.

**C4. `record_effort` can defer derivation.** `effort_recorder.record_effort`'s
`attempt_number` keyword becomes `attempt_number: int | None = 1`; when it is
`None` the recorder calls `insert_attempt_derived` and returns the inserted row
id, otherwise it calls `insert_attempt` exactly as today. A test asserts both
branches: an explicit `attempt_number=3` writes `3`, and `attempt_number=None`
writes `1` on an empty database and `2` on the second call for the same pair.

**C5. The PostToolUse path stops pre-computing.** In
`subagent_transcript.record_attempt_from_transcript`, the
`effort_db.next_attempt_number(...)` call at `subagent_transcript.py:1356-1363`
and its `except Exception: attempt_number = 1` fallback are removed, and
`record_effort` is called with `attempt_number=None`.
`grep -n 'next_attempt_number' skills/pairmode/scripts/subagent_transcript.py`
returns nothing.

**C6. The stale serialism comment in the code is corrected.** The comment block
at `subagent_transcript.py:1348-1355` no longer claims the race is a non-issue
because the loop is serial. Its replacement states that the ordinal is now
derived atomically on the write side (`insert_attempt_derived`, CER-096) because
phase 109 makes parallel spawns real. A grep for the phrase
`serial (no-nested-spawning)` in `skills/pairmode/scripts/` returns nothing.

**C7. `next_attempt_number` survives as a read-only helper.** The function is not
deleted — it still exists, still never raises, still returns `1` on every failure
path, and all of `tests/pairmode/test_effort_db.py`'s `next_attempt_number` tests
(`test_effort_db.py:515-556`) pass unchanged. Its docstring gains one sentence
stating that it is **advisory/read-only** since CER-096 and must not be used to
compute a value that is then written back — `insert_attempt_derived` is the
write path.

### D — sweep ownership and cursor

**D1. `pending_reconcilable` accepts an ownership filter.** Its signature gains
`output_prefix: "str | None" = None`. When `output_prefix` is a non-empty
string, the query adds `AND output_file LIKE ? || '%'` with the prefix bound as
a parameter (never interpolated, never with a caller-supplied wildcard reaching
the pattern unescaped — if the prefix contains `%` or `_`, use an
`ESCAPE` clause). Anything else (`None`, `""`, a non-string) means "no ownership
filter", byte-identical to today's behaviour. Tests assert: no prefix returns
both rows; a prefix matching one row's `output_file` returns only that row; a
prefix matching neither returns `[]`; a prefix containing `%` does not match rows
it should not.

**D2. `pending_reconcilable` accepts an ordering direction.** Its signature gains
`order: str = "newest"`, accepting `"newest"` (`ORDER BY id DESC`, today's
behaviour and the default) and `"oldest"` (`ORDER BY id ASC`). Any other value
falls back to `"newest"` without raising. The direction is chosen by branching in
Python between two literal `ORDER BY` clauses — it is never string-formatted into
the SQL from the parameter value.

**D3. The sweep visits both ends, so no pending row starves.**
`subagent_transcript.reconcile_pending_attempts` fetches its candidate set as the
union of two bounded queries — up to `limit` rows with `order="newest"` and up to
`RECONCILE_OLDEST_ROWS` rows with `order="oldest"` — deduplicated by `id`,
preserving newest-first processing order. `RECONCILE_OLDEST_ROWS: int = 2` is a
module constant in `subagent_transcript.py` with a comment giving the reason.
Both queries receive the same `max_age_days` and `output_prefix` values.

**D4. Starvation is regression-tested.** A test inserts 12 pending rows, runs the
sweep with a stub `read_completed_spawn` that records which row ids it was asked
about and returns `None` for all of them, and asserts that across three
consecutive sweeps the set of visited ids includes the **lowest** id in the table.
Under the pre-change `ORDER BY id DESC LIMIT 5` this assertion fails.

**D5. The sweep exposes ownership but does not invent it.**
`reconcile_pending_attempts` accepts `output_prefix: "str | None" = None` and
forwards it to both `pending_reconcilable` calls. Its default is `None`, and
neither `hooks/session_start.py` nor the internal call sites at
`subagent_transcript.py:1333` and `:1465` pass a value — production behaviour is
unchanged except for D3's two-ended fetch. The docstring states that deriving a
real session-scoped prefix is INFRA-285's (CER-097's) job and names it, so the
next reader does not conclude the parameter is dead code.

**D6. Bounded work is preserved.** The sweep issues at most two
`pending_reconcilable` queries and calls `read_completed_spawn` at most
`limit + RECONCILE_OLDEST_ROWS` times per invocation. A test asserts the
`read_completed_spawn` call count never exceeds that bound even with 50 pending
rows.

### Cross-cutting

**E1. Hook-path cost does not grow.** No logging, no `ANALYZE`, no `VACUUM`, no
retry loop in Python, and no new file writes are added to any hook-invoked path.
The only new work per recording is two pragmas on connect (A1) — and `init_db`'s
six DDL statements are now *removed* from the per-recording path (B4), so the net
change is a reduction. This is the "hooks are thin relays only" constraint's
rationale, not just its letter.

**E2. No `docs/architecture.md` edit.** The diff contains no change to
`docs/architecture.md`. The stale serialism tradeoff paragraph
(`docs/architecture.md:2459-2468`) and the WAL/derivation documentation are
INFRA-286's, per `docs/phases/phase-109.md` § Ordering ("INFRA-286 … rewrites the
serialism comments the other stories obsolete"). The in-code comment is corrected
here (C6) because it sits inside a function this story rewrites.

**E3. The CER row carries a RESOLVED note.** `docs/cer/backlog.md`'s `CER-096`
row gains a bolded `**RESOLVED Phase 109 — INFRA-284 …**` note appended to the
Finding cell, naming all four items and stating explicitly that the
architecture.md serialism prose is amended by INFRA-286 and that session-scoped
sweep ownership is wired by INFRA-285 — the note must not claim work this story
did not do. The row's `Phase` cell still reads `109`. No row is deleted or moved
between quadrants.

**E4. `schema_introduces` stays `false`.** WAL is a journal mode, not a schema
object; no new table, view, or state file is created, so no § Schema delivery row
is owed in `docs/phases/phase-109.md`.

**E5. No recording semantics change beyond the ordinal.** The diff contains no
edit to `reconcile_attempt`'s update logic, `set_spawn_ref`,
`_contained_spawn_output`, `read_completed_spawn`'s parsing, `parse_worker_outcome`,
`classify_pending_reason`, the quiescent-retirement path, or any
`bump_attempt_count` call site. Threading `output_prefix`/`order` through
signatures is permitted and expected.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build the four items in order (A, B, C, D) and run the effort test files after
each — they share fixtures, and a mistake in A is far easier to isolate before C
lands on top of it.

**0. Rebase check.** Confirm INFRA-264 and INFRA-266 are in your `HEAD`
(`## Requires`). Re-read `init_db`, `insert_attempt`, `next_attempt_number`,
`pending_reconcilable` and `reconcile_pending_attempts` as they exist now. Every
line number in this spec is an anchor from the post-INFRA-266 state; if a
function has moved, work from its current body. Never revert an earlier story's
behaviour to make an assertion here easier to satisfy — if a genuine conflict
exists, stop and report it as `FAIL-CAUSE`.

**1. (A) Introduce `_connect` and route every connection through it.** Define
`BUSY_TIMEOUT_SECONDS`/`BUSY_TIMEOUT_MS` next to `PENDING_MAX_AGE_DAYS`, then:

```python
def _connect(resolved: Path) -> sqlite3.Connection:
    """Open effort.db with the concurrency configuration (CER-096).

    ``timeout=`` covers Python's own lock wait; ``PRAGMA busy_timeout``
    covers SQLite's internal one — they are different mechanisms and both
    are needed. WAL itself is set once, persistently, by init_db.
    """
    conn = sqlite3.connect(str(resolved), timeout=BUSY_TIMEOUT_SECONDS)
    try:
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.Error:
        pass
    return conn
```

Then mechanically replace all eleven `conn = sqlite3.connect(str(resolved))`
sites with `conn = _connect(resolved)`. Change nothing else inside those
functions — every `try/finally: conn.close()` and every never-raises contract
stays exactly as it is.

In `init_db`, add `PRAGMA journal_mode = WAL` immediately after opening the
connection, wrapped in `try/except sqlite3.Error: pass`. **WAL is persistent
database state**, so setting it once here is enough; do not add it to `_connect`,
where it would cost a pragma round-trip on every call for no benefit. Say that in
a comment — the "set it everywhere to be safe" reflex is the obvious wrong
change a future reader will make.

Do **not** retrofit the `sqlite3.connect` sites in `pairmode_effort.py`,
`context_budget.py`, `context_health.py`, `drift_evidence.py`,
`refresh_effort_baseline.py`, `context_budget_check.py` or `flex_build.py`. They
are read paths and they inherit WAL from the file itself; widening the diff
across seven more modules is out of scope (below).

**2. (B) Add `ensure_db` and stop calling `init_db` per recording.** Add
`_INITIALISED: set[str] = set()` and `ensure_db` to `effort_db.py`, immediately
after `init_db`. `ensure_db` must consult **both** the cache and
`resolved.exists()` — a cached path whose file has been deleted (test teardown,
an operator `rm`) must re-initialise, or the cache turns a recoverable state into
a permanent one. In `effort_recorder.record_effort`, replace the
`resolve_effort_db_path` + `init_db` pair with `ensure_db(...)`.

The set is deliberately process-local and unbounded: a process opens a handful of
distinct databases at most, and a bounded cache would need eviction logic that
could re-introduce the very cost it exists to remove.

**3. (C) Derive the attempt number on the write side.** Add
`insert_attempt_derived` to `effort_db.py` next to `insert_attempt`. Build it as
a single statement:

```sql
INSERT INTO attempts (<columns>)
SELECT <placeholders-for-non-derived-columns>,
       COALESCE(MAX(attempt_number), 0) + 1
  FROM attempts
 WHERE story_id = ? AND agent_role = ?
```

Order the column list so the derived expression's position matches
`attempt_number`'s position in the INSERT column list; build both lists from
`_INSERT_COLUMNS` so a future column addition cannot silently misalign them.
Wrap the statement in an explicit `BEGIN IMMEDIATE` (via
`conn.execute("BEGIN IMMEDIATE")`, with `isolation_level=None` on the connection
or `conn.commit()` afterwards — pick one and be consistent) so the read of
`MAX(attempt_number)` and the insert occupy the same write lock.

`COALESCE(MAX(...), 0) + 1` rather than `COUNT(*) + 1` is deliberate and must be
commented: `COUNT(*)` re-derives an ordinal that a deleted or historically
`attempt_number = 1` row would make collide, whereas `MAX` is monotone over
whatever is actually there. Note in the docstring that historical rows written
before INFRA-257 all carry `attempt_number = 1`, so the first derived value for
such a pair will be `2` — that is correct and no backfill is performed.

Then change `record_effort`'s `attempt_number` to `int | None = 1` (default
unchanged, so no existing caller changes behaviour) and branch to
`insert_attempt_derived` when it is `None`. Finally, in
`record_attempt_from_transcript`, delete the `next_attempt_number` pre-compute
and pass `attempt_number=None`, replacing the serialism comment per C6.

Leave `next_attempt_number` in place. It is used by nothing on the write path
after this change, but it is a legitimate read helper with six tests, and
deleting it would widen the diff into `test_effort_db.py` for no gain. Mark it
advisory in the docstring instead.

**4. (D) Give the sweep ownership and a two-ended cursor.** Add `output_prefix`
and `order` to `pending_reconcilable`. The function currently branches between a
cutoff and a no-cutoff query; do not multiply that into four literal query
strings — build the `WHERE` clause as a list of fragments with a parallel params
list, and select the `ORDER BY` from a two-entry literal mapping. The
never-raises contract (`return []` on every failure) is unchanged.

For the `LIKE` filter, escape `%`, `_` and `\` in the prefix and append
`ESCAPE '\'`. A prefix is harness-derived, not user input, but an unescaped `%`
would silently widen an *ownership* filter, which is the one thing this parameter
exists to narrow.

In `reconcile_pending_attempts`, add `RECONCILE_OLDEST_ROWS = 2` next to
`RECONCILE_MAX_ROWS`, fetch both ends, and merge preserving newest-first order
and de-duplicating by `id`. Add the `output_prefix` parameter and forward it to
both calls, but **do not wire a session identity at any call site** — that is
INFRA-285's story, and guessing at a prefix shape now would either be dead code
or a conflict to unpick later. The docstring must say so by name.

**5. Tests.** Add to `tests/pairmode/test_effort_db.py` (A1–A4, B1–B5, C1, C3,
C4, C7, D1, D2) and `tests/pairmode/test_subagent_transcript.py` (C5, C6, D3–D6),
following each file's existing fixture style. Create
`tests/pairmode/test_effort_concurrency.py` for the genuinely-concurrent cases
(A5, A6, C2) — they need threads and a shared database file, which does not fit
either existing file's fixtures. Use `threading`/`concurrent.futures` from the
standard library; no new dependency, and no `multiprocessing` (it is slow and
flaky in CI for a test that threads already exercise, since each `_connect` call
opens its own connection).

Keep the concurrency tests deterministic: join every thread, assert on the final
row set rather than on timing, and never `sleep` as a synchronisation primitive —
use a `threading.Barrier` to make the workers contend on purpose.

**6. CER row.** Write E3's RESOLVED note. Be precise about the split with
INFRA-285 and INFRA-286 — an overclaiming resolution note is worse than an open
row.

**7. Ideology note (Step 4a — resolved inline, no conflict).** Three entries
shaped this spec. *"Hooks are thin relays only"* forbids the tempting fixes here:
a Python retry loop, logging every swallowed `OperationalError`, or a repair pass
over stale rows — all add hook-path work. The constraint is satisfied instead by
pushing the cost into SQLite's own busy handler and by *removing* `init_db` from
the recording path (E1), which makes the hook cheaper than before.
*"Sidebar owns all state writes"* is why item D's cursor is derived from the query
(a two-ended fetch) rather than persisted in a cursor file or a new table — a
hook must not acquire a new state-write responsibility, and a new table would owe
a management surface. *"Rationale-bearing decisions over bare rules"* is why four
reasons must survive into the code as comments rather than living only here: why
WAL is set in `init_db` and not in `_connect`; why `ensure_db` checks file
existence as well as the cache; why the derivation uses `MAX` not `COUNT`; and
why `output_prefix` exists but is unwired.

## Tests

Run from the story worktree root. After each item:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_effort_concurrency.py \
  -q 2>&1 | tail -30
```

Then the adjacent effort and context surface, to catch collateral damage:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_record_attempt.py \
  tests/pairmode/test_record_attempt_seed.py \
  tests/pairmode/test_record_attempt_usage_parsing.py \
  tests/pairmode/test_record_attempt_companion.py \
  tests/pairmode/test_pairmode_effort.py \
  tests/pairmode/test_effort_guardrail.py \
  tests/pairmode/test_refresh_effort_baseline.py \
  tests/pairmode/test_context_health.py \
  tests/pairmode/test_drift_evidence.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -40
```

Machine-checkable Ensures:

```bash
grep -c 'sqlite3.connect' skills/pairmode/scripts/effort_db.py        # must print 1
grep -n 'init_db' skills/pairmode/scripts/effort_recorder.py          # must print nothing
grep -n 'next_attempt_number' skills/pairmode/scripts/subagent_transcript.py  # must print nothing
grep -rn 'serial (no-nested-spawning)' skills/pairmode/scripts/       # must print nothing
git diff --name-only main -- docs/architecture.md                     # must print nothing (E2)
grep 'CER-096' docs/cer/backlog.md | grep -c 'RESOLVED Phase 109'     # must print 1
```

Acceptance:

- every new test from A1–A6, B1–B5, C1–C7, D1–D6 passes;
- the concurrency tests (A6, C2, D4) each fail when their fix is reverted —
  verify this once by hand for C2 before committing, since a derivation test that
  passes against the old read-then-write code is worthless;
- every pre-existing test in `test_effort_db.py` and
  `test_subagent_transcript.py` passes by its original name;
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so in the build result.

## Out of scope

- **`docs/architecture.md`.** The serialism tradeoff paragraph
  (`:2459-2468`) and the § Effort tracking documentation of WAL, the atomic
  derivation, and sweep ownership belong to INFRA-286, which the phase doc's
  § Ordering places last precisely so it can rewrite everything the other stories
  obsolete in one pass (E2).
- **Session identity and session-scoped sweep ownership.** This story builds the
  `output_prefix` mechanism and leaves it unwired; deriving a session's spawn-output
  prefix, session-scoped context accounting, atomic `state.json` writers and the
  advisory lock are CER-097 / INFRA-285.
- **`.companion/attempt_counter.json`.** The retry-ladder failure counter is a
  different number in a different file; keying it per story is INFRA-282.
- **Retrofitting the seven other modules' `sqlite3.connect` sites**
  (`pairmode_effort.py`, `context_budget.py`, `context_budget_check.py`,
  `context_health.py`, `drift_evidence.py`, `refresh_effort_baseline.py`,
  `flex_build.py`). They are read paths, they inherit WAL from the database file,
  and CER-096 names the writer surface.
- **Backfilling or repairing existing `attempt_number` values.** Rows written
  before INFRA-257 keep `attempt_number = 1` permanently — unchanged since
  INFRA-257, and a data-repair pass needs its own reversibility argument.
- **Deleting, annotating, or retiring the existing permanently-pending rows** in
  flex's own `.companion/effort.db`. The two-ended sweep reaches more of them;
  it does not clean them up.
- **A cross-process lock, a connection pool, or a write queue.** WAL plus
  `busy_timeout` is the proportionate fix for one-orchestrator parallelism; a lock
  manager is a design for multi-orchestrator operation, which
  `docs/phases/phase-109.md` § Scope statement puts out of scope for the whole
  phase.
- **`ANALYZE`, `VACUUM`, new indices, or any further SQLite tuning.** INFRA-266
  added the one index the sweep needs; each additional index costs write time on a
  hook path.
- **A management UI or CLI view for the attempts table.** No new persistent schema
  object is introduced (E4); `pairmode_effort.py`'s reports remain the surface.
