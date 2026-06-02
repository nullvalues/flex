---
era: "001"
---

# flex — Phase 53: Phase 52 cold-eyes fixes + story cost estimation

← [Phase 52: Lean orchestrator and spec workflow](phase-52.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->
## Goal

Phase 52 shipped the lean orchestrator and spec workflow, but cold-eyes review surfaced four critical and five high findings that defeat its safety and lean-context goals: spec mode invokes `phase_new.py` with a non-existent flag and without `--title`/`--goal`; reviewer-class agents declare no `tools:` frontmatter so the promised tool-restriction safety layer is not enforced; the pre-reviewer commit blindly stages `docs/stories/`, hiding builder edits from the reviewer; both old and new return blocks coexist in builder/reviewer templates; story commits use the wrong convention and `git add -A` widens scope beyond declared files; the per-story attempt counter has no durable home across `/clear`; and spec-mode Plan instructions disagree with the phase template on Stories-table columns. Phase 53 closes every Phase 52 finding (nothing to backlog) and audits the effort-tracking pipeline through Phase 52's minimal return surface, adding a `flex_build.py story-cost-estimate` subcommand that surfaces median rail+story_class token cost at the context gate — so effort-DB data informs `/clear` decisions instead of guesswork.

## Stories

| ID | Title | Status |
|----|-------|--------|
| BUILD-018 | Spec-mode `phase_new.py` invocation + Stories-table column alignment | complete |
| BUILD-019 | Remove verbose return blocks and align commit-message convention in builder/reviewer templates | complete |
| BUILD-020 | Reviewer-class `tools:` frontmatter and scoped `git add` for story commits | complete |
| BUILD-021 | Pre-reviewer commit scope: stop pre-staging `docs/stories/` | complete |
| BUILD-022 | Durable per-story attempt counter via `flex_build.py` + orchestrator instructions | complete |
| INFRA-135 | Effort-tracking integrity audit + `flex_build.py story-cost-estimate` subcommand | planned |
| BUILD-023 | Proposed-phase naming convention — canon and syncable policy | planned |

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

---

### CP-53 Cold-eyes checklist

— developer fills in after phase completion —
