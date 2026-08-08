---
era: "005"
phase_class: production
---

# project — Phase 146: State-lifecycle relief: doctor-state, session-start orphan detection, gate-verdict invalidation

← [Phase 145: Retire flex-harness release channel; merge fold-prep to main](phase-145.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close CER-236..239 (F1-F4): a unified doctor-state command that repairs orphaned stamps/worktrees/permissions artifacts and cross-checks frontmatter against the phase table, session-start orphan detection surfacing the same class of drift proactively, and gate-verdict invalidation when a story's spec is revised after a verdict was recorded.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-442 | doctor-state command: repair orphaned stamps, worktrees, permissions artifacts; frontmatter/table cross-check | complete |
| INFRA-443 | Session-start orphan detection surfacing doctor-state drift | complete |
| INFRA-444 | Invalidate recorded gate verdict when story spec is revised after recording | complete |
| INFRA-445 | diagnose_state scoping fix: exclude closed-phase/historical orphans, validate state.json-derived story IDs, bound SessionStart scan cost | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-146 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
