---
id: INFRA-411
rail: INFRA
title: Fix story_new.py writer/reader escaping mismatch (CER-213)
status: draft
phase: "141"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_story_new.py
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
