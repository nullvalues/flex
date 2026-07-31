---
era: "004"
phase_class: production
---

# project — Phase 115: Observability closeout: API hardening, payload guards, rollup hygiene, functional validation

← [Phase 114: Build-loop closeout: worktrees, scaffolding, migration tooling, doc currency](phase-114.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Harden the observability companion's shared entry points against non-loopback exposure, make the vendored-payload guards honest and self-maintaining, remove non-build noise from effort rollups, and functionally validate the observability UI **and effort-recording data** — the era's stated beta deliverables — before anything is stamped. The backlog truth pass and the 0.3.1 record moved to phase 116 (AG-7, `docs/closeout-agreements-20260729.md`); this phase closes observability, it does not close the era.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-306 | Observability API: loopback-honest CORS and abs_path disclosure gating | complete |
| INFRA-307 | Vendored payload guards: dot-claude tolerance pattern; delete test_extension.node; enumerate native binaries | complete |
| INFRA-308 | Plugin-manifest skill guard: glob-derived expectations with anti-vacuity floor | complete |
| INFRA-309 | Rollup hygiene: shared NON_BUILD_ROLES exclusion across Python and TS read paths | complete |
| INFRA-312 | Observability UI functional validation: dogfood checklist over ≥2 registered repos plus a scoped TypeScript route-test runner | complete |
| INFRA-329 | Effort-db integrity audit on post-campaign fleet data — validate the forward-only L5 fixes against real rows | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-115 Cold-eyes checklist

- [x] written-never-read — does anything this phase persists have no reader?
      No. INFRA-306's CORS/abs_path gating, INFRA-307's native-binary inventory, and
      INFRA-309's `NON_BUILD_ROLES` exclusion are all consumed at read time by the
      code paths they were added for; INFRA-312/329's audit evidence is written into
      the story docs themselves, which is the intended durable record for an audit.
- [x] required-never-written — does any read path depend on a value no writer produces?
      No new read path introduced without a corresponding writer (checked by
      checkpoint-security and checkpoint-intent against server.ts/user.ts/effortDb.ts).
- [x] duplicate state — is any fact now stored twice with independent writers?
      Yes, one instance, deliberately reconciled: `NON_BUILD_ROLES` (INFRA-309) is
      defined once in Python (`effort_db.py`) and mirrored in TypeScript
      (`effortDb.ts`) since the two runtimes don't share a module system. A
      Python-parsed TS-parity test keeps the two lists in sync, so this is not an
      unguarded duplicate-state risk (see checkpoint-security PASS).
- [x] half-implementation — is any branch unreachable, or any producer without its
      consumer? No unreachable branches or orphaned producers found by either
      checkpoint-security or checkpoint-intent.
