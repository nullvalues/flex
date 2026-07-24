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
