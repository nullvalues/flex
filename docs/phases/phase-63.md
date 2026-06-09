---
era: "002"
---

# flex — Phase 63: Observability SPA — read-only window glass

← [Phase 62: Context gate authorization clarity](phase-62.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

**Parent phase:** Absorbs `phase-proposed-observability-spa-20260602-001.md`
(era 002 scope; anchored 2026-05-29; open questions resolved in the planning
session that produced this phase). The proposed file is deleted on the first
commit of this phase per index convention; git history preserves the transit.

## Goal

Ship a local, read-only observability SPA that surfaces pairmode project data
currently buried in the console sidebar, `.companion/state.json`, and
`.companion/effort.db`. Phase 1 is pure window-glass — no controls, no writes,
no LLM calls. Two visualization surfaces ship together:

1. **System of Record** — era → phase → story hierarchy across one or more
   registered repos, with plan/build status per node; lessons / policies /
   memories with mechanical "promotion candidate" flags; phase doc metadata
   (timestamps, checkpoint status, deferred stories).

2. **Context Management** — context-check waypoints, accumulated effort.db
   metrics, near-miss / overrun records, and the live threshold configuration
   (upper context limit, clear-prompt threshold, story estimate flex limits)
   rendered as `{value, source, editable_via}` triples so Phase 64's controls
   slot in without re-plumbing endpoints.

The architecture is additive: the existing console sidebar
(`skills/companion/scripts/sidebar.py`) is untouched in this phase. The SPA
reads the same files the sidebar reads, plus the effort SQLite DB, plus the
phase index, story files, and lessons.json. Multi-repo support is a
first-class concern from day one — one SPA instance shows N registered repos
simultaneously in side-by-side panels.

Other projects already invoke flex's scripts directly (context checks, sync
tools) using flex paths, so the SPA living inside flex and being invoked from
outside it is consistent with the established architecture. No architectural
break.

## Why this phase exists

Era 002's documented theme is "surfacing what was previously invisible…
without requiring orchestrator recall to see them." The console sidebar serves
a narrow live-events role; everything else (story status, effort medians,
threshold settings, lessons, context check history) requires the developer to
grep, sqlite, or read state.json by hand. Multiple recent phases (39, 42, 43,
47, 53, 58, 59, 60) routed observability data into state.json + effort.db
precisely so a downstream surface could consume it without scraping. This phase
is that surface.

## Stack

Aligned with the existing project family (forqsite, cora, asp, aab, radar) to
allow boilerplate reuse and avoid maintaining a divergent JS toolchain.

| Layer | Choice | Rationale |
|---|---|---|
| API server | Fastify 5 | Standard across cora, asp, aab, radar |
| Frontend | Vite + React 19 | Standard across all active SPAs in the family |
| Package manager | pnpm workspaces (`api/` + `ui/`) | Standard monorepo split |
| Styling | Tailwind CSS v4 | Standard; Tailwind v4 is the current baseline |
| Components | shadcn/ui | Pull from forqsite boilerplate |
| Data fetching | TanStack Query | Standard across cora, asp, aab, radar |
| Repo location | `skills/observability/` inside flex | Consistent with how other projects call flex scripts directly |
| Bind | `127.0.0.1:7777` (loopback only) | Dev-local tool; must not appear on a network interface |

## Decisions

Settled before story specs are drafted so they survive context compaction.

- **D1 — Monorepo layout:** `skills/observability/api/` (Fastify 5) +
  `skills/observability/ui/` (Vite + React 19 + Tailwind v4) under a pnpm
  workspace root at `skills/observability/`. The CLI entry point
  (`flex_observability.py`) lives at `skills/observability/scripts/` alongside
  the Python companion scripts, consistent with other skill directories.

- **D2 — Registry at `~/.config/flex-observability/registry.json`.** Schema:
  ```json
  {
    "version": 1,
    "repos": [
      {"id": "flex", "project_dir": "/mnt/work/flex", "color": "#7aa2f7"},
      {"id": "forqsite", "project_dir": "/mnt/work/forqsite", "color": "#e0af68"}
    ],
    "default_port": 7777,
    "bind_host": "127.0.0.1"
  }
  ```
  Survives `rm -rf .companion/` in any repo. Managed only by the
  `flex-observability register/unregister` CLI; Fastify reads it on each
  request (cheap at ≤10 entries).

- **D3 — Read-only contract enforced at the HTTP level.** No PUT / POST /
  DELETE routes ship in Phase 63. Fastify has no write handlers; the only
  fs calls are reads. Phase 64 adds write routes that shell out to existing
  `flex_build.py` subcommands, preserving Phase 47 D11 (state.json has
  exactly one writer per operation).

- **D4 — Threshold surface returns triples, not scalars.** Every
  threshold-shaped value exposes:
  ```json
  {
    "name": "context_budget_threshold",
    "value": 120000,
    "default": 120000,
    "source": "state.json" | "default" | "fixture",
    "editable_via": "flex_build.py set-context-tokens",
    "phase2_writable": true
  }
  ```
  Phase 63 renders `value`; Phase 64 wires the `phase2_writable` flag to
  controls. No re-plumbing needed.

- **D5 — Context check waypoints are derived, not stored.** No new table.
  Waypoint stream is computed by joining (a) reviewer FAIL attempts in
  effort.db with positive `tokens_total` and (b) the current
  `context_current_tokens` + `context_current_tokens_recorded_at` snapshot
  from state.json. Phase 64 may introduce a `waypoints` table if real-time
  fidelity becomes a requirement; Phase 63 explicitly does not.

- **D6 — Lessons promotion candidates flagged mechanically.** A lesson is
  "promotion candidate" iff `status == "applied"` AND
  `methodology_change.affects` contains an entry matching `r"^[a-z_]+\.py$"`
  AND `methodology_change.description` matches a procedural-verb pattern
  (`add\s+a\s+(check|warning|gate)`, `block\s+when`, `warn\s+if`,
  `default\s+to`, `fail\s+(open|closed)\s+when`). No LLM involved.

- **D7 — Memories and policies surfaced read-only, no promotion flag.**
  User-scoped (live outside any repo). Listed in a "User context" tab:
  filename, first heading, modification time, path. Too unstructured for
  the mechanical promotion filter.

- **D8 — Sidebar untouched.** SPA is additive. Sidebar retirement is a
  separate later phase after Phase 64 controls ship and feature parity is
  established.

- **D9 — `flex_factor: float` on story frontmatter, default 1.0.** A
  per-story override of the effective context ceiling:
  `threshold × (1 + overrun_pct) × flex_factor`. Values >1.0 widen the
  budget; values <1.0 tighten it. Phase 63 surfaces the field read-only;
  Phase 64 adds a SPA control to set it. The frontmatter parser in
  `flex_build.py _read_story_frontmatter` already exists; no migration of
  existing story files (absent field treated as 1.0).

- **D10 — 2-second in-process cache.** Multi-repo page-load fan-out
  produces N parallel requests for the same repo's state.json. Cache results
  for 2 seconds in-process per repo to avoid re-reading on every simultaneous
  fetch. No external cache store needed.

- **D11 — SQLite opened read-only.** Fastify opens effort.db with
  `?mode=ro` URI parameter. No risk of write contention with the running
  pairmode session.

## Architecture

```
                           ┌──────────────────────────────────┐
                           │ ~/.config/flex-observability/    │
                           │   registry.json                  │
                           └────────────┬─────────────────────┘
                                        │ read on each request
                                        ▼
┌──────────────────┐  HTTP   ┌──────────────────────────────────┐
│ Browser          │ ◀─────▶ │ Fastify API                      │
│ (Vite + React)   │  GET    │ skills/observability/api/        │
│ TanStack Query   │  /api/  │ 127.0.0.1:7777                   │
│ Tailwind v4      │         │                                  │
│ shadcn/ui        │         │ GET /api/repos                   │
│ side-by-side     │         │ GET /api/repos/:id/system        │
│ per-repo panels  │         │ GET /api/repos/:id/context       │
└──────────────────┘         │ GET /api/repos/:id/lessons       │
                             │ GET /api/user/memories           │
                             │ GET /api/user/policies           │
                             └────────────┬─────────────────────┘
                                          │ read-only fs / sqlite
              ┌───────────────────────────┼───────────────────────┐
              ▼                           ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────────────┐
│ /mnt/work/flex      │  │ /mnt/work/forqsite   │  │ ~/.claude/             │
│ .companion/         │  │ .companion/          │  │   policies/*.md        │
│   state.json        │  │   state.json         │  │   projects/<hash>/     │
│   effort.db  (ro)   │  │   effort.db (ro)     │  │     memory/*.md        │
│ docs/phases/        │  │ docs/phases/         │  └────────────────────────┘
│   index.md          │  │   index.md           │
│   phase-*.md        │  │   phase-*.md         │
│ docs/stories/       │  │ docs/stories/        │
│   */*.md            │  │                      │
│ docs/eras/*.md      │  │                      │
│ lessons/            │  │                      │
│   lessons.json      │  │                      │
└─────────────────────┘  └─────────────────────┘
```

## API surface

All responses: JSON `{repo_id, generated_at, …data}` with a "stale at"
timestamp so the UI can show data age without server-sent events.

### `GET /api/repos`
List registered repos plus live pairmode state (current phase/story, whether
a pairmode session is active).

### `GET /api/repos/:id/system`
Era → phase → story tree parsed from `index.md` + phase docs + story
frontmatter. Story nodes include: id, rail, title, status, story_class,
primary_files, touches, flex_factor.

### `GET /api/repos/:id/context`
- **current**: live token count + recorded_at + story_id + staleness flag
- **thresholds**: array of `{name, value, default, source, editable_via, phase2_writable}`
- **waypoints**: derived join of effort.db reviewer-FAIL rows + state.json snapshot
- **effort_summary**: totals, by-phase, by-rail from effort.db
- **misses**: context block events with token-at-block and expected-next

### `GET /api/repos/:id/lessons`
Lessons from `lessons.json` with `promotion_candidate: bool` and
`promotion_reasons: string[]` computed from D6 filter.

### `GET /api/user/memories`
Per-project-hash memory files from `~/.claude/projects/*/memory/*.md`:
filename, first heading, modified_at, abs_path.

### `GET /api/user/policies`
Policy files from `~/.claude/policies/*.md`: filename, first heading,
modified_at, abs_path.

## Multi-repo registration

`flex-observability` CLI at `skills/observability/scripts/flex_observability.py`:

- `register --project-dir DIR [--name NAME] [--color HEX]`
- `unregister --project-dir DIR | --name NAME`
- `list`
- `serve [--port N]` — starts Fastify via `node`; verifies Node is on PATH

The Fastify server re-reads `registry.json` on every request so newly-registered
repos appear without a restart.

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| `~/.config/flex-observability/registry.json` | `flex-observability register/unregister` CLI only; Fastify reads only | User-scoped, outside any repo |
| Story frontmatter `flex_factor: float` (INFRA-160) | Hand-edit story file in Phase 63; Phase 64 adds SPA control | Optional field; absent = 1.0; no migration of existing story files |

No new SQLite tables. No state.json keys added by this phase.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-156 | `skills/observability/` pnpm workspace — Fastify skeleton + registry + `/api/repos` | complete |
| INFRA-157 | System of Record API: `/api/repos/:id/system` (era → phase → story tree) | complete |
| INFRA-158 | Lessons + memories + policies API; promotion-candidate filter (D6) | complete |
| INFRA-159 | Context Management API: `/api/repos/:id/context` (waypoints, threshold triples, effort.db metrics) | complete |
| INFRA-160 | `flex_factor` frontmatter field + read path through `context_budget.decide()` | planned |
| INFRA-161 | Vite + React 19 + Tailwind v4 + shadcn/ui frontend — multi-repo side-by-side panels | planned |
| INFRA-162 | `flex-observability` Python CLI (register / unregister / list / serve) | planned |
| INFRA-163 | Docs — architecture.md section, `/flex:observability` skill entry | planned |

**Build order:** INFRA-156 (foundation) → INFRA-157 / INFRA-158 / INFRA-159
/ INFRA-160 / INFRA-162 (independent, any order after 156) → INFRA-161
(frontend, after at least 157 + 159 exist) → INFRA-163 (closing docs).

## Phase 1 / Phase 2 boundary

**Phase 63 (this phase) — read-only window-glass:**
- All Fastify routes are GET; no write handlers exist in source.
- `flex_factor` is readable by `context_budget.decide()` but not settable
  via SPA.
- Sidebar untouched; both surfaces run in parallel.
- Threshold triples include `phase2_writable` flag but frontend ignores it.

**Phase 64 (planned follow-on) — controls:**
- Adds PUT/POST routes that shell out to `flex_build.py` subcommands.
- Frontend grows controls bound to `phase2_writable: true` triples.
- Audit log: every write appended to
  `~/.config/flex-observability/audit.log`.

**Firm out-of-scope for Phase 63:**
- Sidebar retirement or feature parity
- Cross-repo aggregate charts
- LLM-driven anything in the SPA
- Real-time websocket updates (poll-on-navigate is enough)
- Persisting waypoints to a new table
- Auth / multi-user / remote hosting

---

### CP-63 Cold-eyes checklist

— developer fills in after phase completion —
