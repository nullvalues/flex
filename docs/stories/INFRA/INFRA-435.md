---
id: INFRA-435
rail: INFRA
title: dark-feature scan at checkpoint
status: stub
id_provisional: true # INFRA numbering assigned at sequencing — upstream counter moves
phase: "proposed:completeness-gate"
narrative_roles: [OPERATOR, INTENT-REVIEWER]
---

## Ensures

A repeatable scan reports every agent without a narrative directory, every default-off flag without a surfacing doc or bootstrap prompt, and every producer (verdict, event, file) without a consumer, runs as a checkpoint step, and the 0.4.1 tree passes it clean.

## Instructions

Elaborated by spec-writer at phase open — see docs/phases/phase-proposed-completeness-gate-20260807-002.md. Keep to
EXEMPLAR-000 proportion: one-sentence Ensures is the size contract.

## Tests

See docs/phases/phase-proposed-completeness-gate-20260807-002.md — Story INFRA-435.
