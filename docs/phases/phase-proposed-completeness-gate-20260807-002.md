---
era: "004"
phase_class: production
status: proposed
sequenced: false
---

# project — Proposed phase (completeness-gate): Completeness gate: landing-spot rule and dark-feature scan

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
      Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Trap the failure mode that shipped the shadow-reviewer narrative-less and default-off: intent review gains the landing-spot rule (no new role, flag, event type, or persistent surface without a same-phase narrative and a discovery surface), a mechanical dark-feature scan enforces it at every checkpoint, and shadow_review itself is surfaced at bootstrap — 0.4.1 must pass its own gate before it ships.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-434 | landing-spot rule in the intent-reviewer procedure (INFRA-356 extension) | stub |
| INFRA-435 | dark-feature scan: agents vs narratives, default-off flags vs surfacing, producers vs consumers | stub |
| INFRA-436 | surface shadow_review: bootstrap prompt, visible default in scaffolded CLAUDE.build.md | stub |

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
