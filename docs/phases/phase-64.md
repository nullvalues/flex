---
era: "002"
---

# flex — Phase 64: Observability SPA hardening — cold-eyes review fixes

← [Phase 63: Observability SPA — read-only window glass](phase-63.md)

**Parent phase:** Phase 63 left behind zero deferred stories; this phase is a clean follow-on.

## Goal

Resolve all 15 findings from the Phase 63 cold-eyes review. No new features —
purely correctness, safety, and data-quality fixes across the Python CLI, the
Python context budget module, the Fastify API routes, and the TypeScript parsers.

## Decisions recorded

**D1 — NaN guard placement:** `math.isnan()` check is inserted *before* the
`<= 0` guard in `decide()` so NaN is caught first; the existing two guards
follow unchanged. This is the minimal addition.

**D2 — render_alert_prompt ceiling:** `flex_factor` is added as an optional
parameter (`default 1.0`) and threaded through the caller in `decide()`. The
function is not renamed — callers outside `decide()` are unaffected.

**D3 — Atomic write tmp uniqueness:** Use
`tempfile.NamedTemporaryFile(dir=path.parent, delete=False, suffix='.tmp')`
so each process gets a unique name; `os.replace` then promotes it. This is
the standard POSIX idiom and preserves the same-filesystem guarantee.

**D4 — ID uniqueness enforcement in register:** If a requested `--name` is
already in use by a *different* `project_dir`, `register` prints an error and
exits 1. Registering the same `(name, project_dir)` pair remains idempotent
(exit 0, "already registered").

**D5 — flex_factor in /context threshold row:** The context route reads
`state.json["current_story"]["id"]` to locate the story file and parse its
`flex_factor` frontmatter. On any read/parse failure the route falls back to
the default `1.0` with `source: "story-frontmatter (fallback)"`.

**D6 — phaseIndex.ts blank-line behaviour:** Replace `break` with `continue`
for blank/whitespace-only lines inside the table body. A non-pipe, non-blank
line (a heading like `## `) still breaks. This matches the authoring pattern
where blank dividers appear between groups of rows.

**D7 — thundering herd fix scope:** A module-level `inflight` Map stores the
in-flight `Promise<T>` while a build is running; subsequent cache-miss
requests for the same repo_id await the same promise instead of spawning a
new build. Applied to all three cached routes (system, context, lessons).

**D8 — sqliteP90 formula:** Change `Math.floor(n * 0.9)` to
`Math.max(0, Math.ceil(n * 0.9) - 1)`. For n=10: `ceil(9)−1=8` → OFFSET 8
→ 9th element (0-based) which is the correct nearest-rank p90.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-164 | `flex_observability.py` CLI hardening — subprocess exit, atomic write, ID uniqueness | planned |
| INFRA-165 | `context_budget.py` flex_factor correctness — NaN clamp + `render_alert_prompt` ceiling | planned |
| INFRA-167 | TypeScript parser robustness — phaseIndex blank-line, MODULE_FILENAME_RE, era leading zeros, flex_factor NaN | planned |
| INFRA-166 | Fastify API route hardening — null project_dir, 0-token divergence, NaN threshold, flex_factor live read | planned |
| INFRA-168 | `effortDb.ts` p90 off-by-one + in-flight promise dedup for route cache thundering herd | planned |

**Dependency note:** INFRA-166 is listed after INFRA-167 because the context
route's flex_factor live-read (finding 7) calls `parseStoryFrontmatter`, which
is fixed in INFRA-167. All other stories are independent.

## Tag

`cp64-obs-hardening`
