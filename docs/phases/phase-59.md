---
era: "001"
---

# flex — Phase 59: context_budget.py silent-fail edge closure (CER-040, CER-041)

← [Phase 58: Context budget gate — state.json contract](phase-58.md)

**Parent phase:** Phase 58 introduced the state.json contract for the context budget gate.
A Phase 58 back-check (opus) found two residual silent-fail edges where the new gate can
still fail open with no operator signal — reproducing the shape of the Phase 47 bug it replaced.

## Goal

Close both residual silent-fail edges in `context_budget.py`:

- **CER-040** — `state.json` exists but is malformed → `_read_state()` returns `None` instead of
  surfacing a signal, so `decide()` passes through identically to "no state.json". An operator
  running pairmode on a project with a corrupt state file gets no warning.
- **CER-041** — `context_current_tokens` has no TTL. After `/clear`, the key retains the previous
  session's value indefinitely. A Task spawn before the next Context gate reads stale data and
  the CONTEXT CHECK REQUIRED block never fires.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-150 | `context_budget.py` — block on malformed state.json with operator signal (CER-040) | complete |
| INFRA-151 | `context_budget.py` — timestamp `context_current_tokens` and treat stale values as absent (CER-041) | complete |

**Story dependency:** INFRA-150 and INFRA-151 touch different functions in `context_budget.py`
and are independently buildable. Build INFRA-150 first (simpler; purely a `_read_state` fix).

## Schema delivery

No new persistent schema objects.

| Object | Management surface | Exception |
|---|---|---|
| `context_current_tokens_recorded_at` (state.json key) | Written by `set-context-tokens`; cleared by `story_context.py --clear` | State.json is a flat config file, not a table; no UI required |

---

### CP-59 Cold-eyes checklist

— developer fills in after phase completion —
