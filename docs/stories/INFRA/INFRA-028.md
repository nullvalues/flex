---
id: INFRA-028
rail: INFRA
title: Effort tracking sqlite schema and record_attempt.py recorder
status: planned
phase: "22"
primary_files:
  - skills/pairmode/scripts/effort_db.py
  - skills/pairmode/scripts/record_attempt.py
touches:
  - skills/pairmode/scripts/bootstrap.py
  - tests/pairmode/test_effort_db.py
  - tests/pairmode/test_record_attempt.py
---

## Acceptance criterion

A sqlite database at `.companion/effort.db` records one row per agent invocation
via the `attempts` table (story_id, phase, rail, agent_role, model, attempt_number,
token counts, tool_uses, duration_ms, outcome, notes, ts). A `record_attempt.py`
CLI lets the orchestrator append a row in one command. **No pricing data is stored
in the schema** — pricing is optional, user-maintained, applied at report time only.
Bootstrap auto-enables `effort_tracking: true` for pairmode-bootstrapped projects.
Tests pass.

## Instructions

See `docs/phases/phase-22.md` — Story INFRA-028.

## Tests

See `docs/phases/phase-22.md` — Story INFRA-028.
