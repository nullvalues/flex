---
id: INFRA-378
rail: INFRA
title: Narrow observability API's CORS origin from wildcard for non-loopback overrides (CER-42)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/observability/api/src/server.ts
  - skills/observability/api/tests/cors.test.ts
  - skills/observability/SKILL.md
narrative_roles: []
model: sonnet  # lower: single-file conditional + one test file, low complexity
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

- `skills/observability/api/src/server.ts` registers `@fastify/cors` with a literal
  `origin: '*'`, and `skills/observability/api/tests/cors.test.ts` exists and passes.
- No ordering dependency on other Phase 119 stories. INFRA-377 (CER-43) also edits
  `server.ts`-adjacent route code; if both are in flight, build serially to avoid a
  spurious conflict.

## Ensures

- `skills/observability/api/src/server.ts` contains no unconditional `origin: '*'` —
  the value passed to `fastify.register(cors, ...)` is computed from `FLEX_OBS_HOST`.
- When `FLEX_OBS_HOST` is unset or a loopback value (`127.0.0.1`, `::1`, `localhost`),
  the registered origin is the wildcard (behaviour unchanged for the default local case).
- When `FLEX_OBS_HOST` is any non-loopback value and `FLEX_OBS_ALLOWED_ORIGINS` is unset
  or empty, the registered origin denies all cross-origin requests (`false`), and exactly
  one warning line naming both env vars is written to stderr at startup.
  Forbidden proxy: a stderr warning emitted while the wildcard origin is still registered.
- When `FLEX_OBS_HOST` is non-loopback and `FLEX_OBS_ALLOWED_ORIGINS` is set to a
  comma-separated list, the registered origin is exactly that list parsed into an array of
  trimmed non-empty strings — no wildcard entry is added.
- `skills/observability/api/tests/cors.test.ts` asserts all four cases above, keyed on the
  resolved origin value itself (not on log output).
- `skills/observability/SKILL.md`'s serve notes state that the API is loopback-only by
  default and that a non-loopback `FLEX_OBS_HOST` requires `FLEX_OBS_ALLOWED_ORIGINS`.
- `pnpm --dir skills/observability/api test` exits 0.

## Instructions

1. In `server.ts`, extract the origin decision into a small exported pure helper (e.g.
   `resolveCorsOrigin(host, allowedOrigins)`) returning the value handed to
   `@fastify/cors`, so the tests can assert it without booting a server. Keep the existing
   `FLEX_OBS_HOST` default resolution where it already lives; the helper takes the resolved
   host as input.
2. Decision table: loopback host -> `'*'`; non-loopback with a non-empty allowlist -> the
   parsed array; non-loopback with no allowlist -> `false`. Treat `127.0.0.1`, `::1`, and
   `localhost` as loopback; everything else (including `0.0.0.0`) as non-loopback.
3. Emit the stderr warning only in the non-loopback + no-allowlist case, from the server
   startup path (not from inside the pure helper), naming both `FLEX_OBS_HOST` and
   `FLEX_OBS_ALLOWED_ORIGINS` and stating that cross-origin access is disabled.
4. Add the four cases to `cors.test.ts`, reusing that file's existing setup style.
5. Update the serve notes in `skills/observability/SKILL.md` with the loopback-only default
   and the `FLEX_OBS_ALLOWED_ORIGINS` escape hatch, including why (a LAN-exposed wildcard
   would let any site read registered repo paths and metrics).

Ideology note (Step 4a): the deny-by-default + documented env-var override shape was chosen
over a silent permissive fallback to preserve "codify policy over implicit convention" and
"rationale-bearing decisions" — the override exists, is named, and carries its reason in
SKILL.md rather than living as an undocumented behaviour of the wildcard.

## Tests

```bash
pnpm --dir skills/observability/api test
```

Acceptance: the observability API vitest suite is green, including the four new
`cors.test.ts` cases. No Python test change is expected for this story.

Preflight note: `spec-preflight` reports two route warnings for `/api/src/server` and
`/api/tests/cors` — both are file-path fragments of the declared `touches:` paths, not HTTP
routes. Expected and intentional.

## Out of scope

- Authentication or bearer-token gating of the observability API — CORS narrowing is not
  an authorization mechanism and this story does not add one.
- `abs_path` disclosure in GET responses (INFRA-377 / CER-43) — separate story, same file
  neighbourhood.
- Binding-behaviour changes to `FLEX_OBS_HOST` itself, or any change to the UI's dev-server
  proxy configuration.
