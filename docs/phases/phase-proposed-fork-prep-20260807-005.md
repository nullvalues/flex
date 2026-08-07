---
era: "004"
phase_class: production
status: proposed
sequenced: false
---

# project — Proposed phase (fork-prep): Fork prep: expunge gate, 0.4.1 tag, fresh-history fork

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
      Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Extend the CER-172/173 de-identification to vocabulary — remove fleet framing, fleet-snapshot.md, and fleet_discovery.py from the tree — pass a zero-match grep gate (fleet, proving-repo names, private remotes) and a green dark-feature scan, tag 0.4.1, and initialize the fresh-history fork from the expunged tree (ruling 12).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-425 | vocabulary expunge: fleet code paths, fleet-snapshot.md, framing in docs | stub |
| INFRA-426 | grep gate: zero matches for fleet terms, proving-repo names, private remotes | stub |
| INFRA-427 | 0.4.1 tag and fresh-history fork runbook (dark-feature scan green is a tag precondition) | stub |

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
