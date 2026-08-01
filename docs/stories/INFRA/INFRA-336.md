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
