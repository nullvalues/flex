---
name: observability
description: Local browser-based observability SPA for context budget, effort metrics, and story status across registered projects.
allowed-tools: Bash, Read
---

# flex:observability

A local read-only observability dashboard (SPA) that surfaces pairmode project data currently
buried in the console sidebar, `.companion/state.json`, and `.companion/effort.db`. Renders
era → phase → story hierarchy, context token counts and thresholds, effort metrics, lessons
with promotion candidates, and user-scoped memories and policies. Multi-repo support is
first-class: one SPA instance shows N registered projects simultaneously in side-by-side panels.

---

## Installation and setup

**Before first use**, install dependencies and build the API/UI bundles:

```bash
cd skills/observability
pnpm install
pnpm --filter @flex-obs/api build
```

(pnpm is the package manager; the project uses a pnpm workspace split into `api/` and `ui/`
subdirectories.)

**Running the API's TS test suite** (INFRA-312 — a scoped vitest route-smoke runner, not
a coverage tool): from `skills/observability/api/`, run `pnpm test`. It boots the Fastify
app in-process (`app.inject()`, no live port) against a hermetic fixture project tree and
exercises all five API routes (`repos`, `context`, `lessons`, `system`, `user`) plus the
INFRA-306 CORS/loopback contract — no live-repo registry or running server required. Run
it alongside `pnpm build` (unaffected by the test runner) whenever either workspace or
route code changes; cp-115's checkpoint and any future observability story should invoke
`pnpm test` the same way the Python suite is invoked.

---

## Commands

Available subcommands: `register`, `unregister`, `list`, `serve`.

### `/flex:observability serve`

**When to use:** Start the observability SPA and open the browser-based dashboard.

**What it does:**
1. Verifies Node.js is available on PATH.
2. Reads `~/.config/flex-observability/registry.json` to load the list of registered projects.
3. Starts the Fastify API server (reads the registry on every request; new registrations appear
   without a restart).
4. Starts the Vite dev server (or uses a pre-built UI if available).
5. Opens the dashboard in your default browser at `http://127.0.0.1:7777`.

**Available when:**
- At least one project has been registered via `register --project-dir`.
- Dependencies have been installed (`pnpm install`) and the API has been built
  (`pnpm --filter @flex-obs/api build`).

**Flags:**
- `--port N` — listen on port N instead of 7777 (default: 7777)
- `--host HOST` — bind to HOST instead of 127.0.0.1 (default: 127.0.0.1 loopback only). Setting
  `--host` (or the `FLEX_OBS_HOST` environment variable it writes into the child process) to
  anything the code does not recognise as loopback — e.g. `0.0.0.0`, `::`, or a LAN address —
  makes the API reachable from other machines. Loopback-only by default; a non-loopback
  `FLEX_OBS_HOST` requires `FLEX_OBS_ALLOWED_ORIGINS` to be set, or cross-origin access is
  denied outright (see CORS policy below). Nothing about the bind itself is blocked — the server
  still listens — but an un-allow-listed non-loopback exposure is loud, not silent: it prints one
  `console.error` warning naming `FLEX_OBS_HOST`/`FLEX_OBS_ALLOWED_ORIGINS` before it starts
  listening.

**CORS policy (CER-042):** on a loopback bind, the API keeps its permissive default —
`Access-Control-Allow-Origin: *` — so the dev dashboard and any local tooling work without
configuration. The moment the bind host is non-loopback, that wildcard is no longer safe (any
website a browser on the exposed network visits could read every registered repo's context
data, effort metrics, and file paths), so the policy flips to **deny all cross-origin requests
by default**, and the server prints exactly one startup warning naming both `FLEX_OBS_HOST` and
`FLEX_OBS_ALLOWED_ORIGINS`. To allow specific origins once exposed, set
`FLEX_OBS_ALLOWED_ORIGINS` to a comma-separated list of origins (e.g.
`FLEX_OBS_ALLOWED_ORIGINS="https://dashboard.example.com,https://ops.example.com"`) in the
environment `flex_observability.py serve` runs in — it is passed through to the Node child
unchanged, no CLI flag needed; once set, the exposure is an explicit, named choice and the
startup warning does not fire. Only consulted off loopback; ignored (loopback stays `*`) on the
default bind.

**Path disclosure gate (CER-043):** `/api/user/memories` and `/api/user/policies` return the
absolute filesystem path of every memory/policy file (`abs_path`) — this discloses the
operator's home directory, username, and directory layout. That field is **omitted by default**
and only included in the response when the request is made with `?include_path=true` (exact
string match; `1`, `yes`, and a bare `?include_path` do not count). This is a dev-convenience
opt-in, not an auth control — pair it with a loopback bind or an allow-listed origin if the API
is exposed.

**Typical workflow:**
```bash
flex_observability.py serve
# Browser opens automatically; dashboard shows all registered projects

# Exposing the API beyond loopback: allow only a known dashboard origin
FLEX_OBS_ALLOWED_ORIGINS="https://dashboard.example.com" flex_observability.py serve --host 0.0.0.0
# FLEX_OBS_ALLOWED_ORIGINS is set, so no startup warning fires — the exposure is explicit.

# Exposing the API beyond loopback with no allow-list: cross-origin access is denied outright
flex_observability.py serve --host 0.0.0.0
# stderr prints: flex-observability api is binding to 0.0.0.0 (FLEX_OBS_HOST is set to a
# non-loopback address); all cross-origin requests are denied because FLEX_OBS_ALLOWED_ORIGINS
# is unset — set it to a comma-separated list of allowed origins to permit cross-origin access.
```

---

### `/flex:observability register`

**When to use:** Add a new project to the observability dashboard.

**Inputs expected:**
- `--project-dir DIR` — absolute or relative path to the project root (required).
- `--name NAME` — user-facing name for this project (optional; defaults to directory name).
- `--color HEX` — hex color code for the project's panel in the dashboard (optional; random
  color assigned if omitted).

**What it does:**
1. Resolves `--project-dir` to an absolute path.
2. Creates `~/.config/flex-observability/registry.json` if it does not exist.
3. Appends the project entry: `{id, project_dir, color}`.
4. Prints: `registered: <project_dir>`.

**Outputs:**
- Updated `~/.config/flex-observability/registry.json` with the new entry.

**Examples:**
```bash
# Register the current project (defaults to directory name as id)
flex_observability.py register --project-dir .

# Register with a custom display name and color
flex_observability.py register --project-dir /mnt/work/flex --name "flex" --color "#7aa2f7"

# Register another project
flex_observability.py register --project-dir /mnt/work/Repo-E --name "Repo-E" --color "#e0af68"
```

---

### `/flex:observability unregister`

**When to use:** Remove a project from the observability dashboard.

**Inputs expected:**
- Either `--project-dir DIR` (path to the project) or `--name NAME` (registered project name).

**What it does:**
1. Reads `~/.config/flex-observability/registry.json`.
2. Finds the entry matching `project_dir` or project name.
3. Removes the entry from the registry.
4. Writes the updated registry.
5. Prints: `unregistered: <project_dir>`.

**Outputs:**
- Updated `~/.config/flex-observability/registry.json` with the entry removed.

**Examples:**
```bash
# Unregister by project path
flex_observability.py unregister --project-dir /mnt/work/flex

# Unregister by registered name
flex_observability.py unregister --name Repo-E
```

---

### `/flex:observability list`

**When to use:** See all projects currently registered for observability.

**Inputs expected:**
- None.

**What it does:**
1. Reads `~/.config/flex-observability/registry.json`.
2. Lists each registered project: id, project path, assigned color.
3. If no projects are registered: prints `No projects registered.`

**Typical output:**
```
Registered projects:
  flex        — /mnt/work/flex (#7aa2f7)
  Repo-E    — /mnt/work/Repo-E (#e0af68)
```

---

## How other projects use this

Other repos register themselves with the flex script path, typically from their own CLAUDE.md
session hooks or manual invocation:

```bash
# From within another project's Claude Code session:
flex_observability.py register --project-dir /path/to/my-project --name "my-project"
```

Once registered, the project appears automatically in the observability SPA the next time
you start the server. Multi-repo dashboards show side-by-side panels, one per registered repo.

---

## Dashboard features

**System of Record tab:** Era → phase → story hierarchy from phase manifests and story files.
Each story node shows: id, rail, title, status, story_class, primary_files, touches, and
flex_factor (the per-story context ceiling override; see Phase 63 D9).

**Context Management tab:** Live token count + recorded timestamp, threshold configuration
(values, sources, and which CLI step sets each one), context check waypoints (join of failed
reviewer attempts + current state snapshot), effort.db rollups by phase/rail, and a record
of near-miss and overrun events.

**Lessons tab:** All lessons from `lessons.json` with `promotion_candidate` flags (computed
mechanically from methodology_change.affects and description patterns; see Phase 63 D6).

**User Context tab:** User-scoped memories (from `~/.claude/projects/*/memory/*.md`) and
policies (from `~/.claude/policies/*.md`), listed with filename, first heading, and modification
time. Absolute path is available on request only — see `?include_path=true` under CER-043 above;
the SPA does not request it and does not render it.

---

## Architecture notes

- **Workspace:** `skills/observability/api/` (Fastify 5 backend) + `skills/observability/ui/`
  (Vite + React 19 frontend) sharing a pnpm workspace root.
- **Registry path:** `~/.config/flex-observability/registry.json`. Survives `rm -rf .companion/`
  in any repo. Managed only by the CLI; Fastify reads it on every request (cheap at ≤10 entries).
- **Database read-only:** Fastify opens `effort.db` with `?mode=ro` URI parameter — no write
  contention with running pairmode sessions.
- **Loopback by default, honest off it (CER-042/CER-043):** Server binds to `127.0.0.1:7777`
  (dev-local) unless `--host`/`FLEX_OBS_HOST` overrides it. On loopback, CORS stays wide open
  (`origin: '*'`) and `abs_path` is available via `?include_path=true` — both are safe because
  only processes on this machine can reach the port. The moment the bind host is not loopback,
  CORS flips to deny-all unless `FLEX_OBS_ALLOWED_ORIGINS` allow-lists specific origins, and a
  startup warning is printed naming the bind host and the effective policy. `abs_path` stays
  gated behind `?include_path=true` in both modes — exposure changes who can reach the API, not
  what a request without the query param discloses.
- **Phase 1 (read-only) / Phase 2 (controls) boundary:** Phase 63 is pure window-glass; all
  routes are GET. Phase 64 adds PUT/POST write routes that shell out to `flex_build.py`
  subcommands, preserving the "exactly one writer per operation" principle.

---

## CLI invocation

Direct script invocation (used by the flex plugin dispatcher):

```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/flex_observability.py" \
  register --project-dir /path/to/project
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/flex_observability.py" \
  serve
```

The plugin dispatcher wraps these to surface them as `/flex:observability register`, etc.

---

## Known limitations — Phase 63

- No write routes; dashboard is read-only. Phase 64 adds controls bound to
  `phase2_writable: true` threshold triples.
- Sidebar runs in parallel; both surfaces work simultaneously. Sidebar retirement is a
  separate later phase after Phase 64 controls ship and feature parity is established.
- Cross-repo aggregate charts are out of scope. Each registered repo gets a side-by-side
  panel; charts stay within one repo.
- No real-time updates via websocket; poll-on-navigate is the model.
- `flex_factor` is readable by context_budget.py but not settable via SPA in Phase 63.
