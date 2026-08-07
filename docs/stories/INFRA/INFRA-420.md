---
id: INFRA-420
rail: INFRA
title: cause-class column on effort.db retry rows (D1)
status: stub
id_provisional: true # INFRA numbering assigned at sequencing — upstream counter moves
phase: "proposed:measurement-columns"
narrative_roles: [OPERATOR]
---

## Ensures

Every retry row in effort.db carries a bounded cause-class enum value, recorded hook-side at write time, with existing rows readable as class unknown.

## Instructions

Elaborated by spec-writer at phase open — see docs/phases/phase-proposed-measurement-columns-20260807-001.md. Keep to
EXEMPLAR-000 proportion: one-sentence Ensures is the size contract.

## Tests

See docs/phases/phase-proposed-measurement-columns-20260807-001.md — Story INFRA-420.
