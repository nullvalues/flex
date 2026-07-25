---
id: INFRA-259
rail: INFRA
title: Live smoke test of async effort recording — fresh-session reconciliation plus a thin build cycle with populated phase-scoped rollup
status: planned
phase: "102"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/stories/INFRA/INFRA-259.md
touches: []
---

## Context

INFRA-258 (cp101) replaced synchronous effort recording with a two-phase
async scheme: at spawn time `record_attempt_from_transcript` writes a row with
`tokens_total` and `outcome` NULL but the spawn's own `agent_id` and
`output_file` persisted (`effort_db.set_spawn_ref`); later, a reconciliation
sweep (`subagent_transcript.reconcile_pending_attempts`, driven from a
subsequent Task/Agent PostToolUse event and, best-effort, from
`hooks/session_start.py`) reads the completed subagent transcript, confirms
the last entry carries `stop_reason: end_turn`, dedupes usage by `message.id`
(last-wins), and backfills `tokens_total`/`outcome` — bumping the FAIL
escalation counter at reconciliation time rather than at spawn time.
INFRA-256 made `checkpoint-report`'s rollup phase-scoped; INFRA-257 made
`attempt_number` truthful; checkpoint workers now attribute to `phase:<key>`.

Every one of those changes is verified by unit tests against synthetic
transcripts. None of them has yet been observed working against the real
harness in a real session. The live evidence available at spec time is
suggestive but incomplete: `.companion/effort.db` rows 343 (`phase:101`,
security-auditor) and 344 (`phase:101`, intent-reviewer) carry spawn refs but
still have NULL `tokens_total`/`outcome` — correct, because no spawn or
session start has fired since they were written, so reconciliation is
genuinely pending rather than broken. Rows ≤342 predate the fix, carry no
refs, and are unrecoverable by design.

Before this machinery is rolled out fleet-wide, the operator wants proof from
the field, not from fixtures. This story is that proof. It is a **verification
procedure**, not an implementation: it defines the observations that must be
made, the exact commands that make them, the pass criteria for each, and the
single place the evidence is written down. Its own build cycle — builder and
reviewer spawns for a doc-class story — is deliberately the specimen: the
smoke test needs live spawns, and this phase's own cycles supply them, so no
synthetic spawn is ever created.

**Decision — manual documented procedure, not a new script (recorded here so
it is not re-litigated).** The alternative considered was a small idempotent
`skills/pairmode/scripts/smoke_effort.py`. It was rejected: every file in
`skills/pairmode/scripts/` is a durable CLI with a dedicated test file in
`tests/pairmode/` and an entry in the `docs/architecture.md` CLI surface, so
adding one would convert a one-shot field observation into a permanent,
test-carrying, documented tool for a check that runs once per rollout. The
observations here are read-only SQL over an existing schema plus one existing
CLI (`flex_build.py checkpoint-report`); writing them as exact, copy-pasteable
commands in this story makes them just as repeatable as a script, and the
evidence — which is the actual deliverable — is preserved in the story file
where a later reader will look for it. If the fleet rollout later wants this
automated, the correct home is a read-only subcommand on the existing
`pairmode_effort.py` surface, not a new top-level script; that is out of scope
here (see `## Out of scope`).

## Requires

- INFRA-258 is complete and merged on `main` at `/mnt/work/flex`:
  `skills/pairmode/scripts/subagent_transcript.py` exposes
  `reconcile_pending_attempts` and calls it from `record_attempt_from_transcript`;
  `skills/pairmode/scripts/effort_db.py` exposes `set_spawn_ref`,
  `pending_reconcilable`, and `reconcile_attempt`; the `attempts` table has
  the `agent_id` and `output_file` columns.
- INFRA-256 (phase-scoped `checkpoint-report` rollup) and INFRA-257 (truthful
  `attempt_number`) are complete.
- `hooks/session_start.py` contains the best-effort reconciliation catch-up
  added by INFRA-258.
- `.companion/effort.db` exists at `/mnt/work/flex/.companion/effort.db` and
  contains rows with `id` 343 and 344 (`phase:101`, roles `security-auditor`
  and `intent-reviewer`) with non-NULL `output_file` and NULL `tokens_total`.
- Effort tracking is enabled for this project (the flag
  `reconcile_pending_attempts` checks before sweeping).
- All commands in this story are run from `/mnt/work/flex`. The
  `/mnt/work/flex-harness` worktree holds a stale toolchain and must not be
  used to run `flex_build.py` for this story.
- `docs/phases/phase-102.md` exists with a `## Stories` table listing
  INFRA-259 and INFRA-260, and a `### CP-102 Cold-eyes checklist` section.

## Ensures

Each assertion below names its **owner** — the actor who makes the observation
and records it — because the observations are spread across the story's own
build cycle and cannot all be made by one actor. The reviewer verifies that
every assertion owned by the builder is present in `## Smoke results` with
pasted command output and an explicit PASS/FAIL, and that assertions owned by
a later actor are present as labelled, un-filled placeholders with their owner
named.

1. **Recording surface — `## Smoke results` exists in this file** (owner:
   builder). This story file contains a top-level `## Smoke results` section
   with exactly the six labelled subsections `### A. Pre-state snapshot`,
   `### B. Fresh-session reconciliation`, `### C. In-session sweep`,
   `### D. New-row integrity`, `### E. Preliminary phase-102 rollup`, and
   `### F. Checkpoint rollup (cp-102)`. Each subsection contains the command
   that was (or will be) run, its verbatim output, and a final line reading
   `RESULT: PASS`, `RESULT: FAIL — <reason>`, or, for the not-yet-observable
   subsections only, `RESULT: PENDING — owner: <actor>`. No subsection is
   empty.

2. **Pre-state snapshot is recorded before any other observation** (owner:
   builder). `### A. Pre-state snapshot` contains the output of query Q1
   (`## Instructions` step 2) showing, for every row with
   `output_file IS NOT NULL`, its `id`, `story_id`, `agent_role`,
   `attempt_number`, `tokens_total`, `outcome`, and `ts`; plus the output of
   query Q0 showing `MAX(id)`. The snapshot is taken as the builder's first
   action, before any file is edited, so that later observations have a
   baseline. It states in one line which row ids were pending
   (`tokens_total IS NULL`) at snapshot time.

3. **Fresh-session reconciliation backfilled the cp101 rows** (owner:
   builder). Rows 343 and 344 have `tokens_total` non-NULL and
   `> 0`, `outcome` non-NULL and one of the documented outcome values, and
   `attempt_number` unchanged from its pre-INFRA-258 recorded value
   (`attempt_number >= 1`, and equal to 1 for these two rows, which were each
   the only spawn of their role for phase 101). Evidence: query Q1's output
   in `### B`, showing both rows populated. **Failure interpretation is part
   of the assertion:** if either row is still NULL *and* query Q2 (pending
   rows) shows its `output_file` path no longer exists on disk, the result is
   recorded as `RESULT: FAIL — transcript expired` and treated as a real
   finding, not a skip; if both rows are populated, `RESULT: PASS`. The
   subsection states explicitly which trigger is believed to have fired
   (SessionStart catch-up vs. an intervening spawn's PostToolUse sweep) and
   the reasoning, based on the `ts` values and Q0's `MAX(id)` from `### A`.

4. **In-session sweep backfills at a later spawn's PostToolUse** (owner:
   builder). `### C` demonstrates that at least one row that was pending in
   `### A`'s snapshot is non-pending after a subsequent Agent/Task spawn in
   the same session, evidenced by a re-run of query Q1 whose output differs
   from `### A`'s for that row id. If `### B` already showed all pre-existing
   pending rows reconciled by the SessionStart path, `### C` instead
   demonstrates the sweep against the builder's *own* pending spawn row — in
   which case `### C` is recorded as `RESULT: PENDING — owner: orchestrator,
   at review close`, because the builder's own row cannot reconcile during the
   builder's own run (its transcript is not yet complete). Exactly one of
   those two forms is present; the subsection states which and why.

5. **New rows carry spawn refs at launch** (owner: builder). Query Q3
   (`SELECT` restricted to `story_id = 'INFRA-259'`) shows a row for
   `agent_role = 'builder'` with non-NULL `agent_id` and non-NULL
   `output_file`, `attempt_number = 1` (or the true attempt ordinal if this
   story was retried — the number must equal the count of prior builder rows
   for INFRA-259 plus one, per INFRA-257), and `story_id` exactly `INFRA-259`
   — never `phase:102`, never `unattributed`, never NULL. Recorded in
   `### D`.

6. **New rows reconcile to real, plausible token counts** (owner:
   orchestrator, at review close). `### D` additionally records, after the
   reviewer spawn has completed, a re-run of Q3 showing both the builder row
   and the reviewer row with `tokens_total` non-NULL and `> 0`, `outcome`
   non-NULL, correct `story_id` attribution for both, and `attempt_number`
   truthful for each role. Each recorded `tokens_total` is cross-checked
   against the token figure the harness reported in that spawn's task
   notification and stated to agree to within one order of magnitude; the
   comparison is written out (`recorded X vs harness-reported Y — same order
   of magnitude: yes/no`). A disagreement of more than one order of magnitude
   is `RESULT: FAIL`, not a rounding note.

7. **The phase-102 rollup is populated** (owner: orchestrator, at review
   close for the preliminary run; owner: orchestrator, at cp-102 for the
   final run). `### E` contains the verbatim output of

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py checkpoint-report
   ```

   run from `/mnt/work/flex`, showing a heading naming phase 102, non-zero
   attempt counts and a non-`None` median-token figure for both `builder` and
   `reviewer` under the phase-scoped section, a per-story line for INFRA-259
   with non-zero counts, and a per-story line for INFRA-260 (expected to show
   the explicit zero/no-attempts marker at this point, since INFRA-260 has not
   been built yet — its presence as a listed line is what is being asserted).
   `### F` holds the same command's output re-run at cp-102 checkpoint time,
   where INFRA-260's line must also show non-zero counts. Until it is run,
   `### F` reads `RESULT: PENDING — owner: orchestrator, at cp-102`.

8. **Checkpoint cross-reference** (owner: orchestrator, at cp-102). The
   `### CP-102 Cold-eyes checklist` section of `docs/phases/phase-102.md`
   carries a one-line pointer to this story's `## Smoke results` section and a
   one-line overall verdict for the smoke test. The evidence itself lives here,
   not in the phase doc — one location, so a later reader is not made to
   reconcile two partial records. This story does not edit the phase doc; the
   orchestrator fills the checklist at checkpoint time as it does for every
   phase.

9. **Accepted limitations are recorded, not silently omitted** (owner:
   builder). This file contains an `## Accepted limitations` section naming
   (a) the deferred live deliberate-FAIL cycle and its unit-test substitute,
   and (b) the unrecoverable rows ≤342 — each with the reason it was accepted
   and by whom.

10. **No production code, schema, or test file is changed by this story.**
    `git diff --stat` for this story's build touches only
    `docs/stories/INFRA/INFRA-259.md`. No file under
    `skills/pairmode/scripts/`, `hooks/`, or `tests/` is modified, and no new
    script is created.

11. **All observations are read-only with respect to effort.db.** Every query
    in `## Smoke results` opens the database with SQLite's read-only URI mode
    (`file:...?mode=ro`). No `UPDATE`, `INSERT`, `DELETE`, or manual
    reconciliation is performed — the whole point is to observe what the
    system does unaided.

## Instructions

You are recording field evidence, not writing code. Work in
`/mnt/work/flex` (the main worktree). The only file you may modify is this
one.

1. **Do not run anything against `/mnt/work/flex-harness`.** That worktree's
   `flex_build.py` predates INFRA-256's phase-scoped rollup and will produce a
   misleading lifetime-only report. Every command below is run with
   `/mnt/work/flex` as the working directory.

2. **Take the pre-state snapshot first, before editing anything.** Note that
   the `sqlite3` command-line binary is not installed in this environment;
   use Python's `sqlite3` module via `uv run`. The four queries this story
   uses:

   Q0 — highest row id, to timestamp the snapshot:

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python -c "
   import sqlite3
   c = sqlite3.connect('file:.companion/effort.db?mode=ro', uri=True)
   print(c.execute('SELECT MAX(id), COUNT(*) FROM attempts').fetchone())
   "
   ```

   Q1 — every row that carries a spawn ref, with its reconciliation state:

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python -c "
   import sqlite3
   c = sqlite3.connect('file:.companion/effort.db?mode=ro', uri=True)
   rows = c.execute('''
       SELECT id, story_id, agent_role, attempt_number, tokens_total,
              outcome, agent_id IS NOT NULL AS has_agent_id,
              output_file IS NOT NULL AS has_output_file, ts
       FROM attempts
       WHERE output_file IS NOT NULL
       ORDER BY id
   ''').fetchall()
   for r in rows:
       print(r)
   "
   ```

   Q2 — pending rows only, plus whether the referenced transcript still
   exists on disk (used to distinguish "not yet swept" from "transcript
   expired"):

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python -c "
   import sqlite3, pathlib
   c = sqlite3.connect('file:.companion/effort.db?mode=ro', uri=True)
   rows = c.execute('''
       SELECT id, story_id, agent_role, output_file, ts
       FROM attempts
       WHERE tokens_total IS NULL AND output_file IS NOT NULL
       ORDER BY id
   ''').fetchall()
   for r in rows:
       print(r, 'transcript_exists=', pathlib.Path(r[3]).exists())
   "
   ```

   Q3 — this phase's own rows:

   ```bash
   PATH=$HOME/.local/bin:$PATH uv run python -c "
   import sqlite3
   c = sqlite3.connect('file:.companion/effort.db?mode=ro', uri=True)
   rows = c.execute('''
       SELECT id, story_id, agent_role, attempt_number, model, tokens_total,
              outcome, agent_id IS NOT NULL AS has_agent_id,
              output_file IS NOT NULL AS has_output_file, ts
       FROM attempts
       WHERE story_id IN ('INFRA-259', 'INFRA-260')
          OR phase = '102'
       ORDER BY id
   ''').fetchall()
   for r in rows:
       print(r)
   "
   ```

   Paste Q0 and Q1 output into `### A. Pre-state snapshot` immediately, before
   making any other edit to this file, and add the one-line statement of which
   row ids were pending at snapshot time. This baseline is what makes
   assertions 3 and 4 falsifiable — without it, a row that was never pending
   cannot be distinguished from one that was reconciled.

3. **Fill `### B. Fresh-session reconciliation`** from the same Q1 output,
   focused on rows 343 and 344. If either is still pending, run Q2 and record
   whether its `output_file` still exists. Write the reasoning about which
   trigger fired: if `MAX(id)` from Q0 is still 344 and the rows are now
   populated, no intervening spawn wrote a row, so the SessionStart catch-up
   is the only candidate; if `MAX(id)` is higher, an intervening spawn's
   PostToolUse sweep may be responsible and the subsection must say the
   evidence is ambiguous rather than claiming the SessionStart path.

4. **Fill `### C. In-session sweep`** per assertion 4. If `### A` showed
   pending rows and a later spawn in this same session cleared them, re-run Q1
   and paste the differing output. If everything pre-existing was already
   reconciled at session start, the only remaining demonstration is the
   builder's own row, which cannot reconcile during the builder's own run —
   record `RESULT: PENDING — owner: orchestrator, at review close` with a
   one-line explanation of the ordering constraint. Do not fabricate a spawn
   to force the observation; this phase's own builder/reviewer cycles are the
   designated live traffic.

5. **Fill `### D. New-row integrity`** with Q3's output, asserting the
   builder-row properties in assertion 5. Leave the post-reviewer half of
   `### D` (assertion 6) as an explicitly labelled `RESULT: PENDING — owner:
   orchestrator, at review close` block with the exact command to re-run, so
   the orchestrator can complete it without re-deriving anything.

6. **Create `### E` and `### F`** as `RESULT: PENDING` placeholders naming
   their owner and carrying the exact `checkpoint-report` command from
   assertion 7. Do not run `checkpoint-report` as the builder: at builder time
   the reviewer row does not exist yet and the rollup would be recorded
   half-populated, which is exactly the misleading artifact this phase exists
   to eliminate.

7. **Write `## Accepted limitations`** with the two entries from assertion 9.
   For the deferred FAIL cycle, state plainly: the reconciled-FAIL escalation
   counter bump is covered by unit tests in
   `tests/pairmode/test_subagent_transcript.py`; a live deliberate-FAIL cycle
   was considered and deferred by operator decision because forcing a real
   builder failure costs a full retry ladder for one counter observation; the
   accepted risk is that the FAIL-at-reconciliation-time path is
   fixture-verified only. Do not spec, script, or perform a synthetic FAIL.

8. **Do not backfill, repair, or hand-reconcile any row.** Rows ≤342 stay as
   they are. If a query reveals a bug in the reconciliation logic, record it
   as a `RESULT: FAIL` finding with the evidence — filing the fix is the
   orchestrator's call, not this story's.

9. **Ideology note (Step 4a, resolved inline).** Two convictions shaped this
   spec and are worth naming so a later agent does not undo them.
   "Rationale-bearing decisions over bare rules" is why the
   script-vs-manual-procedure decision and the deferred-FAIL decision are
   written out with their reasons in `## Context` and `## Accepted
   limitations` rather than left as bare instructions. "Decision fidelity
   over convenience" is why assertion 3 requires a FAIL to be recorded as a
   finding rather than skipped when a transcript has expired, and why
   assertion 1 forbids empty subsections — a smoke test whose negative
   results quietly vanish provides exactly the false confidence the
   "never silently pass contradictions" constraint exists to prevent. No
   conflict with `docs/ideology.md` required routing around; the
   "sidebar owns all state writes" constraint is untouched, as every
   observation here is read-only.

## Tests

This is a `story_class: doc` verification story. It writes no code and no test
file; the assertions are field observations recorded in `## Smoke results`,
verified by the reviewer against pasted command output.

Regression check only — the story must not have perturbed the suite:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Run without `-x`, so a known pre-existing failure cannot mask a real one.

Acceptance: suite result is unchanged from clean `HEAD` — green except the
known pre-existing `test_observability_ui.py::test_ui_build_emits_dist_index_html`
failure, which must be shown to reproduce on clean `HEAD` if it appears. The
reviewer reports `TEST RUN: documentation story — no test file expected`
alongside this result.

## Out of scope

- **Backfilling rows ≤342.** They predate INFRA-258, carry no `agent_id` or
  `output_file`, and are unrecoverable by design. No migration, no estimate,
  no deletion.
- **A synthetic deliberate-FAIL builder cycle** to observe the escalation
  counter bump live — deferred by operator decision; see
  `## Accepted limitations`.
- **Any new script**, including `skills/pairmode/scripts/smoke_effort.py`, and
  any new subcommand on `pairmode_effort.py`, `effort_db.py`, or
  `flex_build.py`. If fleet rollout later wants an automated pending-rows
  check, it belongs as a read-only view on the existing `pairmode_effort.py`
  surface and needs its own story.
- **Fixing anything the smoke test finds.** A FAIL is recorded as evidence;
  remediation is a separate story in this phase or the CER backlog, at the
  orchestrator's discretion.
- **The release-channel fast-forward** and the `record-checkpoint-step`
  tagging route — INFRA-260.
- **Fleet-wide rollout of INFRA-258** to sibling projects. This story
  establishes the evidence that rollout depends on; it does not perform it.
- **Changes to `hooks/session_start.py`**, `subagent_transcript.py`, or the
  `attempts` schema.
- **Observability SPA/API rendering** of the reconciled rows.

## Smoke results

<!-- Filled during and after this story's own build cycle. Owners are named per
     subsection. Every subsection must end with a RESULT line; none may be empty. -->

### A. Pre-state snapshot

<!-- owner: builder, first action -->

### B. Fresh-session reconciliation

<!-- owner: builder -->

### C. In-session sweep

<!-- owner: builder, or orchestrator at review close — see assertion 4 -->

### D. New-row integrity

<!-- owner: builder (spawn refs) + orchestrator at review close (reconciled tokens) -->

### E. Preliminary phase-102 rollup

<!-- owner: orchestrator, at review close -->

### F. Checkpoint rollup (cp-102)

<!-- owner: orchestrator, at cp-102 checkpoint -->

## Accepted limitations

<!-- Filled by the builder per Instructions step 7. Each entry names the
     limitation, the reason it was accepted, and who accepted it. -->
