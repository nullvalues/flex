---
era: "003"
---

# flex — Phase 92: Fix cross-phase status leakage in story_update.py

← [Phase 91: Harden sync-agents body-merge against silent duplication/corruption](phase-91.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

update_phase_story_status in skills/pairmode/scripts/story_update.py scans every docs/phases/*.md file and flips the status column of any Stories-table row whose bare first column equals story_id, with zero phase/rail disambiguation. When two phases each carry a row for the same bare story ID (demonstrated: CER-063 — INFRA-203 collides between main's phase 91 and the unmerged fold-prep branch's HARNESS011-main), a single --status call silently corrupts the unrelated phase's row. This phase scopes the update to only the phase(s) named in the story's own phase: frontmatter field, resolving both exact and suffixed phase-filename forms (mirroring story_new.py's _append_to_phase glob pattern), falling back to the current whole-glob scan only for legacy stories with no phase: field. Adds regression tests reproducing the exact cross-phase leak.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-204 | Scope `update_phase_story_status` to the story's declared `phase:` frontmatter (suffix-aware), fall back to whole-glob only for legacy phase-less stories, with cross-phase-leakage regression tests | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-92 Cold-eyes checklist

— developer fills in after phase completion —
