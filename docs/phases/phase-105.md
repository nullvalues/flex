---
era: "003"
phase_class: production
---

# project — Phase 105: Campaign preflight: hooks, discovery, scope-guard, channel canon

← [Phase 109: Single-orchestrator parallel build concurrency](phase-109.md) — build-order predecessor (index-ordered; numbering is non-sequential)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
De-risk the fleet campaign: hook-registration dedupe, discovery accuracy, scope-guard readiness, context-state hygiene, and canonize /mnt/work/flex-harness as the permanent release channel. Closes CER-081/058/059/080/087/040/041.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-269 | Hook-registration dedupe with audit subcommand and DP8 duplicate-hook check (CER-081) | complete |
| INFRA-270 | Audit registered_projects writers and fix Signal-1 false negatives (CER-058, CER-059) | complete |
| INFRA-271 | Scope-guard campaign readiness: stale current_story clear, idle-checkout tolerance, harness-owned write allow-list (CER-080, CER-087) | complete |
| INFRA-272 | Context-state hygiene: surface context_budget fail-open, clear token-staleness residue (CER-040, CER-041) | complete |
| RELEASE-062 | Canonize the permanent release channel: retire RELEASE-061, rewrite RELEASE-060, amend runbook final-fold steps | complete |

## Ordering

INFRA-269 before INFRA-270 (both touch `fleet_discovery.py`). INFRA-271 must land
before the phase ends — Phase 106's execution model depends on it. INFRA-272 and
RELEASE-062 are independent.

## Checkpoint proves

A fresh DP8 discovery run over the whole fleet reports accurate per-project migration
status; zero duplicate hook blocks on the 8 already-migrated projects; Signal-1 answers
match reality; runbook, architecture.md § Release channel, and the RELEASE-060/061
story dispositions are internally consistent about the permanent channel; flex's own
worktree and harness-owned out-of-repo writes (memory, scratchpad, plan files) are
unblocked.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-105 Cold-eyes checklist

Filled by the orchestrator at cp-105 (2026-07-27).

- **CER-081 closed (INFRA-269):** registrar dedupe (`_find_all_entries_by_command_basename`,
  `_prune_stale_hook_entries`) wired into both bootstrap registrars so stale same-basename
  sibling hook entries are pruned on every write; `pairmode_sync.py audit-hooks`
  (dry-run/`--apply`) reuses the same prune helper; `fleet_discovery.py` surfaces a
  read-only `duplicate_hooks` signal in `discover()`/`--json`/text/snapshot.
- **CER-058/059 closed (INFRA-270):** single-writer invariant test and provenance sidecar
  (`source`/`registered_at`, `audit-projects` CLI) for `registered_projects`; Signal-1
  absence classifier (`signal1_absence_reason`, four reason codes) threaded through
  discovery CLI and snapshot; CER-059(b)/(c) verified as already-correct.
- **CER-080/087 closed (INFRA-271):** scope-guard staleness ageing
  (`STATE_STORY_MAX_AGE_HOURS`, `entry_is_fresh`, `stale` resolution source) plus
  harness-owned out-of-root allow-list (`harness_owned_prefixes`/`_out_of_root_decision`);
  `flex_build.py clear-stale-stories` operator CLI. One justified builder self-expansion
  (collateral fixture fix in `test_pre_tool_use_hook.py`, verified non-reproducing on
  clean HEAD) upheld at review.
- **CER-040/041 closed (INFRA-272):** fail-open stderr signalling
  (`_FAIL_OPEN_PREFIX`/`_warn_fail_open`/`_staleness_unverifiable_reason`) on all
  context-budget pass-through branches and the hook's blanket except; dead CER-041 TTL
  removed end-to-end; observability route gained `gate_stale`/`DISPLAY_STALE_SECONDS`.
  `hooks/pre_tool_use.py` touch was declared in `touches` and passed the hook-performance
  check (stderr print on exception path only).
- **RELEASE-062 (channel canon, 3 attempts):** spec-writer returned `revised` (stub had
  no `primary_files`, empty `touches`; operator populated). Attempt 1 (haiku) missed
  RELEASE-018.md/phase-HARNESS016-main.md entirely (E3); attempt 2 (haiku) annotated
  RELEASE-018 but left its live teardown directive intact; attempt 3 (sonnet, manual
  escalation) neutralized the body as historical-record blockquotes — E3 grep now clean,
  every remaining teardown hit sits inside a superseded/historical note.
- **Gates:** security PASS (0 findings at any severity). Intent ALIGNED (all five stories
  trace to spec; seven CERs closed with matching backlog annotations). Docs PASS on second
  run (first run failed on missing CHANGELOG entry, added at checkpoint as
  `docs(phase-105)` — same pattern as cp-109).
- **Known process gaps this checkpoint:** story statuses again flipped post-merge by the
  orchestrator (same as cp-104/cp-109); checkpoint-report again printed "no attempts
  recorded" for the whole phase (CER-101, still open); NEW: the FAIL escalation ladder
  never engaged across RELEASE-062's two reviewer FAILs — attempt counter never bumped,
  resolver kept prescribing haiku attempt 1 — filed as **CER-102** (likely CER-101-adjacent).
- **New backlog from this phase:** CER-102 (dead FAIL-escalation ladder in the live loop).
