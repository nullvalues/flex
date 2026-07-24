---
id: RELEASE-021
rail: RELEASE
title: Fix the unacknowledgeable CONTEXT CHECK REQUIRED gate trap
status: complete
phase: "HARNESS016-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/context_budget.py
touches:
  - hooks/pre_tool_use.py
  - hooks/user_prompt_submit.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/fixtures/context_budget_prompt.txt
---

## Requires

- RELEASE-019 complete.
- INFRA-192 (CER-040) added a fail-closed `CONTEXT CHECK REQUIRED` verdict in
  `context_budget.decide()` for when `.companion/` exists but
  `context_current_tokens` is absent or stale — returned *before* the
  acknowledgment logic (`should_block`, INFRA-193/CER-... acknowledgment
  gate) runs.
- Because the acknowledgment path never gets a chance to clear this variant,
  the hook writes `acknowledged_at = 0` on block but the next build-cycle
  spawn re-triggers the identical `CONTEXT CHECK REQUIRED` block —
  acknowledgment is a no-op for this specific verdict, unlike the overflow
  verdict (which the overflow prompt fixture,
  `tests/pairmode/fixtures/context_budget_prompt.txt`, handles correctly).
- The block message (`context_budget.py`, ~lines 75-79) states the token
  count "will update automatically after the next tool call completes," but
  the only writers of `context_current_tokens` are the `PostToolUse`
  `Task`/`Agent` branch, `/clear`, and the manual `set-context-tokens`
  command — and the `PreToolUse` block prevents exactly the `Task`/`Agent`
  spawn that would trigger the `PostToolUse` write. The message's own
  promised resolution cannot occur through normal use.
- The real exits — spawn a non-build-cycle agent (not gated by this check),
  run `/clear`, or run `set-context-tokens` manually (documented only at
  `docs/architecture.md:253`) — are not named in the message the blocked
  user actually sees. Found via cold-eyes review 2026-07-17; this scenario
  is corroborated by `docs/phases/phase-HARNESS016-main.md`'s own Background
  note that this gate subsystem "blocked a recent builder spawn attempt in
  this worktree."

## Ensures

- A user hitting `CONTEXT CHECK REQUIRED` has a working, discoverable way
  through it without editing hook code or guessing undocumented commands.
  Either:
  (a) the block message is rewritten to name the actual working exits
  (`set-context-tokens`, `/clear`) explicitly, since the "updates
  automatically" claim is false for this verdict and must not remain in the
  message as-is; or
  (b) `should_block`'s acknowledgment logic is extended to also clear this
  verdict after a genuine human turn (matching the overflow verdict's
  UX) — pick whichever is the smaller, more correct change after reading
  both code paths; document the choice in the commit message.
- No change to the overflow verdict's existing (working) acknowledgment
  behavior.
- No change to the fail-closed *trigger* condition itself (missing/stale
  state still blocks) — this story fixes the escape path, not the
  fail-closed policy, which is a deliberate CER-040 safety property.

## Instructions

1. Read `context_budget.decide()` and `should_block()` in full to confirm
   the exact point where `CONTEXT CHECK REQUIRED` short-circuits past
   acknowledgment logic.
2. Decide between the message-fix and the acknowledgment-extension approach
   per Ensures; do not do both unless reading the code shows the message fix
   alone leaves a real dead-end (e.g. a user with no way to run
   `set-context-tokens` because they don't know the current count).
3. If extending acknowledgment: verify a genuine human turn (per
   `hooks/user_prompt_submit.py`'s sequence counter, INFRA-192) between
   blocks, exactly as the overflow path already requires — do not weaken
   that requirement for this verdict.
4. Update or add a fixture alongside `context_budget_prompt.txt` for the
   CHECK-REQUIRED case if the chosen fix changes the message.

## Tests

- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget.py -x -q`.
- New test: simulate the `.companion/` exists / `context_current_tokens`
  absent state, trigger `CONTEXT CHECK REQUIRED`, then exercise the chosen
  fix's escape path end to end (either the documented manual command or a
  second human-turn-gated spawn) and assert the block clears.
- Regression: overflow-verdict acknowledgment (existing behavior) still
  passes unchanged.
