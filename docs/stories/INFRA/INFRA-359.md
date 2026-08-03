---
id: INFRA-359
rail: INFRA
title: Wire shadow-reviewer dispatch into CLAUDE.build.md and next_action.py
status: complete
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - skills/pairmode/scripts/model_selector.py
  - skills/pairmode/scripts/pairmode_sync.py
  - tests/pairmode/test_model_selector.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-358 built the shadow-reviewer's protocol and static artifacts. This story is the live
dispatch wiring — deliberately sequenced to build only after Phase 117 has fully landed and
checkpointed, since Phase 117 does heavy, multi-story churn in exactly the two files this story
touches (`CLAUDE.build.md`, `next_action.py` is touched only indirectly here via
`select_shadow_reviewer_model`'s consumer, `model_selector.py` directly) — building against a
moving target there risks the same two-copies-drift problem Phase 117's own INFRA-342 exists to
fix.

Design decision (made here, not left implicit): this does **not** add a new `next-action` resolver
action. `next-action` continues to emit `spawn-builder` exactly as today. Concurrent
shadow-reviewer dispatch is an **opt-in orchestrator-prose decision**, conditioned on a new
Build-standards key (`shadow_review=`concurrent``), the same pattern INFRA-315's `intent_review=`
and INFRA-317's `covered_contracts:` already established — this avoids adding another action to the
JSON grammar that could become an orphaned producer if a future story forgets to wire its consumer
(the exact failure class this era's cold-eyes review found three times).

## Requires

- Phase 117 must be fully checkpointed (tagged `cp-117` or equivalent) before this story merges.
- INFRA-358 must land first (the shadow-reviewer role/procedure must exist to be dispatched).

## Ensures

1. `CLAUDE.build.md`'s Build standards line gains an optional `shadow_review=`concurrent`` key,
   parsed the same way `intent_review=` is (absent/anything-other-than-`concurrent` = opted out,
   byte-identical to current behavior).
2. When opted in, the loop's `spawn-builder` branch also spawns the shadow-reviewer agent into the
   *same* worktree `cwd`, dispatched concurrently (not sequentially) with the builder — both
   Agent/Task spawns issued together, not one waited-on-then-the-other.
3. The orchestrator does **not** call `merge-story-worktree`/`discard-story-worktree` until *both*
   the builder and the shadow-reviewer (if dispatched) have completed — this prevents a worktree
   teardown racing a still-running shadow-reviewer session, which would tear its shared filesystem
   out from under it mid-read. If the shadow-reviewer hasn't self-terminated by its own bounded
   cycle cap (INFRA-358) by the time the builder returns, the orchestrator waits for it rather than
   proceeding.
4. `model_selector.py` gains `select_shadow_reviewer_model`, wired into the actual dispatch call
   site added in Ensures 2 — not left as an orphaned function with no live caller (the exact defect
   class INFRA-318 was rejected twice for in Phase 116; this story must not repeat it).
5. `skills/pairmode/templates/CLAUDE.build.md.j2` gains the identical wiring in the same change —
   not a follow-up drift the way `checkpoint-docs`/`spawn-gate-worker`/`spawn-spec-writer` drifted
   between the two files in Phase 116 (Phase 117's INFRA-342 exists specifically to have already
   fixed that class of drift before this story adds anything new to either file).
6. Full `tests/pairmode/` suite green.

**Forbidden proxy:** `shadow_review=`concurrent`` present in a project's Build standards line with
no actual concurrent-dispatch code path reading it — the exact livelock/dead-flag shape this era's
cold-eyes review found repeatedly (GATE-WORKER's verdict, `meta["gate_worker_model"]`). Ensures 2
is the load-bearing item; Ensures 1 alone (just parsing the flag) does not satisfy this story.

## Instructions

1. Confirm Phase 117 is checkpointed before starting — check `docs/phases/index.md`'s Phase 117
   row and the `cp-117` tag exist.
2. Update `CLAUDE.build.md` and its `.j2` template together, in the same commit, not sequentially —
   this is the whole point of sequencing this story after INFRA-342.
3. Write the worktree-teardown-ordering rule (Ensures 3) explicitly into the loop's own prose, not
   just into this story's spec — a future reader of `CLAUDE.build.md` needs to see the ordering
   requirement in the document they actually follow.
4. Add `select_shadow_reviewer_model` following the exact pattern of the other seven
   `select_*_model` functions in `model_selector.py` (INFRA-333's precedent).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_model_selector.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green. Live concurrent-dispatch behavior (does the orchestrator actually wait for
both spawns correctly) is verified by INFRA-360's integration-test extension, not by a unit test
here — the orchestrator's own dispatch behavior lives in prose (`CLAUDE.build.md`), which this
project's test suite does not execute directly.

## Out of scope

- End-to-end proof that a live concurrent builder+shadow-reviewer pair actually produces and
  consumes a suggestion correctly — INFRA-360.
