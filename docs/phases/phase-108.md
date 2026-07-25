---
era: "003"
phase_class: production
---

# project — Phase 108: Era 003 close (gated on observability delivery)

← [Phase 107: CER backlog drain to zero](phase-107.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Validate that observability — the era's purpose — was actually delivered (SPA functional over the fleet, effort recording sound on real campaign data), define the era exit criterion, and run the era transition. Does not checkpoint until validation passes.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-278 | Observability validation: SPA over the post-campaign fleet, effort-db integrity audit on campaign data, evidence record | draft |
| INFRA-279 | Define the era 003 exit criterion, finalize era summary and phase table through 108 | draft |
| RELEASE-072 | Era transition: run era_transition.py, close era 003, scaffold era 004 | draft |

## Ordering

Strictly INFRA-278 → INFRA-279 → RELEASE-072. If INFRA-278 finds defects, fix stories
are minted **into this phase** and the phase stays open — that is the gate. The era does
not close on unvalidated observability.

## Checkpoint proves

Era 003 reads `status: complete` with a met, documented exit criterion; the era ledger
(repaired in Phase 104) is accurate end-to-end through phase 108; era 004 is active.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-108 Cold-eyes checklist

— developer fills in after phase completion —
