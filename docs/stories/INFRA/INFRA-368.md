---
id: INFRA-368
rail: INFRA
title: Fix resolverState.ts getFlexBuildPath() resolving one directory too high (CER-142)
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

CER-142 (MEDIUM): `skills/observability/api/src/readers/resolverState.ts`'s `getFlexBuildPath()`
computes the path to `flex_build.py` one directory too high. It resolves `dirname(import.meta.url)`
up four `..` hops to land on `skills/`, then joins `obsApiDir, '..', 'pairmode', 'scripts',
'flex_build.py'` — the extra `..` steps back out of `skills/` entirely, producing
`<repo-root>/pairmode/scripts/flex_build.py` instead of
`<repo-root>/skills/pairmode/scripts/flex_build.py`. Because that path never exists, `spawnSync`
always fails and `readResolverState` silently returns `null` on every call, so
`/api/repos/:id/system`, `/api/repos/:id/context`'s `resolver_state` field, and `context.ts`'s
`current.story_id`/`current.phase` are always null/empty in production, not just in the INFRA-312
test fixture that surfaced it. Fix: `path.join(obsApiDir, 'pairmode', 'scripts',
'flex_build.py')` — drop the extra `..`. File/function: `skills/observability/api/src/readers/resolverState.ts`
`getFlexBuildPath()`. Filed rather than fixed in INFRA-312 because it was outside that story's
declared `touches:`.

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
