---
id: WORKER-008
rail: WORKER
title: Security-auditor leaf worker — thin shell + plugin procedure skill
status: complete
phase: "HARNESS003-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/security-auditor/procedure.md
  - tests/pairmode/test_security_auditor_worker.py
touches:
  - skills/pairmode/scripts/worker_result.py
---

## Context

Converts the security-auditor from `.claude/agents/security-auditor.md` (rendered from
`security-auditor.md.j2`) to a thin agent shell + plugin procedure skill. The security audit
checklist (hook scripts for key exposure, path traversal, architecture violations per `CLAUDE.md`)
is extracted into the versioned skill. Returns `REVIEW-RESULT`. Used by the checkpoint
`checkpoint-security` action (HARNESS004 RESOLVER-008). The old `.md.j2` template and rendered
file remain during the advisory window.

## Requires

- WORKER-004 complete: `worker_result.py` defines `REVIEW-RESULT`.

## Ensures

- `skills/pairmode/skills/security-auditor/procedure.md` — security audit procedure (the
  `CLAUDE.md` review checklist items 1–9 scoped to security: hook performance, pipe contract,
  spec safety, key exposure, path traversal). Bounded inputs: the diff, the story spec, the
  `hooks/` directory. No accumulated orchestrator state.
- Returns `REVIEW-RESULT{verdict: "PASS"|"FAIL", findings: [str], reason: str}`.
- `spawn-security-auditor` is in `ACTIONS` and `_SPAWN_ACTIONS` (WORKER-004). No routing change
  in this story (HARNESS004 wires the checkpoint routing).
- Tests assert: procedure file exists; bounded inputs; injected `REVIEW-RESULT{verdict: "PASS"}`
  parses; injected `REVIEW-RESULT{verdict: "FAIL", findings: ["CRITICAL: ..."]}" parses.
  No live API call.
- Existing `security-auditor.md.j2` and rendered `.claude/agents/security-auditor.md` NOT removed.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Extract the security audit procedure from the existing `security-auditor.md.j2` content and the
  `CLAUDE.md` security-focused review items. Lift-and-shift.
- The procedure must preserve the CRITICAL/HIGH/MEDIUM/LOW severity classification and the
  `PASS / FAIL — [check name]` output format (the checklist format is the canonical output).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_security_auditor_worker.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: procedure file exists; bounded inputs; injected results parse; no live API call;
suite green.

### Out of scope

- `checkpoint-security` routing (wired in HARNESS004 RESOLVER-008).
- Intent-reviewer — WORKER-009.
