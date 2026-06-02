# flex — Phase 52: Lean orchestrator and spec workflow

← [Phase 51: Stub gate and phase-doc scan enforcement](phase-51.md)

## Goal

Refactor the build orchestrator into a minimal routing loop: static orientation
from the system prompt (CLAUDE.md), build position derived from a `current-phase`
+ `next-story` CLI pair each iteration rather than carried in memory, agents
receiving only a story ID and finding their own context cold. Add a "spec next
phase" workflow that produces committed phase + story spec files via an opus
Plan subagent, ready to hand off to the build loop.

Exit criteria:
- No upfront file reads on general session load; the blanket brief.md /
  architecture.md instruction is removed from CLAUDE.md
- Orchestrator build loop derives position via CLI, not memory or manual reads
- Builder and reviewer receive story ID only; all story content read cold by
  the agent itself
- Agent results returned to orchestrator are minimal: pass/fail summary +
  `<usage>` block
- `/context` check fires inline before each story spawn; over threshold stops
  and prompts user to `/clear` and resume
- `"spec next phase [intent]"` trigger produces committed phase + story spec
  files and reports ready for the build loop

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-011 | Upfront context elimination | planned |
| BUILD-012 | Story-ID-only spawn protocol | planned |
| BUILD-013 | Minimal agent return surface | planned |
| BUILD-014 | /context inline gate | planned |
| BUILD-015 | `spec next phase` orchestrated workflow | planned |

Tag (on ship): `cp52-lean-orchestrator-spec-workflow`
