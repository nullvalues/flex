# Changelog

All notable changes to flex are documented here. This project loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Pairmode-specific
changes are marked `[pairmode]`; modifications to flex core are marked `[core]`.

## [Unreleased]

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
