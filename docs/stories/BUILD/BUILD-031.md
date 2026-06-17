---
id: BUILD-031
rail: BUILD
title: "Context gate flow diagram; README tooling update"
status: planned
phase: "73"
story_class: doc
primary_files:
  - docs/pairmode/context-gate-flow.md
  - README.md
touches: []
---

# BUILD-031 — Context gate flow diagram; README tooling update

**Phase:** 73
**Rail:** BUILD

## Background

Two documentation gaps after Phase 73:

1. **No flow diagram exists** for the context gate mechanism. The architecture is
   described in prose across `CLAUDE.build.md`, `docs/architecture.md`, and `CLAUDE.md`,
   but there is no single reference showing how `/context`, `set-context-tokens`,
   `context_story_tokens`, `context_session_reset_at`, and `pre_tool_use.py` interact
   across actors and tool calls.

2. **README step 2 is stale** — currently describes the Phase 72 JSONL approach.
   Additionally, several sections are behind current tooling: the era status blurb
   (Era 002 is underway, not just "opening"), the Known Limitations list (several items
   have been resolved or changed), and the build loop description (which references
   `context_current_tokens` scalar rather than the dict).

This story must be built **after INFRA-181** (which restores the CLAUDE.build.md
Context gate and updates architecture.md). BUILD-031 produces the flow diagram and
README reflecting the final Phase 73 architecture.

## Ensures

### `docs/pairmode/context-gate-flow.md` (new file)

A reference document containing two ASCII flow diagrams and a data model table.

#### Diagram 1 — Per-story setup (orchestrator, before builder spawn)

Shows the sequence the orchestrator follows at the Context gate step for each story:

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

#### Diagram 2 — Enforcement (hook, on every builder/reviewer spawn)

Shows the hook's decision tree when `pre_tool_use.py` intercepts a Task/Agent call:

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

#### Diagram 3 — Session reset (/clear or startup)

Shows how a `/clear` invalidates pre-clear dict entries:

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

#### Data model table

| `state.json` key | Type | Writer | Reader | Purpose |
|------------------|------|--------|--------|---------|
| `context_story_tokens` | `dict[str, {tokens: int, recorded_at: str}]` | `set-context-tokens` | `decide()` | Per-story token count history; entries validated by hook |
| `context_session_reset_at` | UTC ISO-8601 string | `session_start.py` | `_is_entry_fresh()` | Boundary; entries older than this are stale |
| `context_budget_threshold` | int (default 120,000) | operator / bootstrap | `decide()` | Hard budget limit |
| `context_budget_acknowledged_at` | int (token count at ack) | `pre_tool_use.py` (on block + ack) | `decide()` | Suppresses re-prompt within reprompt margin |
| `context_current_tokens` | int | `set-context-tokens`, `session_start.py` | display only | Backwards-compat scalar; not used by hook or `decide()` |

---

### `README.md` updates

#### Step 2 of "The build loop" — replace stale Context gate paragraph

Replace the current step 2 with:

```
2. **Context gate.** Before the next builder spawns, the orchestrator calls `/context`
   to read the live token count and records it for the current story via
   `flex_build.py set-context-tokens`, which writes to
   `state["context_story_tokens"][story_id]` — a per-story dict that accumulates
   across the session. On `/clear` or fresh startup, the SessionStart hook writes
   `context_session_reset_at`, invalidating pre-clear entries.
   The hook is the sole enforcer: `hooks/pre_tool_use.py` intercepts every Agent
   spawn, looks up the story's dict entry, validates it post-dates the last session
   reset, and blocks if the entry is absent, stale, or the projected token total
   exceeds the overrun ceiling (`threshold × 1.10`, default 132k). If the orchestrator
   skipped `set-context-tokens`, the hook blocks with CONTEXT CHECK REQUIRED — the
   lapse becomes a hard stop, not a silent pass. See
   `docs/pairmode/context-gate-flow.md` for the full flow diagram.
```

#### Era status blurb (lines 10-15) — update to reflect Era 002 progress

Replace:
```
**Era 001 — pairmode foundation (complete)**
An Anchor evolution focused on `/flex:pairmode` context management: enforcing 150k
context limits per build, persistent refocus to the system of record, and systematic
shifts of deterministic processes to code. The result is a largely hands-free
auto-mode build loop. Era 002 opens with a planned observability SPA to replace the
companion sidebar.
```

With:
```
**Era 001 — pairmode foundation (complete)**
An Anchor evolution focused on `/flex:pairmode` context management: enforcing 150k
context limits per build, persistent refocus to the system of record, and systematic
shifts of deterministic processes to code. The result is a largely hands-free
auto-mode build loop.

**Era 002 — build loop and observability (active)**
Extends the build loop with observability and mechanical enforcement: a browser-based
SPA for context budget and effort metrics (Phase 63), story-scoped file permissions
via hook enforcement (Phase 55), a reliable story-ID-bound context gate (Phase 73),
and ongoing closure of spec-quality gaps that cause builder friction.
```

#### Known Limitations — update resolved/changed items

- Remove or update the limitation about `lesson_review.py` not applying suggestions
  if it has been resolved. If still accurate, keep as-is.
- Update "Story status updates and some orchestrator steps require manual bash
  invocations" to note that `story_update.py` and `flex_build.py` now cover the
  full status lifecycle (introduced in Phases 18, 22, 45).
- Add: "Context gate reliability depends on the orchestrator calling `/context` and
  `set-context-tokens` before each story spawn. The hook enforces this by blocking
  when the entry is absent, but cannot force the orchestrator to call `/context` if
  it is operating outside the pairmode build loop."

## Implementation notes

- This is a `doc` story. No Python logic is added or changed.
- `docs/pairmode/context-gate-flow.md` is a **new file**; write it from scratch.
- The builder should verify the diagram matches the actual `context_budget.py`
  and `session_reset.py` code as shipped by INFRA-180/181 before committing.
- The README "Known Limitations" audit: read the current list, verify each item
  against the current codebase state, update accordingly. Do not remove items that
  are still accurate.
- No test file expected for this story (`story_class: doc`).
