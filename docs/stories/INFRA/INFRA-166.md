---
id: INFRA-166
rail: INFRA
title: "Fastify API route hardening — null project_dir crash, 0-token divergence, NaN threshold, flex_factor live read"
status: backlog
phase: "64"
story_class: code
primary_files:
  - skills/observability/api/src/routes/repos.ts
  - skills/observability/api/src/routes/context.ts
  - tests/pairmode/test_observability_context_api.py
touches:
  - skills/observability/api/src/routes/system.ts
---

# INFRA-166 — Fastify API route hardening

## Context

Four bugs in the Fastify API routes, found in the Phase 63 cold-eyes review
(findings 1, 7, 8, 11). INFRA-167 must land first — this story depends on the
fixed `storyFrontmatter.ts` parser for finding 7.

1. **`repos.ts:28` null crash.** If a registry entry has `project_dir: null`
   (hand-edited JSON), `path.join(null, ...)` throws
   `ERR_INVALID_ARG_TYPE` and the entire `/api/repos` response 500s — all
   healthy repos become invisible.

2. **`context.ts:162` flex_factor hardcoded.** The threshold triple for
   `flex_factor` always returns `value: 1.0` with `source: "story-frontmatter"`,
   regardless of what the current story's frontmatter actually declares. The
   source label is a lie.

3. **`context.ts:121` 0-token divergence.** `typeof 0 === 'number'` is true,
   so the TS route treats `context_current_tokens: 0` as a valid recording.
   Python's `read_context_tokens_from_state` returns `None` for `val <= 0`.
   The SPA shows "0 tokens, not stale" while the context gate is blocking
   every Task spawn.

4. **`context.ts:177` NaN threshold.** `typeof NaN === 'number'` is true, so
   a NaN threshold value passes the type guard and propagates into SQLite
   queries where `tokens_total > NaN` always evaluates to false — the misses
   count is silently reported as zero.

## Ensures

### `skills/observability/api/src/routes/repos.ts`

1. The repo-list loop wraps the per-entry `path.join` + `fs.existsSync` in a
   try/catch. On error for one entry, that entry's `state_json_present` is
   set to `false` and the loop continues; the error is logged to `console.error`
   with the repo id. One bad entry never crashes the whole endpoint.

   ```typescript
   let stateJsonPresent = false;
   try {
     const statePath = path.join(r.project_dir, '.companion', 'state.json');
     stateJsonPresent = fs.existsSync(statePath);
   } catch {
     console.error(`[repos] failed to probe state.json for ${r.id}`);
   }
   ```

### `skills/observability/api/src/routes/context.ts`

2. **flex_factor live read.** The `buildThresholds` function is updated to
   accept `projectDir: string` and `stateObj: Record<string, unknown>`. When
   building the `flex_factor` threshold entry it:
   - Reads `stateObj['current_story']` to get `{id, rail}`.
   - Constructs the story path:
     `path.join(projectDir, 'docs', 'stories', rail, `${id}.md`)`.
   - Parses the file with `parseStoryFrontmatter` (from INFRA-167's fixed
     parser).
   - Uses the returned `flex_factor` (already a validated float, default 1.0)
     as the threshold `value`. Sets `source` to `"story-frontmatter"` when
     a story is active and the file exists, or `"default"` otherwise.
   - On any I/O or parse error: falls back to `value: 1.0`,
     `source: "story-frontmatter (fallback)"`.
   - `buildThresholds` is called with `projectDir` and `stateObj` from the
     route handler (both are already in scope).

3. **0-token guard.** The `current` block changes the type guard:
   ```typescript
   // was:
   typeof state['context_current_tokens'] === 'number'
   // becomes:
   typeof state['context_current_tokens'] === 'number' &&
   (state['context_current_tokens'] as number) > 0
   ```
   A zero value is treated the same as absent (tokens: null).

4. **NaN threshold guard.** The threshold value extraction changes:
   ```typescript
   // was:
   const value = typeof rawValue === 'number' ? rawValue : def.default;
   // becomes:
   const value =
     typeof rawValue === 'number' && !Number.isNaN(rawValue)
       ? rawValue
       : def.default;
   ```

### `tests/pairmode/test_observability_context_api.py`

5. New test cases (use the existing `tmp_project` fixture pattern):

   - **`test_repos_null_project_dir_does_not_500`** — write a registry with
     one valid entry and one entry with `"project_dir": null`. Assert
     `/api/repos` returns 200 and the response contains the valid repo; the
     null entry is absent or has `state_json_present: false`.

   - **`test_context_zero_tokens_treated_as_absent`** — write `state.json`
     with `"context_current_tokens": 0`. Assert `/api/repos/:id/context`
     returns `current.tokens: null`.

   - **`test_context_nan_threshold_falls_back_to_default`** — write
     `state.json` with `"context_budget_threshold": null` (JSON null, which
     the TS reader handles via `typeof null !== 'number'` — already correct —
     so additionally test with a registry-modified approach if possible; at
     minimum document the expected default). Assert threshold row for
     `context_budget_threshold` returns `value: 120000` (default).

   - **`test_context_flex_factor_reads_story_frontmatter`** — write
     `state.json` with `"current_story": {"id": "INFRA-999", "rail": "INFRA",
     "phase": "64"}` and create
     `docs/stories/INFRA/INFRA-999.md` with `flex_factor: 1.5` in
     frontmatter. Assert `/api/repos/:id/context` threshold row for
     `flex_factor` returns `value: 1.5` and `source: "story-frontmatter"`.

   - **`test_context_flex_factor_fallback_when_no_story`** — write `state.json`
     with no `current_story`. Assert flex_factor threshold row returns
     `value: 1.0` and `source: "default"`.

6. All existing tests in `test_observability_context_api.py` continue to pass.

## Instructions

- `repos.ts`: the try/catch wraps only the `path.join` + `fs.existsSync`
  block; the rest of the entry (name, color, id) is still included in the
  response.
- `context.ts`: `buildThresholds` currently receives no arguments (it closes
  over module-level state). Change it to a pure function that accepts
  `projectDir` and `stateObj`. Update the one call site in `buildContextPayload`.
- Import `parseStoryFrontmatter` from `'../parsers/storyFrontmatter'` (the
  same parser used by `system.ts`).
- The story file read inside `buildThresholds` is a synchronous `fs.readFileSync`
  (consistent with all other parsers in the codebase). Wrap in try/catch.
- Do not add a new cache layer for the story frontmatter read — it is one
  small file read per context request and is already inside the 2s route cache.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_observability_context_api.py -x -q
```

All tests must pass.

## Out of scope

- Surfacing the null-project_dir entry in the SPA with a visual error badge.
- Validating the full registry schema on load (field-type validation per entry).
- Any write routes (Phase 65).
