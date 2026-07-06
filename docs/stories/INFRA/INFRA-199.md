---
id: INFRA-199
rail: INFRA
title: Signal-1 detection fix and runbook verification step
status: draft
phase: "HARNESS011-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_discovery.py
  - docs/harness-cutover-runbook.md
touches:
  - docs/fleet-snapshot.md
---

## Acceptance criterion

- **CER-059(a)** — `fleet_discovery.py` `_check_signal1` correctly detects projects that
  resolve their scripts path to the flex repo's scripts directory. The root cause of the
  zero-hits finding is diagnosed (false-negative in `relative_to` comparison vs.
  `_THIS_SCRIPTS_DIR`/`_FLEX_ROOT`, or accurate result if projects are genuinely not
  scripts-bound). If it is a false-negative: the detection logic is fixed and the fix is
  tested. If it is accurate: a comment is added explaining why zero hits is expected and
  the `docs/fleet-snapshot.md` note is updated accordingly.
- **CER-059(b)** — `docs/harness-cutover-runbook.md` has an explicit Signal-1
  verification step: after syncing each project, re-run discovery and confirm `binding:
  scripts` appears for that project before proceeding to the next.
- **CER-059(c)** — The runbook's existing HARNESS006 fold-execution step includes an
  explicit acceptance criterion: reconcile `docs/stories/RELEASE/RELEASE-002.md` status
  from `deferred` to `complete` on main after the fold merge.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

### CER-059(a) — diagnose Signal-1

Read `fleet_discovery.py` `_check_signal1`. Check how `_THIS_SCRIPTS_DIR` and `_FLEX_ROOT`
are computed. Run discovery against a known scripts-bound project (e.g. this repo itself):
```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/fleet_discovery.py discover --project-dir .
```
Confirm whether the detection returns the expected binding. Identify and fix any
path-resolution issue, or document why zero-hits is accurate.

### CER-059(b,c) — runbook updates

Edit `docs/harness-cutover-runbook.md` to add:
- Signal-1 verification step after each project sync (described above).
- AC for the fold-merge step: RELEASE-002 status reconciliation.

## Tests

If Signal-1 detection logic changes: add a test in `tests/pairmode/test_fold_preparation.py`
or a new fixture confirming `_check_signal1` returns `True` for a synthetic scripts-bound
project path.
