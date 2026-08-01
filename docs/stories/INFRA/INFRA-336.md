---
id: INFRA-336
rail: INFRA
title: Fix FAIL-escalation ladder: attempt-counter bump reliably fires after discard, plus a stage-to-stage integration test harness
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
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
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests
