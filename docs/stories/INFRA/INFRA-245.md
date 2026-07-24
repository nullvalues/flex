---
id: INFRA-245
rail: INFRA
title: Compact-aware context-counter refresh — unwedge the gate after auto-compaction
status: complete
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/session_start.py
  - skills/pairmode/scripts/session_reset.py
touches:
  - skills/pairmode/scripts/context_budget.py
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_session_reset.py
  - tests/pairmode/test_context_budget.py
  - docs/architecture.md
---

## Context

An adversarial audit of the context-budget gate (this session, in response to the
operator's question about whether the orchestrator's context controls actually work
as designed — specifically whether they're blind-guessing or conflating subagent
token spend with the orchestrator's own window) confirmed the gate's live mechanism
is sound where it's reached: `hooks/post_tool_use.py` writes `context_current_tokens`
from a real JSONL transcript read after every Task/Agent completion (not a
dead-reckoning estimate), and no subagent-token conflation exists in the current
code (the historical conflation vector, `bump-context-tokens`, has zero live callers
— see Out of scope).

But `skills/pairmode/scripts/session_reset.py:41`'s `RESET_SOURCES = frozenset({"clear",
"startup"})` deliberately excludes `"compact"` — confirmed by direct trace this
session: a real transcript shows usage dropping from ~166k to ~39k across a
`compact_boundary` entry, while `state.json` retains the pre-compact figure until the
next Task/Agent spawn completes and refreshes it. This was a defensible fail-safe
choice while the PreToolUse gate was decorative (CER-047's original note: "counter
overstates, which fails safe by over-blocking — revisit if it bites").

It now needs revisiting, because **INFRA-241 (this same phase) reconnects the
PreToolUse gate to real build-cycle spawns.** Once that lands, the stale-high count
after a `/compact` blocks exactly the spawn class whose completion would refresh
it — an operator-facing deadlock, not just occasional over-caution, escapable only by
a manual `/context` + `set-context-tokens` step, a `/clear`, or an ungated spawn. That
manual-step escape hatch is precisely what this entire mechanism exists to eliminate
(per CER-047's own framing).

Per the operator's explicit direction on this line of work: this is not license for a
parser rewrite or a remodel of the context-budget mechanism — the existing read/write
design is sound and should be preserved. This story is narrowly the missing reset
trigger for one specific, real event (`/compact`), analogous to the `/clear`/`startup`
reset that already exists.

## Requires

- INFRA-241 landed first (or in the same build cycle) — this story's urgency is
  specifically that INFRA-241 turns a latent staleness gap into a live deadlock;
  building this story before INFRA-241 is harmless but less urgent.

## Ensures

- On a `SessionStart` hook invocation where `source == "compact"`, the counter is
  refreshed rather than left at its pre-compact value — either by re-deriving it from
  the transcript's first post-`compact_boundary` assistant usage entry if one is
  already present, or by falling back to a documented compact-baseline constant
  (analogous to `session_reset.py`'s existing `DEFAULT_BASELINE_TOKENS` for
  `clear`/`startup`) if not.
- The refresh direction stays fail-safe, consistent with the existing design: on any
  read failure or ambiguity, the fallback is the conservative (higher, more
  cautious) value, never a value that could cause the gate to under-block a session
  that's actually still large.
- A test simulates the exact wedge described in Context: `state.json` holds a stale
  high count, threshold is set low enough to trigger a block, a `compact` SessionStart
  event fires, and the next build-cycle spawn is confirmed *not* blocked on the
  phantom pre-compact number.
- `session_reset.py`'s docstring (currently describing counter behavior in terms that
  predate the INFRA-182 JSONL-read redesign — confirm and correct if still present) is
  updated to accurately describe the current read/write mechanism, not the retired
  dead-reckoning design.
- `docs/architecture.md` is updated to document the `compact` reset path alongside the
  existing `clear`/`startup` one.
- Explicit decision recorded on `flex_build.py`'s dormant `bump-context-tokens`
  command (zero live callers, confirmed by grep this session; historically the actual
  subagent/orchestrator conflation vector, removed as a caller in phases 70-71 per
  `docs/phases/phase-71.md:14`): either remove it outright, or keep it with a
  docstring warning that feeding it subagent costs violates the effort.db ≠
  context-control invariant (`docs/architecture.md`'s DP7 section) — don't leave it
  silently dormant with no comment either way.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains).

## Instructions

1. Add `"compact"` handling to `session_reset.py`'s reset logic — a new branch
   alongside (not replacing) the existing `clear`/`startup` path, per the Ensures
   refresh strategy.
2. Confirm `hooks/session_start.py` actually receives and passes through the
   `source: "compact"` field from its hook payload (the SessionStart hook input
   schema includes `source` per `clear`/`resume`/`compact`/`startup` — verify this
   repo's handler reads it, since CER-047's history notes this field existed but
   wasn't originally read).
3. Add the wedge-simulation test.
4. Correct `session_reset.py`'s docstring if it still describes the retired
   dead-reckoning design.
5. Update `docs/architecture.md`.
6. Make and record the `bump-context-tokens` decision (remove vs. warn-and-keep).
7. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Any change to the live transcript-parsing mechanism itself
  (`compute_context_tokens`) — confirmed sound and already fail-safe; see INFRA-241's
  amended scope for the drift-canary test, which is the only parser-adjacent change
  in this phase.
- Re-deriving `flex_factor` or the threshold constant's actual value — separate
  concerns (INFRA-238 and documentation-only, respectively).
- Building any mechanism to programmatically invoke the real `/context` command —
  confirmed this session (via direct check against current Claude Code hook/tooling
  documentation) that no such mechanism exists: hooks cannot invoke `/context`, hook
  payloads carry no token/usage fields, and transcript-JSONL parsing — while
  officially unsupported and subject to change across Claude Code releases — is the
  only available approximation today. This story works within that known constraint;
  it does not attempt to escape it.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure; new
coverage proves the compact-triggered refresh actually unwedges a simulated
post-compact block.
