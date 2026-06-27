---
id: RELEASE-005
rail: RELEASE
title: "Fleet discovery tool + snapshot (DP8)"
status: complete
phase: "HARNESS001-ante1"
story_class: code
primary_files:
  - skills/pairmode/scripts/fleet_discovery.py
  - tests/pairmode/test_fleet_discovery.py
touches:
  - docs/architecture.md
  - docs/fleet-snapshot.md
---

# RELEASE-005 — Fleet discovery tool + snapshot (DP8)

## Context

This story LANDS ON `main` (which stays 0.2.x). It is additive — a new
standalone script plus a test; it does NOT modify `flex_build.py` (whose surface
is frozen per DP4).

Per **DP8** (✅ AGREED): build a repeatable, READ-ONLY discovery command that
lists projects bound to THIS flex checkout, detecting **both** binding signals:

1. A project `CLAUDE.build.md` whose `pairmode_scripts_dir` references this flex
   checkout (the authoritative binding mechanic, DP5 — `pairmode_scripts_dir =
   Path(__file__).parent` baked at sync time).
2. A `.companion/state.json` carrying `pairmode_version` (the version-nag
   signal).

The known fleet is uncertain: `registered_projects` lists only
`/mnt/work/coherra`; docs additionally name forqsite, radar, asp, aab, cora,
lumin, halfhorse. The true `FLEX_DIR`-consumer set is not enumerable from
config alone — hence a scanning tool.

The tool records a current snapshot. The docs must state that **the
authoritative pre-fold run of this tool is a HARD GATE immediately before the
fold** (under Option Y, the fold makes `/mnt/work/flex` = 0.3.0, so any
un-migrated bound project breaks at the fold; the fleet may change across the
era, so the pre-fold run is what licenses the fold).

## Acceptance criteria

1. A new standalone script `skills/pairmode/scripts/fleet_discovery.py` exists,
   exposing a repeatable READ-ONLY command (e.g. a click command, or
   `if __name__ == "__main__"` CLI). It writes nothing to any scanned project —
   read-only is a hard property.

2. The command scans a set of candidate project directories (default: the
   `registered_projects` from this checkout's `.companion/state.json` plus the
   documented candidate dirs under `/mnt/work/`; overridable via a
   `--candidate-dir` / `--candidates-file` option) and, for each, detects the
   two binding signals:
   - **Signal 1 (scripts binding):** the project's `CLAUDE.build.md` contains a
     `pairmode_scripts_dir` that resolves under THIS flex checkout
     (`Path(__file__).parent.parent` = the `skills/pairmode/scripts` of this
     checkout, or its parent flex root). Match on the resolved flex-root path,
     not a brittle string compare.
   - **Signal 2 (version binding):** the project's `.companion/state.json` has a
     `pairmode_version` key.

3. The command output lists, per discovered project: its path, whether Signal 1
   is present (and the `pairmode_scripts_dir` it found), and whether Signal 2 is
   present (and the `pairmode_version` value). A project bound by either signal
   is reported; the report distinguishes "bound by scripts path" from "bound by
   version only."

4. Running the command records a current snapshot to a committed file (e.g.
   `docs/fleet-snapshot.md` or a JSON under `docs/`), capturing the discovered
   fleet at this point in time. The snapshot is dated and names which signals
   each project matched.

5. The docs (the durable surface — `docs/architecture.md` fleet/observability
   area, or the snapshot file header) state that the **authoritative pre-fold
   run is a hard gate before the fold** (DP8), and that `registered_projects`
   stays drift-opt-in (distinct purpose; optionally seeded from the discovered
   fleet, never forced).

6. A test `tests/pairmode/test_fleet_discovery.py` exercises the detection logic
   against a temp-dir fixture fleet: a fake project with a matching
   `pairmode_scripts_dir` (Signal 1), one with only a `.companion/state.json`
   `pairmode_version` (Signal 2), and one with neither (not reported). Asserts
   the tool is read-only (the fixture files are unchanged after a run).

7. The full suite passes:
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Implementation guidance

- New script `fleet_discovery.py` — clearly additive; do NOT touch
  `flex_build.py`. Resolve THIS checkout's flex root from `__file__`
  (`Path(__file__).resolve().parents[2]` = flex root) — no hardcoded
  `/mnt/work/flex` (skill-isolation rule, checklist item 4). The default
  candidate list MAY include the documented `/mnt/work/*` names, but the binding
  match is computed relative to `__file__`, not a hardcoded self path.
- Read `registered_projects` from this checkout's `.companion/state.json` for
  the default candidate set; merge with the documented candidate names.
- Signal 1: parse the project's `CLAUDE.build.md`, grep the
  `pairmode_scripts_dir` value, `Path(...).resolve()`, test whether it is the
  same as / under this checkout's `skills/pairmode/scripts`.
- Signal 2: load the project's `.companion/state.json` (stdlib `json`), check
  for `pairmode_version`.
- Read-only: never open any scanned file for write; the test asserts this.
- Stdlib + already-listed `click`; no new `requirements.txt` entries.
- Snapshot: writing the snapshot file under `docs/` (this repo) is a write to
  THIS repo, not to a scanned project — that is fine and is the intended
  deliverable.

## Tests

`tests/pairmode/test_fleet_discovery.py` (new). Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_fleet_discovery.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Mutating `registered_projects` from discovery results (stays drift-opt-in;
  optional manual seeding only).
- The actual pre-fold gate RUN (executed at/before the fold, HARNESS006 /
  RELEASE-006 runbook) — this story builds the tool and records the *current*
  snapshot.
- Modifying `flex_build.py` (frozen surface).
