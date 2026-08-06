---
era: "005"
phase_class: production
---

# project — Phase 132: Add excluded-siblings mechanism to the fleet-name reconciliation gate (CER-195)

**Parent phase:** Phase 125 — De-identify fleet repo references from the public repo (CER-172)

← [Phase 131: Fix scrub_fleet_names crash, incomplete anonymization coverage, and unwired gate (CER-194)](phase-131.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-195: scrub_fleet_names.py's --verify reconciliation check (INFRA-400/401) has no way to mark a sibling repo as intentionally excluded from anonymization, so it can never report a clean pass for a project with any legitimately non-fleet sibling directories. Add a small, local-config-only exclusion list scrub_fleet_names.py's reconciliation consults, documented in the committed .example template with synthetic names only.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-402 | Add excluded-siblings mechanism to the fleet-name reconciliation gate (CER-195) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-132 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
