# Changelog

All notable changes to flex are documented here. This project loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Pairmode-specific
changes are marked `[pairmode]`; modifications to flex core are marked `[core]`.

## [Unreleased]

### Fixed [core] — Phase 111 (Plugin packaging repair)
- Local plugin installs (CER-source: fresh-machine install report): `.claude-plugin/marketplace.json`'s plugin entry now declares `"source": "./"` instead of a GitHub clone pointer, so `claude plugin marketplace add ./flex` + `claude plugin install flex@nullvalues-flex` installs the added checkout; README/CONTRIBUTING install documentation corrected (the previous README documented a nonexistent `claude code plugin install <path>` command) and the skill count fixed to four (INFRA-291).
- Doubled skill namespace: the four `skills/*/SKILL.md` frontmatter `name:` values are now bare (`seed`, `companion`, `pairmode`, `observability`) so installed plugin skills surface as `/flex:<skill>` rather than `/flex:flex:<skill>`; `pairmode_migrate.py` rule 8 no longer stamps the prefixed form into downstream repos; both invariants guarded in `tests/pairmode/test_plugin_manifest.py` (INFRA-292).

### Added [pairmode] — Phase 110 (Effort-recording data-flow remediation, CER-101..104)
- Reconciliation pipeline repair (CER-101): symlink-aware lexical containment with an allowlisted link-target check (`_lexical_spawn_output_path`/`_permitted_output_target`), the shared `is_reconcilable_spawn_output` containment+terminator predicate (end_turn OR file quiescence; new `uncontained` pending reason) consumed by both `read_completed_spawn` and `classify_pending_reason`, a lexical `session_output_prefix` fix arming CER-097's ownership filter, and pending-row counts in `checkpoint-report` (INFRA-287).
- Attempt-row dedupe (CER-104): `effort_db.insert_or_update_attempt` treats `attempts.agent_id` as an idempotency key inside the existing `BEGIN IMMEDIATE` transaction (300 s recency window), collapsing duplicate hook-side recordings to one row; new stdlib-only `hook_view.py` merged hook view (settings + settings.local + enabled plugin hooks.json) consumed by `fleet_discovery`, `pairmode_sync audit-hooks`, and `bootstrap` (INFRA-288).
- Attribution and escalation (CER-102, CER-103): `resolve_recording_project` routes effort rows to the spawn's target project via a registered_projects-allowlisted precedence chain (explicit-flag → explicit-label → worktree-path → session-cwd), strict phase-key parsing (`_PHASE_KEY_STRICT_RE`) turns malformed keys into `unattributed:<role>`, and the reconcile-time FAIL bump gained `bump:late-fail`/`skip:late-bump-blocked` traceability (INFRA-289).
- Cold-eyes data-flow checks and recording-state hygiene: the four producer/consumer checks (written-never-read, required-never-written, duplicate state, half-implementation) added as reviewer checklist item 13, security-auditor check 7, and CP-NN phase-template checkboxes; `to-030` migration steps retiring dead `context_story_tokens` and stale legacy-shape `attempt_counter.json`; new `flex_build.py permissions-gc` subcommand with whitelist-of-reasons retention (INFRA-290).

### Added [pairmode] — Phase 105 (Campaign preflight: hooks, discovery, scope-guard, channel canon)
- Hook-registration dedupe (CER-081): `bootstrap.py` gained `_find_all_entries_by_command_basename` and `_prune_stale_hook_entries`, wired into both `_register_pretooluse_hook` and `_register_context_budget_hooks` so stale same-basename sibling hook entries are removed on every write; `pairmode_sync.py` gained an `audit-hooks` subcommand (dry-run / `--apply`) reusing the same prune helper; `fleet_discovery.py` surfaces a read-only `duplicate_hooks` signal in `discover()`, `--json`, text output, and the snapshot's new "Duplicate hook registrations" section (INFRA-269).
- registered_projects integrity (CER-058, CER-059): single-writer invariant test and provenance sidecar (`source`/`registered_at`, `audit-projects` CLI) in `pairmode_register.py`; Signal-1 absence classifier (`signal1_absence_reason`, four reason codes) threaded through `fleet_discovery.py`'s `discover()`/CLI/snapshot (INFRA-270).
- Scope-guard campaign readiness (CER-080, CER-087): staleness ageing (`STATE_STORY_MAX_AGE_HOURS`, `entry_is_fresh`, `stale` resolution source) and a harness-owned out-of-root allow-list (`harness_owned_prefixes`/`_out_of_root_decision`) in `scope_guard.py`, plus a `clear-stale-stories` operator CLI in `flex_build.py` (INFRA-271).
- Context-state hygiene (CER-040, CER-041): fail-open stderr signalling (`_FAIL_OPEN_PREFIX`/`_warn_fail_open`/`_staleness_unverifiable_reason`) across `context_budget.decide()` pass-through branches and `hooks/pre_tool_use.py`'s blanket except; dead CER-041 TTL removed from `read_context_tokens_from_state`; observability context route gained `gate_stale`/`DISPLAY_STALE_SECONDS` (INFRA-272).
- Release-channel canonization (docs-only): `/mnt/work/flex-harness` canonized as the permanent release channel — RELEASE-061 and its HARNESS016-era predecessor RELEASE-018 retired as superseded with historical-record annotations, RELEASE-060 rewritten, the harness-cutover runbook's final-fold teardown steps removed with a permanent-channel call-out, and phase-97/phase-HARNESS016-main ledgers updated (RELEASE-062).

### Added [pairmode] — Phase 109 (Single-orchestrator parallel build concurrency, CER-095..098)
- Resolver in-flight claim: `flex_build.claimed_story_ids` treats a live `.pairmode-worktrees/<story-id>/` directory as a build claim; `next_story.find_next_story` gained an opt-in `claimed=` filter with `claimed_skipped` reporting, and `next_action` skips claimed stories and returns `await-user`/`all-stories-claimed` when every remaining story is claimed (INFRA-280, CER-095.1).
- Story-keyed orchestrator state: `current_story` replaced by a story-keyed `current_stories` record (flat key kept as a derived mirror), with `scope_guard.resolve_call_story` resolving the acting story per-call (worktree cwd → worktree path → state) and refusing to guess on ambiguity — landing one story no longer wipes a sibling's scope enforcement (INFRA-281, CER-095.2). The attempt counter (INFRA-282, CER-095.3) and checkpoint step state (INFRA-283, CER-095.4) received the same story-/phase-keyed treatment with legacy-shape reads and scoped clears.
- effort.db concurrency: WAL + `busy_timeout` on every connection via a shared `_connect`, per-process init cache, atomic `BEGIN IMMEDIATE` write-side attempt-number derivation, and a two-ended reconciliation sweep with `output_prefix` ownership filtering (INFRA-284, CER-096).
- Side-session safety: new `session_state.py` session-keyed `context_sessions` record (display-only flat mirror), session-resolved `context_budget.decide`, sweep ownership exclusion via `exclude_output_prefixes`, and a bounded (2s) advisory fail-open `state_utils.state_lock` adopted by every named `state.json` writer including all three hooks (INFRA-285, CER-097).
- Merge robustness: `merge-story-worktree`/`discard-story-worktree` share a return-code-checked `_teardown_story_worktree`, report residue with literal repair commands, print a documented failed-land recovery block, and serialize their critical sections under a bounded `.companion/merge` advisory lock; the CER-050 serial-writes doctrine amended in `docs/architecture.md`/`docs/cer/backlog.md` (INFRA-286, CER-098).

### Fixed [pairmode] — Phase 104 (Attempt recording and checkpoint correctness, INFRA-263)
- `flex_build.py record-attempt` now forwards its full option set to `record_attempt.py` — previously the alias's Click declaration was empty, so it exited 2 on every documented invocation (`--project-dir`, `--story-id`, `--agent-role`, ...), a downstream-facing defect (CER-071, CER-073) that the alias existed specifically to prevent. `record-attempt --help` now shows `record_attempt.py`'s actual options instead of an empty usage line. `cmd_record_attempt` (`skills/pairmode/scripts/flex_build.py`) is declared with `context_settings={"ignore_unknown_options": True}` and a variadic `click.UNPROCESSED` argument, forwarding the collected tuple unchanged (including `--help`) and exiting with the delegate's return code.

### Added [pairmode] — Phase 103 (Worktree and story-stub friction remediation, CER-090, CER-092)
- `story_new._story_frontmatter()` now emits `touches: []` instead of a trailing-comment line, and relocates the INFRA-186 architecture.md hint prompt to an HTML comment at the top of `_story_body()`, outside the frontmatter block; `schema_validator._parse_frontmatter()`'s scalar-value branch now strips inline `#` comments before the block-sequence-start test (via the same `_strip_inline_comment` helper INFRA-211 introduced for list items), so every story stub — new or already on disk with the old buggy line — parses `touches` as a list instead of a string, closing the `TypeError` that `generate_permissions_artifact` raised inside `create-story-worktree`. Titles containing a whitespace-preceded `#` are now quoted by the generator so the new scalar comment-stripping does not truncate them. **Behaviour-affecting for downstream consumers:** any code importing `schema_validator._parse_frontmatter` directly now sees scalar values with inline comments stripped, matching the existing list-item behaviour (INFRA-262, CER-092).

### Added [pairmode] — Phase 102 (Effort-recording smoke test and harness release-channel fast-forward)
- Live field verification of the INFRA-258 async effort-recording loop, recorded as owner-labelled evidence in `docs/stories/INFRA/INFRA-259.md` § Smoke results: the in-session PostToolUse sweep and spawn-ref integrity are proven working against real builder/reviewer traffic (sections C/D builder-half PASS; final cp-102 rollup fully populated for both stories), while the same observations caught four real defects filed as CER-091 (a repeat spawn recorded no attempts row; tokens-without-outcome partial backfill on row 344; a permanently-pending row 343; post-merge FAIL reconciliation resurrecting a cleared attempt counter) plus CER-090 (gitignored `build/`/`dist/` payload gutting the vendored observability node_modules in fresh story worktrees) and CER-092 (`story_new.py` emits the `touches:` trailing-comment frontmatter that crashes `create-story-worktree`) (INFRA-259).
- `checkpoint-tag` is now CLI-first: `CLAUDE.build.md` § Checkpoint and the fleet `CLAUDE.build.md.j2` template mandate `record-checkpoint-step checkpoint-tag` before any raw `git tag`, closing CER-083's silent-gate-skip gap; `_record_checkpoint_step` stamps `state.json["checkpoint_phase"]` atomically with the step list and `next_action.infer_position` ignores a checkpoint list stamped for a different phase (stale-stamp override, matching-stamp resume, unstamped backward-compat — all regression-tested); the flex-harness release-channel promotion (tag-pinned `merge --ff-only` into `/mnt/work/flex-harness`) is documented as an orchestrator-owned checkpoint step in `docs/architecture.md` § Release channel and flex's own `CLAUDE.build.md` only, keeping the fleet template project-neutral (INFRA-260).


### Added [pairmode] — Phase 101 (Attempt recording and checkpoint reporting correctness)
- `flex_build.py checkpoint-report` now prints a **phase-scoped** cost rollup first (attempts filtered by the active phase's Stories-table story IDs via a parameter-bound `_query_effort_by_story_ids`), with per-role and per-story counts, zero-attempt stories listed explicitly, and explicit degradation lines when scoping is unavailable; the db-lifetime rollup is retained second under a clearly-labeled `=== lifetime cost rollup (all phases) ===` heading. `resolver-state`'s `effort_by_role` payload deliberately stays lifetime-scoped (shipped read contract for the observability SPA), with a lock-in test. Fixes the cp-100 report reading "builder: 19 attempt(s)" — a lifetime count — for a three-story phase whose stories each took one attempt (INFRA-256).
- `attempt_number` in effort.db is now truthful: `effort_db.next_attempt_number` derives a lifetime spawn ordinal per `(story_id, agent_role)` from an indexed, bound-parameter `COUNT(*)`, passed explicitly by `subagent_transcript.record_attempt_from_transcript` (previously every hook-recorded row was stamped with the recorder's default of 1 — e.g. INFRA-247/248's 3–4 same-story rows all reading attempt 1). The `.companion/attempt_counter.json` escalation-ladder semantics (resolver rows 5/6/7) are untouched; the derivation is non-raising, degrades to 1, and sits behind the `effort_tracking` early return. Historical all-1s rows are left as-is, with the discontinuity documented (INFRA-257).
- Async-spawn effort recording made truthful via two-phase deferred reconciliation: at spawn time the hook records the row with `agent_id`/`output_file` spawn refs (guarded `ALTER TABLE` columns); later PostToolUse sweeps and a bounded best-effort SessionStart catch-up read the completed subagent transcript (`stop_reason: end_turn`) and backfill tokens/outcome via a single-shot `WHERE tokens_total IS NULL` update, bumping the FAIL escalation counter at reconciliation time. Token summation now dedupes streaming JSONL entries by message.id last-wins (the old sync path summed them, inflating every recorded total). Phase-level checkpoint workers (security-auditor, intent-reviewer) are attributed to `phase:<key>`, never an individual story. `hooks/post_tool_use.py` untouched (INFRA-258).

### Added [pairmode] — Phase 100 (Scope-guard fail-closed completion, CER-048 close-out)
- `scope_guard.py`'s active-story fail-open branches (missing/malformed/empty permissions artifact) now check `_is_protected()` before allowing, closing the hole where a protected-path write slipped through whenever a story's permissions artifact hadn't materialized; the four `PROTECTED_GLOBS`-duplicate denies were retired from `.claude/settings.json` (tooling-only end-state, operator-applied), and CER-048 is resolved (INFRA-253).
- Live `expected_step_tokens` derivation restored for the context-budget gate: `record_step_growth()` maintains a bounded ring buffer of observed orchestrator context-growth deltas in `state.json` (DP7-clean — never effort.db), `derive_expected_step_tokens()` applies a three-tier live-median → seed → default fallback, `decide()` reports the value's provenance in block messages, and the growth-based re-arm past the threshold is covered by decide()-level tests; wired via one thin delegated call in `hooks/post_tool_use.py` (INFRA-254).
- `scope_guard._normalise()` now resolves and contains **all** `file_path` inputs (relative and absolute) against the main-checkout root before any glob/permissions comparison, failing closed (`path escapes project root`) on escape in every guard state including no-active-story; fixed `_norm_str()`'s character-class `lstrip("./")` (which laundered `./../../etc/passwd` into `etc/passwd`) to a single `removeprefix`. Filed from the CP-100 security audit's HIGH traversal finding (INFRA-255).

### Added [pairmode] — Phase 98 (0.2 → 0.3 regression remediation)
- Restored six caller-side instructions (`CLAUDE.build.md`/procedure skills) that had dropped a still-live mechanism during the Era 3 harness redesign: effort recording (token capture, attempt rows, checkpoint-time cost rollup) now runs hook-side from live transcript data rather than an orchestrator-view (INFRA-236); attempt-count writes for retry/loop-breaker/human-pause escalation are wired back into the build loop (INFRA-237); active-story stamping and story-scope enforcement are restored in the per-story worktree loop, with stale `pipe_path` reads retired and explicit worktree-path normalization added (INFRA-238); `checkpoint-tag` now marks the phase complete in `docs/phases/index.md` atomically in the same CLI call that resets `checkpoint_step` (INFRA-239); per-project parameterization is restored in procedure skills, unblocking phase-97's fleet migrations (INFRA-240, priority); the builder/reviewer spawn `subagent_type` contract is reconciled with the context-budget gate allowlist, with `bootstrap.py` propagation and model-override verification added to scope (INFRA-241).
- Ideology enforcement redesigned as spec-time alignment plus a narrow reviewer drift check, moving the check earlier than end-of-phase-only (INFRA-242).
- Added a durable phase-authoring convention (single-purpose / bounded-complexity / reproducible-from-artifacts) to `phase_new.py`/`phase.md.j2` and `docs/architecture.md`, rather than building new tooling — `phase_new.py` already existed (INFRA-243).
- `README.md` and `docs/architecture.md` brought current with the 0.3 resolver-driven design; removed stale 8-step/0.2-workflow/pre-resolver claims (INFRA-244).
- Added a compact-aware context-counter refresh (`session_start.py` resets the stale post-compact counter) to close the one genuine reliability gap identified in the transcript-JSONL-based context-tracking mechanism, which was otherwise confirmed to read real transcript data and not conflate subagent/orchestrator token counts (INFRA-245).
- `reviewer` removed from `BUILD_CYCLE_SUBAGENTS`: it is the build loop's mandatory, deterministic next step after every builder attempt with no skip path, so gating it on context budget could only wedge the loop, never conserve context (INFRA-246).

### Added [pairmode] — Phase 96 (Build-loop revert safety and worktree-per-cycle isolation)
- The reviewer's FAIL-path revert now scopes `git checkout --`/`git clean -fd --` to the story's declared `primary_files`/`touches` paths (read once during "Before reviewing"), instead of a blanket `git checkout . && git clean -fd`, which had deleted two untracked directories unrelated to a reverted story's scope. Falls back to the whole-tree form only for legacy stories with no declared scope (INFRA-223).
- Added `flex_build.py create-story-worktree` / `merge-story-worktree` / `discard-story-worktree`: each story's builder/reviewer cycle now runs inside a disposable `git worktree` under `.pairmode-worktrees/<story-id>/`, merged (rebase + fast-forward) into the main branch on reviewer PASS or discarded (force-removed, branch deleted) on FAIL — structurally guaranteeing a story's cycle, including a reviewer revert, cannot touch the main worktree's files. Wired into `CLAUDE.build.md.j2`'s build loop and this project's own re-synced `CLAUDE.build.md` (INFRA-224).

### Added [pairmode] — Phase 95 (Downstream context-budget-gate hook registration and fleet rollout)
- `bootstrap.py`/`sync.py` downstream registrar generalized to wire the three load-bearing context-budget-gate hooks (`UserPromptSubmit`, `SessionStart`, `PostToolUse` `Task|Agent`) into a bootstrapped project's `.claude/settings.json`, alongside the existing `PreToolUse` block, using the same by-command find/migrate idempotency; the four companion/sidebar blocks remain opt-in (INFRA-208, CER-067).
- Fleet rollout verified: 13 of 14 in-scope fleet projects already carried the new registrations by the time of verification (no commits required); `cora` formally excluded as a known carve-out, `anchor` remains excluded as a non-pairmode-consumer sibling plugin repo; `asp`'s forged CER-067 workaround keys in `state.json` noted, reset deferred as a follow-up (INFRA-209).
- Fixed a CER-066 recurrence: `next_action.py`'s `_check_phase_completion` checkpoint guard split Stories-table rows on every literal `|`, so an escaped pipe in a title (e.g. `` `Task\|Agent` ``) shredded the row and shifted the status read off the real status cell, causing the guard to report `phase-incomplete` for genuinely-complete phases. Fixed with the unescaped-pipe split already proven in `story_update.py`, status still read from its known schema position — not a "last column" positional guess (INFRA-222).

### Added [pairmode] — HARNESS015-main (Checkpoint-sequence reset and state.json atomic-write adoption)
- `record-checkpoint-step` now resets `state.json["checkpoint_step"]` to `[]` when `checkpoint-tag` is recorded, fixing a bug where the checkpoint sequence (security audit, intent review, docs review, tagging) was silently skipped for every phase after the first (RESOLVER-017, CER-066).
- Remaining `state.json` writers (`hooks/post_tool_use.py`, `story_context.py`, `bootstrap.py`, `skills/companion/scripts/sidebar.py`) adopted the shared `state_utils._atomic_write_json` writer (INFRA-202, CER-050).
- `schema_validator._parse_frontmatter()` now strips inline YAML comments from block-sequence list items (whitespace-preceded `#`, quote-exempt), fixing malformed `permission_scope.py` allow-rules for `touches`/`primary_files` entries with an inline `# reason: ...` comment (INFRA-211).

### Added [pairmode] — HARNESS009-main (Write-path determinism)
- `flex_build.py record-checkpoint-step <step-id>`: atomically appends a validated checkpoint step ID to `state.json["checkpoint_step"]`; validates against `_CHECKPOINT_SEQUENCE`; idempotent; moves checkpoint-step write authority from LLM prose to CLI (RESOLVER-012).
- `parse_worker_verdict_json` in `next_action.py`: fail-closed JSON parser replacing the brittle text-split `parse_worker_verdict_text`; on `JSONDecodeError` or missing key all gates return `block:malformed-verdict` (RESOLVER-013).
- `gate-worker/procedure.md` updated to specify JSON-only stdout output format (RESOLVER-013).
- `_resolve_active_phase` fixed to first-non-inactive-wins, correctly sequencing multiple planned phases (RESOLVER-014).
- `architecture.md`: `record-checkpoint-step` added to `flex_build.py` CLI surface; `checkpoint_step` state-ownership row added (sole writer: `flex_build.py record-checkpoint-step`).

### Added [pairmode]
- Phase 17: correctness fixes across the pairmode skill — story status lifecycle,
  manifest-aware orchestration, schema_validator integration tightening.
- Phase 18: missing tooling — `story_update.py` (canonical story status updater),
  `.pairmode-overrides` support, bootstrap `--yes` non-interactive flag,
  `spec_exception` sidebar handler integration.
- Phase 19: test coverage and integration verification — closed gaps in
  `phase_new`, `story_resolver` link-format handling, CER ID detection,
  bootstrap `--yes` end-to-end coverage, `spec_exception` pipe contract tests.
- Phase 20: PR readiness — `README.md`, `docs/pipe-architecture.md`,
  `docs/pairmode/PAIRMODE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`,
  SessionStart hook (`hooks/session_start.py`), `pairmode_status.py` CLI,
  pre-PR audit gate, and a paused git-history review.

### Changed [core]
- `hooks/{stop,post_tool_use,exit_plan_mode,session_end}.py`: pipe path is now
  project-scoped via `.companion/state.json["pipe_path"]` with fallback to
  `/tmp/companion.pipe`. Backwards-compatible. See `docs/pipe-architecture.md`.
- `.claude-plugin/plugin.json`: added `pairmode` skill entry. The marketplace
  manifest is unchanged.

## [pairmode v0.0.x] — Phases 1-16 (flex era2 branch)

### Added [pairmode]
- Phase 1-7: core scaffold, spec-derived deny-list generation, lessons store,
  `audit` and `sync` commands, companion enhancements, audit noise reduction,
  template coherence pass.
- Phase 8-9: sync confirmation prompt, tooling fixes, dead-code cleanup,
  formal pipe contract definition.
- Phase 10: ideology capture — guided prompt flow, non-interactive mode,
  reconstruction-brief seeding.
- Phase 11-12: reconstruction workflow, blank-slate seeding,
  `RECONSTRUCTION.md.j2` scoring template.
- Phase 13: CER (Critical Engineering Review) cleanup, end-to-end
  reconstruction verification.
- Phase 14: reconstruction agent tooling, `score.py` for filling the
  `RECONSTRUCTION.md` template.
- Phase 15: rails, eras, discrete story files under `docs/stories/<RAIL>/`,
  `schema_validator.py`, `story_new.py`, `era_new.py`.
- Phase 16: `permission_scope.py` (story-scoped allow rules),
  `story_resolver.py`, manifest-aware `CLAUDE.build.md`, rail-violation
  detection in the reviewer checklist, sync rail-gap detection.

### Notes
- All changes through Phase 16 are additive to flex core. Hook files were
  not modified until the Phase 8 pipe-scoping change (which retained legacy
  fallback behavior).
- The lessons store (`lessons/lessons.json`) is append-only. Existing entries
  may only have their `status` field updated.
