# Anchor Pairmode — Checkpoints

Each checkpoint is tagged after all stories in the phase pass the full checkpoint sequence
(build gate → security audit → intent review).

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
**Acceptance:** `/anchor:pairmode bootstrap` runs against a test project and produces
correct scaffold files. All Phase 1 tests pass.

---

## cp2-spec-derived-complete

**Phase:** 2 — Spec-Derived Generation
**Tag command:** `git tag cp2-spec-derived-complete && git push origin cp2-spec-derived-complete`
**Acceptance:** Bootstrap reads an Anchor spec and produces a checklist and deny list
derived from non-negotiables and business rules. All Phase 2 tests pass.

---

## cp3-lessons-complete

**Phase:** 3 — Lessons System
**Tag command:** `git tag cp3-lessons-complete && git push origin cp3-lessons-complete`
**Acceptance:** `/anchor:pairmode lesson` captures a lesson to lessons.json.
`/anchor:pairmode review` surfaces lessons and writes template updates. All Phase 3 tests pass.

---

## cp4-audit-sync-complete

**Phase:** 4 — Audit and Sync
**Tag command:** `git tag cp4-audit-sync-complete && git push origin cp4-audit-sync-complete`
**Acceptance:** `/anchor:pairmode audit` produces correct diff for cora, radar, and forqsite.
`/anchor:pairmode sync` applies deltas non-destructively. All Phase 4 tests pass.
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
Integration test runs bootstrap --from-reconstruction against anchor's own reconstruction.md
and asserts ideology.md output contains real conviction content. 910 tests pass.

---

## cp14-reconstruction-agent-tooling

**Phase:** 14 — Reconstruction agent tooling
**Tag command:** `git tag cp14-reconstruction-agent-tooling && git push origin cp14-reconstruction-agent-tooling`
**Acceptance:** score.py renders pre-populated RECONSTRUCTION.md from a reconstruction brief.
reconstruction-agent.md.j2 agent template created and wired into bootstrap scaffold.
--brief path containment guard added to score.py (MEDIUM security finding). anchor's own
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
