---
id: INFRA-312
rail: INFRA
title: Observability UI functional validation — dogfood checklist over ≥2 registered repos plus a scoped TypeScript route-test runner
status: complete
phase: "115"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/observability/api/package.json
  - docs/stories/INFRA/INFRA-312.md
touches:
  - skills/observability/api/src/server.ts
  - skills/observability/api/src/routes/repos.ts
  - skills/observability/api/src/routes/context.ts
  - skills/observability/api/src/routes/lessons.ts
  - skills/observability/api/src/routes/system.ts
  - skills/observability/api/src/routes/user.ts
  - skills/observability/pnpm-lock.yaml
  - skills/observability/pnpm-workspace.yaml
  - skills/observability/SKILL.md
  - docs/cer/backlog.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The observability SPA is the era's stated beta deliverable, and under the
pre-revision plan it would have shipped in 0.3.1 without ever being
functionally exercised (cold-eyes F6): the only validating story (INFRA-278)
sits in orphaned phase 108, there is no TypeScript test runner at all, and the
existing coverage is Python source-text assertions plus a `pnpm build` compile
gate. "It compiles" is not "it works".

AG-2 (`docs/closeout-agreements-20260729.md`) resolves this with both halves:

1. **A manual dogfood checklist** — the SPA served against **≥ 2 registered
   repos**, every route exercised, evidence pasted into this story file. This
   absorbs INFRA-278's validation obligation (phase 108 is not revived —
   AG-3/INFRA-310 disposition it).
2. **A TypeScript test runner** (vitest or equivalent), deliberately beyond
   the review's minimal floor so validation is *repeatable* — scoped to the
   five existing API routes (`repos`, `context`, `lessons`, `system`, `user`;
   `skills/observability/api/src/routes/`). Smoke/route-level coverage, not a
   coverage crusade.

**The correct signal for this story is route responses observed against real
registered-repo data, plus a runnable `pnpm test` that exercises the same
routes in-process. The forbidden proxy is a green `pnpm build` / `tsc` pass,
or screenshots of the SPA shell with no data loaded — neither may be cited as
validation evidence.**

## Requires

1. The API is a Fastify app (`skills/observability/api/src/server.ts`,
   `@fastify/cors` in `package.json`) with routes registered from
   `src/routes/{repos,context,lessons,system,user}.ts`. `package.json:8-12`
   has `dev` / `build` / `start` scripts and **no `test` script** today.
2. Registered projects come from the registry (`src/registry.ts`); flex
   itself plus at least one other repo are registered on the operator's
   machine (the `flex:observability` skill documents startup). If fewer than
   2 repos are registered at build time, registering a second is part of the
   dogfood run, not a blocker.
3. INFRA-306 (loopback-honest CORS, abs_path gating) is a phase-115 sibling
   that changes API behaviour this story observes — **build after INFRA-306**
   so the checklist validates the shipped behaviour, and after INFRA-309
   (rollup exclusions) for the same reason.
4. Vendored `node_modules` is present (`skills/observability/node_modules`)
   and known-incomplete for some flows (CER-090 history). The runner must
   install its own dev-dependency via pnpm inside the workspace; if the
   sandbox blocks network install, **stop and report** rather than vendoring
   by hand.
5. Baseline: 4116 passed / 211 skipped (Python); no TS test baseline exists —
   this story creates it.

## Ensures

1. **`pnpm test` exists and runs the route suite.**
   `skills/observability/api/package.json` gains a `"test"` script invoking
   vitest (or the chosen equivalent, one line of justification in the story
   evidence if not vitest). Run from `skills/observability/api/`, it exits 0
   with ≥ 1 test file per route (5 minimum).
2. **Route smoke tests are in-process and data-shaped.** Each route test
   boots the Fastify app (injection, not a live port), hits the route, and
   asserts (a) HTTP 200 on the happy path against a fixture project dir,
   (b) the response's top-level shape (keys/types), and (c) one
   failure-shaped case (missing/unregistered repo → the route's documented
   error status, not a crash). **Forbidden proxy: asserting only
   `statusCode === 200` with no body-shape assertion.**
3. **CORS/loopback behaviour pinned.** One test asserts the INFRA-306
   contract (loopback-only origin behaviour) as shipped, so the hardening
   story's behaviour has an executing TS guard.
4. **The dogfood checklist is executed and evidenced.** This story file
   gains a `## Evidence` section containing: the serve command(s) used, the
   ≥ 2 registered repo names, and for each SPA route/view — repos list,
   context budget, effort/story status, lessons, system — the actual
   observed output (curl response excerpt or described rendered state with
   concrete values, e.g. real story IDs and token counts, not "looks fine").
   Every claim names the repo it was observed against.
5. **A defect found is a defect filed.** Any misbehaviour observed during
   the dogfood run is either fixed in-scope (if a one-line route fix) or
   filed as a CER row with severity — the checklist cannot pass by omission.
   The `## Evidence` section states explicitly "defects found: N, filed:
   CER-…" (N may be 0).
6. **No Python regression.** Full Python suite without `-x`: baseline holds.
   The TS runner does not alter `pnpm build` behaviour (`pnpm build` still
   green).
7. **Runner is wired for siblings, not just this story.** A one-paragraph
   note in `skills/observability/SKILL.md` states how to run the TS suite,
   so cp-115's checkpoint and future stories can invoke it.
   (`skills/observability/api/README.md` does not exist; SKILL.md is the
   skill's documented surface and is in `touches:` — do not create a new
   README for this.)

## Instructions

1. Build after INFRA-306 and INFRA-309 (Requires 3).
2. Add vitest as a devDependency in the api workspace; wire `"test"`.
3. Write the five route smoke files against a fixture project dir (a minimal
   `docs/`+`.companion/` tree checked into the test fixtures, or generated in
   a temp dir at test time — not the live flex repo, so tests are hermetic).
4. Run the dogfood checklist against the live SPA with ≥ 2 registered repos;
   paste evidence (Ensures 4); file any defects (Ensures 5).
5. Do not expand scope into UI component testing, e2e browser automation, or
   coverage thresholds — route-level smoke is the agreed floor and ceiling
   for 0.3.1 (AG-2: "not a coverage crusade").

## Tests

```bash
cd skills/observability/api && pnpm test
cd skills/observability/api && pnpm build
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: TS suite green with ≥ 5 route test files; build green; Python
baseline held. Reviewer negative checks: (a) the Evidence section names ≥ 2
repos and cites concrete observed values; (b) no evidence line rests on
`pnpm build` or a screenshot of an empty shell (the forbidden proxy); (c) the
failure-shaped case in each route test asserts a handled status, not a thrown
exception.

## Out of scope

- Browser/e2e automation and UI component tests.
- Coverage thresholds or a coverage tool.
- Fixing INFRA-278/279's phase-108 record — INFRA-310 dispositions phase 108;
  this story only absorbs the *validation* obligation.
- Any new API route or UI feature.

## Scope widenings

Files touched beyond the frontmatter `primary_files`/`touches` declarations,
each an inherent consequence of "add a TS test runner" that could not be
named in advance at spec time:

| File | Reason |
|---|---|
| `skills/observability/api/vitest.config.ts` | New file — the test runner's own config (scopes test discovery to `tests/**`, pins `cacheDir`). |
| `skills/observability/api/tests/**` | New files — the five route smoke-test files plus the fixture-project helper (Ensures 1/2/3). |
| `skills/observability/api/node_modules/**`, `skills/observability/node_modules/**` | Vendored payload for the new `vitest` devDependency (and its transitive deps, hoisted into the workspace root per CER-090/INFRA-261's tracked-`node_modules` convention) — the necessary payload half of adding a devDependency declared in the already-in-scope `package.json`. |
| `.gitignore` | One new entry ignoring `skills/observability/api/node_modules/.vitest-cache/` (vitest's own run cache), same precedent as INFRA-302's `tsconfig.tsbuildinfo` entry — required so `pnpm test` does not dirty a future story worktree. |
| `tests/pairmode/test_vendored_payload_tracked.py` | One-line allow-list addition for the `.vitest-cache/` path above (category 6) — the guard test that enforces the vendored-payload/CER-090 policy needed updating to recognise the new, deliberately-ignored cache path as a category-3-shaped exception, not a CER-090 regression. |

## Evidence

**Serve command used:**
```
cd skills/observability/api && FLEX_OBS_PORT=7778 ./node_modules/.bin/tsx src/server.ts
```
(dev-mode tsx, loopback bind `127.0.0.1` — the default.)

**Registered repos exercised (3, all pre-existing on the operator's registry,
`~/.config/flex-observability/registry.json`):** `radar` (`/mnt/work/radar`),
`forqsite` (`/mnt/work/forqsite`), `flex` (`/mnt/work/flex`).

**Repos list** (`GET /api/repos`): returned all three, each
`state_json_present: true` — `radar`, `forqsite`, `flex` all have a live
`.companion/state.json`.

**Context budget** (`GET /api/repos/:id/context`):
- `radar`: `current.tokens = 25000`, `current.stale = true` (recorded_at
  ~2 days old), `context_budget_overrun_pct = 0.25` (a real per-project
  override, `source: "state.json"`, vs. the `0.10` default).
- `forqsite`: `current.tokens = 109485`, `current.stale = false` (recorded
  86s before the request), `context_budget_threshold = 150000` (also a
  per-project override).
- `flex`: `current.tokens = 272519`, `current.stale = true`,
  `effort_summary.total_attempts` and `waypoints`/`spend_outliers` all
  populated from the live `effort.db` (100 waypoints, capped at the
  route's own LIMIT 100).

**Effort/story status** (`GET /api/repos/:id/system`):
- `radar`: 57 phases parsed; last phase `MU023-main`, status `complete`,
  title "Migrate to pairmode 0.3.0", 1 story (`MU-128`,
  `story_class: methodology`, `status: complete`).
- `forqsite`: 96 phases parsed; last phase `PM068-main`, status `planned`.
- `flex`: 127 phases parsed; last phase `HARNESS016-main`, status
  `deferred`, title "Final fold — pre-fold gate, merge to main, re-sync".

**Lessons** (`GET /api/repos/:id/lessons`):
- `radar`, `forqsite`: `lessons: []` — both repos have no
  `lessons/lessons.json` on disk; the route's fail-open (`parseLessons`
  returns `[]` on ENOENT) is exercised for real, not the fixture only.
- `flex`: 22 lessons parsed, 1 promotion candidate (`L001`,
  `promotion_reasons: ["module-named: audit.py", "procedural-verb: 'add a
  (check|warning|gate)'"]`).

**User memories/policies** (`GET /api/user/memories`, `GET /api/user/policies`,
operator's real `$HOME`): 14 project memory directories found (e.g.
`-mnt-work` with 7 memory files, `-mnt-work-aab` with 15); 3 policy files
found (`auth-abac.md`, `auth-coexistence.md`, `auth-rbac.md`), each with a
real parsed `first_heading`.

**CORS/loopback** (`GET /health` with `Origin: https://evil.example`, server
bound to the default `127.0.0.1`): response carries
`access-control-allow-origin: *`, matching the loopback-wildcard branch of
the INFRA-306 contract as shipped — also pinned by
`tests/cors.test.ts`'s live-`inject()` assertions for both the loopback and
non-loopback-deny branches.

**Failure-shaped case** (`GET /api/repos/nonexistent/system`,
`GET /api/repos/nonexistent/context`): both returned `404`
`{"error":"repo not found","id":"nonexistent"}` — handled, not a crash.

**Defects found: 1, filed: CER-142.** `readResolverState`'s
`getFlexBuildPath()` (`skills/observability/api/src/readers/resolverState.ts`)
resolves one directory too high, so the spawned `flex_build.py
resolver-state` call always fails and `resolver_state` is `null` on every
route response — observed live against all three real repos above
(`radar`, `forqsite`, `flex` all show `resolver_state: null`), not just the
INFRA-312 test fixture. Out of this story's declared `touches:` scope
(`src/readers/` is not listed), so filed rather than fixed in-scope per
Ensures 5's explicit provision, with the exact one-line fix named in the
CER row.
