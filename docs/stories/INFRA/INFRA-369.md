---
id: INFRA-369
rail: INFRA
title: Decouple a migrate test from the literal checkout directory name flex-harness (CER-146)
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

CER-146 (LOW): `tests/pairmode/test_pairmode_migrate.py::test_to030_relocates_stale_flex_harness_hook_command`
fails whenever the pairmode test suite is physically run from inside a checkout literally named
`flex-harness` (e.g. `/mnt/work/flex-harness`) — a pre-existing defect (reproduces back at
cp-115), not introduced by any Phase 116 story. The test asserts the migrated hook command does
not contain the substring `"flex-harness"`, but the migration code (or the fixture project's
derived path) picks up the literal directory name of wherever `pairmode_migrate.py`'s own module
lives — which legitimately contains `flex-harness` when the suite runs from that checkout. This is
a test-environment coupling bug, not a real migration defect. Fix direction: parameterize the
test's fixture project path/name so the assertion is independent of the literal directory the
suite happens to run from, or assert on a synthetic marker instead of the substring
`"flex-harness"`. File: `tests/pairmode/test_pairmode_migrate.py`. Surfaced during Phase 116's
checkpoint-tag promotion when the full suite was run post-merge inside `/mnt/work/flex-harness`.

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
