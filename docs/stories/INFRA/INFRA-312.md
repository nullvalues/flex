---
id: INFRA-312
rail: INFRA
title: Observability UI functional validation — dogfood checklist over ≥2 registered repos plus a scoped TypeScript route-test runner
status: draft
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
