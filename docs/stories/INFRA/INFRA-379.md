---
id: INFRA-379
rail: INFRA
title: Derive test_plugin_manifest.py's expected skill names from skills/*/SKILL.md glob (CER-109)
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

CER-109 (LOW): `tests/pairmode/test_plugin_manifest.py::_EXPECTED_SKILL_NAMES` hardcodes the four
top-level skill names instead of globbing `skills/*/SKILL.md`, so a fifth skill added later would
ship unguarded against the `flex:` prefix regression the test exists to catch. Fix: derive the
expected skill-name set from a `skills/*/SKILL.md` glob rather than a literal list. File:
`tests/pairmode/test_plugin_manifest.py` (`_EXPECTED_SKILL_NAMES`). From the Phase-111 security
audit.

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
