---
id: INFRA-375
rail: INFRA
title: Audit hardcoded flex-harness absolute paths for release-channel staleness risk (CER-160)
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

CER-160 (MEDIUM): a worker that resolves the hardcoded absolute path to `flex-harness`'s copy of
`skills/pairmode/skills/spec-writer/procedure.md` (the path INFRA-304's E13 rationale calls for)
can silently run a stale, pre-checkpoint-promotion version of that procedure mid-phase. This
reproduced live during INFRA-362's Phase 118 dogfood exercise: a spec-writer instructed to use the
absolute harness path found a 298-line, five-bounded-input procedure with no narrative step, while
the correct in-repo copy (already updated by INFRA-355/357 in the same phase) was 381 lines with
six inputs and Steps 4c/4d. Because the release-channel design only updates the harness copy at
checkpoint-tag, any worker resolving a hardcoded harness-absolute path is running last-checkpoint's
tooling by construction. Fix direction: audit every other hardcoded `flex-harness` absolute-path
reference (agent shells, skill docs) for the same staleness risk, and consider whether
procedure/skill docs should resolve from the project's own tree rather than the pinned harness
copy. Files: `skills/pairmode/skills/spec-writer/procedure.md`, plus any other absolute-
`flex-harness`-path references found in the audit.

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
