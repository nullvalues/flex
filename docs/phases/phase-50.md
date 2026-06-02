# flex — Phase 50: Phase/story spec boundary policy

← [Phase 49: Observability SPA](phase-49.md)

## Goal

Establish a durable policy that prevents phase docs from absorbing story-level
implementation specs and codebase recon — the "boundary collapse" failure mode
diagnosed 2026-06-01. Three changes:

1. Update CER-030 with the correct root-cause framing (boundary collapse is the
   primary driver; template thinness is secondary).
2. Add an explicit boundary policy section to `CLAUDE.build.md.j2` (and its
   rendered copy `CLAUDE.build.md`) so every downstream project inherits the rule
   on next `pairmode sync`.
3. Add a one-line boundary reminder comment to `phase.md.j2` so every newly
   scaffolded phase doc carries the constraint visibly in its raw source.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-006 | Update CER-030 with boundary-collapse framing | complete |
| BUILD-007 | Add phase/story boundary policy to CLAUDE.build.md.j2 | complete |
| BUILD-008 | Add boundary reminder comment to phase.md.j2 | complete |

## Out of scope

- Template structural enrichment (type flags, exemplars, structural lint) — the
  original CER-030 "fix shape" items; they remain in Do Later.
- Downstream propagation via `pairmode sync` — operators run sync themselves
  after this ships; no story needed.
- Backfilling existing phase docs to remove embedded story specs — out of scope;
  the policy applies to new phase docs going forward.

Tag (on ship): `cp50-phase-story-boundary-policy`
