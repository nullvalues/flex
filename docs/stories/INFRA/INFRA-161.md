---
id: INFRA-161
rail: INFRA
title: "Vite + React 19 + Tailwind v4 frontend — multi-repo side-by-side panels"
status: planned
phase: "63"
story_class: code
primary_files:
  - skills/observability/ui/package.json
  - skills/observability/ui/vite.config.ts
  - skills/observability/ui/tailwind.config.ts
  - skills/observability/ui/src/main.tsx
  - skills/observability/ui/src/App.tsx
  - skills/observability/ui/src/components/RepoPanel.tsx
  - skills/observability/ui/src/components/SystemOfRecord.tsx
  - skills/observability/ui/src/components/ContextMetrics.tsx
  - skills/observability/ui/src/api/client.ts
touches:
  - skills/observability/api/src/server.ts
  - skills/observability/package.json
---

# INFRA-161 — Vite + React 19 + Tailwind v4 frontend: multi-repo side-by-side panels

## Context

The SPA frontend. Depends on INFRA-156 (server skeleton), INFRA-157
(system endpoint), INFRA-159 (context endpoint). INFRA-158 (lessons)
is a bonus if available but not required for this story to pass.

Stack matches the project family:
- Vite 6 + React 19
- Tailwind CSS v4 (PostCSS plugin)
- TanStack Query v5 for data fetching
- shadcn/ui for components (the card, badge, separator, skeleton components
  are all that's needed for Phase 1)

The UI is a single-page app with two main views per repo:
1. **System of Record** — era → phase → story hierarchy
2. **Context** — current token count, thresholds, waypoints, effort summary

Multiple repos are shown as side-by-side columns (or stacked on narrow
viewports). A repo selector at the top lets the user pin/unpin repos.

Phase 1 is pure window-glass — all data is read-only. Controls come in
Phase 64.

## Ensures

1. `skills/observability/ui/` is a complete Vite + React 19 TypeScript project:
   - `package.json`: name `@flex-obs/ui`, scripts `dev`, `build`, `preview`
   - `vite.config.ts`: proxy `/api` to `http://127.0.0.1:7777` in dev mode
   - `tailwind.config.ts`: scans `src/**`
   - `src/main.tsx`: mounts `<App />` into `#root`
   - `src/index.html`: standard Vite HTML entry

2. `pnpm --filter @flex-obs/ui build` compiles without errors.

3. `GET /` from the Fastify server serves the built `index.html` (Fastify
   serves `skills/observability/ui/dist/` as static files via `@fastify/static`).
   In dev mode, the Vite dev server handles `/`; in production the Fastify
   server does.

4. **App layout:**
   - Top bar: "flex observability" title + last-refreshed timestamp
   - Repo columns: one column per registered repo, side-by-side in a
     horizontal scrollable container (CSS grid, `auto-fill` with min 380px)
   - Each repo column has a tab bar: "System" | "Context" | "Lessons"
   - Refresh button (re-fetches all queries via `queryClient.invalidateQueries`)

5. **System tab (`<SystemOfRecord repoId={id} />`):**
   - Renders the phase list from `GET /api/repos/:id/system`
   - Phases are collapsible (default: show last 5, rest collapsed)
   - Each phase row shows: phase number, title, status badge (colour-coded:
     `complete`=green, `planned`=blue, `deferred`=yellow, unknown=grey)
   - Expanded phase shows stories as a sub-list with: ID, title, status badge,
     `flex_factor` badge when `!= 1.0`
   - Loading state: skeleton cards

6. **Context tab (`<ContextMetrics repoId={id} />`):**
   - Current token count as a progress bar vs. `context_budget_threshold`
   - "Stale" warning badge when `current.stale == true`
   - Threshold table: name, value, source badge (state.json/default)
   - Waypoints: last 10 as a simple table (ts, tokens, story_id, outcome)
   - Effort summary: total attempts, by-phase median table (last 5 phases)

7. **Lessons tab (`<LessonsPanel repoId={id} />`):**
   - Lists lessons from `GET /api/repos/:id/lessons`
   - Promotion-candidate lessons are highlighted (amber border)
   - Each lesson shows: id, date, status, trigger (truncated), promotion badge

8. TanStack Query: each endpoint is a separate query with `staleTime: 2000`
   (matches the server-side 2 s cache). Auto-refresh every 30 seconds
   (`refetchInterval: 30000`).

9. Responsive: on viewports < 640 px wide, repo columns stack vertically.

10. No write controls anywhere in the UI (buttons, forms, inputs that mutate).

11. When the API returns an error (non-2xx), the affected panel shows an
    error state with the HTTP status code and message; other panels continue
    to render.

12. The built `dist/` directory is served by the Fastify server from
    INFRA-156 (`@fastify/static`). Add `@fastify/static` to `api/package.json`.
    Fastify serves `skills/observability/ui/dist/` when `NODE_ENV=production`.

## Instructions

- shadcn/ui: add the `card`, `badge`, `separator`, `skeleton`, `progress`,
  `tabs` components. Follow the shadcn/ui CLI installation pattern.
- Tailwind v4: use the CSS-based configuration (not JS config) unless the
  shadcn setup requires the JS config — defer to shadcn's requirements.
- TanStack Query: wrap `App` in `<QueryClientProvider>`. Create query hooks
  in `src/api/client.ts` (one hook per endpoint).
- The API base URL in `src/api/client.ts` is `/api` (relative), so the
  Vite proxy and the production Fastify static serve both work without
  environment-specific config.
- Do not add charting libraries (Chart.js, Recharts, etc.) in this story —
  the progress bar and tables are sufficient for Phase 1.

## Tests

Manual:
```bash
cd skills/observability
pnpm install
pnpm --filter @flex-obs/api build
pnpm --filter @flex-obs/ui build
# Start server in production mode
NODE_ENV=production node api/dist/server.js &
curl -s http://127.0.0.1:7777/ | grep -q "flex observability" && echo "OK"
kill %1
```

Optionally: `pnpm --filter @flex-obs/ui dev` and open `http://localhost:5173`
to verify the multi-repo panel layout renders for registered repos.

## Out of scope

- Write controls / tuning dials (Phase 64).
- Memories and policies tabs (the Lessons tab covers INFRA-158; memories/policies
  can be a future tab in Phase 64).
- Charting or time-series visualisations beyond the progress bar.
- Authentication.
- Dark mode (use system preference via Tailwind `dark:` classes if convenient,
  but not required).
