---
era: "003"
phase_class: production
---

# project — Phase HARNESS002-main: Gate verdict extraction

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Extract gate judgment into a cold, disposable single gate worker (era's first leaf-worker conversion): the check-* CLIs stay deterministic signal providers, the worker renders the schema+auth verdict (stub mechanical, scope/context advisory), and the next-action resolver routes on the verdict via a new spawn-gate-worker action but never computes it. Establishes the designated safe-clear seam. Advisory-only — NOT wired into the live CLAUDE.build.md until the flip (HARNESS006). Stories: WORKER-001 (verdict grammar + fixture), RESOLVER-005 (spawn-gate-worker action + Row-4 split + routing), WORKER-002 (gate worker: thin shell + plugin procedure skill), RESOLVER-006 (CF-1/CER-060 retry-path model composition fix), WORKER-003 (isolation suite). Input: docs/agreements/HARNESS002-main.md (all 8 DPs AGREED). Built on the harness branch.

## Stories

Built in order; each story's tests pass before the next. RESOLVER-005 and WORKER-002 are
close-coupled via the verdict grammar but separable (injected verdicts let the resolver wiring be
built and tested before the real worker exists). All advisory-only — none wires the gate worker
into the live `CLAUDE.build.md` (HARNESS006 does the flip). Agreements input:
`docs/agreements/HARNESS002-main.md`.

| ID | Title | Status |
|----|-------|--------|
| WORKER-001 | Gate verdict grammar + fixture (DP3) | complete |
| RESOLVER-005 | `spawn-gate-worker` action + Row-4 split + verdict routing (DP4, DP6) | planned |
| WORKER-002 | Gate worker — thin shell + plugin procedure skill (DP1, DP2, DP5, DP6) | planned |
| RESOLVER-006 | CF-1/CER-060 — retry-path model composition fix (DP7) | planned |
| WORKER-003 | Isolation test suite (DP8) | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | HARNESS002 introduces no new persistent schema — the gate worker is stateless (reads existing durable state, persists nothing; DP1.3 / DP4). |

---

### CP-HARNESS002-main Cold-eyes checklist

— developer fills in after phase completion —
