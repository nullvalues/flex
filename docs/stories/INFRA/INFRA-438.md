---
id: INFRA-438
rail: INFRA
title: builder quiescence signal, bounded wait, revise-within-attempt
status: stub
id_provisional: true # INFRA numbering assigned at sequencing — upstream counter moves
phase: "proposed:shadow-handshake"
narrative_roles: [BUILDER]
---

## Ensures

After its last write and before the story commit, the builder writes a .pairmode-review-request marker and checks the lck once per poll: no OPEN acknowledgment within one cycle means the shadow is dead and the builder proceeds immediately (no tuned timeout); on OPEN it waits for CLOSED (generous runaway ceiling only), addresses findings within the attempt, and appends a one-line disposition per finding (adopted / declined + outcome + reason) to the suggestions log; the reviewer procedure gains the exchange record (typed findings + dispositions) as a named bounded input, so declined ensures-gap findings are re-examined at review rather than lost.

## Instructions

MUST-KEEP at elaboration: the reviewer-procedure edit is part of this story's
scope, not a follow-up — skills/pairmode/skills/reviewer/procedure.md adds the
suggestions-log exchange record to its bounded inputs, with declined
ensures-gap findings called out for re-examination. Do not split it out or
defer it.

Elaborated by spec-writer at phase open — see docs/phases/phase-proposed-shadow-handshake-20260807-003.md. Keep to
EXEMPLAR-000 proportion: one-sentence Ensures is the size contract.

## Tests

See docs/phases/phase-proposed-shadow-handshake-20260807-003.md — Story INFRA-438.
