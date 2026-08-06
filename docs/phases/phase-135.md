---
era: "005"
phase_class: production
---

# project — Phase 135: Fleet-gate trivial quality fixes (CER-189/198/199/203/204/205)

← [Phase 134: Recognize OBSOLETE as a CER resolution marker (CER-207)](phase-134.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close six small, independently-scoped quality gaps in the fleet-name reconciliation gate found across the CER-172 remediation chain: a template that looks like real names rather than labels (CER-189), a non-dict fleet-map shape fail-open (CER-198), unescaped shell interpolation in the pre-commit hook template (CER-199), a silently-wrong --root fallback (CER-203), a structurally-always-zero unmapped count (CER-204), and a case-exact conflict check against a case-expanding scrub (CER-205). All are one-file, small fixes in fleet_map.py/scrub_fleet_names.py/.pairmode-fleet.local.json.example.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-405 | Fleet-gate trivial quality fixes (CER-189/198/199/203/204/205) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-135 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
