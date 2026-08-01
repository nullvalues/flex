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
| INFRA-278 | Observability validation: SPA over the post-campaign fleet, effort-db integrity audit on campaign data, evidence record | backlog |
| INFRA-279 | Define the era 003 exit criterion, finalize era summary and phase table through 108 | backlog |
| RELEASE-072 | Era transition: run era_transition.py, close era 003, scaffold era 004 | backlog |

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

## Superseded

**2026-08-01 (INFRA-310, Phase 116, AG-3).** This phase's obligations —
observability validation, the era exit criterion, and the era transition —
were folded into era 004's closeout stories rather than resumed here.
Nothing is deleted; the Goal, Stories table and Ordering above remain the
historical record.

- **INFRA-278** (observability validation) split in two along its own
  title's two halves, because no single era-004 story covered both:
  - The **SPA/UI functional-validation** half was discharged by
    **INFRA-312** (Phase 115) — dogfood checklist over ≥2 registered repos
    plus a scoped TypeScript route-test runner; see INFRA-312's `##
    Evidence` section.
  - The **effort-db integrity** half was never discharged by INFRA-312
    (route/UI-shaped only, never touches `effort.db`) — rescued as new
    story **INFRA-329** (Phase 115, added by the 2026-07-30 reconciliation
    sweep as a sibling of INFRA-312) — effort-db integrity audit on
    post-campaign fleet data; see INFRA-329's `## Evidence` section.
- **INFRA-279**'s exit-criterion obligation was folded into
  `docs/eras/003-flex-orchestrator-as-harness.md`'s own `## Exit criterion`
  section, written by **INFRA-310** (this story, Ensures 26).
- **RELEASE-072**'s era transition — closing era 003 by ID, verifying
  exactly one era active at tag time — was executed by **INFRA-310** (this
  story, Ensures 26) via INFRA-314's gated by-ID close path. Era 004
  already exists and is active; no new era was scaffolded (RELEASE-072's
  original title's "scaffold era 004" clause is stale).

---

### CP-108 Cold-eyes checklist

— developer fills in after phase completion —
