---
id: INFRA-345
rail: INFRA
title: De-duplicate attempt-recording writers: retire or reconcile the legacy record_attempt.py CLI path
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/reviewer/procedure.md
  - skills/pairmode/scripts/record_attempt.py
touches:
  - tests/pairmode/test_record_attempt.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
<!-- SPEC-PREFLIGHT NOTE: hooks/post_tool_use.py, tests/pairmode/test_effort_db.py, and
     skills/pairmode/templates/CLAUDE.build.md.j2 are named in Context/Ensures/Instructions but are
     deliberately NOT in primary_files/touches — this story reads/confirms their existing
     (already-correct) content and requires their tests to keep passing unmodified; it does not
     write to any of the three. See Context § Evidence and Instructions step 6/step 5(d). -->
## Context

HIGH finding F11 of `docs/build-loop-cold-eyes-review-20260801.md` (opus, with live examples): two
independent writers can both record a row for what should be the same spawn — the legacy
`record_attempt.py` CLI path and the hook-driven `subagent_transcript.record_attempt_from_transcript`
path. Opus found concrete live duplicates in flex's own `effort.db` (e.g. rows 473 vs 475 for the
same story/role/attempt-number triple: 33,380 tokens/PASS vs. 117,347 tokens/FAIL) — 12 such
duplicate `(story_id, agent_role, attempt_number)` triples exist today. `next_action.py`'s
loop-breaker `fail_cause` selection (`fail_rows[-1]["notes"]`) resolves which row "wins" by
insertion-order luck when duplicates exist. `CLAUDE.build.md` states recording is "fully hook-side
… no separate orchestrator-side recording step needed," but `skills/pairmode/skills/reviewer/procedure.md`
still instructs calling `record_attempt.py --notes` — two contradictory contracts writing to one
table.

**Evidence gathered during spec elaboration (grounds the decision below):**

- `CLAUDE.build.md` (live) and `skills/pairmode/templates/CLAUDE.build.md.j2` (the template it is
  synced from) both already carry the correct, hook-only prose (identical line 30 in both files:
  "effort-attempt recording AND the attempt counter are fully hook-side … no separate
  orchestrator-side recording step needed"). Neither file calls `record_attempt.py` or
  `flex_build.py record-attempt` anywhere. `tests/pairmode/test_templates.py`'s
  `test_flex_build_md_calls_record_attempt`-style check is explicitly `@pytest.mark.skip(reason=
  "HARNESS-002: thin dispatch loop removed record_attempt prose from live CLAUDE.build.md")` —
  independent confirmation the live build loop never calls `record_attempt.py`.
- `hooks/post_tool_use.py`'s Task/Agent branch calls `subagent_transcript.record_attempt_from_transcript()`
  directly — never `record_attempt.py`. That function calls `effort_recorder.record_effort()` →
  `effort_db.insert_or_update_attempt()`, never shelling out to or importing `record_attempt.py`.
- The actual contradiction is in `skills/pairmode/skills/reviewer/procedure.md`'s "Notes on FAIL"
  and "Return format" sections (~lines 526–533, ~605–610): both describe the hook writing
  `fail_cause` into the effort database by saying it "populate[s] `record_attempt.py`'s `--notes`"
  / "passes it as `--notes` to `record_attempt.py`" — factually wrong terminology (the hook path
  never touches `record_attempt.py`'s CLI at all; it passes `notes=` directly as a Python keyword
  argument to `effort_recorder.record_effort`), and it directly contradicts `CLAUDE.build.md`'s
  "fully hook-side" statement three files away. This stale prose is a real, live documentation
  contradiction (the F11 finding's "two contradictory contracts" claim), even though it does not
  literally instruct the reviewer agent to run the CLI (the same procedure's own "What you must not
  do" list already says "Do not request effort database records").
- `record_attempt.py` **does** have a legitimate, documented, non-hook caller today:
  `docs/architecture.md`'s effort.db row (§ persistence table, line 2663) already lists it as
  "`record_attempt.py` CLI for non-hook callers" alongside the hook path — this is an accepted,
  pre-existing two-path design, not an oversight. `docs/phases/phase-113.md`'s session note
  (line 49) documents a real manual invocation: a human operator ran `record-attempt` (the
  `flex_build.py` passthrough alias, RELEASE-009/INFRA-263) to manually reconcile a spawn the hook
  failed to record live (CER-114), alongside `write-attempt-count`. This is exactly the scenario
  that can produce a genuine duplicate: a human reconciles a spawn via the CLI without first
  checking whether the hook already (or later) wrote its own row for the same triple.
- Column-coverage comparison: `record_attempt.py`'s `record_attempt()` passes `story_class=` and
  `model_selection_reason=` straight through to `effort_db.insert_attempt()` (lines 294–314).
  `subagent_transcript.record_attempt_from_transcript()`'s only DB-write call
  (`effort_recorder.record_effort` / `record_effort_ex`, `effort_recorder.py` lines 125–264) has no
  `story_class` or `model_selection_reason` parameter anywhere in its signature, and neither name
  appears anywhere in `subagent_transcript.py` or `effort_recorder.py` (confirmed by grep — zero
  matches). **These two columns' only live writer is `record_attempt.py`'s CLI path.** Deleting
  that CLI's write path, as one of the two fix options this story was scoped to consider, would
  silently strand `story_class`/`model_selection_reason` with zero writers going forward — the
  outcome `docs/phases/phase-117.md`'s Ordering section flagged as a risk to check before INFRA-348
  (dead effort.db columns) is specced. **Resolution recorded here for INFRA-348: this story does
  NOT delete `record_attempt.py`'s write path — `story_class`/`model_selection_reason` retain a
  live writer after this story lands.** INFRA-348 must not assume these two columns are dead as a
  side effect of this story; if they are still unwritten-in-practice, that is a separate,
  pre-existing gap (nothing in the live build loop calls `record_attempt.py --story-class` today
  either — see the `CLAUDE.build.md` finding above) that INFRA-348 should assess independently.

**Decision:** `record_attempt.py` has no automated (per-spawn, build-loop) live caller — the only
remaining callers are (a) stale, incorrect prose in `skills/pairmode/skills/reviewer/procedure.md`
that this story fixes, and (b) a legitimate, occasional, human-invoked manual-reconciliation path
(`flex_build.py record-attempt`, per phase-113's documented CER-114 use and
`docs/architecture.md`'s existing "CLI for non-hook callers" design). Full deletion of the CLI's
write path is therefore wrong — it would break the only legitimate remaining caller and orphan
`story_class`/`model_selection_reason`. Instead this story does both halves of the two fix
directions it was scoped to choose between: (1) repoint the reviewer procedure to stop describing
`record_attempt.py` as part of the hook's recording path (closes the literal contradiction with
`CLAUDE.build.md`), and (2) add a de-duplication guard to `record_attempt.py`'s own write path
(since a legitimate manual caller still exists and can still collide with a hook-written row for
the same spawn — which is exactly how phase-113's manual reconciliation could produce a duplicate).
After this story: there is still exactly one *automated* writer (the hook), and the one remaining
*manual* writer refuses to silently create a second row for a triple the automated writer (or a
prior manual call) already recorded.

## Requires

<!-- Independent story per phase-117's Ordering section — no prior story in this phase must land first. -->

## Ensures

1. `skills/pairmode/skills/reviewer/procedure.md`'s "Notes on FAIL" section no longer states or
   implies that `fail_cause` is passed as `--notes` to `record_attempt.py`'s CLI. It states
   instead, accurately, that `hooks/post_tool_use.py`'s Task/Agent branch reads `fail_cause` from
   `tool_response` and passes it as the `notes=` keyword argument directly to
   `effort_recorder.record_effort` (via `subagent_transcript.record_attempt_from_transcript`) —
   `record_attempt.py`'s CLI is never invoked on this path. Verifiable: `grep -n "record_attempt.py"
   skills/pairmode/skills/reviewer/procedure.md` returns zero lines that describe it as being
   invoked by, or receiving data from, the hook/reviewer FAIL path. Forbidden proxy: leaving the
   sentence structurally the same but only swapping one word (e.g. "may populate" for "populate") —
   the fix must remove the `record_attempt.py`/`--notes` reference from this description entirely,
   not soften it.
2. `skills/pairmode/skills/reviewer/procedure.md`'s "Return format" section's `fail_cause` field
   description carries the same correction (no longer says "passes it as `--notes` to
   `record_attempt.py`").
3. `skills/pairmode/skills/reviewer/procedure.md` retains no sentence anywhere implying the
   reviewer, the hook, or any part of the automated build loop invokes `record_attempt.py`'s CLI.
   Verifiable: every remaining `record_attempt.py` mention in the file, after the edit, either (a)
   is absent, or (b) explicitly describes it as the separate, non-hook, non-reviewer manual/CLI
   path (not something the automated FAIL/PASS flow calls).
4. `record_attempt.py` gains a `--allow-duplicate` boolean flag (`is_flag=True`, default `False`).
   With the flag absent (default), a call whose `(story_id, agent_role, attempt_number)` triple
   already has an existing row in the effort database exits with a non-zero exit code, writes
   **no** new row, and prints an error to stderr naming the existing row's `id` and the colliding
   triple. Forbidden proxy: printing a warning to stderr while inserting the row anyway (a warning
   that doesn't change the outcome does not satisfy this Ensures — the row must genuinely not be
   written).
5. With `--allow-duplicate` passed, the same colliding call succeeds (exit 0) and inserts a new row
   as before this story (today's un-guarded behavior), for the legitimate reconciliation case where
   a human operator deliberately wants a second row for the same triple.
6. A call whose triple does **not** already exist in the database is unaffected by this story:
   still inserts a row on exit 0, with or without `--allow-duplicate` passed.
7. The duplicate check queries the *effort database itself* (via `effort_db.query_by_story`,
   filtered to `agent_role`/`attempt_number` matching the incoming call), not `state.json` or any
   other file — the check must catch a collision against a row the *hook* already wrote for this
   exact triple, not just against other CLI-written rows.
8. `docs/architecture.md`'s existing description of `record_attempt.py` as "CLI for non-hook
   callers" (the effort.db persistence-table row, and/or the CLI-surface listing naming
   `record-attempt`) gains one sentence naming the new `--allow-duplicate` guard and its default
   refuse-on-collision behavior, so the documented design matches the shipped behavior.
9. The 12 pre-existing live duplicate rows in flex's own `.companion/effort.db` are **not** touched,
   deleted, or merged by this story — this is explicitly out of scope (see `## Out of scope`); no
   `## Ensures` item above requires their reconciliation.
10. `tests/pairmode/test_record_attempt.py` gains tests covering Ensures 4, 5, 6, and 7 (see
    `## Tests` below); the existing full test file continues to pass unmodified otherwise (no
    existing test's expected behavior changes — this story only adds a new refusal path that
    existing tests, which never exercise a colliding triple, do not hit).
11. `tests/pairmode/test_effort_db.py::TestXxx::test_record_attempt_cli_writes_new_fields` (or
    whatever its current class/method name is — locate it, do not assume) still passes unmodified,
    confirming `record_attempt.py`'s `story_class`/`model_selection_reason` write path is
    unaffected by this story.

## Instructions

1. **Fix `skills/pairmode/skills/reviewer/procedure.md`.** Locate the "Notes on FAIL" section
   (currently ~lines 522–533) and the `fail_cause` field description in "Return format" (currently
   ~lines 605–610). In both places, replace the sentence claiming `fail_cause` is passed "as
   `--notes` to `record_attempt.py`" / "populate `record_attempt.py`'s `--notes`" with an accurate
   description: `hooks/post_tool_use.py`'s Task/Agent branch reads `fail_cause` from
   `tool_response` and passes it as the `notes=` keyword argument directly to
   `effort_recorder.record_effort` (via `subagent_transcript.record_attempt_from_transcript`) —
   `record_attempt.py`'s CLI is never invoked by this path. State plainly that this hook path is
   the sole writer for that row. Do not change any other content in the file (checklist items,
   commit/revert commands, other prose describing `context_budget.py`/`subagent_transcript.py`
   elsewhere in the file are unrelated to this fix and must be left alone).
2. **Add the duplicate guard to `record_attempt.py`.** Add a `--allow-duplicate` Click flag
   (`is_flag=True`, `default=False`, help text explaining it overrides the default
   collision-refusal for a deliberate manual reconciliation). Immediately before the existing
   `_effort_db.insert_attempt(...)` call, and only once `story_id`/`agent_role`/`attempt_number`
   are all resolved (i.e. after the `--story-file` auto-fill block and the `story_id is None`
   guard), query `_effort_db.query_by_story(resolved_db, story_id)` and filter to rows where
   `row["agent_role"] == agent_role and row["attempt_number"] == attempt_number`. If any match and
   `allow_duplicate` is `False`: `click.echo` an error to stderr naming the existing row's `id`
   (e.g. `f"error: attempt row already exists for {story_id}/{agent_role}/attempt {attempt_number}
   (row id {existing_id}) — pass --allow-duplicate to insert anyway"`), then `sys.exit(1)` without
   calling `insert_attempt`. If a match exists and `allow_duplicate` is `True`, or no match exists,
   proceed to `insert_attempt` exactly as today.
3. Place the duplicate check after the existing `effort_tracking` disabled early-return (the
   no-op-when-tracking-disabled behavior documented in the module docstring must be preserved
   unchanged — do not run the duplicate query when tracking is off).
4. **Update `docs/architecture.md`.** Locate the existing sentence(s) describing
   `record_attempt.py` as the CLI path "for non-hook callers" (effort.db persistence-table row,
   ~line 2663) and add one sentence noting the new `--allow-duplicate`-gated refusal-on-collision
   behavior (INFRA-345), so a reader of that table learns the CLI path is no longer a silent
   duplicate-writer risk by default.
5. **Extend `tests/pairmode/test_record_attempt.py`.** Add a test class (e.g.
   `TestDuplicateGuard`) with cases for: (a) a second call with the same
   `story_id`/`agent_role`/`attempt_number` triple as an already-inserted row exits non-zero and
   leaves the row count at 1 (Ensures 4); (b) the same collision with `--allow-duplicate` passed
   exits 0 and leaves the row count at 2 (Ensures 5); (c) a call with a different
   `attempt_number` (or `agent_role`) than an existing row for the same `story_id` is unaffected
   and inserts normally (Ensures 6); (d) a collision against a row inserted via
   `effort_db.insert_attempt` directly (simulating a hook-written row, not a prior CLI call) is
   still caught (Ensures 7) — use the module's own `effort_db.insert_attempt` helper in the test
   setup to write the "hook" row, not another `record_attempt` CLI invocation, so the test proves
   the check reads the DB itself rather than some CLI-only bookkeeping.
6. Do not modify `CLAUDE.build.md`, `skills/pairmode/templates/CLAUDE.build.md.j2`, or
   `hooks/post_tool_use.py` — all three are already correct per the Context evidence above; this
   story's fix is scoped to the reviewer-procedure prose and the CLI guard only.
7. Do not attempt to reconcile or delete any of the 12 existing live duplicate rows in flex's own
   `.companion/effort.db` — see `## Out of scope`.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_record_attempt.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_effort_db.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_procedure_skills.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -15
```

Acceptance: `test_record_attempt.py` green, including the new `TestDuplicateGuard` cases;
`test_effort_db.py` green (the `story_class`/`model_selection_reason` round-trip test unaffected);
`test_procedure_skills.py` (the existing test file that reads
`skills/pairmode/skills/reviewer/procedure.md` content — confirmed present via `grep -rl
"reviewer/procedure.md" tests/pairmode/`) green with the corrected prose; the full
`tests/pairmode/` suite is green with no new failures beyond the pre-existing baseline.

## Out of scope

- Deleting `record_attempt.py` or its CLI entirely — it remains the legitimate, documented path for
  non-hook (manual/reconciliation) callers; see `## Context` § Decision.
- Reconciling, merging, or deleting the 12 existing live duplicate `(story_id, agent_role,
  attempt_number)` rows already in flex's own `.companion/effort.db` — this is historical data, not
  a live bug this story's fix prevents going forward; a future story may choose to clean it up, but
  it is not required for this story's acceptance.
- Adding a database-level `UNIQUE` constraint on `(story_id, agent_role, attempt_number)` — the
  12 existing duplicate rows would make such a constraint fail to apply retroactively without a
  separate data-migration/cleanup step (explicitly out of scope above); this story's guard is an
  application-level check in `record_attempt.py` only, not a schema change.
- `INFRA-348`'s disposition of `story_class`/`model_selection_reason` (whether they should be
  wired into the live build loop, or removed) — this story only records, for INFRA-348's benefit,
  that their sole writer (`record_attempt.py`) survives this story unmodified in its write path.
- Any change to the hook-side dedup mechanism already built for INFRA-288/CER-104
  (`effort_db.insert_or_update_attempt`'s `dedupe_agent_id` idempotency key) — that mechanism
  guards against a *doubled hook registration* for the same spawn, a different failure mode from
  this story's manual-CLI-vs-hook collision; it is untouched.
