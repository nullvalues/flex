---
era: "003"
phase_class: production
---

# project — Phase 107: CER backlog drain to zero

← [Phase 106: Fleet migration campaign (driven from flex)](phase-106.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Every remaining CER backlog row gets an honest disposition — fixed, verified-closed, or formally routed to Do Never with a per-row reason — leaving zero open findings.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-273 | Doc and procedure drift sweep (CER-078, CER-079, CER-084, CER-085, CER-086, CER-035, CER-014, CER-065b) | draft |
| INFRA-274 | Legacy quick-fix sweep: pairmode_status path, story validator vs story_new, rail traversal, split-pipe audit (CER-012, CER-006, CER-010, CER-069) | draft |
| INFRA-275 | Worktree and vendoring residue: guard-test .claude tolerance, test_extension.node disposition, worktree env provisioning (CER-093, CER-094, CER-075) | draft |
| INFRA-276 | Verify-and-close pass: CER-070, CER-062a, CER-009, CER-031, plus file the two cp-103 quoting advisories | draft |
| INFRA-277 | Do Never routing of the legacy tail with per-row reasons, duplicate CER-066 repair, zero-unresolved audit | draft |

## Ordering

INFRA-273/274/275 in any order (disjoint files). INFRA-276 after the fix stories.
INFRA-277 strictly last — it sweeps anything the fix stories descoped.

## Checkpoint proves

`docs/cer/backlog.md` contains zero rows without a resolution or rejection note; the
Do Now, Do Later, and Do Much Later quadrants hold no open findings; the Do Never
section carries a per-row reason for everything routed there.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-107 Cold-eyes checklist

— developer fills in after phase completion —
