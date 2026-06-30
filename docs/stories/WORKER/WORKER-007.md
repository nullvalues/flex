---
id: WORKER-007
rail: WORKER
title: Loop-breaker leaf worker — thin shell + plugin procedure skill
status: planned
phase: "HARNESS003-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/loop-breaker/procedure.md
  - tests/pairmode/test_loop_breaker_worker.py
touches:
  - skills/pairmode/scripts/worker_result.py
---

## Context

Converts the loop-breaker from `.claude/agents/loop-breaker.md` (rendered from `loop-breaker.md.j2`)
to a thin agent shell + plugin procedure skill. The loop-breaker procedure (cold-eyes analysis of
the failing error, one alternative approach) is extracted from the existing agent content into the
versioned skill. Returns `ADVICE`. The resolver already emits `spawn-loop-breaker` in Row 6 of
`resolve_next_action` (HARNESS001-main RESOLVER-003); no routing change in this story. The old
`.md.j2` template and rendered file remain during the advisory window.

## Requires

- WORKER-004 complete: `worker_result.py` defines `ADVICE` and `parse_worker_result`.

## Ensures

- `skills/pairmode/skills/loop-breaker/procedure.md` — loop-breaker procedure (cold-eyes error
  analysis, one alternative approach, no code reproduction). Bounded inputs: the error/failure
  description (from the resolver scalar), the failing file:line reference, the prior approaches
  tried. No accumulated orchestrator history beyond the bounded scalar.
- Returns `ADVICE{type: "ADVICE", approach: str, rationale: str}`.
- `spawn-loop-breaker` is already in `ACTIONS` and `_SPAWN_ACTIONS` (HARNESS001-main). No change.
- Tests assert: procedure file exists; bounded inputs; injected `ADVICE` parses; no live API call.
- Existing `loop-breaker.md.j2` and rendered `.claude/agents/loop-breaker.md` NOT removed.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Extract the loop-breaker procedure from the existing `loop-breaker.md.j2` content plus
  `CLAUDE.md` § Loop-breaker mode. Lift-and-shift; do not redesign the procedure.
- Bounded inputs: error string, file:line, prior attempts tried (passed as the spawn `scalar`
  or a structured input block). No prior-attempt transcripts not conveyed in the scalar.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_loop_breaker_worker.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: procedure file exists; bounded inputs; injected `ADVICE` parses; no live API call;
suite green.

### Out of scope

- Security-auditor and intent-reviewer — WORKER-008/009.
- Routing change for `spawn-loop-breaker` (already routes in Row 6; unchanged).
