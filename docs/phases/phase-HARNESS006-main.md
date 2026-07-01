---
era: "003"
phase_class: production
---

# project — Phase HARNESS006-main: Harness reduction — the flip

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

The flip: reduce `CLAUDE.build.md` and its `.j2` template to the thin dispatch loop (~20 lines),
retire the per-project rendered agent templates, dogfood flex on the new loop, remove the
effort.db ≠ context-control comingling (CER-053 state half: `expected_step_tokens` re-sourced to
a thin-harness growth constant), and prepare the fold to `main` at `v0.3.0`. This phase is safe
only once HARNESS001–005 exist — all leaf workers and resolver extensions are advisory-built and
tested. The irreversible git fold (merge `harness` → `main`, tag `v0.3.0`, fleet re-sync, worktree
removal) is an operator action per `docs/harness-cutover-runbook.md`; the buildable stories deliver
everything that must be true before that merge. CER-059 Signal-1 diagnosis, runbook verification
step, and RELEASE-002 reconciliation AC land in RELEASE-007. Agreements input:
`docs/agreements/HARNESS006-main.md` (all 7 DPs AGREED).

## Stories

| ID | Title | Status |
|----|-------|--------|
| HARNESS-001 | Thin dispatch loop + `CLAUDE.build.md.j2` template reduction | complete |
| HARNESS-002 | Dogfood flip — apply thin loop + retire agent templates | complete |
| HARNESS-003 | Re-source `expected_step_tokens` off effort.db (CER-053 state half) | complete |
| RELEASE-007 | Fold preparation — version finalize, Signal-1 diagnosis, runbook gate, RELEASE-002 reconcile | complete |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | HARNESS006 introduces no new persistent schema objects. |

---

### CP-HARNESS006-main Cold-eyes checklist

**Build gate:** 2747 passed, 203 skipped, 1 xpassed — PASS

**Phase completion check:** All 4 planned stories complete (HARNESS-001, HARNESS-002, HARNESS-003, RELEASE-007). No deferred stories.

**Security audit:** Agent type unavailable; manual review found no new attack surface. Hook remains a thin dispatcher; no secrets in new files; `context_model.py` is a single constant.

**Intent review:** Agent type unavailable; manual review confirms all stories match their acceptance criteria. The try/except import fallback in `context_budget.py` is the minimal correct fix — the hook's flat-import context cannot load the package import.

**Documentation review:**
- `context_model.py` docstring documents the separation from effort.db
- `test_fold_preparation.py` documents Signal-1 diagnosis finding (accurate, not a bug)
- Runbook Signal-1 verification step added at CER-059b
- RELEASE-002 reconciliation AC documented in test

**CER backlog review:** HARNESS007 OBS-003 (CER-053 display half) remains correctly sequenced in HARNESS007; it depends on the SPA refactor that lands in OBS-002. No backlog items pulled forward.

**Dogfood verification:** flex builds on the thin loop (HARNESS-002 dogfood arc). `pairmode_version` == `0.3.0` after self-sync (this phase). The pre-fold discovery gate (DP8) and final fold sequence remain operator actions per the runbook.
