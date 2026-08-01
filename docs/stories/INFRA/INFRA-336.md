---
id: INFRA-336
rail: INFRA
title: Fix FAIL-escalation ladder: attempt-counter bump reliably fires after discard, plus a stage-to-stage integration test harness
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/subagent_transcript.py
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/story_context.py
touches:
  - tests/pairmode/test_subagent_transcript.py
  - tests/pairmode/test_flex_build_attempt_counter.py
  - tests/pairmode/test_stage_integration.py
  - tests/pairmode/test_story_context.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CRITICAL finding F1 of `docs/build-loop-cold-eyes-review-20260801.md`: two independent cold-eyes
reviews (fable and opus) each traced the same bug — the FAIL escalation ladder (attempt 1 → attempt
2 retry-upgrade → loop-breaker at attempt >=2 FAIL → operator pause) does not reliably advance.
Root cause: `discard-story-worktree` (`flex_build.py:4783`) clears the `current_stories` stamp
before the next `next-action` poll, per `CLAUDE.build.md`'s prescribed order — but the SubagentStop
sweep's `_story_accepts_late_bump` guard (`subagent_transcript.py`) requires that same stamp (or an
already-recorded counter entry) to authorize a FAIL bump. The PostToolUse bump path is itself
acknowledged in the codebase's own comment as structurally unreachable for the live async spawn
shape, and `reconcile_one` (the primary SubagentStop path since INFRA-298) deliberately never
bumps. That leaves the sweep as the only live writer, gated shut in exactly the
just-discarded-a-story case.

**This is not theoretical — opus found live evidence in this repo's own
`.companion/effort_recording.log`**: 8 `bump:late-fail` vs 8 `skip:late-bump-blocked` lines, a
roughly 50% ladder-advance failure rate, most recently on INFRA-330 (2026-07-31T05:52). A story
whose builder/reviewer cycle FAILs on its first attempt can loop at attempt 1 forever.

Both reviewers independently converged on the same highest-leverage fix for verifying this class of
bug going forward: **a real integration test driving `next-action → create-story-worktree →
(simulated FAIL) → discard-story-worktree → next-action` and asserting the second poll returns
attempt 2.** No such test exists today (`test_flex_build.py` has solid multi-CLI worktree chains
that never call `next-action`; `test_next_action.py` never invokes a worktree CLI). This story
should build that reusable integration-test harness alongside the fix, since later stories in this
phase (INFRA-339, INFRA-341, INFRA-344) also need to prove their fixes hold across a real stage
transition rather than an isolated unit test.

**Folded in (era 004's own goal is zero unresolved operational findings, not "later" — these are
the same file/subsystem this story is already fixing, so fixing them separately would mean a
second pass over the same code):**

- **CER-147 (MEDIUM):** `attempt_counter.json`'s writers (`write_attempt_count`,
  `bump_attempt_count`, `clear`) do a lock-free read-modify-write of the whole counter map, unlike
  every `state.json` writer migrated under INFRA-285/CER-097's `state_lock`. Under the declared
  parallel-build model (Phase 109's target capability), two near-simultaneous FAIL bumps for
  different in-flight stories, or a merge-clear racing a sibling story's bump, can silently lose an
  update. Route through the existing `state_lock` (or an equivalent file lock scoped to
  `attempt_counter.json`), same pattern already used for `state.json`.
- **CER-148 (MEDIUM):** a double-FAIL-in-one-cycle (builder self-reports FAIL, then the reviewer
  also FAILs the same worktree) can double-bump the counter for what is semantically one failed
  cycle, collapsing the 3-strike ladder to ~1.5 real cycles. The bump paths key only on `story_id` +
  `outcome=="FAIL"`, blind to which role produced the FAIL — this needs a role-aware or
  cycle-aware bump rule so one semantic attempt only ever counts once.

The integration-test harness this story builds should assert both of these directly: a simulated
concurrent bump doesn't lose an update, and a builder-FAIL-then-reviewer-FAIL sequence bumps the
counter exactly once, not twice.

## Requires

1. Read `_story_accepts_late_bump` (`skills/pairmode/scripts/subagent_transcript.py:1613-1687`)
   in full, including its docstring's rule 2 and the "synchronous PostToolUse-time
   bump ... is deliberately not gated" paragraph — the fix changes rule 2, not the
   synchronous path.
2. Read `discard-story-worktree` (`skills/pairmode/scripts/flex_build.py:4729-4786`)
   in full, including the CER-098(a) comment on why the residue-exit path
   deliberately does *not* clear the stamps, and the INFRA-238 comment on what
   the success path clears (`_clear_active_story`, `clear_permissions_artifact`).
   Confirm from `CLAUDE.build.md`'s build-loop pseudocode (line 25) that
   `discard-story-worktree` is invoked on exactly one condition — reviewer FAIL
   — never on a merge or an unrelated abandon; the fix may rely on that
   invocation contract without re-deriving it.
3. Read `bump_attempt_count` / `write_attempt_count` / `clear_attempt_count`
   (`skills/pairmode/scripts/flex_build.py:2137-2270`) in full — these are the
   three CER-147 writers.
4. Read `state_utils.py`'s `state_lock` and `update_state_json` in full,
   including the "why it is deliberately weak" docstring section — the
   CER-147 fix must reuse this existing bounded/advisory/fail-open lock
   primitive (or a scoped instance of it keyed to
   `.companion/attempt_counter.json.lock`), not invent a second locking
   scheme or a blocking lock.
5. Read the `bump:late-fail` / `skip:late-bump-blocked` sweep loop in
   `reconcile_attempts_from_effort_db` (`skills/pairmode/scripts/subagent_transcript.py`,
   the block around line 2201-2236) — this is where CER-148's builder-FAIL/
   reviewer-FAIL double-count would need a role- or cycle-aware guard.
6. Baseline suite count (`uv run pytest tests/pairmode/ -q`, no `-x`) —
   record pass/fail totals before making any change, per the project's
   pytest-no-x-before-merge lesson.

## Ensures

1. **The escalation ladder advances after a discard.** A story whose first
   builder/reviewer cycle FAILs, and whose worktree is then discarded via
   `discard-story-worktree` (clearing its `current_stories` stamp) before the
   FAIL is reconciled from `effort.db`, still has its attempt counter bumped
   to 1 by the reconciliation sweep — i.e. `_story_accepts_late_bump` (or its
   replacement gating logic) returns `True` for this exact sequence. Forbidden
   proxy: a fix that only changes behavior for a story that already has a
   prior counter entry (attempt 2+) — the failing case in the evidence
   (INFRA-330, 2026-07-31T05:52) and in the story's own root-cause narrative
   is a story's **first** FAIL, with no pre-existing counter entry.
2. **The fix does not reopen the gate the guard exists to close.** A FAIL
   reconciled for a `story_id` that is not currently in `current_stories`,
   has no counter entry, and was **not** the subject of a recent
   `discard-story-worktree` call (e.g. a stale or replayed `effort.db` row
   for a story nobody is building and nobody just discarded) is still
   skipped — `_story_accepts_late_bump` (or its replacement) must not
   degrade to an unconditional `True`. Forbidden proxy: removing rule 2
   entirely rather than widening it to also recognize a just-discarded
   story.
3. **Any new discard-side marker is bounded, not permanent.** If the fix
   adds a persisted "pending fail bump" record written by
   `discard-story-worktree`, that record is consumed/cleared once the late
   bump for that `story_id` has fired (or the story is re-stamped by a later
   `create-story-worktree`) — it must not accumulate unboundedly across
   many discards, and must not cause a *second*, unrelated FAIL for the same
   `story_id` to be treated as still-eligible after the story has already
   moved on.
4. **CER-147 — `attempt_counter.json` writers are lock-protected.**
   `write_attempt_count`, `bump_attempt_count`, and `clear_attempt_count`
   each wrap their read-modify-write critical section in `state_utils`'s
   `state_lock` (or an equivalent scoped file lock following the same
   bounded/advisory/fail-open contract), keyed to a lock file scoped to
   `.companion/attempt_counter.json` (not shared with `state.json`'s own
   lock file, since they are independent read-modify-write windows).
   Forbidden proxy: wrapping only one of the three writers, or wrapping the
   read half but not the write half of the critical section.
5. **CER-147 — concurrent bumps do not lose an update.** A test exercising
   two near-simultaneous `bump_attempt_count` calls for the *same*
   `story_id` (real threads or subprocesses, not a mock of the lock) asserts
   the final persisted count reflects both increments (i.e. equals the
   starting count + 2, not +1). A second test exercising simultaneous
   `bump_attempt_count`/`write_attempt_count`/`clear_attempt_count` calls for
   two *different* `story_id`s asserts both stories' final entries are
   correct and neither clobbers the other.
6. **CER-148 — one semantic FAIL cycle bumps the counter exactly once.** A
   simulated cycle in which the builder self-reports `FAIL` and the reviewer
   also reports `FAIL` for the same `story_id` within the same attempt
   (i.e. before any bump for that attempt has been counted) results in the
   attempt counter advancing by exactly 1 for that cycle, not 2. Forbidden
   proxy: de-duplicating by `tool_use_id` or `row.id` alone, since builder
   and reviewer FAILs are genuinely two different `effort.db` rows — the
   guard must be role- or cycle-aware (e.g. keyed on `story_id` +
   attempt-in-progress), not row-identity-aware.
7. **A reusable stage-to-stage integration-test harness exists** at
   `tests/pairmode/test_stage_integration.py`, driving the *real* CLI
   surface (`flex_build.py next-action`, `create-story-worktree`,
   `discard-story-worktree` — via `CliRunner.invoke` or subprocess, not
   monkeypatched internals) against a real temporary project directory with
   real `.companion/state.json` / `.companion/attempt_counter.json` files on
   disk. At minimum it contains one test driving exactly the sequence named
   in the Context: `next-action` (asserts `spawn-builder`, attempt 1) →
   `create-story-worktree` → a simulated FAIL outcome recorded through the
   real reconciliation path (`record_attempt_from_transcript` and/or
   `reconcile_attempts_from_effort_db`, not a direct `write_attempt_count`
   call, since a direct call would not exercise the bug this story fixes) →
   `discard-story-worktree` → `next-action` again, asserting the second
   poll's `attempt_count` (or `meta["attempt"]`) equals 2. This test module
   is written so that later stories in this phase (INFRA-339, INFRA-341,
   INFRA-344) can add sibling test functions in the same module rather than
   duplicating the harness helpers.
8. **The integration harness also directly proves Ensures 5 and 6** — i.e.
   it contains (or the story's `touches:` test files contain) a test
   asserting the concurrent-bump-no-lost-update behavior and a test
   asserting the builder-FAIL-then-reviewer-FAIL-bumps-once behavior, each
   described in the Context's closing paragraph.
9. **`docs/architecture.md` gains a pointer to the new harness** — wherever
   the existing test-layout/test-strategy section lives (locate before
   assuming a location), add one sentence naming
   `tests/pairmode/test_stage_integration.py` as the reusable stage-to-stage
   integration harness and what it exercises, so INFRA-339/341/344 (which
   the phase doc's Ordering section says extend it) do not have to
   rediscover it from scratch.
10. **Suite green.** Full run without `-x`; baseline (Requires 6) held, plus
    all tests added by this story.

## Instructions

1. Do the Requires reading (1-6) before writing any code — this bug's root
   cause is a gating-logic interaction across two files
   (`subagent_transcript.py`'s guard, `flex_build.py`'s discard command), and
   the fix must not be designed from either file in isolation.
2. **Escalation-ladder fix (Ensures 1-3).** Recommended shape, consistent
   with the root-cause narrative in Context: have `discard-story-worktree`
   record, at the point it clears the `current_stories` stamp (INFRA-238's
   existing `_clear_active_story` call), a small persisted marker naming the
   `story_id` it just discarded — e.g. a `state.json` key such as
   `recently_discarded_stories` (a dict of `story_id -> timestamp`, written
   through `state_lock`/`update_state_json` like every other `state.json`
   mutation) — and widen `_story_accepts_late_bump`'s rule 2 to also return
   `True` when `story_id` appears in that marker. Consume (remove) the
   marker entry for a `story_id` the moment `_story_accepts_late_bump`
   authorizes a bump for it, or the moment `create-story-worktree` re-stamps
   that `story_id` as current (whichever comes first) — this bounds the
   marker's lifetime and prevents it from re-authorizing a later, unrelated
   FAIL for the same `story_id` (Ensures 3). You are not required to use
   this exact key name or shape if you find a design that satisfies Ensures
   1-3 more directly (e.g. threading a `just_discarded=True` flag through the
   sweep call site instead) — but do not solve this by simply deleting rule
   2's liveness check, per Ensures 2's forbidden proxy.
3. **CER-147 lock fix (Ensures 4-5).** Wrap each of
   `write_attempt_count`/`bump_attempt_count`/`clear_attempt_count`'s
   read-modify-write body in `state_utils.state_lock(path)`, where `path` is
   `_attempt_counter_path(project_dir)` — mirror `story_context.py`'s two
   existing `with state_lock(companion_dir / "state.json")` call sites for
   the calling convention. `bump_attempt_count` currently composes
   `read_attempt_count` + `write_attempt_count` as two separate calls
   (a read-modify-write split across two functions is exactly the window
   `state_lock` exists to narrow) — the fix should take the lock once around
   the whole read-modify-write, not once per sub-call (taking it twice would
   either deadlock the same process or silently reduce to two independent
   critical sections, defeating the point). `update_state_json` is not
   directly reusable as-is (it returns `None` for a missing file, but a
   story's first bump must succeed against a not-yet-existing
   `attempt_counter.json`) — either extend it with a "create if missing"
   mode or write a small parallel helper in `flex_build.py` that takes
   `state_lock` directly around the existing `_read_attempt_counters`
   / `_atomic_write_json` pair. Do not touch `state.json`'s own lock file —
   `attempt_counter.json` gets its own `.lock` sibling.
4. **CER-148 role/cycle-aware bump fix (Ensures 6).** In the sweep loop
   (`reconcile_attempts_from_effort_db`, the `bump:late-fail` block),
   determine what already distinguishes "this is a new attempt cycle" from
   "this is the second FAIL row for a cycle already counted" — read
   `record_attempt_from_transcript`'s synchronous bump path and the
   `attempt_count`/`current_stories` bookkeeping around
   `create-story-worktree` to find the right anchor (e.g. only the *first*
   FAIL row observed since the most recent `create-story-worktree` stamp for
   that `story_id` counts; a second FAIL row for the same still-open attempt
   is logged but does not bump). Add a `log_recording_event` decision string
   for the skipped-as-duplicate case (following the existing
   `bump:late-fail` / `skip:late-bump-blocked` naming convention, e.g.
   `skip:duplicate-fail-in-cycle`) so the fix is traceable in
   `effort_recording.log` the same way the original bug was diagnosed.
5. **Integration harness (Ensures 7-8).** Build
   `tests/pairmode/test_stage_integration.py` using `CliRunner` against the
   real `flex_build` Click group (see `test_e2e_roundtrip.py` for the
   project's existing CLI-invocation-via-`CliRunner` pattern) inside a
   `tmp_path`-scaffolded project directory (bootstrap it, or hand-construct
   the minimal `.companion/` + `docs/stories/` layout an existing worktree
   test already uses — check `test_flex_build.py`'s multi-CLI worktree
   chains for the setup pattern named in Context, and adapt it to also call
   `next-action` rather than stopping short of it). Factor the
   scaffold-and-invoke helpers so a later story can import or copy them
   without re-deriving the setup.
6. Do not touch `select_builder_model`/`select_reviewer_model` or any of the
   other phase-117 stories' target files (`cer.py`, `next_action.py`'s
   pause-context/model-dispatch regions, `spawn-gate-worker` wiring,
   `CLAUDE.build.md`/`.j2`, the build-gate timeout, `record_attempt.py`) —
   those are separate stories in this phase (INFRA-337 through INFRA-345)
   and are out of scope here even where the symptom overlaps.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_subagent_transcript.py -q 2>&1 | tail -20
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_attempt_counter.py -q 2>&1 | tail -20
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_stage_integration.py -q 2>&1 | tail -20
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

Acceptance: green; baseline (Requires 6) held, no test count regression.
Reviewer negative check: run the new
`test_stage_integration.py::…discard_then_next_action…` test (or its
equivalent name) in isolation and confirm it fails against a git-stashed
pre-fix version of `subagent_transcript.py` (i.e. it actually exercises the
bug, not just a happy path) — `git stash` the fix, run the single test,
confirm red, `git stash pop`.

## Out of scope

- INFRA-337's brace-in-string JSON-verdict parser fix (`parse_worker_outcome`)
  — a related but separately-filed symptom in a different file.
- INFRA-345's de-duplication of the legacy `record_attempt.py` CLI writer —
  this story does not retire or touch that CLI path, only the
  `attempt_counter.json` library functions it may also call.
- Any redesign of `effort.db`'s schema or `reconcile_attempt`'s row-update
  contract — this story only changes what gates a bump, not how attempts are
  recorded.
- Extending the integration harness to cover INFRA-339/341/344's own
  scenarios — this story only builds the harness and populates it with the
  three tests named in Ensures 7-8; the later stories add their own.
