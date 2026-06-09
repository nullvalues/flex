---
id: INFRA-156
rail: INFRA
title: "`skills/observability/` pnpm workspace — Fastify skeleton + registry + `/api/repos`"
status: complete
phase: "63"
story_class: code
primary_files:
  - skills/observability/package.json
  - skills/observability/api/package.json
  - skills/observability/api/src/server.ts
  - skills/observability/api/src/registry.ts
  - skills/observability/api/src/routes/repos.ts
  - skills/observability/api/tsconfig.json
touches:
  - skills/observability/ui/package.json
  - skills/observability/pnpm-workspace.yaml
---

# INFRA-156 — `skills/observability/` pnpm workspace: Fastify skeleton + registry + `/api/repos`

## Context

This story scaffolds the `skills/observability/` workspace that will host
the Observability SPA (Phase 63). It is the foundation all other Phase 63
stories build on top of.

The workspace uses the same pnpm monorepo split (`api/` + `ui/`) used by
cora, asp, aab, and radar. The API server uses Fastify 5, matching those
projects. Phase 1 is read-only; no write routes exist.

The registry at `~/.config/flex-observability/registry.json` is the source of
truth for which repos are registered. The Fastify server re-reads it on every
request so newly-registered repos appear without a restart.

## Ensures

1. `skills/observability/` directory exists with:
   - `pnpm-workspace.yaml` declaring `packages: ['api', 'ui']`
   - `package.json` (workspace root, private: true, no scripts)

2. `skills/observability/api/` contains a complete Fastify 5 TypeScript project:
   - `package.json` with scripts: `dev` (tsx watch), `build` (tsc), `start` (node dist/)
   - `tsconfig.json` targeting Node 20, `moduleResolution: node16`, `outDir: dist`
   - `src/server.ts` — creates and exports the Fastify instance; starts on
     `FLEX_OBS_HOST` (default `127.0.0.1`) and `FLEX_OBS_PORT` (default `7777`)
   - `src/registry.ts` — `readRegistry(): Promise<Registry>` reads
     `~/.config/flex-observability/registry.json`; returns `{version, repos: []}` if
     absent. Schema: `{version: number, repos: [{id, project_dir, color}], default_port?, bind_host?}`.
   - `src/routes/repos.ts` — registers `GET /api/repos` on the Fastify instance

3. `skills/observability/ui/` contains a minimal placeholder `package.json`
   (name: `@flex-obs/ui`, private: true) so the workspace resolves. No source
   files yet (INFRA-161 fills this).

4. `GET /api/repos` returns JSON:
   ```json
   {
     "generated_at": "<ISO timestamp>",
     "repos": [
       {
         "id": "flex",
         "project_dir": "/mnt/work/flex",
         "color": "#7aa2f7",
         "registered": true,
         "state_json_present": true
       }
     ]
   }
   ```
   - `state_json_present` is `true` iff `<project_dir>/.companion/state.json`
     is readable.
   - An empty registry returns `{"generated_at": "...", "repos": []}`.

5. `GET /health` returns `{"status": "ok"}` with HTTP 200.

6. All Fastify responses set `Content-Type: application/json`.

7. CORS: allow `*` origin in development (the Vite dev server proxies to Fastify;
   production serves the built UI as static files from the same origin, but allow-all
   is correct for the dev workflow).

8. No write routes (`PUT`, `POST`, `DELETE`) exist anywhere in the `api/` source.

9. `pnpm install` in `skills/observability/` resolves without errors.

10. `pnpm --filter @flex-obs/api build` compiles without TypeScript errors.

## Instructions

- Use Fastify 5 (`fastify@^5`). Do not use Express.
- Use `tsx` for the dev script (TypeScript execution without separate compilation).
- Dependencies: `fastify`, `@fastify/cors`. Dev: `typescript`, `tsx`, `@types/node`.
- No database connections, no write operations of any kind in this story.
- The server reads `registry.json` from `FLEX_OBS_REGISTRY` env var path if set,
  otherwise defaults to `~/.config/flex-observability/registry.json`.
- `readRegistry` must gracefully return the empty registry shape when the file is
  absent (no throw, no process exit).

## Tests

Manual verification only for this story (no Python test suite; the pnpm build
passing is the acceptance signal).

Run:
```bash
cd skills/observability && pnpm install && pnpm --filter @flex-obs/api build
```
Assert exit 0 with no TypeScript errors.

Then:
```bash
FLEX_OBS_PORT=7778 node skills/observability/api/dist/server.js &
curl -s http://127.0.0.1:7778/health && curl -s http://127.0.0.1:7778/api/repos
kill %1
```
Assert `/health` returns `{"status":"ok"}` and `/api/repos` returns JSON with
a `repos` array.

## Out of scope

- Registering repos (INFRA-162).
- Any per-repo API endpoints (INFRA-157, 158, 159).
- The Vite frontend (INFRA-161).
- The Python CLI (INFRA-162).
