---
id: INFRA-040
rail: INFRA
title: Companion-vs-pairmode positioning in README and PAIRMODE.md
status: complete
phase: "21"
primary_files:
  - README.md
  - docs/pairmode/PAIRMODE.md
touches:
  - docs/architecture.md
  - tests/pairmode/test_docs.py
---

## Acceptance criterion

`README.md` and `docs/pairmode/PAIRMODE.md` make the boundary between companion and
pairmode explicit using the reactive-vs-proactive framing. README contains a comparison
table and "use it when" guidance. PAIRMODE.md gains a "Pairmode in relation to companion"
section. `docs/architecture.md` Pairmode design section opens with a separation-of-concerns
preamble. Tests pass.

## Instructions

See `docs/phases/phase-21.md` — Story INFRA-040.

## Tests

See `docs/phases/phase-21.md` — Story INFRA-040.
