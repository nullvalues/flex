---
era: "005"
phase_class: production
---

# project — Phase 145: Retire flex-harness release channel; merge fold-prep to main

← [Phase 144: Harden title/path serialization at two live writer gaps (CER-221/222)](phase-144.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Merge fold-prep into main (preserving INFRA-332's 3 agent files), retire the flex-harness release channel in favor of the marketplace-cache install, repoint flex's own build loop at it, and dispose of the flex-harness clone/branches.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-441 | Repoint flex build loop at marketplace install; retire release-channel docs | complete |
| INFRA-440 | Merge fold-prep to main; disposition of flex-harness clone and stale remote branches | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-145 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
