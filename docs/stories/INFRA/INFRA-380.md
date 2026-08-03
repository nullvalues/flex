---
id: INFRA-380
rail: INFRA
title: Match suffixed phase filenames in story_new.py's phase-manifest lookup (CER-62)
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

CER-62 (MEDIUM): `story_new.py`'s `_append_to_phase` phase-manifest lookup
(`skills/pairmode/scripts/story_new.py:127-137`) only matches two filename shapes — `{phase}-*.md`
and exact `phase-{phase}.md`. Suffixed phase manifests of the form `phase-<phase_id>-<suffix>.md`
(the naming convention `phase_new.py --phase-id --suffix` produces, per CER-038) match neither
glob, so `story_new.py --phase MU020` silently returns `False` from `_append_to_phase` and the new
story is never added to the phase's Stories table — with no error surfaced to the caller. This was
confirmed live on the radar project (fable-orchestrated build), where the operator had to add the
Stories table rows by hand. Fix: add a third glob `phase-{phase}-*.md` (or generalize to
`*{phase}*.md`) alongside the two existing globs, and consider surfacing a warning when
auto-registration falls through to `False` instead of failing silently. Story files are still
created correctly under this bug — only the phase manifest's Stories table drifts until manually
reconciled. File: `skills/pairmode/scripts/story_new.py:127-137` (`_append_to_phase`).

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
