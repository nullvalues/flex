---
era: "003"
phase_class: production
---

# project — Phase 104: Recording and checkpoint correctness

← [Phase 103: Worktree and story-stub friction remediation (CER-090, CER-092)](phase-103.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Make attempt recording, effort-DB integrity, and the checkpoint sequence provably correct before the fleet campaign and before any further checkpoints run. Picks up open Do Later findings CER-071/073/074/076/077/082/088/089/091/016.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-263 | Fix record-attempt click alias to forward the full option set (CER-071, CER-073) | complete |
| INFRA-264 | Fix the four async effort-recording defects from the INFRA-259 smoke test (CER-091) | complete |
| INFRA-265 | Thread an explicit phase key through record-checkpoint-step and checkpoint-tag (CER-077) | complete |
| INFRA-266 | Effort-DB hardening: bounded pending_reconcilable scan, output_file containment, path-guard parity (CER-088, CER-089, CER-016) | complete |
| INFRA-267 | Stage docs/eras in commit paths, era-ledger status updates, backfill phases 96-103 (CER-082) | complete |
| INFRA-268 | Document the one-iteration-per-story contract, retire the dead spawn-reviewer action, fix stub-gate quoted-text false positive (CER-074, CER-076) | complete |

## Ordering

Stories touching `flex_build.py` (INFRA-263, INFRA-265, INFRA-267) and stories touching
the record_attempt/effort-DB surface (INFRA-264, INFRA-266) are serialized within their
group to avoid worktree merge conflicts. Build order: 263, 264, 265, 266, 267, 268.
INFRA-268 is independent and may slot anywhere.

## Checkpoint proves

cp-104 is self-validating: `checkpoint-tag` marks *phase 104* complete via the explicit
phase key (INFRA-265's fix, not a re-derived guess), the era-003 ledger row flips status
(INFRA-267), and every attempt spawned during this phase produced a correct effort.db
row through the fixed alias — outcomes recorded, no permanent-pending residue, no
counter resurrection (INFRA-264/266).

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-104 Cold-eyes checklist

— developer fills in after phase completion —
