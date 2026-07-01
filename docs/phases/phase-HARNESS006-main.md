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
| HARNESS-002 | Dogfood flip — apply thin loop + retire agent templates | planned |
| HARNESS-003 | Re-source `expected_step_tokens` off effort.db (CER-053 state half) | planned |
| RELEASE-007 | Fold preparation — version finalize, Signal-1 diagnosis, runbook gate, RELEASE-002 reconcile | planned |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | HARNESS006 introduces no new persistent schema objects. |

---

### CP-HARNESS006-main Cold-eyes checklist

— developer fills in after phase completion —
