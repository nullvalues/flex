---
id: INFRA-249
rail: INFRA
title: Self-sync flex's .companion/state.json — pairmode_version to 0.3.0, verify banner correctness
status: planned
phase: "99"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - .companion/state.json
touches:
  - docs/fleet-snapshot.md
---

## Context

This is an **operational story** in the INFRA-209 mold (filed as
`story_class: code` for the same schema reason INFRA-209 documents: the
validator has no "operational" class and requires non-empty `primary_files`).

The RELEASE-059 fold shipped pairmode v0.3.0 —
`skills/pairmode/scripts/_version.py` says `PAIRMODE_VERSION = "0.3.0"`,
`.claude-plugin/plugin.json` says `"version": "0.3.0"` — but flex's own
`.companion/state.json` still records `"pairmode_version": "0.2.0"`. The
SessionStart banner therefore announces "Pairmode v0.2.0 is active in this
repo" (`session_start.py` reads the state key), and any `pairmode audit`
comparison keyed on `state.json`'s version will misreport flex itself.

flex is the one project that never receives `pairmode sync` from itself; the
fold updated the scaffold but nothing updated the consumer-side state. Two
stale keys were already corrected manually during spec-writing for this phase
(`current_story` pinned to the long-complete INFRA-209, and its
`story_scope.json`, which together blocked writing the phase-99 spec); this
story completes the self-sync and makes the correction durable and verified.

## Requires

- INFRA-247 and INFRA-248 complete, so the banner verification in Ensures
  runs against the deduplicated hook registration and a trustworthy counter.
- Use the sanctioned mechanism where one exists (`pairmode sync` applied to
  flex itself, or the narrowest documented state-update path) rather than
  hand-editing JSON; if no sanctioned path can target flex itself, that gap
  is recorded and the manual edit documented.

## Ensures

1. `.companion/state.json` records `"pairmode_version": "0.3.0"`, matching
   `_version.PAIRMODE_VERSION`.
2. `current_story` remains absent/cleared (no re-stamp of INFRA-209 by any
   tooling run during this story), and no stale `story_scope.json` exists.
3. A fresh session's SessionStart banner reports "Pairmode v0.3.0 is active
   in this repo." — exactly once (once is INFRA-247's guarantee; 0.3.0 is
   this story's).
4. `docs/fleet-snapshot.md` (or the equivalent rollout record) notes that
   flex itself is now at 0.3.0, so the phase-97 fleet re-sync has an accurate
   baseline row for the hub repo.
5. If a sanctioned self-sync path did not exist and manual state editing was
   required, the gap is recorded (CER/backlog entry or build note) so
   phase-97's re-sync tooling can close it.

## Build notes (2026-07-24)

- **No sanctioned narrow self-sync path exists for flex's own
  `.companion/state.json`.** `.companion/` is git-ignored and, per INFRA-238,
  a per-story worktree is deliberately created without a `.companion/` of its
  own (`flex_build.py create-story-worktree`: "the worktree has no
  `.companion/` of its own; `scope_guard.py` always resolves state from the
  main checkout regardless of cwd"). The only two version-writing mechanisms
  (`bootstrap.py`'s `main` and `sync.py`'s `sync_project`) are full-scaffold
  operations, not a targeted `pairmode_version` write, and both would still
  have to target `project_dir=/mnt/work/flex` — the main checkout — which a
  worktree-confined builder cannot touch (`CLAUDE.build.md`: "The builder and
  reviewer operate inside the returned worktree path, never the main project
  directory").
- Per Ensures #5's documented fallback, and mirroring INFRA-247's
  operator-applied `.claude/settings.json` precedent, **the state write was
  applied by the operator/orchestrator directly against the main checkout**,
  outside this worktree and outside the builder/reviewer loop:
  `/mnt/work/flex/.companion/state.json` now reads
  `"pairmode_version": "0.3.0"`, verified before/after the edit. `current_story`
  and `.claude/story_scope.json` were already clean (no re-stamp of
  INFRA-209; no stale `story_scope.json`) — verified independently before the
  operator action, so no further correction was needed there.
- Banner verification (Ensures #3): `hooks/session_start.py` reads
  `pairmode_version` directly from `.companion/state.json` and formats
  `f"Pairmode v{pairmode_version} is active in this repo."` — with the main
  checkout's state now at `0.3.0`, a fresh session's banner reads "Pairmode
  v0.3.0 is active in this repo." The once-only guarantee is INFRA-247/248's
  (hook-registration dedupe), unchanged by this story.
- The in-worktree portion of this story (this Build notes section and the
  `docs/fleet-snapshot.md` note) was completed after the operator's state
  write, so the note in `docs/fleet-snapshot.md` is accurate at the time it
  was written.
