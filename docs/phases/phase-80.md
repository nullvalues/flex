# Phase 80 — pre-reviewer blanket-stage exclusion fix

**Era:** era-002
**Status:** complete

## Goal

Fix the pre-reviewer `git add` in `CLAUDE.build.md` (and its `.j2` template)
so that story deliverables whose `primary_files` live under `docs/phases/` or
`docs/cer/` are not silently committed under the chore message before the
reviewer fires.

Single-story phase. See L018 for the lesson that surfaced this.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-039 | pre-reviewer git add: exclude story primary_files from blanket stage | complete |

## Schema delivery

No new persistent schema objects introduced in this phase.
