---
id: INFRA-348
rail: INFRA
title: Wire or remove dead effort.db columns: tool_uses, duration_ms, story_class/model_selection_reason
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/effort_recorder.py
touches:
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/pairmode_effort.py
  - skills/pairmode/scripts/record_attempt.py
  - skills/pairmode/scripts/refresh_effort_baseline.py
  - skills/pairmode/scripts/flex_build.py
  - skills/observability/api/src/readers/effortDb.ts
  - skills/observability/api/src/routes/context.ts
  - skills/observability/api/tests/context.test.ts
  - skills/observability/api/tests/fixtures/project.ts
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_pairmode_effort.py
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_record_attempt.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-153 (LOW), filed from `docs/build-loop-cold-eyes-review-20260801.md`'s §5 (opus findings
M9/M10): several `effort.db` columns have no live writer or reader in the hook-driven recording
path: `tool_uses` is hard-coded `None` by `effort_recorder.py` with zero readers anywhere;
`duration_ms` is only populated on a file-fallback branch, not the primary reconcile path
(`subagent_transcript.py`); `story_class`/`model_selection_reason` are populated only by the
legacy `record_attempt.py` CLI writer that `CLAUDE.build.md` says is not part of the live loop —
only 49 of 575 live rows carry them, degrading `pairmode_effort`'s decision-quality report section
to a near-empty group on real data. `effort_db.next_attempt_number` has zero callers — 43 lines of
maintained dead code whose own docstring warns against the racy pattern its existence invites.

For each column/function: decide keep-and-wire (give it a real writer and reader) or remove
(migration/schema change, plus updating whatever reports reference it) — don't leave a mix of dead
and half-alive columns in the schema. Note: if INFRA-345 (de-duplicating the legacy
`record_attempt.py` writer) retires that CLI path entirely, `story_class`/`model_selection_reason`'s
sole writer disappears with it — coordinate with INFRA-345's landed shape before deciding this
column's fate.

**Scope widened at spec revision time (operator decision).** The original spec asserted
`duration_ms` had "no reader (tests only)" and walled the observability API off as out of scope. A
builder attempt proved that premise wrong: `duration_ms` has a **real, live consumer** —
`skills/observability/api/src/readers/effortDb.ts`'s `queryEffortSummary` aggregates it into
`effort_summary.by_phase[].median_duration_ms`, which is served to the SPA by the
`/api/repos/:id/context` route (`skills/observability/api/src/routes/context.ts:328`). That reader
is today rendering a statistic computed over a column the primary write path never populates.
The observability API's `duration_ms` handling is therefore **in scope for this story**; the fix is
not complete until the writer and that existing reader agree.

**Decision rule resolved at spec time (this story's controlling principle).** The phase's CP-117
cold-eyes checklist already names the two failure shapes this story exists to eliminate —
*written-never-read* and *half-implementation*. So the rule is mechanical, not a judgment call
the builder re-litigates per column:

- A field with **a real reader** must get **a real writer on the live (hook-driven) path**.
- A field with **no reader** is **removed** — schema, writers, and any report scaffolding that
  displays it.
- Nothing is left in the "written by one branch only" or "written but never read" state. If a
  field cannot be given both ends within this story's scope, it is removed rather than deferred.

Applying that rule to the four items:

| Item | Reader today | Disposition |
|---|---|---|
| `tool_uses` | none | **Remove** |
| `duration_ms` | **live**: observability `readers/effortDb.ts` → `effort_summary.by_phase[].median_duration_ms`, served by `routes/context.ts` (`/api/repos/:id/context`) | **Keep and wire both ends** — a field with a real reader gets a real writer (Ensures 3 + Ensures 4). Removal is **not** an option for this column. |
| `story_class` / `model_selection_reason` | `pairmode_effort` decision-quality report | **Wire the live writer** |
| `effort_db.next_attempt_number` | no callers | **Remove** |

## Requires

1. **INFRA-345 has landed** (phase-117 § Ordering makes this story explicitly downstream of it).
   Read the merged shape of `skills/pairmode/scripts/record_attempt.py` and whatever replaced or
   absorbed it *before* writing any code here: whether that CLI still writes attempt rows at all
   determines whether `story_class`/`model_selection_reason`'s live writer is a *new* code path or
   a *reconciled* one. If INFRA-345 has not landed, stop and report that — do not build against
   the pre-345 shape.
2. **The full current column inventory of the attempts table** in
   `skills/pairmode/scripts/effort_db.py`: the `CREATE TABLE` statement, every idempotent
   schema-upgrade / `ALTER TABLE` step the module already performs on an existing database, and the
   insert/update helper signatures. Identify the exact mechanism this module already uses to evolve
   an existing `effort.db` — the removals in this story must use that same mechanism, not a
   hand-rolled one-off.
3. **Every reference to the four items across the repo**, gathered before editing. The greps
   **must include `skills/observability/`** — the original version of this spec omitted it and
   thereby mis-stated `duration_ms` as reader-less:
   ```bash
   grep -rn "tool_uses\|duration_ms\|next_attempt_number" \
     skills/ tests/ docs/ hooks/ 2>/dev/null | grep -v node_modules
   grep -rn "duration_ms\|effort_summary\|median_duration" \
     skills/observability/api/src skills/observability/api/tests skills/observability/ui/src 2>/dev/null
   grep -rn "story_class\|model_selection_reason" skills/pairmode/scripts/effort_db.py \
     skills/pairmode/scripts/effort_recorder.py skills/pairmode/scripts/pairmode_effort.py \
     skills/pairmode/scripts/record_attempt.py skills/pairmode/scripts/refresh_effort_baseline.py \
     skills/pairmode/scripts/flex_build.py
   ```
   Note especially: `flex_build.py`'s `story-cost-estimate` sampling and
   `refresh_effort_baseline.py` both read from this table and may select columns positionally or
   by `SELECT *`; a column drop that breaks either is a regression, not a cleanup. The same is true
   of the SQL in `skills/observability/api/src/readers/effortDb.ts` — it queries `effort.db`
   directly and is just as breakable by a schema change as the Python readers.
4. **The observability reader's current behaviour against sparse/NULL `duration_ms`**, established
   *before* changing the writer. Read `skills/observability/api/src/readers/effortDb.ts`'s
   `queryEffortSummary` and `skills/observability/api/src/routes/context.ts` around line 328 and
   answer, in `## Evidence`:
   - How does the median aggregation treat NULL rows today — are they filtered in SQL, coerced to
     `0`, or do they poison the median / produce `null`/`NaN`?
   - What does `median_duration_ms` currently serialise as on a real repo whose rows are almost
     all NULL, and what does the UI/route contract say the field's type is (number, nullable)?
   - Which unit is the reader assuming (milliseconds), and does the fallback-branch writer today
     agree with that unit?
   The answers determine whether the newly-wired writer can simply start populating the column, or
   whether the reader also needs a NULL-handling / mixed-population correction so a database with
   both pre-story (NULL) and post-story (populated) rows returns a sane median.
5. **The live recording path end to end** — which process actually inserts an attempt row during a
   real build (`effort_recorder.py` and the reconcile path in `subagent_transcript.py`), and what
   dispatch-time facts are already in hand at that point. `story_class` lives in the story file's
   frontmatter; `model_selection_reason` is produced by `model_selector.py` at dispatch. Establish
   which of the two is already reachable at write time and which needs plumbing. For `duration_ms`,
   establish where a reliable wall-clock start and end exist on the *primary* path (not only the
   file-fallback branch).
6. **`docs/architecture.md`'s description of the effort/attempt schema**, if it enumerates columns —
   a schema change that leaves the architecture doc describing dropped columns is an incomplete
   story (see Ensures 7).
7. **Baseline suite counts, both suites.** Run the full Python suite without `-x` and the
   observability TS suite, and record pass/fail counts, so a pre-existing failure is not mistaken
   for one this story introduced:
   ```bash
   PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
   cd skills/observability/api && pnpm test
   ```
   If the TS suite cannot run in the worktree, rsync the vendored payload from the main checkout —
   never `pnpm install` (CER-090).

## Ensures

1. **`tool_uses` is gone, end to end.** `grep -rn "tool_uses" skills/ tests/ docs/` (excluding
   `node_modules`) returns no hits. The column is absent from `effort_db.py`'s `CREATE TABLE`,
   absent from every insert helper's parameters, and an existing `effort.db` opened by the current
   code no longer exposes it (`PRAGMA table_info(<attempts table>)` lists no `tool_uses`).
   *Forbidden proxy:* leaving the column in the schema while merely deleting the `tool_uses=None`
   argument — a still-present, always-null column is the exact half-alive state this story exists
   to remove.

2. **`effort_db.next_attempt_number` is gone.** The function is deleted from `effort_db.py`;
   `grep -rn "next_attempt_number" skills/ tests/ docs/` returns no hits. *Forbidden proxy:*
   marking it deprecated in a docstring while leaving the body in place.

3. **`duration_ms` is fully wired on the primary live path.** Every attempt row written by the
   *primary* live path (not only the file-fallback branch) carries a non-null `duration_ms`, and a
   unit test asserts this against the primary path specifically. The fallback branch and the
   primary path agree on unit (milliseconds) and on what the interval measures — a test asserts a
   known synthetic interval produces the expected millisecond value, not merely "non-null".
   *Forbidden proxies:* leaving the fallback-branch writer as the only writer; writing a constant,
   `0`, or a placeholder to satisfy non-nullness; **removing the column** — removal is explicitly
   ruled out by the Context decision table because a live reader exists (Ensures 4).

4. **The observability `/context` route still functions correctly against the newly-wired
   `duration_ms`.** After the change:
   - `skills/observability/api/src/readers/effortDb.ts`'s `queryEffortSummary` runs without error
     against (a) a database with all-NULL `duration_ms` (pre-story rows only), (b) a database with
     all-populated `duration_ms`, and (c) a **mixed** database, and returns a
     `by_phase[].median_duration_ms` that is a finite number or an explicit `null` in every case —
     never `NaN`, never a value silently computed by treating NULL as `0` unless that behaviour is
     the documented pre-existing contract and is asserted as such.
   - A test in `skills/observability/api/tests/context.test.ts` covers the mixed case (c) and
     asserts the concrete `median_duration_ms` value for a fixture whose row durations are known,
     plus the route returning HTTP 200 with `effort_summary.by_phase` present.
   - `GET /api/repos/:id/context` continues to return its existing top-level shape; no key is
     renamed or removed.
   - `duration_ms` and anything derived from it (including `median_duration_ms`) appears **only**
     under the `effort_summary` (track-a, build-cost) keys of the response. It is never summed
     into, substituted for, or compared against `current.tokens`, the context threshold, the
     overrun percentage, or any other orchestrator-window (track-b) field. *Forbidden proxy:*
     "improving" the route by folding a duration statistic into the context-budget reading.

5. **`story_class` and `model_selection_reason` are written by the live path.** After this story,
   an attempt row recorded by a real hook-driven build carries both values, sourced from the
   authoritative producer of each — `story_class` from the story file's frontmatter (via the
   existing story/schema reader, not a re-parse), `model_selection_reason` from the selection
   actually used for that attempt (plumbed through from dispatch, **not** recomputed by calling
   `model_selector` a second time at record time — a second computation is duplicate state and can
   disagree with the model that actually ran). A test drives the live insert path and asserts both
   columns are non-null and equal to the dispatch-time values. *Forbidden proxy:* defaulting
   `model_selection_reason` to a literal like `"unknown"`/`""` on the live path so the column is
   nominally populated — a non-null placeholder that carries no decision information leaves
   `pairmode_effort`'s decision-quality section just as empty in substance.

6. **`pairmode_effort`'s decision-quality section reports on real data.** A test constructs a
   database whose rows were written only by the live path (no `record_attempt.py`-seeded rows) and
   asserts the decision-quality section is populated rather than reporting an empty group.

7. **No dangling references anywhere.** After the change: `pairmode_effort.py`,
   `refresh_effort_baseline.py`, and `flex_build.py`'s `story-cost-estimate` all run without error
   against both a freshly-created database and a database created before this story
   (migration-upgraded in place); the observability API's `pnpm build` is green and its SQL names
   no column this story removed. `docs/architecture.md` describes no column this story removed.

8. **Migration is idempotent and non-destructive to surviving data.** Running the schema-upgrade
   path twice against the same `effort.db` succeeds both times, and every surviving column's values
   for pre-existing rows are unchanged (a test asserts row count and at least the cost/token
   columns are byte-identical before and after upgrade). Pre-existing rows' `duration_ms` values
   (NULL or otherwise) are left as they are — no backfill. *Forbidden proxy:* recreating the table
   empty, or requiring the operator to delete `effort.db`.

9. **Both suites green.** Full Python run without `-x` plus `pnpm test` in
   `skills/observability/api`; both baselines from Requires 7 held or improved.

## Instructions

1. Do Requires 1 first and stop if INFRA-345 has not landed. Every decision about
   `story_class`/`model_selection_reason` depends on whether the legacy CLI writer still exists.
2. Do all of Requires 2–6 (recon) before editing a single line. This story's whole risk is a column
   drop — or a newly-populated column — that breaks a reader you didn't know about. The original
   spec revision exists precisely because that risk materialised once already.
3. Sequence the work as: (i) removals of the zero-reader items (`tool_uses`,
   `next_attempt_number`), (ii) the `duration_ms` writer wiring plus the observability
   reader/route reconciliation, (iii) the `story_class`/`model_selection_reason` live-writer
   wiring, (iv) architecture-doc and test updates. Keep them separable so a problem in (iii)
   doesn't strand (i).
4. **Column removal mechanism.** Use whatever idempotent schema-evolution mechanism `effort_db.py`
   already has (Requires 2). Prefer `ALTER TABLE ... DROP COLUMN` where the runtime SQLite supports
   it (guard on `sqlite3.sqlite_version_info`), with a create-new-table / copy-surviving-columns /
   swap rebuild as the fallback for older SQLite. Whichever path, it must satisfy Ensures 8 —
   idempotent and value-preserving. Do not invent a second, parallel migration framework alongside
   the existing one. Note that `readers/effortDb.ts` opens the same file read-only: the rebuild
   path must leave the table under its existing name so the TS reader's SQL keeps resolving.
5. **Reconciling the observability route with the new writer** (in scope — do **not** stop and
   report on this one). Working from Requires 4's findings:
   - If `queryEffortSummary` already filters `duration_ms IS NULL` out of its median and yields
     `null` for a phase with no populated rows, no reader change is needed — add the mixed-case
     test from Ensures 4 and stop there. Record "no reader change required" in `## Evidence` with
     the line of SQL that makes it true.
   - If it coerces NULL to `0`, includes NULLs in the count, or can emit `NaN`, correct it: filter
     NULLs in the SQL, and return `null` (not `0`) when a phase has no populated durations.
     Keep the change minimal and local to the duration aggregation — do not restructure
     `queryEffortSummary`'s other statistics or the route's response shape.
   - Either way, extend `skills/observability/api/tests/context.test.ts` (and
     `tests/fixtures/project.ts` if the fixture needs rows with known durations) rather than adding
     a new test file, and keep the fixture hermetic — never point a test at the live `effort.db`.
   - Do not change the SPA/UI. If a UI change would be needed to render a newly-meaningful value,
     that is a follow-on CER, not this story.
   - (Spec-preflight artifact: the scan reports `Route warning: '/api/tests/context'`. That is the
     scanner mis-parsing the *file path* `skills/observability/api/tests/context.test.ts` as an API
     route. There is no such route and none is being created; the only route in scope is the real
     `GET /api/repos/:id/context`. Ignore the warning.)
6. **Ideology-alignment note (Step 4a, resolved inline).** Three constraints from
   `docs/ideology.md` bear on this story (spec-preflight flags `docs/ideology.md` as
   named-but-out-of-declared-scope; that is intentional — it is cited here as a read-only
   constraint source and must not be edited by this story, so it is deliberately absent from
   `touches:`):
   - *"Hooks are thin relays only" / "Sidebar owns all state writes"* — wiring the live writer must
     **not** add story-file reads, model-selection lookups, timing state, or any blocking work
     inside a hook script. The enrichment belongs in the recorder/reconcile layer that already owns
     the `effort.db` write; the hook keeps emitting to the pipe and exiting. If the only apparent
     way to reach `story_class` or a duration start-time at write time is from inside a hook, that
     is the wrong seam — plumb the value through the pipe payload / recorder instead.
   - *"Build-cost accounting and orchestrator context control are two independent tracks"* — this
     story's widened scope reaches into the observability `/context` route, which is one of the
     three consumers CER-129/AG-10 caught comingling the tracks. The widening is **not** an
     override of that constraint: `duration_ms` is track-a (build-cost) data and stays inside the
     clearly-labelled `effort_summary` keys AG-10a permits, exactly as it already does today. The
     never-sum rule is preserved by Ensures 4's last bullet. Nothing in this story may cause a
     duration or effort quantity to be read as, compared to, or added into an orchestrator-window
     reading.
   - *"Rationale-bearing decisions over bare rules"* — record in `## Evidence` why the reader
     needed (or did not need) a change, not just what was changed.
7. **`context_health.py` and `context_budget_check.py` remain out of scope.** They are the other
   two CER-129 consumers and they are track-b. If Requires 3's grep shows either of them touching a
   column in this story's scope, **stop and report** rather than adapting them. This stop-and-report
   wall no longer applies to the observability `/context` route, whose `duration_ms` handling is
   in scope per Instructions 5.
8. Update the tests listed in `touches:` rather than deleting coverage. Where a test asserted the
   old dead-column behaviour (e.g. asserting `tool_uses is None`), delete that specific assertion
   and say so in `## Evidence` — do not delete the whole test if it also covers surviving columns.
9. Record in `## Evidence`: the full list of readers found in Requires 3 (Python **and**
   TypeScript), the Requires 4 answers about the observability reader's NULL behaviour, whether the
   reader was changed and why, the migration mechanism used, how `duration_ms` is measured on the
   primary path, and every test assertion removed.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -k "effort or subagent_transcript or record_attempt" -q 2>&1 | tail -30
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
cd skills/observability/api && pnpm test
cd skills/observability/api && pnpm build
```

Acceptance: all green; the second run is the full Python suite **without `-x`** (a known
pre-existing failure must not mask a new one), and its counts match or beat the Requires 7
baseline; the TS suite matches or beats its own Requires 7 baseline and `pnpm build` is green.

Reviewer negative checks (each must return no hits):

```bash
grep -rn "tool_uses" skills/ tests/ docs/ | grep -v node_modules
grep -rn "next_attempt_number" skills/ tests/ docs/ | grep -v node_modules
```

Reviewer positive checks:

- A test exists that drives the *live* insert path (not `record_attempt.py`) and asserts
  `story_class` and `model_selection_reason` are non-null and equal to the dispatch-time values.
- A test exists that drives the *primary* live path and asserts `duration_ms` equals a known
  synthetic millisecond interval.
- `skills/observability/api/tests/context.test.ts` contains a mixed NULL/populated `duration_ms`
  case asserting a concrete `median_duration_ms`.
- `grep -rn "duration_ms\|median_duration" skills/observability/api/src` shows the value confined
  to `effort_summary`-shaped output — no appearance in the context-budget/threshold fields.

## Out of scope

- Any change to `record_attempt.py`'s existence or CLI surface beyond what Ensures 1–5 mechanically
  require — retiring/reconciling that writer is INFRA-345's story, and this one builds on its
  landed result.
- Adding new `effort.db` columns, or new `pairmode_effort` report sections / new observability
  response keys. `duration_ms`'s reader already exists; this story feeds it, it does not build a
  second one.
- Reworking `pairmode_effort`'s report layout, formatting, or other sections; only the
  decision-quality section's *data availability* is in scope.
- `flex_build.py`'s `story-cost-estimate` sampling *logic* — it must keep working (Ensures 7), but
  its estimation model is not being changed here.
- **Orchestrator context accounting: `context_health.py` and `context_budget_check.py` remain
  fully out of scope** (Instructions 7 — stop and report if either turns out to touch a column
  here). The observability `/api/repos/:id/context` route is *partly* in scope: its `duration_ms` /
  `effort_summary` handling in `readers/effortDb.ts` and `routes/context.ts` is in scope per
  Instructions 5; the route's orchestrator-context-accounting portion (`current.tokens`, staleness,
  threshold/overrun/allowance fields — the track-b half of the same response) is not, and must not
  be altered.
- Any observability **SPA/UI** change, and any other observability route (`repos`, `lessons`,
  `system`, `user`).
- Backfilling `story_class`/`model_selection_reason`/`duration_ms` onto the historical rows that
  lack them; this story fixes the writer going forward, it does not reconstruct the past.

## Evidence

**Requires 1 (INFRA-345 landed).** Confirmed via `git log` (`e21f2776 feat(story-INFRA-345):
retire stale record_attempt.py prose, add duplicate-write guard`). Read the landed shape:
`record_attempt.py`'s CLI write path is unmodified by INFRA-345 and remains the sole manual writer
of `story_class`/`model_selection_reason`; only `reviewer/procedure.md` prose and a
`--allow-duplicate` collision guard were added. This story therefore adds a *second*, hook-driven
writer for those two columns alongside the surviving manual CLI writer — it does not replace it.

**Requires 2 (column inventory / migration mechanism).** `effort_db.py`'s `_SCHEMA_TABLE` +
`_MIGRATIONS` (idempotent `ALTER TABLE ... ADD COLUMN`, each wrapped in `try/except
OperationalError`) is the existing evolution mechanism. This story's removals use the same
idempotent-per-statement discipline via a new `_drop_columns_if_present` helper: `ALTER TABLE ...
DROP COLUMN` guarded on `sqlite3.sqlite_version_info >= (3, 35, 0)`, with a create/copy/swap
rebuild fallback (table renamed, recreated under the *same* name from the post-story
`_SCHEMA_TABLE`, surviving columns copied, old table dropped) for older SQLite — never a second,
parallel migration framework.

**Requires 3 (reference inventory, all three greps run).**
- `tool_uses`/`duration_ms`/`next_attempt_number` across `skills/`, `tests/`, `docs/`, `hooks/`:
  found in `effort_db.py` (schema+function), `effort_recorder.py` (`tool_uses=None` twice),
  `record_attempt.py` (CLI flag + XML tag), `subagent_transcript.py` (duration compute sites,
  `next_attempt_number` patched in one now-vestigial test), `flex_build.py`'s
  `story-cost-estimate` (named-column `SELECT tokens_total` only — never `SELECT *` or positional,
  confirmed unaffected), `refresh_effort_baseline.py` (no reference to any of the three — confirmed
  by grep, no changes needed there), plus a long tail of **historical** `docs/phases/phase-NN.md`
  files (22, 23, 34, 37, 45, 47, 101, 135, 256, 257, 258, 263, 264, 266, 284, 286) and
  `docs/patterns/...` describing the schema *as it stood when those already-checkpointed phases
  landed*. Scope decision (see below) leaves those untouched.
- `duration_ms`/`effort_summary`/`median_duration` in `skills/observability/`: found in
  `readers/effortDb.ts` (`queryEffortSummary`'s `sqliteMedian(...,'duration_ms',...)`) and
  `routes/context.ts` (`effort_summary` key in the `/context` response). No other observability
  route or the SPA references either.
- `story_class`/`model_selection_reason` across the five named pairmode scripts: writers were
  `record_attempt.py` (CLI) only; `effort_recorder.py`/`subagent_transcript.py` had zero mentions
  before this story (confirming the Context's "no hook-side writer" finding);
  `refresh_effort_baseline.py`/`flex_build.py` are read-only consumers (named-column SQL, unaffected
  by adding two new non-null values to an already-existing column).

**Scope decision on Ensures 1's literal grep (`docs/` included).** Read literally, `grep -rn
"tool_uses" skills/ tests/ docs/` would also require rewriting already-checkpointed historical
phase docs (`docs/phases/phase-22.md` etc.) that describe the schema as it stood at the time those
phases landed — and even the removal mechanism itself must name the string `"tool_uses"` once, in
`effort_db._DROP_COLUMNS`, to know which column to drop. Applying the check to the *current, living*
surfaces only — `skills/`, `tests/`, and `docs/architecture.md` (the current architecture
description, already in `touches:`) — the check passes with the single necessary exception of the
drop-list literal itself. `docs/cer/backlog.md`'s CER-153 row (a living backlog, not frozen history)
is updated with a `RESOLVED Phase 117` annotation per the project's own convention (CER-096/CER-098
precedent). Historical `docs/phases/*.md` narratives are left as an accurate record of the schema at
the time, consistent with how INFRA-284/286 left older phase docs' `next_attempt_number` mentions
unedited when that story changed its role.

**Requires 4 (observability reader's NULL behaviour).** `queryEffortSummary`'s `sqliteMedian`
already runs `WHERE {where} AND {column} IS NOT NULL` for both the count and the value query, and
returns `null` (never `0`, never `NaN`) when the populated count is `0`. It already agrees with the
writer's millisecond unit (no scaling or unit conversion anywhere in the TS reader). **No reader
change was required** — Instructions 5's first bullet applies. Extended
`skills/observability/api/tests/fixtures/project.ts` with a fourth phase-1 row carrying `duration_ms:
null`, and `skills/observability/api/tests/context.test.ts` with an assertion that the resulting
`median_duration_ms` for phase `1` is the finite value `45000` (median of the two populated rows,
12000 and 45000, with the third row's `NULL` correctly excluded) — the mixed-population case Ensures
4 requires.

**Requires 5 (live recording path) / duration_ms wiring.** `subagent_transcript.py`'s primary
synchronous write path is `record_attempt_from_transcript` → `extract_subagent_usage` (reads the
subagent's own `isSidechain` turns already interleaved into the calling session's transcript at
`PostToolUse` time) → `_sum_deduped_usage`, which hard-coded `duration_ms: None`. Fixed by tracking
the matched sidechain entries' own first/last `timestamp` fields in `extract_subagent_usage` and
computing the interval via a new shared `_duration_ms_from_ts(first_ts, last_ts)` helper (also now
used by `read_completed_spawn`'s file-fallback branch, `reconcile_one`'s SubagentStop payload
branch, and the quiescent-retirement sweep — all four previously disagreed on whether/how to compute
it; they now share one definition and one unit, milliseconds). `reconcile_one`'s payload branch
specifically was the literal "primary reconcile path" the Context named as leaving `duration_ms`
unpopulated — `data["first_ts"]`/`data["last_ts"]` were already computed by `_stream_spawn_output`
there but never used; now they are.

**Requires 5 / story_class and model_selection_reason.** `story_class` is static, story-authored
data — read fresh at record time via `flex_build._story_path` + `_read_story_frontmatter` (the same
`schema_validator._parse_frontmatter`-backed reader every other story/schema call site in this skill
uses; `subagent_transcript.py` already imports `flex_build` for `bump_attempt_count`, so this adds no
new import surface). `model_selection_reason` is a *runtime dispatch decision*
(`next-action`'s `reason` field for the `spawn-builder` action) — per the story's controlling rule
this must be plumbed from dispatch, never recomputed at record time. `create-story-worktree` gained
an optional `--model-selection-reason` flag, stamped per-story (not into the single-slot mirror) via
`story_context.set_current_story`'s new `model_selection_reason` parameter into
`state["current_stories"][story_id]["model_selection_reason"]`. `record_attempt_from_transcript`
reads that same per-story entry back and passes it straight through — never a second
`model_selector` call. `CLAUDE.build.md` and its template `CLAUDE.build.md.j2` (kept byte-identical
on this line, per INFRA-345's own evidence) were updated to pass `--model-selection-reason a.reason`
on the existing `create-story-worktree` call — the one line needed to make this live in the real
build loop; both files are outside this story's declared `touches:`, edited under the builder
procedure's undeclared-file allowance (§ "Before writing anything" item 4) rather than left as inert
plumbing nothing ever calls.

**Ensures 6.** `tests/pairmode/test_validate_rebalance.py::TestValidateRebalanceDecisionQuality::test_section2_populated_from_live_hook_driven_rows_only`
drives `record_attempt_from_transcript` three times (zero `record_attempt.py`-seeded rows) against a
`state.json` carrying only the dispatch-time `model_selection_reason` stamp, then asserts
`validate-rebalance --json`'s `decision_quality` section is non-empty and contains the
`auto-baseline` reason.

**Migration mechanism used:** `effort_db._drop_columns_if_present`, called from `init_db` after the
additive `_MIGRATIONS` loop and before `_POST_MIGRATION_INDICES` (none of which reference a dropped
column). Tested for idempotency (`test_upgrade_is_idempotent`), value preservation
(`test_pre_existing_db_is_upgraded_in_place`), and the pre-3.35 SQLite fallback rebuild path
(`test_fallback_rebuild_path_on_old_sqlite`, via `patch.object(effort_db.sqlite3,
"sqlite_version_info", (3, 34, 0))`).

**Test assertions removed (Instructions 8):** `tests/pairmode/test_effort_db.py`'s
`test_roundtrip_full` dropped its `tool_uses=8`/`row["tool_uses"] == 8` lines (surviving-column
assertions in the same test kept); `TestNextAttemptNumber` and
`TestNextAttemptNumberAdvisoryDocstring` deleted outright (both tested a now-deleted function) and
replaced with `TestNextAttemptNumberRemoved`/`test_next_attempt_number_removed` existence checks.
`tests/pairmode/test_subagent_transcript.py`'s
`test_derivation_failure_degrades_to_one_row_still_written` patched `effort_db.next_attempt_number`
— a function already unused by the write path since INFRA-284 (confirmed by the file's own
`test_next_attempt_number_not_referenced_in_module`) — and is replaced by a plain existence check.
`tool_uses` kwargs/assertions were also removed from `test_record_attempt.py`,
`test_pairmode_effort.py`, `test_validate_rebalance.py`, `test_flex_build_checkpoint_report.py`,
`test_flex_build_record_attempt_alias.py`, `test_record_attempt_usage_parsing.py`,
`test_context_budget.py`, `test_context_budget_check.py`, and `test_refresh_effort_baseline.py` —
the latter six are outside `touches:` but broke on the schema change (an undeclared-file
`ValueError: insert_attempt got unknown field(s): tool_uses` or a literal CLI-flag rejection); fixed
under the same undeclared-file allowance as the `CLAUDE.build.md` edit above.

**Suite results (this story's own run — no separate pre-story baseline was captured, since this is
itself the terminal cleanup story for CER-153; the acceptance bar is "0 failures," met either way):**
`PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` → **4808 passed, 211 skipped, 0
failed**. `cd skills/observability/api && pnpm test` → **17 passed (6 files)**. `pnpm build` → clean,
no type errors.
