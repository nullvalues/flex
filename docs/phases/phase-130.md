---
era: "005"
phase_class: production
---

# project — Phase 130: Close CER-172 scrub completeness and regression gaps (CER-188)

**Parent phase:** Phase 125 — De-identify fleet repo references from the public repo (CER-172)

← [Phase 129: De-duplicate pairmode_drift_report.py's stale override-key parser (CER-181)](phase-129.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-188: the CER-172 fleet-name scrub (INFRA-393/394) is incomplete (a real sibling-repo name was dropped from .pairmode-fleet.local.json during externalization and never scrubbed; at least two more real names were never in the map at all) and can regress (fleet_discovery.py still writes real absolute paths into the tracked docs/fleet-snapshot.md, scrub_fleet_names.py's own output/errors leak real names, and no mechanical gate enforces --verify before a commit). Reconcile the map against the real sibling set, anonymize fleet_discovery.py's write path, stop the script's own output from leaking real names, and add a verify gate.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-400 | Close CER-172 scrub completeness and regression gaps (CER-188) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-130 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
