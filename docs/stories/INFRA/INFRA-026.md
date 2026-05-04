---
id: INFRA-026
rail: INFRA
title: Pin reviewer agents to model opus in pairmode templates
status: complete
phase: "21"
primary_files:
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/agents/intent-reviewer.md.j2
  - skills/pairmode/templates/agents/loop-breaker.md.j2
  - skills/pairmode/templates/agents/security-auditor.md.j2
touches:
  - tests/pairmode/test_templates.py
---

## Acceptance criterion

The four reviewer-class agent templates carry an explicit `model: opus` field in
their YAML frontmatter. `builder.md.j2` remains pinned to `sonnet`. Tests assert
the pin is present. Tests pass.

## Instructions

See `docs/phases/phase-21.md` — Story INFRA-026.

## Tests

See `docs/phases/phase-21.md` — Story INFRA-026.
