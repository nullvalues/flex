---
era: "003"
phase_class: production
---

# flex — Phase 96: Build-loop revert safety and worktree-per-cycle isolation

← [Phase 95: Wire context-budget-gate hooks (UserPromptSubmit, SessionStart, PostToolUse Task/Agent) into downstream bootstrap registration](phase-95.md)

**Parent phase:** [HARNESS016-main](phase-HARNESS016-main.md), paused
2026-07-21 after the RELEASE-022 review incident (reviewer FAIL-path revert
deleted two untracked, unrelated directories). HARNESS016-main left behind
RELEASE-022 (needs a retry) plus the remaining fleet-migration and fold-gate
stories (RELEASE-024/026-040, RELEASE-015-018), all marked `deferred` in its
Stories table — see its `## Deferred stories` section. This phase builds the
safety fix; HARNESS016-main resumes afterward.

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

A reviewer/loop-breaker revert (git checkout . && git clean -fd) currently sweeps the whole working tree, not just the story's declared scope -- RELEASE-022's FAIL revert deleted two untracked directories (docs/stories/CORE/, docs/stories/TEST/) that had nothing to do with that story, recovered only because they were empty and mirrored in a sibling worktree. Scope every builder/reviewer/loop-breaker revert to the story's declared primary_files/touches instead of a blanket tree-wide checkout+clean, and add per-build-cycle git worktree isolation so concurrent story builds (now or in a future parallel build loop) cannot touch each other's files even before any revert runs. This is defense-in-depth: worktree isolation prevents cross-story damage; scoped revert prevents same-worktree collateral damage within one story's own build cycle.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-223 | Scope reviewer FAIL-path revert to the story's declared primary_files/touches instead of a blanket git checkout . && git clean -fd | complete |
| INFRA-224 | Per-build-cycle git worktree isolation for builder/reviewer story cycles | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-96 Cold-eyes checklist

- **checkpoint-security** — PASS. No CRITICAL/HIGH findings; no `hooks/` files touched; worktree/branch names regex-validated before use in subprocess argv (no `shell=True`, no injection/traversal surface); no credential exposure.
- **checkpoint-intent** — ALIGNED. Both stories built exactly to their `## Ensures`; the HARNESS016-main pause/fork was handled per the phase-continuity policy (Deferred stories section, status flips, Parent phase line).
- **checkpoint-docs** — PASS (after two fix cycles). First pass FAILed on the same class of gap as Phase 95's checkpoint: no explicit Phase 96 reference in `docs/architecture.md`, no `CHANGELOG.md` entry — both fixed (commit `a5dd389`). Second pass FAILed on unrelated pre-existing backlog debt: CER-045's `SUPERSEDED` note claimed a still-live symptom, but its successor CER-054 had since been `RESOLVED` (cp-HARNESS007-main) — closed out the chain (commit `ba309bf`). Third pass PASSed clean.
- **INFRA-224 review incident** — attempt 1's reviewer FAILed on `docs/architecture.md` staleness (legitimate finding) but reported having reverted without the revert command actually executing (tool-call gap, same pattern noted below); the orchestrator ran the scoped revert manually per INFRA-223's own new convention, confirming it works correctly end-to-end (declared-scope files reverted, untracked `docs/stories/CORE/TEST` left untouched). Attempt 2 (opus, prompted-upgrade) fixed the finding and reviewer PASS this time did execute its commit, verified via `git log`.
- **Reviewer self-report reliability** — three separate reviewer invocations this build cycle (RELEASE-022 revert, INFRA-224 attempt 1 "revert") described git actions (commit or revert) in their JSON report that had not actually run when checked against `git log`/`git status`. Every reviewer result in this session was independently verified against actual repo state before being trusted; this is a live gap worth a future story (a mechanical post-review `git status`/`git log` check the orchestrator always runs, already the de facto practice this session) rather than continuing to catch it ad hoc.
