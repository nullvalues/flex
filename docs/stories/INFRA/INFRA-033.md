---
id: INFRA-033
rail: INFRA
title: Document model fallback policy in agent templates
status: complete
phase: "21"
primary_files:
  - skills/pairmode/templates/agents/builder.md.j2
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/agents/intent-reviewer.md.j2
  - skills/pairmode/templates/agents/loop-breaker.md.j2
  - skills/pairmode/templates/agents/security-auditor.md.j2
touches:
  - docs/architecture.md
  - CLAUDE.build.md
  - tests/pairmode/test_templates.py
---

## Acceptance criterion

Pairmode agent templates encode an inline fallback comment after `model:`
(builder: `# fallback: haiku  (never below)`; reviewers: `# fallback: sonnet  (never below)`).
`docs/architecture.md` adds a "Model selection and fallback" subsection documenting the
role-based pinning and rate-limit fallback procedure. `CLAUDE.build.md` references the
architecture subsection. Tests assert the fallback comments are present. Tests pass.

## Instructions

See `docs/phases/phase-21.md` — Story INFRA-033.

## Tests

See `docs/phases/phase-21.md` — Story INFRA-033.
