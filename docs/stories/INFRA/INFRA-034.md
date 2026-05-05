---
id: INFRA-034
rail: INFRA
title: Real-time effort guardrail in build loop
status: planned
phase: "22"
primary_files:
  - skills/pairmode/scripts/effort_db.py
touches:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - docs/architecture.md
  - tests/pairmode/test_effort_guardrail.py
---

## Acceptance criterion

After each builder attempt, the orchestrator queries the effort database for the
median tokens-per-attempt for the current rail and compares against the
just-completed attempt's tokens. If the attempt exceeds N× the median (default 3.0,
configurable via `state["effort_guardrail_multiplier"]`), the orchestrator surfaces
a structured warning to stderr before spawning the reviewer. The guardrail is
informational (exit 0), not blocking. Insufficient sample (< 3 PASSing builds for
the rail) returns early without firing. CLAUDE.build.md (and the template) include
the guardrail invocation step. Tests pass.

## Protected file justification

This story modifies `CLAUDE.build.md` (and its template) to add a guardrail
invocation step. Same additive pattern as INFRA-030 (recording wiring) and INFRA-042
(commit discipline) — purely additive instructions to the build-loop steps, no
restructuring of existing builder/reviewer/checkpoint flow.

## Instructions

See `docs/phases/phase-22.md` — Story INFRA-034.

## Tests

See `docs/phases/phase-22.md` — Story INFRA-034.
