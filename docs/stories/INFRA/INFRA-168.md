---
id: INFRA-168
rail: INFRA
title: "`effortDb.ts` p90 off-by-one + in-flight promise dedup for route cache thundering herd"
status: planned
phase: "HARNESS007-main"
story_class: code
primary_files:
  - skills/observability/api/src/readers/effortDb.ts
  - skills/observability/api/src/routes/system.ts
  - skills/observability/api/src/routes/context.ts
  - skills/observability/api/src/routes/lessons.ts
touches:
  - tests/pairmode/test_observability_context_api.py
---

# INFRA-168 — `effortDb.ts` p90 off-by-one + route cache thundering herd

## Context

Two bugs from the Phase 63 cold-eyes review (findings 6, 12).

1. **`effortDb.ts:104` sqliteP90 off-by-one.** `OFFSET Math.floor(n * 0.9)`
   returns the maximum value (not p90) when `n * 0.9` is a whole number.
   For n=10: `floor(9)=9` → OFFSET 9 → 10th element (= max). Correct
   nearest-rank p90 for n=10 is index 8 (`ceil(0.9 × 10) − 1 = 8`).
   The error surfaces for any phase with 10, 20, 30, … attempts.

2. **Route cache thundering herd.** `system.ts`, `context.ts`, and
   `lessons.ts` all use the pattern:
   ```typescript
   if (cached && now - cached.ts < CACHE_TTL_MS) return cached.data;
   const data = await buildPayload(...);
   cache.set(id, { ts: Date.now(), data });
   ```
   Two concurrent requests during a cache miss both execute `buildPayload`
   in parallel — no in-flight deduplication exists. On a project with 63
   phase docs this doubles disk I/O on every burst.

## Ensures

### `skills/observability/api/src/readers/effortDb.ts`

1. Fix `sqliteP90`:
   ```typescript
   // was:
   const offset = Math.floor(n * 0.9);
   // becomes:
   const offset = Math.max(0, Math.ceil(n * 0.9) - 1);
   ```
   Verification table:
   | n  | old OFFSET | new OFFSET | correct index (0-based) |
   |----|-----------|-----------|------------------------|
   | 10 | 9 (wrong) | 8         | 8                      |
   | 11 | 9         | 9         | 9                      |
   | 20 | 18 (wrong)| 17        | 17                     |
   | 1  | 0         | 0         | 0                      |

   The `sqliteMedian` function is not changed.

### `skills/observability/api/src/routes/system.ts`
### `skills/observability/api/src/routes/context.ts`
### `skills/observability/api/src/routes/lessons.ts`

2. Add a module-level `inflight` Map alongside each existing `cache` Map:
   ```typescript
   const inflight = new Map<string, Promise<SystemOut>>();   // (or ContextOut / LessonsOut)
   ```

3. Replace the cache-miss / build / cache-set sequence with:
   ```typescript
   const now = Date.now();
   const cached = cache.get(id);
   if (cached && now - cached.ts < CACHE_TTL_MS) {
     return cached.data;
   }

   const existing = inflight.get(id);
   if (existing) return existing;

   const promise = buildPayload(repo.project_dir, id)
     .then((data) => {
       cache.set(id, { ts: Date.now(), data });
       inflight.delete(id);
       return data;
     })
     .catch((err) => {
       inflight.delete(id);
       throw err;
     });

   inflight.set(id, promise);
   return promise;
   ```
   The pattern is identical in all three route files; only the type
   parameters and `buildPayload` function names differ.

4. The `inflight` Map is never persisted and has no TTL — entries are
   deleted immediately when the promise resolves or rejects. This is correct
   because a resolved promise's result is immediately stored in `cache`.

### `tests/pairmode/test_observability_context_api.py`

5. New test cases:

   - **`test_p90_correct_for_round_n`** — insert exactly 10 attempt rows
     into a tmp effort.db with `tokens_total` values `[10, 20, ..., 100]`.
     Call `queryEffortSummary` (or trigger it via the `/context` endpoint).
     Assert `p90_tokens` in the response equals 90 (the 9th element,
     0-based index 8), not 100 (the maximum).

   - **`test_p90_correct_for_odd_n`** — insert 11 rows with
     `tokens_total` in `[10, 20, ..., 110]`. Assert `p90_tokens == 100`
     (index 9 = `ceil(11 * 0.9) - 1 = ceil(9.9) - 1 = 10 - 1 = 9`).

6. The thundering herd fix is verified implicitly by the build gate (no
   TypeScript runtime test harness exists for concurrent HTTP in the Python
   test suite). A code-review assertion: confirm that `inflight` Map is
   present in all three route files and that `.catch` deletes the entry.

7. All existing tests continue to pass.

## Instructions

- `effortDb.ts`: the fix is one line. Do not alter `sqliteMedian`.
- Route files: the `inflight` Map declaration and the promise-wrapping
  pattern are the only changes. The `buildPayload` calls, error handling,
  and 404 logic are unchanged.
- The `inflight` Map is typed with the same payload type as the `cache`
  Map entry's `data` field, but wrapped in `Promise<T>`.
- Return type of the route handler already returns `Promise` implicitly
  (Fastify async handlers); returning the in-flight promise is valid.
- Apply the pattern identically across all three route files — do not add
  a shared helper abstraction (YAGNI: three usages do not warrant one yet).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_observability_context_api.py -x -q
```

All tests must pass.

## Out of scope

- Bounding the cache size or adding TTL-based eviction (Low severity, not
  in the 15 findings).
- Sharing the `inflight` / `cache` state across route files.
- `sqliteMedian` correctness (no finding against it).
