---
id: INFRA-237
rail: INFRA
title: Wire attempt-count writes into the build loop (retry/loop-breaker/human-pause escalation)
status: complete
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/scripts/flex_build.py
touches:
  - CLAUDE.build.md
  - tests/pairmode/test_next_action.py
  - tests/pairmode/test_flex_build_attempt_count.py
---

## Context

0.2's `CLAUDE.build.md.j2` wrote the per-story attempt counter at every stage:
`write-attempt-count` after each spawn (`:547`), `clear-attempt-count` on PASS
(`:704`), and bumped it to 2/3 on FAIL (`:725,741`). 0.3's `flex_build.py` still
exposes `write-attempt-count`/`read-attempt-count`/`clear-attempt-count`
(`flex_build.py:806,851,865`), and the resolver still *depends* on the counter:
`next_action.py:681-711` derives `last_attempt_outcome` (a FAIL requires
`attempt_count > 0`), Row 6 spawns the loop-breaker at attempt 2, Row 7 pauses for a
human at attempt ≥3, and `attempt ≥ 2` drives `retry-upgrade` model selection in
`select_builder_model`. But the current 51-line `CLAUDE.build.md` never calls any of
the three commands, and `record-attempt` (the one recording step that *is* wired,
per INFRA-236) doesn't touch the counter either. `.companion/attempt_counter.json`
does not exist in this checkout.

Net effect: a failing story is perpetually re-dispatched as attempt 1, on the same
model, forever — the loop-breaker and its fable escalation tier (INFRA-226) are
unreachable, and the ≥3-attempt human-pause safety valve never fires.
`docs/architecture.md:943,1074-1077` still documents the counter as live.

## Requires

- INFRA-236's `record-attempt` step lands first (or lands in the same story cycle) —
  the natural place to also fire attempt-count writes is immediately alongside it,
  not as separate orchestrator prose, per the minimize-prose intent.

## Ensures

- After a builder or reviewer FAIL, `flex_build.py read-attempt-count --story-id <ID>`
  returns 1, then 2, then 3 on successive attempts at the same story.
- On reviewer PASS and successful `merge-story-worktree`, the counter is cleared for
  that story.
- A resolver call (`next-action`) after two recorded FAILs for the same story emits
  `spawn-loop-breaker`; after three, emits the human-pause action.
- The counter write is deterministic and CLI-side: folded into `record-attempt` (bump
  on FAIL outcome) and `merge-story-worktree`/`discard-story-worktree` (clear on
  merge, bump on discard) rather than new orchestrator template prose — consistent
  with how `record-checkpoint-step` and `mark_phase_complete` already move state
  ownership into CLI commands rather than LLM-authored steps.
- `docs/architecture.md:943,1074-1077` confirmed accurate against the implemented
  wiring (or corrected if the chosen wiring point differs from what's documented).

## Instructions

1. Decide the wiring point: either (a) `record-attempt` itself increments/clears the
   counter based on the `--outcome` it's given, or (b) `merge-story-worktree` and
   `discard-story-worktree` own the clear/bump. Prefer (a) if `record-attempt` already
   receives the outcome and story ID needed — avoids a second call site.
2. Implement the chosen wiring in `flex_build.py`.
3. Add the resulting call (if any) to `CLAUDE.build.md.j2`'s pseudocode, or confirm no
   template change is needed if fully absorbed into the CLI step already added by
   INFRA-236.
4. Add resolver-level integration coverage: simulate two consecutive FAILs and assert
   `next-action` routes to `spawn-loop-breaker`; simulate three and assert the pause
   action.
5. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Changing the loop-breaker/human-pause thresholds themselves (2 and 3) — this story
  only restores the write path the existing thresholds depend on.
- INFRA-236 (effort recording), INFRA-238 (current_story) — adjacent gaps, separate
  root causes, separate stories.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure; new/updated
tests cover the counter lifecycle across simulated PASS/FAIL sequences and the
resolver's Row-6/Row-7 routing.
