---
id: INFRA-043
rail: INFRA
title: Auto-plumb phase rail and attempt counter into record_attempt.py (CER-015)
status: planned
phase: "23"
primary_files:
  - skills/pairmode/scripts/record_attempt.py
  - skills/pairmode/scripts/effort_db.py
touches:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - docs/cer/backlog.md
  - tests/pairmode/test_record_attempt.py
  - tests/pairmode/test_effort_db.py
---

## Acceptance criterion

`record_attempt.py` accepts a `--story-file <path>` flag that auto-extracts
`phase`, `rail`, and `id` from the story file's frontmatter via
`schema_validator._parse_frontmatter`. A new `effort_db.next_attempt_number()`
helper queries the database for the highest existing `attempt_number` for a
given `(story_id, agent_role)` pair and returns the next value. A new
`--auto-attempt` CLI flag uses this helper and is mutually exclusive with
`--attempt-number`. CLAUDE.build.md and the template use the new flags so the
orchestrator no longer hand-substitutes phase/rail/attempt values. Tests pass.
CER-015 marked RESOLVED.

## Protected file justification

This story modifies `CLAUDE.build.md` (a normally-protected file) and its
template. Justification: same additive pattern as INFRA-030, INFRA-034, and
INFRA-042 — replacing hardcoded placeholder values in example bash invocations
with the new flags. No structural rewrite of the build loop.

## Instructions

See `docs/phases/phase-23.md` — Story INFRA-043.

## Tests

See `docs/phases/phase-23.md` — Story INFRA-043.
