---
id: INFRA-398
rail: INFRA
title: Fix .pairmode-overrides template/migration gap from audit.py key-format change (CER-180)
status: draft
phase: "128"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/.pairmode-overrides.j2
  - skills/pairmode/scripts/audit.py
touches:
  - tests/pairmode/test_audit.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
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
