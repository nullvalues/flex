---
id: INFRA-266
rail: INFRA
title: "Effort-DB hardening: bounded pending_reconcilable scan, output_file containment, path-guard parity (CER-088, CER-089, CER-016)"
status: complete
phase: "104"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/record_attempt.py
  - skills/pairmode/scripts/pairmode_effort.py
touches:
  - docs/architecture.md
  - docs/cer/backlog.md
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_record_attempt.py
  - tests/pairmode/test_pairmode_effort.py
  - docs/stories/INFRA/INFRA-266.md
---

## Context

Three long-open effort-DB findings are closed here. None of them is a
recording-semantics bug — that is INFRA-264's job, immediately before this
story. All three are **cost and containment** defects on paths that a hook
invokes, which is why they are grouped: they touch the same four files, they
share one test surface, and each is small enough that spending three separate
worktree round-trips on them would cost more than the fixes.

**A — CER-088 (MEDIUM): the pending sweep is an unindexed full-table scan on a
hook path.** `effort_db.pending_reconcilable` (`effort_db.py:394-431`) issues
`SELECT * FROM attempts WHERE tokens_total IS NULL AND output_file IS NOT NULL
ORDER BY id DESC LIMIT ?`. The three indices created by `init_db`
(`_SCHEMA_INDICES`, `effort_db.py:104-108`) cover `story_id`, `phase`, and
`rail` only — nothing in the predicate — so SQLite scans every row on every
call. `LIMIT` bounds the *result* size, not the *scan* cost. The caller is
`subagent_transcript.reconcile_pending_attempts`, invoked from both
`hooks/session_start.py` and the PostToolUse `Task`/`Agent` branch — the
"hooks are thin relays only" constraint (`docs/ideology.md`) exists precisely so
these paths stay millisecond-thin, and an unindexed scan violates its rationale
even while flex's own 362-row table keeps the symptom invisible. There is a
second unboundedness in the same query that the finding did not name: nothing
excludes rows too old to ever reconcile. A spawn whose `/tmp` output file has
been evicted is permanently pending, and because the sweep takes the newest
`RECONCILE_MAX_ROWS = 5` first, an accumulation of them is harmless today but
turns the sweep into pure waste as the table grows.

**B — CER-089 (LOW): `read_completed_spawn` opens a persisted path with no
containment.** `subagent_transcript.read_completed_spawn`
(`subagent_transcript.py:479-577`) takes the `output_file` string that was
written into `attempts.output_file` at PostToolUse time and opens it with no
`resolve()` and no check on where it points. The audit correctly graded it
observational — the value is harness-generated launch metadata, the same trust
category as hook-payload `cwd` — but the parsed content flows straight into
`effort.db` (`tokens_*`, `outcome`, `notes`), so a wrong path is a data-integrity
issue as much as a traversal one, and the fix is cheap. The live shape (rows
357-362, 2026-07-25) is
`/tmp/claude-<uid>/<project-slug>/<session-id>/tasks/<hash>.output`.

**C — CER-016 (LOW): path-guard parity.** The finding says
`resolve_effort_db_path` applies only `_depth_guard` and not containment. That
half is **already fixed** — INFRA-058 (commit `ee584df`) added the
`resolve().relative_to(project_dir.resolve())` check at `effort_db.py:189-193`;
the row was simply never closed. What *is* still open is the part the finding
called "the same shape mirrored in record_attempt.py and pairmode_effort.py".
Both files bypass `resolve_effort_db_path` entirely when an explicit
`--db-path` is supplied and do their own resolution with **neither** guard:
`record_attempt.py:277-281` and `pairmode_effort.py:141-148` each do
`Path(db_path)`, join it to `project_path` if relative, and hand the result
straight to `init_db`/`sqlite3.connect`. So the containment rule exists in one
of three places, which is the worst of both worlds: a reader of `effort_db.py`
reasonably concludes the surface is guarded. The fix is to single-source it, not
to write the check a third and fourth time.

**Sequencing — this story is built on top of INFRA-264.** INFRA-264 (CER-091)
is the story immediately before this one in the phase build order and edits two
of the same files (`subagent_transcript.py`, `effort_db.py`) for the
*recording-semantics* defects: the PostToolUse branch not firing for a repeat
spawn, `reconcile_attempt` committing tokens without an outcome, the
permanent-pending leak's diagnostic surface, and the reconciliation-time
attempt-counter resurrection. This story's worktree must be cut from a `main`
that already contains INFRA-264's merge, and the scopes are kept disjoint by
construction: **this story changes no recording semantics.** It does not touch
`reconcile_attempt`'s update logic, `record_attempt_from_transcript`'s
recording branch, `bump_attempt_count` call sites, `parse_worker_outcome`, or
what counts as a completed spawn. Where the two stories genuinely interact —
INFRA-264 may add a read-only pending-age diagnostic over the same query — this
story is specified so the interaction is safe: the new age cutoff is an
**opt-in keyword argument defaulting to "no cutoff"**, applied only at the
sweep call site, so every other caller of `pending_reconcilable` (including any
diagnostic INFRA-264 added) keeps seeing the complete pending set. Hiding
permanently-pending rows from a diagnostic whose entire purpose is to surface
them would be a direct regression of INFRA-264.

## Requires

- **INFRA-264 is complete and merged to `main`**, and this story's worktree is
  cut from a `HEAD` that contains it. Verify before building:
  `git log --oneline -1 --grep 'INFRA-264'` returns a commit reachable from
  `HEAD`. If INFRA-264's diff has changed any function this story edits
  (`pending_reconcilable`, `read_completed_spawn`,
  `reconcile_pending_attempts`, `init_db`), rebase this story's edits onto its
  version — do not revert or rewrite its changes.
- INFRA-263 and INFRA-265 are complete (phase build order 263 → 264 → 265 →
  266); they touch `flex_build.py`, not this story's files.
- `skills/pairmode/scripts/effort_db.py` exposes `_depth_guard`,
  `resolve_effort_db_path`, `init_db`, `pending_reconcilable`,
  `reconcile_attempt`, `set_spawn_ref`, and the module-level `_SCHEMA_TABLE`,
  `_MIGRATIONS`, `_SCHEMA_INDICES` constants.
- `skills/pairmode/scripts/subagent_transcript.py` exposes
  `read_completed_spawn`, `reconcile_pending_attempts`, `RECONCILE_MAX_ROWS`,
  and `RECONCILE_MAX_LINES`.
- `docs/cer/backlog.md` contains a `CER-016` row under `## Do Later` and
  `CER-088` / `CER-089` rows under `## Do Much Later`, each with a `Phase` cell
  of `—`.
- `attempts.ts` is written by every writer as
  `datetime.now(tz=timezone.utc).isoformat()`
  (`effort_recorder.py:60-61`, `record_attempt.py`), i.e. a lexicographically
  orderable ISO-8601 UTC string — the age cutoff in item A depends on this.

## Ensures

Grouped by item. Every assertion is checkable from the diff or by running a
command.

### A — CER-088: the pending sweep is indexed and age-bounded

**A1. A partial index covering the pending predicate exists.**
`skills/pairmode/scripts/effort_db.py` creates an index named
`idx_attempts_pending` on the `attempts` table whose definition includes
`WHERE tokens_total IS NULL AND output_file IS NOT NULL`. After
`effort_db.init_db(path)` runs against a fresh database,
`SELECT name FROM sqlite_master WHERE type='index' AND name='idx_attempts_pending'`
returns one row.

**A2. The new index is created *after* the column migrations, not with the
existing three.** The statement creating `idx_attempts_pending` is executed
after the `_MIGRATIONS` loop in `init_db`, in its own
`try/except sqlite3.OperationalError`. `_SCHEMA_INDICES` still contains exactly
its original three `story_id`/`phase`/`rail` statements. Verified by a test that
builds a *pre-INFRA-258-shaped* database (an `attempts` table with no
`output_file` and no `agent_id` column), calls `init_db` on it, and asserts
`init_db` did not raise, the two ALTER-added columns now exist, and
`idx_attempts_pending` exists.

**A3. The query planner uses the index.** A test executes
`EXPLAIN QUERY PLAN` for the exact statement `pending_reconcilable` issues
(both variants: with and without the age cutoff) against a database with at
least one pending and one non-pending row, and asserts the concatenated plan
text contains `idx_attempts_pending` in both cases.

**A4. `pending_reconcilable` accepts an opt-in age cutoff, defaulting to
off.** Its signature is
`pending_reconcilable(path, limit, *, max_age_days: "int | None" = None)`.
With `max_age_days=None` (the default) the returned rows are identical to
today's behaviour — a test inserts a pending row with a `ts` two years in the
past and asserts the default call still returns it. With
`max_age_days=14` the same row is excluded while a pending row stamped
"now" is returned. The cutoff is bound as a SQL parameter, never interpolated
into the query text.

**A5. A non-positive or non-integer `max_age_days` is treated as "no cutoff",
never an error.** `pending_reconcilable(db, 5, max_age_days=0)`,
`(..., max_age_days=-1)`, and `(..., max_age_days="14")` each return the same
rows as `max_age_days=None` and raise nothing. (The function's
never-raises contract, `effort_db.py:402`, is unchanged: every failure path
still returns `[]`.)

**A6. The hook sweep passes the cutoff; nothing else does.**
`subagent_transcript.reconcile_pending_attempts` calls
`effort_db.pending_reconcilable` with an explicit
`max_age_days=RECONCILE_MAX_AGE_DAYS`. `RECONCILE_MAX_AGE_DAYS` is defined in
`subagent_transcript.py` as `effort_db.PENDING_MAX_AGE_DAYS` (single source, not
a second literal), and `effort_db.PENDING_MAX_AGE_DAYS == 14`.
`grep -n 'pending_reconcilable' skills/pairmode/scripts/` shows no other call
site passing a non-`None` `max_age_days`.

**A7. `reconcile_pending_attempts` exposes the cutoff for callers and tests.**
It accepts `max_age_days: "int | None" = None` meaning "use
`RECONCILE_MAX_AGE_DAYS`", and an explicitly passed value overrides it. Passing
`max_age_days=None` never means "no cutoff" at this call site — the sweep is
always bounded.

### B — CER-089: `read_completed_spawn` is contained

**B1. Containment helper exists and is pure.**
`subagent_transcript.py` defines `_contained_spawn_output(output_file,
tasks_root=None) -> "Path | None"` which returns a resolved `Path` for an
acceptable spawn-output path and `None` for everything else. It never raises,
never opens the file, and performs no writes.

**B2. The default allow-rule is temp-root + a `tasks` path component.** With
`tasks_root=None`, a candidate is accepted only when all of the following hold
on `Path(output_file).resolve()`: it is contained under one of the roots
returned by the module's `default_spawn_output_roots()` (the resolved
`tempfile.gettempdir()`, plus a resolved `$TMPDIR` when set and distinct); the
literal component `"tasks"` appears in its `.parts`; and it `is_file()`.
`SPAWN_TASKS_DIR_NAME` is a module constant equal to `"tasks"`.
(`spec-preflight` warns that `SPAWN_TASKS_DIR_NAME` has no definition in the
source tree — intentional: this story creates it.)

**B3. An explicit `tasks_root` is a strict containment root.** When
`tasks_root` is given, the candidate must satisfy
`resolved.relative_to(Path(tasks_root).resolve())` and `is_file()`; the
temp-root and `tasks`-component rules do not apply. This is the injection point
tests use.

**B4. `read_completed_spawn` refuses uncontained paths before opening.** Its
signature gains `*, tasks_root: "Path | str | None" = None`, and its first
action on a non-`None` `output_file` is to route through
`_contained_spawn_output`; a `None` result returns `None` immediately, with no
`open()` call. Verified by tests asserting:
  - a path outside the temp root (e.g. a file created under the repo's own
    `tests/` tree or any non-temp `tmp` sibling) → `None`;
  - a `..` traversal string that resolves outside the given `tasks_root` →
    `None`;
  - a symlink placed *inside* the tasks root whose target is outside it →
    `None` (the `resolve()` is what makes this work; a test asserting this is
    required);
  - a directory rather than a file → `None`;
  - a well-formed, completed spawn file at the real shape
    `<tmp>/claude-x/<slug>/<session>/tasks/<id>.output` → the usual populated
    dict, unchanged from today.

**B5. The sweep threads the root through.**
`reconcile_pending_attempts` accepts `tasks_root: "Path | str | None" = None`
and forwards it to every `read_completed_spawn` call. Its default (`None`)
means "use the default allow-rule" — i.e. production behaviour is unchanged
except that uncontained paths are now skipped.

**B6. No existing INFRA-258/INFRA-264 test is deleted.** Tests in
`tests/pairmode/test_subagent_transcript.py` that build fixture output files
are adjusted to a realistic location (a `tasks/` subdirectory of `tmp_path`) or
pass `tasks_root=`, but every existing test case name still exists and still
passes.

**B7. Rejection is silent-by-contract but documented.**
`read_completed_spawn`'s docstring states that an uncontained path yields
`None` and names the failure mode it creates (a row stays pending forever), so
a future reader debugging a stuck row finds the guard rather than rediscovering
it. No logging is added — this is a hook path.

### C — CER-016: one containment rule, three call sites

**C1. A single shared resolver exists.** `effort_db.py` defines a public
`resolve_db_path_arg(project_dir: Path, db_path: "str | Path | None") -> Path`
which: returns `resolve_effort_db_path(project_dir)` unchanged when `db_path`
is `None`; otherwise joins a relative `db_path` to `project_dir`, applies
`_depth_guard`, then applies `resolve().relative_to(Path(project_dir).resolve())`
and raises `ValueError` when either guard fails. The raised message names both
the rejected path and `project_dir`.

**C2. The asymmetry is deliberate and documented.** `resolve_db_path_arg`'s
docstring states that an escaping value from `.companion/state.json` falls back
silently to the default (unchanged behaviour, `effort_db.py:189-193`) while an
escaping *explicit* `db_path` argument raises — with the reason: a config value
is project-owned and a silent default is recoverable, whereas an operator who
named a specific file must not have their rows silently written somewhere else.

**C3. `record_attempt.py` delegates.** The block at `record_attempt.py:277-282`
is replaced by a single `_effort_db.resolve_db_path_arg(project_path, db_path)`
call wrapped in `try/except ValueError`, which prints the message to stderr and
exits non-zero (exit code `2`). `grep -n 'Path(db_path)' skills/pairmode/scripts/record_attempt.py`
returns nothing.

**C4. `pairmode_effort.py` delegates.** `_resolve_db` (`pairmode_effort.py:141-148`)
becomes a thin wrapper over `_effort_db.resolve_db_path_arg`; every one of its
five call sites behaves identically for valid input, and an escaping
`--db-path` exits non-zero with the message on stderr rather than reading an
out-of-project database.
`grep -n 'Path(db_path)' skills/pairmode/scripts/pairmode_effort.py` returns
nothing.

**C5. Containment is regression-tested at the source.**
`tests/pairmode/test_effort_db.py` asserts, for `resolve_db_path_arg`:
`None` → the default `<project>/.companion/effort.db`; a relative path inside
the project → accepted and absolute; an absolute path outside `project_dir` →
`ValueError`; a `../../escape.db` relative path → `ValueError`; a symlink
inside the project pointing outside it → `ValueError`; a shallow path (e.g.
`/x`) → `ValueError`. The existing `resolve_effort_db_path` tests still pass
unchanged.

**C6. CLI-level regression tests exist.** `tests/pairmode/test_record_attempt.py`
and `tests/pairmode/test_pairmode_effort.py` each gain one test invoking the
CLI with a `--db-path` that escapes `--project-dir`, asserting a non-zero exit
and that no database file was created outside the project directory.

### Cross-cutting

**D1. Documentation.** `docs/architecture.md` § Effort tracking records, in at
most one short paragraph each: the `idx_attempts_pending` partial index and why
it is created after the migrations; the sweep's age bound and why the cutoff is
opt-in rather than baked into the shared query; and the two containment rules
(spawn `output_file` under the tasks root, `--db-path` under `project_dir` via
`resolve_db_path_arg`). No new `##`-level heading is added.

**D2. All three CER rows carry RESOLVED notes.** `docs/cer/backlog.md`'s
`CER-088`, `CER-089`, and `CER-016` rows each gain a bolded
`**RESOLVED Phase 104 — INFRA-266 …**` note appended to the Finding cell,
naming what was actually done, and each row's `Phase` cell reads `104`. No row
is deleted or moved between quadrants (`docs/cer/backlog.md:6-7`). CER-016's
note must additionally state that the `resolve_effort_db_path` half was already
closed by INFRA-058 and that this story closed the `record_attempt.py` /
`pairmode_effort.py` mirrors — the row must not claim work it did not do.

**D3. No recording semantics change.** The diff contains no edit to
`effort_db.reconcile_attempt`'s update logic, `effort_db.insert_attempt`,
`subagent_transcript.record_attempt_from_transcript`,
`parse_worker_outcome`, `_derive_attribution`, or any `bump_attempt_count` call
site. (Signature-only threading of `tasks_root`/`max_age_days` through
`reconcile_pending_attempts` is permitted and expected.)

**D4. `schema_introduces` stays `false`.** An index on an existing table is not
a new persistent schema object; no management-surface row is owed in
`docs/phases/phase-104.md` § Schema delivery. No new table, no new state file.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build the three items in order (A, B, C) and run the suite after each — they
share test files and a mistake in A is easier to isolate before B lands on top.

**0. Rebase check.** Confirm INFRA-264 is in your `HEAD` (`## Requires`). Read
the current bodies of `pending_reconcilable`, `read_completed_spawn`,
`reconcile_pending_attempts`, and `init_db` as they exist *after* INFRA-264 —
the line numbers cited throughout this spec are pre-INFRA-264 and are anchors,
not coordinates. If INFRA-264 changed one of these functions, your edit layers
on top of its version. Never revert its behaviour to make an assertion here
easier to satisfy; if a genuine conflict exists, stop and report it as
`FAIL-CAUSE` rather than resolving it by deleting its work.

**1. (A) Add the partial index, after the migrations.** In `effort_db.py`, add
a new module constant next to `_SCHEMA_INDICES`:

```python
#: Indices that reference ALTER-added columns and therefore must be created
#: AFTER _MIGRATIONS has run (CER-088). Putting these in _SCHEMA_INDICES would
#: crash init_db on exactly the legacy (pre-INFRA-258) databases the migrations
#: exist to upgrade, because output_file does not exist yet at that point.
_POST_MIGRATION_INDICES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_attempts_pending "
    "ON attempts(id DESC) "
    "WHERE tokens_total IS NULL AND output_file IS NOT NULL;",
)
```

In `init_db`, after the existing `for migration in _MIGRATIONS:` loop and
before `conn.commit()`, execute each entry in its own
`try/except sqlite3.OperationalError: pass` — an ancient SQLite without partial
index support must degrade to "no index", never break `init_db`. Do not touch
`_SCHEMA_INDICES`.

If A3's `EXPLAIN QUERY PLAN` assertion does not name the index for the
cutoff-bearing variant, you may change the indexed columns (e.g.
`ON attempts(ts DESC, id DESC)`) — but keep the partial `WHERE` clause, keep
the name `idx_attempts_pending`, and keep the assertion for both variants.
Do not "fix" it by running `ANALYZE` (out of scope) or by dropping the
assertion.

**2. (A) Add the opt-in age cutoff.** Define
`PENDING_MAX_AGE_DAYS: int = 14` at module level in `effort_db.py` with a
one-line comment giving the reason for the number: `/tmp` spawn-output files do
not survive that long, so a pending row older than the window can never
reconcile and scanning for it is pure cost. Change the signature to
`pending_reconcilable(path, limit, *, max_age_days: "int | None" = None)`.
Inside, when `max_age_days` is a positive `int`, compute
`cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()`
and append `AND ts >= ?` to the `WHERE` clause, binding `cutoff` as a
parameter alongside `limit`. Anything else (`None`, `0`, negative, a string,
a bool) → no cutoff clause at all. Both `datetime`/`timedelta`/`timezone` are
already imported (`effort_db.py:43`).

The lexicographic `ts >= ?` comparison is valid *only* because every writer
stamps `datetime.now(tz=timezone.utc).isoformat()` (see `## Requires`). Say so
in a comment — a future writer using a different format would silently break
the bound, and the failure would look like "reconciliation stopped working."

**3. (A) Wire the cutoff at the sweep only.** In `subagent_transcript.py`,
next to `RECONCILE_MAX_ROWS`/`RECONCILE_MAX_LINES`, add
`RECONCILE_MAX_AGE_DAYS = effort_db.PENDING_MAX_AGE_DAYS` (import, do not
re-literal). Give `reconcile_pending_attempts` a
`max_age_days: "int | None" = None` keyword whose `None` resolves to
`RECONCILE_MAX_AGE_DAYS`, and pass the resolved value into
`pending_reconcilable`. Change no other call site.

The default-off choice at the `effort_db` layer is deliberate and load-bearing:
`pending_reconcilable` is the shared query, and INFRA-264's pending-row
diagnostic (if it landed) must keep seeing permanently-pending rows — those
rows are the thing it exists to surface. Only the sweep, which cannot act on
them anyway, opts into the bound. Put that reason in the docstring.

**4. (B) Write the containment helper.** In `subagent_transcript.py`, add
`import os` and `import tempfile` (both stdlib, no new dependency), then:

```python
#: Directory component every Claude Code spawn-output file sits under.
SPAWN_TASKS_DIR_NAME = "tasks"


def default_spawn_output_roots() -> "tuple[Path, ...]": ...
def _contained_spawn_output(output_file, tasks_root=None) -> "Path | None": ...
```

`default_spawn_output_roots()` returns the resolved `tempfile.gettempdir()`,
plus a resolved `$TMPDIR` when set and different. `_contained_spawn_output`
implements B2/B3 and returns `None` on any failure, wrapped so it never raises.

**Record the design reasoning in the helper's docstring**, because the obvious
"stricter is better" review reflex would break the system: the observed live
shape is
`/tmp/claude-<uid>/<project-slug>/<session-id>/tasks/<hash>.output` (effort.db
rows 357-362, 2026-07-25), but the guard deliberately checks only *temp root +
a `tasks` component* rather than pinning the full `claude-<uid>/<slug>/<session>`
shape. A harness-side layout change under a pinned rule would make every
`output_file` uncontained and silently stop all reconciliation — rows pending
forever, which is exactly the CER-091 failure class this phase is fixing. The
looser rule still blocks what the finding is about: a persisted path pointing at
`/etc/passwd`, a repository file, or `~/.ssh/*`.

**5. (B) Apply it.** Give `read_completed_spawn` a
`*, tasks_root: "Path | str | None" = None` keyword; replace its
`path = ...; if not path.exists(): return None` preamble with a
`_contained_spawn_output` call that returns `None` on rejection, then proceed
with the existing streaming loop against the *resolved* path. Thread
`tasks_root` through `reconcile_pending_attempts` (B5). Change nothing else in
either function — the completion detection (`stop_reason == "end_turn"`), the
`RECONCILE_MAX_LINES` bail-out, and the returned dict shape are INFRA-258/264
semantics and are out of scope.

**6. (B) Fix up the existing fixtures.** Existing tests in
`test_subagent_transcript.py` that write an output file directly into
`tmp_path` will now be rejected (no `tasks` component). Move each fixture into
`tmp_path / "tasks"` — the realistic shape, which also exercises the default
rule — rather than passing `tasks_root=tmp_path` everywhere. Reserve explicit
`tasks_root=` for the containment tests themselves. Delete no test.

**7. (C) Single-source the db-path resolution.** Add
`resolve_db_path_arg` to `effort_db.py` per C1/C2, immediately after
`resolve_effort_db_path`. Then:

- `record_attempt.py`: replace the `if db_path is not None:` block
  (`:277-282`) with the delegating call and a `try/except ValueError` that
  echoes the message to stderr and `sys.exit(2)`. Keep the surrounding
  `effort_tracking`-disabled early exit (`sys.exit(0)`) exactly as it is — that
  is a documented behaviour, not an error path.
- `pairmode_effort.py`: reduce `_resolve_db` to a delegating wrapper. Its five
  callers (`:632`, `:670`, `:712`, `:759`, `:1228`) each already have a click
  command context; let the `ValueError` surface as a non-zero exit with the
  message on stderr — either by catching it in `_resolve_db`'s callers or by
  converting it once inside `_resolve_db` to a `SystemExit(2)` with an echoed
  message. Prefer the single conversion inside `_resolve_db` over five
  identical try/excepts.

Do not add containment to `effort_db.resolve_effort_db_path`'s state.json
branch — it is already there, and changing its silent-fallback behaviour is a
semantics change this story does not own.

**8. Tests.** Add to `tests/pairmode/test_effort_db.py` (A1–A5, C1/C2/C5), to
`tests/pairmode/test_subagent_transcript.py` (B1–B5, plus the fixture moves),
and one CLI test each to `tests/pairmode/test_record_attempt.py` and
`tests/pairmode/test_pairmode_effort.py` (C6). Follow each file's existing
fixture style. The legacy-schema test for A2 must build its table with an
explicit `CREATE TABLE attempts (...)` lacking `agent_id`/`output_file` — do
not simulate it by dropping columns.

**9. Docs and CER rows.** Write D1's architecture paragraphs and D2's three
RESOLVED notes. For CER-016, state plainly that INFRA-058 had already closed
the `resolve_effort_db_path` half and that INFRA-266 closed the two mirrors —
an overclaiming resolution note is worse than an open row.

**10. Ideology note (Step 4a — resolved inline, no conflict).** Two entries
shaped this spec. *"Hooks are thin relays only"* is the whole justification for
item A: the constraint's rationale is that hook-path work must not block a
session, so an unindexed scan violates its spirit even at 362 rows — but the
same rationale forbids the tempting stricter fixes (logging rejected paths,
`ANALYZE`, a repair pass over stale rows), all of which add hook-path work, and
all of which are explicitly out of scope below. *"Rationale-bearing decisions
over bare rules"* is why three specific reasons must survive into the code as
comments rather than being merely correct in this document: why the index is
created after the migrations, why the age cutoff defaults off at the shared
query, and why the spawn-output guard is deliberately looser than the observed
path shape. Each of those is a place where a future reader's "obvious
improvement" is a regression.

## Tests

Run from the story worktree root. After each item:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_subagent_transcript.py \
  tests/pairmode/test_record_attempt.py \
  tests/pairmode/test_pairmode_effort.py \
  -q 2>&1 | tail -30
```

Then the adjacent effort surface, to catch collateral damage:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_record_attempt_seed.py \
  tests/pairmode/test_record_attempt_usage_parsing.py \
  tests/pairmode/test_record_attempt_companion.py \
  tests/pairmode/test_effort_guardrail.py \
  tests/pairmode/test_refresh_effort_baseline.py \
  tests/pairmode/test_context_health.py \
  tests/pairmode/test_drift_evidence.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
grep -n 'Path(db_path)' skills/pairmode/scripts/record_attempt.py    # must print nothing
grep -n 'Path(db_path)' skills/pairmode/scripts/pairmode_effort.py   # must print nothing
grep -rn 'pending_reconcilable' skills/pairmode/scripts/             # only the sweep passes max_age_days
grep -c '104' <<< "$(grep 'CER-088' docs/cer/backlog.md)"            # row carries the phase
```

Acceptance:

- every new test from A1–A5, B1–B5, C1–C6 passes;
- every pre-existing test in the four primary test files passes, by its
  original name (B6);
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so explicitly in the build
  result. Do not assume the CER-090 worktree UI-build failure — INFRA-261
  closed it in phase 103; a `test_observability_ui.py` failure now is a real
  finding, not a known one.

## Out of scope

- **Everything CER-091 / INFRA-264 owns.** The PostToolUse branch not firing for
  a repeat spawn of the same story+role; making `reconcile_attempt` atomic over
  tokens+outcome; the permanent-pending diagnostic surface; the
  reconciliation-time attempt-counter resurrection guard. This story changes no
  recording semantics (D3).
- **Retroactive cleanup of the existing pending rows** in flex's own
  `.companion/effort.db`. The age cutoff makes the sweep skip them; it does not
  delete, backfill, or annotate them. A data-repair pass is a separate story
  with its own reversibility argument.
- **Changing `resolve_effort_db_path`'s silent-fallback behaviour** when a
  `state.json` `effort_db_path` escapes the project. Established, intentional,
  and a behaviour change would ripple to every consumer's config.
- **A general `permission_scope.py`-style containment refactor** across the
  other `_depth_guard` users (`pairmode_drift_report.py`, `lesson_review.py`,
  `pairmode_register.py`, `flex_build.py`). CER-016 names only the effort-db
  surface; widening it is a fleet-scoped change needing its own story.
- **Logging or telemetry for rejected spawn-output paths.** Tempting for
  debuggability, forbidden by "hooks are thin relays only" — the guard's
  behaviour is documented in the docstring instead (B7).
- **`ANALYZE`, `VACUUM`, WAL mode, or any other SQLite tuning.** A3 is
  satisfied by the index, not by statistics.
- **New indices for the other query paths** (`query_by_phase`,
  `next_attempt_number`, the rollup queries). CER-088 names the sweep only, and
  each additional index costs write time on a hook path.
- **A management UI or CLI view for the attempts table.** No new persistent
  schema object is introduced (D4); the existing `pairmode_effort.py` reports
  remain the surface.
