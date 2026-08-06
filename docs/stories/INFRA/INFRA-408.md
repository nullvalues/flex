---
id: INFRA-408
rail: INFRA
title: Close shadow-reviewer scope_guard cwd-resolution gap (CER-176/177/201)
status: draft
phase: "138"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/reviewer_bash_guard.py
  - skills/pairmode/scripts/scope_guard.py
touches:
  - tests/pairmode/test_reviewer_bash_guard.py
  - tests/pairmode/test_scope_guard.py
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
