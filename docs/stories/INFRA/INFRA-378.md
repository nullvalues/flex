---
id: INFRA-378
rail: INFRA
title: Narrow observability API's CORS origin from wildcard for non-loopback overrides (CER-42)
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

CER-42 (LOW): `skills/observability/api/src/server.ts` registers `@fastify/cors` with
`origin: '*'` (line 35). This is acceptable when the server is bound to the default `127.0.0.1`
(browser same-origin restrictions don't apply to loopback, and a local dev tool has no secret to
protect), but risk activates if an operator sets `FLEX_OBS_HOST=0.0.0.0` to expose the server on a
LAN or remote interface — the wildcard origin would then let any website read all registered
repos' context data, effort metrics, and file paths via cross-origin requests. Fix: narrow
`origin` to an explicit allowed-origins list when `FLEX_OBS_HOST != "127.0.0.1"`, or document the
loopback-only constraint in the SKILL.md serve notes and warn to stderr on a non-loopback host
override. File/line: `skills/observability/api/src/server.ts:35`. From the Phase 63 security
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
