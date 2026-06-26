---
id: RELEASE-002
rail: RELEASE
title: "Version reconciliation + match-guard (DP3)"
status: planned
phase: "HARNESS001-ante1"
story_class: code
primary_files:
  - skills/pairmode/scripts/_version.py
  - skills/pairmode/SKILL.md
  - .claude-plugin/plugin.json
  - .claude-plugin/marketplace.json
  - tests/pairmode/test_version_match.py
touches:
---

# RELEASE-002 — Version reconciliation + match-guard (DP3)

## Context

> **BRANCH PLACEMENT — READ FIRST.** This story LANDS ON THE `harness` BRANCH
> ONLY (in the `/mnt/work/flex-harness` worktree). It MUST NOT touch `main`.
> Bumping `PAIRMODE_VERSION` on the fleet-facing checkout would make every
> fleet project's SessionStart hook immediately print "behind canon — run
> sync" before 0.3.0 is ready and syncable. `main` stays `0.2.x` through the
> entire migration window; the bump reaches the fleet's line only at cutover
> (DP5), where the nag firing is the *intentional* "run sync now" trigger.

Per **DP3** (✅ AGREED), the two version numbers are reconciled:

- **Pairmode methodology:** `0.2.0` → `0.3.0-dev` on `harness` (finalized to
  `0.3.0` at the flip, HARNESS006). Single-sourced from
  `skills/pairmode/scripts/_version.py` and mirrored in `SKILL.md` frontmatter.
- **Plugin version:** `.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` → `0.3.0`. Documented rule: "plugin version
  and pairmode version bump together." This is NOT single-sourced into the JSON
  manifests (not worth a build step) — it is two manually-synced fields guarded
  by one small test.

The plugin manifests use the bare semver `0.3.0` (no `-dev` suffix); the
methodology version carries `0.3.0-dev` on the dev line. The match-guard test
asserts the plugin version matches the *release core* of the pairmode version
(i.e. `0.3.0-dev` and `0.3.0` are considered a match on the `0.3.0` core).

## Acceptance criteria

1. `skills/pairmode/scripts/_version.py`: `PAIRMODE_VERSION` is `"0.3.0-dev"`.

2. `skills/pairmode/SKILL.md` frontmatter: `pairmode_version` is `"0.3.0-dev"`
   (mirrors `_version.py`).

3. `.claude-plugin/plugin.json`: `version` is `"0.3.0"`.

4. `.claude-plugin/marketplace.json`: the flex plugin entry's `version` is
   `"0.3.0"`.

5. A new test file `tests/pairmode/test_version_match.py` exists and asserts the
   "bump together" rule: the plugin manifest version (`plugin.json`, and
   `marketplace.json`'s flex entry) equals the release core of
   `PAIRMODE_VERSION` (with any `-dev`/pre-release suffix stripped before the
   comparison). The test reads the live values from the four files — it does not
   hardcode `0.3.0` as the only acceptable answer, so it keeps guarding after
   the `0.3.0-dev → 0.3.0` finalization at the flip.

6. The test also asserts `SKILL.md`'s `pairmode_version` frontmatter equals
   `PAIRMODE_VERSION` (the mirror invariant).

7. The full suite passes:
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

## Implementation guidance

- Edit `_version.py`: `PAIRMODE_VERSION: str = "0.3.0-dev"`.
- Edit `SKILL.md` frontmatter line `pairmode_version: "0.2.0"` → `"0.3.0-dev"`.
- Edit `plugin.json` `"version": "0.1.0"` → `"0.3.0"`.
- Edit `marketplace.json` — the `version` field inside `plugins[0]` (the flex
  entry) `"0.1.0"` → `"0.3.0"`.
- New test `tests/pairmode/test_version_match.py`:
  - Import `PAIRMODE_VERSION` from `skills.pairmode.scripts._version` (conftest
    puts the repo root on `sys.path`).
  - Parse `plugin.json` and `marketplace.json` with `json` (stdlib).
  - Parse `SKILL.md` frontmatter version with a small regex / `str.split`
    (avoid adding a YAML dependency — stdlib only, per Python standards).
  - Compute the release core of `PAIRMODE_VERSION` by stripping at the first
    `-` (`PAIRMODE_VERSION.split("-")[0]`).
  - Assert: `plugin.version == core`, `marketplace flex entry version == core`,
    `skill_frontmatter_version == PAIRMODE_VERSION`.
- Use only stdlib (`json`, `re`/`pathlib`) — no new entries in
  `requirements.txt`.

## Tests

`tests/pairmode/test_version_match.py` (new). Run:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_version_match.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Finalizing `0.3.0-dev → 0.3.0` (happens at the flip, HARNESS006 / RELEASE-006
  runbook).
- Single-sourcing the plugin version into the JSON manifests via a build step
  (explicitly rejected in DP3 — two manually-synced fields + one guard test).
- Any change on `main` — this story is harness-only.

### Protected-file note (reviewer)

`.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are PROTECTED
files (CLAUDE.md review checklist item 7). They are modified here **deliberately
and for a stated reason: version reconciliation per DP3** (plugin version
aligned to `0.3.0`, bumping together with the pairmode methodology version).
This is the sanctioned reason; the protected-file check should PASS on that
basis.
