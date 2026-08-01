---
id: INFRA-339
rail: INFRA
title: Fix or remove INFRA-316 pause-context: OUTCOME_PASS is unreachable from infer_position; also fix session-scoping mismatch
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
touches:
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_next_action_schema.py
  - tests/pairmode/fixtures/next_action.schema.json
  - tests/pairmode/fixtures/next_action_samples.json
  - tests/pairmode/test_checkpoint_step.py
  - tests/pairmode/test_harness003_isolation.py
  - tests/pairmode/test_harness004_isolation.py
  - tests/pairmode/test_harness005_isolation.py
  - tests/pairmode/test_needs_spec.py
  - tests/pairmode/test_stage_integration.py
  - docs/architecture.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH findings F2 and F12 of `docs/build-loop-cold-eyes-review-20260801.md`. Both reviewers
independently found the identical bug in INFRA-316 (Phase 116, reviewer-PASSed and merged this
session): `infer_position` can only set `last_attempt_outcome = OUTCOME_PASS` when
`_has_story_commit(next_story_id, git_log)` is true, but `next_story_id` comes from
`find_next_story` (`next_story.py`), which *skips* any story for which that same function already
returned true — same function, same `_git_log_oneline(project_dir)` output, microseconds apart.
`OUTCOME_PASS` is therefore unreachable from a live `infer_position` call; Row 8 (the
`pause-context` between-story context-etiquette check) fires only in hand-constructed test
fixtures. Everything downstream of Row 8 — `PAUSE_CONTEXT`, `_check_context_pause`,
`_read_state_for_context_pause`, the `SCHEMA_VERSION` 4→5 bump — is dead in production. The normal
"next story after a merge" case is handled by Row 2, which produces the same `spawn-builder`/
`auto-baseline` action *without* the context check INFRA-316 was supposed to add.

Separately (F12): even setting reachability aside, the Row-8 context check hand-assembles
arguments from the flat top-level `state.json` mirror rather than the session-scoped values the
equivalent PreToolUse hook check uses (`context_budget.decide(..., session_id=...)`,
`state.json["context_sessions"][<id>]`). Fix both together — reachability first, then correctness —
so that when pause-context becomes reachable it also reads the right data. Fix direction for
reachability: the contradiction is inherent to reusing the same "has a commit" test for both
"should this story be dispatched next" and "did the just-finished story pass" — the resolver needs
a way to observe the *most recently merged* story's outcome that isn't simultaneously the predicate
that excludes it from being the *next* story to dispatch. Consider whether this needs a genuinely
different signal (e.g. reading the merge/discard event itself, or a short-lived "last completed
story" stamp analogous to `current_stories` but written at merge/discard time and consumed once) —
or whether, on reflection, removing the feature as designed and keeping only the blunt PreToolUse
hook block is the more honest outcome. Either way, extend INFRA-336's integration-test harness to
prove which one holds.

## Requires

1. **INFRA-336 merged** (`feat(story-INFRA-336): fix FAIL-escalation ladder
   stall after discard, plus CER-147/148 and a stage-integration test
   harness`, commit `6dd03878`). `tests/pairmode/test_stage_integration.py`
   exists with `_scaffold_project`/`_invoke`/`_next_action_json` helpers
   factored explicitly for this story and INFRA-341/INFRA-344 to reuse
   (module docstring, `:11-16`). Its `status: draft` frontmatter is stale —
   this is CER-136, fixed later in this same phase by INFRA-347 — and is not
   evidence the merge did not happen; the git log is authoritative.
2. **Design decision, resolved by this spec (not left open for the
   builder).** Investigated both options the stub's Context posed:
   - Read `infer_position` (`next_action.py:968-1172`) and `find_next_story`
     (`next_story.py:237-311`): `find_next_story` returns the first
     `story_id` in the phase table for which `_has_story_commit(story_id,
     git_log)` is `False` (`next_story.py:272-273`); `infer_position` then
     re-derives `git_log` via the same `_git_log_oneline(project_path)` and
     calls the same `_has_story_commit(next_story_id, git_log)`
     (`next_action.py:1166-1169`) microseconds later against the same repo
     state. The two calls cannot disagree — `OUTCOME_PASS` is provably
     unreachable from a live call, confirming F2.
   - Read `_check_context_pause`/`_read_state_for_context_pause`
     (`next_action.py:1399-1512`) against `hooks/pre_tool_use.py`'s
     `context_budget.decide(project_dir, flex_factor, session_id=...)` call
     (`pre_tool_use.py:145-149`) and `context_budget.decide`'s own
     session-scoping contract (`context_budget.py:769-874`, esp. `:792-801`
     and `:848-874`): the hook resolves through the calling session's own
     `context_sessions` record and fails safe (CONTEXT CHECK REQUIRED) when
     a live sibling session holds the flat mirror. `_check_context_pause`
     takes no `session_id`, never imports `session_state`, and reads
     `context_current_tokens` etc. straight off the flat top-level
     `state.json` mirror — under a concurrent second session it can read
     that session's window instead of the calling orchestrator's, the exact
     CER-097 under-blocking shape the hook was fixed for (INFRA-285),
     confirming F12.
   - **Recommendation: remove the pause-context feature as designed (option
     b), not build a new reachability signal (option a).** Reasoning, in
     order of weight: (i) the phase's own goal names this one of "two
     features shipped in Phase 116 that are structurally unreachable in the
     live loop" under the "dead handoffs" umbrella (`docs/phases/phase-117.md`
     § Goal) — the phase's own framing already leans toward closing dead
     code, not re-founding it; (ii) the PreToolUse hook gate
     (`hooks/pre_tool_use.py` + `context_budget.decide`) already enforces the
     orchestrator-track budget correctly and is session-scoped and
     field-proven (INFRA-193/INFRA-285 lineage) — removing Row 8's second,
     broken gate does not remove coverage, it removes a redundant path that
     never fired; (iii) a genuinely different reachability signal (a
     merge/discard-time "last completed story" stamp, consumed once) is a
     new state-machine invention with its own races and lifecycle rules —
     exactly the class of decision the era's own conviction "we prefer
     spec-first development over code-first development" says needs its own
     dedicated design pass, not a bolt-on inside a two-bug remediation story;
     (iv) reviving a structurally-broken mechanism just to keep it
     technically present is the forbidden shape the launcher instructions
     named directly: "dead code with a real bug should not be revived just
     to justify its own existence." This reasoning is recorded here, in the
     spec, rather than resolved silently in the diff (ideology.md's
     "Decision fidelity over convenience").
   - Per spec-writer procedure Step 5, this does not meet any of the
     human-review-signal criteria (frontmatter is filled, `## Ensures`
     below does not depend on an undocumented architecture decision — it
     retires one, `docs/architecture.md` is updated in the same story, no
     model-raise is proposed) — so `status: "done"` is returned rather than
     `"revised"`. If a human reviewing this spec disagrees with the removal
     direction, that is exactly what the reviewer/checkpoint gates before
     build are for.
3. `_has_story_commit`'s scope/fallback matching rules
   (`next_story.py:164-234`, CER-116) are unrelated to this story's fix and
   must not be touched — only the pause-context plumbing is in scope.

## Ensures

1. **`PAUSE_CONTEXT` is no longer a live action.** `next_action.ACTIONS` does
   not contain `PAUSE_CONTEXT`'s value (`"pause-context"`); `len(ACTIONS) ==
   13`. The `PAUSE_CONTEXT` name constant itself remains importable from
   `next_action` (mirrors the existing `CHECKPOINT` precedent at
   `next_action.py:337-340` — "removed from ACTIONS ... retained for
   backward import compatibility only") so any external import does not
   hard-crash; nothing produces the value at runtime.
   Forbidden proxy: leaving `PAUSE_CONTEXT` in `ACTIONS` but simply making
   `_check_context_pause` always return `(None, None)` — that hides the
   removal behind a dead branch instead of shrinking the grammar, and a
   future edit could silently re-enable a still-broken check.
2. **The Row-8 seam is unconditional again.** `resolve_next_action`'s
   `last_attempt_outcome == OUTCOME_PASS` branch (`next_action.py:1767-1802`)
   emits `spawn-builder` (scalar=next story ID, attempt=1) directly, with no
   call to `_check_context_pause` in between. `_check_context_pause` and
   `_read_state_for_context_pause` (`next_action.py:1399-1512`) are deleted
   from `next_action.py` entirely — not merely made unreachable.
3. **`SCHEMA_VERSION` bumps 5 → 6** (a grammar shrink is a grammar change,
   same as INFRA-316's 4 → 5 bump for the add). `tests/pairmode/
   fixtures/next_action.schema.json`'s `const` and every `next_action_
   samples.json` sample's `meta.schema_version` read `6`; the schema's
   `enum` no longer lists `"pause-context"`; the `pause-context` sample
   entry is deleted (not replaced — Ensures 1 means no producer exists to
   generate a sample for it). `tests/pairmode/test_next_action_schema.py`'s
   `len(ACTIONS) == 14` assertion becomes `== 13`, its `"pause-context"`
   membership/enum-closure references are removed, and its `PAUSE_CONTEXT`
   import is dropped (or kept only if still exercising Ensures 1's
   backward-compat-import check — builder's call, state which in the
   commit). `test_checkpoint_step.py`, `test_harness003_isolation.py`,
   `test_harness004_isolation.py`, `test_harness005_isolation.py`, and
   `test_needs_spec.py`'s hardcoded `SCHEMA_VERSION == 5` (or `meta[
   "schema_version"] == 5`) assertions become `== 6` — mirroring the exact
   widening table INFRA-316 recorded for its own 4 → 5 bump.
4. **No orphaned test class.** `tests/pairmode/test_next_action.py`'s
   `TestResolveNextActionRow8ContextPause` class (`:1566-1786`) is deleted
   in full — not skipped, not xfailed. No remaining test in the suite
   references `PAUSE_CONTEXT`, `pause-context`, `_check_context_pause`, or
   `_read_state_for_context_pause` except the new integration coverage
   (Ensures 6).
5. **Docs match code.** `docs/architecture.md`'s "INFRA-316 landed this
   constraint (Phase 116)" paragraph (`:1003-1030`) is rewritten to record,
   in the past tense, that Row 8's context-etiquette check shipped
   structurally unreachable (F2) and with a session-scoping bug (F12), and
   was removed by this story (INFRA-339) rather than repaired — the
   orchestrator-track budget gate that remains live is the PreToolUse hook
   (`hooks/pre_tool_use.py` + `context_budget.decide`) only. This is a
   correction of the historical record, not a deletion of it (ideology.md
   § Core convictions: "we prefer codifying policy over implicit
   convention"). `skills/pairmode/templates/CLAUDE.build.md.j2`'s
   `pause-context` handoff comment line (`:20`) is deleted.
6. **Stage-integration proof (per the stub's own instruction: "extend
   INFRA-336's integration-test harness to prove which one holds").** A new
   test in `tests/pairmode/test_stage_integration.py`, reusing
   `_scaffold_project`/`_invoke`/`_next_action_json`, drives the real CLI:
   `next-action` (spawn-builder) → `create-story-worktree` → a commit on the
   story branch whose subject satisfies `_has_story_commit` →
   `merge-story-worktree` → `next-action` again, with `.companion/
   state.json`'s flat `context_current_tokens`/`context_budget_threshold`
   set to a deliberately over-threshold pair (mirroring the deleted unit
   test's fixture values) before the second poll. Asserts the second
   `next-action` call's `action` is `spawn-builder` (never `pause-context`,
   which no longer exists in `ACTIONS` per Ensures 1) — proving Row 2/Row 8
   in the live loop was always the reachable path this whole time, exactly
   as F2 found, and that removing the second, broken gate changes nothing
   observable in the live sequence.
7. **Suite green** without `-x` (per project lesson on `-x` masking
   pre-existing failures); no reference to `pause-context`/`PAUSE_CONTEXT`
   remains anywhere under `skills/pairmode/scripts/`, `tests/pairmode/`, or
   `docs/architecture.md` except the historical-record paragraph named in
   Ensures 5 and the `PAUSE_CONTEXT` backward-compat constant named in
   Ensures 1.

## Instructions

1. In `skills/pairmode/scripts/next_action.py`: remove `PAUSE_CONTEXT` from
   the `ACTIONS` frozenset (`:355-372`) but keep the `PAUSE_CONTEXT: str =
   "pause-context"` constant declaration itself (mirrors the `CHECKPOINT`
   precedent already in this file, `:337-340`) — update its comment to say
   it was removed from the live grammar by INFRA-339 and why, replacing the
   INFRA-316 landing comment above it (`:347-353`).
2. Delete `_check_context_pause` and `_read_state_for_context_pause` in
   full (`:1399-1512`), and the `context_budget` import block's
   INFRA-316-specific comment (`:299-308`) — the module no longer needs
   `context_budget` unless something else in the file still uses it; check
   before removing the import itself.
3. In the Row 8 branch (`:1767-1802`), delete the `_check_context_pause`
   call and the `if _pause_reason is not None:` branch; collapse straight to
   the `spawn-builder` emission that already existed, updating the
   docstring comment above Row 8 (`:1563-1567`) to drop the `pause-context`
   line.
4. Bump `SCHEMA_VERSION` 5 → 6 (`:314`). Update the module docstring's
   INFRA-316 entry (`:171-211`) to a short retrospective note ("removed by
   INFRA-339 — see Requires 2 for why") rather than deleting the historical
   entry outright — this module's docstring is itself a changelog of prior
   stories' grammar edits (see the INFRA-315/318/333 entries preceding it)
   and that pattern is preserved.
5. Update `tests/pairmode/fixtures/next_action.schema.json`: `enum` drops
   `"pause-context"`; `const`/description bump to `6`.
6. Update `tests/pairmode/fixtures/next_action_samples.json`: delete the
   `pause-context` sample entry; bump every remaining sample's
   `meta.schema_version` from `5` to `6`.
7. Update `tests/pairmode/test_next_action_schema.py`: `len(ACTIONS) == 14`
   → `== 13`; remove `"pause-context"` from the expected-enum list
   (`:189`) and from `expected`/`schema_enum` comparisons; drop the
   `PAUSE_CONTEXT` import if nothing in the file still references it after
   the class deletion in step 8.
8. Delete `TestResolveNextActionRow8ContextPause` in full from
   `tests/pairmode/test_next_action.py` (`:1566-1786`), and its
   `PAUSE_CONTEXT` import (`:987`) if nothing else in the file uses it.
9. Bump the hardcoded `SCHEMA_VERSION`/`schema_version` == 5 assertions to
   == 6 in `test_checkpoint_step.py`, `test_harness003_isolation.py`,
   `test_harness004_isolation.py`, `test_harness005_isolation.py`, and
   `test_needs_spec.py` — grep each file for `== 5` in a schema_version
   context before editing; do not touch unrelated `== 5` literals.
10. Rewrite `docs/architecture.md:1003-1030` per Ensures 5. Delete
    `skills/pairmode/templates/CLAUDE.build.md.j2:20`'s `pause-context`
    handoff comment.
11. Add the Ensures 6 test to `tests/pairmode/test_stage_integration.py`,
    following the file's existing helper conventions
    (`_scaffold_project`/`_invoke`/`_next_action_json`); do not re-derive
    scaffold logic already factored there (the module docstring names this
    story explicitly as an intended consumer).

**Do not:** invent a new reachability signal (merge/discard stamp) for
`last_attempt_outcome`/Row 8 — that is the explicitly rejected option
(Requires 2); touch `_has_story_commit`'s matching rules (Requires 3); widen
this story into INFRA-340's Row 9 territory (phase Ordering note: INFRA-339
and INFRA-340 both touch `next_action.py`'s Row 8/Row 9 region — build this
one first per the documented ordering, merge, then INFRA-340); change
anything about the PreToolUse hook gate itself (`hooks/pre_tool_use.py`,
`context_budget.py`) — it is already correct and is explicitly out of scope.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py tests/pairmode/test_next_action_schema.py tests/pairmode/test_stage_integration.py -q 2>&1 | tail -30
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

Acceptance: green, no `-x` (project lesson: a known pre-existing failure
must not be masked). Reviewer negative checks: (a) `grep -rn "pause-context\|PAUSE_CONTEXT" skills/pairmode/scripts/ tests/pairmode/ docs/architecture.md`
returns only the Ensures-1 backward-compat constant, the Ensures-5
historical-record paragraph, and this story's own test/doc edits — no live
producer or consumer; (b) the new `test_stage_integration.py` test fails
(red) if run against the pre-story code with `PAUSE_CONTEXT` still wired,
confirming it actually exercises the removed seam rather than passing
vacuously.

## Out of scope

- Building a genuinely different reachability signal for
  `last_attempt_outcome`/Row 8 (the merge/discard-time stamp option) — this
  story resolves the design question toward removal (Requires 2); a future
  story may reopen between-story context etiquette from scratch if the
  operator wants it, but that is a fresh design, not a repair of this one.
- Any change to the PreToolUse/UserPromptSubmit hook gates or
  `context_budget.py`/`context_budget_check.py` — both are already correct
  and unrelated to this story's two findings.
- INFRA-340's Row 9 (checkpoint-security/checkpoint-intent model dispatch)
  and INFRA-341's gate-worker verdict wiring — adjacent `next_action.py`
  regions per the phase Ordering note, deliberately sequenced as separate
  stories.
- CER-136 (merge-status-flip not updating a story's frontmatter `status` to
  `complete`) — that is INFRA-347, not this story; Requires 1 notes the
  symptom only to explain why INFRA-336's git-log evidence is trusted over
  its stale frontmatter.
