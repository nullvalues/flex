---
id: WORKER-009
rail: WORKER
title: Intent-reviewer leaf worker — thin shell + plugin procedure skill
status: complete
phase: "HARNESS003-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/intent-reviewer/procedure.md
  - tests/pairmode/test_intent_reviewer_worker.py
touches:
  - skills/pairmode/scripts/worker_result.py
---

## Context

Converts the intent-reviewer from `.claude/agents/intent-reviewer.md` (rendered from
`intent-reviewer.md.j2`) to a thin agent shell + plugin procedure skill. The intent review
procedure (compare what was built against what was planned, identify design pivots, recommend
specific doc edits) is extracted into the versioned skill. Returns `REVIEW-RESULT`. Used by the
checkpoint `checkpoint-intent` action (HARNESS004 RESOLVER-008). The old `.md.j2` template and
rendered file remain during the advisory window.

## Requires

- WORKER-004 complete: `worker_result.py` defines `REVIEW-RESULT`.

## Ensures

- `skills/pairmode/skills/intent-reviewer/procedure.md` — intent-review procedure (compare what
  was built vs. planned, identify design pivots, recommend doc edits). Bounded inputs: the story
  spec, the diff, the phase doc (the agreements input). No accumulated orchestrator state.
- Returns `REVIEW-RESULT{verdict: "PASS"|"FAIL"|"ALIGNED", findings: [str], reason: str}`.
  (Note: `ALIGNED` is the canonical intent-review verdict. The REVIEW-RESULT schema restricts
  `verdict` to `{"PASS", "FAIL", "ALIGNED"}` — the implementation uses a closed enum, not an
  open string. Future verdict extensions require adding to the enum in `worker_result.py`.)
- `spawn-intent-reviewer` is in `ACTIONS` and `_SPAWN_ACTIONS` (WORKER-004). No routing change
  in this story (HARNESS004 wires the checkpoint routing).
- Tests assert: procedure file exists; bounded inputs; injected `REVIEW-RESULT{verdict: "ALIGNED"}`
  parses; injected `REVIEW-RESULT{verdict: "FAIL", findings: ["MEDIUM: ..."]}` parses.
  No live API call.
- Existing `intent-reviewer.md.j2` and rendered `.claude/agents/intent-reviewer.md` NOT removed.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Extract the intent-review procedure from the existing `intent-reviewer.md.j2` content (or the
  `intent-reviewer` agent description in the build instructions). Lift-and-shift.
- The procedure must preserve the "ALIGNED/[findings]" output format that the checkpoint step
  relies on.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_intent_reviewer_worker.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: procedure file exists; bounded inputs; injected results parse; no live API call;
suite green.

### Out of scope

- `checkpoint-intent` routing (wired in HARNESS004 RESOLVER-008).
- Isolation suite (WORKER-010).
