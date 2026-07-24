---
era: "003"
---

# project — Phase 101: Attempt recording and checkpoint reporting correctness

← [Phase 100: — Scope-guard fail-closed completion (CER-048 close-out)](phase-100.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Make effort.db attempt recording and checkpoint-time cost reporting truthful: the checkpoint rollup must be scoped to the phase it reports on, and repeated spawns for a story must record real attempt numbers.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-256 | Phase-scoped checkpoint cost rollup — filter effort rollup to the phase being checkpointed | complete |
| INFRA-257 | Truthful attempt_number recording — derive real attempt sequence for repeated same-story spawns | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-101 Cold-eyes checklist

— developer fills in after phase completion —
