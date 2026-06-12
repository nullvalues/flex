---
era: "002"
---

# flex — Phase 68: SessionStart context-counter reset (CER-047)

← [Phase 67: Bootstrap context-token seed](phase-67.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Close the second half of the manual-context-step problem. Phase 67 fixed the
fresh-bootstrap case; this phase fixes the mid-build `/clear` case (CER-047).
Today `context_current_tokens` survives `/clear`: the dead-reckoning counter
keeps the old session's accumulated total (confirmed in production: 212,492
tokens carried across a clear in coherra), and the context gate re-blocks on a
number that describes a window that no longer exists. The CER-041 TTL only
recovers after 60 minutes, and even then routes the operator to the same manual
`set-context-tokens` step.

The fix follows the documented thin-delegation hook pattern: `hooks/
session_start.py` reads the hook stdin payload (which carries
`source: "startup" | "resume" | "clear" | "compact"`), delegates the decision
to a new pure module, and — when the source indicates a fresh context window
(`clear` or `startup`, never `resume`) — performs a single hook-owned state
write resetting `context_current_tokens` to a fresh-session baseline.
`compact` is deliberately out of scope (see CER-047).

This amends two documented contracts and both amendments are in-scope stories
here, not side effects: the architecture.md rule that `context_current_tokens`
is "never written by the … hook", and the CLAUDE.md HOOK PERFORMANCE
exception list, which gains a `session_start.py` thin-delegation entry.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-175 | Reset `context_current_tokens` on SessionStart `clear`/`startup` via thin-delegation hook | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-68 Cold-eyes checklist

— developer fills in after phase completion —
