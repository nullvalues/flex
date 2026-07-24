---
id: RELEASE-058
rail: RELEASE
title: Pre-fold discovery gate (DP8) — fresh fleet snapshot, hard block on un-migrated projects
status: backlog
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
touches:  # If this story changes any documented architecture, add docs/architecture.md to this list.
---

## Context

Phase 97 resumes HARNESS016-main's deferred tail and folds `fold-prep` into
`main` as pairmode `v0.3.0`. The fold (RELEASE-059) is a **breaking change** for
downstream consumers: at the flip the plugin CLIs shift under them and their
bootstrapped `CLAUDE.build.md` no longer matches, so a consumer that has not
deliberately migrated to `0.3.0` breaks the moment `main` moves. The era's
compatibility strategy (HARNESS001-ante1, DP1–DP8) keeps `main` on the stable
`0.2.x` line through the whole migration window precisely so no consumer breaks
before it has opted in.

DP8 is the **pre-fold discovery gate**: the last check before the fold. It takes
a *fresh* fleet snapshot — not a cached or stale one — and hard-blocks the fold
if any fleet project has not yet migrated to pairmode `0.3.0`. The gate exists so
the fold cannot proceed while a consumer would be silently broken by it. It is
the enforcement point for "the fold only happens once the fleet is ready."

This gate is deliberately sequenced **before** RELEASE-059 (the fold merge) and
**after** the per-project fleet migrations. Per the Phase 97 deferred-stories
note, the fleet migrations (originally RELEASE-043–057) no longer run from this
repo — each project migrates in its own session via its own build loop — so the
DP8 gate here reads each project's recorded `pairmode_version` from a freshly
regenerated fleet snapshot and blocks until every project reports `0.3.0`.

## Requires

- Phase 97 is the active phase; `HARNESS006-main` (the flip) is complete, so
  `0.3.0` is the version the fleet must reach before the fold.
- The fold to `main` (RELEASE-059) has **not** yet happened — this gate runs
  immediately before it and is its precondition.
- The per-project fleet migrations described in the Phase 97 `## Deferred
  stories` section have run in their own sessions; each fleet project has a
  recorded `pairmode_version` reflecting whether it reached `0.3.0`.
- **Human-review gap (see `status: revised`):** this stub carries **no
  `primary_files` frontmatter** and an empty `touches` list. Story-scoped write
  permissions are seeded from `primary_files`, so the concrete files this gate
  touches must be pinned before a builder is dispatched. Likely targets, to be
  confirmed by a human and recorded in frontmatter:
  - `docs/fleet-snapshot.md` — the fresh fleet-snapshot artifact this gate
    regenerates and reads (currently modified in the working tree).
  - the fleet-discovery / pairmode-status tooling under
    `skills/pairmode/scripts/` (e.g. `fleet_discovery.py`, `pairmode_status.py`)
    if the gate is implemented as a CLI check rather than a doc-only assertion.
  - a test file under `tests/pairmode/` for the gate logic (see § Tests).
- **Human-review gap (blocked precondition):** the Phase 97 deferred-stories
  note states RELEASE-058 "remains blocked, correctly, until the fleet actually
  migrates via this new per-project path." A human must confirm the fleet has in
  fact migrated (every project at `0.3.0`) before this gate can pass — a builder
  cannot manufacture that state.
- **Architecture-decision gap:** how the gate *hard-blocks* the fold (a
  non-zero-exit CLI the fold sequence calls; a checklist assertion RELEASE-059
  reads; a `state.json` / index flag) is not recorded in `docs/architecture.md`
  or the phase doc. This must be decided by a human before build.

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line. -->

- A fresh fleet snapshot is regenerated at gate time (the snapshot artifact,
  e.g. `docs/fleet-snapshot.md`, is rewritten from a live fleet-discovery scan,
  not read from a pre-existing cached copy).
- The snapshot records, per fleet project, the project name and its recorded
  `pairmode_version`.
- The gate produces a clear PASS/BLOCK verdict: it passes only when **every**
  discovered fleet project reports `pairmode_version` `>= 0.3.0`, and blocks
  otherwise.
- When at least one project is below `0.3.0`, the gate output names each
  un-migrated project and its current version, and the fold (RELEASE-059) is
  prevented from proceeding (the gate's block signal is observable to the fold
  step — exact mechanism per the resolved architecture-decision gap above).
- When the gate is implemented as a CLI, a passing gate exits 0 and a blocking
  gate exits non-zero.
- The pairmode test suite is green: `uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. Resolve the two human-review gaps first (see § Requires): pin `primary_files`
   in frontmatter, and confirm with the operator (a) that the fleet has migrated
   and (b) the chosen hard-block mechanism. Do not build until these are settled.
2. **Regenerate the fleet snapshot.** Run the existing fleet-discovery tooling
   (`fleet_discovery.py`, extended by INFRA-231 to cover the full candidate
   list) to produce a *fresh* snapshot of every fleet project, writing the
   snapshot artifact (`docs/fleet-snapshot.md`) from the live scan. Do not reuse
   a stale snapshot — freshness is the point of DP8.
3. **Read each project's `pairmode_version`.** For every discovered project,
   obtain its recorded methodology version (via `pairmode_status.py` or the
   equivalent recorded field). Compare each against the `0.3.0` threshold.
4. **Compute the gate verdict.** PASS only if every project is `>= 0.3.0`.
   Otherwise BLOCK, and emit the list of un-migrated projects with their current
   versions so the operator knows exactly what remains.
5. **Wire the hard block** using the mechanism resolved in step 1 (e.g. a
   non-zero CLI exit that RELEASE-059's fold sequence checks, or a documented
   precondition the fold step reads). The fold must not be able to proceed while
   the verdict is BLOCK.
6. Keep the change minimal and additive; do not alter the fold merge logic
   itself (that is RELEASE-059) or the per-project migration path.
7. Add a test under `tests/pairmode/` that exercises both verdicts: a synthetic
   all-`0.3.0` fleet passes, and a fleet with at least one sub-`0.3.0` project
   blocks (and names the offender).

## Tests

- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` — suite
  green.
- New test asserts the gate PASSES when every project reports `>= 0.3.0`.
- New test asserts the gate BLOCKS (non-zero exit / block verdict) when at least
  one project is below `0.3.0`, and that the offending project name appears in
  the output.
- Manual verification: run the gate against the real fleet snapshot and confirm
  the verdict matches the actual migration state of the fleet.

## Out of scope

- **The fold merge itself** — merging `fold-prep` into `main` and tagging
  `v0.3.0` is RELEASE-059; this story only gates it.
- **The per-project fleet migrations** — each project migrates in its own
  session via its own build loop (Phase 97 `## Deferred stories`); this gate does
  not perform migrations, it only verifies them.
- **Post-fold re-sync** of migrated projects (RELEASE-060) and worktree
  retirement (RELEASE-061).
- Changing the fleet-discovery candidate list (INFRA-231, already complete) or
  the `pairmode_version` comparison logic in `pairmode_status.py` beyond what the
  gate needs to read it.

## Resolution — operator override (2026-07-23)

The gate's fresh-snapshot check was run **manually** on 2026-07-23 — see
`docs/fleet-snapshot.md` (committed 2026-07-23). The verdict was **BLOCK**:
only **8 of 16** discovered fleet projects report pairmode `0.3.0`.
Un-migrated projects: **base56, caddy, cora (0.1.0), forqsite.help, halfhorse,
lumin, meander, pokus** (all at 0.2.0 except cora as noted). Discovery deltas:
`anchor` no longer appears in discovery; `stackabid` is newly discovered,
already at `0.3.0`.

The operator (David) **explicitly overrode the block**: the per-project
migration path is not working properly, so waiting on it would stall the fold
indefinitely. The override accepts that un-migrated projects break at the flip;
each will be **manually patched post-fold**. The fold (RELEASE-059) proceeds
under this override.

The gate CLI/tooling described in this spec was **not built**. This story is
waived by operator decision; its status is set to `backlog` (the closest
available status to "waived") and this section carries the real disposition.
