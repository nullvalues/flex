---
id: INFRA-360
rail: INFRA
title: Extend INFRA-336's integration-test harness to cover concurrent shadow-reviewer dispatch
status: complete
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_next_action.py
touches:
  - tests/pairmode/test_flex_build.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 117's INFRA-336 built this project's first real stage-to-stage integration-test harness
(`next-action → create-story-worktree → (simulated outcome) → merge/discard → next-action`,
asserted against real git-backed fixtures rather than hand-constructed Position dicts — the gap
both cold-eyes reviewers identified as the reason three Phase-116 defects shipped reviewer-PASSed).
This story extends that harness with the one new stage shape Phase 118 introduces: two agents
(builder + shadow-reviewer) operating in the *same* worktree concurrently, rather than the
sequential builder-then-reviewer shape every existing test simulates.

Since a real Agent/Task spawn can't be driven inside a `pytest` test, "integration test" here means:
simulate both sides' *file-level protocol* against a real git worktree fixture (real writes, real
timestamps, real git log) — proving the mechanism (append-only suggestions file, high-water-mark
tracking, stop-condition detection, teardown-ordering) is correct, without literally spawning two
live agents.

## Requires

- INFRA-358 and INFRA-359 must both land first.

## Ensures

1. A fixture-driven test simulates a builder writing story files and committing, while a
   concurrently-simulated shadow-reviewer appends two or more timestamped entries to
   `.pairmode-suggestions.md` in the same worktree — asserts the file accumulates entries
   append-only (no entry overwritten or lost) regardless of interleaving order.
2. A test asserts the builder-side high-water-mark logic (INFRA-358 Ensures 4) correctly identifies
   "new since last checked" content across multiple check points, and does not re-surface an
   already-seen suggestion.
3. A test asserts the shadow-reviewer's stop condition (INFRA-358 Ensures 2) — simulate a
   `story-<ID>` commit appearing in the worktree's git log mid-simulation and assert the documented
   stop condition would trigger, and separately assert the bounded-max-cycles fallback triggers
   when no commit ever appears.
4. A test asserts `.pairmode-suggestions.md` is excluded from `git status`/the story's diff (the
   `.gitignore` entry from INFRA-358 actually takes effect against a real git worktree, not just
   asserted by inspection of the `.gitignore` file's text).
5. A test asserts the orchestrator-level teardown-ordering rule (INFRA-359 Ensures 3): simulate a
   shadow-reviewer task still "in flight" (no terminal marker written) at the moment the builder
   completes, and assert that `merge-story-worktree`/`discard-story-worktree` is not the correct
   next action per the documented ordering rule (this may be a documentation/contract-level
   assertion rather than a runtime-enforced one, since the orchestrator's own wait-for-both
   behavior lives in `CLAUDE.build.md` prose, not code — state clearly which kind of assertion this
   is when you build it, don't imply a stronger guarantee than exists).
6. Full `tests/pairmode/` suite green.

## Instructions

1. Read INFRA-336's own integration-test harness in full before extending it — reuse its git-backed
   fixture helpers rather than building a second, parallel fixture mechanism.
2. Where a real concurrent agent spawn can't be simulated in a test process, say so explicitly in
   the test's own docstring (e.g. "simulates the file-level protocol both sides implement;
   does not spawn real Task/Agent processes") — don't let a test's name imply more than it proves.
3. Build the five test cases directly against INFRA-358/359's actual shipped mechanism, not against
   this story's own re-description of it — if the landed shape differs from what INFRA-358/359's
   specs described, test the real thing.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green.

## Out of scope

- A genuine end-to-end run with two real spawned agents — that's a dogfooded live run (INFRA-362),
  not something a `pytest` suite can drive.
