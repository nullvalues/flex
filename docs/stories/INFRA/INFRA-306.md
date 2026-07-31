---
id: INFRA-306
rail: INFRA
title: Observability API: loopback-honest CORS and abs_path disclosure gating
status: complete
phase: "115"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/observability/api/src/server.ts
  - skills/observability/api/src/routes/user.ts
touches:
  - skills/observability/SKILL.md
  - tests/pairmode/test_observability_api_security.py
  - docs/architecture.md
  - docs/stories/INFRA/INFRA-306.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 115 closes the observability half of the CER backlog. This story drains the
two Phase-63 security-audit rows that both describe the same latent defect: the
observability API is *documented* as loopback-only but is not *built* that way.

- **CER-042** — `skills/observability/api/src/server.ts:34-36` registers
  `@fastify/cors` with `origin: '*'`, unconditionally. The bind host is resolved
  separately in `main()` at `server.ts:88`
  (`process.env.FLEX_OBS_HOST ?? '127.0.0.1'`), and the launcher
  (`skills/observability/scripts/flex_observability.py:193-229`) exposes a
  `--host` flag that writes `FLEX_OBS_HOST` into the child environment. So an
  operator who runs `serve --host 0.0.0.0` to see the dashboard from another
  machine silently hands every website their browser visits read access to every
  registered repo's context data, effort metrics, and filesystem paths. The
  wildcard is defensible on loopback and indefensible off it, and today the code
  cannot tell the difference — `buildServer()` never sees the host.
- **CER-043** — `routes/user.ts` declares `abs_path: string` on both
  `MemoryFile` (:15) and `PolicyFile` (:37) and populates it at :126 and :160
  with the full absolute path of every file under `~/.claude/projects/*/memory/`
  and `~/.claude/policies/`. That leaks the operator's home directory, username,
  and directory layout to any client that can reach the API — harmless on
  loopback, a real disclosure once CER-042's exposure path is taken.

Both rows are LOW severity precisely *because* the default is loopback. The fix
is therefore not "lock it down" but "make the code honest about which mode it is
in": keep the permissive, frictionless behaviour on loopback, and fail closed the
moment the operator opts into exposure — loudly, so the choice is visible.

**Recon already performed — do not redo it:**

- `buildServer()` (`server.ts:31`) has exactly one caller, `main()` at
  `server.ts:97`. Nothing else in the repo imports it. Adding a parameter is a
  one-site change.
- **The SPA does not consume `abs_path` at all.** `grep -rn "abs_path" ` over
  `skills/observability/ui/src/` returns zero hits; so does `grep -rn "api/user"`.
  The UI (`ui/src/api/client.ts`, `App.tsx`, `components/{ContextMetrics,
  LessonsPanel,RepoPanel,SystemOfRecord}.tsx`) never calls `/api/user/memories`
  or `/api/user/policies`. The closeout plan's "UI consumers reconciled" item is
  therefore satisfied by *evidence of absence*, not by an edit — see Ensures 7.
  (`skills/seed/scripts/setup.py:45` and the `tests/pairmode/test_scope_guard.py`
  hits are unrelated local variables named `abs_path`.)
- Observability tests are **Python structural assertions** — there is no TS test
  runner in this repo. `tests/pairmode/test_observability_context_api.py` reads
  `.ts` files as text and asserts on substrings, plus one
  `subprocess.run(["pnpm","build"], cwd=api)` compile gate at :188-198.
- `skills/observability/api/package.json` defines `build` as plain `tsc` (not
  `tsc --noEmit`); `dist/` is gitignored (`.gitignore:6`) and untracked, so the
  build gate emits nothing that pollutes the tree.
- `flex_observability.py serve` copies `os.environ` before adding
  `FLEX_OBS_PORT`/`FLEX_OBS_HOST`/`FLEX_OBS_REGISTRY` (:228-231), so a
  `FLEX_OBS_ALLOWED_ORIGINS` set in the operator's shell reaches the Node child
  with **no launcher change required**.
- `docs/architecture.md:3331` currently states the API binds "to `127.0.0.1:7777`
  (loopback, dev-local only)" — the sentence that this story makes true in code.

## Requires

- Working tree clean at HEAD on `main`; branch/worktree provisioned by
  `create-story-worktree` per the standard build loop.
- `skills/observability/api/src/server.ts` registers `@fastify/cors` with
  `origin: '*'` at :34-36, resolves `const host = process.env.FLEX_OBS_HOST ??
  '127.0.0.1'` at :88, and calls `await app.listen({ host, port })` at :99.
- `skills/observability/api/src/routes/user.ts` declares `abs_path: string` at
  :15 and :37 and populates it at :126 and :160; both route handlers currently
  bind their request argument as `_request` (:89, :141).
- `@fastify/cors@^10` is present in `api/package.json` dependencies (its `origin`
  option accepts `string | boolean | string[] | RegExp | function`; `false`
  disables CORS headers entirely).
- `pnpm` and the vendored `skills/observability/node_modules` payload are usable
  from the build worktree. If they are not, rsync the payload from the main
  checkout (CER-090) — **never** run `pnpm install` in a worktree.
- No sibling Phase-115 story is required first; INFRA-306 is independent of
  INFRA-307/308/309 and must precede only INFRA-310's backlog annotation of
  CER-042/043.

## Ensures

1. `skills/observability/api/src/server.ts` exports a pure predicate
   `isLoopbackHost(host: string): boolean` that returns `true` for `127.0.0.1`,
   any `127.x.y.z`, `::1`, `[::1]`, and `localhost` (case-insensitive, surrounding
   whitespace tolerated) and `false` for `0.0.0.0`, `::`, `192.168.1.10`, and the
   empty string. `grep -c 'export function isLoopbackHost'
   skills/observability/api/src/server.ts` returns 1.
2. `server.ts` exports a pure function
   `resolveCorsOrigin(host: string, allowedOriginsRaw: string | undefined)`
   returning `'*' | string[] | false`, with exactly this behaviour:
   - host is loopback → `'*'` (current behaviour retained verbatim);
   - host is non-loopback and `allowedOriginsRaw` yields ≥1 non-empty origin after
     splitting on `,` and trimming → that `string[]`;
   - host is non-loopback and `allowedOriginsRaw` is `undefined`, empty, or all
     blank after trimming → `false` (deny all cross-origin; `@fastify/cors` emits
     no `Access-Control-Allow-Origin` header).
   The deny default is the documented, tested branch — not an accident of falsy
   handling.
3. `buildServer()` accepts the host as an explicit parameter (signature
   `buildServer(host: string = process.env.FLEX_OBS_HOST ?? '127.0.0.1')`) and
   registers `cors` with `{ origin: resolveCorsOrigin(host,
   process.env.FLEX_OBS_ALLOWED_ORIGINS) }`. The literal `origin: '*',` no longer
   appears in the `app.register(cors, …)` call:
   `grep -c "origin: '\*'," skills/observability/api/src/server.ts` returns 0.
4. `main()` resolves `host` exactly once (the existing :88 line is the single
   source) and passes it to `buildServer(host)`. There is no second
   `process.env.FLEX_OBS_HOST` read inside `main`.
5. When `isLoopbackHost(host)` is false, `main()` writes exactly one
   `console.error` warning **before** `await app.listen(...)`. The message names
   (a) the bind host, (b) that the API is reachable beyond this machine, and (c)
   the effective CORS policy — either the allow-listed origins or the phrase that
   all cross-origin requests are denied and `FLEX_OBS_ALLOWED_ORIGINS` is how to
   permit them. No warning is emitted on a loopback host.
6. `routes/user.ts` gates the path field: `abs_path` is declared optional
   (`abs_path?: string;`) on both `MemoryFile` and `PolicyFile`, and is set on a
   response object **only** when the request's `include_path` query value is the
   exact string `'true'`. Both handlers type their querystring
   (`Querystring: { include_path?: string }`) and bind `request` rather than
   `_request`. Absent, empty, `false`, `1`, or `TRUE` → field omitted from the
   JSON entirely (not `null`, not `""`).
7. The SPA has no `abs_path` consumer, and the story does not create one:
   `grep -rn "abs_path\|/api/user" skills/observability/ui/src/` returns no
   matches on the post-change tree. This is recorded in the story's evidence as a
   grep transcript — it is the whole of the "UI consumers reconciled" item.
8. `skills/observability/SKILL.md`'s `serve` section documents, in prose a
   non-author operator can act on: the loopback default; `FLEX_OBS_HOST` /
   `--host` and that overriding it triggers the exposure warning;
   `FLEX_OBS_ALLOWED_ORIGINS` (comma-separated, empty default = deny all
   cross-origin, only consulted off loopback); and the `?include_path=true`
   parameter on `/api/user/memories` and `/api/user/policies`. The existing
   "Loopback-only" design note (~:190) is updated so it describes enforced
   behaviour rather than an assumption.
9. `docs/architecture.md`'s observability section (the loopback sentence at
   ~:3331) records the CORS policy table (loopback → `*`; exposed + allow-list →
   list; exposed + no allow-list → deny) and the `include_path` gate, with the
   rationale that the default must fail closed.
10. `PATH=$HOME/.local/bin:$PATH uv run pytest
    tests/pairmode/test_observability_api_security.py
    tests/pairmode/test_observability_context_api.py -q` is fully green,
    including `test_observability_context_api.py::test_typescript_compiles`
    (`pnpm build` = `tsc`, exit 0). This build gate is in this story's scope and
    may **not** be waived as an environment failure.
11. `cd skills/observability/api && pnpm exec tsc --noEmit` exits 0, transcript
    pasted into the story's evidence.
12. Full suite run without `-x` —
    `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` — reports no
    failures other than
    `test_observability_ui.py::test_ui_build_emits_dist_index_html`, and that one
    only if it is the known worktree-only CER-090 payload failure (main is green
    at 4116 passed / 211 skipped, so any failure on main is a real regression).

## Instructions

1. **`server.ts` — CORS policy.** Add two exported functions above
   `buildServer()`, each with a docstring-style comment naming CER-042 and the
   reason the loopback branch stays permissive:
   - `isLoopbackHost(host)` — normalise with `host.trim().toLowerCase()`, strip a
     surrounding `[...]`, then return true for `localhost`, `::1`, and
     `/^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/`. Do **not** treat `0.0.0.0` or `::` as
     loopback: they are all-interfaces binds, i.e. the exposure case.
   - `resolveCorsOrigin(host, allowedOriginsRaw)` — implement Ensures 2 exactly.
     Return type `'*' | string[] | false`; annotate it explicitly so `tsc` pins
     the contract.

   Change `buildServer()` to `export async function buildServer(host: string =
   process.env.FLEX_OBS_HOST ?? '127.0.0.1')` and pass
   `{ origin: resolveCorsOrigin(host, process.env.FLEX_OBS_ALLOWED_ORIGINS) }`
   to `app.register(cors, …)`. The default parameter keeps the single existing
   caller and any future test harness working without an argument; `main()` still
   passes its resolved `host` explicitly so there is one authoritative read.

2. **`server.ts` — exposure warning.** In `main()`, after `host` is resolved and
   before `await app.listen(...)`, add:

   ```ts
   if (!isLoopbackHost(host)) {
     // eslint-disable-next-line no-console
     console.error(<one-line warning per Ensures 5>);
   }
   ```

   One `console.error` call, one line of output, no `process.exit` — exposure is
   an operator's prerogative, not an error. Do not warn on loopback: a warning
   that fires on the default path is a warning nobody reads.

3. **`routes/user.ts` — `include_path` gate.** Make `abs_path` optional in both
   interfaces. In each handler, change `async (_request, reply)` to
   `async (request, reply)` and type the route generic
   `app.get<{ Querystring: { include_path?: string } }>('/api/user/memories', …)`.
   Compute `const includePath = request.query.include_path === 'true';` **once**
   per handler, outside the loop. Build the pushed object without `abs_path` and
   spread the field in conditionally — e.g.
   `...(includePath ? { abs_path: absPath } : {})` — so the key is absent, not
   null, when the gate is closed. Keep the local `absPath` variable: it is still
   needed for `safeReadFile`/`safeStat`. Strict `=== 'true'` only; do not accept
   `1`, `yes`, or a bare `?include_path`. Add a comment naming CER-043 and why
   the default is omission.

4. **Do not change the launcher.** `flex_observability.py serve` already copies
   `os.environ`, so `FLEX_OBS_ALLOWED_ORIGINS` passes through untouched. Adding a
   `--allowed-origins` flag would create a second configuration surface for one
   value; it is explicitly out of scope below.

5. **Docs.** Update the `serve` subcommand section and the "Loopback-only" design
   note in `skills/observability/SKILL.md` per Ensures 8, and the observability
   paragraph in `docs/architecture.md` per Ensures 9. State the *reason* the
   default denies (rationale-bearing decisions, `docs/ideology.md` § Core
   convictions), not just the rule.

6. **Tests.** Create `tests/pairmode/test_observability_api_security.py` in the
   structural style of `test_observability_context_api.py` (module docstring
   explaining these are structural assertions over TS sources; `FLEX_ROOT =
   Path(__file__).resolve().parents[2]`; `SRC = FLEX_ROOT / "skills" /
   "observability" / "api" / "src"`). A new module rather than an extension of
   `test_observability_context_api.py`: that file is the INFRA-159 context-route
   guard and already carries the shared `pnpm build` gate — reuse the gate, do
   not duplicate it, and keep the security assertions addressable on their own.
   Cover, at minimum, the cases listed under `## Tests`. Additionally re-express
   `isLoopbackHost`'s classification table as a pure-Python mirror over the same
   host strings (the `test_p90_correct_for_round_n` idiom at
   `test_observability_context_api.py:296-317`) so the intended semantics are
   pinned as data, and assert the corresponding regex/literals are present in the
   TS source.

7. **Ideology note (Step 4a, resolved inline).** `docs/ideology.md` § Core
   convictions prefers "codifying policy over implicit convention" and
   "rationale-bearing decisions over bare rules"; § Value hierarchy puts
   "decision fidelity over convenience". The instructions above therefore require
   the deny-by-default branch to be an explicitly documented, separately tested
   code path (Ensures 2, 5, 8, 9) rather than a falsy fall-through, and require
   the SKILL.md/architecture text to carry the reason, not just the setting. No
   accepted constraint is engaged: the hook/pipe/sidebar boundary and
   single-writer rule are untouched by this story (the observability API is a
   read-only reader, not a state writer). "Python everywhere" is a prototype
   fingerprint marked *Conditional*, and this story writes TypeScript inside the
   already-TypeScript observability package — no new language boundary is
   introduced, and the tests stay Python.

8. **Spec-preflight note (INFRA-190/191).** The preflight scan over this story
   reports two classes of finding, both intentional: `Route warning:
   '/api/src/server'` ×3 is the scanner reading the file path
   `skills/observability/api/src/server.ts` as an API route (it is a source file,
   not a route); and `Constant warning: 'FLEX_OBS_ALLOWED_ORIGINS'` is expected
   because this story is what introduces that environment variable.

9. **Do not** attempt runtime verification by launching the server against a
   non-loopback interface. The invariants above are asserted statically plus the
   compile gate; live exposure testing is the operator's, at checkpoint.

## Tests

Targeted run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_observability_api_security.py \
  tests/pairmode/test_observability_context_api.py -q
```

Compile evidence (paste the transcript into the story record):

```bash
cd skills/observability/api && pnpm exec tsc --noEmit
```

Then the full suite, **without** `-x` so the known worktree-only failure cannot
mask a real one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

New assertions in `tests/pairmode/test_observability_api_security.py`:

1. `server.ts` contains `export function isLoopbackHost` and
   `export function resolveCorsOrigin`.
2. `server.ts` no longer contains `origin: '*',` inside the cors registration;
   the string `'*'` survives only inside `resolveCorsOrigin`'s loopback branch
   (assert `resolveCorsOrigin` is the only function whose body mentions it, e.g.
   by slicing the source between the two `export function` markers).
3. `server.ts` references `FLEX_OBS_ALLOWED_ORIGINS` at least once.
4. `server.ts` contains a `console.error` guarded by `!isLoopbackHost(` in
   `main`, and that guard appears **before** `await app.listen(` in the file
   (index comparison on the source text).
5. `buildServer` signature carries a `host` parameter (`buildServer(host` present
   in the source) and `main` calls `buildServer(host)`.
6. Loopback classification mirror: a Python table over
   `["127.0.0.1","127.1.2.3","::1","[::1]","localhost","LOCALHOST"," 127.0.0.1 "]`
   → loopback, and `["0.0.0.0","::","192.168.1.10","10.0.0.5",""]` → not
   loopback; assert the TS source contains the `127\.` regex and the `localhost`
   and `::1` literals that implement it.
7. `routes/user.ts` declares `abs_path?: string;` exactly twice and contains no
   `abs_path: string;` (required-field form).
8. `routes/user.ts` contains `include_path` in both a `Querystring` generic and a
   `=== 'true'` comparison, and no longer binds `_request` in either
   `/api/user/memories` or `/api/user/policies`.
9. UI-absence guard: a walk of `skills/observability/ui/src/**/*.{ts,tsx}`
   asserts zero occurrences of `abs_path` and zero of `/api/user` — this test
   fails the day someone adds a consumer without revisiting the gate.
10. `skills/observability/SKILL.md` mentions `FLEX_OBS_ALLOWED_ORIGINS`,
    `FLEX_OBS_HOST`, and `include_path`.

**Acceptance:** the targeted run is fully green (including
`test_typescript_compiles`), `tsc --noEmit` exits 0, and the full run reports no
failures except `test_observability_ui.py::test_ui_build_emits_dist_index_html`
when — and only when — that failure is the known CER-090 worktree payload
symptom. `main` is green at 4116 passed / 211 skipped, so anything else is a
regression introduced by this story. If the compile gate or the UI test fails in
the worktree, rsync `skills/observability/node_modules` from the main checkout;
never run `pnpm install` inside a worktree.

## Out of scope

- **Authentication or authorization on the API.** Every route stays unauthenticated.
  This story only decides *which origins a browser may read from* and *whether a
  filesystem path is disclosed*; it does not introduce tokens, sessions, or
  per-repo access control.
- **A `--allowed-origins` CLI flag on `flex_observability.py serve`.** The
  environment variable passes through the launcher's `os.environ.copy()`
  unchanged; adding a flag would create a second writer for one setting.
- **Changing the bind default or refusing to bind off loopback.** Exposure stays
  an operator choice; this story makes it loud, not impossible.
- **Removing `abs_path` outright, or adding a relative-path replacement field.**
  The field remains available behind `?include_path=true` for the dev-convenience
  case the audit acknowledged.
- **Gating paths on any other route.** `/api/repos/*`, `/api/system`,
  `/api/lessons`, and `/api/context` also return project paths; CER-043 scopes
  only the two `/api/user/*` routes, and widening the gate would change the SPA's
  live contract (those routes *are* consumed).
- **Introducing a TypeScript test runner (vitest/node:test).** Structural Python
  assertions plus the `tsc` gate remain the contract for this package; changing
  it is a phase-sized decision, not a story-sized one.
- **CSRF/`Access-Control-Allow-Credentials` handling.** No route sets cookies or
  reads credentials, so no credentialed-CORS policy is needed.
- **The other Phase-115 CER rows** — CER-093/094 (INFRA-307), CER-109
  (INFRA-308), CER-107 (INFRA-309) — and the backlog annotation of CER-042/043
  itself, which INFRA-310 performs as part of the truth pass.
