# Phase 76 — sync-build state.json context gate seed

**Era:** era-002
**Status:** planned

## Problem

`sync-build --apply` updates `CLAUDE.build.md` but does not touch `.companion/state.json`.
Projects migrating to the Phase 74/75 context gate design can have two failure states
that cause false-positive hard blocks on every agent spawn:

1. **Missing `context_session_reset_at`** — projects that predate Phase 68 (SessionStart
   hook) have no reset boundary key. A stale high `context_current_tokens` value (from a
   session weeks or months ago) looks fresh to `decide()` and can trigger blocks at
   well below actual context usage. Cora: 117,500 tokens recorded on 2026-06-13,
   blocking at 68k actual context.

2. **Missing `context_current_tokens`** — projects with no prior PostToolUse history
   have the key absent; `decide()` hard-blocks on first spawn.

The sync-build tool is the migration path. It should leave the project in a runnable
state, not require a separate manual state.json patch.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-032 | sync-build seeds context gate state on --apply | complete |
