---
id: LESSON-002
rail: LESSON
title: Capture model upgrade-downgrade pattern as a lesson
status: complete
phase: "21"
primary_files:
  - lessons/lessons.json
  - lessons/LESSONS.md
touches: []
---

## Acceptance criterion

A new lesson entry in `lessons/lessons.json` (id auto-assigned by lesson_utils)
documents the model-selection methodology with trigger / problem / learning /
methodology_change / affects fields. `lessons/LESSONS.md` is regenerated to
include the new entry. Tests pass.

## Protected file justification

This story modifies `lessons/lessons.json` and `lessons/LESSONS.md`, the
append-only lessons store. Justification: the lesson IS the deliverable. The
standing prohibition on lesson edits exists to prevent unauthorized appends
during builder activity for non-LESSON stories; for a LESSON-* story, the
lesson append is in scope by definition. The `save_lessons` helper in
`lesson_utils.py` enforces the append-only invariant programmatically (rejects
removal or modification of any field other than `status` on existing entries),
so the protection that matters most stays in force.

## Instructions

See `docs/phases/phase-21.md` — Story LESSON-002.

## Tests

Lesson stories typically have no unit tests; the acceptance criterion is the
lesson entry being well-formed and the pairmode test suite still passing.
