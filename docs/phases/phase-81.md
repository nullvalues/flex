# Phase 81 — write-permissions + clear-permissions wired into build loop

**Era:** era-002
**Status:** planned

## Goal

Wire the missing Layer 2 permission calls into `CLAUDE.build.md` (and its
`.j2` template): `write-permissions` before the builder spawns, and
`clear-permissions` after the reviewer returns. Eliminates the auto-mode
toggle requirement that upstream era-002 projects experience on every story.

Single-story phase.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-040 | CLAUDE.build.md: add write-permissions + clear-permissions to build loop | planned |

## Schema delivery

No new persistent schema objects introduced in this phase.
