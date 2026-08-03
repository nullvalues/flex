---
id: INFRA-382
rail: INFRA
title: Correct stale story statuses in docs/phases/phase-64.md's Stories table (CER-125)
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

CER-125 (LOW): `docs/phases/phase-64.md`'s Stories table lists INFRA-164..168 as `backlog` even
though all five completed under `HARNESS007-main` (Phase G resume) — a stale manifest that
`story_update.py` cannot reach by design, since legacy phase docs are outside its write scope. Fix
is a hand edit of the five status cells with a pointer note to `HARNESS007-main`. Gate was the
next hand edit to `phase-64.md` for any reason, or any `story_update.py` change adding
legacy-phase-doc handling — either has now arrived given this phase's scope. File:
`docs/phases/phase-64.md` (Stories table, INFRA-164 through INFRA-168 rows). From the 2026-07-29
cold-eyes review (F12).

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
