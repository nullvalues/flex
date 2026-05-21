---
id: INFRA-041
rail: INFRA
title: Propagate fallback-policy pointer to CLAUDE.build.md.j2 template (CER-013)
status: complete
phase: "22"
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - docs/cer/backlog.md
  - tests/pairmode/test_templates.py
---

## Acceptance criterion

`skills/pairmode/templates/CLAUDE.build.md.j2` contains the same one-line
fallback note that INFRA-033 added to flex's own `CLAUDE.build.md`. Future
pairmode bootstraps inherit the orchestrator-level pointer to the fallback
policy. A test asserts the rendered template contains the fallback line.
CER-013 is marked RESOLVED.

## Instructions

See `docs/phases/phase-22.md` — Story INFRA-041.

## Tests

See `docs/phases/phase-22.md` — Story INFRA-041.
