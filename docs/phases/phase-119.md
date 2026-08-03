---
era: "004"
phase_class: production
---

# project — Phase 119: Spec precision (frozen exemplar) and fundamental-doc trim

← [Phase 118: Narrative of Record: propagation, spec-writer/intent-reviewer integration, and mid-build steering](phase-118.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

**Status: PROPOSED, NOT SEQUENCED.** This phase doc and its stories are a spec only. Nothing in
it has been scheduled — no `state.json` active-phase pointer has been set, and no build
invocation should treat this as the phase to build next after Phase 118 checkpoints. Operator
will set the active phase and say "Build Phase 119" manually when ready. Do not auto-advance into
this phase from Phase 118's checkpoint sequence.

## Goal

Follow up on Phase 118's spec-volume remediation (INFRA-357) with two independent, narrowly
scoped fixes surfaced by a two-round third-party analysis (session 2026-08-03, requested
independently of the Devin/Windsurf cold-eyes reviews already cited in INFRA-357): (1) replace
the spec-writer's "one recent story" exemplar input with a frozen reference exemplar, since a
moving exemplar is structurally self-reinforcing regardless of INFRA-357's brevity instruction;
and (2) trim four specific, already-identified pieces of dead or duplicated content out of this
project's own fundamental docs (`docs/ideology.md`, `docs/architecture.md`,
`skills/pairmode/SKILL.md`).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-363 | Freeze the spec-writer's format exemplar; correct INFRA-357's attempt-count claim | draft |
| INFRA-364 | Trim dead/duplicated content from ideology.md, architecture.md, and pairmode SKILL.md | draft |

## Ordering

Both stories are independent of each other and of the rest of Phase 118 — neither touches a file
the other touches, and neither depends on Phase 118's Cluster A/B/C work landing first. Either can
build in any order, or in parallel, whenever the operator schedules this phase.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

Neither story introduces a persistent schema object — n/a.

---

### CP-119 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
