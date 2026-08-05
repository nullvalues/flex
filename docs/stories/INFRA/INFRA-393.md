---
id: INFRA-393
rail: INFRA
title: Externalize fleet_discovery.py's hardcoded repo list into a local gitignored config (CER-172)
status: draft
phase: "125"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_discovery.py
  - .gitignore
touches:
  - tests/pairmode/test_fleet_discovery.py
  - .pairmode-fleet.local.json.example
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

`fleet_discovery.py`'s `_DOCUMENTED_CANDIDATES` module constant (around line 57)
hardcodes a literal list of real sibling-repo directory names under `/mnt/work/`
as a fallback candidate source for `_default_candidates()`. This repo is public;
committing real names of private sibling repos in source code is the bug CER-172
tracks. This story is the prerequisite half of the fix: move that list out of
committed source into a local, gitignored config file, shaped so the same file
can also serve INFRA-394 as the real→anonymized-label mapping for scrubbing
already-committed docs. INFRA-394 cannot run for real until this story lands —
it depends on the local config file and its loader existing.

## Requires

None — first story in Phase 125, no story prerequisite.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| .pairmode-fleet.local.json.example | story requires creating tracked example template file at repo root, not declared in primary_files/touches | 2026-08-05T11:55:41Z |

## Ensures

- `fleet_discovery.py`'s source contains no `_DOCUMENTED_CANDIDATES` symbol and
  no hardcoded repo-name string literal; the only source of extra fleet
  candidates beyond `registered_projects` is a new `_load_local_fleet_map()`
  function that reads a local config file.
- `_load_local_fleet_map()` reads `<flex-root>/.pairmode-fleet.local.json`
  (a mapping of stable anonymized label, e.g. `"repo-a"`, to real absolute
  path, e.g. `"repo-a": "/mnt/work/<real-name>"`) and returns it as a
  `dict[str, str]`; when the file is missing, unreadable, or not valid JSON it
  returns `{}` — forbidden proxy: raising `FileNotFoundError` or
  `json.JSONDecodeError` instead of returning `{}` (same never-raise contract
  as the existing `_read_registered_projects()`).
- `_default_candidates()` builds its "documented" extra candidates from
  `Path(p) for p in _load_local_fleet_map().values()` instead of iterating the
  removed `_DOCUMENTED_CANDIDATES` name list under `work_dir`; behaviour for
  `registered_projects`-sourced candidates and the final dedupe pass is
  unchanged.
- `.gitignore` gains an entry for `.pairmode-fleet.local.json`; confirmed
  before adding that no existing pattern in `.gitignore` already matches that
  filename (i.e. this is a genuinely new ignore rule, not a no-op).
- A new tracked file `.pairmode-fleet.local.json.example` exists at the repo
  root, is valid JSON, and every key/value in it is a clearly-fake placeholder
  (e.g. `"example-repo-1": "/path/to/example-repo-1"`) — no real repo name or
  real absolute path appears in it.
- `tests/pairmode/test_fleet_discovery.py` covers the local-config-driven path:
  present-file-with-entries (candidates include the mapped paths),
  absent-file (`_load_local_fleet_map()` returns `{}`, no crash), and
  malformed-JSON (also returns `{}`, no crash) — plus a structural test
  asserting the source no longer defines `_DOCUMENTED_CANDIDATES`.
- `uv run pytest tests/pairmode/test_fleet_discovery.py -q` passes.

## Instructions

1. In `fleet_discovery.py`, remove the `_DOCUMENTED_CANDIDATES` list entirely.
   Add a module constant `_LOCAL_FLEET_CONFIG_FILENAME = ".pairmode-fleet.local.json"`
   and a `_load_local_fleet_map() -> dict[str, str]` function, placed near
   `_read_registered_projects()` and following its same defensive shape (open
   `_FLEX_ROOT / _LOCAL_FLEET_CONFIG_FILENAME`; on `FileNotFoundError`,
   `OSError`, or `json.JSONDecodeError`, return `{}`; otherwise return the
   parsed JSON object as-is — do not validate label/path shape beyond "is a
   JSON object", since that is an operator-owned local file).
2. Update `_default_candidates()` so the "documented" branch iterates
   `_load_local_fleet_map().values()` (each value is a real absolute path
   string) instead of the removed name list. The existing `registered_projects`
   branch and the final resolve-and-dedupe loop are unchanged.
3. Update the module docstring / the comment above the removed constant to
   describe the new local-config mechanism (filename, shape, and a pointer to
   `.pairmode-fleet.local.json.example`) without naming any real repo.
4. Add `.pairmode-fleet.local.json` to `.gitignore`, with a short comment in
   the same style as the file's existing entries, referencing CER-172 as the
   reason (a fleet-local, per-operator file that must never be committed).
5. Create `.pairmode-fleet.local.json.example` at the repo root containing 2-3
   placeholder entries in the target shape (label → fake path). This is the
   template a fresh operator copies to `.pairmode-fleet.local.json` and fills
   with their own real fleet paths.
6. Update `tests/pairmode/test_fleet_discovery.py`: add a test class (e.g.
   `TestLocalFleetConfig`) that monkeypatches `fd._FLEX_ROOT` to a `tmp_path`,
   writes a `.pairmode-fleet.local.json` there with fake labels/paths, and
   asserts `_load_local_fleet_map()` returns the expected dict and that
   `_default_candidates()`'s resolved set includes those paths. Add a
   missing-file case and a malformed-JSON case, both asserting `{}`/no crash.
   Add one structural test that reads `fd.__file__`'s source text and asserts
   the substring `_DOCUMENTED_CANDIDATES` is absent, as a regression guard
   against the old hardcoded-list shape resurfacing.
7. Do not populate `.pairmode-fleet.local.json` itself with any real path as
   part of this story's diff — it is gitignored and per-operator; only the
   `.example` template is committed.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_fleet_discovery.py -q
```
Acceptance: green, including the new local-config coverage (present/absent/
malformed cases) and the `_DOCUMENTED_CANDIDATES`-absence structural test.

## Out of scope

- INFRA-394's scrub of already-committed docs that mention real repo names —
  a separate story that depends on this one's local config existing.
- Populating `.pairmode-fleet.local.json` with this operator's actual fleet —
  a local, uncommitted, per-operator action outside any story's committed diff.
- Changing `_read_registered_projects()`'s `.companion/state.json`-based
  signal, or any other fleet-discovery signal (Signal 1/2, duplicate-hooks,
  machine-absolute-hooks checks) — untouched, unrelated mechanisms.
