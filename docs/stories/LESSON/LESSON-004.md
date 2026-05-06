---
id: LESSON-004
rail: LESSON
title: Capture sonnet-baseline opus-on-demand rebalance rationale
status: planned
phase: "23"
primary_files:
  - lessons/lessons.json
  - lessons/LESSONS.md
touches: []
---

## Acceptance criterion

A new lesson entry in `lessons/lessons.json` (id auto-assigned by lesson_utils)
captures the model-rebalance methodology — sonnet baseline with opus reserved
for explicit upgrade triggers. `lessons/LESSONS.md` is regenerated to include
the new entry.

## Protected file justification

This story modifies `lessons/lessons.json` and `lessons/LESSONS.md`, the
append-only lessons store. Justification: the lesson IS the deliverable.
Standing prohibition exists to prevent unauthorized appends during builder
activity for non-LESSON stories; for a LESSON-* story the append is in scope
by definition. The `save_lessons` helper in `lesson_utils.py` enforces the
append-only invariant programmatically.

## Instructions

See `docs/phases/phase-23.md` — Story LESSON-004.

## Tests

Lesson stories have no unit tests; the acceptance criterion is the lesson
entry being well-formed and the pairmode test suite still passing.
