---
id: WORKER-006
rail: WORKER
title: Reviewer leaf worker — thin shell + plugin procedure skill
status: complete
phase: "HARNESS003-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/reviewer/procedure.md
  - tests/pairmode/test_reviewer_worker.py
touches:
  - skills/pairmode/scripts/worker_result.py
---

## Context

Converts the reviewer from `.claude/agents/reviewer.md` (rendered from `reviewer.md.j2`) to a
thin agent shell + plugin procedure skill. The review checklist from `CLAUDE.md` § Review
checklist and the reviewer logic from `CLAUDE.build.md` are extracted into the versioned procedure
skill. Returns `REVIEW-RESULT`. The old `.md.j2` template and rendered file remain during the
advisory window.

## Requires

- WORKER-004 complete: `worker_result.py` defines `REVIEW-RESULT` and `parse_worker_result`.
- WORKER-005 complete: the builder leaf pattern is established.

## Ensures

- `skills/pairmode/skills/reviewer/procedure.md` — canonical reviewer procedure (review checklist
  from `CLAUDE.md`, reviewer spawn logic from `CLAUDE.build.md`). Bounded inputs: the story spec,
  the diff (`git diff`), the phase doc, `CLAUDE.md` checklist. No accumulated orchestrator context.
- Returns `REVIEW-RESULT{verdict: "PASS"|"FAIL", findings: [str], reason: str}`.
- **DP1.3 input-bound guard:** procedure references only bounded inputs. Asserted in WORKER-010.
- `spawn-reviewer` is in `ACTIONS` and `_SPAWN_ACTIONS` (WORKER-004). No action grammar change.
- Tests assert: procedure file exists; bounded inputs (negative assertion); injected
  `REVIEW-RESULT{verdict: "PASS"}` parses; injected `REVIEW-RESULT{verdict: "FAIL", findings: ["x"]}`
  parses. No live API call.
- Existing `reviewer.md.j2` and rendered `.claude/agents/reviewer.md` NOT removed (advisory window).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Extract the review procedure from `CLAUDE.md` § Review checklist + `CLAUDE.build.md` reviewer
  spawn prose. The checklist items become the procedure body verbatim (lift-and-shift).
- The thin shell: "Load `skills/pairmode/skills/reviewer/procedure.md`. Review the diff for story
  `{scalar}`. Return the result as JSON matching the `REVIEW-RESULT` schema."

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_reviewer_worker.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: procedure file exists; bounded inputs; injected results parse; no live API call;
suite green.

### Out of scope

- Loop-breaker, security-auditor, intent-reviewer — WORKER-007/008/009.
- Removal of old agent files — HARNESS006.
