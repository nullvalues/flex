---
era: "001"
---

# flex — Phase 54: sync-all wrapper command

← [Phase 53: Phase 52 cold-eyes fixes + story cost estimation](phase-53.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Add a `sync-all` wrapper subcommand to `pairmode_sync.py` that sequences the three existing pairmode sync operations — `sync.py` (methodology files), `sync-agents` (agent templates), and `sync-build` (CLAUDE.build.md) — preserving each command's surgical, separately-callable form. The wrapper defaults to dry-run (matching `sync-build`'s safe-by-default posture), accepts `--apply`, `--yes`, and `--project-dir` for parity with sibling subcommands, and emits the three downstream outputs concatenated with clear per-command separators. SKILL.md gains a `/flex:pairmode sync-all` entry. Advances era 001's INFRA rail by shifting another piece of deterministic ceremony out of the orchestrator's head and into versioned, testable CLI code.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-136 | `pairmode_sync.py sync-all` wrapper subcommand and SKILL.md entry | complete |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-54 Cold-eyes checklist

— developer fills in after phase completion —
