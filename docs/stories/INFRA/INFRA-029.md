---
id: INFRA-029
rail: INFRA
title: Effort tracking pairmode_effort.py reporting CLI
status: complete
phase: "22"
primary_files:
  - skills/pairmode/scripts/pairmode_effort.py
touches:
  - tests/pairmode/test_pairmode_effort.py
---

## Acceptance criterion

A Click CLI at `skills/pairmode/scripts/pairmode_effort.py` produces four reports
from `.companion/effort.db`: `rollup`, `rework`, `expensive`, `models`. Token
counts are the primary metric in every report. Dollar projections are an optional
`--dollars <pricing.json>` flag. Tests pass.

## Instructions

See `docs/phases/phase-22.md` — Story INFRA-029.

## Tests

See `docs/phases/phase-22.md` — Story INFRA-029.
