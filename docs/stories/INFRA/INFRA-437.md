---
id: INFRA-437
rail: INFRA
title: REVIEW-OPEN/CLOSED entries and the final-diff pass
status: stub
id_provisional: true # INFRA numbering assigned at sequencing — upstream counter moves
phase: "proposed:shadow-handshake"
narrative_roles: [SHADOW-REVIEWER]
---

## Ensures

When the builder signals quiescence, the shadow acknowledges within one event-driven poll by writing OPEN to the shadow-owned .pairmode-review.lck, runs one full-diff review pass, appends findings to the suggestions log — each self-classified by type (mechanical, ensures-gap, intent-deviation, taste) — and writes CLOSED to the lck; scope_guard’s shadow confinement widens from one literal path to exactly two (log + lck), default-deny otherwise, CER-174/175 hardening pattern unchanged.

## Instructions

Elaborated by spec-writer at phase open — see docs/phases/phase-proposed-shadow-handshake-20260807-003.md. Keep to
EXEMPLAR-000 proportion: one-sentence Ensures is the size contract.

## Tests

See docs/phases/phase-proposed-shadow-handshake-20260807-003.md — Story INFRA-437.
