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

Filled by the orchestrator at cp-104 (2026-07-26).

- **CER-071/073 closed (INFRA-263):** the `flex_build.py record-attempt` click
  alias now forwards the full option set (ignore_unknown_options + variadic
  UNPROCESSED pass-through, `--help` included); the exact CER-073 reproducer
  and a full-flag round trip are pinned in
  `test_flex_build_record_attempt_alias.py`.
- **CER-091 closed (INFRA-264):** all four async effort-recording defects —
  ALIGNED verdict recognition, atomic tokens+outcome reconciliation, the
  nine-reason `classify_pending_reason` diagnostic surfaced via
  `pairmode_effort.py pending` (plus age-gated quiescent retirement), and the
  `_story_accepts_late_bump` guard against counter resurrection — with an
  append-only recording trace (`.companion/effort_recording.log`) and an
  explicit `reconcile` CLI trigger.
- **CER-077 closed (INFRA-265):** `record-checkpoint-step`/`checkpoint-tag`
  take an explicit `--phase-key` resolved through a strict precedence chain;
  double-`active` index rows now raise `AmbiguousActivePhaseError` at every
  CLI boundary (exit 2, no traceback) instead of silently mis-stamping.
- **CER-088/089/016 closed (INFRA-266):** partial index on the pending
  predicate (planner-verified), 14-day sweep age bound, spawn-output
  containment (`_contained_spawn_output`) on `read_completed_spawn`, and
  `--db-path` escape rejection in both CLI writers.
- **CER-082 closed (INFRA-267):** era phase-ledger revived end to end —
  qualified `## Phases` heading match, status flip wired into
  `mark-phase-complete` and `checkpoint-tag`, `docs/eras/` staged in both
  harness commit paths, era-003 ledger backfilled for phases 96–108.
- **CER-074/076 closed (INFRA-268):** one-iteration-per-story contract
  documented in the harness, template, and architecture; `SPAWN_REVIEWER`
  marked orchestrator-dispatched-only with a six-shape never-emits regression
  test; stub gate masks fenced/inline code regions before the delegation
  search.
- **Gates:** security PASS (0 CRITICAL/HIGH; MEDIUM — `_stream_spawn_output`
  called on raw `output_file` in `classify_pending_reason`/quiescent sweep,
  bypassing the INFRA-266 containment guard, filed as CER-099; INFORMATIONAL —
  stale thin-delegation exception list in the security-auditor procedure
  skill, filed as CER-100). Intent ALIGNED (all six stories trace
  line-for-line to spec; three builder deviations — stale check-index
  baseline, deliberate phase-109 ledger exclusion, `## Phases` wording
  substitution — adjudicated legitimate at review). Docs gate: see
  checkpoint record.
- **New backlog from this phase:** CER-099 (containment parity), CER-100
  (auditor-skill exception list).
- **Schema delivery:** no new persistent schema objects introduced (table
  intentionally empty; `effort_recording.log` is an append-only size-capped
  diagnostic file, not a schema object).
