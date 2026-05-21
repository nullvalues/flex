---
id: INFRA-042
rail: INFRA
title: Encode pre-reviewer commit discipline in CLAUDE.build.md.j2 (CER-014)
status: complete
phase: "22"
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - CLAUDE.build.md
touches:
  - docs/cer/backlog.md
  - tests/pairmode/test_templates.py
---

## Acceptance criterion

`skills/pairmode/templates/CLAUDE.build.md.j2` and flex's own `CLAUDE.build.md`
contain an explicit pre-reviewer step that commits any uncommitted story-file
changes and runs `git checkout -- lessons/` before the reviewer is spawned.
The architecture doc claim about "pre-reviewer commit discipline" is now backed
by an actual orchestrator instruction. CER-014 is marked RESOLVED.

## Protected file justification

This story modifies `CLAUDE.build.md` (the orchestrator instruction file) and
its template. Justification: the architecture doc already claims this
discipline exists; the orchestrator's behavior across phases 17-21 has
implicitly performed it. The change makes the claim true. The addition is
purely additive — a new Step 1.5 between existing Step 1 and Step 2 — with no
modification to the existing builder/reviewer/checkpoint flow.

## Instructions

See `docs/phases/phase-22.md` — Story INFRA-042.

## Tests

See `docs/phases/phase-22.md` — Story INFRA-042.
