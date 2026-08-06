---
id: INFRA-407
rail: INFRA
title: Overrides/audit key-shape quality fixes (CER-182/184/185/202)
status: draft
phase: "137"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/scripts/lesson_review.py
  - skills/pairmode/scripts/pairmode_drift_report.py
touches:
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_lesson_review.py
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
