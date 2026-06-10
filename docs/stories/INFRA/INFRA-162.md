---
id: INFRA-162
rail: INFRA
title: "`flex-observability` Python CLI — register / unregister / list / serve"
status: complete
phase: "63"
story_class: code
primary_files:
  - skills/observability/scripts/flex_observability.py
  - tests/pairmode/test_flex_observability.py
touches: []
---

# INFRA-162 — `flex-observability` Python CLI: register / unregister / list / serve

## Context

The Python entry point for the Observability SPA. Manages the registry at
`~/.config/flex-observability/registry.json` and launches the Fastify server.

Follows the same Click-based CLI pattern used by other `flex` scripts
(`flex_build.py`, `pairmode_sync.py`). Python is used (not a Node script)
to stay consistent with the flex tooling convention.

## Ensures

### `skills/observability/scripts/flex_observability.py`

1. Click-based CLI with four subcommands: `register`, `unregister`, `list`, `serve`.

2. **`register --project-dir DIR [--name NAME] [--color HEX]`**
   - Resolves `DIR` to an absolute path. Rejects paths with fewer than
     3 components (depth guard, matching `pairmode_sync.py` convention).
   - If `NAME` is omitted, defaults to the final path component of `DIR`.
   - If `COLOR` is omitted, assigns the next colour from a fixed rotation:
     `["#7aa2f7","#e0af68","#9ece6a","#f7768e","#bb9af7","#7dcfff"]`.
   - Reads existing registry (or creates empty). If `project_dir` already
     registered, prints `already registered: <path>` and exits 0.
   - Appends `{"id": NAME, "project_dir": DIR, "color": COLOR}` to
     `repos` list and writes registry atomically (temp file + rename).
   - Prints `registered: <NAME> → <DIR>`.

3. **`unregister --project-dir DIR`** (or **`--name NAME`**)
   - At least one of `--project-dir` or `--name` required.
   - Removes matching entry from registry. If not found: `not registered`.
   - Writes registry atomically.
   - Prints `unregistered: <NAME>`.

4. **`list`**
   - Reads registry. Prints a table:
     ```
     ID          PROJECT_DIR              COLOR
     flex        /mnt/work/flex           #7aa2f7
     forqsite    /mnt/work/forqsite       #e0af68
     ```
   - If registry empty or absent: `No repos registered.`

5. **`serve [--port N] [--host HOST]`**
   - Default port: read from registry `default_port`, fallback to `7777`.
   - Default host: read from registry `bind_host`, fallback to `127.0.0.1`.
   - Locates `server.mjs` at
     `Path(__file__).parent.parent / "api" / "dist" / "server.js"`.
   - If `server.js` does not exist, prints:
     ```
     API server not built. Run:
       cd skills/observability && pnpm install && pnpm --filter @flex-obs/api build
     ```
     and exits 1.
   - Verifies `node` is on PATH. If not: prints guidance and exits 1.
   - Sets env vars `FLEX_OBS_PORT`, `FLEX_OBS_HOST`,
     `FLEX_OBS_REGISTRY=<registry_path>` before spawning.
   - Spawns `node <server.js>` via `subprocess.run` (blocking — serve is a
     foreground process). Ctrl-C propagates cleanly (catch KeyboardInterrupt,
     print "Server stopped.", exit 0).

6. Registry file path: `Path.home() / ".config" / "flex-observability" / "registry.json"`.
   Parent directory is created if absent.

7. Registry JSON schema (written by `register`):
   ```json
   {
     "version": 1,
     "repos": [
       {"id": "flex", "project_dir": "/mnt/work/flex", "color": "#7aa2f7"}
     ]
   }
   ```

### `tests/pairmode/test_flex_observability.py`

8. Uses `subprocess` to invoke the CLI via:
   ```python
   _SCRIPT = Path(__file__).parent.parent.parent / "skills/observability/scripts/flex_observability.py"
   def _run(*args, env=None):
       return subprocess.run(
           [sys.executable, str(_SCRIPT), *args],
           capture_output=True, text=True, env=env
       )
   ```

9. Fixture: `tmp_registry` — a `tmp_path`-backed registry path, injected
   via `FLEX_OBS_REGISTRY_PATH` env var (add env var support to the script:
   `FLEX_OBS_REGISTRY_PATH` overrides the default `~/.config/...` path).

10. Required test cases:

    - **`test_register_adds_entry`** — register `/mnt/work/flex`. Assert
      registry has one entry with `id="flex"`, `project_dir="/mnt/work/flex"`.

    - **`test_register_idempotent`** — register same path twice. Assert
      registry has one entry; exit 0 on second call.

    - **`test_register_depth_guard`** — register `/a/b`. Assert exit 1.

    - **`test_register_custom_name_and_color`** — `--name myrepo --color #aabbcc`.
      Assert registered entry has correct id and color.

    - **`test_unregister_removes_entry`** — register then unregister. Assert
      registry empty; exit 0.

    - **`test_unregister_not_registered`** — unregister path not in registry.
      Assert exit 0; stdout contains `not registered`.

    - **`test_list_empty`** — no registry. Assert stdout contains
      `No repos registered.`

    - **`test_list_shows_entries`** — register two repos. Assert list output
      contains both ids and project_dirs.

## Instructions

- Use `click` (already in flex's requirements). No new Python dependencies.
- Atomic write: write to `<registry>.tmp`, then `os.replace(tmp, registry)`.
- The `serve` subcommand uses `subprocess.run` not `subprocess.Popen` — it
  blocks the CLI process, which is the correct UX for a foreground server.
- `FLEX_OBS_REGISTRY_PATH` env var for testability must be checked before
  the default path in all subcommands (not just in `serve`).

## Tests

Run:
```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_observability.py -x -q
```
All tests must pass.

## Out of scope

- A `status` subcommand showing whether the server is running.
- Multiple simultaneous server instances.
- Auto-start on session open.
- The `serve` subcommand wiring into the Fastify prod build (that's confirmed
  by the manual test in INFRA-156).
