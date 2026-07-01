---
id: RELEASE-007
rail: RELEASE
title: Fold preparation — version finalize, Signal-1 diagnosis, runbook gate, RELEASE-002 reconcile
status: complete
phase: "HARNESS006-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/_version.py
  - skills/pairmode/scripts/fleet_discovery.py
  - docs/harness-cutover-runbook.md
  - tests/pairmode/test_fold_preparation.py
touches:
  - docs/stories/RELEASE/RELEASE-002.md
  - docs/fleet-snapshot.md
---

## Context

The buildable/checkable preparation for the fold (agreements `HARNESS006-main.md` DP4/DP5;
CER-059 a/b/c; runbook Phase 1 + pre-fold discovery gate). The **irreversible git fold** (merge
`harness` → `main`, tag `v0.3.0`, re-sync, remove worktree) stays an operator action per
`docs/harness-cutover-runbook.md` § Final fold sequence. This story delivers the parts that must
be true **before** that merge: the version finalize, the CER-059(a) Signal-1 diagnosis, the
CER-059(b) runbook verification step, and the CER-059(c) RELEASE-002 reconciliation AC.

## Requires

- HARNESS-001/-002/-003 complete: the thin loop, the dogfood flip, and the comingling removal
  — the fold is only safe once these exist.
- HARNESS001-ante1 RELEASE-005/006: `fleet_discovery.py` and the cutover runbook exist.

## Ensures

- **Version finalize:** `skills/pairmode/scripts/_version.py` `PAIRMODE_VERSION` `"0.3.0-dev"`
  → `"0.3.0"` (the "migration-ready" marker). The version-match guard
  (`tests/pairmode/test_version_match.py`) stays green (plugin manifests already `0.3.0`).
- **CER-059(a) Signal-1 diagnosis:** the zero-Signal-1-hit in `docs/fleet-snapshot.md` is
  diagnosed — determine whether `fleet_discovery._check_signal1` has a path-resolution bug
  (`relative_to` vs `_THIS_SCRIPTS_DIR`/`_FLEX_ROOT`) or the projects baked an absolute path
  that no longer resolves. If it is a detection bug, fix `_check_signal1` so a scripts-bound
  project reports `binding: scripts`; if accurate, record the finding. A test exercises a
  synthetic scripts-bound project tree and asserts Signal-1 is detected.
- **CER-059(b) runbook gate step:** `docs/harness-cutover-runbook.md` § Pre-fold discovery gate
  gains an explicit Signal-1 verification step ("after syncing each project, re-run discovery
  and confirm `binding: scripts` appears").
- **CER-059(c) RELEASE-002 reconciliation AC:** this story carries an explicit, checkable AC
  that `docs/stories/RELEASE/RELEASE-002.md` status is reconciled `deferred → complete` on
  `main` **after** the fold merge (the runbook notes it in prose; here it is a checkable AC).
  The reconciliation itself is part of the operator fold; this story records the AC and a test
  that fails if RELEASE-002 is still `deferred` once the fold tag exists (skipped/xfail pre-fold).
- **Dogfood verification recorded:** the runbook Phase 1 acceptance (flex builds on the new loop;
  `pairmode_version` == `0.3.0` after self-sync) is captured in the phase cold-eyes checklist.
- `tests/pairmode/test_fold_preparation.py` asserts deterministically: `_version.py` == `0.3.0`;
  Signal-1 detection passes on a synthetic scripts-bound tree; the runbook contains the Signal-1
  verification step; the RELEASE-002 reconciliation AC is present (pre-fold: assert the AC text
  exists; the status-flip check is xfail until the fold tag exists).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- This story does **not** perform the git merge/tag/worktree-removal — those are operator actions
  in the runbook. Deliver the version finalize, the Signal-1 fix/diagnosis, the runbook step,
  and the RELEASE-002 AC + guard test.
- For CER-059(a): write a focused test with a synthetic project whose `CLAUDE.build.md`'s
  `pairmode_scripts_dir` points under the harness scripts dir, and assert `_check_signal1`
  returns a hit. If the current code already handles it, the diagnosis records "accurate (baked
  stale absolute path)" and the runbook step covers re-detection post-sync.
- Keep the RELEASE-002 status-flip assertion xfail/skip pre-fold so the build gate stays green
  on the `harness` branch; it becomes a real check after the operator folds.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_fold_preparation.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_version_match.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: `_version.py` == `0.3.0`; Signal-1 detection diagnosed/fixed; runbook Signal-1 step
present; RELEASE-002 reconciliation AC present (status-flip guard xfail pre-fold); version-match
green; full suite green.

### Out of scope

- The irreversible git fold (merge/tag/re-sync/worktree-removal) — operator, per the runbook.
- The thin loop / agent retirement / comingling removal — HARNESS-001/002/003.
- Fleet Phases 2–3 migration (operator).
