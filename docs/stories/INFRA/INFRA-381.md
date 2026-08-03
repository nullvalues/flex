---
id: INFRA-381
rail: INFRA
title: Add drift/staleness tracking for bootstrap-seeded cold-start triad docs (CER-121)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-121 (HIGH): `docs/architecture.md` (item #2 of the mandatory cold-start triad) and
`docs/checkpoints.md` are bootstrap-seeded, deny-listed from writes, and tracked by nothing — no
body compare, no staleness check, no drift report — with observed downstream spread of 99-1568
lines across projects. INFRA-311 only landed the `bootstrap.SCAFFOLD_FILES ⊆ audit-tracked` parity
test; the actual body-tracking mechanism for these two seeded-doc families is this row's scope.
Gate: the next canon change to a seeded-doc template (`architecture.md`/`checkpoints.md` families)
or the first post-0.3.1 fleet sync campaign, whichever comes first — both conditions have now
arrived given Phase 119's own scope. Files: `docs/architecture.md`, `docs/checkpoints.md`, and the
tracking mechanism itself (likely `skills/pairmode/scripts/audit.py`, which already carries the
analogous staleness-check pattern for `docs/ideology.md`/`docs/reconstruction.md`). From the
2026-07-29 cold-eyes review (F3).

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests
