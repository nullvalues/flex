---
id: RESOLVER-017
rail: RESOLVER
title: Reset checkpoint_step on checkpoint-tag completion (CER-066)
status: complete
phase: "HARNESS015-main"
story_class: code
auth_gated: false
schema_introduces: false
touches:  # If this story changes any documented architecture, add docs/architecture.md to this list.
---

## Requires

- `skills/pairmode/scripts/next_action.py` `_CHECKPOINT_SEQUENCE` = `(checkpoint-security, checkpoint-intent, checkpoint-docs, checkpoint-tag)` (current, unchanged).
- `skills/pairmode/scripts/flex_build.py` `_record_checkpoint_step()` (RESOLVER-012) currently appends `step_id` to `state.json["checkpoint_step"]` and never removes anything.

## Ensures

- `_record_checkpoint_step()` resets `state["checkpoint_step"]` to `[]` in the same write when the step being recorded is `checkpoint-tag` (the terminal entry of `_CHECKPOINT_SEQUENCE`), instead of leaving all four step names accumulated.
- A new regression test in `tests/pairmode/test_record_checkpoint_step.py` asserts: recording `checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`, `checkpoint-tag` in sequence leaves `state.json["checkpoint_step"] == []` after the `checkpoint-tag` call (not `[..., "checkpoint-tag"]`).
- A new regression test in `tests/pairmode/test_next_action.py` asserts: given `state.json["checkpoint_step"]` already contains all four step names (simulating the stale-carryover bug), `resolve_next_action()` at Row 9 (active phase, no next story) still returns `checkpoint-security` — not `done` — proving a prior phase's completed sequence can no longer short-circuit a new phase's checkpoint.
- All pre-existing tests in `test_record_checkpoint_step.py` and `test_next_action.py` still pass unmodified in behavior (idempotency for non-terminal steps is unchanged: re-recording `checkpoint-security` twice is still a no-op write).
- `.companion/state.json` in this repo has `checkpoint_step` reset to `[]` as a one-time cleanup (it currently holds the stale 4-item list left over from the HARNESS013-main/HARNESS014-main checkpoints, run before this fix existed), so `flex_build.py next-action` correctly proposes `checkpoint-security` — not `done` — when this phase (HARNESS015-main) reaches its own checkpoint.

## Instructions

In `skills/pairmode/scripts/flex_build.py`, inside `_record_checkpoint_step()`:
after appending `step_id` to `current` (and before the atomic write), check
`if step_id == _CHECKPOINT_SEQUENCE[-1]: current = []` — i.e. recording the
terminal step clears the list rather than leaving it populated. Write
`state["checkpoint_step"] = current` as today.

Do not change `_CHECKPOINT_SEQUENCE`, `resolve_next_action()`'s Row 9 read
logic, or the CLI signature — the fix is contained to the write side.

As a one-time data cleanup (not a new mechanism), reset the *current* repo's
`.companion/state.json["checkpoint_step"]` to `[]` by hand, since it already
holds the stale list from before this fix shipped and the code fix alone
won't retroactively clear data written before it existed.

## Tests

- Extend `tests/pairmode/test_record_checkpoint_step.py` with a test that
  records the full 4-step sequence in order and asserts
  `state.json["checkpoint_step"] == []` after the final (`checkpoint-tag`)
  call.
- Extend `tests/pairmode/test_next_action.py` with a test that pre-seeds
  `state.json["checkpoint_step"]` with all four step names and asserts
  `resolve_next_action()` (active phase, `next_story_id=None`, guards passing)
  returns `checkpoint-security`, not `done`.
