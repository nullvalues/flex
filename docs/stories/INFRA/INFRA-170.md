---
id: INFRA-170
rail: INFRA
title: "`story_context.py --clear` — retain token count between stories"
status: complete
phase: "65"
story_class: code
primary_files:
  - skills/pairmode/scripts/story_context.py
touches:
  - tests/pairmode/test_story_context.py
---

# INFRA-170 — `story_context.py --clear`: retain token count between stories

## Context

Part A of the Phase 65 fix. Phase 59 INFRA-151 (CER-041) added `context_current_tokens`
and `context_current_tokens_recorded_at` pops to `clear_current_story()` as
belt-and-suspenders alongside the TTL check. The intent: force a fresh `/context`
check at each story's Context gate.

The actual effect: the accumulated value from `bump-context-tokens` (INFRA-169) is
wiped after every story, so it never accumulates. The fix: remove the pops.
The TTL remains as the only cross-session staleness backstop, which is sufficient —
values older than `context_current_tokens_ttl_minutes` (default 60 min) are already
treated as absent by `read_context_tokens_from_state`.

## Acceptance criteria

1. `clear_current_story()` no longer removes `context_current_tokens` or
   `context_current_tokens_recorded_at` from state.json.

2. `current_story` is still removed (the existing behavior for that key is unchanged).

3. A test confirms that a state with `context_current_tokens: 78000` retains that
   value after `--clear`.

4. Existing tests that asserted the keys were absent after `--clear` are updated to
   reflect the new behavior (they should assert the keys are PRESENT and unchanged).

5. `tests/pairmode/test_story_context.py` passes.

## Implementation guidance

In `skills/pairmode/scripts/story_context.py`, `clear_current_story()` (line 85):

Remove:
```python
state.pop("context_current_tokens", None)
state.pop("context_current_tokens_recorded_at", None)
```

Update the docstring to remove the CER-041 reference (or update it to describe the
new behavior: "context_current_tokens is retained so accumulated costs survive story
transitions within a session; TTL in `read_context_tokens_from_state` handles
cross-session staleness").

## Tests

Update `tests/pairmode/test_story_context.py`. The test(s) that verified
`context_current_tokens` and `context_current_tokens_recorded_at` are absent after
`--clear` should now verify they are RETAINED.

Add a new test: `test_clear_retains_token_accumulation` — state has
`context_current_tokens: 78000` and `context_current_tokens_recorded_at: <iso>`;
after `clear_current_story()`, both keys are still present with the same values.
