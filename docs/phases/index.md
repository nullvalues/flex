# flex — Phase Index

This document is the index of all build phases for the project.
Each phase has a dedicated file in `docs/phases/`. Phases 1–7 are recorded in the
legacy monolithic doc at `docs/phase-prompts.md`.

New phases are created via `skills/pairmode/scripts/phase_new.py` (`/flex:pairmode phase-new`),
which prints the phase-authoring checklist on creation — see `docs/architecture.md` §
Phase-authoring convention (INFRA-243) for the single-purpose / bounded-complexity /
reproducible-from-artifacts criteria a well-formed phase should meet.

| Phase | Title | Status | Tag |
|-------|-------|--------|-----|
| 1–7 | Core pairmode scaffold, spec-derived generation, lessons, audit/sync, companion enhancements, audit noise, template coherence | complete | cp1 – cp7 |
| 8 | Sync confirmation, template coherence, and tooling fixes | complete | [phase-8.md](phase-8.md) · cp8-sync-tooling-fixes |
| 9 | Final cleanup — dead code, path fixes, hook pipe contract enforcement | complete | [phase-9.md](phase-9.md) · cp9-final-cleanup |
| 10 | Ideology capture infrastructure — template, brief upgrade, reviewer/intent-reviewer enforcement, guided capture, staleness audit | complete | [phase-10.md](phase-10.md) · cp10-ideology-infrastructure |
| 11 | Brief hygiene and reconstruction workflow | complete | [phase-11.md](phase-11.md) · cp11-reconstruction-workflow |
| 12 | Reconstruction seeding and comparison scaffolding | complete | [phase-12.md](phase-12.md) · cp12-reconstruction-seeding |
| 13 | CER cleanup and end-to-end reconstruction verification | complete | [phase-13.md](phase-13.md) · cp13-cer-cleanup-e2e |
| 14 | Reconstruction agent tooling | complete | [phase-14.md](phase-14.md) · cp14-reconstruction-agent-tooling |
| 15 | Rails, eras, and story structure — foundation | complete | [phase-15.md](phase-15.md) · cp15-rails-eras-story-structure |
| 16 | Build loop integration and rail-aware review | complete | [phase-16.md](phase-16.md) · cp16-build-loop-integration |
| 17 | Correctness — fix all known bugs | complete | [phase-17.md](phase-17.md) · cp17-correctness-fixes |
| 18 | Missing tooling — story lifecycle, overrides, --yes, orchestrator clarity | complete | [phase-18.md](phase-18.md) · cp18-missing-tooling |
| 19 | Test coverage and integration verification | complete | [phase-19.md](phase-19.md) · cp19-test-coverage-integration |
| 20 | PR readiness — documentation, changelog, git history | complete | [phase-20.md](phase-20.md) · cp20 |
| 21 | Orchestrator hardening and auth-policy integration | complete | [phase-21.md](phase-21.md) · cp21 |
| 22 | Effort tracking infrastructure | complete | [phase-22.md](phase-22.md) · cp22 |
| 23 | Drift detection foundations (pivoted — see Phase 29) | deferred | [phase-23.md](phase-23.md) · cp23 |
| 24 | Data-defensible model rebalance refinement | complete | [phase-24.md](phase-24.md) · cp24-data-defensible-methodology |
| 25 | Backlog remediation and cross-project agent sync | complete | [phase-25.md](phase-25.md) · cp25-backlog-remediation-and-agent-sync |
| 26 | Build loop retry automation and auth policy canonization | complete | [phase-26.md](phase-26.md) · cp26-build-loop-retry-and-auth-canonization |
| 27 | Auth check per-story placement fix | complete | [phase-27.md](phase-27.md) · cp27-auth-check-per-story-placement |
| 28 | CER backlog remediation (LOW items) | complete | [phase-28.md](phase-28.md) · cp28-cer-backlog-remediation |
| 29 | Project drift detection and promotion workflow | complete | [phase-29.md](phase-29.md) · cp29-drift-detection-and-promotion |
| 30 | Hook security fix and sync tooling gaps | complete | [phase-30.md](phase-30.md) · cp30-hook-fix-and-sync-tooling |
| 31 | Discoverability and status panel | complete | [phase-31.md](phase-31.md) · cp31-discoverability-and-status |
| 32 | Story-as-contract and story_context CLI | complete | [phase-32.md](phase-32.md) · cp32-story-as-contract |
| 33 | Build loop portability and sibling catch-up | complete | [phase-33.md](phase-33.md) · cp33-build-loop-portability |
| 34 | Checkpoint context health report | complete | [phase-34.md](phase-34.md) · cp34-checkpoint-context-health |
| 35 | Project rename to flex | complete | [phase-35.md](phase-35.md) · cp35-rename-anchor-flex |
| 36 | `/flex:pairmode migrate-from-anchor` — sibling project migration tool | complete | [phase-36.md](phase-36.md) · cp36-migrate-from-anchor |
| 37 | Builder model-selection tuning + token-direction recording | complete | [phase-37.md](phase-37.md) · cp37-builder-model-tuning |
| 38 | Data quality and portability cleanup | complete | [phase-38.md](phase-38.md) · cp38-data-quality-portability |
| 39 | Context budget check | complete | [phase-39.md](phase-39.md) · cp39-context-budget-check |
| 40 | Pre-story schema gate | complete | [phase-40.md](phase-40.md) · cp40-pre-story-schema-gate |
| 41 | Re-frame docs around pairmode as the lead capability | complete | [phase-41.md](phase-41.md) · cp41-pairmode-as-lead-capability |
| 42 | Context budget session-relative token tracking | complete | [phase-42.md](phase-42.md) · cp42-context-budget-session-relative |
| 43 | Replace DB-based context budget gate with orchestrator context check | complete | [phase-43.md](phase-43.md) · cp43-orchestrator-context-check |
| 44 | Fix `sync-agents` silent rendering failure | complete | [phase-44.md](phase-44.md) · cp44-sync-agents-context-fix |
| 45 | Deterministic orchestrator offload | complete | [phase-45.md](phase-45.md) · cp45-deterministic-orchestrator-offload |
| 46 | Local model infrastructure | complete | [phase-46.md](phase-46.md) · cp46-local-model-infrastructure |
| 47 | Pair-mode methodology consolidation | complete | [phase-47.md](phase-47.md) · cp47-pairmode-methodology-consolidation |
| 48 | Open-patterns publication initiative | complete | [phase-48.md](phase-48.md) · cp48-open-patterns-publication |
| 50 | Phase/story spec boundary policy | complete | [phase-50.md](phase-50.md) · cp50-phase-story-boundary-policy |
| 51 | Stub gate and phase-doc scan enforcement | complete | [phase-51.md](phase-51.md) · cp51-stub-gate-enforcement |
| 52 | Lean orchestrator and spec workflow | complete | [phase-52.md](phase-52.md) · cp52-lean-orchestrator-spec-workflow |
| 53 | Phase 52 cold-eyes fixes + story cost estimation | complete | [phase-53.md](phase-53.md) · cp53 |
| 54 | sync-all wrapper command | complete | [phase-54.md](phase-54.md) · cp54 |
| 55 | Story-scoped file permissions via hook enforcement | complete | [phase-55.md](phase-55.md) · cp55-story-scoped-permissions |
| 56 | Phase naming suffix convention | complete | [phase-56.md](phase-56.md) · cp56-phase-naming-suffix |
| 57 | Global session hook + era-001 documentation close | complete | [phase-57.md](phase-57.md) · cp57-global-session-hook-era001-close |
| 58 | Context budget gate — state.json contract | complete | [phase-58.md](phase-58.md) · cp58 |
| 59 | context_budget.py silent-fail edge closure (CER-040, CER-041) | complete | [phase-59.md](phase-59.md) · cp59-context-budget-silent-fail-edges |
| 60 | Checkpoint report intelligence — phase-key fix and next-phase detection | complete | [phase-60.md](phase-60.md) · cp60-checkpoint-report-intelligence |
| 61 | Scope-Miss Capture & Pre-Story Scope Checks | complete | [phase-61.md](phase-61.md) · cp61 |
| 62 | Context gate authorization clarity | complete | [phase-62.md](phase-62.md) · cp62 |
| 63 | Observability SPA — read-only window glass | complete | [phase-63.md](phase-63.md) · cp63-observability-spa |
| 64 | Observability SPA hardening — cold-eyes review fixes | deferred | [phase-64.md](phase-64.md) — resumed in Era 003 Phase G |
| 65 | Context budget per-story drift fix | complete | [phase-65.md](phase-65.md) |
| 66 | PAIRMODE_VERSION single-source | complete | [phase-66.md](phase-66.md) |
| 67 | Bootstrap context-token seed | complete | [phase-67.md](phase-67.md) |
| 68 | SessionStart context-counter reset (CER-047) | complete | [phase-68.md](phase-68.md) |
| 69 | PreToolUse matcher dead under Agent rename (CER-049) | complete | [phase-69.md](phase-69.md) |
| 70 | Remove bump-context-tokens from orchestrator build loop | complete | [phase-70.md](phase-70.md) |
| 71 | Propagate BUILD-029 Context gate fix into CLAUDE.build.md.j2 template | complete | [phase-71.md](phase-71.md) |
| 72 | Restore JSONL-based context gate | complete | [phase-72.md](phase-72.md) |
| 73 | Per-story context token dict; revert Phase 72 JSONL gate | complete | [phase-73.md](phase-73.md) |
| 74 | PostToolUse JSONL context gate — deterministic, no LLM cooperation | complete | [phase-74.md](phase-74.md) |
| 75 | Phase 74 security remediation — bound JSONL scan, session_id containment, CLAUDE.md doc | complete | [phase-75.md](phase-75.md) |
| 76 | sync-build seeds context gate state on --apply | complete | [phase-76.md](phase-76.md) |
| 77 | multi-era index parser fix | complete | [phase-77.md](phase-77.md) |
| 78 | orchestrator pre-flight gate CLI offload | complete | [phase-78.md](phase-78.md) |
| 79 | era-002 index-tooling maintenance (current-phase, mark-phase-complete, reviewer revert) | complete | [phase-79.md](phase-79.md) |
| 80 | pre-reviewer blanket-stage exclusion fix | complete | [phase-80.md](phase-80.md) |
| 81 | write-permissions + clear-permissions wired into build loop | complete | [phase-81.md](phase-81.md) |
| 82 | security-auditor: document pairmode hook exceptions + audit scope rule | complete | [phase-82.md](phase-82.md) |
| 83 | Spec quality gates | complete | [phase-83.md](phase-83.md) |
| 84 | Spec preflight verification | complete | [phase-84.md](phase-84.md) |
| 85 | Context budget acknowledgment integrity fix | complete | [phase-85.md](phase-85.md) |
| 86 | permissions-create idempotency | complete | [phase-86.md](phase-86.md) |
| 87 | checklist-item-level override granularity for sync/audit | complete | [phase-87.md](phase-87.md) |
| 88 | Scope context-budget gate to pairmode build-cycle agents | complete | [phase-88.md](phase-88.md) |
| 89 | Remove flex-specific hook paragraph from canonical CLAUDE.md.j2 template | complete | [phase-89.md](phase-89.md) |
| 90 | Fix stale pre-INFRA-191 assertion in CLAUDE.build.md test | complete | [phase-90.md](phase-90.md) |
| 91 | Harden sync-agents body-merge against silent duplication/corruption | complete | [phase-91.md](phase-91.md) |
| 92 | Fix cross-phase status leakage in story_update.py | complete | [phase-92.md](phase-92.md) |
| 93 | Wire Edit/Write/Read matchers into pre_tool_use.py's PreToolUse registration | complete | [phase-93.md](phase-93.md) |
| 94 | Fix escaped-pipe corruption in story_update.py phase-table row matching | complete | [phase-94.md](phase-94.md) |
| 95 | Wire context-budget-gate hooks (UserPromptSubmit, SessionStart, PostToolUse Task/Agent) into downstream bootstrap registration | complete | [phase-95.md](phase-95.md) |
| HARNESS001-ante1 | Versioning & upstream compatibility | complete | [phase-HARNESS001-ante1.md](phase-HARNESS001-ante1.md) |
| HARNESS001-main | Resolver foundation (deterministic skeleton) | complete | [phase-HARNESS001-main.md](phase-HARNESS001-main.md) |
| HARNESS002-main | Gate verdict extraction | complete | [phase-HARNESS002-main.md](phase-HARNESS002-main.md) |
| HARNESS003-main | Builder/reviewer/loop-breaker/security-auditor/intent-reviewer as leaf workers | complete | [phase-HARNESS003-main.md](phase-HARNESS003-main.md) |
| HARNESS004-main | Checkpoint as an action sequence | complete | [phase-HARNESS004-main.md](phase-HARNESS004-main.md) |
| HARNESS005-main | Spec-writer as a leaf worker | complete | [phase-HARNESS005-main.md](phase-HARNESS005-main.md) |
| HARNESS006-main | Harness reduction — the flip | complete | [phase-HARNESS006-main.md](phase-HARNESS006-main.md) · cp-HARNESS006-main |
| HARNESS007-main | Observability refactor (Phase G) | complete | [phase-HARNESS007-main.md](phase-HARNESS007-main.md) |
| HARNESS008-main | Housekeeper consolidation | complete | [phase-HARNESS008-main.md](phase-HARNESS008-main.md) · cp-HARNESS008-main |
| HARNESS009-main | Write-path determinism | complete | [phase-HARNESS009-main.md](phase-HARNESS009-main.md) · cp-HARNESS009-main |
| HARNESS010-main | Token surgery | complete | [phase-HARNESS010-main.md](phase-HARNESS010-main.md) · cp-HARNESS010-main |
| HARNESS009-post1 | HARNESS009 backlog close-out | complete | [phase-HARNESS009-post1.md](phase-HARNESS009-post1.md) · cp-HARNESS009-post1 |
| HARNESS011-main | Era 3 closeout remediation | complete | [phase-HARNESS011-main.md](phase-HARNESS011-main.md) |
| HARNESS012-main | Era 3 Fold Prep | complete | [phase-HARNESS012-main.md](phase-HARNESS012-main.md) · cp-HARNESS012-main |
| HARNESS013-main | Era 3 Fleet Migration | complete | [phase-HARNESS013-main.md](phase-HARNESS013-main.md) |
| HARNESS014-main | Lessons enforcement instrumentation | complete | [phase-HARNESS014-main.md](phase-HARNESS014-main.md) · cp-HARNESS014-main |
| HARNESS015-main | Checkpoint-sequence reset and state.json atomic-write adoption | complete | [phase-HARNESS015-main.md](phase-HARNESS015-main.md) · cp-HARNESS015-main |
| HARNESS016-main | Final fold — pre-fold gate, merge to main, re-sync | deferred | [phase-HARNESS016-main.md](phase-HARNESS016-main.md) — paused 2026-07-21, forked to Phase 96 |
| 96 | Build-loop revert safety and worktree-per-cycle isolation | complete | [phase-96.md](phase-96.md) |
| 97 | Fold resume — pre-fold gate, fleet migration, merge to main, re-sync | complete | [phase-97.md](phase-97.md) — closed 2026-07-29 by phase-106's RELEASE-071; deferred fleet-migration stubs RELEASE-043..057 superseded |
| 98 | 0.2 → 0.3 regression remediation | complete | [phase-98.md](phase-98.md) · cp98-context-budget-regression-remediation |
| 99 | Post-fold self-sync remediation | complete | [phase-99.md](phase-99.md) · cp99-post-fold-self-sync-remediation |
| 100 | Scope-guard fail-closed completion (CER-048 close-out) | complete | [phase-100.md](phase-100.md) · cp100-scope-guard-fail-closed-completion |
| 101 | Attempt recording and checkpoint reporting correctness | complete | [phase-101.md](phase-101.md) · cp101-attempt-recording-reporting-correctness |
| 102 | Effort-recording smoke test and harness release-channel fast-forward | complete | [phase-102.md](phase-102.md) · cp102-effort-smoke-and-release-channel-ff |
| 103 | Worktree and story-stub friction remediation (CER-090, CER-092) | complete | [phase-103.md](phase-103.md) |
| 104 | Recording and checkpoint correctness | complete | [phase-104.md](phase-104.md) |
| 109 | Single-orchestrator parallel build concurrency (index-ordered after 104 — scaffolded 2026-07-25, builds before 105) | complete | [phase-109.md](phase-109.md) |
| 105 | Campaign preflight: hooks, discovery, scope-guard, channel canon | complete | [phase-105.md](phase-105.md) |
| 110 | Effort-recording data-flow remediation (CER-101..104; index-ordered after 105 — scaffolded 2026-07-28, builds before phase 106 resumes) | complete | [phase-110.md](phase-110.md) |
| 111 | Plugin packaging repair: local marketplace source and skill-name de-namespacing (index-ordered before held phase 106 — scaffolded 2026-07-28) | complete | [phase-111.md](phase-111.md) |
| 112 | Campaign unblockers: worker result-grammar reconciliation, CER-guard placeholder fix, snapshot write targeting (index-ordered before blocked phase 106 — scaffolded 2026-07-28) | complete | [phase-112.md](phase-112.md) |
| 113 | Shared blockers: frontmatter, resolver evidence, recording determinism (index-ordered before held phase 106 — reordered 2026-07-29) | complete | [phase-113.md](phase-113.md) |
| 106 | Fleet migration campaign (driven from flex) | complete | [phase-106.md](phase-106.md) |
| 107 | CER backlog drain to zero | deferred | [phase-107.md](phase-107.md) — superseded by phases 113–116 / INFRA-310 (reconciliation sweep 2026-07-30) |
| 108 | Era 003 close (gated on observability delivery) | deferred | [phase-108.md](phase-108.md) — superseded by phases 113–116 / INFRA-310 (reconciliation sweep 2026-07-30) |
| 114 | Build-loop closeout: worktrees, scaffolding, migration tooling, doc currency | complete | [phase-114.md](phase-114.md) |
| 115 | Observability closeout: API hardening, payload guards, rollup hygiene, functional validation | complete | [phase-115.md](phase-115.md) |
| 116 | Repo-G upstream: methodology gates, resolver cadence, spec-time controls; backlog truth pass and 0.3.1 | complete | [phase-116.md](phase-116.md) |
| 117 | Build-loop integrity remediation: escalation ladder, dead handoffs, CER-append corruption | complete | [phase-117.md](phase-117.md) |
| 118 | Narrative of Record: propagation, spec-writer/intent-reviewer integration, and mid-build steering | complete | [phase-118.md](phase-118.md) |
| 119 | Spec precision (frozen exemplar), fundamental-doc trim, and CER backlog drain (era 004 closeout) | complete | [phase-119.md](phase-119.md) |
| 120 | CER-159 hook-firing fix: marketplace install migration, era-004 stable close | complete | [phase-120.md](phase-120.md) |
| 121 | sync-all to-030 fold-in and fleet stale-hook remediation | complete | [phase-121.md](phase-121.md) |
| 122 | shadow-reviewer write capability (CER-164) and shadow_review enablement | complete | [phase-122.md](phase-122.md) |
| 123 | Fix audit.py override-key normalisation mismatch (CER-170) | planned | [phase-123.md](phase-123.md) |
| 124 | Scaffold EXEMPLAR-000.md for downstream projects (CER-171) | planned | [phase-124.md](phase-124.md) |
| 125 | De-identify fleet repo references from the public repo (CER-172) | planned | [phase-125.md](phase-125.md) |
| 126 | Close shadow-reviewer Bash-guard bypass and scope its Write grant (CER-174) | planned | [phase-126.md](phase-126.md) |
| 127 | Close shadow-reviewer git-flag write bypass and worktree-path scope_guard gap (CER-175) | planned | [phase-127.md](phase-127.md) |
| 128 | Fix .pairmode-overrides template/migration gap from audit.py key-format change (CER-180) | planned | [phase-128.md](phase-128.md) |

---

## Proposed phases (not yet sequenced)

Phases conceived before they enter the build queue are stored as
`phase-proposed-<name>-YYYYMMDD-NNN.md`. They carry no sequential number
until sequenced. When sequenced, their stories are absorbed into the next
available phase and the proposed file is deleted (git history records the transit).

*(none — `phase-proposed-observability-spa-20260602-001.md` absorbed into Phase 63)*

## backlog promotions
_(List items promoted from the Do-Later / Do-Much-Later backlog into active phases here, with a one-line reason and the target phase.)_

- CER-071/073/074/076/077/082/088/089/091/016 → Phase 104 — recording/checkpoint correctness must precede the fleet campaign (cp-102 mandate on CER-091)
- CER-081/058/059/080/087/040/041 → Phase 105 — campaign preflight; hook dedupe and scope-guard fixes de-risk cross-repo migration work
- CER-078/079/084/085/086/035/014/065b, CER-012/006/010/069, CER-093/094/075, CER-070/062a/009/031 → Phase 107 — backlog drain to zero (fix, verify-and-close, or Do Never routing per operator decision 2026-07-25) — **superseded, re-routed to phases 113/114/115/116 by INFRA-310 (2026-08-01): phase 107 itself is superseded, not built; see `phase-107.md` § Superseded for the per-row disposition.**
- CER-095/096/097/098 → Phase 109 — parallel-build concurrency audit findings (filed and promoted same day, 2026-07-25); phase builds between cp-104 and phase 105
