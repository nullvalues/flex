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
| INFRA-440 | Merge fold-prep to main; disposition of flex-harness clone and stale remote branches | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-145 Cold-eyes checklist

- [x] written-never-read — checked, and one was caught: docs/architecture.md initially described pairmode_scripts_dir as resolving to the installed plugin cache, a directory nothing in this phase wrote to. Fixed same-phase (67dcf734) to describe the actual writer/reader pair (the marketplace source clone, advanced by manual git checkout).
- [x] required-never-written — no read path in this phase depends on a value with no writer; the marketplace-cache advancement is documented as a manual step, not silently assumed automatic.
- [x] duplicate state — no: pairmode_scripts_dir has exactly one declaration site (CLAUDE.build.md) after this phase; the old flex-harness worktree path is gone, not duplicated.
- [x] half-implementation — one caught and fixed: 9 rendered agent-shell fallback paths pointed at the now-deleted flex-harness directory after INFRA-440 removed it, before the checkpoint-security re-audit caught it and it was repointed (durable via the templates' existing {{ pairmode_scripts_dir }} parameterization). Two cosmetic residuals remain, filed as CER-241/CER-242 (Do Much Later, non-blocking).

— filled in by orchestrator at checkpoint (2026-08-07) —
