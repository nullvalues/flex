---
era: "003"
phase_class: production
---

# flex-harness — Phase 98: 0.2 → 0.3 regression remediation

← [Phase 97: Fold resume — pre-fold gate, fleet migration, merge to main, re-sync](phase-97.md)

**Parent context:** not a fork of an in-progress phase — phase-97 continues
unpaused (its own next action, RELEASE-058, is untouched). This phase is a
sibling opened directly from a dedicated audit (a `fable`-model Plan-mode
comparison of `/mnt/work/flex` 0.2.0 against this repo's 0.3.0), kept
separate from phase-97 because its purpose (harness self-correctness) is
distinct from phase-97's (fold mechanics) — per the single-purpose-per-phase
convention below.

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

The 0.2→0.3 redesign ("Era 3 Flex Orchestrator as Harness") deliberately shifted
prose-heavy per-role agent templates into shared procedure skills and a
deterministic resolver (`next_action.py`). That shift is sound and confirmed
working for story sequencing, gate verdicts, and checkpoint guards. But the audit
found six places where the *caller* (the 51-line `CLAUDE.build.md` template, or a
procedure skill) dropped an instruction that drove a mechanism which still
exists and is still relied upon elsewhere in the codebase — not deprecated
functionality, dead wiring. Two further items are design decisions the operator
made explicitly this session, going beyond a simple restore: ideology
enforcement should move earlier (into spec authoring) rather than stay
end-of-phase-only, and phase-level authoring needs a durable convention even
though it stays a manual, operator-fed workflow.

INFRA-240 (per-project parameterization) is flagged **priority** among these:
it affects every one of phase-97's 14 pending fleet migrations, each of which
would otherwise receive a reviewer/builder that checks its own code against
*flex's* conventions rather than its own.

An adversarial second-opinion review (fable, Plan mode) checked all 8 original
stories against the live code before any of them were built. It confirmed the
diagnoses were sound but flagged 4 stories needing revision (INFRA-236's token
source, INFRA-238's worktree path-normalization gap, INFRA-241's missing
`bootstrap.py` propagation + unverified model-override risk, INFRA-243's false
"no tooling exists" premise — `phase_new.py` already exists) and one gap the phase
itself had: nothing touched `README.md` despite this project's own checkpoint
policy requiring README currency, and both `README.md` and `docs/architecture.md`
were found to contain concrete over-claims beyond what the other 7 stories fix
(INFRA-244, added). All four flagged stories were amended in place; amendments are
marked inline in each story's Context/Requires/Ensures sections rather than
silently rewritten.

**Recommended build order** (per the adversarial review; dependency-driven, not
the order stories are listed below): **INFRA-239 → INFRA-241 → INFRA-236 →
INFRA-237 → INFRA-238 → INFRA-240 → INFRA-242/INFRA-243 → INFRA-244.**
INFRA-241 needs to settle the spawn/model contract before INFRA-236 (token
capture source) and INFRA-237 (per-attempt model escalation) can safely build
against it. INFRA-244 (README currency) is last by design — it documents
post-remediation behavior, not a snapshot of the current broken state.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-236 | Restore effort recording pipeline end-to-end (token capture, attempt rows, checkpoint-time cost rollup) — amended: hook-side transcript extraction, not orchestrator-view | planned |
| INFRA-237 | Wire attempt-count writes into the build loop (retry/loop-breaker/human-pause escalation) | planned |
| INFRA-238 | Restore active-story stamping and story-scope enforcement in the worktree loop; retire stale `pipe_path` reads — amended: explicit worktree-path-normalization requirement | planned |
| INFRA-239 | Make checkpoint-tag mark the phase complete | planned |
| INFRA-240 | Restore per-project parameterization in procedure skills (fold-blocking) | planned |
| INFRA-241 | Reconcile builder/reviewer spawn `subagent_type` contract with the context-budget gate allowlist — amended: `bootstrap.py` propagation + model-override verification added to scope | planned |
| INFRA-242 | Redesign ideology enforcement — spec-time alignment + narrow reviewer drift check | planned |
| INFRA-243 | Phase-authoring convention for single-purpose, bounded, reproducible phases — amended: `phase_new.py`/`phase.md.j2` already exist, story adds the convention to them rather than building new tooling | planned |
| INFRA-244 | Bring README.md current with the 0.3 resolver-driven design — remove 8-step/0.2-workflow/pre-resolver claims | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-98 Cold-eyes checklist

— developer fills in after phase completion —
