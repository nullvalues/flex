---
era: "003"
phase_class: production
---

# project — Phase HARNESS001-main: Resolver foundation (deterministic skeleton)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Build the deterministic build-loop skeleton as a standalone, advisory-only CLI — flex_build.py next-action — that emits the era's load-bearing action grammar. next-action is a pure-read function of existing durable state (DP7): it composes the existing position/model/gate modules as a library (DP5), maps the 9-state build-sequencing table to a closed-but-extensible action enum {action,scalar,model,reason,meta} (DP1/DP2), routes every judgment-handoff to await-user without computing any verdict (DP4), embeds the resolved model for auto spawns and emits await-user:model-upgrade for prompted-upgrade (DP6), and is fully unit-tested in isolation against a synthetic durable-state fixture tree (DP8). Advisory only — NOT wired into the live CLAUDE.build.md; the additive contract + CLI-surface freeze test (RELEASE-003/004) guard the fleet during this window (DP7). Out of scope: gate verdict extraction (HARNESS002), leaf-worker conversion + durable return contract (HARNESS003), checkpoint-step decomposition (HARNESS004), spec-writer action (HARNESS005), the flip (HARNESS006), housekeeper (HARNESS008). Input: docs/agreements/HARNESS001-main.md.

## Stories

| ID | Title | Status |
|----|-------|--------|
| RESOLVER-001 | Action grammar + schema fixture (DP1) | planned |
| RESOLVER-002 | Position-inference read-model (DP3, DP5) | planned |
| RESOLVER-003 | State machine + next-action subcommand (DP2, DP4, DP6) | planned |
| RESOLVER-004 | Isolation test suite (DP8) | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-HARNESS001-main Cold-eyes checklist

— developer fills in after phase completion —
