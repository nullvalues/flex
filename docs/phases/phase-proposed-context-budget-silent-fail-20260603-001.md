---
era: "001"
---

# flex — Proposed Phase: context_budget.py silent-fail edges (CER-040, CER-041)

**Proposed:** 2026-06-03  
**Trigger:** Phase 58 back-check (opus) identified two cases where the new state.json-based gate can fail silently, reproducing the shape of the Phase 47 bug it replaced.

---

## Intent

Phase 58 fixed the primary failure mode (transcript_path always None → gate never fires). The back-check found two residual silent-fail edges:

1. **CER-040** — `state.json` absent or malformed → `decide()` returns `None` (pass-through) with no operator signal. Same silent-fail shape, one layer out.
2. **CER-041** — No session invalidation on `context_current_tokens`. After `/clear`, the key retains the previous session's value until the orchestrator overwrites it at the first Context gate. A Task spawn before the Context gate reads stale data.

Both are mitigated by the pairmode protocol in the happy path. Both are worth closing because they leave invisible dead-gate states with no signal.

---

## Proposed stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-150 | `context_budget.py` — block on missing/malformed state.json with operator signal (CER-040) | planned |
| INFRA-151 | `context_budget.py` — timestamp `context_current_tokens` and treat stale values as absent (CER-041) | planned |

---

## Design notes (for spec mode)

**INFRA-150 shape:**
- `_read_state()` currently catches all exceptions and returns `None`. A new path is needed to distinguish "state.json does not exist" (non-pairmode project → still fail-open) from "state.json exists but is malformed" (misconfigured pairmode project → should surface as `CONTEXT CHECK REQUIRED`).
- One approach: check `state_path.exists()` first; if exists but `json.loads` raises, return a sentinel (e.g. `{}` empty dict) so `read_context_tokens_from_state({})` returns `None` and the `_CONTEXT_CHECK_REQUIRED_MSG` block fires.
- Non-pairmode compat: no state.json → still pass-through (unchanged from current).

**INFRA-151 shape:**
- `flex_build.py set-context-tokens` should write `context_current_tokens_recorded_at` (UTC ISO-8601) alongside `context_current_tokens`.
- `read_context_tokens_from_state` should check staleness: if recorded_at exists and is older than `context_current_tokens_ttl_minutes` (state.json config, default 60), treat as absent → triggers CONTEXT CHECK REQUIRED.
- `story_context.py --clear` should also reset `context_current_tokens` and `context_current_tokens_recorded_at` to `None`/absent (belt and suspenders alongside TTL).
- Tests: fresh write → valid; write then TTL-expired check → absent; `--clear` → absent.

---

## To spec this phase

In a fresh session, say:

```
spec phase 59: close the two context_budget.py silent-fail edges from the Phase 58 back-check —
CER-040 (malformed state.json fails open) and CER-041 (stale context_current_tokens after /clear).
See docs/phases/phase-proposed-context-budget-silent-fail-20260603-001.md for design notes.
```
