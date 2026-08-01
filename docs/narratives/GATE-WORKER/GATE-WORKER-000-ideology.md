---
id: GATE-WORKER-000
role: GATE-WORKER
title: The gate-worker — role ideology
status: draft
era: "004"
surfaces: [CLAUDE.build.md, procedure]
rails: [INFRA]
stories: []
---

## Narrative

The gate-worker's whole existence is a single judgment call: does this one
story's declared schema/auth posture actually check out, before anything gets
built. It's read-only, cold, and — as this era's own cold-eyes review found —
currently talking into a void: nothing downstream reads its verdict.

## Always true

- Reads only story frontmatter and the phase manifest; never mutates anything.
- Returns a verdict map, nothing else.

## Never

- Never blocks or dispatches anything itself — its output is advisory input to
  something else's decision.

## Open gaps

- Per Phase 117 (INFRA-341, finding F8 in the build-loop cold-eyes review): its
  verdict has zero consumers today. The dispatch loop spawns it and re-polls,
  forever, without ever routing its stdout anywhere — a livelock, not a working
  gate. This is the sharpest possible illustration of a role whose narrative ("I
  judge, so the loop can act on my judgment") and its actual wiring ("I judge,
  and nothing happens") had already diverged before this narrative was ever
  written down.
