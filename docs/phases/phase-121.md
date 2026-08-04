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
Fold the to-030 stale-flex-harness hook repair into sync-all as an idempotent, order-independent step, then apply it across the 13 remaining fleet repos (coherra, meander, caddy, forqsite.help, halfhorse, cora, aab, asp, lumin, pokus, radar, rockue, stackabid) still carrying duplicate/stale settings.json hook entries per fleet_discovery.py's 2026-08-04 scan.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-386 | Fold to-030 stale-flex-harness repair into sync-all as a fifth step | draft |
| INFRA-387 | Apply to-030 stale-hook repair across remaining fleet repos | draft |

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
