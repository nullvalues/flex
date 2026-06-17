# Context gate flow

This document is the single reference for the pairmode context gate mechanism.
It shows how `/context`, `flex_build.py set-context-tokens`,
`context_story_tokens`, `context_session_reset_at`, and `pre_tool_use.py`
interact across the orchestrator, the hook, and the SessionStart reset path.

The prose architecture lives across `CLAUDE.build.md`, `docs/architecture.md`,
and `CLAUDE.md`. This document is the visual companion to that prose; the code
in `skills/pairmode/scripts/context_budget.py` and
`skills/pairmode/scripts/session_reset.py` is the ground truth.

---

## Diagram 1 — Per-story setup (orchestrator, before builder spawn)

The orchestrator runs this sequence at the Context gate step for each story,
once, before spawning the builder.

```
ORCHESTRATOR — Context gate (once per story, before builder spawn)
──────────────────────────────────────────────────────────────────

  story_context.py --set RAIL-NNN
    └─► state["current_story"]["id"] = "RAIL-NNN"

  /context
    └─► N tokens (live window size — authoritative)

  flex_build.py set-context-tokens --tokens N
    └─► state["context_story_tokens"]["RAIL-NNN"] = {
          "tokens": N,
          "recorded_at": "<UTC ISO-8601>"
        }
    └─► state["context_current_tokens"] = N  (display compat)

  Output: "CONTEXT: N / 120,000 tokens"

  flex_build.py story-cost-estimate --story-id RAIL-NNN
    └─► estimate E tokens  (informational; does not block)
```

---

## Diagram 2 — Enforcement (hook, on every builder/reviewer spawn)

The hook is the sole budget enforcer. It fires every time the orchestrator
spawns a Task/Agent and either passes (no action) or blocks (with a prompt
the operator must answer).

```
PRE_TOOL_USE HOOK — fires on every Task / Agent spawn
──────────────────────────────────────────────────────────────────

  tool_name ∈ {"Task", "Agent"}?
    No  ──► pass (not an agent spawn)
    Yes ──►

  Read state.json
    story_id   = state["current_story"]["id"]
    entry      = state["context_story_tokens"].get(story_id)
    reset_at   = state.get("context_session_reset_at")

  Entry exists?
    No  ──► BLOCK: CONTEXT CHECK REQUIRED
              "No token count recorded for RAIL-NNN this session.
               Call /context and run set-context-tokens."

  entry["recorded_at"] > reset_at?   (session-boundary check)
    No  ──► BLOCK: CONTEXT CHECK REQUIRED
              "Token count for RAIL-NNN predates the last /clear.
               Call /context and run set-context-tokens."

  tokens + estimated_next_step > threshold × (1 + overrun_pct)?
    (default: 120,000 × 1.10 = 132,000)
    Yes ──► BLOCK: CONTEXT BUDGET prompt
              options: Proceed (acknowledge) or /clear and resume
              writes: state["context_budget_acknowledged_at"]

    No  ──► PASS — builder/reviewer spawn proceeds
```

---

## Diagram 3 — Session reset (/clear or startup)

A `/clear` (or fresh process startup) wipes the live context window. The
SessionStart hook records a boundary timestamp so any pre-clear dict entries
are treated as stale on the next enforcement pass.

```
SESSION RESET — fires on SessionStart with source "clear" or "startup"
──────────────────────────────────────────────────────────────────

  session_start.py
    └─► session_reset.decide_reset(source="clear", state)
          └─► returns {
                "context_current_tokens": 25000,  (baseline)
                "context_current_tokens_recorded_at": "<now>",
                "context_session_reset_at": "<now>"
              }

  state.json updated:
    context_session_reset_at = "<now>"   ← boundary timestamp

  Effect on existing dict entries:
    state["context_story_tokens"]["RAIL-NNN"]["recorded_at"] < context_session_reset_at
      └─► _is_entry_fresh() returns False
      └─► decide() treats entry as absent → CONTEXT CHECK REQUIRED

  On resume after /clear:
    Orchestrator calls /context → records fresh N for RAIL-NNN
    state["context_story_tokens"]["RAIL-NNN"] = {
      "tokens": N,          ← post-clear value (overwrites pre-clear)
      "recorded_at": "<now>" ← now > context_session_reset_at → fresh
    }
```

`resume` and `compact` sources do not reset. `resume` restores the same
window so the dead-reckoning counter is still correct; `compact` is
deliberately excluded because the post-compact window size is unknown and a
stale counter over-blocks (fail-safe; deferred per CER-047).

---

## Data model

The keys below live in `<project_dir>/.companion/state.json` and define the
contract between the orchestrator, the hook, and the SessionStart reset path.

| `state.json` key | Type | Writer | Reader | Purpose |
|------------------|------|--------|--------|---------|
| `context_story_tokens` | `dict[str, {tokens: int, recorded_at: str}]` | `set-context-tokens` | `decide()` | Per-story token count history; entries validated by hook |
| `context_session_reset_at` | UTC ISO-8601 string | `session_start.py` | `_is_entry_fresh()` | Boundary; entries older than this are stale |
| `context_budget_threshold` | int (default 120,000) | operator / bootstrap | `decide()` | Hard budget limit |
| `context_budget_acknowledged_at` | int (token count at ack) | `pre_tool_use.py` (on block + ack) | `decide()` | Suppresses re-prompt within reprompt margin |
| `context_current_tokens` | int | `set-context-tokens`, `session_start.py` | display only | Backwards-compat scalar; not used by hook or `decide()` |

---

## See also

- `skills/pairmode/scripts/context_budget.py` — `decide()` and helper logic
- `skills/pairmode/scripts/session_reset.py` — `decide_reset()` and reset rules
- `hooks/pre_tool_use.py` — thin dispatcher and the only state.json writer for
  `context_budget_acknowledged_at`
- `docs/architecture.md` § Pairmode build loop step 9 — prose specification
- `CLAUDE.build.md` Context gate step — orchestrator-side procedure
