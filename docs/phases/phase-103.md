---
era: "003"
---

# project — Phase 103: Worktree and story-stub friction remediation (CER-090, CER-092)

← [Phase 102: Effort-recording smoke test and harness release-channel fast-forward](phase-102.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Remove the two per-story friction defects phase 102 exposed: make the vendored observability node_modules complete under git so fresh story worktrees pass the UI build gate without manual payload rsync (CER-090), and fix story_new.py's stub frontmatter so a freshly-stubbed story no longer crashes create-story-worktree (CER-092).

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-261 | Track the full vendored observability node_modules payload — un-gitignore build//dist under vendored trees so fresh story worktrees pass the UI build gate (CER-090) | draft |
| INFRA-262 | Fix story_new.py stub frontmatter — emit parseable touches and invert the test pinning the trailing-comment bug (CER-092) | draft |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-103 Cold-eyes checklist

— developer fills in after phase completion —
