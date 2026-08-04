---
id: INFRA-384
rail: INFRA
title: Document version-bump-before-reinstall discipline and accepted @inline dual-registration limitation
status: complete
phase: "120"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/architecture.md
  - docs/cer/backlog.md
touches: []
narrative_roles: []
model: sonnet  # lower: documentation-only, two prose edits, no logic
---

## Context

CER-159's investigation surfaced two facts that INFRA-383's migration does not
resolve and that will be lost with this session's context if not written down.
(1) flex's marketplace install copies the plugin into a **version-keyed cache
directory**, not a live symlink to source — so a reinstall against an unchanged
version string can silently no-op onto a stale cache. This was observed directly:
a second machine in this fleet was running a cache snapshot frozen at 2026-07-28
(commit `0bab2ee`, `plugin.json` version 0.3.0) while its source tree had
advanced ~30 commits, with 41 file diffs in `skills/pairmode` and
`hooks/subagent_stop.py` missing from the cache entirely. (2) Once a project both
has its own `.claude-plugin/plugin.json` at cwd root and is installed as a
marketplace plugin, **both registrations load in the same session** — confirmed
via `~/.claude.json`'s `pluginUsage` map incrementing `flex@inline` and
`flex@nullvalues-flex` together across a restart — and no supported way to
suppress the inline one was found. This story writes both down: the first as
forward-looking operational discipline (which needs a home outside the CER
backlog, since it is a practice, not a closed finding), the second as an accepted
limitation this project stops chasing.

## Requires

None blocking. INFRA-383 establishes the marketplace install this text describes,
so building after it reads more naturally, but this story touches no code and can
land in either order.

## Ensures

1. `docs/architecture.md` documents the version-bump-before-reinstall discipline:
   it names the version-keyed cache path shape
   (`~/.claude/plugins/cache/nullvalues-flex/flex/<version>/`), states that a
   reinstall at an unchanged version can no-op onto the stale cache, and gives the
   two remedies — bump the declared version in `.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json` *before* reinstalling, or delete the stale
   cache directory first. Forbidden proxy: a CER backlog row alone — a
   forward-looking practice recorded only in a findings list is not durably
   documented.
2. That same passage records the observed evidence (the 0.3.0 / `0bab2ee` /
   2026-07-28 frozen cache, 41 diffs in `skills/pairmode`, absent
   `hooks/subagent_stop.py`) so the rationale survives without this session.
3. `docs/architecture.md` records the `@inline` dual-registration as an **accepted
   limitation**, stating all three of: both registrations load simultaneously;
   `claude plugin disable flex@inline -s project` exits 0 and writes
   `"enabledPlugins": {"flex@inline": false}` to `.claude/settings.json` but has no
   functional effect on the inline auto-load; the accepted cost is wasted hook exec
   cycles and misleading `pluginUsage` telemetry, with no correctness regression.
4. `docs/cer/backlog.md` carries the `@inline` dual-registration limitation as a
   row (new row, or an annotation on CER-159), marked as an upstream Claude Code
   CLI gap that is not fixable in this project.
5. No version string is changed by this story: `git diff` after the build shows no
   modification to `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`.
   Forbidden proxy: bumping the version "while we're here".

## Instructions

1. Place the two passages in `docs/architecture.md`'s existing plugin/hooks
   section (the section that already describes plugin packaging and
   `CLAUDE_PLUGIN_ROOT`), as a short subsection each. Do not create a new
   top-level document.
2. Write the dual-registration passage in accepted-limitation voice, not
   open-bug voice: it is closed for this project. Note as a recommendation (not a
   requirement of this story) that it is worth filing upstream via `/feedback`.
3. Use `docs/cer/backlog.md`'s existing row format for Ensures 4; match how other
   "found via direct investigation, not fixable here" rows are written.
4. Keep both passages tight — this is a durable note, not a narrative of the
   investigation.

Spec-preflight note: `hooks/subagent_stop.py` appears in this spec as cited
evidence (it was absent from the stale cache) and is deliberately not in
`primary_files`/`touches` — this story does not modify it.

## Tests

Documentation story — no test file expected. Run the suite as a regression check
only:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green (unchanged from pre-story state), and
`git diff --name-only` lists only `docs/architecture.md` and
`docs/cer/backlog.md`.

## Out of scope

- Performing a version bump. The one affected machine already had its stale cache
  wiped manually; no bump is needed now. This story only ensures the discipline is
  not forgotten the next time it matters.
- Building any workaround for the dual registration — in particular relocating
  `.claude-plugin/plugin.json`. Considered and rejected: this repo's own
  self-reference depends on that file being exactly where it is, so the workaround
  carries more risk than the limitation it removes.
- The migration itself (marketplace install, hook-firing verification) — that is
  INFRA-383.
