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
