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

— developer fills in after phase completion —
