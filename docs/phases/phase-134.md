---
era: "005"
phase_class: production
---

# project — Phase 134: Recognize OBSOLETE as a CER resolution marker (CER-207)

← [Phase 133: Fix invalid-JSON fleet-config example causing silent fail-open verify (CER-196)](phase-133.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-207: cer.is_resolution_marked only recognizes RESOLVED/SUPERSEDED as closing a backlog row, but this project's own convention (used 19+ times) closes rows with an OBSOLETE annotation instead, which the shared grammar doesn't recognize -- causing already-fixed rows to report as permanently open to groom/gate/next-action forever. Extend the grammar to accept OBSOLETE, add a regression test, and update the published grammar documentation.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-404 | Recognize OBSOLETE as a CER resolution marker (CER-207) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-134 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
