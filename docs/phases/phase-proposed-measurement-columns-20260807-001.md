---
era: "004"
phase_class: production
status: proposed
sequenced: false
---

# project — Proposed phase (measurement-columns): Measurement columns and dead-code retirement

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
      Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Land the two D1/D2 measurement columns (cause-class on effort.db retries, silent-deviation marking on verdicts) so era 005 opens with backfillable data, and retire the gate-worker whose verdict has had zero consumers since the phase-117 finding.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-420 | cause-class column on effort.db retry rows (D1) | stub |
| INFRA-421 | silent-deviation marking on verdict records (D2) | stub |
| INFRA-422 | retire gate-worker: agent, dispatch entry, narrative status (phase-117 livelock) | stub |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-<assigned at sequencing> Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?
- [ ] dark feature — does any new role, flag, event type, or surface lack a narrative and a landing spot?

— developer fills in after phase completion —
