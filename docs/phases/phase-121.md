---
era: "005"
phase_class: production
---

# project — Phase 121: sync-all to-030 fold-in and fleet stale-hook remediation

**Parent phase:** Phase 120 — CER-159 hook-firing fix: marketplace install migration, era-004 stable close

← [Phase 120: CER-159 hook-firing fix: marketplace install migration, era-004 stable close](phase-120.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fold the to-030 stale-flex-harness hook repair into sync-all as an idempotent, order-independent step, then apply it across the 13 remaining fleet repos (Repo-A, Repo-B, Repo-C, Repo-D, Repo-F, Repo-G, Repo-H, Repo-I, Repo-J, Repo-K, Repo-L, Repo-M, Repo-N) still carrying duplicate/stale settings.json hook entries per fleet_discovery.py's 2026-08-04 scan.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-386 | Fold to-030 stale-flex-harness repair into sync-all as a fifth step | complete |
| INFRA-387 | Apply to-030 stale-hook repair across remaining fleet repos | deferred |
| INFRA-389 | Fix bootstrap.py plugin-sourced-skip branches bypassing A7 stale-hook eviction (CER-169) | complete |
| INFRA-390 | Trim CHANGELOG.md under the 200-line test gate | complete |

## Deferred stories

- **INFRA-387** — Apply to-030 stale-hook repair across remaining fleet repos.
  Deferred: all 13 target fleet repos had dirty working trees at every build
  attempt (unrelated operator work in progress), and the story's Ensures
  correctly forbid writing to a dirty tree — so the fleet-wide re-scan
  Ensures item could not be satisfied through no fault of the mechanism
  itself (confirmed working via the two already-clean exclusion repos).
  Resumes once the operator has committed/stashed the fleet repos' working
  trees, as a new story in a new phase per the phase-continuity resume
  convention (this phase is closing checkpointed regardless).

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-121 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
