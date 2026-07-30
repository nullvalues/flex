---
era: "003"
phase_class: production
---

# project — Phase 106: Fleet migration campaign (driven from flex)

← [Phase 105: Campaign preflight: hooks, discovery, scope-guard, channel canon](phase-105.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Finish the pairmode 0.3.0 fleet migration as a driven campaign: 8 remaining projects through the runbook 6-step mechanic, full-fleet DP8 gate, phase-97 formally closed. Picks up deferred stories from Phase 97 (RELEASE-043..057 superseded).

## Stories

| ID | Title | Status |
|----|-------|--------|
| RELEASE-063 | Migrate meander to pairmode 0.3.0 (campaign canary) | complete |
| RELEASE-064 | Migrate lumin to pairmode 0.3.0 | complete |
| RELEASE-065 | Migrate caddy to pairmode 0.3.0 (seed never delivered) | complete |
| RELEASE-066 | Migrate forqsite.help to pairmode 0.3.0 | complete |
| RELEASE-067 | Migrate halfhorse to pairmode 0.3.0 | complete |
| RELEASE-068 | Migrate pokus to pairmode 0.3.0 — canon files only | complete |
| RELEASE-069 | Decommission pairmode from base56 (strip, not migrate — product is fully developed) | complete |
| RELEASE-070 | Migrate cora from 0.1.0 to 0.3.0 (unpark RELEASE-030 lesson-extraction carve-out) | complete — hand-migrated outside this campaign, carve-out unverified |
| RELEASE-071 | Campaign close: full-fleet DP8 gate, supersede RELEASE-043..057, clean stale seeds, mark phase-97 complete | complete |

**Parent phase:** Phase 97 (Fold resume) — its RELEASE-043..057 fleet-migration stubs were
deferred to per-project sessions that produced zero migrations; this phase reverses that
resolution and drives the migrations centrally. Phase 97's doc remains the historical
record for the original IDs; RELEASE-071 formally closes it.

## Ordering

RELEASE-063 (meander, canary) strictly first — it proves the campaign playbook.
RELEASE-064..067 in any order after the canary passes. RELEASE-068 (pokus — narrowed
2026-07-29 to canon-only; see the note at the end of this doc), RELEASE-069 (base56,
originally scoped as an index-drift migration, **reversed 2026-07-29 to a full
decommission** — pairmode stripped, not upgraded, per operator directive; see the note
at the end of this doc), RELEASE-070 (cora, originally scoped as a 0.1.0 migration gap
— **recorded as already hand-migrated outside this campaign's driven mechanic**,
verification only, no build performed; the RELEASE-030 lesson-extraction carve-out this
story's title names was never separately verified, see RELEASE-070 § Evidence) last,
each carrying a complication. RELEASE-071 strictly last.

## Execution model (cross-repo — deviation from the standard loop)

Campaign stories are **not** built by sandboxed builder subagents in per-story flex
worktrees: their write targets are `/mnt/work/<project>`, outside this repo, which the
worktree loop and scope_guard forbid. Instead, execution is **orchestrator-level with
the operator present**: the pairmode CLIs (`pairmode_sync.py`, `pairmode_migrate.py`,
`fleet_discovery.py`) run via Bash against the permanent release channel
(`/mnt/work/flex-harness`); the proving story cycle (mechanic step 6) runs inside the
target project's own `CLAUDE.build.md` loop with its own numbering; the flex-side story
file holds the evidence (discovery output, proving-cycle reference, 0.3.0 stamp
verification). Acceptance criteria are evidence-shaped, not diff-shaped. Phase 105's
CER-080/087 fixes remove the known scope-guard false-blocks; do not start this phase
before cp-105.

## Checkpoint proves

DP8 fleet snapshot shows 16/16 projects at pairmode 0.3.0 with single-block hooks; each
migrated project completed one proving story cycle whose attempt rows landed correctly in
its effort.db — the live downstream validation of the CER-091 fix (INFRA-264); phase-97
is closed in the index.

**Denominator corrected 2026-07-29 (RELEASE-071).** base56 was decommissioned from
pairmode entirely (RELEASE-069), not migrated — the fleet denominator drops from 16 to
15. Final DP8 disposition, per RELEASE-071's fresh fleet sweep: **14/15 clean**
(binding: both, 0.3.0), **1/15 partial** (cora — `binding: version` only, hooks resolve
to the flex dev checkout rather than the release channel; INFRA-319 candidate, not fixed
here), **1 project out of scope by design** (base56, decommissioned). The "16/16" text
above is left as historical record of the phase's original acceptance bar; see
RELEASE-071 § Evidence for the corrected final disposition and per-project detail.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-106 Cold-eyes checklist

— developer fills in after phase completion —


## Paused (2026-07-28) — recording remediation forked to Phase 110

RELEASE-063 (canary) executed 2026-07-27/28: meander migrated and verified
(E1-E5, E7-E12 pass), but E6 failed — the effort-recording cluster
(CER-101/102/103/104, root-caused in Phase 110's audit dossier). Per the canary
gate (RELEASE-063 Instructions step 8), RELEASE-064..071 are blocked. They stay
`draft` here (never started, so no per-story deferral entries); this phase
resumes after cp-110. Parent-phase pointer recorded in phase-110.md.

**Resumed (2026-07-28, post cp-110/cp-111).** Phase 110 checkpointed the
recording remediation; phase 111 (interposed) fixed plugin packaging.
RELEASE-064 (lumin) then ran the mechanic successfully but its proving cycle
(E5/E6/E7) was deferred by operator decision — see its `## Evidence`. The
operator subsequently **explicitly overrode the campaign gate** (2026-07-28) to
proceed with RELEASE-065+ while the downstream E6 proof of the CER-101/103/104
remediation remains outstanding. Standing requirement: the first proving cycle
to run anywhere in the fleet gets the full E6a/b/c + E7 checks; a pairmode-owned
recording failure there reopens the cluster and re-blocks the campaign.

**Re-blocked (2026-07-28, RELEASE-065 verdict).** The caddy migration's E6
split verdict landed the foreseen re-block: attribution (CER-103) and dedupe
(CER-104) PROVEN downstream, but E6b content FAILED — `sync-agents` preserved
stale 0.2-era agent bodies, so workers returned the plain-text
`BUILD-RESULT: DONE` / `REVIEW-RESULT: PASS` grammar that
`parse_worker_outcome` could not read (rows permanently pending). Two further
field defects: the scaffolded CER `(none)` placeholder row read as an
unresolved Do Now item, and `fleet_discovery`'s default snapshot wrote into the
channel checkout. Campaign held at RELEASE-065; record in commit `2894b425`
and RELEASE-065 `## Evidence`.

**Unblocked (2026-07-28, cp-112).** Phase 112 (interposed, index-ordered
before this phase) fixed all three: INFRA-293 (legacy plain-text verdict
grammar tolerance + sync-agents legacy-heading replacement + CER-099
containment parity), INFRA-294 (shared `cer.is_placeholder_row`), INFRA-295
(snapshot refuse-by-default). Field acceptance F3 PASSED the same day: an
explicit reconcile sweep against caddy's live `effort.db` turned rows 33/34
from `outcome NULL` to `(sonnet, 7457, PASS)` / `(sonnet, 9145, PASS)` — the
E6b content half is field-proven. cp-112 is promoted to the channel; campaign
resumes at RELEASE-066 with `--no-snapshot` mandated on every discovery
invocation per the corrected Signal-1 runbook form.

**RELEASE-068 narrowed (2026-07-29, operator directive).** RELEASE-068 is now a
**canon-only** migration of pokus: sync the 0.3.0 canon surfaces
(`CLAUDE.md`, `CLAUDE.build.md`, the seven `.claude/agents/` shells,
`.companion/state.json`) into `/mnt/work/pokus` and nothing more, so this phase can
close. The original "coordinate around in-flight UAT-gated work" scope is
**superseded** — the coordination risk is eliminated by not touching pokus's code,
docs, stories, backlog or UAT work rather than by scheduling around them. No
proving story cycle runs for pokus, so the § *Checkpoint proves* per-project
proving clause is narrowed for pokus by this directive and RELEASE-071 must count
it as **proof-deferred, not proven** (the campaign's downstream proof already
stands on forqsite.help/halfhorse).
