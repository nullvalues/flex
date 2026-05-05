---
id: INFRA-030
rail: INFRA
title: Wire effort recording into the build loop CLAUDE.build.md
status: planned
phase: "22"
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - docs/architecture.md
  - tests/pairmode/test_templates.py
---

## Acceptance criterion

`CLAUDE.build.md` (and `CLAUDE.build.md.j2`) include explicit bash steps after each
builder spawn and after each reviewer spawn that invoke `record_attempt.py` to capture
the agent's `<usage>` block. Recording is conditional on `state["effort_tracking"]`
(record_attempt.py handles the no-op silently). `docs/architecture.md` documents the
effort-tracking data model and the tokens-as-primary-metric framing. Tests assert
the wiring is present in both files. Tests pass.

## Protected file justification

This story modifies `CLAUDE.build.md` (a normally-protected file) and its template.
Justification: this is the same Step-extension pattern used by INFRA-042 (Step 1.5
commit discipline) — additive instructions to the existing build-loop steps, no
restructuring. The wiring is the entire point of INFRA-030.

## Instructions

See `docs/phases/phase-22.md` — Story INFRA-030.

## Tests

See `docs/phases/phase-22.md` — Story INFRA-030.
