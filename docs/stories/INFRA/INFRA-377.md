---
id: INFRA-377
rail: INFRA
title: Gate abs_path disclosure in observability API GET responses (CER-43)
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

CER-43 (LOW): `GET /api/user/memories` and `GET /api/user/policies` return an `abs_path` field
containing the absolute filesystem path of each memory/policy file (e.g.
`/home/username/.claude/projects/-mnt-work-flex/memory/user_role.md`), disclosing the operator's
home directory path, username, and directory structure to any client that can reach the API. In
the default loopback-only configuration this is low-risk (only the local user can reach the
endpoint), but the risk activates when the server is exposed beyond loopback. Fix: either omit
`abs_path` from the response (the UI can reconstruct relative paths) or gate it behind a separate
`?include_path=true` query parameter. File/lines: `skills/observability/api/src/routes/user.ts:15,37,126,160`.
From the Phase 63 security audit.

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
