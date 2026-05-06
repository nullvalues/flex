---
id: INFRA-044
rail: INFRA
title: Flip reviewer-class templates to sonnet baseline (model rebalance)
status: planned
phase: "23"
primary_files:
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/agents/intent-reviewer.md.j2
  - skills/pairmode/templates/agents/security-auditor.md.j2
touches:
  - docs/architecture.md
  - tests/pairmode/test_templates.py
---

## Acceptance criterion

`reviewer.md.j2`, `intent-reviewer.md.j2`, and `security-auditor.md.j2` carry
`model: sonnet` (not `model: opus`). `loop-breaker.md.j2` remains `model: opus`.
Each affected template gains an `# upgrade: opus  (when retry / pre-PR audit /
mid-phase pivot)` comment after the model line. `docs/architecture.md` "Model
selection" subsection is replaced with the "sonnet baseline, opus on demand"
framing documenting upgrade triggers explicitly. Tests assert the new defaults.

## Instructions

See `docs/phases/phase-23.md` — Story INFRA-044.

## Tests

See `docs/phases/phase-23.md` — Story INFRA-044.
