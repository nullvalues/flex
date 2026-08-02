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
(`subagent_transcript.py`), and also has zero readers outside tests; `story_class`/
`model_selection_reason` are populated only by the legacy `record_attempt.py` CLI writer that
`CLAUDE.build.md` says is not part of the live loop — only 49 of 575 live rows carry them,
degrading `pairmode_effort`'s decision-quality report section to a near-empty group on real data.
`effort_db.next_attempt_number` has zero callers — 43 lines of maintained dead code whose own
docstring warns against the racy pattern its existence invites.

For each column/function: decide keep-and-wire (give it a real writer and reader) or remove
(migration/schema change, plus updating whatever reports reference it) — don't leave a mix of dead
and half-alive columns in the schema. Note: if INFRA-345 (de-duplicating the legacy
`record_attempt.py` writer) retires that CLI path entirely, `story_class`/`model_selection_reason`'s
sole writer disappears with it — coordinate with INFRA-345's landed shape before deciding this
column's fate.

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
| `duration_ms` | none (tests only) | **Wire both ends, or remove** — see Ensures 3 |
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
3. **Every reference to the four items across the repo**, gathered before editing:
   ```bash
   grep -rn "tool_uses\|duration_ms\|next_attempt_number" skills/ tests/ docs/ hooks/ 2>/dev/null
   grep -rn "story_class\|model_selection_reason" skills/pairmode/scripts/effort_db.py \
     skills/pairmode/scripts/effort_recorder.py skills/pairmode/scripts/pairmode_effort.py \
     skills/pairmode/scripts/record_attempt.py skills/pairmode/scripts/refresh_effort_baseline.py \
     skills/pairmode/scripts/flex_build.py
   ```
   Note especially: `flex_build.py`'s `story-cost-estimate` sampling and
   `refresh_effort_baseline.py` both read from this table and may select columns positionally or
   by `SELECT *`; a column drop that breaks either is a regression, not a cleanup.
4. **The live recording path end to end** — which process actually inserts an attempt row during a
   real build (`effort_recorder.py` and the reconcile path in `subagent_transcript.py`), and what
   dispatch-time facts are already in hand at that point. `story_class` lives in the story file's
   frontmatter; `model_selection_reason` is produced by `model_selector.py` at dispatch. Establish
   which of the two is already reachable at write time and which needs plumbing.
5. **`docs/architecture.md`'s description of the effort/attempt schema**, if it enumerates columns —
   a schema change that leaves the architecture doc describing dropped columns is an incomplete
   story (see Ensures 6).
6. **Baseline suite count.** Run the full suite without `-x` first and record pass/fail counts, so
   a pre-existing failure is not mistaken for one this story introduced.

## Ensures

1. **`tool_uses` is gone, end to end.** `grep -rn "tool_uses" skills/ tests/ docs/` returns no
   hits. The column is absent from `effort_db.py`'s `CREATE TABLE`, absent from every insert
   helper's parameters, and an existing `effort.db` opened by the current code no longer exposes
   it (`PRAGMA table_info(<attempts table>)` lists no `tool_uses`). *Forbidden proxy:* leaving the
   column in the schema while merely deleting the `tool_uses=None` argument — a still-present,
   always-null column is the exact half-alive state this story exists to remove.

2. **`effort_db.next_attempt_number` is gone.** The function is deleted from `effort_db.py`;
   `grep -rn "next_attempt_number" skills/ tests/ docs/` returns no hits. *Forbidden proxy:*
   marking it deprecated in a docstring while leaving the body in place.

3. **`duration_ms` is either fully wired or fully removed — never half.** Exactly one of:
   - **(a) Wired:** every attempt row written by the *primary* live path (not only the
     file-fallback branch) carries a non-null `duration_ms`, a unit test asserts this against the
     primary path specifically, **and** `pairmode_effort` renders the value in at least one report
     section with a test asserting the rendered output contains it; or
   - **(b) Removed:** `grep -rn "duration_ms" skills/ tests/ docs/` returns no hits and
     `PRAGMA table_info` no longer lists the column.

   Branch (a) is preferred and must be attempted first; branch (b) is taken only if the primary
   reconcile path has no reliable wall-clock start/end available without adding new state — in
   which case the builder records *why* in `## Evidence`. *Forbidden proxy:* wiring the writer
   without a reader ("we'll report on it later"), or leaving the fallback-branch writer as the
   only writer.

4. **`story_class` and `model_selection_reason` are written by the live path.** After this story,
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

5. **`pairmode_effort`'s decision-quality section reports on real data.** A test constructs a
   database whose rows were written only by the live path (no `record_attempt.py`-seeded rows) and
   asserts the decision-quality section is populated rather than reporting an empty group.

6. **No dangling references anywhere.** After the change: `pairmode_effort.py`,
   `refresh_effort_baseline.py`, and `flex_build.py`'s `story-cost-estimate` all run without error
   against both a freshly-created database and a database created before this story
   (migration-upgraded in place). `docs/architecture.md` describes no column this story removed.

7. **Migration is idempotent and non-destructive to surviving data.** Running the schema-upgrade
   path twice against the same `effort.db` succeeds both times, and every surviving column's values
   for pre-existing rows are unchanged (a test asserts row count and at least the cost/token
   columns are byte-identical before and after upgrade). *Forbidden proxy:* recreating the table
   empty, or requiring the operator to delete `effort.db`.

8. **Suite green.** Full run without `-x`; baseline count from Requires 6 held or improved.

## Instructions

1. Do Requires 1 first and stop if INFRA-345 has not landed. Every decision about
   `story_class`/`model_selection_reason` depends on whether the legacy CLI writer still exists.
2. Do all of Requires 2–5 (recon) before editing a single line. This story's whole risk is a column
   drop that breaks a reader you didn't know about.
3. Sequence the work as: (i) removals of the zero-reader items (`tool_uses`,
   `next_attempt_number`), (ii) the `duration_ms` decision, (iii) the
   `story_class`/`model_selection_reason` live-writer wiring, (iv) architecture-doc and test
   updates. Keep them separable so a problem in (iii) doesn't strand (i).
4. **Column removal mechanism.** Use whatever idempotent schema-evolution mechanism `effort_db.py`
   already has (Requires 2). Prefer `ALTER TABLE ... DROP COLUMN` where the runtime SQLite supports
   it (guard on `sqlite3.sqlite_version_info`), with a create-new-table / copy-surviving-columns /
   swap rebuild as the fallback for older SQLite. Whichever path, it must satisfy Ensures 7 —
   idempotent and value-preserving. Do not invent a second, parallel migration framework alongside
   the existing one.
5. **Ideology-alignment note (Step 4a, resolved inline).** Two constraints from
   `docs/ideology.md` bear directly on Ensures 4 (spec-preflight flags `docs/ideology.md` as
   named-but-out-of-declared-scope; that is intentional — it is cited here as a read-only
   constraint source and must not be edited by this story, so it is deliberately absent from
   `touches:`) and are already routed around in the instructions
   above:
   - *"Hooks are thin relays only" / "Sidebar owns all state writes"* — wiring the live writer must
     **not** add story-file reads, model-selection lookups, or any blocking work inside a hook
     script. The enrichment belongs in the recorder/reconcile layer that already owns the
     `effort.db` write; the hook keeps emitting to the pipe and exiting. If the only apparent way
     to reach `story_class` at write time is from inside a hook, that is the wrong seam — plumb the
     value through the pipe payload / recorder instead.
   - *"Build-cost accounting and orchestrator context control are two independent tracks"* — this
     story touches `effort.db` (track a) only. Nothing added or removed here may be read by
     `context_health.py`, `context_budget_check.py`, or the observability `/context` route, and no
     new field may be introduced that invites summing effort spend into an orchestrator-window
     reading. If a grep in Requires 3 shows any of those three consumers touching a column in this
     story's scope, stop and report it rather than adapting them.
6. Update the tests listed in `touches:` rather than deleting coverage. Where a test asserted the
   old dead-column behaviour (e.g. asserting `tool_uses is None`), delete that specific assertion
   and say so in `## Evidence` — do not delete the whole test if it also covers surviving columns.
7. Record in `## Evidence`: the disposition actually taken for `duration_ms` (branch a or b, with
   reasoning), the migration mechanism used, the full list of readers found in Requires 3, and
   every test assertion removed.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -k "effort or subagent_transcript or record_attempt" -q 2>&1 | tail -30
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

Acceptance: both green; the second run is the full suite **without `-x`** (a known pre-existing
failure must not mask a new one), and its counts match or beat the Requires 6 baseline.

Reviewer negative checks (each must return no hits):

```bash
grep -rn "tool_uses" skills/ tests/ docs/
grep -rn "next_attempt_number" skills/ tests/ docs/
```

Reviewer positive check: a test exists that drives the *live* insert path (not
`record_attempt.py`) and asserts `story_class` and `model_selection_reason` are non-null and equal
to the dispatch-time values.

## Out of scope

- Any change to `record_attempt.py`'s existence or CLI surface beyond what Ensures 1–4 mechanically
  require — retiring/reconciling that writer is INFRA-345's story, and this one builds on its
  landed result.
- Adding new `effort.db` columns or new report sections beyond the single `duration_ms` reader that
  Ensures 3 branch (a) requires.
- Reworking `pairmode_effort`'s report layout, formatting, or other sections; only the
  decision-quality section's *data availability* is in scope.
- `flex_build.py`'s `story-cost-estimate` sampling *logic* — it must keep working (Ensures 6), but
  its estimation model is not being changed here.
- Any change to orchestrator context accounting (`context_health.py`, `context_budget_check.py`,
  the observability `/context` route) — explicitly walled off by Instructions 5.
- Backfilling `story_class`/`model_selection_reason` onto the 526 historical rows that lack them;
  this story fixes the writer going forward, it does not reconstruct the past.
