---
era: "005"
phase_class: production
---

# project — Phase 122: shadow-reviewer write capability (CER-164) and shadow_review enablement

**Parent phase:** Phase 121 — sync-all to-030 fold-in and fleet stale-hook remediation

← [Phase 121: sync-all to-030 fold-in and fleet stale-hook remediation](phase-121.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Fix CER-164 — restore the shadow-reviewer role's ability to read git state and write .pairmode-suggestions.md — then set shadow_review=concurrent in CLAUDE.build.md so flex's own build loop dogfoods the concurrent shadow-reviewer it built in INFRA-358/359.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-388 | Restore shadow-reviewer write capability (CER-164) and enable shadow_review=concurrent | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-122 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
