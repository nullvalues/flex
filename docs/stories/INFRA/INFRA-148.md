---
id: INFRA-148
rail: INFRA
title: "`context_budget.py` — replace transcript parsing with state.json contract"
status: complete
phase: "58"
story_class: code
primary_files:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_context_budget.py
  - tests/pairmode/test_pre_tool_use_hook.py
  - tests/pairmode/fixtures/context_budget_prompt.txt
touches:
  - hooks/pre_tool_use.py
---

# INFRA-148 — `context_budget.py`: replace transcript parsing with state.json contract

## Context

The Phase 47 hook-based context budget gate chose transcript JSONL parsing (D3) as its token
source. `compute_context_tokens(transcript_path)` silently returns `None` whenever `transcript_path`
is absent or incorrect in PreToolUse hook payloads — which is the case on every production session.
Evidence: `context_budget_acknowledged_at` is absent from every project's `state.json` across the
entire fleet. The secondary gate has never blocked a single Task spawn since it was built.

The fix replaces the broken transcript approach with a state.json contract. The orchestrator calls
`/context` (already required by the Context gate in CLAUDE.build.md), then writes the result to
`state.json["context_current_tokens"]` via a new `flex_build.py set-context-tokens` command. The
hook reads from there. No transcript dependency anywhere.

`hooks/pre_tool_use.py` is a protected file. Stated reason for modification: remove the
`transcript_path` argument from the `context_budget.decide()` call — a single-line change.

## Acceptance criteria

### `skills/pairmode/scripts/context_budget.py`

1. **Delete** `compute_context_tokens(transcript_path)` in its entirety.

2. **Add** `read_context_tokens_from_state(state: dict) -> int | None`:
   - Returns `int(state["context_current_tokens"])` when the key is present and the value is a
     valid positive integer.
   - Returns `None` for any other case (absent, zero, negative, non-numeric).

3. **`decide(project_dir: Path) -> dict | None`** — remove the `transcript_path` parameter.
   - When `read_context_tokens_from_state` returns `None`: return a block dict with:
     ```python
     {
       "block": True,
       "reason": _CONTEXT_CHECK_REQUIRED_MSG,
       "tokens": 0,
       "acknowledged_at": 0,
     }
     ```
     where `_CONTEXT_CHECK_REQUIRED_MSG` is a module-level constant:
     ```
     CONTEXT CHECK REQUIRED
     No token count recorded for this session. Before spawning, call /context and run:
       PATH=$HOME/.local/bin:$PATH uv run python <flex_build_path> \
         set-context-tokens --tokens N --project-dir .
     Replace N with the integer token count from /context.
     ```
     `<flex_build_path>` is computed from `__file__`: `Path(__file__).resolve().parent / "flex_build.py"`.
   - When `read_context_tokens_from_state` returns a valid int: proceed with the existing
     `should_block` / `render_alert_prompt` logic unchanged.

4. **`render_alert_prompt`** gains an `expected_next: int` parameter. Update to substitute two new
   placeholders from the fixture file: `[E]` → `expected_next` and `[R]` → `ceiling - current_tokens`
   where `ceiling = int(threshold * (1 + overrun_pct))`.
   Signature becomes:
   ```python
   def render_alert_prompt(
       story_id: str | None,
       tokens: int,
       threshold: int,
       overrun_pct: float,
       expected_next: int,
   ) -> str:
   ```

5. Update the `decide()` call to `render_alert_prompt` to pass `expected_next`.

### `tests/pairmode/fixtures/context_budget_prompt.txt`

Replace the file contents with:

```
CONTEXT BUDGET — [story RAIL-NNN] just completed.
Context is at approximately [N] tokens (threshold: [T], overrun: [O]).
Estimated next step: ~[E] tokens — [R] tokens remaining before ceiling.

Continuing risks context compaction mid-story. Options:

1. **Proceed** — continue building in this session; budget acknowledged.
   Say: "Continue building"

2. **Clear and resume** — run /clear, then in the fresh session:
   Say: "Continue building Phase X from story RAIL-NNN"
```

### `skills/pairmode/scripts/flex_build.py`

6. Add a `set-context-tokens` subcommand:
   - `--tokens N` (required, `type=int`)
   - `--project-dir DIR` (standard depth-guarded project-dir argument, same pattern as siblings)
   - Validates `N > 0`; exits with a non-zero code and a message if not.
   - Reads `.companion/state.json` (creates it if absent with `{}`), sets
     `state["context_current_tokens"] = N`, writes back with `indent=2`.
   - Prints: `context: recorded {N:,} tokens`
   - No other side effects. Does not touch `context_budget_acknowledged_at`.

### `hooks/pre_tool_use.py` (protected — single-line change)

7. Change the `context_budget.decide()` call from:
   ```python
   result = context_budget.decide(
       project_dir=Path(data.get("cwd") or "."),
       transcript_path=data.get("transcript_path") or "",
   )
   ```
   to:
   ```python
   result = context_budget.decide(
       project_dir=Path(data.get("cwd") or "."),
   )
   ```
   No other changes to `pre_tool_use.py`.

### Tests

8. **`tests/pairmode/test_context_budget.py`** — replace all transcript-file-writing fixtures with
   `state.json["context_current_tokens"]` writes. Required test cases:
   - `context_current_tokens` present and below ceiling → `decide()` returns `None` (pass through)
   - `context_current_tokens` present and above ceiling → `decide()` returns block with budget prompt
   - `context_current_tokens` absent → `decide()` returns block with `"CONTEXT CHECK REQUIRED"` in reason
   - `context_current_tokens` present, `acknowledged_at` set, tokens within reprompt margin → `None`
   - `render_alert_prompt` with `expected_next` → output contains substituted `[E]` and `[R]` values
   - `read_context_tokens_from_state`: present valid int → returns it; absent → `None`; zero → `None`
   - `set-context-tokens` CLI: writes `context_current_tokens` to state.json; rejects `--tokens 0`; rejects negative

9. **`tests/pairmode/test_pre_tool_use_hook.py`** — update tests:
   - Remove all transcript file writes; replace with `state.json["context_current_tokens"]` seeding.
   - "Block emitted" test: state has `context_current_tokens` above ceiling → hook emits `decision: block`.
   - Add: Task hook with no `context_current_tokens` in state.json → hook emits `decision: block`
     with reason containing `"CONTEXT CHECK REQUIRED"`.
   - "No block" test: state has `context_current_tokens` below ceiling → hook exits 0, empty stdout.

## Out of scope

- Changing `context_budget_acknowledged_at` write logic in `hooks/pre_tool_use.py` (behavior unchanged)
- Changing `should_block`, `estimate_next_step_tokens`, or any other `context_budget.py` function
- Updating `CLAUDE.build.md` or the template to call `set-context-tokens` (INFRA-149)
- Syncing the fix to downstream projects (handled as part of INFRA-149 acceptance)
