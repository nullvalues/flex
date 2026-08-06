---
id: INFRA-400
rail: INFRA
title: Close CER-172 scrub completeness and regression gaps (CER-188)
status: draft
phase: "130"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_discovery.py
  - skills/pairmode/scripts/scrub_fleet_names.py
  - .pairmode-fleet.local.json.example
touches:
  - tests/pairmode/test_fleet_discovery.py
  - tests/pairmode/test_scrub_fleet_names.py
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
