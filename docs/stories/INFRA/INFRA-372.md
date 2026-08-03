---
id: INFRA-372
rail: INFRA
title: Track .pairmode-overrides in CANONICAL_FILES/SCAFFOLD_FILES audit surfaces (CER-132)
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

CER-132 (MEDIUM): `.pairmode-overrides` is bootstrap-seeded (`bootstrap.SCAFFOLD_FILES`,
`.pairmode-overrides.j2`) and is the sanctioned keep-my-extension mechanism that both the audit's
EXTRA-severity split and sync's `RETIRED_SECTIONS` pruning (INFRA-311) defer to — yet no audit
surface tracks the file itself: it appears in neither `audit.CANONICAL_FILES` nor
`audit.SCAFFOLD_FILES` and has no dedicated existence/health check (unlike
`docs/ideology.md`/`docs/reconstruction.md`, which do have staleness checks in `audit.py`). A
deleted or corrupted overrides file therefore silently strips a project's declared protections on
the next sync. Body compare is the wrong tool here since the content is project-owned; the fix is
an existence check plus a parse-health check (unparseable lines reported by `_load_overrides`, not
silently dropped). File: `skills/pairmode/scripts/audit.py` (`CANONICAL_FILES`/`SCAFFOLD_FILES`
lists at ~lines 52/70, `_load_overrides` at ~line 410). Surfaced by INFRA-311's
`bootstrap.SCAFFOLD_FILES ⊆ audit-tracked` parity test, which currently excepts
`.pairmode-overrides` via `_KNOWN_GAPS` pending this fix.

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
