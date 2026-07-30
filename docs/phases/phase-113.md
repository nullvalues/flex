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

- [x] written-never-read — `widenings` field in BUILD-RESULT (builder procedure) has no code/orchestrator consumer and is absent from worker_result.py's allowed set (security-audit MEDIUM #3; the real audit record — the story-file `## Scope widenings` table — does have a reviewer-procedure consumer). INFRA-311's attempt-2 `AuditItem.retired_by`/`AuditResult.finding_count` were caught in review and dropped; attempt 3 stores no fields. INFRA-298 gave `attempts.agent_id` its first production reader.
- [x] required-never-written — none found: reconcile_one's guard reads only columns every writer produces; `standing_paths`/`story_phase` artifact keys are written by generate_permissions_artifact and check_path unions live computation for older artifacts (no migration dependency).
- [x] duplicate state — RETIRED_SECTIONS is single-sourced in sync.py (audit lazy-imports it); RECOGNISED_BUILD_OUTCOMES deliberately mirrors worker_result.py's enum with a mirror-and-why comment and a test pinning both (accepted mirror, not silent duplication). Attempt counter remains hook-written/orchestrator-read (this session: hook recording did not fire for async spawns — CER-114 confirmed live; manually reconciled via record-attempt/write-attempt-count; fixed going forward by INFRA-298's relay).
- [x] half-implementation — sync.py's new `--dry-run` is unreachable from the sync-all wrapper (pairmode_sync.py hard-skip) — filed as CER-133(6) with the SKILL.md stale claims (5), gated to the pre-fleet-campaign pass. CER-131 filed for relay-path rejections not logging to effort_recording.log (INFRA-298/299 same-phase sequencing seam).

— filled by orchestrator at CP-113, 2026-07-29 —
