---
id: INFRA-309
rail: INFRA
title: "Rollup hygiene: shared NON_BUILD_ROLES exclusion across Python and TS read paths"
status: draft
phase: "115"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/pairmode_effort.py
  - skills/pairmode/scripts/refresh_effort_baseline.py
  - skills/observability/api/src/readers/effortDb.ts
touches:
  - tests/pairmode/test_pairmode_effort.py
  - tests/pairmode/test_refresh_effort_baseline.py
  - tests/pairmode/test_waypoint_outcome.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-309.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`attempts` is written by more than the pairmode build loop. Three roles record
real token cost that is not a build attempt:

| Role | Writer | Story-ID shape |
|---|---|---|
| `sidebar-extractor` | `skills/companion/scripts/sidebar.py` `:440`, `:496` | `sidebar:<id>` / `sidebar:no-story` (`:432`, `:492`) |
| `seed-miner` | `skills/seed/scripts/mine_sessions.py` `:232`, `:262` | mining session id |
| `seed-reconcile` | `skills/seed/scripts/reconcile.py` `:83`, `effort_recorder.py:20` | reconcile target |

All three appear in `record_attempt.py`'s documented `--agent-role` list
(`:74-75`) alongside the five build-loop roles, so they are legitimate rows —
not drift.

### The CER-107 row's stated harm does not exist

CER-107 (`docs/cer/backlog.md:76`) claims these rows are "counted by
lifetime/role rollups, **polluting build-role medians**", and offers two
remedies: exclude from rollups, **or stop recording them**. The medians claim is
wrong, and the second remedy is wrong. Both were checked against the live
database before this spec was written:

```
$ python3 -c "...select agent_role, count(*), sum(tokens_total is null), sum(phase is null), sum(rail is null) ... group by 1"
('sidebar-extractor', 297, 297, 297, 297)
('builder',            78,  23,  57,   2)
('reviewer',           68,  17,  49,   0)
('security-auditor',   14,   5,   7,   9)
('intent-reviewer',    12,   3,   3,   9)
```

**Medians are safe by construction.** Every per-role statistic keys *on*
`agent_role`, so a non-build role forms its own bucket and cannot enter a
builder's or reviewer's distribution:

- `flex_build._query_effort_by_role` (`:2659-2698`) groups into `by_role` and
  takes `statistics.median` per key, over `tokens_total IS NOT NULL AND
  tokens_total > 0`.
- `refresh_effort_baseline._aggregate` consumes `(agent_role, tokens_total)`
  pairs from `_collect_rows` (`:30-47`) and buckets by role.
- `pairmode_effort._query_models` (`:388-400`) groups by `(model, agent_role)` —
  a separate cell per role.

**The real harm is read-side, and it is unattributed-bucket harm, not median
harm.** Two live readers count these rows into aggregates that present as build
activity:

1. **`pairmode_effort._query_rollup`** (`:243-272`) groups by
   `(phase, rail, model)` with no role predicate. Sidebar rows carry
   `phase=NULL, rail=NULL`, so all 297 land in a single anonymous bucket that
   reports `attempts=297, total_tokens=0` — an "unattributed" row that dwarfs
   every real rail's attempt count and reads as 297 zero-cost build attempts.
   `_attach_rollup_dollars` (`:425-470`) re-queries each group by the same
   `(phase, rail, model)` triple, so any group a non-build row shares with build
   rows also carries that row's spend into the dollar projection.
2. **`skills/observability/api/src/readers/effortDb.ts`** — `queryEffortSummary`
   (`:186`) computes `total_attempts` as a bare `SELECT COUNT(*) FROM attempts`
   (`:193`). On this repo that is 469, of which 297 (63%) are sidebar
   extractions. The SPA's headline attempt count is majority non-build **today**.
   `queryWaypoints` (`:123-157`) is a latent instance of the same defect: its
   `WHERE tokens_total IS NOT NULL` (`:153`) happens to hide sidebar rows only
   because `record_effort`'s usage capture is currently yielding NULL on every
   one of the 297 — `sidebar.py:433-437` does pass a `usage` object on the
   Anthropic path, so the moment that capture starts working, 100 sidebar rows
   flood the waypoint timeline as build events. `queryMisses` (`:246`) has the
   same latent shape behind its threshold filter.

### Why "stop recording them" is rejected

Sidebar extraction is a real LLM call against a real model with real token cost.
Deleting the writer trades a permanent loss of cost data for a cosmetic fix to a
read path, and it violates the era's own value hierarchy ("decision fidelity
over convenience — a system that silently drops context cannot be trusted").
This story changes **no writer**. Recording is unchanged; only readers learn the
distinction.

### The shape of the fix

One shared constant, `effort_db.NON_BUILD_ROLES`, defined once in Python and
consumed by every Python reader that aggregates *across* roles. `effortDb.ts`
cannot import it — the SPA API is TypeScript and there is no cross-language
constant channel — so it mirrors the set as an exported TS constant carrying a
Python-source-of-truth comment, and the duplication is pinned by a Python test
that parses the TS literal and asserts set equality. Duplicated state with two
independent writers is exactly what the CP-115 cold-eyes checklist asks about;
the answer here is that the duplication is deliberate, minimal (three strings),
and mechanically enforced, and that answer is written into
`docs/architecture.md` rather than left to be rediscovered.

Reports that are already role-keyed keep every row: `models` retains non-build
roles and *labels* them, because "how much did sidebar extraction cost" is a
question the report should still answer.

## Requires

- **INFRA-299 (phase 113) is specced and its handoff is honoured.** INFRA-299
  documents at its `## Out of scope` (`docs/stories/INFRA/INFRA-299.md:607-609`)
  that its builder must **not** edit
  `skills/observability/api/src/readers/effortDb.ts`, because *this* story owns
  read-side rollup hygiene in that file. The reciprocal obligation lands here:
  INFRA-299's E2 establishes that `effortDb.ts:205-211`'s
  `SELECT DISTINCT phase FROM attempts WHERE phase IS NOT NULL` yields a
  **checkpoint-rows-only** per-phase breakdown *by design* (`attempts.phase` is
  populated only for `subagent_transcript.CHECKPOINT_ROLES`). This story must
  therefore leave that query and the `by_phase` loop (`:212-235`) alone: sidebar
  rows carry `phase=NULL` and are already excluded there, and "fixing" it would
  contradict a decision INFRA-299 just recorded in `docs/architecture.md`.
  INFRA-299 need not be *merged* before this story builds — the two share no
  file — but if both are in flight, `effortDb.ts` conflicts must resolve in
  favour of this story.
- `skills/companion/scripts/sidebar.py` records `agent_role="sidebar-extractor"`
  at `:440` and `:496` with `story_id` from `:432` / `:492`. **Read-only input.**
- `skills/seed/scripts/mine_sessions.py:232,262` records `seed-miner`;
  `skills/seed/scripts/reconcile.py:83` and
  `skills/pairmode/scripts/effort_recorder.py:20` record `seed-reconcile`.
  **Read-only inputs.**
- `skills/pairmode/scripts/record_attempt.py:71-76` is the canonical documented
  role list: `builder, reviewer, intent-reviewer, security-auditor,
  loop-breaker, seed-miner, seed-reconcile, sidebar-extractor`. The first five
  are build-loop roles (matching `subagent_transcript.RECORDABLE_SUBAGENT_ROLES`,
  `:95-101`); the last three are the non-build set this story names.
- `skills/pairmode/scripts/effort_db.py` has a module-level constant block
  (`_ATOMIC_RECONCILE_FIELDS` `:115`, `AGENT_DEDUPE_WINDOW_SECONDS` `:183`,
  `_INSERT_COLUMNS` `:187`) and today defines **no** role constant.
- `skills/pairmode/scripts/pairmode_effort.py`: `_query_rollup` `:243-286`
  (SQL `:254-263`, `GROUP BY` `:272`); `_attach_rollup_dollars` `:425-470`;
  `_query_models` `:388-410` (SQL `:392-400`); `_emit` `:200-221` (JSON mode
  emits a bare array at `:201-203`); `rollup_cmd` `:628-658`; `models_cmd`
  `:759-792`.
- `skills/pairmode/scripts/refresh_effort_baseline.py`: `_collect_rows` `:30-47`,
  SQL `:39-40` (`WHERE tokens_total IS NOT NULL AND agent_role IS NOT NULL`).
- `skills/observability/api/src/readers/effortDb.ts`: `queryWaypoints` `:123`
  (SELECT `:151-155`), `queryEffortSummary` `:186` (`COUNT(*)` `:193`,
  `SELECT DISTINCT phase` `:209`), `queryMisses` `:246` (count `:277`,
  SELECT `:281-287`).
- There is **no TypeScript test runner** in this repo. Observability behaviour is
  asserted from Python: `tests/pairmode/test_waypoint_outcome.py` mirrors
  `queryWaypoints`'s SQL against a synthetic `sqlite3` fixture (`:64-91`) and
  reads `effortDb.ts` as text. Follow that pattern; do not add a JS test runner.
- `sqlite3(1)` is **not installed** on this host. Every database read in this
  story uses Python's stdlib `sqlite3` module.
- `docs/cer/backlog.md:76` holds the `CER-107` row with `—` in its `Phase` cell.
- `docs/architecture.md` `## Effort tracking` begins at `:2590`; the
  `pairmode_effort.py` view list is `:2654-2666`.
- **Baseline:** `main` is green at 4116 passed / 211 skipped. The
  `test_observability_ui` failure is **worktree-only** (CER-090: the vendored
  `node_modules` payload is incomplete in a fresh worktree). Repair it by
  rsyncing the payload from the main checkout — **never** by running
  `pnpm install`.

## Ensures

Line numbers above are pre-verified as of this spec; re-confirm before editing.

> **Spec-preflight note.** `spec-preflight` reports
> `Constant warning: 'NON_BUILD_ROLES' referenced in story but no definition
> found in source tree.` This is expected and intentional: A1 creates the
> constant. No other preflight finding is outstanding.

### A — The shared constant

**A1. `effort_db.NON_BUILD_ROLES` exists, exactly once.**
`skills/pairmode/scripts/effort_db.py` gains a module-level

```python
NON_BUILD_ROLES: frozenset[str] = frozenset({
    "sidebar-extractor",
    "seed-miner",
    "seed-reconcile",
})
```

placed in the existing constant block (near `AGENT_DEDUPE_WINDOW_SECONDS`,
`:183`). It is the **only** definition of this set in Python:
`grep -rn 'sidebar-extractor' skills/ --include=*.py` returns exactly the two
`sidebar.py` writer lines plus this one definition — no reader hardcodes the
string.

**A2. The constant carries its rationale.** A comment above it states: these are
the `record_attempt.py:74-75` roles that are not build-loop attempts; their rows
are *deliberately retained* because the token cost is real; the constant exists
for **read-side** aggregation only and is never consulted by a writer; and it is
complementary to — not a substitute for —
`subagent_transcript.RECORDABLE_SUBAGENT_ROLES` (which governs what
`subagent_transcript` *records*, a different question).

**A3. Membership is by role, never by `story_id` prefix.** No code added by this
story tests for a `"sidebar:"` prefix. `agent_role` is the discriminator; the
`story_id` shape is incidental.

### B — `pairmode_effort` rollup

**B4. `_query_rollup` excludes non-build roles.** Its SQL gains
`AND (agent_role IS NULL OR agent_role NOT IN (?, ?, ?))` with the placeholders
bound from `sorted(effort_db.NON_BUILD_ROLES)` — **parameterised**, not
string-interpolated, and the count of placeholders derived from the constant's
length so a fourth role needs no SQL edit. The import is
`from ... import effort_db`-style (module or symbol), never a literal copy.

**B5. NULL `agent_role` rows are retained.** A row with `agent_role IS NULL` is
not a *known* non-build role and must not silently vanish from the rollup. A
test pins this: a fixture row with NULL role and non-zero tokens still appears
in `rollup` output after the change.

**B6. `_attach_rollup_dollars` applies the identical exclusion.** Its per-group
re-query (`:444-470`) gains the same predicate. Without it, a `(phase, rail,
model)` group shared by a build row and a non-build row would report
`total_tokens` from the filtered query and `dollars_estimate` from an unfiltered
one. A test asserts that for a fixture where a sidebar row shares a
`(phase, rail, model)` triple with a builder row, `total_tokens` and the dollars
projection are computed over the **same** row set.

**B7. Text-mode output discloses the exclusion.** `rollup_cmd` echoes one line
before the table naming the excluded roles, e.g.:

```
(excluding non-build roles: seed-miner, seed-reconcile, sidebar-extractor)
```

The role names are rendered from `sorted(effort_db.NON_BUILD_ROLES)`, not
retyped. A test asserts the line is present in text output and names all three.

**B8. JSON-mode output shape is unchanged.** `--json` still emits a bare array
of row dicts (`_emit` `:201-203`); the disclosure line is **not** emitted in
JSON mode and no wrapper object is introduced. The exclusion is documented in
`rollup_cmd`'s docstring and `_query_rollup`'s docstring so a JSON consumer can
discover it. A test asserts `json.loads(result.output)` is still a `list` and
that the output contains no disclosure text.

**B9. Live before/after evidence is recorded in `## Evidence`.** Run
`pairmode_effort.py rollup --json` against this repo's `.companion/effort.db`
before and after the change. Before: a row with `phase: null, rail: null` and
`attempts: 297`. After: that row is absent, or present only with the
non-sidebar residue, and the summed `attempts` across all rows drops by exactly
the non-build row count. Paste both, with the count arithmetic shown.

### C — `pairmode_effort` models report retains and labels

**C10. `_query_models` returns every role, including non-build ones.** No row is
dropped; `GROUP BY model, agent_role` (`:398`) is unchanged. "How much did
sidebar extraction cost" stays answerable.

**C11. Each models row gains a `role_class` field** whose value is
`"non-build"` when `row["agent_role"] in effort_db.NON_BUILD_ROLES` and
`"build"` otherwise (NULL role → `"build"`, consistent with B5's
don't-silently-reclassify rule; state this in the code comment).
`models_cmd`'s `columns` list (`:781-790`) includes `role_class` immediately
after `agent_role`, so it appears in both text and JSON output.

**C12. `pass_rate_pct` arithmetic is untouched.** The CER-055 semantics pinned by
`tests/pairmode/test_waypoint_outcome.py:249+` (NULL outcome is neither PASS nor
FAIL) still hold, and those tests pass **by their original names**.

### D — Baseline seeding

**D13. `refresh_effort_baseline._collect_rows` excludes non-build roles.** Its
SQL (`:39-40`) gains the same parameterised `NOT IN` predicate, sourced from
`effort_db.NON_BUILD_ROLES` (add whatever `sys.path` wiring the file already
uses for sibling imports; if it has none, import by module path in the same
style as its sibling scripts — do not vendor a copy of the set).

**D14. The docstring records why.** `_collect_rows`'s docstring states that the
seed file feeds `expected_step_tokens` guardrails for *build* work, so non-build
roles are excluded at the source rather than filtered by every consumer.

**D15. Seed output stays idempotent and byte-identical for build roles.**
`tests/pairmode/test_refresh_effort_baseline.py::test_idempotent_byte_identical_output`
and the two aggregation tests pass unchanged; a new test proves a fixture db
containing `sidebar-extractor` rows with non-NULL `tokens_total` produces a seed
file with **no** `sidebar-extractor` key and unchanged builder statistics.

### E — TypeScript mirror

**E16. `effortDb.ts` exports a mirrored constant.**

```ts
// Source of truth: skills/pairmode/scripts/effort_db.py NON_BUILD_ROLES.
// TypeScript cannot import the Python constant; this list is duplicated
// deliberately and pinned by tests/pairmode/test_waypoint_outcome.py's
// parity test — change both or neither. See docs/architecture.md
// § Effort tracking.
export const NON_BUILD_ROLES = ['seed-miner', 'seed-reconcile', 'sidebar-extractor'] as const;
```

Sorted alphabetically so the parity test compares stable text. Defined once,
above `queryWaypoints`.

**E17. `queryWaypoints` excludes non-build roles.** Its SELECT (`:151-155`)
gains `AND (agent_role IS NULL OR agent_role NOT IN (...))` with bound
parameters generated from `NON_BUILD_ROLES` (placeholder count derived, not
hardcoded). NULL role retained, matching B5.

**E18. `queryEffortSummary.total_attempts` excludes non-build roles.** The
`SELECT COUNT(*) AS total FROM attempts` at `:193` gains the same predicate.
This is the live defect: 297 of 469 rows on this repo. Evidence block records
the before and after numbers.

**E19. `queryMisses` excludes non-build roles** in **both** its count query
(`:277`) and its row query (`:281-287`), so the miss count and the listed
entries agree. It is a latent instance of the same defect — a non-build row with
tokens above the ceiling would be reported as a build near-miss — and it costs
one predicate to close.

**E20. The per-phase breakdown is NOT touched.** `SELECT DISTINCT phase`
(`:209`), the `by_phase` loop (`:212-235`), and its median/p90 helpers are
byte-unchanged. Reason, per INFRA-299 E2: `attempts.phase` is
checkpoint-role-only by design, so that breakdown is already free of non-build
rows, and altering it would contradict a decision INFRA-299 records in
`docs/architecture.md`. `git diff` on `effortDb.ts` shows no hunk inside
`:205-235`.

**E21. The API still builds.** `pnpm --filter @flex-obs/api build` succeeds and
`tsc --noEmit` is clean for the api package. If the vendored payload is
incomplete in the worktree, rsync it from the main checkout (CER-090) — never
`pnpm install`.

**E22. Parity is mechanically enforced.** A new test in
`tests/pairmode/test_waypoint_outcome.py` reads `effortDb.ts` as text,
regex-extracts the `NON_BUILD_ROLES` array literal, parses it to a `set[str]`,
and asserts equality with `effort_db.NON_BUILD_ROLES`. The test fails with a
message naming both files when they diverge, and fails (rather than passing
vacuously) if the literal cannot be found or parses empty.

**E23. TS read-path semantics are pinned from Python.** Following the existing
`_query_waypoints` mirror pattern (`test_waypoint_outcome.py:64-91`), add
fixture-backed tests proving that, over a synthetic db containing builder,
reviewer, NULL-role and `sidebar-extractor` rows *with non-NULL tokens*: the
waypoint mirror returns the builder/reviewer/NULL rows and not the sidebar row;
the summary mirror's `total_attempts` counts the same set; the misses mirror
excludes a sidebar row above the ceiling.

### F — Documentation and backlog

**F24. `docs/architecture.md` § Effort tracking (`:2590`) records the boundary.**
A short passage states: which roles are non-build and where each is written;
that the write side is deliberately unchanged because the token cost is real;
that `NON_BUILD_ROLES` is the single Python definition and every cross-role
aggregate consumes it; which readers exclude (`_query_rollup` +
`_attach_rollup_dollars`, `refresh_effort_baseline._collect_rows`,
`queryWaypoints`, `queryEffortSummary.total_attempts`, `queryMisses`) and which
deliberately do not (`_query_models` — labels instead; `_query_effort_by_role`
and `_query_effort_by_story_ids` — already role- or story-keyed; the
`effortDb.ts` per-phase breakdown — checkpoint-only per INFRA-299); and that the
Python↔TypeScript duplication is deliberate, unavoidable across the language
boundary, and enforced by the E22 parity test. The `pairmode_effort.py` view
list (`:2654-2666`) is updated so the `rollup` and `models` entries name the
exclusion and the label respectively.

**F25. The CER-107 backlog row is annotated with the correction, not just a
resolution.** `docs/cer/backlog.md:76` gains `RESOLVED Phase 115 (INFRA-309)`
**and** an explicit statement that the row's original diagnosis was wrong: the
"polluting build-role medians" claim does not hold, because every per-role
statistic keys on `agent_role`
(`flex_build._query_effort_by_role:2659-2698`, `refresh_effort_baseline._aggregate`,
`_query_models:388-400`); the real harm was the unattributed `(phase, rail,
model)` bucket in `_query_rollup` and the `effortDb.ts` SPA counters; and the
row's alternative remedy "stop recording them" was **rejected** because sidebar
extraction is real token cost. Cite the live 297-row / 63%-of-`total_attempts`
evidence.

**F26. Full suite green.** `uv run pytest tests/pairmode/` run **without `-x`**
is green modulo the known `test_observability_ui` failure, which must be
verified to reproduce on clean `HEAD` before it is accepted as pre-existing.

## Instructions

Work in the story worktree. Order matters: the constant lands first, then each
consumer, then the docs.

1. **Re-verify the anchors** listed in `## Requires` — every line number was
   confirmed when this spec was written, but confirm before editing. If any has
   moved materially (a function renamed, a query restructured), record the
   correction in `## Evidence` and proceed against the real code.

2. **Capture the "before" evidence** (B9, E18). Using stdlib `sqlite3` (there is
   no `sqlite3(1)` on this host), record from this repo's `.companion/effort.db`:
   per-role row counts, `SELECT COUNT(*) FROM attempts`, and the output of
   `pairmode_effort.py rollup --json`. Paste into `## Evidence`. Do this before
   any code change — the after-numbers are meaningless without them.

3. **Add `NON_BUILD_ROLES` to `effort_db.py`** (A1, A2). Constant block only; no
   function in `effort_db.py` consumes it — this module is the definition site
   because it is the one module every effort reader already imports, not because
   it filters anything itself.

4. **Update `pairmode_effort.py`** (B4-B8, C10-C12). Build the predicate once —
   a small module-level helper that returns `(sql_fragment, params)` from
   `effort_db.NON_BUILD_ROLES` is preferable to writing the same `NOT IN` three
   times, and makes B6's "identical exclusion" mechanically true rather than
   coincidentally true. Remember `agent_role IS NULL OR` in the fragment.

5. **Update `refresh_effort_baseline.py`** (D13-D15). Reuse the same helper if
   the import direction allows it; otherwise consume the constant directly. Do
   not copy the three strings.

6. **Update `effortDb.ts`** (E16-E21). Three query sites; the per-phase block is
   off-limits (E20). Better-sqlite3 `.prepare(...).all(...)` takes positional
   bindings — generate the `?` placeholders from the constant's length.

7. **Write the tests** (B5, B6, B7, B8, C12, D15, E22, E23). All Python; no JS
   test runner. Extend the three existing test files listed in `touches:` — do
   not create a new test module.

8. **Build the API** (E21) and capture the "after" evidence (B9, E18).

9. **Write the documentation** (F24) and annotate the backlog row (F25). The
   backlog annotation is a *correction*, not a checkbox — a future reader must
   be able to tell that the original row's reasoning was mistaken, so that the
   same misdiagnosis is not repeated.

**Ideology note (Step 4a, resolved inline).** `docs/ideology.md`'s
"Python everywhere" fingerprint is marked *Conditional* — free to change
provided the canonical formats stay stable. This story adds a TypeScript
constant, but introduces no new language: `effortDb.ts` already exists as the
SPA's reader and this story does not migrate any logic into it. The fingerprint
is respected by keeping Python the **source of truth** (E16's comment) and by
making the duplication mechanically checked from the Python side (E22), which
also satisfies the "codifying policy over implicit convention" and
"rationale-bearing decisions over bare rules" convictions: the reason the two
lists must move together lives next to both of them. No conflict required
escalation.

## Tests

Run from the story worktree root.

Targeted, after step 7:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_pairmode_effort.py \
  tests/pairmode/test_refresh_effort_baseline.py \
  tests/pairmode/test_waypoint_outcome.py \
  -q 2>&1 | tail -30
```

Adjacent surface — the other readers of `effort.db`, to catch collateral damage:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_effort_db.py \
  tests/pairmode/test_effort_guardrail.py \
  tests/pairmode/test_validate_rebalance.py \
  tests/pairmode/test_observability_context_api.py \
  tests/pairmode/test_docs.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**, so the known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

TypeScript build (E21) — if the vendored payload is incomplete, rsync it from
the main checkout; never `pnpm install`:

```bash
cd skills/observability && pnpm --filter @flex-obs/api build
```

## Evidence

**Anchor correction (step 1).** The `## Requires` line-number anchors for
`effort_db.py`, `pairmode_effort.py`, and `refresh_effort_baseline.py` matched
source exactly at build time; no drift. `effortDb.ts` had one real anchor
drift: the story's `## Requires` and `## Instructions` name a function
`queryMisses` at `:246` (count `:277`, SELECT `:281-287`). No function of
that name exists in the current `effortDb.ts` — the "near-miss" query is
named `querySpendOutliers` (INFRA-321 § E3 renamed it away from the
`_miss`/`_block` framing, since no block ever occurs at these numbers). E19's
obligation ("exclude in both its count query and its row query, so the miss
count and the listed entries agree") is honoured against the real function:
`querySpendOutliers`'s `count` query and its `entries` row query both gained
the identical `NON_BUILD_ROLE_EXCLUSION_SQL` predicate. `## Tests` § E23's
mirror test is named accordingly
(`_query_spend_outliers_mirror` / `TestNonBuildRoleExclusionTsMirror` in
`tests/pairmode/test_waypoint_outcome.py`).

**Before (step 2), against this repo's live `.companion/effort.db`:**

Per-`agent_role` row counts:

```
('sidebar-extractor', 312)
('builder',            118)
('reviewer',           103)
('security-auditor',    17)
('intent-reviewer',     15)
('loop-breaker',         1)
```

`SELECT COUNT(*) FROM attempts` → **566** (`total_attempts` before, mirroring
`queryEffortSummary`).

`pairmode_effort.py rollup --json` (before): 46 rows; `sum(attempts)` across
all rows = **566**. The anonymous `(phase=NULL, rail=NULL, model='llama3.1:8b')`
bucket — the sidebar-extraction rows' model tag on this repo — reports
`attempts: 312, total_tokens: 0`, an unattributed row that dwarfs every real
rail's attempt count. (Two further `phase=NULL, rail=NULL` rows also exist,
`model='opus'` with 2 attempts and `model=NULL` with 2 attempts — these are
unrelated non-sidebar rows with a null phase/rail, e.g. early loop-breaker
recordings, and are correctly retained since their `agent_role` is not in
`NON_BUILD_ROLES`.)

**After (step 8), same database, same commands:**

`pairmode_effort.py rollup --json` (after): 45 rows — the
`model='llama3.1:8b'` anonymous bucket is gone entirely; `sum(attempts)` =
**254**.

**Arithmetic:** `566 - 254 = 312`, exactly the `sidebar-extractor` row count
above. No `builder`/`reviewer`/`security-auditor`/`intent-reviewer`/
`loop-breaker` row was touched — none of those roles are in
`NON_BUILD_ROLES`, and the two non-sidebar `phase=NULL, rail=NULL` rows noted
above survive in both the before and after row sets.

`SELECT COUNT(*) FROM attempts WHERE agent_role IS NULL OR agent_role NOT IN
('sidebar-extractor', 'seed-miner', 'seed-reconcile')` → **254** — the
`queryEffortSummary.total_attempts` mirror (E18), confirming the SPA's
headline attempt counter drops from 566 (63.8% attributable to
`sidebar-extractor` on this repo, consistent with the story's Context
observation of majority-non-build attempt counts) to 254 on this repo.

Text-mode disclosure line, confirmed present:

```
(excluding non-build roles: seed-miner, seed-reconcile, sidebar-extractor)
```

**Type-check / build (E21):** `pnpm --filter @flex-obs/api build` succeeded
(`tsc` clean, no output); `pnpm exec tsc --noEmit` in `skills/observability/api`
also produced no output (clean).

**`git diff` on `effortDb.ts`'s per-phase block (E20):**
`git diff -U0 skills/observability/api/src/readers/effortDb.ts | grep -n 'DISTINCT phase'`
and `... | grep -n 'by_phase'` both produced no output — no hunk touches
that block.

**Full suite (F26):** `uv run pytest tests/pairmode/ -q` (no `-x`) →
**4586 passed, 211 skipped**, zero failures. `test_observability_ui.py`
(37 tests) passed cleanly in this worktree — the CER-090 vendored
`node_modules` gap this story's `## Requires` flagged as a known
worktree-only risk did not reproduce here, so no rsync repair was needed.

Machine-checkable Ensures:

```bash
grep -c 'NON_BUILD_ROLES' skills/pairmode/scripts/effort_db.py                    # >= 1, single definition
grep -rn "'sidebar-extractor'\|\"sidebar-extractor\"" skills/ --include=*.py      # only sidebar.py writers + effort_db.py def
grep -n 'NON_BUILD_ROLES' skills/pairmode/scripts/pairmode_effort.py             # imported, used
grep -n 'NON_BUILD_ROLES' skills/pairmode/scripts/refresh_effort_baseline.py     # imported, used
grep -n 'NON_BUILD_ROLES' skills/observability/api/src/readers/effortDb.ts       # exported const + 3 query sites
git diff -U0 skills/observability/api/src/readers/effortDb.ts | grep -n 'DISTINCT phase'   # no output (E20)
grep -c 'excluding non-build roles' skills/pairmode/scripts/pairmode_effort.py   # 1
grep -n 'role_class' skills/pairmode/scripts/pairmode_effort.py                  # query + columns list
grep -n 'NON_BUILD_ROLES' docs/architecture.md                                   # § Effort tracking passage
grep -c 'CER-107.*RESOLVED Phase 115' docs/cer/backlog.md                        # 1
```

Acceptance:

- `## Evidence` is populated with the before/after rollup and `total_attempts`
  numbers from step 2 and step 8, and the arithmetic reconciles;
- every new test from A-F passes;
- every pre-existing test in the six adjacent files passes **by its original
  name** — in particular `test_idempotent_byte_identical_output` and the
  CER-055 pass-rate tests;
- `pnpm --filter @flex-obs/api build` succeeds and `tsc --noEmit` is clean;
- the full suite is green modulo the known `test_observability_ui` failure,
  verified to reproduce on clean `HEAD`.

## Out of scope

- **Changing any writer.** `sidebar.py:427-449` / `:479-503`,
  `mine_sessions.py:232,262`, `reconcile.py:83`, `effort_recorder.py:20`,
  `record_attempt.py` and `effort_db.insert_attempt` /
  `insert_or_update_attempt` are untouched. CER-107's "stop recording them"
  remedy is explicitly rejected (see `## Context`): sidebar extraction is real
  token cost, and deleting the record trades data for cosmetics. `git diff`
  shows no hunk in any writer.
- **Any schema change.** No new column, no new `_MIGRATIONS` entry, no index,
  no backfill or deletion of existing rows. The 297 sidebar rows stay exactly
  where they are.
- **`effortDb.ts`'s per-phase breakdown** (`:205-235`). Checkpoint-only by
  design; owned and documented by INFRA-299 (E20).
- **`flex_build._query_effort_by_role` (`:2659`) and
  `_query_effort_by_story_ids` (`:2701`).** Already immune — the first keys by
  role, the second scopes by an explicit story-ID list. F24 records why no
  change was needed rather than leaving the omission to be rediscovered.
- **Filtering non-build roles out of the `models` report.** C10 deliberately
  retains them; the cost of sidebar extraction is a question the report should
  answer, so it is labelled, not hidden.
- **Adding a JavaScript/TypeScript test runner.** Observability behaviour is
  asserted from Python against synthetic `sqlite3` fixtures plus source-text
  parsing (E22, E23), matching the existing `test_waypoint_outcome.py` pattern.
- **A generated-from-Python TS constant (codegen).** A build step that emits the
  TS list from `effort_db.py` would remove the duplication, but adds a
  generation step to a vendored, checked-in API package for three strings. The
  parity test is the cheaper enforcement; if the set grows past a handful of
  roles, revisit.
- **Anything INFRA-306 / INFRA-307 / INFRA-308 own** — CORS and `abs_path`
  gating in `server.ts` / `routes/user.ts`, the vendored-payload allow-list, and
  the plugin-manifest skill guard. This story shares no file with any of them.
- **The CER-107 row's `Phase` cell beyond this story's annotation**, and every
  other backlog row: INFRA-310 owns the backlog truth pass.
