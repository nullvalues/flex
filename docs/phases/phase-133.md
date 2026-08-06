---
era: "005"
phase_class: production
---

# project — Phase 133: Fix invalid-JSON fleet-config example causing silent fail-open verify (CER-196)

**Parent phase:** Phase 132 — Add excluded-siblings mechanism to the fleet-name reconciliation gate (CER-195)

← [Phase 132: Add excluded-siblings mechanism to the fleet-name reconciliation gate (CER-195)](phase-132.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-196: .pairmode-fleet.local.json.example is invalid JSON (leading // comment lines), and fleet_map.load_local_fleet_map silently swallows the resulting JSONDecodeError, so scrub_fleet_names.verify() silently reports no config exists and passes instead of catching the leak-prevention gate being unusable. Make the template either valid JSON or the loader fail loudly on parse errors, plus a test asserting the committed template parses.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-403 | Fix invalid-JSON fleet-config example causing silent fail-open verify (CER-196) | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-133 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
