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

- **checkpoint-security** — PASS, first run, no findings at any severity.
  `hooks/` unchanged in the phase diff; INFRA-257's `COUNT(*)` derivation
  verified indexed (`idx_attempts_story`), bounded, try/except-wrapped, and
  behind the `effort_tracking` early return; all new SQL uses bound
  parameters.
- **checkpoint-intent** — ALIGNED, both stories, no pivots. Touched files are
  exactly the union of declared `primary_files`/`touches` plus phase docs.
  "Hooks are thin relays only" explicitly addressed by INFRA-257's bounded
  one-query design; no ideology drift.
- **checkpoint-docs** — PASS after a pre-tag docs commit adding the missing
  Phase 101 CHANGELOG entry and filling this checklist. architecture.md
  verified accurate against the shipped code (checkpoint-report scoping,
  `next_attempt_number`, call-site derivation); no stale lifetime-only or
  always-1 references remain; no new CERs from this phase.
- **Provenance:** both stories filed from the operator's post-cp100 review of
  the misleading "builder: 19 attempt(s)" rollup (db-lifetime count read as
  phase cost) and the all-1s `attempt_number` rows (INFRA-247/248 shape);
  operator directed fixing both before continuing the fleet rollout.
