---
era: "004"
phase_class: production
---

# project — Phase 113: Shared blockers: frontmatter, resolver evidence, recording determinism

← [Phase 112: Campaign unblockers: worker result-grammar reconciliation, CER-guard placeholder fix, snapshot write targeting](phase-112.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Close the parsing, resolver-evidence, and spawn-recording defects both rails stand on: flow-style frontmatter that half-creates worktrees, cross-referenced story IDs read as build evidence, async spawn outcomes recoverable only by an unreachable timer, unvalidated JSON BUILD outcomes, and duplicate-hook false positives — plus the fleet-propagation defect (sync cannot deliver canon shrinkage) that every later canon rewrite in this era depends on (AG-1, `docs/closeout-agreements-20260729.md`). Nothing in phases 114–116 is trustworthy until these land; four stories gate the in-flight phase-106 campaign, and INFRA-311 gates phase-106's disposition (AG-3).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-296 | Flow-style frontmatter sequences: parse or refuse; never leave a half-created worktree | complete |
| INFRA-297 | Scope commit build-evidence to the commit's own story; shared escaped-pipe table-split helper | complete |
| INFRA-298 | Deterministic spawn completion: SubagentStop relay, quiescence demoted to backstop | complete |
| INFRA-299 | Recording data integrity: enum-validate JSON BUILD outcomes; document attempts.phase and the acknowledged_at misnomer | complete |
| INFRA-300 | Duplicate-hook detection precision: matcher-aware keying and actionable classification | complete |
| INFRA-311 | Sync canon-shrink propagation; audit flags EXTRA inside canonical files; SCAFFOLD_FILES parity test | complete |
| INFRA-320 | Mid-build scope relief: standing shared surfaces, audited permissions-widen, scope-implication preflight — hard block preserved | complete |

INFRA-320 was pulled from **CER-128** (operator-flagged 2026-07-29, "scope friction") as an operator-directed mid-phase addition after the era-004 closeout agreements were applied; see `docs/closeout-agreements-20260729.md` § AG-9.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-113 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
