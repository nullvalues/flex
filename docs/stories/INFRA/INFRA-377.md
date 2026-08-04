---
id: INFRA-377
rail: INFRA
title: Gate abs_path disclosure in observability API GET responses (CER-43)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/observability/api/src/routes/user.ts
touches:
  - docs/cer/backlog.md
  - skills/observability/api/tests/user.test.ts
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

- No prior story in this phase. `skills/observability/api/src/routes/user.ts` exists and its
  `GET /api/user/memories` and `GET /api/user/policies` handlers currently emit `abs_path`.
- INFRA-378 (CER-42, CORS narrowing) touches the same package but a different module; no ordering
  constraint, but do not fold its change into this diff.

## Ensures

1. `GET /api/user/memories` and `GET /api/user/policies`, called with no query parameters, return
   entries that contain **no** `abs_path` key at all. Correct signal: the key is absent from the
   serialized JSON. Forbidden proxy: `abs_path` present but blanked/redacted to `""`, `null`, or a
   masked string — the field must not be emitted, not emitted-then-scrubbed.
2. Called with `?include_path=true`, both endpoints return the same entries **with** `abs_path`
   populated with the same absolute path value they return today (opt-in restores the old shape
   exactly; no other field changes between the two modes).
3. Any value of `include_path` other than the literal `true` (absent, `false`, `1`, `TRUE`,
   garbage) yields the omitting behaviour of Ensures 1 — the default is closed, and only an exact
   opt-in opens it.
4. No caller inside this repo reads `abs_path` from these two responses without passing
   `include_path=true`. Correct signal: a repo-wide search for `abs_path` in the observability UI
   sources returns either no hits or only hits on a request path that sets the flag. Forbidden
   proxy: leaving a UI read of `abs_path` intact and relying on it rendering `undefined`.
5. The observability API's own test suite (whatever `skills/observability/api` already declares as
   its test script) passes, and includes at least one new assertion covering the default-omit case
   and one covering the `include_path=true` case, for both endpoints.
6. `tests/pairmode/` suite green.
7. `docs/cer/backlog.md`'s CER-43 entry is marked resolved, citing INFRA-377.

## Instructions

1. Read `skills/observability/api/src/routes/user.ts` (CER-43 cites lines 15, 37, 126, 160 — the
   two list-building sites and the two response-shaping sites). Confirm the actual current shape
   before editing; the line numbers are from the Phase 63 audit and may have drifted.
2. Implement the gate as an opt-in query parameter, not an unconditional removal: parse
   `include_path` from the request query, treat only the exact string `true` as enabled, and build
   the response entry with `abs_path` present only when enabled. Prefer omitting the key at
   construction over deleting it afterward, so no code path can leak it.
3. Keep the change local to these two GET handlers. Do not change the request/response shape of any
   other route in the file, and do not alter what `abs_path` contains when opted in.
4. Update any in-repo consumer that reads `abs_path` from these endpoints (observability UI
   sources) to either stop using it or request it explicitly. If no consumer reads it, say so in
   the build note rather than leaving Ensures 4 unaddressed.
5. Add the tests described in Ensures 5 to the observability API's existing test file for these
   routes; do not create a parallel test harness.
6. Update `docs/cer/backlog.md`'s CER-43 entry to resolved, citing this story ID.
7. Preflight note: `spec-preflight` warns about a route `/api/src/routes/user` — that is the scanner
   mis-parsing the file path `skills/observability/api/src/routes/user.ts` as a route reference, not
   a real hallucinated route. Left as-is.
8. Ideology note: the opt-in gate rather than a silent removal was chosen to preserve the
   "explicit configuration over inferred defaults" conviction — the disclosure becomes a stated
   request, and the default is closed.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: green.

Plus the observability API's own suite, run with whatever command that package already declares
(check its `package.json` test script rather than assuming a runner):

```bash
cd skills/observability/api && <declared test command>
```

Acceptance: green, including the four new assertions from Ensures 5 (default-omit and
`include_path=true`, for each of the two endpoints).

## Out of scope

- CORS origin narrowing for the observability API — that is INFRA-378 (CER-42), a separate story in
  this phase.
- Any authentication or authorization layer on the observability API. This story gates one field
  behind an explicit query parameter; it does not introduce access control, and a client that can
  reach the endpoint can still opt in.
- Auditing other observability routes for path disclosure. CER-43 names exactly these two GETs;
  widening the sweep belongs in its own CER.
