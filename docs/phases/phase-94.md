---
era: "003"
---

# flex — Phase 94: Fix escaped-pipe corruption in story_update.py phase-table row matching

← [Phase 93: Wire Edit/Write/Read matchers into pre_tool_use.py's PreToolUse registration](phase-93.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

_update_story_row_in_phase in skills/pairmode/scripts/story_update.py parses a Stories-table row with a naive stripped.split(pipe), which does not respect markdown-escaped pipes inside a cell. Any story title containing a literal escaped pipe (a real, likely occurrence in this INFRA rail, which frequently documents matcher strings like Edit-pipe-Write or Task-pipe-Agent -- see INFRA-205, INFRA-206) gets its title truncated at the first escaped pipe and the intended status value spliced into the truncated fragment instead of the real status cell, while the real last cell is left unchanged. Reproduced directly and live-hit twice during Phase 93s own build (INFRA-205 and INFRA-206 status updates), both manually repaired by the orchestrator. This phase (CER-066) fixes the row-splitting logic to treat an escaped pipe as a literal character within a cell rather than a column separator, and adds regression tests with escaped-pipe titles including the exact INFRA-205/INFRA-206 collision shape.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-207 | Fix escaped-pipe row corruption in `_update_story_row_in_phase`: split Stories-table rows on unescaped pipes only (`\|` treated as a literal cell character, not a column separator), so titles documenting matcher strings like `Edit\|Write` update the real status cell instead of truncating the title; add escaped-pipe regression tests including the INFRA-205/INFRA-206 collision shape | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-94 Cold-eyes checklist

— developer fills in after phase completion —
