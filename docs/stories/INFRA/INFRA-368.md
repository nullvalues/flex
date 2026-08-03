---
id: INFRA-368
rail: INFRA
title: Fix resolverState.ts getFlexBuildPath() resolving one directory too high (CER-142)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/observability/api/src/readers/resolverState.ts
touches:
  - skills/observability/api/tests
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

- `skills/observability/api/src/readers/resolverState.ts` exists and `getFlexBuildPath()` still
  builds its path with an extra `..` segment before `'pairmode'`. If the bug is already absent,
  stop and report the story as already resolved rather than inventing a change.
- The observability API package's dependencies are installed in the working checkout (do not run
  a fresh package install inside a story worktree; copy the existing payload if it is missing).
- No ordering dependency on other Phase 119 stories — no other story in the phase declares
  `skills/observability/api/src/readers/resolverState.ts`.

## Ensures

- `getFlexBuildPath()` returns an absolute path whose tail is
  `skills/pairmode/scripts/flex_build.py`. Forbidden proxy: a path whose tail is
  `pairmode/scripts/flex_build.py` with no `skills/` component immediately before it.
- The `path.join(...)` expression inside `getFlexBuildPath()` contains no `..` segment between
  the base directory variable and `'pairmode'`.
- A test in the observability API package asserts that the path returned by `getFlexBuildPath()`
  actually exists on disk (`fs.existsSync(...) === true`). Forbidden proxy: a test that compares
  the returned path against an expected string assembled by re-running the same `path.join`
  expression the source uses — that passes for both the broken and the fixed form.
- `readResolverState()` returns a non-null object when invoked from this repo checkout.
  Forbidden proxy: it still returns `null` while a warning/debug line is emitted about the
  failed spawn.
- The observability API package's test suite passes.
- `uv run pytest tests/pairmode/` passes (no regression in the Python suite).

## Instructions

1. In `skills/observability/api/src/readers/resolverState.ts`, change `getFlexBuildPath()`'s
   final join from `path.join(obsApiDir, '..', 'pairmode', 'scripts', 'flex_build.py')` to
   `path.join(obsApiDir, 'pairmode', 'scripts', 'flex_build.py')`.
2. Before assuming only the trailing `..` is wrong, confirm the hop count that produces
   `obsApiDir` against the module's *runtime* location. The `..` hops are counted from
   `import.meta.url`; if the API is executed from a compiled output directory rather than
   `src/readers/`, the base hop count is also wrong and must be corrected in the same edit.
   Whatever the runtime layout, the assertion in `## Ensures` is the contract: the returned
   path must resolve to the real `flex_build.py` on disk.
3. Add or extend a test in the API package's test directory that calls the path resolution and
   asserts the file exists. An existence assertion is the only form that distinguishes the
   broken path from the fixed one; a string-equality assertion built from the same join does not.
4. Keep `readResolverState()`'s failure contract unchanged — it still returns `null` when the
   subprocess genuinely fails. This story fixes the path, not the error-handling policy.
5. This is a read path only. Do not add any state write, cache file, or persisted artifact while
   fixing it — "sidebar owns all state writes" (`docs/ideology.md`, Accepted constraints) applies
   to the observability readers as much as to the hooks.
6. Ideology note (4a-iii): the "Python everywhere" fingerprint is marked *Conditional*, and the
   observability API is an already-accepted TypeScript exception to it. This story edits inside
   that existing exception and must not widen it — no new non-Python surface.
7. Scope note for the operator: this story's frontmatter carries no `primary_files:` and an empty
   `touches:`, yet the fix necessarily edits
   `skills/observability/api/src/readers/resolverState.ts` plus a test file in the same package.
   The spec-writer may not edit frontmatter, so the declared scope must be filled in by a human
   before this story is dispatched to a builder. `spec-preflight` reports three `scope:`
   findings on this story: `resolverState.ts` (real — the file this story edits, and the one
   whose declared scope is missing), `skills/pairmode/scripts/flex_build.py` (intentional — it is
   the *target* of the resolved path, never edited), and `docs/ideology.md` (intentional — cited
   as the source of the constraint in step 5, never edited).

## Tests

```bash
# Python suite — regression only
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

```bash
# Observability API package suite (the package's own `test` script, run from its directory)
cd skills/observability/api && <package manager> test
```

Acceptance: both suites green, and the new/extended test that asserts
`fs.existsSync(getFlexBuildPath()) === true` passes. Sanity check that the test is real: revert
the one-character fix, confirm the new test fails, then restore the fix.

## Out of scope

- Any other reader under `skills/observability/api/src/readers/` — only `resolverState.ts` is fixed
  here, even if a sibling reader uses a similar path-hop idiom (file a CER if one is spotted).
- Changing `readResolverState()`'s null-on-failure contract, or adding logging/telemetry so that
  silent spawn failures become visible. That is a separate, real gap — this story only removes
  the specific cause.
- The `/api/repos/:id/system` and `/api/repos/:id/context` route handlers and `context.ts`'s
  `current.story_id`/`current.phase` fields. They are the observable *symptom* of this bug and
  should recover on their own once the path resolves; they are not edited here.
