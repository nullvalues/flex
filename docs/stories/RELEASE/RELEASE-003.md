---
id: RELEASE-003
rail: RELEASE
title: "CLI-surface freeze guard test (DP4.4)"
status: planned
phase: "HARNESS001-ante1"
story_class: code
primary_files:
  - tests/pairmode/test_cli_surface_freeze.py
  - tests/pairmode/fixtures/cli_surface_0_2.json
touches:
---

# RELEASE-003 — CLI-surface freeze guard test (DP4.4)

## Context

This story LANDS ON `main` (which stays 0.2.x). It is purely additive — a new
test and a snapshot fixture; it does not modify `flex_build.py` or any existing
file.

Per **DP4** (✅ AGREED — the four-point additive contract, scoped to the
additive window `HARNESS001-main … HARNESS005-main`), point 1 freezes the
existing CLI surface: no rename / removal / flag-change to existing
`flex_build.py` subcommands. Additions (notably `next-action`) are allowed;
consolidation/removal of old CLIs happens only at/after the flip. DP4.4
requires a guard test that **snapshots the 0.2.x `flex_build.py` command/flag
surface and asserts the live surface stays a SUPERSET of it** (additions OK;
removals/renames FAIL) through the additive window. The snapshot is rebaselined
at the flip (HARNESS006).

`flex_build.py` exposes a click group named `flex_build` (`@click.group()`);
each subcommand is registered via `@flex_build.command("name")` with
`@click.option(...)` flags. The surface is introspectable through click's
object model (`group.commands` → `{name: Command}`; each `Command.params` →
options/arguments).

## Acceptance criteria

1. A snapshot fixture `tests/pairmode/fixtures/cli_surface_0_2.json` records the
   current (0.2.x) `flex_build.py` surface: for every subcommand, its name and
   the set of its option/argument names (flag long-names). This fixture is the
   frozen baseline.

2. A new test `tests/pairmode/test_cli_surface_freeze.py` introspects the LIVE
   `flex_build` click group (via click's object model — `group.commands` and
   each command's `params`) and builds the same shape.

3. The test asserts the live surface is a **superset** of the snapshot:
   - Every subcommand in the snapshot is still present in the live group
     (no removed/renamed command) — else FAIL.
   - For every snapshotted command, every snapshotted flag is still present on
     the live command (no removed/renamed flag) — else FAIL.
   - Commands or flags present live but absent from the snapshot are ALLOWED
     (additions do not fail the test).

4. The failure messages name the specific missing command(s)/flag(s) so a
   regression is diagnosable without reading the diff.

5. The full suite passes:
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Implementation guidance

- Import the click group object directly:
  `from skills.pairmode.scripts.flex_build import flex_build` (conftest puts the
  repo root on `sys.path`). Do not shell out and parse `--help`; use click's
  object model — it is stable and exact.
- Surface extraction (live):
  ```python
  surface = {
      name: sorted(
          opt
          for p in cmd.params
          for opt in (p.opts if hasattr(p, "opts") else [p.name])
      )
      for name, cmd in flex_build.commands.items()
  }
  ```
  Normalize to long flag names (the strings in `param.opts`, e.g.
  `--story-id`). Argument params (no `--`) may be recorded by their declared
  name; keep the chosen normalization consistent between the fixture generator
  and the test.
- Generate the fixture by serializing the live surface once with stdlib `json`
  (a tiny `if __name__ == "__main__":` generator block in the test file, or a
  one-off documented in this guidance). Commit the produced
  `cli_surface_0_2.json`.
- The assertion is subset-of-snapshot ⊆ live (superset check), NOT equality —
  equality would fail the moment `next-action` is added in HARNESS001-main,
  which is exactly the addition the contract permits.
- Stdlib only (`json`) + the already-listed `click` dependency; no new
  `requirements.txt` entries.

## Tests

`tests/pairmode/test_cli_surface_freeze.py` (new) +
`tests/pairmode/fixtures/cli_surface_0_2.json` (new fixture). Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cli_surface_freeze.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Output-contract stability of individual commands — DP4.4 states that rides on
  the existing per-command unit tests, not this surface guard.
- Rebaselining the snapshot — done at the flip (HARNESS006), not here.
- Any modification to `flex_build.py` itself (its surface is frozen, not edited).
