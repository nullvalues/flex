---
era: "003"
phase_class: production
---

# project — Phase HARNESS003-main: Builder/reviewer/loop-breaker/security-auditor/intent-reviewer as leaf workers

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

## Goal

Convert the five remaining build-loop workers (builder, reviewer, loop-breaker, security-auditor,
intent-reviewer) from per-project rendered `.claude/agents/*.md` files to thin agent shells +
plugin procedure skills — the same pattern HARNESS002 established for the gate worker. Introduces a
generalized `worker_result.py` return contract (`BUILD-RESULT`, `REVIEW-RESULT`, `ADVICE`) so the
resolver can route deterministically on every worker's output. Adds new resolver actions
(`spawn-reviewer`, `spawn-security-auditor`, `spawn-intent-reviewer`) and bumps `SCHEMA_VERSION` to
2. All advisory-only — per-project agent files not removed until the HARNESS006 dogfood flip.
Isolation-tested with no live API calls. Agreements input: `docs/agreements/HARNESS003-main.md`
(all 7 DPs AGREED).

## Stories

Built in order; each story's tests pass before the next. WORKER-004 (return contract) must
precede all worker conversions. All advisory-only.

| ID | Title | Status |
|----|-------|--------|
| WORKER-004 | Generalized worker return contract (`worker_result.py` + grammar fixture) | complete |
| WORKER-005 | Builder leaf worker — thin shell + plugin procedure skill | complete |
| WORKER-006 | Reviewer leaf worker — thin shell + plugin procedure skill | planned |
| WORKER-007 | Loop-breaker leaf worker — thin shell + plugin procedure skill | planned |
| WORKER-008 | Security-auditor leaf worker — thin shell + plugin procedure skill | planned |
| WORKER-009 | Intent-reviewer leaf worker — thin shell + plugin procedure skill | planned |
| WORKER-010 | HARNESS003 isolation suite | planned |

## Schema delivery

| Object | Management surface | Exception |
|---|---|---|
| _(none)_ | — | HARNESS003 introduces no new persistent schema — all workers are stateless (read existing durable state, persist nothing). |

---

### CP-HARNESS003-main Cold-eyes checklist

— developer fills in after phase completion —
