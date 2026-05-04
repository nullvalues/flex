---
id: LESSON-003
rail: LESSON
title: Capture reviewer-as-read-only-Bash pattern as a lesson
status: complete
phase: "21"
primary_files:
  - lessons/lessons.json
  - lessons/LESSONS.md
touches: []
---

## Acceptance criterion

A new lesson entry in `lessons/lessons.json` (id auto-assigned by lesson_utils)
documents the reviewer tools restriction methodology with trigger / problem /
learning / methodology_change / affects fields, including the concrete
"reviewer edits assertion to make a failing test pass" example. `lessons/LESSONS.md`
is regenerated. Tests pass.

## Protected file justification

Same as LESSON-002: the lesson IS the deliverable. The append-only invariant
in `save_lessons` remains the load-bearing protection.

## Instructions

See `docs/phases/phase-21.md` — Story LESSON-003.

## Tests

Lesson stories typically have no unit tests; the acceptance criterion is the
lesson entry being well-formed and the pairmode test suite still passing.
