---
era: "003"
phase_class: production
---

# project — Phase HARNESS001-ante1: Versioning & upstream compatibility

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Establish the dev environment, version line, and compatibility guarantees for the Era 003 harness refactor before any refactor code lands. Create the isolated harness dev line (worktree + branch), tag the v0.2.0 fleet rollback anchor, reconcile plugin/pairmode versions to 0.3.0 on the harness line only, freeze the additive CLI surface with a guard test, document the four-point additive contract + state-ownership table + the effort.db != context-control invariant, ship a read-only fleet-discovery tool, and author the cutover/migration runbook. Preflight only — does not start the refactor (that begins at HARNESS001-main).

## Stories

| ID | Title | Status |
|----|-------|--------|
| RELEASE-001 | Dev-line & rollback anchor (DP1, DP2) | complete |
| RELEASE-002 | Version reconciliation + match-guard (DP3) | deferred |
| RELEASE-003 | CLI-surface freeze guard test (DP4.4) | complete |
| RELEASE-004 | Additive contract + state-ownership table (DP4, DP7) | planned |
| RELEASE-005 | Fleet discovery tool + snapshot (DP8) | planned |
| RELEASE-006 | Cutover & migration runbook (DP5, DP6) | planned |
| INFRA-185 | Isolate lesson_review CLIOutputClarity tests from live drift promotion (CER-057) | complete |

## Deferred stories

- **RELEASE-002** — Version reconciliation + match-guard. Built and committed on
  the `harness` branch (commit `175925d`; status `complete` there). It is
  harness-only by design (DP3 — the version bump must not land on `main` until
  cutover, or every fleet project nags "behind canon" prematurely). On `main` it
  is **deferred to the fold (HARNESS006 / RELEASE-006 cutover)**, when the artifact
  lands and it becomes `complete` on `main`. Marked `deferred` here so `next_story`
  (git-authoritative — `complete` requires a matching commit on the current branch)
  and the phase-completion check treat `main` as progressing past it. The fold will
  resolve the one-line status difference (main `deferred` ↔ harness `complete`) in
  favour of `complete`; RELEASE-006's runbook notes this reconciliation.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-HARNESS001-ante1 Cold-eyes checklist

— developer fills in after phase completion —
