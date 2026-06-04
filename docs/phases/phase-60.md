# project — Phase 60: Checkpoint report intelligence — phase-key fix and next-phase detection

← [Phase 59: context_budget.py silent-fail edge closure (CER-040, CER-041)](phase-59.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Replace two brittle placeholders in the checkpoint report template. First: rename [CP-N] to [phase-id] so suffix-keyed phases (e.g. RD077-main) render correctly. Second: replace the [N+1] arithmetic in both the context-health advisory and the closing prompt with a new flex_build.py next-phase CLI that reads the index and returns the next row's key — enabling the closing prompt to branch between 'Build Phase [ID]' when a next phase is already spec'd and 'spec next phase [intent]' when none exists. Both the live CLAUDE.build.md and the canonical CLAUDE.build.md.j2 template receive the update; forqsite sync follows the same AC5 pattern as INFRA-149.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-152 | `flex_build.py next-phase --after [phase-id]` — index-based next-phase lookup | planned |
| INFRA-153 | Checkpoint report — fix `[CP-N]` / `[N+1]` placeholders and add next-phase branching | planned |

**Story dependency:** INFRA-153 depends on the `next-phase` CLI introduced in INFRA-152. Build INFRA-152 first.

## Schema delivery

No new persistent schema objects.

| Object | Management surface | Exception |
|---|---|---|
| — | — | No new tables |

---

### CP-60 Cold-eyes checklist

— developer fills in after phase completion —
