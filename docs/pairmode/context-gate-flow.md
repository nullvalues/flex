# Context gate flow

This document is the single reference for the pairmode context gate mechanism.
It shows how `post_tool_use.py`, `pre_tool_use.py`, `context_budget.py`, and the
SessionStart reset path interact to enforce the context budget without LLM cooperation.

The prose architecture lives across `CLAUDE.build.md`, `docs/architecture.md`,
and `CLAUDE.md`. This document is the visual companion to that prose; the code
in `skills/pairmode/scripts/context_budget.py` and
`skills/pairmode/scripts/session_reset.py` is the ground truth.

---

## Diagram 1 — PostToolUse writer (after each builder/reviewer spawn)

After every Task/Agent tool call completes, `post_tool_use.py` reads the live
token count from the JSONL transcript and writes it to state.json. No orchestrator
action required.

```
POST_TOOL_USE HOOK — fires after every Task / Agent completion
──────────────────────────────────────────────────────────────────

  tool_name ∈ {"Task", "Agent"}?
    No  ──► pass (handled by Write/Edit/MultiEdit branch)
    Yes ──►

  context_budget.read_current_tokens(project_dir, session_id)
    └─► _derive_transcript_path(cwd, session_id)
          └─► ~/.claude/projects/{cwd_key}/{session_id}.jsonl
          └─► containment check: resolved path must be under ~/.claude/
    └─► compute_context_tokens(transcript_path)
          └─► read last 500 lines, scan in reverse
          └─► find last assistant entry with usage block
          └─► return input_tokens + cache_read_input_tokens
                     + cache_creation_input_tokens

  live_tokens is not None?
    No  ──► exit silently (no write; state.json unchanged)
    Yes ──►

  state.json updated:
    context_current_tokens          = live_tokens
    context_current_tokens_recorded_at = "<now>"

  Never emits decision: block. Write-only branch.
```

---

## Diagram 2 — PreToolUse enforcement (before each builder/reviewer spawn)

The hook is the sole budget enforcer. It fires every time the orchestrator
spawns a Task/Agent and either passes (no action) or blocks (with a prompt
the operator must answer).

```
PRE_TOOL_USE HOOK — fires on every Task / Agent spawn
──────────────────────────────────────────────────────────────────

  tool_name ∈ {"Task", "Agent"}?
    No  ──► pass (not an agent spawn)
    Yes ──►

  context_budget.decide(project_dir)
    └─► Read state.json
          tokens     = state.get("context_current_tokens")
          recorded   = state.get("context_current_tokens_recorded_at")
          reset_at   = state.get("context_session_reset_at")

    └─► tokens is None?
          Yes ──► BLOCK: CONTEXT CHECK REQUIRED
                    "Context token count is missing or stale.
                     It will update automatically after the next
                     tool call completes."

    └─► recorded < reset_at?   (session-boundary staleness check)
          Note: recorded == reset_at is treated as FRESH
          (SessionStart baseline sets both to the same timestamp)
          Yes ──► BLOCK: CONTEXT CHECK REQUIRED (stale pre-clear value)

    └─► tokens + estimated_next_step > threshold × (1 + overrun_pct)?
          (default: 120,000 × 1.10 = 132,000)
          Yes ──► BLOCK: CONTEXT BUDGET prompt
                    options: Proceed (acknowledge) or /clear and resume
                    hook writes: state["context_budget_acknowledged_at"]

          No  ──► PASS — builder/reviewer spawn proceeds
```

---

## Diagram 3 — Session reset (/clear or startup)

A `/clear` (or fresh process startup) wipes the live context window. The
SessionStart hook resets `context_current_tokens` to a baseline and writes
`context_session_reset_at` so any values recorded before the clear are
detected as stale on the next PreToolUse enforcement pass.

```
SESSION RESET — fires on SessionStart with source "clear" or "startup"
──────────────────────────────────────────────────────────────────

  session_start.py
    └─► session_reset.decide_reset(source="clear", state)
          └─► returns {
                "context_current_tokens": 25000,           (baseline)
                "context_current_tokens_recorded_at": "<now>",
                "context_session_reset_at": "<now>"
              }

  state.json updated:
    context_current_tokens             = 25000  ← fresh-session baseline
    context_current_tokens_recorded_at = "<now>"  ← == reset_at → fresh
    context_session_reset_at           = "<now>"  ← boundary timestamp

  Effect on pre-clear values:
    Any context_current_tokens_recorded_at < context_session_reset_at
      └─► _is_stale() returns True
      └─► decide() treats value as absent → CONTEXT CHECK REQUIRED

  On first spawn after /clear:
    PostToolUse fires after the spawn completes
    └─► reads fresh JSONL count → overwrites context_current_tokens
    └─► recorded_at = "<now>" > reset_at → fresh

  First spawn uses the SessionStart baseline (25,000). PostToolUse then
  updates it with the real JSONL count after the spawn completes.
```

`resume` and `compact` sources do not reset. `resume` restores the same
window so the counter is still valid; `compact` is deliberately excluded
because the post-compact window size is unknown and a stale counter
over-blocks (fail-safe; deferred per CER-047).

---

## Data model

The keys below live in `<project_dir>/.companion/state.json` and define the
contract between PostToolUse, PreToolUse, and the SessionStart reset path.

| `state.json` key | Type | Writer | Reader | Purpose |
|------------------|------|--------|--------|---------|
| `context_current_tokens` | int | `post_tool_use.py` (Task/Agent), `set-context-tokens` (override), `session_start.py` (baseline) | `decide()` | Live context window token count |
| `context_current_tokens_recorded_at` | UTC ISO-8601 string | same writers as above | `_is_stale()` | Staleness check against `context_session_reset_at` |
| `context_session_reset_at` | UTC ISO-8601 string | `session_start.py` on `clear`/`startup` | `_is_stale()` | Boundary; values recorded before this are stale |
| `context_budget_threshold` | int (default 120,000) | operator / bootstrap | `decide()` | Hard budget limit |
| `context_budget_acknowledged_at` | int (token count at ack) | `pre_tool_use.py` (on block + ack) | `decide()` | Suppresses re-prompt within reprompt margin |
| `context_story_tokens` | dict | `set-context-tokens` (legacy) | — | **Legacy after INFRA-182**; no longer read by `decide()` |

---

## See also

- `skills/pairmode/scripts/context_budget.py` — `decide()`, `read_current_tokens()`, and helpers
- `skills/pairmode/scripts/session_reset.py` — `decide_reset()` and reset rules
- `hooks/post_tool_use.py` — Task/Agent branch: JSONL reader and sole live writer of `context_current_tokens`
- `hooks/pre_tool_use.py` — thin dispatcher; sole writer of `context_budget_acknowledged_at`
- `docs/architecture.md` § Pairmode build loop step 9 — prose specification
- `CLAUDE.build.md` Context gate step — orchestrator-side display procedure
