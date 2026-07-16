---
id: INFRA-193
rail: INFRA
title: "context_budget acknowledgment gate — require genuine user turn since block"
status: complete
phase: "85"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - hooks/pre_tool_use.py
touches:
  - CLAUDE.md
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_pre_tool_use_hook.py
---

## Requires

- INFRA-192 has landed: `hooks/user_prompt_submit.py` exists and increments
  `state["context_budget_user_turn_seq"]` (int, default 0 when absent) on
  every `UserPromptSubmit` event.
- Current (buggy) behavior, verified directly in this repo's
  `skills/pairmode/scripts/context_budget.py::decide()` and
  `hooks/pre_tool_use.py`:
  - `decide()` returns `"acknowledged_at": current_tokens` when blocking —
    the token count *at the moment of the block*, not a distinct
    acknowledgment marker.
  - `pre_tool_use.py` writes that value to
    `state["context_budget_acknowledged_at"]` unconditionally the instant it
    blocks, before any human has replied to anything.
  - A blocked Task/Agent call never completes, so `context_current_tokens`
    (written only by `post_tool_use.py` after a completed call) is unchanged
    on the very next attempt.
  - `should_block()`'s suppression check,
    `current_tokens >= acknowledged_at + reprompt_margin`, is therefore
    always false on an immediate retry (`current_tokens == acknowledged_at`),
    meaning suppression currently only re-arms after ~10k tokens of *any*
    kind accrue — not after a human actually saw and responded to the
    prompt. **Correction to prior read:** re-verify this exact branch while
    implementing — the fix below closes the gap regardless of which exact
    boundary condition is in play, by adding an independent human-turn
    requirement.
- D11 design boundary (documented in `context_budget.py`'s module docstring):
  `decide()` MUST NOT write to state.json — it is strictly read-only. The
  hook remains the sole state.json writer for context-budget state. This
  story's fix must preserve that boundary.

## Ensures

- `should_block()` gains a `user_turn_seq: int` parameter and an
  `acknowledged_user_turn_seq: int | None` parameter. Suppression
  (`return False` despite being over ceiling) now requires **both**:
  1. `current_tokens >= acknowledged_at + reprompt_margin` (existing token
     check, unchanged), **and**
  2. `acknowledged_user_turn_seq is None OR user_turn_seq > acknowledged_user_turn_seq`
     (new: a `UserPromptSubmit` event has occurred since the block was
     written).
- `decide()` reads `state.get("context_budget_user_turn_seq", 0)` and
  `state.get("context_budget_acknowledged_user_turn_seq")`, passes them to
  `should_block()`, and — when returning a block dict — includes
  `"user_turn_seq_at_block": <current context_budget_user_turn_seq value>`.
- `decide()` remains strictly read-only (D11 preserved): it does not write
  `context_budget_acknowledged_user_turn_seq` itself.
- `hooks/pre_tool_use.py`, when `result["block"]` is `True`, writes both
  `state["context_budget_acknowledged_at"] = result["acknowledged_at"]`
  (existing) and
  `state["context_budget_acknowledged_user_turn_seq"] = result["user_turn_seq_at_block"]`
  (new) in the same read-modify-write.
- Regression test: seed state with `context_current_tokens` over ceiling,
  `context_budget_acknowledged_at` equal to `context_current_tokens` (the
  exact self-clearing condition from the external report), and
  `context_budget_acknowledged_user_turn_seq` equal to the current
  `context_budget_user_turn_seq` (no new user turn). Assert `decide()` still
  returns a block dict (`block: True`) — i.e. a bare retry with no
  intervening `UserPromptSubmit` event no longer clears the gate.
- Regression test: same seed, but `context_budget_user_turn_seq` incremented
  by 1 relative to `context_budget_acknowledged_user_turn_seq` (simulating a
  real human reply having arrived) and `context_current_tokens >=
  acknowledged_at + reprompt_margin`. Assert `decide()` returns `None`
  (suppressed) — the gate correctly reopens after a genuine human turn.
- Regression test: same seed as the first case, but with
  `context_budget_acknowledged_user_turn_seq` absent from state entirely
  (pre-INFRA-192 state.json, upgrade path). Assert this is treated as
  `None` and does not itself block suppression when the token condition
  alone would have suppressed under the old contract — this preserves
  backward compatibility for state.json written before this story lands,
  rather than wedging existing sessions into a permanent block. Document
  this explicitly as a one-time upgrade grace period in a code comment.
- `CLAUDE.md`'s documented `hooks/pre_tool_use.py` thin-delegation paragraph
  (Review checklist item 1) is updated to describe the second state write
  (`context_budget_acknowledged_user_turn_seq`) alongside the existing
  `context_budget_acknowledged_at` write.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

**1. Update `should_block()` in `context_budget.py`.**

```python
def should_block(
    current_tokens: int,
    expected_next: int,
    threshold: int,
    overrun_pct: float,
    acknowledged_at: int | None,
    reprompt_margin: int = 0,
    user_turn_seq: int = 0,
    acknowledged_user_turn_seq: int | None = None,
) -> bool:
    """Pure decision. Block iff:

      current + expected > threshold * (1 + overrun_pct)
      AND (acknowledged_at is None OR NOT (
          current_tokens >= acknowledged_at + reprompt_margin
          AND (acknowledged_user_turn_seq is None
               OR user_turn_seq > acknowledged_user_turn_seq)
      ))

    The user-turn condition (INFRA-193) closes a self-clearing bug: without
    it, a bare identical retry with no human involvement satisfies the token
    condition trivially (current_tokens == acknowledged_at on a blocked call
    that never completed) and silently suppresses the gate. Requiring a
    UserPromptSubmit event strictly after the block (INFRA-192) ensures
    suppression only occurs once a human has actually had a turn since the
    prompt was shown.

    ``acknowledged_user_turn_seq=None`` is treated as "no user-turn
    requirement recorded" (pre-INFRA-192 state.json upgrade path) and does
    not itself force a block.
    """
    ceiling = threshold * (1.0 + overrun_pct)
    if (current_tokens + expected_next) <= ceiling:
        return False
    if acknowledged_at is None:
        return True
    token_ok = current_tokens >= acknowledged_at + reprompt_margin
    turn_ok = (
        acknowledged_user_turn_seq is None
        or user_turn_seq > acknowledged_user_turn_seq
    )
    return not (token_ok and turn_ok)
```

**2. Update `decide()` in `context_budget.py`.**

Read the two new state keys alongside the existing `acknowledged_at` read:

```python
user_turn_seq = int(state.get("context_budget_user_turn_seq", 0) or 0)
ack_turn_seq_raw = state.get("context_budget_acknowledged_user_turn_seq")
acknowledged_user_turn_seq = (
    int(ack_turn_seq_raw) if ack_turn_seq_raw is not None else None
)
```

Pass both into the `should_block(...)` call. When returning the block dict,
add `"user_turn_seq_at_block": user_turn_seq`:

```python
return {
    "block": True,
    "reason": prompt,
    "tokens": current_tokens,
    "acknowledged_at": current_tokens,
    "user_turn_seq_at_block": user_turn_seq,
}
```

Also update the `should_block(...)` call site to pass
`user_turn_seq=user_turn_seq, acknowledged_user_turn_seq=acknowledged_user_turn_seq`.

**3. Update `hooks/pre_tool_use.py`'s block-write branch.**

```python
if result and result.get("block"):
    try:
        state_path = project_dir / ".companion" / "state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text())
            state["context_budget_acknowledged_at"] = result["acknowledged_at"]
            if "user_turn_seq_at_block" in result:
                state["context_budget_acknowledged_user_turn_seq"] = result[
                    "user_turn_seq_at_block"
                ]
            state_path.write_text(json.dumps(state, indent=2))
    except Exception:
        pass
    print(json.dumps({"decision": "block", "reason": result["reason"]}))
```

**4. Update `CLAUDE.md`'s `hooks/pre_tool_use.py` thin-delegation paragraph
(Review checklist item 1).**

Extend the existing sentence describing the state write:

```markdown
   ... The Task branch has one state-write path:
   `context_budget_acknowledged_at` and (INFRA-193)
   `context_budget_acknowledged_user_turn_seq` when blocking (single
   `write_text()` call covering both keys).
```

## Tests

Add to `tests/pairmode/test_context_budget.py`:

- `test_should_block_bare_retry_without_user_turn_stays_blocked()` — the
  exact self-clearing repro: `current_tokens == acknowledged_at`,
  `user_turn_seq == acknowledged_user_turn_seq`, tokens over ceiling; assert
  `should_block(...)` returns `True`.
- `test_should_block_suppresses_after_genuine_user_turn()` — same seed but
  `user_turn_seq = acknowledged_user_turn_seq + 1` and
  `current_tokens >= acknowledged_at + reprompt_margin`; assert
  `should_block(...)` returns `False`.
- `test_should_block_acknowledged_user_turn_seq_none_is_backward_compatible()`
  — `acknowledged_user_turn_seq=None` with token condition satisfied; assert
  `should_block(...)` returns `False` (pre-INFRA-192 state.json is not
  wedged into a permanent block).
- `test_decide_block_dict_includes_user_turn_seq_at_block(tmp_path)` — seed
  state over ceiling with no prior acknowledgment; call `decide()`; assert
  the returned dict has a `user_turn_seq_at_block` key matching
  `state["context_budget_user_turn_seq"]`.
- `test_decide_is_read_only_does_not_write_user_turn_ack(tmp_path)` — call
  `decide()` on blocking state; assert
  `context_budget_acknowledged_user_turn_seq` is NOT present in state.json
  on disk afterward (D11 boundary — only the hook writes it).

Add to `tests/pairmode/test_pre_tool_use_hook.py`:

- `test_bare_retry_without_user_turn_blocks_again(tmp_path)` — seed state.json
  reproducing the external-report scenario (tokens over ceiling,
  `context_budget_acknowledged_at == context_current_tokens`,
  `context_budget_acknowledged_user_turn_seq == context_budget_user_turn_seq`);
  invoke the hook; assert stdout contains `"decision": "block"` (the retry
  is blocked again, not silently suppressed).
- `test_retry_after_user_prompt_submit_suppresses(tmp_path)` — same seed but
  with `context_budget_user_turn_seq` incremented past
  `context_budget_acknowledged_user_turn_seq` (simulating
  `hooks/user_prompt_submit.py` having fired) and token margin satisfied;
  invoke the hook; assert stdout is empty (suppressed).

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pre_tool_use_hook.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
