---
era: "004"
phase_class: production
status: proposed
sequenced: false
---

# project — Proposed phase (final-sync-all): Final proving-cycle sync-all (INFRA-387 resume)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
      Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Resume the deferred INFRA-387 stale-hook repair across the 13 proving repos now that their working trees are committed, then run the final sync-all so every proving project is clean or explicitly pinned at 0.3.x before the fork.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-423 | apply to-030 stale-hook repair across remaining proving repos (resumes INFRA-387) | stub |
| INFRA-424 | final sync-all with version-consistency scan; record pinned-at-0.3.x projects | stub |

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
