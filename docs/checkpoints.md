# Flex Pairmode — Checkpoints

Each checkpoint is tagged after all stories in the phase pass the full checkpoint sequence
(build gate → security audit → intent review).

---

## cp47-pairmode-methodology-consolidation

**Phase:** 47 — Pair-mode methodology consolidation
**Tag command:** `git tag cp47-pairmode-methodology-consolidation && git push origin cp47-pairmode-methodology-consolidation`
**Acceptance:** Twelve stories across 7 tracks + CER-027 sub-track. T8 (INFRA-124, BOOTSTRAP-003): `{{ test_command }}` variable in CLAUDE.md.j2; toolchain-mismatch validator in bootstrap/sync. T3 (INFRA-125): .pairmode-overrides.j2 boilerplate corrected to `##`-marker format. T4 (INFRA-126): DOC CURRENCY pointer fixed to `.claude/agents/reviewer.md`. CER-027 sub-track (INFRA-127, INFRA-128, INFRA-129): `context_budget.py` module with transcript tail-read + effort.db median estimate; `refresh_effort_baseline.py` seed CLI; `hooks/pre_tool_use.py` PreToolUse-on-Task mechanical enforcement; CLAUDE.build.md.j2 ritual prose replaced with mechanical-enforcement pointer; HOOK PERFORMANCE carve-out added to flex CLAUDE.md; architecture.md step 9 rewritten. T6 (INFRA-130): auth check generalized to detect `**Classification:**` marker in architecture.md and auto-satisfy. T2 (BOOTSTRAP-004): `## Schema delivery` section added to phase.md.j2. T5 (BOOTSTRAP-005): index.md.j2 enriched with next-to-build pointer, Deferred-from column, Backlog-promotions section. T1 (INFRA-131): `flex_build.py` CLI with 8 subcommands replaces 8 inline `python -c` blocks in CLAUDE.build.md.j2. T7 (INFRA-132): `--drift-only` flag added to `lesson_review.py`; SKILL.md drift workflow updated to 6 steps with story-creation clarification. Build gate: 1835 tests pass. Security audit: 0 CRITICAL/HIGH (3 LOW/MEDIUM). Intent review: 4 doc corrections applied (phase-47.md status + INFRA-128 Note; architecture.md module tree + Hook architecture exception). CER-027 resolved; CER-028 re-triaged to Do Later.

---

## cp46-local-model-infrastructure

**Phase:** 46 — Local model infrastructure
**Tag command:** `git tag cp46-local-model-infrastructure && git push origin cp46-local-model-infrastructure`
**Acceptance:** Four stories: INFRA-120 (`call_model.py` — `call_ollama` HTTP client for Ollama's `/api/chat` endpoint, returns `None` on connection error or non-200, no anthropic SDK); INFRA-121 (`sidebar.py` wired to pluggable backend — existing `call_claude` renamed to `_call_anthropic` with all claude_agent_sdk internals preserved, new public `call_claude` dispatcher reads `FLEX_MODEL_BACKEND`/`FLEX_OLLAMA_BASE_URL`/`FLEX_OLLAMA_MODEL` env vars, startup health-check when `ollama` backend is active); INFRA-122 (fallback for `extract_incremental`, `check_conflicts`, and `check_file_against_spec` — on local-model parse failure, retries once with `_call_anthropic`; plan-impact at both call sites hardcoded to `_call_anthropic` unconditionally); INFRA-123 (`backend TEXT` column added to effort DB `attempts` table with migration, threaded through `effort_recorder.record_effort`, `_record_sidebar_effort` passes `"anthropic"`, Ollama dispatcher records `"ollama"`). Build gate: 1760 tests pass. Security audit: 0 findings. Intent review: 3 architecture.md edits applied (`backend` column in data model, sidebar data-flow line updated, cross-skill recording note added). Medium gap noted: `check_conflicts`/`check_file_against_spec` fallback paths are untested (spec only required extraction tests); tracked as follow-on.

---

## cp45-deterministic-orchestrator-offload

**Phase:** 45 — Deterministic orchestrator offload
**Tag command:** `git tag cp45-deterministic-orchestrator-offload && git push origin cp45-deterministic-orchestrator-offload`
**Acceptance:** Four stories: INFRA-116 (`next_story.py` — CLI to find first unbuilt story from a phase file, using git-commit authoritative check, exit codes 0/1/2, JSON mode); INFRA-117 (`model_selector.py --story-file` CLI — reads frontmatter, dispatches to the four selection functions, two-line output model+reason); INFRA-118 (`effort_db.py guardrail-check` and `context_health.py check` CLI subcommands, wrapping existing functions behind thin argparse entry points); INFRA-119 (`record_attempt.py --usage-block` — parses the `<usage>` XML block from file or stdin, eliminates manual transcription of seven token/timing fields). Build gate: 1745 tests pass. Security audit: 0 findings. Intent review: 2 LOW deviations (INFRA-116 uses click not argparse; complete-with-no-commit treated as returnable), architecture.md corrected for `select_intent_reviewer_model`/`select_security_auditor_model` return type (was `-> str`, now `-> tuple[str, str]`), `next_story.py` added to module listing.

---

## cp44-sync-agents-context-fix

**Phase:** 44 — Fix `sync-agents` silent rendering failure
**Tag command:** `git tag cp44-sync-agents-context-fix && git push origin cp44-sync-agents-context-fix`
**Acceptance:** Two stories: INFRA-114 (`_build_template_context` extended with `domain_isolation_rule` and `protected_paths`; `sync-agents` replaced bare `{"project_name": ...}` dict with full context — fixes silent "No changes to apply." false negative for all current agent templates); INFRA-115 (`_collect_changes` returns `(changes, render_errors)` tuple; `sync-agents` surfaces errors to stderr and exits 1 when all files fail to render; "No changes to apply." only printed when rendering is clean and no diffs exist). `architecture.md` body-propagation-limitation section updated to reflect Phase 44 context expansion and new error-surfacing behaviour. Build gate: 1728 tests pass. Security audit: 0 findings. Intent review: 1 alignment deviation (mixed-errors-with-changes exit code untested; LOW risk — common case correct) and architecture.md updated.

---

## cp37-builder-model-tuning

**Phase:** 37 — Builder model-selection tuning + token-direction recording
**Tag command:** `git tag cp37-builder-model-tuning && git push origin cp37-builder-model-tuning`
**Acceptance:** Three stories: INFRA-097 (raise `_CODE_UPGRADE_FILE_COUNT` from 3 → 5 — file-count trigger now fires at ≥ 5 primary_files, reducing false Opus upgrades for 3–4 file stories); INFRA-098 (add `attempt_number: int = 1` to `select_builder_model` — code stories on attempt ≥ 2 return `(opus, "retry-upgrade")` unconditionally, matching the reviewer's existing retry-upgrade pattern; new `REASON_RETRY_UPGRADE` constant exported); INFRA-099 (extend `CLAUDE.build.md` `<usage>` block extraction to document and pass `--tokens-in`, `--tokens-out`, `--cache-read-tokens`, `--cache-write-tokens` to `record_attempt.py` — directional token fields no longer null for all builder/reviewer rows). Intent review: `architecture.md` updated with new 4-arg `select_builder_model` signature, `retry-upgrade` reason, updated decision table (< 5 threshold), and corrected prompt example. Security audit: 0 findings. 1713 tests pass.

---

## cp36-migrate-from-anchor

**Phase:** 36 — `/flex:pairmode migrate-from-anchor` sibling project migration tool
**Tag command:** `git tag cp36-migrate-from-anchor && git push origin cp36-migrate-from-anchor`
**Acceptance:** Six stories: INFRA-092 (`pairmode_migrate.py` — 15-rule substitution engine, `MigrationReport` dataclass, 7 verification gates, idempotency check, depth guard, dry-run/apply/backup safety); INFRA-093 (21-test suite with fixture-based anchor-bootstrapped project); INFRA-094 (`skills/pairmode/SKILL.md` documentation for `migrate-from-anchor` command); INFRA-095 (security hardening — `_validate_backup_suffix` at CLI + sentinel-file check before apply); INFRA-096 (defense-in-depth — `_validate_backup_suffix` moved inside `migrate()` for programmatic callers). Key design notes: subprocess invocation for sync-build/sync-agents (Click handlers, not importable); backup file gate-scan side-effect documented; `report.missing` limited to subprocess rules only. Security audit: 2 HIGH findings resolved across INFRA-095/096, clean final audit. 1704 tests pass.

---

## cp35-rename-anchor-flex

**Phase:** 35 — Project rename to flex (anchor → flex hard fork)
**Tag command:** `git tag cp35-rename-anchor-flex && git push origin cp35-rename-anchor-flex`
**Acceptance:** Hard fork of upstream `nraychaudhuri/anchor` renamed to `flex` under `nullvalues/flex` ownership. Five stories: INFRA-087 (manifests + ATTRIBUTION.md crediting upstream author Nilanjan Raychaudhuri); INFRA-088 (filesystem paths and identifiers — `_ANCHOR_ROOT`→`_REPO_ROOT` brand-neutral, `~/.anchor/`→`~/.flex/`, `/tmp/anchor_*`→`/tmp/flex_*`, `ANCHOR_PROJECT_*`→`FLEX_PROJECT_*`); INFRA-089 (slash namespace `/anchor:*`→`/flex:*` plus emitted strings: `"anchor:pairmode"` generated_by, `name: anchor:seed`, `# Anchor Methodology Lessons` heading); INFRA-090 (project-name prose rewrite across docs, agent bodies, openspec, historical phase docs, story files, `.gitignore`); INFRA-091 (one-time append-only bypass on `lessons.json` source_project + free-text fields, `LESSONS.md` regenerated, sync-build/sync-agents re-render, 9-gate final verification). CER-023 filed (hook portability deferred per spec). Security audit clean (0 findings). 1681 tests pass.

---

## cp34-checkpoint-context-health

**Phase:** 34 — Checkpoint context health report
**Tag command:** `git tag cp34-checkpoint-context-health && git push origin cp34-checkpoint-context-health`
**Acceptance:** `context_health.py` with three public functions (`phase_retry_burden`, `rolling_phase_median`, `check_context_health`) queries the effort DB for per-phase retry burden and compares against a rolling median; uses `COALESCE(tokens_out, CAST(tokens_total * 0.15 AS INTEGER))` fallback for the current NULL `tokens_out` column (INFRA-085). Checkpoint sequence gains `### 7.5. Context health check` step and `Context health:` line in step 8 report; `CLAUDE.build.md.j2` and `CLAUDE.build.md` updated (INFRA-086). 1681 tests pass.

---

## cp33-build-loop-portability

**Phase:** 33 — Build loop portability and sibling catch-up
**Tag command:** `git tag cp33-build-loop-portability && git push origin cp33-build-loop-portability`
**Acceptance:** `CLAUDE.build.md.j2` uses `{{ pairmode_scripts_dir }}` — all rendered CLAUDE.build.md files now contain absolute flex script paths so sibling builds record effort data (INFRA-079). `pairmode_version` bumped to `0.2.0` with outdated signal in `pairmode status` (INFRA-080). `sync-agents` additively merges new H2 body sections from templates; body propagation requires full-template rendering and is silently inoperative for sibling projects (INFRA-081). Bootstrap writes four `PAIRMODE_ALLOW` Bash allow rules to `settings.local.json` (INFRA-082). `select_reviewer_model` returns `(model, reason)` tuple; reviewer `record_attempt.py` example updated to use `$reason` (INFRA-083). All four sibling projects (cora, radar, aab, forqsite) synced — absolute paths in `CLAUDE.build.md`, `## Contract check` in `reviewer.md`, `PAIRMODE_ALLOW` in `settings.local.json` (INFRA-084). CER-022 filed (sync-agents missing depth guard — Do Later). 1658 tests pass.

---

## cp32-story-as-contract

**Phase:** 32 — Story-as-contract and story_context CLI
**Tag command:** `git tag cp32-story-as-contract && git push origin cp32-story-as-contract`
**Acceptance:** `story_new.py` generates `## Requires`/`## Ensures` stubs; `schema_validator.py` accepts new, legacy, and transition formats (INFRA-074). `reviewer.md.j2` and `.claude/agents/reviewer.md` gain a `## Contract check` section that verifies each `## Ensures` item as a binary assertion before the checklist (INFRA-075). `story_context.py` CLI (`--set`, `--get`, `--clear`, `--project-dir`) is now a working entry point; `bootstrap.py` next-steps step 1 references it (INFRA-076). `CLAUDE.build.md` and template gain an optional `### 0. Spec review` step before the first build loop; L006/L008–L013 marked `applied` (INFRA-077). CER-021 resolved — `_resolve_story_file` adds `relative_to(stories_root)` containment and `cli()` adds `len(parts)<3` depth guard (INFRA-078). 1637 tests pass.

---

## cp31-discoverability-and-status

**Phase:** 31 — Discoverability and status panel
**Tag command:** `git tag cp31-discoverability-and-status && git push origin cp31-discoverability-and-status`
**Acceptance:** SKILL.md now documents `drift-report`, `sync-build`, and `register/unregister/list-projects` with full flag lists and a Drift detection workflow narrative section (INFRA-071). `pairmode status` shows `Registered: N project(s)` and a drift-report hint when projects are registered; silent when none (INFRA-072). Bootstrap prints a `## Next steps` block after successful completion — not on `--dry-run` — with story creation, project registration, and audit suggestions (INFRA-073). Broken `story_context.py --set` invocation corrected to `story_new.py` at intent-review time. `docs/phases/index.md` backfilled for phases 30–31. 1606 tests pass.

---

## cp30-hook-fix-and-sync-tooling

**Phase:** 30 — Hook security fix and sync tooling gaps
**Tag command:** `git tag cp30-hook-fix-and-sync-tooling && git push origin cp30-hook-fix-and-sync-tooling`
**Acceptance:** CER-020 closed — `exit_plan_mode.py` now applies the same `_resolve_pipe_path` containment guard as the other three hooks fixed in Phase 28 (INFRA-068). `pairmode sync-build` added to `pairmode_sync.py` — diffs and optionally applies rendered `CLAUDE.build.md.j2` to a target project, with `--dry-run`, `--apply`, `--yes` (INFRA-069). `pairmode register/unregister/list-projects` added via `pairmode_register.py` — manages the `registered_projects` list in `.companion/state.json` atomically (INFRA-070). `docs/architecture.md` Pairmode tooling section now has prose blocks for both new subcommands. 1598 tests pass.

---

## cp29-drift-detection-and-promotion

**Phase:** 29 — Project drift detection and promotion workflow
**Tag command:** `git tag cp29-drift-detection-and-promotion && git push origin cp29-drift-detection-and-promotion`
**Acceptance:** Drift detection and promotion feedback loop complete. Optional `source:` field added to story frontmatter to track drift-promoted stories (INFRA-063). `pairmode_drift_report.py` compares registered projects against canonical templates, classifies MISSING/EXTRA/DRIFT/INTENTIONAL, surfaces convergence candidates with `--convergent` (INFRA-065). `.pairmode-overrides` sections reclassified as INTENTIONAL in drift reports (INFRA-064). `pairmode review` extended with interactive drift promotion — promote/reject/skip convergence candidates, creates story with `source:` set on promotion (INFRA-066). `drift_evidence.py` scores candidates from effort.db with token-efficiency evidence, `(None, "insufficient data")` when fewer than 5 attempts (INFRA-067). Phase continuity policy added to ~/.claude/CLAUDE.md and checkpoint sequence (Step 5: phase completion check). 1563 tests pass.

---

## cp28-cer-backlog-remediation

**Phase:** 28 — CER backlog remediation (LOW items)
**Tag command:** `git tag cp28-cer-backlog-remediation && git push origin cp28-cer-backlog-remediation`
**Acceptance:** All six open Do Later CER items closed: CER-019 (pairmode_sync.py project_name YAML injection — INFRA-057), CER-016 (effort_db.py relative_to containment guard — INFRA-058), CER-018 (lesson.py value_framing/validation_phase CLI flags — INFRA-059), CER-004 (lesson_review.py str.startswith() → Path.relative_to() — INFRA-060), CER-017 (bootstrap.py effort_tracking transparency note — INFRA-061), CER-009 (hooks PIPE_PATH tempdir validation — INFRA-062). New CER-020 filed for exit_plan_mode.py unvalidated pipe_path override (pre-existing gap narrowed but not fully closed by INFRA-062). 1487 tests pass.

---

## cp27-auth-check-per-story-placement

**Phase:** 27 — Auth check per-story placement fix
**Tag command:** `git tag cp27-auth-check-per-story-placement && git push origin cp27-auth-check-per-story-placement`
**Acceptance:** Auth check moved from "Before the first build loop" (phase-level, fires once) to a dedicated "## Auth check (conditional — per story)" section between "Model evaluation" and "Step 1" (fires on every story independently). architecture.md Build loop integration bullet updated to match. 1451 tests pass.

---

## cp26-build-loop-retry-and-auth-canonization

**Phase:** 26 — Build loop retry automation + auth policy canonization
**Tag command:** `git tag cp26-build-loop-retry-and-auth-canonization && git push origin cp26-build-loop-retry-and-auth-canonization`
**Acceptance:** Build loop Step 3 FAIL branch replaced with three-tier escalation — attempt 1 auto-retries builder, attempt 2 auto-invokes loop-breaker, only then prompts user; standalone `## Loop-breaker` section removed (INFRA-054). Auth policy Step 8 added to "Before the first build loop" in CLAUDE.build.md and template; `architecture.md` gets "Auth policy integration" subsection mapping spec.json non-negotiables to pairmode's architecture.md equivalent (INFRA-055). 1451 tests pass.

---

## cp25-backlog-remediation-and-agent-sync

**Phase:** 25 — Backlog remediation and cross-project agent sync
**Tag command:** `git tag cp25-backlog-remediation-and-agent-sync && git push origin cp25-backlog-remediation-and-agent-sync`
**Acceptance:** CER-015 resolved — `record_attempt.py --story-file` auto-extracts phase/rail/story_class/story_id from frontmatter (INFRA-051). CER-010 resolved and CER-011 partially resolved — `story_new.py` and `era_new.py` gain formal `resolve().relative_to()` containment guards (INFRA-052). `pairmode sync-agents` subcommand added to propagate template frontmatter to existing projects without re-bootstrap (INFRA-053). L013 captures the template-drift-and-sync pattern (LESSON-006). CER-019 added for pairmode_sync.py project_name YAML injection (LOW, Do Later). 1451 tests pass.

---

## cp24-data-defensible-methodology

**Phase:** 24 — Data-defensible model rebalance refinement
**Tag command:** `git tag cp24-data-defensible-methodology && git push origin cp24-data-defensible-methodology`
**Acceptance:** `story_class` and `phase_class` frontmatter fields added and validated
(INFRA-045/046). `model_selector.py` provides `select_reviewer_model`, `select_intent_reviewer_model`,
`select_security_auditor_model`, and `select_builder_model` helpers — all wired into
`CLAUDE.build.md` and its Jinja2 template (INFRA-047/048/050). `pairmode_effort.py validate-rebalance`
reports per-cell PASS rate and decision-quality efficiency ratio (INFRA-049). Effort DB gains
`story_class` and `model_selection_reason` columns; `record_attempt.py` accepts those flags
(INFRA-050). L012 captures the data-defensible methodology lifecycle and efficiency-ratio value
framing (LESSON-005). 1422 tests pass.

---

## cp1-scaffold-complete

**Phase:** 1 — Pairmode Skill Scaffold
**Tag command:** `git tag cp1-scaffold-complete && git push origin cp1-scaffold-complete`
**Acceptance:** `/flex:pairmode bootstrap` runs against a test project and produces
correct scaffold files. All Phase 1 tests pass.

---

## cp2-spec-derived-complete

**Phase:** 2 — Spec-Derived Generation
**Tag command:** `git tag cp2-spec-derived-complete && git push origin cp2-spec-derived-complete`
**Acceptance:** Bootstrap reads an Flex spec and produces a checklist and deny list
derived from non-negotiables and business rules. All Phase 2 tests pass.

---

## cp3-lessons-complete

**Phase:** 3 — Lessons System
**Tag command:** `git tag cp3-lessons-complete && git push origin cp3-lessons-complete`
**Acceptance:** `/flex:pairmode lesson` captures a lesson to lessons.json.
`/flex:pairmode review` surfaces lessons and writes template updates. All Phase 3 tests pass.

---

## cp4-audit-sync-complete

**Phase:** 4 — Audit and Sync
**Tag command:** `git tag cp4-audit-sync-complete && git push origin cp4-audit-sync-complete`
**Acceptance:** `/flex:pairmode audit` produces correct diff for cora, radar, and forqsite.
`/flex:pairmode sync` applies deltas non-destructively. All Phase 4 tests pass.
Sibling repos audited and findings documented.

---

## cp5-companion-complete

**Phase:** 5 — Companion Enhancements
**Tag command:** `git tag cp5-companion-complete && git push origin cp5-companion-complete`
**Acceptance:** Sidebar shows story context panel when current_story is set.
Multi-module boundary alerts fire correctly. Permission overrides are captured to spec.
All Phase 5 tests pass.

---

## cp6-audit-noise-skillmd-e2e

**Phase:** 6 — Audit noise reduction, SKILL.md accuracy, e2e roundtrip
**Tag command:** `git tag cp6-audit-noise-skillmd-e2e && git push origin cp6-audit-noise-skillmd-e2e`
**Acceptance:** Audit false-positive rate reduced. SKILL.md reflects actual bootstrap behaviour.
E2E roundtrip test passes. All Phase 6 tests pass.

---

## cp7-phase7-templates

**Phase:** 7 — Template coherence and phase-new scaffolding
**Tag command:** `git tag cp7-phase7-templates && git push origin cp7-phase7-templates`
**Acceptance:** phase_new.py generates correct per-phase scaffold. All Phase 7 templates render
without error. All Phase 7 tests pass.

---

## cp8-sync-tooling-fixes

**Phase:** 8 — Sync confirmation, tooling fixes, documentation currency
**Tag command:** `git tag cp8-sync-tooling-fixes && git push origin cp8-sync-tooling-fixes`
**Acceptance:** sync.py requires explicit confirmation before writing. Phase-per-file migration
works. Documentation currency step added to checkpoint sequence. All Phase 8 tests pass.

---

## cp9-final-cleanup

**Phase:** 9 — Final cleanup (dead code, path fixes, hook pipe contract)
**Tag command:** `git tag cp9-final-cleanup && git push origin cp9-final-cleanup`
**Acceptance:** All Phase 8 checkpoint defects resolved. Hook pipe contract enforced — hooks
emit to pipe only; sidebar owns all state writes. All Phase 9 tests pass.

---

## cp10-ideology-infrastructure

**Phase:** 10 — Ideology Capture Infrastructure
**Tag command:** `git tag cp10-ideology-infrastructure && git push origin cp10-ideology-infrastructure`
**Acceptance:** `docs/ideology.md` generated by bootstrap with all six sections. brief.md.j2
has Core beliefs, Accepted tradeoffs, and What a second implementation must preserve. Reviewer
checks ideology alignment (item 5). Intent-reviewer detects ideology drift. Bootstrap guided
capture mode with --ideology-skip/--conviction/--constraint flags. Audit detects stale ideology.
Path traversal containment guard in bootstrap, audit, sync. 822 tests pass.

---

## cp11-reconstruction-workflow

**Phase:** 11 — Brief hygiene and reconstruction workflow
**Tag command:** `git tag cp11-reconstruction-workflow && git push origin cp11-reconstruction-workflow`
**Acceptance:** must_preserve dual-type collision fixed (must_preserve_str for brief.md.j2,
must_preserve list for ideology.md.j2). reconstruction.md.j2 brief template created.
docs/reconstruction.md wired into bootstrap scaffold and DEFAULT_DENY. reconstruct.py script
refreshes reconstruction.md from ideology.md and brief.md. 859 tests pass.

---

## cp12-reconstruction-seeding

**Phase:** 12 — Reconstruction seeding and comparison scaffolding
**Tag command:** `git tag cp12-reconstruction-seeding && git push origin cp12-reconstruction-seeding`
**Acceptance:** RECONSTRUCTION.md.j2 scoring template created. audit.py detects missing or
stale reconstruction.md. ideology_parser.py shared parser extracted. bootstrap.py accepts
--from-reconstruction PATH to seed a new project from a reconstruction brief. 905 tests pass.

---

## cp13-cer-cleanup-e2e

**Phase:** 13 — CER cleanup and end-to-end reconstruction verification
**Tag command:** `git tag cp13-cer-cleanup-e2e && git push origin cp13-cer-cleanup-e2e`
**Acceptance:** parse_ideology_text(text) added to ideology_parser.py; parse_ideology_file
delegates to it; tempfile round-trip eliminated from reconstruct.py (CER-001 resolved).
Integration test runs bootstrap --from-reconstruction against flex's own reconstruction.md
and asserts ideology.md output contains real conviction content. 910 tests pass.

---

## cp14-reconstruction-agent-tooling

**Phase:** 14 — Reconstruction agent tooling
**Tag command:** `git tag cp14-reconstruction-agent-tooling && git push origin cp14-reconstruction-agent-tooling`
**Acceptance:** score.py renders pre-populated RECONSTRUCTION.md from a reconstruction brief.
reconstruction-agent.md.j2 agent template created and wired into bootstrap scaffold.
--brief path containment guard added to score.py (MEDIUM security finding). flex's own
.claude/agents/reconstruction-agent.md generated. 929 tests pass.

---

## cp16-build-loop-integration

**Phase:** 16 — Build loop integration and rail-aware review
**Tag command:** `git tag cp16-build-loop-integration && git push origin cp16-build-loop-integration`
**Acceptance:** permission_scope.py writes/clears story-scoped allow rules in settings.local.json
with path containment guard (HIGH security finding fixed in Story 16.5). story_resolver.py
resolves story IDs and parses phase manifests. CLAUDE.build.md updated with manifest-aware
orchestrator loop and feat(story-RAIL-NNN) commit format. CLAUDE.md item 9 renamed to RAIL
SCOPE with MEDIUM/HIGH flag logic. reviewer.md.j2 and intent-reviewer.md.j2 updated with
rail violation detection. sync.py detects and prompts for missing default rails. 1043 tests pass.

---

## cp15-rails-eras-story-structure

**Phase:** 15 — Rails, eras, and story structure — foundation
**Tag command:** `git tag cp15-rails-eras-story-structure && git push origin cp15-rails-eras-story-structure`
**Acceptance:** schema_validator.py validates story/era/phase manifest frontmatter. story_new.py
creates story files on named rails. era_new.py creates era documents. phase_new.py writes
manifest format with era reference and empty Stories table. bootstrap.py suggests rails, prompts
for confirmation, creates rail directories, and initializes docs/eras/001-initial.md. Template
stubs for docs/stories/ and docs/eras/ added. 997 tests pass.

---

## cp48-open-patterns-publication

**Phase:** 48 — Open-patterns publication initiative
**Tag command:** `git tag cp48-open-patterns-publication && git push origin cp48-open-patterns-publication`
**Acceptance:** Six catalog-template-compliant pattern docs drafted in `docs/patterns/` covering
5 novel agentic methodology patterns (NP-1 through NP-6). PR #4 opened at
cloudnirvana/open-patterns with 5 patterns (NP-6 held pending PR #3 resolution; tracked as
CER-031). All docs follow the catalog template verbatim with real "What Broke" incidents and
"Security Implications" filled. 1835 tests pass (documentation-only phase; no Python changed).
