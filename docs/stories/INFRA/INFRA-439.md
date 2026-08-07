---
id: INFRA-439
rail: INFRA
title: guard and stop-condition updates for handshake artifacts
status: stub
id_provisional: true # INFRA numbering assigned at sequencing — upstream counter moves
phase: "proposed:shadow-handshake"
narrative_roles: [SHADOW-REVIEWER, ORCHESTRATOR]
---

## Ensures

scope_guard admits the builder-owned .pairmode-review-request marker and the shadow-owned .pairmode-review.lck (both gitignored, never committed, each writable by exactly one role), and the shadow procedure’s stop condition becomes CLOSED-then-story-commit with the existing poll ceiling as the mid-review-death backstop.

## Instructions

Elaborated by spec-writer at phase open — see docs/phases/phase-proposed-shadow-handshake-20260807-003.md. Keep to
EXEMPLAR-000 proportion: one-sentence Ensures is the size contract.

## Tests

See docs/phases/phase-proposed-shadow-handshake-20260807-003.md — Story INFRA-439.
