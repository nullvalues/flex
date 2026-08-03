---
era: "004"
phase_class: production
---

# project — Phase 118: Narrative of Record: propagation, spec-writer/intent-reviewer integration, and mid-build steering

← [Phase 117: Build-loop integrity remediation: escalation ladder, dead handoffs, CER-append corruption](phase-117.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

<!-- State this phase's single purpose in one or two sentences (docs/architecture.md
     § Phase-authoring convention, INFRA-243). If the work naturally splits into more
     than one purpose, that's a signal to open a sibling phase, not to widen this one. -->
Establish Narrative of Record as a templated, propagated doc-of-record layer for the pairmode build loop's own roles (mirroring the .claude/agents/ template+sync pattern), wire it into spec-writer's bounded inputs and intent-reviewer's alignment checks, reduce spec-writer's measured over-specification spiral, and prototype a concurrent shadow-reviewer mid-build steering mechanism via a shared worktree suggestions file — sequenced to build after Phase 117's next_action.py/CLAUDE.build.md churn settles.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-351 | Split harness-role narratives into pairmode template source; scaffold via bootstrap NARRATIVE_FILES | complete |
| INFRA-352 | Add sync-narratives to pairmode_sync.py, reusing INFRA-332's add-missing-file path | complete |
| INFRA-353 | OPERATOR seed-then-extend: templated typical-operator baseline plus bootstrap-led project extension | complete |
| INFRA-354 | Backfill flex's own docs/narratives/ from the new template source (real dogfood backfill) | complete |
| INFRA-355 | Add Narrative of Record as spec-writer's sixth bounded input (DP1.3) | complete |
| INFRA-356 | Add narrative-alignment checking to intent-reviewer (post-build and pre-build modes) | complete |
| INFRA-357 | Reduce spec-writer over-specification: cap exemplar imitation, add brevity counter-instruction | complete |
| INFRA-358 | Build the shared-suggestions-file mid-build steering mechanism (concurrent shadow-reviewer) | complete |
| INFRA-359 | Wire shadow-reviewer dispatch into CLAUDE.build.md and next_action.py | complete |
| INFRA-360 | Extend INFRA-336's integration-test harness to cover concurrent shadow-reviewer dispatch | complete |
| INFRA-361 | Establish Narrative of Record in docs/architecture.md; propose CLAUDE.md cold-start quad | complete |
| INFRA-362 | Dogfood narrative citation on flex's own story specs going forward | draft |

## Ordering

**Cluster A — narrative propagation (INFRA-351 → 352 → 353 → 354, strict order):** each depends on
the prior landing. 351 builds the template mechanism; 352 adds sync for already-bootstrapped
projects; 353 adds OPERATOR's distinct seed-then-extend path (needs 351's `NARRATIVE_FILES` to
exist); 354 is the real dogfood backfill against flex's own tree and needs all three of the above
landed to backfill from.

**Cluster B — spec-writer/intent-reviewer integration (INFRA-355 → 356, then 357 any time):** 355
(spec-writer's sixth input) must land before 356 (intent-reviewer's alignment check) has anything
real to check against — a story with no `narrative_roles:` mechanism can't yet be checked for
alignment. 357 (spec-volume/brevity fix) is independent of both and can build any time, though it's
grouped here since it's the other half of the Devin/Windsurf remediation. Cluster B depends on
Cluster A (351-354) being complete, since 355/356 need real narrative files to point at.

**Cluster C — shadow-reviewer mechanism (INFRA-358, then 359, then 360):** 358 builds the static
protocol/artifacts and can build any time. **359 (live dispatch wiring) must not merge before Phase
117 is fully checkpointed** — it touches the same `CLAUDE.build.md`/`next_action.py`-adjacent
region Phase 117's own INFRA-342 just finished reconciling, and building against that file mid-churn
recreates the exact two-copies-drift problem 117 exists to fix. 360 (integration-test extension)
needs both 358 and 359 landed. Cluster C is otherwise independent of Clusters A/B and can build in
parallel with them, modulo the Phase-117 gate on 359 specifically.

**Terminal (INFRA-361, then 362):** 361 (formal architecture.md establishment + CLAUDE.md proposal)
should build after Clusters A and B land, since it documents what they actually shipped, not a plan
for it. 362 (dogfood verification) is strictly last — it needs everything else in this phase
(351-361) complete to have a real mechanism to dogfood against.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

## Dogfood note

INFRA-362 (this phase's closing story) exercised the narrative-citation mechanism for real against
`docs/stories/INFRA/INFRA-363.md`. See its `## Evidence` section for the full record: a real
spec-writer run, a real intent-reviewer narrative-alignment check (FAIL — a genuine, uncontrived
finding), one inline fix (CER-161's phase-118-caused portion: a procedure/narrative contract gap
this phase itself introduced), and three CER filings (CER-160, CER-161, CER-162) for what needs a
separate story or coordination with another phase.

---

### CP-118 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
