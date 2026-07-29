---
era: "004"
phase_class: production
---

# project — Phase 115: Observability closeout: API hardening, payload guards, rollup hygiene, 0.3.1

← [Phase 114: Build-loop closeout: worktrees, scaffolding, migration tooling, doc currency](phase-114.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Harden the observability companion's shared entry points against non-loopback exposure, make the vendored-payload guards honest and self-maintaining, remove non-build noise from effort rollups, execute the backlog truth pass and phase-107 supersession, and ship version 0.3.1.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-306 | Observability API: loopback-honest CORS and abs_path disclosure gating | draft |
| INFRA-307 | Vendored payload guards: dot-claude tolerance pattern; delete test_extension.node; enumerate native binaries | draft |
| INFRA-308 | Plugin-manifest skill guard: glob-derived expectations with anti-vacuity floor | draft |
| INFRA-309 | Rollup hygiene: shared NON_BUILD_ROLES exclusion across Python and TS read paths | draft |
| INFRA-310 | Backlog truth pass, phase-107 supersession, zero-open audit, and the 0.3.1 version record | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-115 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
