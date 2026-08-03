---
id: INFRA-367
rail: INFRA
title: Add non-interactive rail-creation flags to story_new.py (CER-117)
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

CER-117 (LOW): `story_new.py` prompts interactively (`Rail X does not exist. Create it? [Y/n]`)
when the target rail doesn't exist yet, which aborts under a non-interactive orchestrator unless
the prompt is piped `yes`. Fix direction: add a `--create-rail` (or `--yes`) flag so
scripted/orchestrated invocations can bypass the prompt. File: `skills/pairmode/scripts/story_new.py`
(the rail-creation prompt path). Surfaced by RELEASE-067 E12 (new-2), 2026-07-29.

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
