---
era: "005"
phase_class: production
---

# project — Phase 136: Fleet-gate coverage and leak-closure fixes (CER-190/191/197/206)

← [Phase 135: Fleet-gate trivial quality fixes (CER-189/198/199/203/204/205)](phase-135.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close four real coverage/leak gaps in the fleet-name reconciliation gate: unbounded case-variant/domain-suffix blind spots in the scrub pattern (CER-190), a silent 16-to-15 candidate-count drop in fleet_discovery's sibling scan (CER-191), un-anonymized real paths nested inside --json duplicate_hooks/machine_absolute_hooks stdout output (CER-197), and a malformed-config error path that silently discards a custom _fleet_root and degrades anonymization scope (CER-206).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-406 | Fleet-gate coverage and leak-closure fixes (CER-190/191/197/206) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-136 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
