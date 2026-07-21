---
era: "003"
phase_class: production
---

# flex — Phase 96: Build-loop revert safety and worktree-per-cycle isolation

← [Phase 95: Wire context-budget-gate hooks (UserPromptSubmit, SessionStart, PostToolUse Task/Agent) into downstream bootstrap registration](phase-95.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

A reviewer/loop-breaker revert (git checkout . && git clean -fd) currently sweeps the whole working tree, not just the story's declared scope -- RELEASE-022's FAIL revert deleted two untracked directories (docs/stories/CORE/, docs/stories/TEST/) that had nothing to do with that story, recovered only because they were empty and mirrored in a sibling worktree. Scope every builder/reviewer/loop-breaker revert to the story's declared primary_files/touches instead of a blanket tree-wide checkout+clean, and add per-build-cycle git worktree isolation so concurrent story builds (now or in a future parallel build loop) cannot touch each other's files even before any revert runs. This is defense-in-depth: worktree isolation prevents cross-story damage; scoped revert prevents same-worktree collateral damage within one story's own build cycle.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-223 | Scope reviewer FAIL-path revert to the story's declared primary_files/touches instead of a blanket git checkout . && git clean -fd | planned |
| INFRA-224 | Per-build-cycle git worktree isolation for builder/reviewer story cycles | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-96 Cold-eyes checklist

— developer fills in after phase completion —
