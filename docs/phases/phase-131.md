---
era: "005"
phase_class: production
---

# project — Phase 131: Fix scrub_fleet_names crash, incomplete anonymization coverage, and unwired gate (CER-194)

**Parent phase:** Phase 125 — De-identify fleet repo references from the public repo (CER-172)

← [Phase 130: Close CER-172 scrub completeness and regression gaps (CER-188)](phase-130.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-194: fleet_map.py's sibling_repo_dirs() crashes with an unhandled PermissionError instead of skipping unreadable directories, breaking scrub_fleet_names.py --verify entirely; fleet_discovery.py's snapshot anonymization misses signal1_value/signal1_absent_detail and the CLI print path, so real paths can still leak into docs/fleet-snapshot.md or stdout; and the install-hook pre-commit gate from INFRA-400 is never actually wired into any operational touchpoint, so it protects nothing today.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-401 | Fix scrub_fleet_names crash, incomplete anonymization coverage, and unwired gate (CER-194) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-131 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
