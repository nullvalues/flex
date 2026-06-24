# Phase 77 — multi-era index parser fix

**Era:** era-002
**Status:** planned

## Problem

`_parse_index_phases` in `flex_build.py` breaks out of its scan loop on the
first non-empty, non-pipe line it encounters after entering a table. For a
single-era index (one table, then EOF) this is harmless. For a multi-era index
— where a section heading like `## Era 002` separates two tables — the parser
exits after the first table and never reads subsequent ones.

Projects whose active phase lives in era 2+ have all era-1 phases marked
`complete`, so `current-phase` returns exit 1 ("No active phase found") even
though an active phase exists in a later table.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-033 | fix multi-era index parser in _parse_index_phases | complete |

## Out-of-band change

Commit 963e62e raised the `context_budget.py` default threshold from 120,000
to 130,000 tokens (effective ceiling 143,000) and updated the matching
`CLAUDE.build.md` documentation line. This change was applied without a story
spec (global policy violation — minor). It is recorded here for traceability.
Affected files: `skills/pairmode/scripts/context_budget.py`, `CLAUDE.build.md`.
