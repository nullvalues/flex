---
id: INFRA-434
rail: INFRA
title: landing-spot rule in the intent-reviewer procedure
status: stub
id_provisional: true # INFRA numbering assigned at sequencing — upstream counter moves
phase: "proposed:completeness-gate"
narrative_roles: [INTENT-REVIEWER]
---

## Ensures

The intent-reviewer procedure FAILs any phase that introduces an agent role, config flag, event type, or persistent surface without a same-phase narrative entry and a discovery surface (default-on, bootstrap prompt, or documented landing spot), and the rule is recorded in the intent-reviewer narrative with the shadow-reviewer shipping as its named precedent.

## Instructions

Elaborated by spec-writer at phase open — see docs/phases/phase-proposed-completeness-gate-20260807-002.md. Keep to
EXEMPLAR-000 proportion: one-sentence Ensures is the size contract.

## Tests

See docs/phases/phase-proposed-completeness-gate-20260807-002.md — Story INFRA-434.
