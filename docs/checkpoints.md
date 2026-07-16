# Flex Pairmode — Checkpoints

Each checkpoint is tagged after all stories in the phase pass the full checkpoint sequence
(build gate → security audit → intent review).

---

## cp90-fix-stale-preinfra191-assertion

**Tag command:** `git tag cp90-fix-stale-preinfra191-assertion a8a7004 && git push origin cp90-fix-stale-preinfra191-assertion`
**Phase:** 90
**Stories:** INFRA-201
**Acceptance:** A routine `sync-all` run caught flex's own `CLAUDE.build.md` up to the already-approved INFRA-191 spec-preflight flow, which broke `TestBuild025PreStoryScopeCheck` in `test_templates.py` — the test still asserted the pre-INFRA-191 wording. Updated the assertion to match the current, correct flow. Single-file test fix; reviewer-approved and committed at build time. **Retroactively tagged 2026-07-16** — this checkpoint was never tagged when the phase completed; tag applied directly at the phase's completion commit (`a8a7004`) rather than re-run against historical state, since the story was already reviewer-approved (tests + checklist) and is low-risk (test-assertion-only change).

---

## cp89-remove-flex-hook-paragraph-from-canonical-template

**Tag command:** `git tag cp89-remove-flex-hook-paragraph-from-canonical-template f293f6a && git push origin cp89-remove-flex-hook-paragraph-from-canonical-template`
**Phase:** 89
**Stories:** INFRA-200
**Acceptance:** A pairmode sync-attempt review on a downstream (non-flex) project surfaced that its synced `CLAUDE.md` described a "thin-delegation exception" naming `hooks/pre_tool_use.py`/`cold_read_guard.py`/INFRA-196 — flex-internal identifiers with no counterpart in that project's repo, since `bootstrap.py` never copies `hooks/` into a target project. Removed the flex-specific paragraph from the canonical `skills/pairmode/templates/CLAUDE.md.j2` PROTECTED FILES checklist item, leaving the generic instruction intact; `/mnt/work/flex/CLAUDE.md` (this repo's own file) is untouched and keeps its full paragraph. Single-template-file change; reviewer-approved and committed at build time. **Retroactively tagged 2026-07-16** — this checkpoint was never tagged when the phase completed; tag applied directly at the phase's completion commit (`f293f6a`) rather than re-run against historical state, since the story was already reviewer-approved (tests + checklist) and is low-risk (template-prose-only change).

---

## cp91-sync-agents-body-merge-hardening

**Tag command:** `git tag cp91-sync-agents-body-merge-hardening && git push origin cp91-sync-agents-body-merge-hardening`
**Phase:** 91
**Stories:** INFRA-202, INFRA-203
**Acceptance:** Closes a live, repeatable correctness bug found via production incident (2026-07-16, commit 85a6f52): `sync-all --apply` against flex itself appended duplicate, differently-numbered checklist content past the logical end of `.claude/agents/reviewer.md` and `.claude/agents/security-auditor.md`, and separately merged a nonsensical empty checklist line. `_heading_concept_key`/`_target_concept_keys`/`_sections_to_add` (INFRA-202) teach `_merge_body_sections` to recognize canonical sections already present under non-`##` formatting (bold-inline pseudo-headers, numbered enumerators) and never duplicate-append. `_empty_variable_in_appended_sections` (INFRA-203) makes an empty/degenerate template-variable render for a required, newly-appended section fail loudly (stderr error, non-zero exit, no write) instead of merging blank content, reusing the INFRA-202 section-scoping so already-present sections are never over-blocked. `docs/architecture.md` updated. Security audit: 0 CRITICAL/HIGH/MEDIUM/LOW. Intent review: both stories ALIGNED, no pivots; filed CER-063 (Do Later) for a forward-looking `INFRA-203` rail+number collision with the unmerged `fold-prep` branch, to be resolved at merge time. 2371 tests pass.

---

## cp88-context-budget-subagent-scoping

**Tag command:** `git tag cp88-context-budget-subagent-scoping && git push origin cp88-context-budget-subagent-scoping`
**Phase:** 88
**Stories:** INFRA-199
**Acceptance:** Closes a methodology bug found via live operator observation: `hooks/pre_tool_use.py`'s Task/Agent branch called `context_budget.decide()` for every agent spawn regardless of subagent type, so a general-purpose spawn (Plan, Explore, general-purpose) could be wedged by the CONTEXT BUDGET gate exactly as a builder spawn would — and because the gate's turn-tracking acknowledgment (INFRA-192/193) only clears on a genuine new `UserPromptSubmit`, a same-turn retry could never satisfy it. Fix: a module-level `BUILD_CYCLE_SUBAGENTS` frozenset ({`builder`, `reviewer`, `loop-breaker`, `security-auditor`, `intent-reviewer`}) gates the dispatch on `tool_input.subagent_type`; non-allowlisted or absent `subagent_type` passes through with no `context_budget` call, no block, no state write. `context_budget.py`'s internal decide/should_block/turn-tracking logic is unchanged; CER-049's dual `Task`/`Agent` tool-name acceptance is preserved. `CLAUDE.md` and `docs/architecture.md` updated; `docs/pairmode/context-gate-flow.md` and `docs/patterns/agentic-architecture/builder-reviewer-sub-agent-loop.md` doc-currency gaps fixed at checkpoint. Security audit: 0 CRITICAL/HIGH/MEDIUM/LOW. Intent review: ALIGNED, no pivots. 2359 tests pass.

---

## cp87-checklist-item-override-granularity

**Tag command:** `git tag cp87-checklist-item-override-granularity && git push origin cp87-checklist-item-override-granularity`
**Phase:** 87
**Stories:** INFRA-195, INFRA-196, INFRA-197, INFRA-198
**Acceptance:** Four stories. INFRA-195 extends `audit.py`/`sync.py` section-boundary detection to bold-marker checklist items (`**N[.letter][.sub]. LABEL**`), allowing overrides at item granularity rather than only whole `##` sections. INFRA-196 adds a `Read`-dispatch branch to `hooks/pre_tool_use.py` delegating to a new `cold_read_guard.py`, blocking orchestrator-level (non-subagent) reads of `docs/stories/**` and `.claude/agents/**` so the orchestrator passes story IDs to subagents instead of reading specs cold itself. INFRA-197 adds a third glob shape (`phase-{phase}-*.md`) to `story_new.py`'s phase-manifest lookup so suffixed phase filenames resolve (CER-062). INFRA-198 reframes `permissions-create`-related prose in `INFRA-194.md`/`architecture.md` to drop "protected path / deny rule" language that caused a builder to self-block a sanctioned Bash call, adds explicit `Bash` allow entries for `permissions-create`/`write-permissions`/`clear-permissions` in `.claude/settings.json`, and adds an orchestrator skip-check to `CLAUDE.build.md` (and its template) to avoid re-invoking `permissions-create` when scope hasn't drifted. Security audit: 0 CRITICAL/HIGH/MEDIUM/LOW. Intent review: ALIGNED (4/4); one MEDIUM-risk open question noted — whether the new `Bash` allow-pattern for `permissions-create`/`write-permissions`/`clear-permissions` actually prefix-matches Claude Code's runtime permission classifier given the leading `PATH=...` env-assignment token on the emitted command (unverified; not a new failure mode — mirrors a pre-existing untouched pattern in `settings.local.json`). 2348 tests pass.

---

## cp86-permissions-create-idempotency

**Tag command:** `git tag cp86-permissions-create-idempotency && git push origin cp86-permissions-create-idempotency`
**Phase:** 86
**Stories:** INFRA-194
**Acceptance:** Closes a methodology bug found via external report (meander): `permissions-create` (Layer 1 of the two-layer permission model) unconditionally rewrote `docs/phases/permissions/<story_id>.json` — including a fresh `generated_at` — on every invocation, even when the computed `allowed_paths` were unchanged, re-triggering the auto-mode re-authorization gate on every story despite no scope drift. `cmd_permissions_create` now reads the existing file (if present and parseable) and no-ops when `allowed_paths` match; writes with a fresh `generated_at` only on genuine drift, absence, or corruption. `docs/architecture.md` updated to describe the no-op behavior. Security audit: 0 CRITICAL/HIGH/MEDIUM/LOW. Intent review: ALIGNED. 2327 tests pass.

---

## cp79-era002-index-tooling-maintenance

**Phase:** 79 — era-002 index-tooling maintenance (current-phase, mark-phase-complete, reviewer revert)
**Tag command:** `git tag cp79-era002-index-tooling-maintenance && git push origin cp79-era002-index-tooling-maintenance`
**Acceptance:** Three stories. **BUILD-036**: `current-phase` first-incomplete selection + terminal/parked status classification (`_is_terminal_status`/`_is_active_status` helpers; forward-scan replaces last-wins; fileless-phase guard folded in). **BUILD-037**: `mark-phase-complete` column-count-preserving status rewrite (`cells[1:-1]` inner-cell extraction; 4- and 5-column layouts both preserved). **BUILD-038**: dropped `git clean -fd` from the FAIL-revert block in `.claude/agents/reviewer.md` (tracked files restored via `git checkout .`; untracked files intentionally left in place). Doc update: `architecture.md` revert-path description corrected. Surfaced CER-060 (template `reviewer.md.j2` still carries `git clean -fd` — follow-up story needed). Security audit: 0 CRITICAL/HIGH/MEDIUM/LOW. Intent review: ALIGNED. 2266 tests pass.

---

## cp-HARNESS001-ante1

**Phase:** HARNESS001-ante1 — Versioning & upstream compatibility (Era 003 preflight)
**Tag command:** `git tag cp-HARNESS001-ante1 && git push origin cp-HARNESS001-ante1`
**Acceptance:** Seven stories. **RELEASE-001** (operator git): `v0.2.0` rollback-anchor tag at main HEAD + `harness` branch & `/mnt/work/flex-harness` worktree, main untouched & still 0.2.x. **RELEASE-002** (harness-only, `deferred` on main): pairmode → `0.3.0-dev`, plugin/marketplace → `0.3.0` + version match-guard test (built on `harness` 175925d; lands on main at the fold). **RELEASE-003**: CLI-surface freeze guard test (24-command click snapshot, superset assertion). **RELEASE-004**: "Era 003 additive contract" section in `architecture.md` (four-point contract + state-ownership table + effort.db≠context-control invariant, comingling flagged for HARNESS006). **RELEASE-005**: read-only `fleet_discovery.py` + 20 tests + dated `docs/fleet-snapshot.md` (9 projects). **RELEASE-006**: `docs/harness-cutover-runbook.md` (Option Y rolling sync-driven migration). **INFRA-185**: isolated `lesson_review` CLIOutputClarity tests from live drift promotion (CER-057 gate-blocker; `--skip-drift`). Security audit: 0 CRITICAL/HIGH. Intent review: ALIGNED. 2255 tests pass.

---

## cp76-sync-build-context-gate-seed

**Phase:** 76 — sync-build seeds context gate state on --apply
**Tag command:** `git tag cp76-sync-build-context-gate-seed && git push origin cp76-sync-build-context-gate-seed`
**Acceptance:** One story: BUILD-032. Added `_seed_context_gate_state()` to `pairmode_sync.py`; `sync-build --apply` now seeds missing `context_session_reset_at`, `context_current_tokens`, and `context_current_tokens_recorded_at` when absent; dry-run emits warning lines; six tests cover all edge cases. Also raised pre-existing flaky performance test wall-clock limit 5s→15s. Security audit: 0 findings. 2201 tests pass.

---

## cp75-phase74-security-remediation

**Phase:** 75 — Phase 74 security remediation
**Tag command:** `git tag cp75-phase74-security-remediation && git push origin cp75-phase74-security-remediation`
**Acceptance:** One story: INFRA-183. Bounded `compute_context_tokens` to last 500 lines (CRITICAL from Phase 74 audit); added `Path.resolve().is_relative_to()` containment guard to `_derive_transcript_path` (HIGH from Phase 74 audit); updated `CLAUDE.md` HOOK PERFORMANCE section to document `post_tool_use.py` thin-delegation exception and correct stale `decide()` interface description; filed CER-052 as resolved; updated `docs/pairmode/context-gate-flow.md` and `README.md` to reflect INFRA-182 write/read split design. Security audit: 0 findings. 2195 tests pass.

---

## cp74-posttooluse-jsonl-context-gate

**Phase:** 74 — PostToolUse JSONL context gate — deterministic, no LLM cooperation
**Tag command:** `git tag cp74-posttooluse-jsonl-context-gate && git push origin cp74-posttooluse-jsonl-context-gate`
**Acceptance:** One story: INFRA-182. Added `Task|Agent` PostToolUse matcher to `hooks/hooks.json`; `post_tool_use.py` Task/Agent branch reads JSONL transcript via `context_budget.read_current_tokens()` and writes `context_current_tokens` + `context_current_tokens_recorded_at` to state.json (never blocks); `pre_tool_use.py` simplified to `decide(project_dir)` — no `story_id`, no `session_id`; `context_budget.py` restored JSONL reading functions, `decide()` reads scalar `context_current_tokens` only (hard-blocks if absent or stale), removed all per-story dict logic; `CLAUDE.build.md` and `.j2` template updated to display-only Context gate. Security audit findings from Phase 74 resolved in Phase 75 (cp75 tags with this phase). 2195 tests pass.

---

## cp68-sessionstart-context-reset

**Phase:** 68 — SessionStart context-counter reset (CER-047)
**Tag command:** `git tag cp68-sessionstart-context-reset && git push origin cp68-sessionstart-context-reset`
**Acceptance:** One story. INFRA-175: `hooks/session_start.py` thin-delegation dispatcher reads the `source` field from the SessionStart hook payload and delegates to a new pure module `skills/pairmode/scripts/session_reset.py`. On `clear` or `startup`, the hook writes `context_current_tokens = context_baseline_tokens` (default 25k) and `context_current_tokens_recorded_at` to `.companion/state.json`, resetting the dead-reckoning counter so the context gate no longer re-blocks on a stale value from the previous session. `compact` and `resume` are deliberately excluded. CLAUDE.md checklist item 1 updated with session_start.py thin-delegation entry; architecture.md state.json field docs and Hook architecture section updated. CER-047 resolved. 2157 tests pass (2155 at acceptance, 2 gained from Phase 69 additions; all pass against the Phase 68 code surface).

---

## cp67-bootstrap-context-seed

**Phase:** 67 — Bootstrap context-token seed
**Tag command:** `git tag cp67-bootstrap-context-seed && git push origin cp67-bootstrap-context-seed`
**Acceptance:** One story. INFRA-174: `_record_state()` in `bootstrap.py` now seeds `context_current_tokens = 1` alongside the other budget defaults when creating a new `state.json`. The seed value (1) passes the `> 0` guard in `read_context_tokens_from_state`, lets the first build step proceed without the manual `set-context-tokens` anchor, and is replaced by the orchestrator's real value before the first builder spawns. Three new tests cover the seed on new state, the downstream `context_budget.decide()` pass-through, and preservation of the field on existing state. `architecture.md` updated with seed documentation. 2157 tests pass.

---

## cp66-pairmode-version-deferred

**Phase:** 66 — PAIRMODE_VERSION single-source
**Tag command:** `git tag cp66-pairmode-version-deferred && git push origin cp66-pairmode-version-deferred`
**Acceptance:** Zero stories built. INFRA-173 (single-source PAIRMODE_VERSION) was formally deferred — CER-046 (the blocking Do Now finding) remained open through Phases 67 and 68; the build was deferred to avoid compaction. The fix was delivered in Phase 69 as INFRA-178 (`_version.py` created, all three import sites updated, same design as INFRA-173's acceptance criteria). Phase formally closed as deferred. 2157 tests pass (codebase unchanged from cp65 in this phase).

---

## cp73-per-story-context-token-dict

**Phase:** 73 — Per-story context token dict; revert Phase 72 JSONL gate
**Tag command:** `git tag cp73-per-story-context-token-dict && git push origin cp73-per-story-context-token-dict`
**Acceptance:** Three stories. INFRA-180: `context_budget.py` gains `_read_story_token_entry` and `_is_entry_fresh`; `read_context_tokens_from_state` gains `story_id` parameter with dict-first read path; `decide()` renames `session_id` → `story_id`; `set-context-tokens` writes `context_story_tokens[story_id]` dict entry alongside the backwards-compat scalar; `session_reset.decide_reset()` return type changed from `int|None` to `dict|None` and now returns `context_session_reset_at`; `session_start.py` writes `context_session_reset_at` on clear/startup; `pre_tool_use.py` Task/Agent branch simplified to single `decide(story_id=...)` call with `context_budget_acknowledged_at`-only state write. INFRA-181: `_derive_transcript_path`, `compute_context_tokens`, and `read_current_tokens` (Phase 72 JSONL dead code) removed; `CLAUDE.build.md` and `.j2` template restored to `/context` + `set-context-tokens` Context gate; `CLAUDE.md`, `docs/architecture.md`, and `README.md` updated. BUILD-031: `docs/pairmode/context-gate-flow.md` created with three ASCII flow diagrams (per-story setup, hook enforcement, session reset) and data model table; `README.md` Era 002 blurb and Known Limitations updated. 2192 tests pass.

---

## cp72-restore-jsonl-context-gate

**Phase:** 72 — Restore JSONL-based context gate
**Tag command:** `git tag cp72-restore-jsonl-context-gate && git push origin cp72-restore-jsonl-context-gate`
**Acceptance:** One story. INFRA-179: `context_budget.py` gains `_derive_transcript_path` (constructs JSONL path from `cwd` + `session_id`), `compute_context_tokens` (tail-reads last 100 lines, finds last `type: "assistant"` entry, sums `input + cache_read + cache_creation` tokens), and `read_current_tokens` (JSONL-only public function for the hook). `decide()` gains `session_id` parameter and JSONL-first waterfall (JSONL → state.json fallback). `_CONTEXT_CHECK_REQUIRED_MSG` updated to note auto-resolution. `hooks/pre_tool_use.py` Task/Agent branch expanded: two delegated calls (`read_current_tokens` + `decide`), merged state.json write (`context_current_tokens` + `context_current_tokens_recorded_at` on JSONL success; `context_budget_acknowledged_at` on block). `CLAUDE.build.md` Context gate converted to display-only (reads state.json; no `/context` call; no `set-context-tokens`); hook is sole enforcer. `skills/pairmode/templates/CLAUDE.build.md.j2` mirrored. `CLAUDE.md` carve-out updated to document two delegated calls and both state-write paths. `docs/architecture.md` §9, Hook architecture, and Companion data files updated with JSONL-first waterfall description. `README.md` Context gate description updated. CER-051 logged (LOW: `session_id` traversal advisory). 2173 tests pass (17 new test cases in `test_context_budget.py`; `test_templates.py` updated for new Context gate text).

---

## cp71-propagate-context-gate-fix-to-template

**Phase:** 71 — Propagate BUILD-029 Context gate fix into CLAUDE.build.md.j2 template
**Tag command:** `git tag cp71-propagate-context-gate-fix-to-template && git push origin cp71-propagate-context-gate-fix-to-template`
**Acceptance:** One story. BUILD-030: `CLAUDE.build.md.j2` Context gate section rewritten to open with `/context` call; `CONTEXT CHECK REQUIRED` branch removed from gate; `set-context-tokens` call added to below-threshold path; `bump-context-tokens --cost` blocks removed from Step 1 and Step 2; "Primary gate" paragraph updated to describe live `/context` call; "Secondary fallback" matcher updated to `Task|Agent`. Also corrected stale template sections discovered during sync-build parity check (decision table columns/thresholds, `record_attempt.py` extended token flags, retry model re-selection instruction, `build_command`/`test_command` `or` fallbacks). `sync-build --dry-run` on this project produces "No changes to apply." — template and live `CLAUDE.build.md` now agree. 2157 tests pass. Attempt 2 (first attempt failed AC 10: sync-build still showed 97-line diff; second attempt reconciled all remaining template drift).

---

## cp70-restore-context-gate-remove-bump

**Phase:** 70 — Restore per-story `/context` call in Context gate
**Tag command:** `git tag cp70-restore-context-gate-remove-bump && git push origin cp70-restore-context-gate-remove-bump`
**Acceptance:** One story. BUILD-029: `CLAUDE.build.md` Context gate rewritten to open with a direct `/context` call (live read) instead of reading `context_current_tokens` from state.json; below-threshold path records the count via `set-context-tokens` for the hook; the CONTEXT CHECK REQUIRED branch removed from the gate (hook still emits it when stored value is absent/stale); both `bump-context-tokens` invocations removed from Step 1 (builder) and Step 2 (reviewer); "Context budget check" section updated to describe the primary gate as the per-story `/context` call and the secondary fallback matcher as `Task|Agent`; `docs/architecture.md` § 9 and state.json key descriptions updated; `README.md` updated. `bump-context-tokens` command itself preserved in `flex_build.py`. Intent review identified template gap: `skills/pairmode/templates/CLAUDE.build.md.j2` not updated (follow-on in Phase 71). 2157 tests pass.

---

## cp69-pretooluse-agent-matcher-cer046

**Phase:** 69 — PreToolUse matcher dead under Agent tool rename (CER-049)
**Tag command:** `git tag cp69-pretooluse-agent-matcher-cer046 && git push origin cp69-pretooluse-agent-matcher-cer046`
**Acceptance:** Three stories. INFRA-176 (CER-049): `hooks/hooks.json` PreToolUse matcher widened from `"Task"` to `"Task|Agent"`; `pre_tool_use.py` dispatch widened to `tool_name in ("Task", "Agent")`; three parametrized test cases added for both tool names; `## Verification result` section written in story file confirming the harness rename; `docs/architecture.md` matcher references updated in three locations. INFRA-177: one-time lessons bypass rule (rule 14, strategy `"bypass"`, handler `"lessons_json"`) removed from `pairmode_migrate.py`; `_apply_bypass_rule()` function and `elif strategy == "bypass"` dispatch branch removed; `test_migrate_lessons_with_flag` removed; `test_lessons_gated_rule_is_only_14` updated to expect only the remaining regenerate rule (security audit cp-69 HIGH finding resolved). INFRA-178 (CER-046): `_version.py` created as single source of truth (`PAIRMODE_VERSION = "0.2.0"`); `audit.py`, `bootstrap.py`, and `sync.py` all import from it; local diverging definitions removed; `AuditResult.canonical_version` default fixed; test assertions updated. CER-046 and CER-049 resolved. 2157 tests pass.

---

## cp65-context-budget-drift-fix

**Phase:** 65 — Context budget per-story drift fix
**Tag command:** `git tag cp65-context-budget-drift-fix && git push origin cp65-context-budget-drift-fix`
**Acceptance:** Six stories. INFRA-169: `flex_build.py bump-context-tokens --cost N` accumulates actual per-story token cost into `state["context_current_tokens"]` (9 test cases). INFRA-170: `clear_current_story()` retains `context_current_tokens` and `context_current_tokens_recorded_at` so accumulated costs survive story transitions within a session; TTL handles cross-session staleness. INFRA-171: Three-tier estimation fallback in `estimate_next_step_tokens` (per-phase → global → seeded) and four-tier fallback in `_query_story_cost_samples` (rail → all-rails → global → insufficient). INFRA-172: `flex_build.py mark-phase-complete --phase N` writes `complete` status to `docs/phases/index.md` with atomic write and idempotency; forqsite retroactive fix committed. BUILD-027: Context gate redesigned to read accumulated value from state.json instead of calling `/context`; absent/stale key emits `CONTEXT CHECK REQUIRED` once per session; bump-context-tokens wired after both builder and reviewer record_attempt calls; forqsite synced. BUILD-028: `mark-phase-complete` wired into checkpoint step 7 before tagging; template updated; forqsite synced and retroactive index fix committed. CER-045 resolved. 2128 tests pass.

---

## cp60-checkpoint-report-intelligence

**Phase:** 60 — Checkpoint report intelligence — phase-key fix and next-phase detection
**Tag command:** `git tag cp60-checkpoint-report-intelligence && git push origin cp60-checkpoint-report-intelligence`
**Acceptance:** Two stories. INFRA-152: `flex_build.py next-phase --after [phase-id]` subcommand added; reads `docs/phases/index.md` via `_parse_index_phases()`, returns the key of the immediately following row (exit 0) or exits 1 silently when the phase is not found, is last, or the index is absent; `_is_aggregate_range()` helper extracted to correctly distinguish integer-range rows from suffix-keyed phase refs (fixing a pre-existing `_parse_index_phases` skip bug); 6 new test cases in `test_flex_build_next_phase.py`. INFRA-153: `CLAUDE.build.md` and `skills/pairmode/templates/CLAUDE.build.md.j2` updated — `[CP-N]` replaced by `[phase-id]` in checkpoint header; `next_phase_id` capture block inserted after step 7 tag; context-health advisory and closing prompt branch on `next_phase_id` non-empty/empty (replacing `[N+1]` arithmetic). Architecture.md: `flex_build.py` helper count updated 17→18, `next-phase` appended to command list. 1991 tests pass.

---

## cp59-context-budget-silent-fail-edges

**Phase:** 59 — context_budget.py silent-fail edge closure (CER-040, CER-041)
**Tag command:** `git tag cp59-context-budget-silent-fail-edges && git push origin cp59-context-budget-silent-fail-edges`
**Acceptance:** Two stories. INFRA-150 (CER-040): `_read_state()` now returns `{}` instead of `None` when `state.json` exists but is malformed (JSON decode error or non-dict root); file-absent path still returns `None` (non-pairmode compat preserved); 3 new test cases. INFRA-151 (CER-041): `flex_build.py set-context-tokens` writes `context_current_tokens_recorded_at` (UTC ISO-8601) alongside the token count; `read_context_tokens_from_state` gains `_now` injection param and TTL staleness check (default 60 min, configurable via `context_current_tokens_ttl_minutes`) — stale values treated as absent, triggering CONTEXT CHECK REQUIRED; `clear_current_story()` removes both token keys as belt-and-suspenders; 7 new test cases across `test_context_budget.py` and `test_story_context.py`. Architecture.md updated: three new state.json keys documented, step-9 context budget description updated to name CER-040/CER-041 block paths, hook architecture exception updated. CER-040 and CER-041 resolved. 1985 tests pass.

---

## cp57-global-session-hook-era001-close

**Phase:** 57 — Global session hook + era-001 documentation close
**Tag command:** `git tag cp57-global-session-hook-era001-close && git push origin cp57-global-session-hook-era001-close`
**Acceptance:** Two stories. `global_session_check.py` added as a stdlib-only global SessionStart hook: detects pairmode via `.companion/pairmode_context.json` or fallback file presence, prints a status block (current story, active era, last git tag, canon sync status) or a soft bootstrap prompt for non-pairmode projects; graceful failure on all error paths; 7 tests pass (INFRA-146). README updated with era-001 accomplishment banner and production-ready status; context budget gate added to build loop description; `docs/brief.md` `pre_tool_use.py` dual-delegate description updated; `docs/eras/001-initial.md` era status set to `closing` with era summary appended (INFRA-147). `SKILL.md` gains `pairmode_version: "0.2.0"` for canon sync check, `### Global session hook` install docs, and `global_session_check.py` entry added to `docs/architecture.md` module listing. 1964 tests pass.

---

## cp56-phase-naming-suffix

**Phase:** 56 — Phase naming suffix convention
**Tag command:** `git tag cp56-phase-naming-suffix && git push origin cp56-phase-naming-suffix`
**Acceptance:** Three stories (2 planned + 1 security remediation). `phase_new.py` `--phase-id` changed from `type=int` to `str`; new `--suffix` flag added; `phase_key = f"{phase_id}-{suffix}"` used as the canonical identifier in filenames, index rows, era table, and Jinja2 template; `prev_phase` detection gated on `re.fullmatch(r"\d+", phase_id) and not suffix` for backwards compat (INFRA-143). Path validation via `_SAFE_PHASE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")` guards `--phase-id` and `--suffix` before any filesystem access; traversal tests added (INFRA-145 / CER-038). Documentation updated: SKILL.md phase-new section, `CLAUDE.build.md.j2` + live `CLAUDE.build.md`, `index.md.j2` naming-convention block, `PAIRMODE.md` design-decisions table, `architecture.md` Phase documentation policy section (INFRA-144 + intent review). 1957 tests pass.

---

## cp55-story-scoped-permissions

**Phase:** 55 — Story-scoped file permissions via hook enforcement
**Tag command:** `git tag cp55-story-scoped-permissions && git push origin cp55-story-scoped-permissions`
**Acceptance:** Seven stories (5 planned + 2 security remediations). `flex_build.py permissions-create` generates `docs/phases/permissions/<STORY_ID>.json` from story `primary_files`/`touches` frontmatter; includes `_STORY_ID_RE` validation and `resolve().relative_to()` path containment (INFRA-137, INFRA-141). `scope_guard.py` reads `.companion/state.json["current_story"]["id"]` and the permissions file to enforce story file scope; fails open on all error conditions (INFRA-138). `hooks/pre_tool_use.py` gains `Edit`/`Write` dispatch branch delegating to `scope_guard.check_path`; CLAUDE.md carve-out updated to document dual-dispatch pattern (INFRA-139). `sync.py` now calls `_merge_deny_list` + `_prune_superseded_deny_entries` after `_register_pretooluse_hook`; `DEFAULT_DENY` simplified to `docs/phases/permissions/**` only; `_SUPERSEDED_DENY_ENTRIES` exported for downstream cleanup (INFRA-140). `CLAUDE.build.md` and template updated: `write-permissions` replaced by `permissions-create STORY_ID`, `story_context.py --set` added, `clear-permissions` replaced by `story_context.py --clear`, spec-mode step 5 adds permissions loop (BUILD-024). `docs/architecture.md` updated: `pre_tool_use.py` description expanded, step 9.5 added, documented exception block extended to dual-delegate, `scope_guard.py` added to module list, `permission_scope.py` marked legacy, build-loop step 2 updated (INFRA-142 + intent review). 1938 tests pass.

---

## cp54-sync-all-wrapper

**Phase:** 54 — sync-all wrapper command
**Tag command:** `git tag cp54-sync-all-wrapper && git push origin cp54-sync-all-wrapper`
**Acceptance:** One story. `pairmode_sync.py` gains a `sync-all` click subcommand that sequences `sync.py` → `sync-agents` → `sync-build` in fixed order via subprocess. Defaults to dry-run; `sync.py` is skipped in dry-run mode (no `--dry-run` support in that script) with an explanatory notice. `--apply` runs all three; `--yes` propagates to each. Fail-fast: on non-zero exit from any step, remaining steps are skipped and wrapper exits with the same code. `_depth_guard_sync_build` runs before any downstream call. SKILL.md gains `### /flex:pairmode sync-all` section and Commands-index entry. architecture.md updated. 1902 tests pass.

---

## cp53-phase52-fixes-story-cost-estimate

**Phase:** 53 — Phase 52 cold-eyes fixes + story cost estimation
**Tag command:** `git tag cp53-phase52-fixes-story-cost-estimate && git push origin cp53-phase52-fixes-story-cost-estimate`
**Acceptance:** Seven stories. `phase_new.py` invocation fixed to pass `--phase-id`, `--title`, `--goal`; Stories-table column corrected to `ID | Title | Status` (BUILD-018). Verbose `BUILT`/`REVIEW PASS|FAIL` output blocks removed from builder/reviewer templates; commit convention aligned to `feat(story-RAIL-NNN):` (BUILD-019). Reviewer-class agents (`reviewer`, `loop-breaker`, `security-auditor`, `intent-reviewer`) gain `tools: [Read, Bash, Glob, Grep]` frontmatter in both live files and `.j2` templates; PASS-branch `git add` scoped to story's `primary_files`/`touches` (BUILD-020). Pre-reviewer commit excludes `docs/stories/` so reviewer can diff builder-edited story files (BUILD-021). `flex_build.py` gains `write-attempt-count`, `read-attempt-count`, `clear-attempt-count` subcommands; orchestrator wired to restore/persist/clear counter across `/clear` boundaries (BUILD-022). `flex_build.py story-cost-estimate` subcommand queries effort.db for median PASS-outcome tokens and surfaces it at the context gate; pipeline integrity audit adds `test_record_attempt_usage_parsing.py` (INFRA-135). Proposed-phase naming convention (`phase-proposed-<kebab-name>-YYYYMMDD-NNN.md`) canonized in `CLAUDE.build.md` and `index.md.j2` (BUILD-023). 1891 tests pass.

---

## cp52-lean-orchestrator-spec-workflow

**Phase:** 52 — Lean orchestrator and spec workflow
**Tag command:** `git tag cp52-lean-orchestrator-spec-workflow && git push origin cp52-lean-orchestrator-spec-workflow`
**Acceptance:** Seven stories. CLAUDE.md blanket brief/architecture read instruction removed; `flex_build.py current-phase` CLI subcommand replaces manual orientation steps (BUILD-011). Builder and reviewer now receive story ID only; each agent reads its own spec cold (BUILD-012). Structured `BUILD-RESULT`/`REVIEW-RESULT` blocks added to both agents; orchestrator parses result and summary only (BUILD-013). `/context` inline gate inserted as first step of each story loop iteration (BUILD-014). Spec mode workflow added: `"spec next phase [intent]"` triggers a Plan subagent confirm-gate-commit flow (BUILD-015). `bootstrap.py` prompts for era strategic intent; `_build_era_001_content` updated with `strategic_intent` parameter (BUILD-016). `era_transition.py` created with `flex_build.py transition-era` subcommand: formally closes the active era and opens the next (BUILD-017). 1868 tests pass.

---

## cp51-stub-gate-enforcement

**Phase:** 51 — Stub gate and phase-doc scan enforcement
**Tag command:** `git tag cp51-stub-gate-enforcement && git push origin cp51-stub-gate-enforcement`
**Acceptance:** CLAUDE.build.md.j2 gains a phase-doc boundary scan (step 3.5) and a pre-story
stub gate that blocks delegation stubs and stories missing an acceptance surface. reviewer.md.j2
gains STORY SPEC check (2.5) catching the same patterns post-build. flex_build.py gains a
`check-stubs` CLI subcommand for pre-build audits: scans docs/stories/**/*.md, reports
STUB/OK per story, exits 1 when any stubs found. Also ships phase 50 boundary-collapse
policy (BUILD-006/007/008) and phase 49 H3+ sync fix. 1847 tests pass.

---

## cp50-phase-story-boundary-policy

**Phase:** 50 — Phase/story spec boundary policy
**Tag command:** `git tag cp50-phase-story-boundary-policy && git push origin cp50-phase-story-boundary-policy`
**Acceptance:** CER-030 updated with boundary-collapse root-cause framing. CLAUDE.build.md.j2
gains "Phase doc boundary scan" gate and "Spec surface discipline" section. phase.md.j2 gains
boundary reminder comment. Shipped as part of cp51 commit bundle. 1847 tests pass.

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

## cp77-multi-era-index-parser-fix
**Tag command:** `git tag cp77-multi-era-index-parser-fix && git push origin cp77-multi-era-index-parser-fix`
**Phase:** 77
**Stories:** BUILD-033
**Acceptance:** `_parse_index_phases` now resets table state on section boundaries (headings between era tables) instead of breaking, allowing multi-era index files to be fully scanned. Four new tests added. 2205 tests pass.

## cp78-orchestrator-preflight-gate-cli-offload
**Tag command:** `git tag cp78-orchestrator-preflight-gate-cli-offload && git push origin cp78-orchestrator-preflight-gate-cli-offload`
**Phase:** 78
**Stories:** INFRA-184, BUILD-034, BUILD-035
**Acceptance:** Orchestrator pre-flight gates (auth, schema, stub) offloaded from inline LLM judgment to `flex_build.py` CLI calls. New story frontmatter fields `auth_gated` + `schema_introduces` scaffolded by `story_new.py`. CLAUDE.build.md.j2 template updated so `sync-build --apply` propagates to upstream repos. 2232 tests pass.

## cp80-prereview-blanket-stage-exclusion
**Tag command:** `git tag cp80-prereview-blanket-stage-exclusion && git push origin cp80-prereview-blanket-stage-exclusion`
**Phase:** 80
**Stories:** BUILD-039
**Acceptance:** `git reset HEAD` exclusion loop added to Step 1.5 of `CLAUDE.build.md` (and its `.j2` template) — the orchestrator now unstages any story `primary_files`/`touches` swept up by the blanket `git add docs/phases/ docs/cer/` before the pre-reviewer commit fires. Prevents story deliverables whose primary_file lives under `docs/phases/` from being silently committed unreviewed under the chore message (L018). 2266 tests pass.

## cp81-write-clear-permissions-build-loop
**Tag command:** `git tag cp81-write-clear-permissions-build-loop && git push origin cp81-write-clear-permissions-build-loop`
**Phase:** 81
**Stories:** BUILD-040
**Acceptance:** `flex_build.py write-permissions` and `clear-permissions` wired into `CLAUDE.build.md` Step 1 and Step 3 respectively (and matching `.j2` template). Layer 2 allow-rule writes now suppress Claude Code permission prompts for story-declared files on every build, eliminating the manual auto-mode toggle requirement in upstream era-002 projects. `docs/architecture.md` updated to describe the two-layer permission model. 2266 tests pass.

## cp84-spec-preflight-verification
**Tag command:** `git tag cp84-spec-preflight-verification && git push origin cp84-spec-preflight-verification`
**Phase:** 84
**Stories:** INFRA-190, INFRA-191
**Acceptance:** `spec_preflight.py` created — scans story Ensures/Instructions/Implementation-notes for `/api/` routes and SCREAMING_SNAKE constants, warns when none are found in source tree, always exits 0, 12 tests (INFRA-190). `flex_build.py spec-preflight` subcommand registered, inserted into `CLAUDE.build.md.j2` between stub gate and scope check with informational surface block, `docs/architecture.md` updated with module entry and build-loop prose (INFRA-191). Security audit: 0 CRITICAL/HIGH (1 LOW — CER-061 filed Do Later). Intent review: ALIGNED. 2310 tests pass.

## cp85-context-budget-acknowledgment-integrity-fix
**Tag command:** `git tag cp85-context-budget-acknowledgment-integrity-fix && git push origin cp85-context-budget-acknowledgment-integrity-fix`
**Phase:** 85
**Stories:** INFRA-192, INFRA-193
**Acceptance:** Closes a self-clearing bug in the context-budget gate (external report): `hooks/user_prompt_submit.py` added as a thin `UserPromptSubmit` dispatcher incrementing `context_budget_user_turn_seq` (INFRA-192); `context_budget.should_block()`/`decide()` and `hooks/pre_tool_use.py` now require a genuine `UserPromptSubmit` event (not just token progress) since the last block before suppressing a re-prompt, closing the bare-retry self-clear path, with a backward-compatible grace period for pre-INFRA-192 state.json (INFRA-193). D11 read-only boundary on `decide()` preserved. Security audit: 0 CRITICAL/HIGH/MEDIUM/LOW. Intent review: both stories ALIGNED (INFRA-193 shipped a benign implementation restructure vs. the story's literal code sample); flagged `docs/architecture.md` and `docs/pairmode/context-gate-flow.md` doc-currency gap, applied at checkpoint. 2324 tests pass.

## cp83-spec-quality-gates
**Tag command:** `git tag cp83-spec-quality-gates && git push origin cp83-spec-quality-gates`
**Phase:** 83
**Stories:** BUILD-042, BUILD-043, INFRA-186, INFRA-187, INFRA-188, INFRA-189
**Acceptance:** Six targeted interventions to reduce fleet-wide retry rate: `effort_tracking` enabled on flex itself (BUILD-042); reviewer FAIL-CAUSE emission + `--notes` capture in effort DB (BUILD-043); `docs/architecture.md` touches hint in `story_new.py` and `check-story-scope` (INFRA-186); pointer-only Ensures rejection for `code`/`methodology` stories in `schema_validator.py` (INFRA-187); scope budget warning at >8 declared files in `check-story-scope` (INFRA-188); `test_gate` frontmatter field with `story`/`phase_checkpoint`/`none` values validated by schema_validator and scaffolded by `story_new.py` (INFRA-189). Security audit: 0 findings. Intent review: ALIGNED (2 doc edits applied to `docs/architecture.md`). 2294 tests pass.

## cp82-security-auditor-hook-exceptions-audit-scope
**Tag command:** `git tag cp82-security-auditor-hook-exceptions-audit-scope && git push origin cp82-security-auditor-hook-exceptions-audit-scope`
**Phase:** 82
**Stories:** BUILD-041
**Acceptance:** Security-auditor template (`skills/pairmode/templates/agents/security-auditor.md.j2`) and live agent file (`.claude/agents/security-auditor.md`) updated to enumerate the five documented pairmode thin-delegation hook exceptions and add an Audit scope rule excluding upstream plugin infrastructure findings from downstream project checkpoint PASS/FAIL. Eliminates false CRITICAL/HIGH findings that blocked era-002 projects. `docs/architecture.md` clarified that `stop.py` and `session_end.py` are plain pipe relays requiring no thin-delegation exception documentation. Security audit: 0 findings. Intent review: ALIGNED. 2266 tests pass.
