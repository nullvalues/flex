---
id: INFRA-370
rail: INFRA
title: Auto-derive model_selector.py's test file into touches: when the module is touched (CER-145)
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

CER-145 (LOW): three consecutive Phase 116 stories against
`skills/pairmode/scripts/model_selector.py` (INFRA-333, INFRA-334, and their common test
companion) each omitted `tests/pairmode/test_model_selector.py` from `touches:`, even though it is
the direct unit-test file for the story's own `primary_files:` module. Each time the builder
wrote/updated the tests anyway, the reviewer correctly flagged the file as undeclared scope and
left it uncommitted, and the orchestrator had to widen `touches:` after the fact to avoid losing
coverage (INFRA-333 commit cf94af3c, INFRA-334 commit 8cbf3abf). The spec-writer procedure has no
rule auto-including a `primary_files:` module's conventional test path
(`tests/pairmode/test_<module>.py`) in `touches:`. Fix direction: either the spec-writer procedure
auto-derives and includes the primary module's test file, or `story_new.py`'s scaffolding does it
mechanically before spec-writer elaboration runs. Files named:
`skills/pairmode/skills/spec-writer/procedure.md`, `skills/pairmode/scripts/story_new.py`.

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
