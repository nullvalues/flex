---
id: INFRA-339
rail: INFRA
title: Fix or remove INFRA-316 pause-context: OUTCOME_PASS is unreachable from infer_position; also fix session-scoping mismatch
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
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
