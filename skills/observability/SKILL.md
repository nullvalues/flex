---
name: flex:observability
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
- `--host HOST` — bind to HOST instead of 127.0.0.1 (default: 127.0.0.1 loopback only)

**Typical workflow:**
```bash
flex_observability.py serve
# Browser opens automatically; dashboard shows all registered projects
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
flex_observability.py register --project-dir /mnt/work/forqsite --name "forqsite" --color "#e0af68"
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
flex_observability.py unregister --name forqsite
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
  forqsite    — /mnt/work/forqsite (#e0af68)
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
policies (from `~/.claude/policies/*.md`), listed with filename, first heading, modification
time, and absolute path.

---

## Architecture notes

- **Workspace:** `skills/observability/api/` (Fastify 5 backend) + `skills/observability/ui/`
  (Vite + React 19 frontend) sharing a pnpm workspace root.
- **Registry path:** `~/.config/flex-observability/registry.json`. Survives `rm -rf .companion/`
  in any repo. Managed only by the CLI; Fastify reads it on every request (cheap at ≤10 entries).
- **Database read-only:** Fastify opens `effort.db` with `?mode=ro` URI parameter — no write
  contention with running pairmode sessions.
- **Loopback-only:** Server binds to `127.0.0.1:7777` (dev-local, not exposed to a network
  interface).
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
