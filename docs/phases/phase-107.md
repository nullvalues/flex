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
| INFRA-273 | Doc and procedure drift sweep (CER-078, CER-079, CER-084, CER-085, CER-086, CER-035, CER-014, CER-065b) | backlog |
| INFRA-274 | Legacy quick-fix sweep: pairmode_status path, story validator vs story_new, rail traversal, split-pipe audit (CER-012, CER-006, CER-010, CER-069) | backlog |
| INFRA-275 | Worktree and vendoring residue: guard-test .claude tolerance, test_extension.node disposition, worktree env provisioning (CER-093, CER-094, CER-075) | backlog |
| INFRA-276 | Verify-and-close pass: CER-070, CER-062a, CER-009, CER-031, plus file the two cp-103 quoting advisories | backlog |
| INFRA-277 | Do Never routing of the legacy tail with per-row reasons, duplicate CER-066 repair, zero-unresolved audit | backlog |

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

## Superseded

**2026-08-01 (INFRA-310, Phase 116, AG-3).** This phase's scope — draining
`docs/cer/backlog.md` to zero open findings — was re-done on merits across
era 004's phases 113–116, not resumed here. The classification changed
materially, not just the numbering: e.g. **CER-069** (this phase's
`INFRA-274` bundle labeled it a "legacy quick-fix") was re-classified during
era-004 spec work as a shared blocker and drained by **INFRA-297** (Phase
113) instead — a different quadrant of urgency than this phase's own framing
assumed. The doc sweep (INFRA-273's CER-078/079/084/085/086/035/014/065b)
and the code sweeps (INFRA-274/275) were also split apart rather than kept
as one bundle, because era 004's stories were scoped file-by-file rather
than by CER-cluster.

Each of the five stubs below is superseded by named era-004 work; none of
this phase's content or Stories table above is deleted or rewritten — it
remains the historical planning record.

- **INFRA-273** (doc/procedure drift, CER-078/079/084/085/086/035/014/065b)
  — CER-078/079/084/085/086/065b absorbed by **INFRA-305** (Phase 114);
  CER-035/014 verified provably obsolete and annotated by **INFRA-310**
  (this story, Ensures 1).
- **INFRA-274** (legacy quick-fix: CER-012/006/010/069) — CER-069 already
  `RESOLVED` (Phase 113 / **INFRA-297**); CER-006/010/012 verified provably
  obsolete and annotated by **INFRA-310** (Ensures 1).
- **INFRA-275** (worktree/vendoring: CER-093/094/075) — CER-075/070 owned by
  **INFRA-302** (Phase 114, worktree provisioning); CER-093/094 owned by
  **INFRA-307** (Phase 115, vendored-payload guards).
- **INFRA-276** (verify-and-close: CER-070/062a/009/031) — CER-070 retained
  exclusively for **INFRA-302** (do not double-annotate, Note A); CER-062
  already resolved (Phase 87 / **INFRA-197**); CER-009 verified provably
  obsolete and annotated by **INFRA-310** (Ensures 1); CER-031 retained via
  **INFRA-310** Ensures 4 (`BACKLOG-RETAIN`).
- **INFRA-277** (Do Never routing, duplicate CER-066 repair, zero-unresolved
  audit) — the duplicate-CER map is owned by **INFRA-310** Requires 3, and
  the zero-open enumeration by **INFRA-310** Ensures 6 (this story, Phase
  116). No second, differently-worded zero-unresolved predicate was built.

Nothing was deleted. The Goal, Stories table and Ordering sections above are
left intact as the historical record.

---

### CP-107 Cold-eyes checklist

— developer fills in after phase completion —
