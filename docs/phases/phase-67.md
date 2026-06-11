---
era: "002"
---

# flex — Phase 67: Bootstrap context-token seed

← [Phase 66: PAIRMODE_VERSION single-source](phase-66.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Eliminate the manual `set-context-tokens` step required on every fresh pairmode
bootstrap. Today, `context_budget.decide()` blocks with CONTEXT CHECK REQUIRED
when `state.json` has no `context_current_tokens` entry — which is always the
case after a first bootstrap, because `_record_state()` seeds the budget thresholds
but not the token count itself. The fix: seed `context_current_tokens = 1` alongside
the other budget defaults in `_record_state()` when creating a new `state.json`. A
value of 1 passes the `> 0` guard in `read_context_tokens_from_state`, produces
`(1 + expected_next) < ceiling`, and lets the first build step proceed without
manual intervention. The orchestrator's normal `set-context-tokens` call will
replace the seed with the real value before the first build step executes.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-174 | Seed `context_current_tokens` in `_record_state()` to skip manual bootstrap step | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-67 Cold-eyes checklist

— developer fills in after phase completion —
