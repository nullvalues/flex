---
id: "001"
name: flex — Initial development
status: active
---

## Strategic intent

Era 001 establishes three foundations for AI-assisted development at scale:

**Context management.** LLM sessions have finite windows and drift without
anchoring. This era builds the instruments that hold a build loop inside its
budget: context budget gates, the lean orchestrator that derives position from
CLI rather than memory, clear-and-resume discipline, per-story attempt counter
persistence, and effort-DB cost estimation that makes the /clear decision
data-driven rather than intuitive.

**System of record.** Intent must survive across sessions, agents, and
implementations. This era builds pairmode's full record-keeping surface:
spec-first stories with frontmatter contracts, rail ownership, phase/story
boundary policy, stub gates, schema gates, the ideology/reconstruction
pipeline, and the append-only lessons store. Every build commitment has an
auditable spec; every methodology lesson has a durable entry.

**Shifting deterministic process from LLM to code.** Any rule an LLM must
remember is a rule it can forget. This era systematically moves deterministic
decisions into CLI scripts: `flex_build.py` subcommands replace inline
reasoning for model selection, permission scope, guardrail checks, context
health, phase position, and era transition. The orchestrator becomes a routing
loop; the logic lives in versioned, testable code.

Era 002 opens when the lean orchestrator is stable with reliable cost
estimates, and the first downstream project has bootstrapped and run in steady
state. Era 002 focus: metric use and observability — the Observability SPA,
effort-DB analytics, and surfacing the data era 001 accumulated.

## Rails

| Rail | Primary domain |
|------|----------------|
| BOOTSTRAP | Scaffold generation and initialization — `bootstrap.py`, the workflow that sets up a pairmode project from spec or reconstruction brief |
| AUDIT | Drift detection and non-destructive sync — `audit.py`, `sync.py`, comparison of project state against canonical templates |
| RECONSTRUCT | Ideology capture and reconstruction workflow — `ideology.md`, `reconstruction.md`, `score.py`, the n-tier reconstruction pipeline |
| LESSON | Methodology learning and template evolution — `lesson.py`, `lesson_review.py`, lessons.json append-only store |
| BUILD | Build loop and orchestrator — `CLAUDE.build.md`, `CLAUDE.build.md.j2`, `flex_build.py`, builder/reviewer agent definitions |
| TEMPLATE | Jinja2 scaffold templates — `skills/pairmode/templates/`, the canonical forms from which bootstrapped projects are generated |
| AGENT | Agent definitions and lifecycle — `.claude/agents/*.md` and their `.j2` counterparts; model selection; tool restriction |
| INFRA | Infrastructure scripts and CLI utilities — effort tracking, context budget, schema validation, permission scope, story lifecycle |

## Phases

| Phase | Title | Status |
|-------|-------|--------|
| 1–7 | Core pairmode scaffold, spec-derived generation, lessons, audit/sync, companion enhancements, audit noise, template coherence | complete |
| 8 | Sync confirmation, template coherence, and tooling fixes | complete |
| 9 | Final cleanup — dead code, path fixes, hook pipe contract enforcement | complete |
| 10 | Ideology capture infrastructure | complete |
| 11 | Brief hygiene and reconstruction workflow | complete |
| 12 | Reconstruction seeding and comparison scaffolding | complete |
| 13 | CER cleanup and end-to-end reconstruction verification | complete |
| 14 | Reconstruction agent tooling | complete |
| 15 | Rails, eras, and story structure — foundation | complete |
| 16 | Build loop integration and rail-aware review | complete |
| 17 | Correctness — fix all known bugs | complete |
| 18 | Missing tooling — story lifecycle, overrides, --yes, orchestrator clarity | complete |
| 19 | Test coverage and integration verification | complete |
| 20 | PR readiness — documentation, changelog, git history | complete |
| 21 | Orchestrator hardening and auth-policy integration | complete |
| 22 | Effort tracking infrastructure | complete |
| 23 | Drift detection foundations (pivoted — see Phase 29) | complete |
| 24 | Data-defensible model rebalance refinement | complete |
| 25 | Backlog remediation and cross-project agent sync | complete |
| 26 | Build loop retry automation and auth policy canonization | complete |
| 27 | Auth check per-story placement fix | complete |
| 28 | CER backlog remediation (LOW items) | complete |
| 29 | Project drift detection and promotion workflow | complete |
| 30 | Hook security fix and sync tooling gaps | complete |
| 31 | Discoverability and status panel | complete |
| 32 | Story-as-contract and story_context CLI | complete |
| 33 | Build loop portability and sibling catch-up | complete |
| 34 | Checkpoint context health report | complete |
| 35 | Project rename to flex | complete |
| 36 | `/flex:pairmode migrate-from-anchor` — sibling project migration tool | complete |
| 37 | Builder model-selection tuning + token-direction recording | complete |
| 38 | Data quality and portability cleanup | complete |
| 39 | Context budget check | complete |
| 40 | Pre-story schema gate | complete |
| 41 | Re-frame docs around pairmode as the lead capability | complete |
| 42 | Context budget session-relative token tracking | complete |
| 43 | Replace DB-based context budget gate with orchestrator context check | complete |
| 44 | Fix `sync-agents` silent rendering failure | complete |
| 45 | Deterministic orchestrator offload | complete |
| 46 | Local model infrastructure | complete |
| 47 | Pair-mode methodology consolidation | complete |
| 48 | Open-patterns publication initiative | complete |
| 50 | Phase/story spec boundary policy | complete |
| 51 | Stub gate and phase-doc scan enforcement | complete |
| 52 | Lean orchestrator and spec workflow | complete |
| 53 | Phase 52 cold-eyes fixes + story cost estimation | planned |
| 54 | sync-all wrapper command | planned |
| 56 | Phase naming suffix convention | planned |
