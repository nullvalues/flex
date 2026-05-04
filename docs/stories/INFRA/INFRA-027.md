---
id: INFRA-027
rail: INFRA
title: Default reviewer agents to read-only tools Read Grep Glob Bash
status: complete
phase: "21"
primary_files:
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/agents/intent-reviewer.md.j2
  - skills/pairmode/templates/agents/loop-breaker.md.j2
  - skills/pairmode/templates/agents/security-auditor.md.j2
touches:
  - docs/architecture.md
  - tests/pairmode/test_templates.py
---

## Acceptance criterion

The four reviewer-class agent templates restrict tools to `[Read, Grep, Glob, Bash]`
(security-auditor: `[Read, Grep, Glob]` — no Bash). Verification step (expanded per
CER finding) confirms that across all four templates, every commit/revert/test
operation is Bash-mediated. `docs/architecture.md` records the two-layer rationale
(read-only tools + pre-reviewer commit discipline). Tests pass.

## Instructions

See `docs/phases/phase-21.md` — Story INFRA-027.

## Tests

See `docs/phases/phase-21.md` — Story INFRA-027.
