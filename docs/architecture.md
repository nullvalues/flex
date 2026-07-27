# Flex — Architecture

## What flex is

Flex is a Claude Code plugin built around two layers. **Pairmode** is the primary workflow: a
structured builder/reviewer build loop with effort tracking, per-story schema gates, context budget
checks, and model selection per attempt. **Companion** is the memory layer underneath: a sidebar
that captures decisions live and a canonical spec format (`spec.json`) that survives across
sessions. Pairmode enforces intent at the build gate; companion records what was decided along the
way.

This document is the source of truth for the flex codebase itself. Read it before any task.

---

## Module structure

```
flex/
  hooks/                          ← thin relays (no API calls); see § Hook architecture
    hooks.json                    ← hook event registration
    stop.py                       ← historian: extract decisions after each response
    exit_plan_mode.py             ← relay plan content for impact analysis
    post_tool_use.py              ← pair partner: relay file changes; Task/Agent branch: reads JSONL via context_budget.read_current_tokens() and writes context_current_tokens to state.json (INFRA-182); also calls subagent_transcript.record_attempt_from_transcript() to write one effort.db attempt row per spawn (INFRA-236)
    session_end.py                ← signal sidebar to summarize and exit
    pre_tool_use.py               ← thin dispatcher: Task|Agent → context_budget.py (CER-027 budget enforcement, CER-049 matcher rename; INFRA-199 scoped to tool_input.subagent_type ∈ build-cycle agents only); Edit/Write → scope_guard.py (Phase 55 file-scope enforcement); Read → cold_read_guard.py (INFRA-196 cold-read enforcement, registered/reachable since INFRA-205/INFRA-206, CER-065)
    session_start.py              ← thin dispatcher: SessionStart source → session_reset.py on clear/startup (CER-047 / Phase 68 INFRA-175); stdlib + skill import; one hook-owned state write (context_current_tokens + context_current_tokens_recorded_at + context_session_reset_at on clear/startup — INFRA-180)

  skills/
    pairmode/                     ← /flex:pairmode — bootstrap and manage pairmode
      SKILL.md
      gate_worker/
        SKILL.md                  ← plugin-versioned gate judgment procedure (WORKER-002, HARNESS002-main): single source of schema+auth verdict evaluation; instructs the worker to self-check via check-* CLIs, judge schema/auth only, treat stub as mechanical, and return the WORKER-001 per-gate verdict map; live since the flip (HARNESS006)
      skills/
        builder/
          procedure.md            ← plugin-versioned builder procedure (WORKER-005, HARNESS003-main): bounded inputs, BUILDER STUCK format, BUILD-RESULT return schema; live since the flip (HARNESS006)
        reviewer/
          procedure.md            ← plugin-versioned reviewer procedure (WORKER-006, HARNESS003-main): review checklist, REVIEW-RESULT return schema; live since the flip (HARNESS006)
        loop-breaker/
          procedure.md            ← plugin-versioned loop-breaker procedure (WORKER-007, HARNESS003-main): cold-eyes analysis, one-alternative approach, ADVICE return schema; live since the flip (HARNESS006)
        security-auditor/
          procedure.md            ← plugin-versioned security-audit procedure (WORKER-008, HARNESS003-main): CRITICAL/HIGH/MEDIUM/LOW checklist, REVIEW-RESULT return schema; live since the flip (HARNESS006)
        intent-reviewer/
          procedure.md            ← plugin-versioned intent-review procedure (WORKER-009, HARNESS003-main): story-alignment scale, design-pivot detection, doc-edit recommendations, REVIEW-RESULT with ALIGNED verdict; live since the flip (HARNESS006)
        checkpoint-docs/
          procedure.md            ← plugin-versioned docs-review procedure (WORKER-011, HARNESS004-main): documentation currency checklist, bounded inputs (phase doc, era doc, index.md, architecture.md, cer/backlog.md, story files, CHANGELOG.md), REVIEW-RESULT return schema; live since the flip (HARNESS006)
        spec-writer/
          procedure.md            ← plugin-versioned spec-writer procedure (WORKER-013, HARNESS005-main): bounded inputs (stub story file, phase doc, active era doc, one format exemplar), elaborates stub story in place (Ensures/Instructions/Tests/Out-of-scope), returns SPEC-RESULT{status: "done"|"revised"}; live since the flip (HARNESS006)
      scripts/
        bootstrap.py              ← generate pairmode scaffold from spec
        audit.py                  ← diff project against canonical templates
        sync.py                   ← apply delta from audit non-destructively
        lesson.py                 ← capture a lesson learned
        lesson_review.py          ← surface lessons, propose template updates; --drift-only runs drift promotion without lesson review
        context_budget.py         ← orchestrator context-window estimation + block decision logic (CER-027)
        flex_build.py             ← CLI wrapping pairmode helper functions (select-builder-model, select-reviewer-model, select-security-auditor-model, select-intent-reviewer-model, write-permissions, clear-permissions, permissions-create, check-guardrail, context-health, check-stub, check-schema-gate, check-auth-gate, current-phase, transition-era, write-attempt-count, read-attempt-count, clear-attempt-count (INFRA-282: `--story-id` is now an optional scope — omitted clears the whole counter file, given clears only that story's entry), story-cost-estimate, set-context-tokens, bump-context-tokens, mark-phase-complete, next-phase, check-story-scope, next-action, resolver-state, record-checkpoint-step, record-attempt); next-action added in HARNESS001-main (since the flip, HARNESS006, the sequencing core the thin dispatch loop in CLAUDE.build.md calls each iteration); resolver-state added in HARNESS007-main (pure-read resolver state dump); record-checkpoint-step added in HARNESS009-main (RESOLVER-012) — atomically appends a validated checkpoint step ID to state.json["checkpoint_step"], replacing LLM-prose writes; replaces inline python -c blocks in CLAUDE.build.md.j2; INFRA-239 wires the `checkpoint-tag` step of record-checkpoint-step to also call `_mark_phase_complete_in_index` (the write side `mark-phase-complete` shares) in the same invocation, so the checkpoint_step reset and the phase-index `complete` write happen atomically in one CLI call rather than requiring a second, separately-remembered `mark-phase-complete` call; INFRA-267 (CER-082) adds a second write to that same path — `_mark_phase_complete_in_era_ledger` flips the matching row in the active `docs/eras/` doc's `## Phases` ledger, from the same phase key, so era ledger and phase index never diverge; record-attempt added in RELEASE-009 (HARNESS012-main) — Click alias delegating to record_attempt.py, so the orchestrator template can call a single entry point; the alias is a transparent passthrough (INFRA-263): it declares no options of its own, forwards all arguments including --help to record_attempt.py, and exits with the delegate's exit code; `checkpoint-report`'s printed rollup is scoped to the active phase's stories as of INFRA-256 — story IDs are derived from the resolved phase doc's `## Stories` table (via `_parse_phase_stories_with_status`), not from `attempts.phase` or a timestamp window; a lifetime rollup (unchanged, all-phases) is printed separately underneath it — see § Effort tracking for the scoping rationale
        refresh_effort_baseline.py ← regenerate skills/pairmode/seed/effort_baseline.json from downstream effort.db files
        story_context.py          ← read/write current story in state.json; pairmode detection
        spec_exception.py         ← record protected-file overrides into spec.json conflicts
        reconstruct.py            ← refresh docs/reconstruction.md from ideology.md and brief.md
        ideology_parser.py        ← shared ideology.md and reconstruction.md brief parser
        score.py                  ← render pre-populated RECONSTRUCTION.md scoring report from reconstruction brief
        story_new.py              ← create story files on named rails
        era_new.py                ← create era documents
        era_transition.py         ← formally close the current active era and open the next; CLI: uv run era_transition.py --project-dir DIR [--name NAME] [--intent INTENT] [--yes]; also registered as flex_build.py transition-era
        schema_validator.py       ← validate story/era/phase manifest frontmatter
        permission_scope.py       ← story-scoped allow rules lifecycle for .claude/settings.local.json (legacy; Phase 55 replaces runtime use with scope_guard.py + permissions-create for new projects)
        scope_guard.py            ← story file-scope enforcement for pre_tool_use hook; reads docs/phases/permissions/<story_id>.json; fails open on non-protected paths when no active story, but fails closed (blocks) on PROTECTED_GLOBS paths even without an active story (INFRA-196), on protected paths in the active-story missing/malformed/empty-artifact branches (INFRA-253), and on any path that resolves outside the project root — all inputs resolved+contained before glob/permission checks (INFRA-255)
        state_utils.py            ← shared helper for atomic state.json writes (`_atomic_write_json`); adopted by all remaining state.json writers as of HARNESS015-main (INFRA-202) — hooks/post_tool_use.py, story_context.py, bootstrap.py, skills/companion/scripts/sidebar.py (pairmode_sync.py/pairmode_register.py already had their own inline atomic implementation)
        session_reset.py          ← pure decision logic for SessionStart counter reset; no I/O (mirrors context_budget.py D11 boundary); CER-047 / Phase 68 INFRA-175
        spec_preflight.py         ← INFRA-190/191 — scans story body sections for unverifiable route and constant references; informational only (always exits 0)
        story_resolver.py         ← resolve story IDs to story file content; parse phase manifest Stories tables
        next_story.py             ← find next unbuilt story from a phase file; CLI: uv run next_story.py <phase-file> [--json] [--project-dir DIR]
        gate_verdict.py           ← WORKER-001 gate verdict grammar: VERBS (clean/block/flag), JUDGED_GATES (schema/auth; stub excluded), parse_verdict (string → (verb, reason)), validate_verdict_map (dict → violation list); stdlib-only, no I/O; the WORKER-rail contract analogue of next_action.py's action grammar
        worker_result.py          ← generalized worker return contract (WORKER-004, HARNESS003-main): four result types (BUILD-RESULT, REVIEW-RESULT, ADVICE, SPEC-RESULT), parse_worker_result (text → dict, validated), validate_worker_result (dict → violation list); stdlib-only, no I/O; parallel to gate_verdict.py for all non-gate workers
        next_action.py            ← next-action resolver: action grammar (make_action, validate_action, ACTIONS), position read-model (infer_position), 9-state DP2 machine (resolve_next_action); HARNESS002-main adds spawn-gate-worker to ACTIONS, Row-4 DP2 split (stub→await-user directly; schema/auth→spawn-gate-worker), parse_worker_verdict_text (worker text return → per-gate verdict map), route_gate_verdict (DP3.2 aggregation: block→await-user, flag→proceed+warnings, clean→proceed); the live sequencing core since the flip (HARNESS006), pure-read; HARNESS003-main adds spawn-reviewer, spawn-security-auditor, spawn-intent-reviewer to ACTIONS and _SPAWN_ACTIONS; SCHEMA_VERSION bumped to 2; HARNESS004-main adds checkpoint-security, checkpoint-intent, checkpoint-docs, checkpoint-tag to ACTIONS; removes monolithic checkpoint from ACTIONS (constant retained for import compat); adds check_checkpoint_guards (pre-checkpoint guards: phase-completion, CER Do Now, build-gate via injectable gate_fn); checkpoint step sequencing via _CHECKPOINT_SEQUENCE; SCHEMA_VERSION bumped to 3; HARNESS005-main adds spawn-spec-writer to ACTIONS and _SPAWN_ACTIONS; adds needs_spec bool to infer_position Position (True when ## Ensures absent or &lt; 5 non-blank lines — stub heuristic; fail-safe: unreadable story file → True); Row-2 split: needs_spec True → spawn-spec-writer (model=opus, reason=needs-spec), needs_spec False → spawn-builder as before; _count_ensures_nonblank_lines private helper (pure, no I/O); SPEC-RESULT{revised} routing lives in CLAUDE.build.md orchestrator prose (not in resolve_next_action); canonical reason string: spec-revised-awaiting-review; SCHEMA_VERSION bumped to 4; spawn-reviewer is in ACTIONS/_SPAWN_ACTIONS for orchestrator dispatch but is never emitted by resolve_next_action (CER-074)
        pairmode_sync.py          ← re-render agent file frontmatter from canonical templates (sync-agents subcommand); propagate CLAUDE.build.md template changes (sync-build subcommand); sequence all three sync operations in fixed order (sync-all subcommand); also registers register/unregister/list-projects in the top-level CLI group
        pairmode_register.py      ← manage registered_projects in .companion/state.json (register/unregister/list-projects subcommands)
        pairmode_migrate.py       ← one-shot migration of an anchor-bootstrapped sibling project to flex naming (migrate-from-anchor subcommand)
        global_session_check.py   ← global SessionStart hook; detects pairmode, prints status block or bootstrap prompt; stdlib-only (runs as bare python3)
      seed/
        effort_baseline.json      ← seeded token-cost baseline for bootstrap (refreshed by refresh_effort_baseline.py)
      templates/                  ← Jinja2 templates for scaffold generation
        CLAUDE.md.j2
        CLAUDE.build.md.j2
        RECONSTRUCTION.md.j2     ← scoring report template filled in by a reconstruction agent
        agents/
          builder.md.j2             ← thin builder agent shell (WORKER-005); retired in HARNESS002-main, re-registered in INFRA-241 so subagent_type: "builder" resolves to a real agent for the context-budget gate (INFRA-199)
          reviewer.md.j2            ← thin reviewer agent shell (WORKER-006); retired in HARNESS002-main, re-registered in INFRA-241
          loop-breaker.md.j2        ← thin loop-breaker agent shell (WORKER-007); retired in HARNESS002-main, re-registered in INFRA-241; model: fable
          security-auditor.md.j2    ← thin security-auditor agent shell (WORKER-008); retired in HARNESS002-main, re-registered in INFRA-241
          intent-reviewer.md.j2     ← thin intent-reviewer agent shell (WORKER-009); retired in HARNESS002-main, re-registered in INFRA-241
          reconstruction-agent.md.j2
          gate-worker.md.j2         ← thin gate-worker agent shell (WORKER-002, HARNESS002-main); delegates all judgment logic to skills/pairmode/gate_worker/SKILL.md; carries no inline gate-detection logic; live since the flip (HARNESS006)
        docs/
          brief.md.j2
          ideology.md.j2           ← ideology and conviction record; generated by bootstrap
          reconstruction.md.j2     ← reconstruction brief for blank-slate agent; generated by bootstrap or reconstruct
          architecture.md.j2
          checkpoints.md.j2
          phases/
            index.md.j2
            phase.md.j2       ← per-phase scaffold; generated by phase_new.py
          stories/.gitkeep    ← creates stories root in bootstrapped projects (template stub only)
          eras/.gitkeep       ← creates eras root in bootstrapped projects (template stub only)
          cer/
            backlog.md.j2
    companion/                    ← /flex:companion — start each session
      SKILL.md
      scripts/
        sidebar.py                ← companion sidebar process (long-running)
        start_sidebar.sh          ← detects OS, opens sidebar in new terminal
        launch_sidebar.command    ← macOS launcher
        launch_sidebar.sh         ← Linux launcher
    observability/                ← /flex:observability — browser observability SPA
      SKILL.md
      scripts/
        flex_observability.py     ← CLI: register / unregister / list / serve
      api/                        ← Fastify 5 TypeScript API (pnpm workspace)
      ui/                         ← Vite + React 19 frontend (pnpm workspace)
    seed/                         ← /flex:seed — bootstrap canonical spec (run once)
      SKILL.md
      scripts/
        setup.py                  ← product config writer
        mine_sessions.py          ← transcript decision extractor
        reconcile.py              ← spec merger

  lessons/
    lessons.json                  ← global methodology lessons (lives in flex repo)
    LESSONS.md                    ← human-readable summary, auto-generated

  .claude-plugin/
    plugin.json                   ← plugin manifest
    marketplace.json              ← marketplace registration
```

---

## Data flow

```
Claude Code session
    ↓ (after each response)
stop.py hook → writes to /tmp/companion-<hash>.pipe (relay only, no API calls)
    (pipe path is project-scoped; hash is first 8 chars of md5 of project dir)
    ↓
sidebar.py reads pipe → calls model backend (claude_agent_sdk by default; Ollama when FLEX_MODEL_BACKEND=ollama) → extracts decisions
    ↓
persist_capture() → .companion/changes/<session-id>/incremental.json
    ↓
session ends → sidebar shows summary, exits
    ↓
next /flex:companion → detects unreconciled sessions → reconcile.py
    ↓
reconcile.py → merges into <spec_location>/openspec/specs/<module>/spec.json
```

```
post_tool_use.py → pipe → sidebar tracks file→module mapping
post_tool_use.py (Task/Agent branch) → reads JSONL transcript → writes context_current_tokens to state.json (INFRA-182)
post_tool_use.py (Task/Agent branch) → reads JSONL transcript + tool_input/tool_response/state.json → writes one attempts row to effort.db (INFRA-236)
exit_plan_mode.py → pipe → sidebar analyzes plan for cross-module impact
session_end.py → pipe → sidebar graceful shutdown signal
```

---

## Pairmode build loop

Each story moves through a fixed sequence. The orchestrator (`CLAUDE.build.md`) drives every step:

**Per-story worktree isolation (Phase 96, INFRA-223/INFRA-224).** The builder/reviewer cycle for each
story runs inside a disposable git worktree, not directly against the main project
directory. Before the builder spawns, `flex_build.py create-story-worktree --story-id
<ID>` creates `.pairmode-worktrees/<ID>/` on a fresh branch `pairmode/<ID>` cut from
the current branch tip and prints its absolute path; the orchestrator passes that path
as the builder's and reviewer's working directory. On reviewer PASS the orchestrator
calls `flex_build.py merge-story-worktree`, which rebases `pairmode/<ID>` onto the main
branch's current tip, fast-forward-merges it in, then removes the worktree and deletes
the branch (a rebase conflict aborts cleanly and surfaces to the operator — no partial
state, no auto-resolution). On reviewer FAIL the orchestrator calls `flex_build.py
discard-story-worktree`, which force-removes the worktree (uncommitted and untracked
content included) and deletes the branch **without running any command against the main
worktree's working directory**. This is the structural guarantee that a story's cycle —
including a reviewer revert — cannot touch files outside that story's worktree, closing
both the RELEASE-022 collateral-damage risk and the future cross-story concurrency risk.
Only story-build actions (`spawn-builder` / `spawn-reviewer`) are worktree-wrapped;
checkpoint-stage workers (`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`)
are read-mostly, never commit, and stay on the main worktree unwrapped. `.pairmode-worktrees/`
is git-ignored. Steps 3, 5, and 6 below happen inside that worktree.

**Worktree as in-flight claim (CER-095.1, INFRA-280).** The worktree created above is not
only an isolation boundary — it is also the *only* record of which stories are currently
being built, and the resolver reads it. The claim is taken by `create-story-worktree` (it
fails loudly rather than silently reusing an existing directory or branch) and released by
whichever of `merge-story-worktree` / `discard-story-worktree` ends the cycle; there is no
second claim file, lock, PID, or TTL — `flex_build.claimed_story_ids` reads
`.pairmode-worktrees/` directly. `next-action` skips a claimed story when selecting the next
one (`next_story.find_next_story(..., claimed=...)`), which is what lets a single orchestrator
dispatch a second story while the first is still building: the resolver names story B on the
poll that follows story A's claim, rather than repeating A until it lands. This is only sound
under one ordering rule: **the worktree must be created before the next `next-action` poll** —
the poll is what selects a story and the worktree is what claims it, so a poll issued before
the claim exists could hand the same story to two dispatches. When every remaining story in the
active phase is claimed, `infer_position` sets `all_stories_claimed = True` and
`resolve_next_action` returns `await-user` with `reason="all-stories-claimed"` — never a
checkpoint action. This is deliberate: `next_story_id is None` is otherwise read as "the phase
is finished," and Row 9's terminal step tags a phase complete; treating "every remaining story
is claimed" as a synonym for "done" would let the loop checkpoint a phase that is still
building — an irreversible write derived from an ambiguous read (the CER-077 failure class).
Stale-claim recovery is manual and deliberately so: a worktree left behind by a crashed loop
hides its story from the resolver indefinitely, and the operator clears it with
`discard-story-worktree --story-id <ID>`. The resolver never prunes a worktree it observes —
a reader that self-heals a claim would become a second writer of build state, which is exactly
the two-sources-of-truth condition CER-095 exists to close.

**Merge robustness (INFRA-286, CER-098).** Landing a story is the one moment in the loop that
touches git directly, and it has three closed gaps. (a) `merge-story-worktree` and
`discard-story-worktree` both route their `git worktree remove --force` / `git branch -D` pair
through the shared `_teardown_story_worktree` helper, which checks both return codes: a failed
removal short-circuits the branch delete (git refuses to delete a branch still checked out in a
worktree) and reports exactly what remains, with the exact repair commands, rather than printing
success over a stale claim. On `merge-story-worktree` the three loop-state clears
(`clear_attempt_count`, the `current_stories` entry, the Layer 1 permission artifact) still run
**unconditionally** after teardown — the merge already landed, so the story *is* done, and a
cleanup hiccup must not carry a stale FAIL count into the next story — with residue reported to
stderr and a non-zero exit *after* the clears, not instead of them. On `discard-story-worktree`
nothing has landed, so residue short-circuits **before** the clears, preserving the pre-existing
behaviour; the asymmetry is deliberate, not an inconsistency. (b) A failed `--ff-only` merge — the
rebase and the merge are two separate git invocations against a shared main branch, so another
`merge-story-worktree` can land between them — tears down nothing and clears nothing: the story's
commits exist only on `pairmode/<ID>`, and releasing the claim or clearing the scope stamps would
orphan them and free the resolver to hand the same story to a second dispatch while its work sits
unmerged on a branch nobody is watching. Both failure branches print a `recovery: `-prefixed block
naming exactly what survives and the copy-pasteable re-run command; re-running is the supported
recovery — it rebases again onto the new tip and lands — and is idempotent. (c) Both commands hold
`_merge_lock` (`state_utils.state_lock` on `.companion/merge`, `MERGE_LOCK_TIMEOUT_SECONDS = 120.0`,
chosen to match `_run_git`'s own subprocess timeout) across their whole critical section, narrowing
the window in which two landings contend on git's own `index.lock`. This is deliberately a bounded
advisory lock, not a queue and not a retry loop and not a multi-orchestrator guarantee
(`docs/phases/phase-109.md` § Scope statement): non-acquisition is fail-open — the command
proceeds exactly as it does today and prints a `warning: merge lock not acquired` line — because an
unbounded wait or a lock daemon would trade a rare loud, precisely-recoverable failure for a common
stall, the same trade-off `state_utils.state_lock`'s own docstring rejects. `.companion/merge.lock`
is a zero-byte advisory lock file, not persistent state — it holds no data and is never read for
content, so it owes no management-surface story.

**One-iteration-per-story contract (CER-074).** The resolver never emits `spawn-reviewer` —
it is orchestrator-dispatched only. The constant is a live member of `ACTIONS`/`_SPAWN_ACTIONS`
(the orchestrator's `ACTION_SUBAGENT_TYPE` map and the model-override rule key on it), but no
`resolve_next_action` code path constructs it, and a regression test pins that invariant. The
reason: DP3 outcome inference is git-authoritative — `infer_position` reports `PASS` if and only
if a `story-<ID>` commit exists — and only the reviewer commits, inside the story worktree, so
no intermediate state between builder-return and merge is legible to the resolver's pure-read
model over durable state. The operational rule that follows: exactly one `next-action` poll per
story — the builder spawn, the reviewer spawn, and the merge-or-discard all happen inside that
single iteration. A mid-story poll sees `attempt_count > 0` with no story commit, infers `FAIL`,
and re-dispatches a wasteful attempt 2 over a finished build. Originating decision:
`docs/agreements/HARNESS003-main.md`. "One poll per story" is one poll per story
**dispatch** (CER-095.1): the no-re-poll-before-merge rule above is unaffected by claim
filtering — a re-poll mid-story now returns a *different* story (whichever one is next
unclaimed) rather than silently re-offering the same one, which is worse, not better, and
still a caller error the rule exists to prevent.

1. **Story spec** — the phase doc names the story; the story file at
   `docs/stories/<RAIL>/<RAIL>-NNN.md` defines `## Requires`, `## Ensures`, and
   `primary_files`/`touches`. Before the builder spawns, three pre-story gates run
   as `flex_build.py` CLI calls — exit 0 is a silent pass, exit 1 surfaces the
   printed block and blocks the orchestrator, exit 2 indicates a missing story file.
   Decision logic lives in the CLI, not in the orchestrator:
   (a) the **auth gate** (`check-auth-gate`) reads `auth_gated` from story frontmatter;
   when `true`, verifies a `**Classification:**` line exists in `docs/architecture.md`;
   (b) the **schema gate** (`check-schema-gate`) reads `schema_introduces` from story
   frontmatter; when `true`, checks for a management surface story in the phase or a
   documented exception phrase in the story body;
   (c) the **stub gate** (`check-stub`) checks whether the story file contains delegation
   language ("See phase doc") or is missing an acceptance surface section.
   A story that fails any gate is blocked until the operator resolves it.
   After all gates pass, `flex_build.py spec-preflight` scans the story's
   Ensures/Instructions/Implementation-notes sections for API route references and
   SCREAMING_SNAKE constants and warns when none are found in the source tree;
   informational only, always exits 0. (Phase 84 INFRA-190/191)
   Then the **pre-story scope check** runs `flex_build.py check-story-scope` to
   surface likely-missing file declarations (missing sibling test, missing
   live-rendered template counterpart); it is informational only and never blocks.
   (Phase 78 BUILD-034/BUILD-035)

2. **Permission pre-write** — Two layers exist; only Layer 1 is wired into the automatic
   per-story worktree cycle (INFRA-238):
   Layer 1 (`permissions-create`): folded directly into `flex_build.py create-story-worktree`
   (no separate template step) — immediately after the worktree/branch are created,
   `create-story-worktree` reads the story's frontmatter and calls
   `generate_permissions_artifact()`, which generates `docs/phases/permissions/<story_id>.json`
   from the story's `primary_files` and `touches`, no-op'ing (no write, no `generated_at`
   change) when the computed `allowed_paths` already match the file on disk — so that only
   genuine scope drift re-triggers the Layer 1 file write. (Phase 86, INFRA-194; wired into the
   worktree cycle by INFRA-238.) `create-story-worktree` also calls `story_context.set_current_story()`
   directly (not via a separate `story_context.py --set` template step) to stamp the active story
   into the **main checkout's** `.companion/state.json` — the worktree has no `.companion/` of its
   own, and `scope_guard.py` always resolves state from the main checkout root regardless of the
   spawn's cwd (a git worktree carries a `.git` pointer file back to the main repo). INFRA-281
   (CER-095.2): `set_current_story()` stamps `state.json["current_stories"][story_id]` (the
   keyed record — authoritative once more than one story can be in flight) *and* the flat
   `current_story` mirror in one write, and `clear_current_story()` now takes the story ID —
   `create-story-worktree`, `merge-story-worktree` and `discard-story-worktree` all pass their
   own `story_id` through, so on PASS `merge-story-worktree` clears only *its own*
   `current_stories` entry (and the Layer 1 permission artifact for that story) via
   `story_context.clear_current_story(companion_dir, story_id)` / `clear_permissions_artifact()`;
   on FAIL `discard-story-worktree` clears both identically. Before INFRA-281 both teardown
   commands called `clear_current_story()` unconditionally: with two builders in flight, the
   first to land wiped the *global* `current_story` slot out from under whichever sibling story
   was still building, silently disabling that sibling's scope enforcement for every subsequent
   write (CER-095 defect 2) — the story-scoped clear is what closes that gap.
   **INFRA-282 (CER-095.3):** `.companion/attempt_counter.json` is the third single-slot
   structure this era keys — it is now story-keyed, one entry (`{"stories": {"<story_id>":
   <count>, ...}}`) per in-flight story, rather than a single `{"story_id", "attempt_count"}`
   whole-file rewrite. The legacy flat shape is still read transparently (`_read_attempt_counters`
   normalises both shapes) and is upgraded to the keyed shape only on the next write, so no
   migration step exists — the pre-INFRA-282 file format never needs a bootstrap pass. Under the
   pre-story whole-file rewrite, one story's FAIL bump silently reset a sibling's in-flight
   escalation count to 1 the moment the sibling also FAILed (CER-095 item 3): the resolver's
   attempt-count read for the wiped story would then infer `none` instead of `FAIL` and never
   reach the loop-breaker/model-upgrade rows. `merge-story-worktree` therefore clears only its own
   landed story's counter entry (`clear_attempt_count(project_dir, story_id)`), leaving a
   still-building sibling's count intact, mirroring the `current_stories` scoping above;
   `discard-story-worktree` clears nothing at all, so a discarded attempt's count survives into
   the retry and the ladder still escalates. The INFRA-264 E9 late-bump guard
   (`subagent_transcript._story_accepts_late_bump`) resolves "is the loop building this story?"
   from the story-keyed `current_stories` record first, falling back to the flat `current_story`
   mirror only for pre-INFRA-281 state files — keying it on the flat mirror alone would refuse a
   second live story's first late FAIL bump and stall its ladder at attempt 1. **Accepted
   limitation:** writes persist via `state_utils._atomic_write_json` (temp-file + `os.replace`),
   which guarantees no reader ever observes a truncated file, but does not serialise two
   interleaved read-modify-write calls — a genuine advisory lock across `.companion/` writers is
   deferred to INFRA-285 (CER-097) rather than being pre-empted here with a second, competing
   locking scheme.
   **INFRA-285 (CER-097):** the context-budget accounting is the fourth structure this era
   keys, and the deferred lock above now exists. `state.json["context_sessions"][<session_id>]`
   holds `context_current_tokens`, `context_current_tokens_recorded_at`,
   `context_session_reset_at`, `context_step_growth_samples` and `expected_step_tokens`
   (`session_state.SESSION_SCOPED_KEYS`) plus that session's `spawn_output_prefix` and a
   `last_seen_at` stamp; the flat top-level copies of those five keys survive as a
   **derived mirror**, written in the same read-modify-write and never consulted to *gate*
   once a keyed record exists. The mirror is kept for exactly two readers that have no
   session id to resolve against — `skills/observability/api/src/routes/context.ts` and any
   CLI reader invoked outside a session — and re-keying them is OBS-rail work. `decide()`
   resolves through `session_state.session_view()` when the PreToolUse hook passes its
   `session_id`, and fails safe with the existing CONTEXT CHECK REQUIRED block (no new reason
   string) when that session is unregistered while another entry is live within
   `SESSION_LIVE_TTL_MINUTES` (180 — deliberately not `context_budget`'s 60-minute token
   staleness TTL: one asks "is this number trustworthy?", the other "might that process still
   be running?"). A pre-INFRA-285 state file reads correctly and is upgraded on its next
   write; there is no migration step.
   Sweep ownership is filtered in **opposite directions at the two call sites, on purpose.**
   `record_attempt_from_transcript`'s PostToolUse sweep runs inside a session that just
   spawned, so it passes that session's own stored `spawn_output_prefix` as
   `pending_reconcilable(output_prefix=...)` — an inclusive "only my rows" filter, and the
   cheapest correct query. `hooks/session_start.py`'s sweep instead passes
   `exclude_output_prefixes=session_state.other_live_session_prefixes(...)`: its whole reason
   for existing (INFRA-258) is collecting orphan rows left by sessions that have since died,
   and an inclusive filter there would strand every one of them. Both filters reach both ends
   of INFRA-284's two-ended cursor, so the anti-starvation oldest-first query cannot route
   around an exclusion. This is also what stops a side session's SessionStart from bumping
   `attempt_counter.json` for a story the build loop is actively building — the row is never
   reached, so `_story_accepts_late_bump` (which cannot tell "live elsewhere" from "live
   here") never needs to.
   `state_utils.state_lock(path)` is the advisory lock, and `state_utils.update_state_json`
   the single locked read-modify-write helper every `state.json` writer now routes through
   (`user_turn_seq`, `sync`, `story_context`, and all three hooks; `phase_new` and
   `story_update`'s markdown rewrites use the sibling `_atomic_write_text`). It is
   **advisory, bounded and fail-open** by design, because "hooks are thin relays only"
   (`docs/ideology.md` § Accepted constraints, no override permitted) forbids unbounded
   blocking on the hook path: a non-blocking `flock(LOCK_EX|LOCK_NB)` poll loop bounded at
   `STATE_LOCK_TIMEOUT_SECONDS` (2 s), yielding anyway on timeout, on a missing `fcntl`, or
   on any `OSError`. It therefore **reduces but does not eliminate** lost-update risk, and it
   does not make the system safe for two competing build loops — multi-orchestrator operation
   remains out of scope (`docs/phases/phase-109.md` § Scope statement). Making it "reliable"
   (retry-until-success, a lock daemon, contention telemetry) would be a regression, trading a
   rare lost update for a common session stall.
   The `pre_tool_use.py` hook enforces the declared scope via `scope_guard.py` on
   every Edit/Write call during the builder session, including when the spawn's cwd is the
   story's worktree (`.pairmode-worktrees/<story_id>/`): `scope_guard._normalise()` strips a
   leading `.pairmode-worktrees/<segment>/` prefix from the candidate path before comparing it
   against `allowed_paths`, but **only when `<segment>` equals the currently active story's ID**
   — as of INFRA-281 resolved **per call** by `scope_guard.resolve_call_story()` (§ 9.5) rather
   than read from the single global slot `_read_current_story()` used to consult. A path under a
   *different* story's worktree (`.pairmode-worktrees/INFRA-999/...` while `INFRA-238` is active)
   is never treated as an in-scope match by this stripping, even if its trailing path segments
   happen to match an `allowed_paths` entry name for the active story — per-story worktree
   isolation depends on this distinction; stripping unconditionally would let a spawn write into
   a concurrently in-progress different story's worktree while scope_guard reports it as allowed.
   This is also why `resolve_call_story()`'s path-derived signal (`worktree-path`, § 9.5) requires
   the named worktree directory to exist on disk before it is trusted: an unverified path-string
   ID fed straight back into this same stripping check would always agree with itself by
   construction, silently defeating the guarantee this paragraph describes.
   Layer 2 (`write-permissions`/`clear-permissions`) remains a manual/on-demand mechanism —
   `flex_build.py write-permissions` calls `write_story_permissions()` to write `Edit` allow
   rules (never `Write` — the Claude Code permission engine only matches `Edit(path)` against
   file-editing tools including Write; a bare `Write(path)` rule is never evaluated, INFRA-235)
   into `.claude/settings.local.json` for every declared file, suppressing the Claude Code
   permission prompt before writes even reach the hook (Phase 81, BUILD-040). Layer 2 is
   deliberately **not** wired into the automatic worktree cycle by INFRA-238 — it is a distinct,
   optional prompt-suppression aid, not part of the enforcement path Layer 1 + `scope_guard.py`
   already cover. An operator (or a future story) may still invoke `write-permissions`/
   `clear-permissions` by hand.

3. **Builder spawn** — `model_selector.select_builder_model()` picks the model (haiku for
   doc/lesson, sonnet baseline for code, opus on high-scope signals or retry). The builder
   subagent implements the story, runs the test suite, and exits — all inside the story's
   worktree (`.pairmode-worktrees/<ID>/`), which the orchestrator created and passed as the
   builder's working directory (see § Per-story worktree isolation above).

4. **Tests** — the builder confirms `pytest tests/pairmode/ -x -q` passes before handing off.

5. **Reviewer spawn** — `model_selector.select_reviewer_model()` picks the model (sonnet
   baseline; opus on retry for `code`-class stories). The reviewer checks the diff against
   every `## Ensures` assertion and the review checklist, then either commits or reverts —
   operating inside the same story worktree as the builder.

6. **Commit / merge or discard + retry** — on PASS the reviewer commits inside the worktree
   and story status is updated to `complete`, then the orchestrator merges the worktree back
   onto the main branch (`merge-story-worktree`: rebase → fast-forward → teardown). On FAIL
   the orchestrator discards the worktree (`discard-story-worktree`) — the builder's work is
   thrown away wholesale rather than reverted in place — and respawns the builder with
   attempt_number incremented. The reviewer's in-worktree revert is now a defense-in-depth
   layer; the worktree discard is the structural guarantee (see § Per-story worktree isolation).

7. **Effort recording** — `hooks/post_tool_use.py`'s Task/Agent branch calls
   `skills/pairmode/scripts/subagent_transcript.py`'s
   `record_attempt_from_transcript()` (INFRA-236) after every builder and
   reviewer spawn. It reads the spawn's own usage directly from the live
   JSONL transcript (the same mechanical source `context_budget.py` already
   trusts for `context_current_tokens` — see § effort.db ≠ context-control
   invariant below), plus `tool_input`/`tool_response`/`state.json` for
   role/story/model/outcome, and writes one row via
   `effort_recorder.record_effort()` to `.companion/effort.db` (tokens,
   model, duration, outcome). This replaced the 0.2-era design where each
   agent template ended its final message with a self-reported
   `<usage>total_tokens: N</usage>` block that `record_attempt.py
   --usage-block` parsed — 0.3's builder/reviewer `procedure.md` return-format
   sections forbid that block entirely (WORKER-004 grammar); nothing reads
   agent-authored token prose anymore. `record_attempt.py`'s CLI remains the
   underlying writer other (non-hook) callers use directly.

8. **Loop-breaker** — if the same story fails twice, the orchestrator invokes the loop-breaker
   subagent (fable) to diagnose the root cause cold and propose one alternative approach.

9. **Context budget check** — `hooks/pre_tool_use.py` fires on every
   agent-spawn tool call (matcher `"Task|Agent"`; the current Claude Code
   harness names the tool `Agent`, earlier harnesses named it `Task` —
   see CER-049) and delegates to
   `skills/pairmode/scripts/context_budget.py`. The module reads the token
   count from `state["context_current_tokens"]` (written by
   `hooks/post_tool_use.py` after each Task/Agent completion via
   `context_budget.read_current_tokens()`, or by the SessionStart baseline
   on `/clear`/`startup`). Blocks with CONTEXT CHECK REQUIRED when
   `context_current_tokens` is absent or stale
   (`context_current_tokens_recorded_at < context_session_reset_at`; equal
   timestamps are treated as fresh — the SessionStart baseline sets both to
   the same value). When present and fresh, checks whether
   `current_tokens + expected_next` exceeds
   `threshold * (1 + overrun_pct) * flex_factor`; blocks when it does
   (unless acknowledged within the reprompt margin).
   The `decide()` signature is `(project_dir, flex_factor=1.0)` — no `story_id`.
   `pre_tool_use.py` resolves `flex_factor` itself (RELEASE-020) via
   `_resolve_flex_factor()`, which reuses `scope_guard.resolve_call_story()`
   (INFRA-281 — per-call resolution, superseding `_read_current_story` here)
   and `flex_build._story_path` / `flex_build._read_story_frontmatter`
   (frontmatter parsing) rather than duplicating story-lookup logic; it
   fails open to `1.0` when there is no active story, resolution is
   ambiguous (two or more stories in flight, which a `Task`/`Agent` spawn's
   main-checkout cwd cannot disambiguate), the story file is missing, no
   `flex_factor` is set, or any error occurs — the no-override path is
   unchanged. This closes the gap where a story's declared `flex_factor`
   raised the ceiling shown by the
   observability SPA (see `/context` route below) but not the ceiling the
   gate actually enforced, found via cold-eyes review 2026-07-17.
   No manual `set-context-tokens` call is required during normal operation;
   PostToolUse updates the count automatically. `set-context-tokens` remains
   available as a manual override / debugging escape hatch.
   Also blocks with `CONTEXT CHECK REQUIRED` when `state.json` exists but is malformed
   (JSON decode error or non-dict root) — the malformed-file path returns `{}` from
   `_read_state()`, which propagates to a missing-tokens block (CER-040).
   References: CER-027, CER-039, CER-040, INFRA-180, INFRA-181, INFRA-182.

   **Live `expected_step_tokens` derivation from orchestrator growth
   (INFRA-254).** CER-053 correctly severed `expected_step_tokens` from
   effort.db (a subagent's own per-story cost — DP7) but its HARNESS-003 fix
   left the value entirely static: `decide()` called
   `estimate_next_step_tokens(None, None, seed)` with `db_path=None`, so the
   only path that could ever change `state["expected_step_tokens"]` was a
   manual edit, and nothing at runtime overwrote it — an operator-hand-edited
   value of `111` was observed to persist through multiple builds and distort
   the ceiling arithmetic (`current_tokens + expected_next`) toward
   near-zero headroom loss. INFRA-254 restores the original INFRA-127
   live-estimate intent with a DP7-clean source: the orchestrator's own
   observed context-window growth (`context_current_tokens` deltas between
   consecutive PostToolUse observations — trustworthy since INFRA-251's
   `isSidechain` fix excluded subagent turns from that count).

   - **Recording (`hooks/post_tool_use.py` → `context_budget.record_step_growth()`).**
     In the same read-modify-write PostToolUse already performs to write
     `context_current_tokens`, it now also captures the *previous* value
     before overwriting it and passes both to `record_step_growth()`. That
     function appends `new - previous` to a bounded ring buffer,
     `state["context_step_growth_samples"]` (capped at 20 entries, oldest
     evicted), only when both values are valid positive integers and the
     delta is strictly positive — a non-positive delta (a same-value re-read,
     or a lower value from a fresh `/clear` baseline) is not genuine step
     growth and is skipped rather than corrupting the median with zero/
     negative noise. It then re-derives and writes back
     `state["expected_step_tokens"]` via `derive_expected_step_tokens()` (see
     next bullet) — this is the "gate evaluation" write path: it fires on
     every PostToolUse Task/Agent observation, immediately upstream of the
     next PreToolUse `decide()` call that will read the freshly-derived value.
   - **Derivation (`context_budget.derive_expected_step_tokens(state)`,
     pure, no I/O).** Three tiers, in order: (1) **live** — if
     `context_step_growth_samples` holds >= 5 numeric entries, return their
     median; (2) **seed** — otherwise, the stored `state["expected_step_tokens"]`
     value (bootstrap seed, or any hand-edited override) when present and
     positive; (3) **default** — otherwise, `THIN_HARNESS_STEP_TOKENS`. Once
     >= 5 growth samples exist, tier 1 permanently overrides tier 2 on every
     subsequent recording call — a hand-edited value is overwritten by the
     next derivation once live data is available. This is the intended
     behavior, not a bug: the whole point of restoring liveness is that a
     stale manual number cannot silently persist once real observations
     exist.
   - **`decide()` stays strictly read-only (D11).** It calls
     `derive_expected_step_tokens(state)` to read (never write) the current
     tier and value, then still passes that value through
     `estimate_next_step_tokens(None, None, seeded_default)` — preserving the
     literal `estimate_next_step_tokens(None` call site CER-053's own
     regression test (`test_expected_step_tokens_source.py`) asserts, and
     the DP7 guarantee that no code path in the derivation ever opens
     effort.db. `record_step_growth()` (called only from `post_tool_use.py`)
     remains the sole writer of both `context_step_growth_samples` and
     `expected_step_tokens`.
   - **Provenance in the block message (Ensures #5).** The rendered
     `CONTEXT BUDGET` prompt appends a trailing
     `[expected_step_tokens estimate: <provenance>]` line —
     `"live (N samples, median M)"`, `"seed"`, or `"default"` — so an
     operator can see at a glance whether the number the gate is using is
     live-observed or cold-start.
   - **Growth-based re-arm past threshold.** `should_block()`'s existing
     margin-crossing re-block logic (INFRA-193/INFRA-251) already covers
     this case correctly at the pure-function level — when the budget was
     acknowledged and `context_current_tokens` has since grown by
     `>= context_budget_reprompt_margin` while still over the ceiling, it
     re-blocks (fresh acknowledgment required); below margin, or below
     threshold, acknowledgment clearing is unchanged. INFRA-254 adds
     decide()-level integration test coverage for this path (previously
     only exercised at the `should_block()` unit level) as part of closing
     the 102k→174k silent-gap symptom the operator observed, where a
     hand-edited near-zero `expected_step_tokens` made the ceiling-crossing
     check depend almost entirely on `current_tokens` alone, so the gate
     only ever fired at whatever coarse-grained `Task`/`Agent` boundary
     happened to cross it — a live, realistic `expected_next` estimate
     closes that gap in practice by making the projected-total check
     meaningful again, without changing `should_block()`'s math itself.
   - **State key inventory addition:** `context_step_growth_samples` — a
     bounded list (max 20) of positive integer deltas, written only by
     `record_step_growth()`, read only by `derive_expected_step_tokens()`.
     No new database table; this is a `state.json` ring buffer only, and is
     observable via the existing `/context` observability route / companion
     surfaces (no dedicated management UI required for this bounded,
     regenerated-on-observation buffer).

   **On the threshold constant (INFRA-241).** The live default threshold
   (`context_budget.py`'s `decide()`: `int(state.get("context_budget_threshold",
   130000) or 130000)`) is an **empirically-tuned defensive heuristic for
   managing build-churn/drift, not a hard platform token limit**. It is not
   derived from any documented model context window; it exists to give an
   operator a "close enough" signal to decide whether to `/clear` or continue
   given the next story's complexity, before a session's accumulated context
   degrades build quality. It may need recalibration over time — different
   models, longer sessions, or changed story complexity profiles could all
   shift where "close enough" actually sits — and recalibrating it is a
   config-value change (`context_budget_threshold` in `state.json`), not an
   architectural one.

   **On the gate's real dispatch scope (INFRA-241).** The subagent_type
   allowlist above (`BUILD_CYCLE_SUBAGENTS`) is a no-op unless spawns for
   those four roles actually carry a real, registered `subagent_type` —
   see § Spawn contract: subagent_type resolution below for the full history
   of why this was previously fully decorative and how it was restored.
   `reviewer` is not in `BUILD_CYCLE_SUBAGENTS` (INFRA-246): it is the build
   loop's mandatory, deterministic next step after every builder attempt,
   with no legitimate alternative action for the gate to preserve by
   blocking it, unlike the four discretionary/escalation roles above.

9.5 **Story file-scope enforcement** — `hooks/pre_tool_use.py` also intercepts
   `Edit` and `Write` tool calls. It delegates to
   `skills/pairmode/scripts/scope_guard.py`, which resolves which story the
   call belongs to via `resolve_call_story(project_dir, file_path)`
   (INFRA-281, CER-095.2 — superseding the single-slot
   `state.json["current_story"]["id"]` read a prior revision of this
   paragraph described) and then reads
   `<project_dir>/docs/phases/permissions/<story_id>.json` to verify the target
   path is declared in the active story's `primary_files` or `touches`.
   `resolve_call_story` tries, in order: (1) `worktree-cwd` — *project_dir*
   is, or is inside, `<main>/.pairmode-worktrees/<ID>/`; (2) `worktree-path`
   — otherwise, the target path is under a worktree directory that exists on
   disk (deliberately filesystem-verified, not path-string-only: trusting an
   unverified path segment would let `_strip_worktree_prefix`'s own
   "segment == active story" guarantee be satisfied by construction for any
   spelled-out worktree path, defeating it — see
   `test_scope_guard_blocks_foreign_story_worktree_path_bypass`);
   (3) `state-single` — `state.json["current_stories"]` holds exactly one
   entry; (4) `state-legacy` — `current_stories` is empty/absent and the flat
   `current_story` names a story; (5) `ambiguous` — `current_stories` holds
   two or more entries: resolves to *no story*, never a guess; (6) `none` —
   no signal at all. The ambiguous case is treated identically to
   no-active-story (fail-open for ordinary paths, fail-closed for
   `PROTECTED_GLOBS`) rather than picking the most recently stamped story,
   because a wrong attribution would hand one story's allow-list to another
   story's write — worse than the already-understood no-active-story
   semantics that already cover orchestrator work between stories
   (`docs/ideology.md` § "Never silently pass contradictions"). If the
   path is not declared, the hook emits `{"decision": "block", "reason": "..."}`.
   On any error (missing state, missing permissions file, malformed JSON), the
   check fails open for **non-protected** paths so non-story orchestrator work
   (checkpointing, spec mode) is never blocked. `PROTECTED_GLOBS` paths fail
   closed unconditionally (INFRA-196, corrected INFRA-253): with no active
   story, a protected path is always blocked; with an active story, a
   protected path is blocked whenever that story's permissions artifact is
   missing, empty, or malformed — the same fail-open early returns that cover
   non-protected paths are checked against `_is_protected()` first and denied
   before they can fire. A protected path is only satisfiable by an explicit
   entry in the permissions artifact (which `permissions-create` derives from
   the story's `primary_files` + `touches`, not `primary_files` alone) — an
   active story with no permissions artifact yet is not, by itself,
   sufficient authorization for a protected path. Introduced in Phase 55
   (INFRA-138, INFRA-139); the mid-story fail-open hole in the active-story
   branch (protected paths were allowed whenever the permissions artifact was
   missing/empty/malformed, regardless of `_is_protected()`) was closed in
   INFRA-253 (Phase 100), which also retired the `PROTECTED_GLOBS`-duplicate
   static denies in flex's own `.claude/settings.json` (CER-048).

   **Input-normalisation contract (INFRA-255):** every `file_path` scope_guard
   receives — relative or absolute — is resolved to an absolute path and
   contained against the project root *before* any `PROTECTED_GLOBS` glob
   match or `allowed_paths` comparison runs. Relative inputs are resolved
   against the main-checkout root (`_resolve_main_project_root()`'s return
   value), never the raw worktree cwd; absolute inputs are resolved as
   before. `_normalise()` returns `None` for any input whose resolved path is
   not the project root or a descendant of it, and `check_path()` denies
   `None` with `"path escapes project root"` in **every** guard state — no
   active story, active story with a missing/malformed/empty permissions
   artifact, and active story with a populated `allowed_paths` alike; the
   no-active-story branch previously fell through to its fail-open
   `"no active story — allowing"` return for an unresolvable relative path,
   which is the hole this story closes. Fnmatch-based glob matching on an
   unresolved path string is not a security boundary — resolution and
   containment must happen first, or a relative traversal string
   (`../../../etc/passwd`) or a disguised one (`./../../etc/passwd`) never
   matches `PROTECTED_GLOBS` and walks straight through the fail-open
   returns. `resolve()` also follows symlinks, so a repo-internal symlink
   pointing outside the project root is denied by the same containment
   check — a deliberate fail-closed reading, not a bug.

   **`.claude/settings.json` end-state doctrine (INFRA-253):** settings.json
   carries tooling only — the PostToolUse pytest hook, `Bash` allow rules for
   the permissions CLI, and the `Edit(.claude/agents/**)` allow. It does not
   duplicate `PROTECTED_GLOBS` as static `Edit`/`Write` denies (that
   drift-prone duplicate surface is what CER-048 named and this story
   retires); story-aware authorization is scope_guard's job, per the fail-
   closed contract above. The one deny that stays,
   `Edit(docs/phases/permissions/**)`, is deliberately outside the
   story-satisfiable gate — it guards against a story authorizing edits to
   its own (or another story's) permissions artifact, an anti-self-scope-
   modification rule that must never be liftable by any story's declared
   scope. Normal build cycles must not require writes to
   `.claude/settings.json` or `.claude/settings.local.json` — both are
   themselves `PROTECTED_GLOBS` entries, and the one legitimate change
   surface (this doctrine's own edits) is operator-applied, not builder-
   applied, because Claude Code's auto-mode classifier blocks all agent
   writes to `.claude/settings.json` regardless of scope_guard's decision
   (INFRA-247 precedent, harness-level, above project hooks).

10. **Checkpoint** — at phase end, the checkpoint sequence runs:
    `checkpoint-security` (security-auditor, WORKER-008) → `checkpoint-intent` (intent-reviewer,
    WORKER-009) → `checkpoint-docs` (docs-reviewer, WORKER-011) → `checkpoint-tag` (inline git
    operation). Pre-checkpoint guards (phase-completion, CER Do Now, build gate) must pass before
    the sequence starts. Step state persists in `state.json["checkpoint_step"]`; the resolver emits
    one action per call, and the harness applies the checkpoint-agent model override (model_selector)
    when spawning each leaf worker. Documentation is updated, all planned stories are verified
    complete or deferred, and the phase is tagged. Live since the flip (HARNESS006).

    Completing `checkpoint-tag` (`flex_build.py record-checkpoint-step checkpoint-tag`) does two
    writes in the same CLI call (INFRA-239): it resets `state.json["checkpoint_step"]` to `[]`
    (RESOLVER-017) **and** flips the just-tagged phase's status cell to `complete` in
    `docs/phases/index.md`, via the shared `_mark_phase_complete_in_index` helper (the phase is
    resolved by an explicit `--phase-key`/stamp/re-derivation precedence chain — see
    "Explicit phase-key precedence" below, INFRA-265). Both writes landing in one call closes the gap where
    an operator/orchestrator had to remember a second `mark-phase-complete` invocation: without the
    index write, the just-tagged phase kept re-resolving as active (its status cell was still not
    `complete`), the phase-completion guard passed vacuously (no unbuilt stories), and the freshly
    reset `checkpoint_step` made the resolver re-emit `checkpoint-security` for a phase that was
    already tagged — the `_CHECKPOINT_SEQUENCE`-complete `done` branch structurally could never be
    reached again for that phase. The write is a graceful no-op (not a failure) when
    `docs/phases/index.md` is absent or the phase row can't be found, so legacy layouts and unit
    tests that don't set up an index are unaffected.

    **Phase-stamped checkpoint state (INFRA-260 / CER-083).** `CLAUDE.build.md`'s checkpoint-tag
    instruction was, before this story, a raw `git tag && git push` — the CLI's `checkpoint-tag`
    step was never recorded, so neither the `checkpoint_step` reset nor the index mark-complete
    ever fired. Live consequence at cp99→phase-100 (2026-07-24): the leftover `checkpoint_step`
    list held the three gate steps with no `checkpoint-tag` entry, so phase-100's `next-action`
    resolved straight to `checkpoint-tag`, silently skipping `checkpoint-security`,
    `checkpoint-intent`, and `checkpoint-docs`. The fix has two halves: `CLAUDE.build.md` and
    `skills/pairmode/templates/CLAUDE.build.md.j2` now mandate the CLI path *before* the raw
    `git tag` (never the raw tag alone); and every `record-checkpoint-step` call now stamps
    `state.json["checkpoint_phase"]` with the phase key resolved by `resolve_current_phase` in the
    same atomic write that appends the step, reset to `""` alongside the `checkpoint_step` reset on
    `checkpoint-tag`. `next_action.infer_position` reads that stamp: when it is a non-empty string
    that differs from the active phase's own key, `position["checkpoint_step"]` is exposed as `[]`
    instead of the stored (stale) list — a checkpoint sequence recorded for a phase that has since
    been superseded can no longer be silently mistaken for the active phase's own progress. An
    absent, empty, or matching stamp leaves the stored list untouched, so state files predating
    this story keep resuming correctly. The resolver remains pure-read: it never writes
    `checkpoint_phase` or repairs a stale stamp it observes — only `record-checkpoint-step` writes
    it.

    **Explicit phase-key precedence (INFRA-265 / CER-077).** INFRA-260 stamped the phase key but
    left `_record_checkpoint_step` re-deriving it from `resolve_current_phase` on every call — a
    read-model documented to pick the *first* candidate row, not the *correct* one. Live-hit
    (2026-07-23): the `fold-prep` index had phase-97 and phase-98 both flagged `active`;
    phase-98's `checkpoint-tag` resolved to phase-97 — the still-in-progress fold — and marked it
    complete as a side effect of tagging 98 (caught and reverted by hand, commit `c6c2c6a`). The
    fix threads an optional `--phase-key` through `record-checkpoint-step` (era 003's
    additive-until-flip contract keeps every existing fleet call site working without it) and
    replaces the single re-derivation with a fixed precedence, applied entirely before any write:
    (1) `--phase-key` when given, first validated against `docs/phases/index.md` — a key naming no
    row exits 2 with no write; (2) otherwise `state.json["checkpoint_phase"]` when non-empty —
    recorded by an earlier step in the *same* checkpoint sequence, while that phase was provably
    active; (3) otherwise `resolve_current_phase`'s underlying candidate set
    (`_active_phase_candidates`), but **only** when it yields exactly one row — more than one
    candidate is a loud, no-write exit 2 for the terminal step (naming every candidate key and
    instructing `--phase-key`), and a stderr warning (stamp `""`, continue) for a non-terminal
    step, since nothing irreversible happens until `checkpoint-tag`. An explicit `--phase-key` that
    disagrees with a non-empty stamp is also an error, not a choice between the two — two
    disagreeing sources are strictly less trustworthy than none. `CLAUDE.build.md` and
    `skills/pairmode/templates/CLAUDE.build.md.j2` now pass `--phase-key <phase-key>` on every
    `record-checkpoint-step` call, so the mandated loop path never depends on re-derivation at all.

    **`resolve_current_phase`'s ambiguity contract (INFRA-265 / CER-077).** `resolve_current_phase`
    (and `next_action._resolve_active_phase`, which composes the same `_active_phase_candidates`
    helper rather than re-parsing the index) raises `AmbiguousActivePhaseError` when **more than
    one** index row is flagged `active` (or `active`-prefixed) with an existing phase file — the
    exact CER-077 condition. It deliberately does **not** raise when multiple rows are `planned`:
    a queue of planned future phases (this repo's own 105–108 behind 104, at spec time) is the
    normal, correct steady state of every index in the fleet, and raising there would break
    `current-phase`/`next-action` on every multi-phase project. That multi-`planned` ambiguity is
    instead caught only where it causes irreversible harm — the `checkpoint-tag` mark-complete
    write — by the precedence chain above. `current-phase`, `checkpoint-report`, `next-action`,
    `resolver-state`, and `record-checkpoint-step` each catch `AmbiguousActivePhaseError` at the CLI
    boundary and exit 2 with the message on stderr, never a raw traceback.

    **Phase-keyed checkpoint step state (INFRA-283 / CER-095.4).** Phase 109 restores single-
    orchestrator parallel builds, and `state.json["checkpoint_step"]` / `["checkpoint_phase"]` were
    the last of CER-095's four single-slot coordination structures still shared across an entire
    project: every `record-checkpoint-step` call appended to the same list and stamped the same
    slot regardless of which phase was being checkpointed, so two phases checkpointing concurrently
    interleaved into each other's progress — a step recorded for phase Q could read as already-done
    against phase P's list, and `checkpoint-tag` for one phase reset the shared list out from under
    the other phase's mid-sequence gates. (a) Completed steps now live in
    `state.json["checkpoint_steps"]`, a `dict[phase_key, list[step_id]]` — one entry per in-flight
    phase, so concurrent phases cannot silently record or wipe one another's progress. (b) The key
    used is exactly the one INFRA-265's `--phase-key`/stamp/re-derivation precedence chain already
    resolves; no new resolution logic exists, and the chain's ordering (A2 index validation, then
    A4 stamp disagreement, then A3 precedence) still runs entirely before the idempotency check,
    which is now per-key rather than global. (c) A legacy-shape `state.json` (no keyed record yet)
    is read correctly and upgraded to the keyed shape on its next successful write; there is no
    migration command and no bootstrap change. Because a genuinely legacy state predates all
    phase-keying, its accumulated list is treated as this call's own list regardless of which key
    the old stamp happened to name — matching the single-shared-list behaviour it always had — and
    only lands under a specific phase key once the keyed record exists. (d) `checkpoint-tag` removes
    only its own key (`steps.pop(effective_key, None)`) — a sibling phase's mid-sequence progress
    survives a terminal call for a different phase. (e) `checkpoint_step` / `checkpoint_phase`
    survive as a **derived mirror**, written on every call but never read to decide what to append —
    they exist only for readers outside this fix's scope
    (`skills/observability/api/src/readers/resolverState.ts`,
    `skills/observability/ui/src/api/client.ts`), which still expect one flat list and one stamp. A
    single flat slot cannot name more than one live checkpoint, so on a non-terminal step it mirrors
    that call's own key/list; on the terminal step it mirrors the sole remaining entry if exactly
    one keyed phase remains, and falls back to `[]` / `""` (today's exact post-tag value) when zero
    or two-or-more remain, rather than guessing which one to name. The CER-083 stale-stamp rule
    (above) now applies only on the legacy read path — once the keyed record exists,
    `next_action.infer_position` reads the active phase's own keyed entry directly and the stamp
    comparison is structurally unnecessary, since keying by the active phase's own key means a
    sibling phase's entry can never be mistaken for this one's. The same reasoning applies to
    `record-checkpoint-step`'s A4 disagreement check: on a legacy-shape state (at most one phase has
    ever been stamped) it still protects against an operator typo exactly as before; once the keyed
    record exists, the flat stamp only ever names whichever phase wrote most recently and a
    mismatch is no longer evidence of an operator mistake, so A4 is not applied there — applying it
    unconditionally would resurrect the exact interleave bug this story closes, rejecting a second
    phase's perfectly correct call. **Accepted limitation:** the read-modify-write window between
    a `record-checkpoint-step` call's state read and its atomic `os.replace` is not itself
    serialised by this story — two calls that interleave inside that window can still lose one
    update. Atomic replacement guarantees no reader ever observes a truncated or corrupt file; it
    does not guarantee no lost update. File-level serialisation of `.companion/` writers is
    INFRA-285's advisory state lock (CER-097), deliberately deferred rather than pre-empted here to
    avoid a second, competing locking scheme. **That deferred lock now exists** —
    `state_utils.state_lock` / `update_state_json` (INFRA-285) — and is bounded, advisory and
    fail-open, matching the reasoning above: it narrows this window rather than closing it.

### Release channel — flex-harness

flex dogfoods its own pairmode: `CLAUDE.build.md` sets `pairmode_scripts_dir =
/mnt/work/flex-harness/skills/pairmode/scripts`, a **sibling git worktree**, not
`/mnt/work/flex/skills/pairmode/scripts`. The orchestrator's build loop executes the toolchain out
of that sibling worktree deliberately, and only fast-forwards it at checkpoints — it is never
repointed at `main` directly.

**Why a separate worktree instead of pointing the loop at `main`.** If the live build loop executed
`skills/pairmode/scripts/` straight from the working tree it is itself building, every half-built
story's CLI edits would take effect on the very loop building it mid-phase — a toolchain that
changes under the harness while the harness is running is exactly the class of self-reference this
project has already been bitten by (RESOLVER-012 through RESOLVER-017 were all incidents in this
same file). Pinning the executed toolchain to the last checkpoint tag instead gives flex's own
build loop the same property it gives downstream fleet consumers: the code that runs has passed all
three checkpoint gates (`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`).

**Mechanics.** `main` is the dev line. `/mnt/work/flex-harness` (branch `fold-prep`, tracking
`origin/fold-prep`) is the pinned release channel — its `HEAD` is always some prior `cp-<phase>`
tag. Promotion is a `git merge --ff-only` to the newest checkpoint tag, run **after** the three
checkpoint gate workers have passed and the tag has been pushed — never before, since the entire
point of the channel is that the executed toolchain is one that passed them. This is a checkpoint
step (`CLAUDE.build.md` § Checkpoint, `checkpoint-tag` item 3), not an automatic or gated action;
INFRA-260 deliberately left "automate/gate the promotion" out of scope — this story makes the step
documented and verifiable, not enforced.

**Promotion commands**, run from `/mnt/work/flex` unless noted, with `<cp-tag>` resolved (never
assumed — existing tags use the `cp101-<slug>` shape, not a bare `cp-102`):

```bash
# P1 — resolve the tag and verify the fast-forward is legitimate
git -C /mnt/work/flex tag --list 'cp102*'
git -C /mnt/work/flex-harness status --porcelain --untracked-files=no   # must be empty
git -C /mnt/work/flex merge-base --is-ancestor \
    "$(git -C /mnt/work/flex-harness rev-parse HEAD)" <cp-tag> && echo FF-OK

# P2 — promote
git -C /mnt/work/flex-harness merge --ff-only <cp-tag>

# P3 — verify the pin
git -C /mnt/work/flex-harness rev-parse HEAD
git -C /mnt/work/flex rev-parse "<cp-tag>^{commit}"
git -C /mnt/work/flex-harness describe --tags --exact-match HEAD

# P4 — smoke the promoted toolchain (read-only)
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py \
  checkpoint-report --project-dir /mnt/work/flex
```

Three details are load-bearing, not incidental:

- `--untracked-files=no` on the cleanliness check — as of INFRA-261 (CER-090) the vendored
  `node_modules` payload is fully tracked and no longer the reason for this flag. The flag itself is
  unchanged (out of scope for INFRA-261); it still guards against ordinary local build noise —
  `.venv/`, `ui/dist`/`api/dist` build output, `__pycache__/`, and similar — that would otherwise
  fail a naive cleanliness check even on a channel with no real drift.
- `--ff-only` on the merge, never `--force` or `reset --hard` — a non-fast-forward means the sibling
  worktree holds commits nobody has triaged, and the correct response is to **stop and investigate**,
  not discard them.
- Promotion happens **after** the checkpoint gates, never before — the channel's entire purpose is
  that the toolchain it runs has already passed `checkpoint-security` / `checkpoint-intent` /
  `checkpoint-docs`.

**Ancestry precondition and failure rule.** The promotion is only legitimate when the harness
worktree's current `HEAD` is an ancestor of the new tag (P1's `merge-base --is-ancestor` check). If
it is not — the harness worktree has diverged, carrying commits the tag does not — the promotion
does not proceed with `--force`, `reset --hard`, or a discard of the divergent commits; it stops,
and the divergence is investigated and resolved (e.g. by rebuilding the harness worktree from the
tag, or by determining the divergent commits were themselves a mistake) before any fast-forward is
attempted.

---

## The canonical spec format

Each module has one `spec.json` at `<spec_location>/openspec/specs/<module>/spec.json`:

```json
{
  "module": "module-name",
  "summary": "One paragraph — what this module does and why.",
  "business_rules": [
    "Rules that must hold for the module to function correctly"
  ],
  "non_negotiables": [
    "Hard constraints that must never be violated — architectural, security, or contractual"
  ],
  "tradeoffs": [
    {
      "decision": "what was decided",
      "reason": "why",
      "accepted_cost": "what we gave up"
    }
  ],
  "conflicts": [],
  "lineage": [
    {
      "session_id": "...",
      "summary": "what happened in this session",
      "date": "YYYY-MM-DD",
      "resume": "claude --resume ..."
    }
  ]
}
```

**Invariants:**
- `non_negotiables` entries never auto-resolve. They require a developer decision to override.
- `lineage` is append-only. Sessions are never removed from lineage.
- `summary` is always rewritten during reconcile to reflect current state.

---

## Pairmode design

### Pairmode and companion: separation of concerns

Pairmode is flex's primary build workflow; companion is the memory layer it draws on.
Pairmode and companion are two temporal postures on the same concern — keeping intent
intact across sessions and across builds. Companion is **reactive**: the sidebar observes
a session as it unfolds and writes decisions, drift, and lineage into `spec.json` after
the fact. Pairmode is **proactive**: every story is specced in writing before code is
written, and the builder/reviewer loop gates every commit against that spec.

The two are coupled only through `.companion/state.json`. Companion writes `current_story`
so the sidebar can surface story context; pairmode reads `pairmode_version` to compute
audit deltas against the canonical templates. There is no other runtime dependency:
pairmode functions without the sidebar (the deny list still blocks protected-file writes;
the reviewer still runs), and companion functions without a pairmode scaffold (the
sidebar still captures decisions; the spec still grows).

**Reviewer-class agent tool restriction (build-loop safety).** Reviewer-class agents
(`reviewer`, `intent-reviewer`, `loop-breaker`, `security-auditor`) are restricted to
read-only tools plus `Bash` (all four reviewer-class agents declare
`tools: [Read, Bash, Glob, Grep]`; Bash is needed for test runs and git operations in
the reviewer and loop-breaker; security-auditor includes it for consistency). Tool
restriction prevents the reviewer from backdooring a fix into the code instead of
reverting it. Both commit and revert paths in the reviewer template are Bash-mediated.
The commit path stages files via `git add` scoped to the story's declared
`primary_files` + `touches` paths (or `git add -A` for legacy stories with no declared
scope). The revert path runs `git checkout -- <path>` and `git clean -fd -- <path>` for
each declared path (or `git checkout . && git clean -fd` for legacy stories with no
declared scope), ensuring revert never touches files outside the story's scope.

This document describes pairmode's internals: the scaffold it generates, the rails/eras
model, the schema validators, and the non-negotiables that keep its bootstraps repeatable.

### Core concepts

**Spec-derived protections:** The deny list in a pairmode project's `.claude/settings.json`
is generated from the project's `spec.json` non-negotiables, not hand-written. Each protection
carries a comment linking back to the non-negotiable it encodes.

**Permission override capture:** When a developer edits a protected file, the sidebar
(not the hook) classifies the file against `.claude/settings.deny-rationale.json` and
displays an override prompt. If the developer provides a reason, the sidebar writes a
`spec_exception` pipe message. The sidebar's pipe-reader calls
`skills/pairmode/scripts/spec_exception.record_spec_exception()` to append a conflict
entry to the relevant module's `spec.json` conflicts array. The hook emits only
`path` and `tool` — deny-rationale reads never occur in hooks.

**Lessons:** Methodology improvements are captured in `flex/lessons/lessons.json`.
Each lesson records the triggering situation, what was learned, what changed in the methodology,
and which projects it applies to. Lessons flow into templates via `/flex:pairmode review`.

**Template versioning:** Each pairmode-bootstrapped project records the `pairmode_version`
it was bootstrapped with in `.companion/state.json`. `/flex:pairmode audit` uses this to
determine the delta between the project's methodology and the current canonical version.
Audit compares section headers (structural presence of `##` headings) between project files
and raw Jinja2 template source — it does not render templates before comparison. Section
bodies in canonical templates contain Jinja2 variable expressions (`{{ project_name }}`
etc.); body-level content comparison should not be relied upon for semantic drift detection.

### Rails and eras

**Rails** are named architectural lanes. Each story belongs to one rail. Rail name + 3-digit
sequence number = stable story ID (e.g., `BOOTSTRAP-003`, `AUDIT-007`). Rails are defined per
project at bootstrap time; pairmode suggests defaults based on the project's tech stack.

**Eras** are strategic containers above phases. An era defines a period of development with a
unified intent. Phases and rails belong to an era. Eras are named chronologically (e.g.,
`001-initial`, `002-reconstruction`).

**Story files** live at `docs/stories/<RAIL>/<RAIL>-NNN.md` with structured YAML frontmatter:
`id`, `rail`, `title`, `status`, `phase`, `primary_files` (files primarily owned by this story),
`touches` (secondary files the story modifies). Phase docs reference story IDs in a `## Stories`
table; full story content lives in the individual story file.

Story frontmatter fields summary:

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Rail + 3-digit sequence (e.g. `INFRA-063`) |
| `rail` | yes | Rail name, uppercase |
| `title` | yes | Short description string |
| `status` | yes | One of `draft`, `planned`, `in-progress`, `complete`, `backlog` |
| `phase` | yes | Phase number string |
| `primary_files` | yes | List; may be empty only when `status` is `draft` or `backlog` |
| `touches` | no | Secondary files the story modifies |
| `story_class` | no | One of `code`, `doc`, `lesson`, `methodology`; defaults to `code` |
| `auth_gated` | no | Boolean; `false` if absent; read by `flex_build.py check-auth-gate` — when `true`, the auth gate checks `docs/architecture.md` for a recorded `**Classification:**` before building |
| `schema_introduces` | no | Boolean; `false` if absent; read by `flex_build.py check-schema-gate` — when `true`, the schema gate requires a management surface story in the phase or a documented exception |
| `source` | no | Set by drift promotion to record the originating project |
| `test_gate` | no | One of `story`, `phase_checkpoint`, `none`; absent = `story` (default). `phase_checkpoint` defers whole-suite green to the phase checkpoint; only story-scoped tests must pass. `none` skips the test run (HIGH finding when `story_class: code`). Read by the reviewer agent before running tests. |

**Story body contract sections** follow the frontmatter block. Every story must contain either
the canonical new-format sections or the legacy alias:

- `## Requires` — preconditions: prior stories that must be complete, file or system state that
  must hold before building begins.
- `## Ensures` — binary verifiable assertions, checked independently by the reviewer. One per
  line. Each assertion must be verifiable without interpretation: file exists, command output
  contains X, function Y returns Z.
- `## Acceptance criterion` — legacy alias for `## Ensures`. Accepted by all tooling without
  error; new stories generated by `story_new.py` use `## Requires` + `## Ensures` instead.

A story body that contains neither `## Acceptance criterion` nor both `## Requires` and
`## Ensures` is rejected by `schema_validator.py`. A story containing both the legacy and new
sections is also valid (transition stories written mid-migration).

**Body-section enforcement:** `validate_story_file` rejects `code` and `methodology` stories (non-`draft`, non-`backlog`) whose Ensures/Acceptance section consists entirely of pointer-delegation lines matching `See (docs|phase)` — these are not binary-verifiable assertions. Doc and lesson stories are exempt. Introduced in Phase 83 (INFRA-187).

**Era files** live at `docs/eras/NNN-kebab-name.md` with frontmatter: `id`, `name`, `status`.

**Era phase ledger (INFRA-267, CER-082).** Each era doc carries one machine-maintained ledger
section: heading `## Phases` — exactly that, or `## Phases` plus a trailing qualifier
(`## Phases (proposed — …)`), the first such heading in document order winning — holding a pipe
table with columns `| Phase | Title | Status |`. `phase_new.py` appends
`| <phase> | <title> | planned |` to it at scaffold time (`_update_era_phases_table`);
`flex_build.py mark-phase-complete` and `record-checkpoint-step checkpoint-tag` flip that row's
status cell to `complete` (`_mark_phase_complete_in_era_ledger`), from the same resolved phase key
they pass to `_mark_phase_complete_in_index`; and `check-index` check 2c
(`index_integrity._parse_era_phase_table`) enforces parity between every ledger row and
`docs/phases/index.md`. A ledger row is never written from a worktree-scoped commit path — commits
of scaffolded planning docs must stage `docs/eras/` alongside `docs/phases/` and `docs/stories/`.
Any other heading (a narrative phase-design section) must not begin with `## Phases`, or the
prefix match will resolve to it instead.

**`schema_validator.py` is the canonical frontmatter parser.** Its `_parse_frontmatter` function
must be imported and used by sibling scripts that need to read YAML frontmatter from
story/era/phase files. Do not re-implement the parser inline. Callers import it as
`from schema_validator import _parse_frontmatter` after inserting the scripts dir into `sys.path`.

**Inline-comment rule (minimal YAML subset):** a `#` preceded by whitespace, or at the start of
the value, begins an inline comment and is stripped; a `#` glued to non-whitespace content is
literal data, not a comment start. This rule applies uniformly to both block-sequence list items
(`  - value  # comment`, INFRA-211) and scalar values (`key: value  # comment`, CER-092 /
INFRA-262, phase 103) via the shared `_strip_inline_comment` helper — there is one comment rule for the
whole parser, not two. A wholly-quoted value (matching leading/trailing `"` or `'`) is exempt
from comment stripping and returned verbatim with the quotes removed. A scalar whose value is
entirely a comment (e.g. `touches:  # note`) reduces to `""` after stripping and is parsed as a
block-sequence start, exactly as an explicit `touches: []` would be.

**`schema_validator.py` draft/backlog exemption:** `validate_story_file` permits an empty
`primary_files` list when `status` is `draft` or `backlog`. Non-draft, non-backlog stories
must have at least one entry in `primary_files`.

### Story classification

Story files accept an optional `story_class` frontmatter field. Allowed values:

- `code` — production code in `skills/`, `hooks/`, etc. Default if field is absent. Reviewer
  uses sonnet baseline; upgrades to opus on retry.
- `doc` — documentation only (`README.md`, `docs/`, prose). Reviewer stays sonnet even on
  retry. Doc reviews do not get harder with retries.
- `lesson` — append-only lesson entries. Reviewer stays sonnet — lessons are high-structure
  JSON with a programmatic invariant check.
- `methodology` — template / scaffold / orchestrator-instruction changes. Reviewer stays
  sonnet baseline; upgrades if any other story in the same phase touches `code`.

The field is optional and additive — existing stories without it are treated as `code`.
`schema_validator.py` validates the value when present. `story_new.py` accepts
`--story-class` to write the field into generated frontmatter.

### Phase classification

Phase files accept an optional `phase_class` frontmatter field. Allowed values:

- `production` — at least one story in the phase touches production code (`skills/`, `hooks/`,
  etc.). Checkpoint security-auditor upgrades to opus. This is the default when the field is
  absent.
- `docs-only` — no story in the phase touches production code (documentation, lessons, templates
  only). Checkpoint security-auditor stays on sonnet.
- `pre-pr` — the phase is a final-pass audit before code leaves the repo. All checkpoint agents
  (intent-reviewer, security-auditor) upgrade to opus across every story in the phase.

The field is optional and additive — existing phase files without it default to `production` at
read time. `schema_validator.py` validates the value when present via `validate_phase_manifest`.
`phase_new.py` accepts `--phase-class` to write the field into generated frontmatter. The field
enables deterministic model-upgrade decisions at the checkpoint-agent level (INFRA-048).

### Phase-authoring convention (INFRA-243)

`skills/pairmode/scripts/phase_new.py` (wired to `/flex:pairmode phase-new`) already does the
mechanical work of authoring a phase — it renders `skills/pairmode/templates/docs/phases/phase.md.j2`
and updates `docs/phases/index.md`. This section is not new tooling; it is the convention that tool
does not yet prompt for or check, so a phase authored through it (or by hand) can still drift from
what makes a phase well-formed. Phase instantiation stays manual/operator-driven — the operator
feeds the objective via `phase-new` — this convention does not add automation on top of that
decision.

A well-formed phase meets three criteria, stated here in the operator's own terms:

1. **Single purpose.** A phase is bounded by one idea/objective — not a grab-bag of unrelated
   fixes. When a session's work naturally splits into unrelated concerns, that is a signal to open
   a sibling phase rather than widen the current one's Goal.
2. **Bounded, comparable complexity.** Phases should be roughly similar in total scope/effort to
   each other. When a single idea is too large for one phase, the break points between the
   resulting phases should be **intentional seams** — natural stopping points where the software is
   in a coherent, buildable state — not arbitrary chunking by story count.
3. **Reproducible from artifacts.** A phase's committed artifacts (the phase doc, its stories' spec
   files, whatever `docs/architecture.md`/`docs/ideology.md` sections it references) should let
   another agent or a human reader — with no access to the conversation that produced them —
   understand and continue the work. This mirrors this document's own cold-start claim in
   `CLAUDE.md` § "read before any task."

**Phase-authoring checklist** — analogous to the existing CP-N Cold-eyes checklist each phase doc
carries at *completion* time, but applied at phase *authoring* time instead:

- [ ] Does this phase's Goal section state one purpose, in one or two sentences?
- [ ] Is its scope comparable to recent phases — rough story count / `primary_files` count across
  its stories as a proxy, not a hard metric — and if not, is the reason (e.g. a break point being
  deferred to a sibling phase) explicit in the Goal or a `Parent context`/`Deferred stories` note?
- [ ] Could an agent with no access to the conversation that produced this phase, given only this
  phase's doc and its stories' spec files, start building it correctly?

`phase_new.py` prints this checklist to the operator immediately after creating a phase file (a
CLI echo, not new gating or validation logic — the operator remains the sole judge of whether the
new phase satisfies it).

**Worked example (retroactive, per Instructions item 4 — not a request to split or resize either
phase; INFRA-243's Out of scope explicitly rules that out):**

- *Phase 97* ("Fold resume — pre-fold gate, fleet migration, merge to main, re-sync"): single
  purpose — yes, fold mechanics only. Scope — large (14 pending fleet migrations) but the phase doc
  itself frames this as the reason phase-98 was opened as a sibling rather than folded in, so the
  seam is intentional and documented, not arbitrary. Reproducible — yes; the phase doc's `Parent
  context` and linked story files carry enough history to resume cold.
- *Phase 98* (this phase, "0.2 → 0.3 regression remediation"): single purpose — yes; the phase doc
  states directly that it was kept separate from phase-97 specifically because their purposes
  differ (harness self-correctness vs. fold mechanics), which is the single-purpose criterion
  working as intended. Scope — 11 stories is larger than most prior single-digit-story phases in
  this index; the phase doc's own "Recommended build order" note and per-story dependency
  annotations are what keep it reproducible despite the count, so this is treated as useful
  calibration signal for the convention (audit-driven remediation phases may legitimately run
  larger than feature phases) rather than a defect to fix retroactively. Reproducible — yes; the
  Goal section documents the audit lineage (fable Plan-mode comparison, adversarial second-opinion
  review, follow-up operator questions) an agent would otherwise be missing.

**`story_update.py` is the canonical tool for updating story status.**
`update_story_status(story_id, project_dir, status)` updates a story file's frontmatter
`status` field. `update_phase_story_status(story_id, project_dir, status)` updates the status
column in matching `## Stories`-table row(s). Since INFRA-204, the scan is scoped to the phase
manifest(s) named by the target story's own `phase:` frontmatter — resolving exact
(`phase-<key>.md`) and suffixed (`phase-<key>-<suffix>.md`) filename forms, mirroring
`story_new.py`'s `_append_to_phase` glob shapes (CER-062 / INFRA-197) — and only falls back to
scanning every `docs/phases/*.md` when the story declares no `phase:` (legacy stories predating
the `phase:` field convention). This closes CER-064's cross-phase status-leakage bug, where an
update to one phase's story row could leak into an unrelated phase manifest carrying a colliding
bare story ID.
CLI: `uv run python skills/pairmode/scripts/story_update.py --story-id RAIL-NNN --status complete --project-dir .`
**Current status (corrected — the current `CLAUDE.build.md` is a ~52-line thin loop with no
numbered "Step 3" and never calls `story_update.py`; neither does
`skills/pairmode/skills/reviewer/procedure.md`):** frontmatter/phase-table story status is not
written automatically by any orchestrator step today. It is git-commit-verified after the fact —
`flex_build.py check-index`'s status-drift check (RESOLVER-010) reads git log for a
`feat(story-<ID>)` commit and flags any story whose file still shows `planned`/`draft` as drift —
rather than orchestrator-prose-driven at commit time. `story_update.py` remains the canonical CLI
for making the correction (manual or checkpoint-docs-driven), it is just not wired into the build
loop as an automatic post-commit step.
Valid statuses: `draft`, `planned`, `in-progress`, `complete`, `backlog`.

**Note (Phase 55 / Phase 81):** Phase 55 replaced the allow-rule-only cycle with
`flex_build.py permissions-create` + `scope_guard.py` (Layer 1 hook enforcement). Phase 81
(BUILD-040) re-introduced `flex_build.py write-permissions` (which calls
`write_story_permissions()`) as Layer 2, running alongside Layer 1 to suppress Claude Code
permission prompts for the story's declared files. Both layers are now active in the build loop
simultaneously. The `permission_scope.py` functions remain for backward compatibility and manual
use.

**`permission_scope.py` path containment:** `write_story_permissions` validates every path
from `primary_files` and `touches` against `project_dir` using `Path.resolve().relative_to()`
before generating any allow rule. Paths that escape `project_dir` (traversal, absolute) are
skipped with a stderr warning. This guard must not be removed or weakened.

**`permission_scope.py` gitignore side-effect:** `write_story_permissions` appends
`.claude/story_scope.json` to the project's `.gitignore` (creating it if absent). This is
intentional — story_scope.json is ephemeral and must not be committed. Any project-level
`.gitignore` management must account for this.

**`permission_scope.py` empty-files behavior:** When both `primary_files` and `touches` are
empty (or all paths are filtered by the containment guard), the function returns without
writing `story_scope.json` or modifying `settings.local.json`. Callers must not assume that
"clear was called" implies rules were removed if write was a no-op.

**`PAIRMODE_DEFAULT_RAILS` (in `bootstrap.py`)** is the canonical source for default rail sets
by project type. It is imported by `sync.py`'s `_check_rail_gaps`. Treat it as a public
constant; changing its structure requires updating all callers.

**Rail-to-file mapping:** When `permission_scope.py` reads `primary_files` and `touches`, both
lists being empty produces zero allow rules with a warning, not a crash or silent
misconfiguration.

### Model selection: sonnet baseline, opus on demand

Pairmode pins each agent to a specific Claude model in its template frontmatter.
This is deliberate. Inheriting the orchestrator's model is a silent capability
leak — a phase started with Opus will give every builder Opus, hiding the cost
and obscuring whether the work actually requires that tier.

**Default.** Sonnet is the baseline for all reviewer-class agents (`reviewer`,
`intent-reviewer`, `security-auditor`) and for the `builder`. The
`loop-breaker` is the one exception: it is fable by default — an escalation
tier ranking above opus — because by the time the loop-breaker fires the case
is — by definition — hard, and the reasoning premium is justified. The `reconstruction-agent` is not subject to
the build-loop model pinning policy — it is spawned infrequently outside the
build loop and inherits the orchestrator's model; the reconstruction-agent
template carries no `model:` field by design.

**Reviewer model selection.** The orchestrator calls
`skills/pairmode/scripts/model_selector.select_reviewer_model(story_class,
attempt_number, phase_id=None, project_dir=None)` before spawning each
reviewer and passes the result as the Agent tool's `model` parameter. The
helper implements the following selection table:

| `story_class` | `attempt_number = 1` | `attempt_number >= 2` |
|---|---|---|
| `code` | sonnet | opus |
| `doc` | sonnet | sonnet |
| `lesson` | sonnet | sonnet |
| `methodology` | sonnet | sonnet (opus if a same-phase `code` story exists) |

Stories without a `story_class` field default to `code`. Unknown values also
default to `code` (conservative). The "same-phase code story" check for
`methodology` reads the phase manifest via `story_resolver.list_phase_stories`
and inspects each story file's frontmatter; it returns `sonnet` (fail-safe) if
the phase manifest or any story file cannot be read.

**Operational mechanism.** Override at *call time* via the Agent tool's
`model` parameter. The template intent stays clean — it encodes the baseline,
not the override — and the upgrade is per-invocation. This is the same
mechanism used for rate-limit fallback. Example:
`Agent({..., subagent_type: "reviewer", model: "opus"})`. Each affected
template carries an inline YAML comment after `model:` documenting the upgrade
triggers (e.g. `# upgrade: opus  (when retry / pre-PR audit / mid-phase pivot)`).
The pre-existing `# fallback:` comments remain in the templates — fallback
handles rate-limit substitution downward, upgrade handles edge-case
substitution upward; both apply concurrently.

**Correction (INFRA-241).** Until INFRA-241, this `Agent({..., subagent_type:
"reviewer", ...})` example described a spawn shape that could not actually
occur: HARNESS-002 had retired the rendered per-role `builder.md` /
`reviewer.md` / `loop-breaker.md` / `security-auditor.md` / `intent-reviewer.md`
agent files in favor of shared procedure skills loaded by generic thin shells,
which left no custom agent type named `reviewer` (etc.) registered anywhere
for `subagent_type` to resolve to — every real build-cycle spawn since
HARNESS-002 used `subagent_type: "general-purpose"` instead. INFRA-241
re-registers the five build-cycle roles as thin `.claude/agents/*.md` shells
(bodies unchanged from the "Shell instruction" already documented in each
role's `procedure.md` — no judgment/implementation logic duplicated into the
shell, preserving HARNESS-002's single-source-of-truth intent) so this example
is now accurate: `subagent_type: "reviewer"` resolves to a real registered
agent, and `model` is still overridden per call exactly as described above.
See § Spawn contract: subagent_type resolution below for the full mechanism
and the model-override verification this correction depends on.

**Rationale.** Most reviews catch nothing because most builders produce
correct work. The per-story reviewer task is mechanical: diff matches spec,
tests pass, checklist OK, commit. Sonnet handles that fine. Opus is overhead
for the common case. Reserve it for the explicit edge cases above where the
judgment edge actually matters — the cost difference compounds across a build
loop that may run dozens of reviews per phase.

**Fallback policy (rate limits).** If the preferred model is rate-limited,
fall back exactly one tier. Reviewers fall Opus → Sonnet (or stay at Sonnet
if already there). The builder falls Sonnet → Haiku. Never fall below Haiku
— the reasoning quality cliff is too steep to preserve loop integrity; better
to wait for the rate limit to clear than to ship with a model that cannot
follow the spec.

**Builder model selection.** The orchestrator calls
`skills/pairmode/scripts/model_selector.select_builder_model(story_class,
primary_files, protected_files, attempt_number=1) -> (model, reason)` before spawning each
builder. The function returns a `(model, reason)` tuple:

- `model` is one of `"haiku"`, `"sonnet"`, or `"opus"`
- `reason` is one of `"auto-downgrade"`, `"auto-baseline"`, `"prompted-upgrade"`,
  `"retry-upgrade"`

| `story_class` | complexity signal | attempt | model | reason | action |
|---|---|---|---|---|---|
| `doc` | any | any | haiku | `auto-downgrade` | auto |
| `lesson` | any | any | haiku | `auto-downgrade` | auto |
| `methodology` | any | any | sonnet | `auto-baseline` | auto |
| `code` | < 5 `primary_files`, no protected file | 1 | sonnet | `auto-baseline` | auto |
| `code` | ≥ 5 `primary_files` OR a protected file in touches | 1 | opus | `prompted-upgrade` | **prompt user** |
| `code` | any | ≥ 2 | opus | `retry-upgrade` | auto (no prompt) |

`protected_files` is derived from the deny list in `CLAUDE.md` § Protected
files and from `.claude/settings.json`. When the function returns
`prompted-upgrade`, the orchestrator displays the upgrade suggestion to the
user and waits for confirmation before spawning the builder. If the user
overrides the suggestion downward, the orchestrator records reason
`user-override` in the effort DB. The `--story-class` and
`--model-selection-reason` flags on `record_attempt.py` persist both fields
so the `validate-rebalance` view can surface decision-quality evidence.

Prompt text for `prompted-upgrade`:

```
MODEL SUGGESTION — Story [ID]
story_class: code
Signal: [e.g. "touches protected file hooks/stop.py" or "5 primary_files"]
Suggested builder model: opus (baseline: sonnet)
Reason: high-scope code story; opus reduces rework risk
Say "upgrade" to use opus, or "continue" to proceed with sonnet.
```

**Checkpoint-agent model selection.** The helper family is extended with two
additional selectors driven by the `phase_class` frontmatter field:

`select_intent_reviewer_model(phase_class) -> tuple[str, str]` — returns `(model, reason)` for the
intent-reviewer checkpoint agent. The `reason` string is emitted on the second line of `model_selector.py` CLI output.

| `phase_class` | model |
|---|---|
| `production` | sonnet |
| `docs-only` | sonnet |
| `pre-pr` | opus |

`select_security_auditor_model(phase_class) -> tuple[str, str]` — returns `(model, reason)` for the
security-auditor checkpoint agent. The `reason` string is emitted on the second line of `model_selector.py` CLI output.

| `phase_class` | model |
|---|---|
| `production` | opus |
| `docs-only` | sonnet |
| `pre-pr` | opus |

Unknown or absent `phase_class` values default to `"production"` for both
helpers. The orchestrator reads `phase_class` from the phase manifest frontmatter
before spawning each checkpoint agent and passes the result as the Agent tool's
`model` parameter (same override mechanism as the reviewer model selection).

### Spawn contract: subagent_type resolution (INFRA-241)

**The gap.** `hooks/pre_tool_use.py`'s context-budget gate (INFRA-199) only
calls `context_budget.decide()` when `tool_input.subagent_type` is one of the
build-cycle types in `BUILD_CYCLE_SUBAGENTS` — intentional design, not a bug;
`general-purpose`/`Plan`/`Explore` spawns must never be blocked. At the time
of this fix `BUILD_CYCLE_SUBAGENTS` held all five roles (`builder`,
`reviewer`, `loop-breaker`, `security-auditor`, `intent-reviewer`); INFRA-246
later removed `reviewer` (it is the build loop's mandatory next step, not a
discretionary spawn), leaving four gated types — see § Spawn contract above.
But HARNESS-002 had retired the rendered per-role agent files in `.claude/agents/`
in favor of shared procedure skills loaded by generic thin shells, which left
no custom agent type registered under any of those five names — nothing for
`subagent_type` to resolve to. Every real build-cycle spawn following the
then-current process used `subagent_type: "general-purpose"` (confirmed by
direct trace of the INFRA-235 build), which is never in `BUILD_CYCLE_SUBAGENTS`
— so the gate hit `sys.exit(0)` before `decide()` ever ran, for every real
build-cycle spawn since HARNESS-002. Not a partial gap: total.

**The fix.** Re-register the five build-cycle roles as thin
`.claude/agents/{builder,reviewer,loop-breaker,security-auditor,intent-reviewer}.md`
shells (`skills/pairmode/templates/agents/*.md.j2`, deployed via
`bootstrap.py`'s `AGENT_FILES` to every newly-bootstrapped and re-synced
project). Each shell's entire body is the "Shell instruction" already
documented in its role's `skills/pairmode/skills/<role>/procedure.md` — load
the procedure skill, execute for the given story/phase identifier, return the
typed result. No judgment or implementation logic is duplicated into the
shell; this preserves HARNESS-002's single-source-of-truth intent exactly (the
`gate-worker.md.j2` bootstrap template already established this thin-shell-
over-shared-skill pattern, so registering five more does not reintroduce the
per-role-file duplication HARNESS-002 eliminated). `CLAUDE.build.md.j2`'s
build-loop pseudocode now names the exact `subagent_type` per `a.action` via
an explicit table (see `CLAUDE.build.md` § Build loop) rather than leaving
`leaf-worker-for(a.action)` ambiguous — the ambiguity is what produced the
`general-purpose` choice in the first place.

**Model-override verification (Requires item 2).** Each of the five new
shells carries a frontmatter `model:` default (`sonnet` for `builder`,
`reviewer`, `security-auditor`, `intent-reviewer`; `fable` for
`loop-breaker`, matching `model_selector.select_loop_breaker_model()`'s
unconditional escalation) — consistent with the "Pairmode pins each agent to
a specific Claude model" policy above. This is safe regardless of whether a
frontmatter-pinned `model:` can be overridden per call, because the build
loop never actually depends on the frontmatter default being used: every
spawn in `CLAUDE.build.md.j2`'s pseudocode already passes `model=a.model`
explicitly (`a.model` always resolved beforehand by the matching
`model_selector.select_*_model()` call — `next_action.py` guarantees `model`
is non-`None` for all five of these actions, see `_SPAWN_ACTIONS`). The
per-call `model` parameter on the `Task`/`Agent` tool call is standard Claude
Code subagent behavior: a custom agent's frontmatter `model:` field sets only
that agent's *default* when invoked with no override; passing `model` on the
spawn call itself takes precedence for that one invocation. INFRA-237's
per-attempt escalation ladder (retry-upgrade at attempt ≥ 2, the loop-breaker's
fable tier) therefore continues to work unchanged post-INFRA-241 — it was
never resting on the frontmatter default in the first place, only on
`model_selector` computing the right value and the orchestrator passing it
per call, both of which are unaffected by this story. The `# fallback:` /
`# upgrade:` inline YAML comments on each shell (matching the `gate-worker.md.j2`
precedent) document the manual-invocation defaults only.

**Observability.** The gate reconnecting to real spawns is directly testable:
`tests/pairmode/test_pre_tool_use_hook.py::test_allowlisted_subagent_type_still_gates`
(parametrized over all `BUILD_CYCLE_SUBAGENTS` values — four since INFRA-246
removed `reviewer`) asserts `decide()` runs and blocks for each;
`tests/pairmode/test_bootstrap.py`'s
`TestBuildCycleSubagentDispatch` asserts each of the five shells is deployed,
project-name-rendered, references its procedure skill, and its frontmatter
`name:` matches the literal string `BUILD_CYCLE_SUBAGENTS` matches on.

### Pairmode tooling

**`pairmode_sync.py` — `sync-agents` subcommand.**
Re-renders the frontmatter of each agent file in `<project_dir>/.claude/agents/` from the
current canonical pairmode templates; also merges new H2 body sections from the rendered
template into the target file additively (Phase 33+).

CLI:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  sync-agents [--project-dir DIR] [--dry-run] [--yes]
```

Behaviour:
- For each `*.md` file in `<project_dir>/.claude/agents/`, finds the matching template by
  filename stem (e.g. `reviewer.md` → `reviewer.md.j2`) in `skills/pairmode/templates/agents/`.
- Renders only the frontmatter block of the template using the full context from
  `_build_template_context()` (Phase 44+): `project_name`, `build_command`, `test_command`,
  `test_dir` (INFRA-240; defaults to `"tests/"`), `migration_command`, `pairmode_scripts_dir`,
  `domain_isolation_rule`, and `protected_paths`.
  Values are sourced from `.companion/pairmode_context.json` with `.companion/state.json` as
  fallback; missing keys default to `""` or `[]`.
- Replaces the frontmatter block in the target file.
- Attempts to render the full template to extract new H2 body sections (`_merge_body_sections`).
  Sections present in the template but absent from the target are appended; existing target
  sections and project-specific sections are preserved. Sections already present are not
  duplicated.
- **Body propagation:** Full-template rendering uses `StrictUndefined`. Since Phase 44,
  the context passed to `sync-agents` includes all variables used by the canonical agent
  templates (`build_command`, `test_command`, `domain_isolation_rule`, `protected_paths`).
  For projects whose `pairmode_context.json` and `state.json` supply these values, body
  propagation now works as intended. Since INFRA-203, a body render that fails — whether
  by `StrictUndefined` on a truly-missing variable, or because an empty-valued variable
  (a graceful `""`/`[]` fallback from `_build_template_context`) feeds a section that would
  be newly appended to the target — is surfaced as an explicit `"error: failed to render
  {filename}: {reason}"` line on stderr, the file is skipped entirely (not written, on-disk
  content byte-for-byte unchanged), and `sync-agents` exits 1 when no other file produced a
  clean change. Sections whose empty variable only appears inside content already present in
  the target (and therefore not appended) do not trigger this failure. In either failure
  case, new body sections must be applied manually during deployment stories.
- Prints a unified diff (`difflib.unified_diff`) for each changed file before writing.
- `--dry-run`: exits after printing diffs without writing any files.
- `--yes`: writes without prompting.

All `*.md` files in `.claude/agents/` with a matching template are re-rendered, including
`reconstruction-agent.md` if that template exists. Files without a matching template are
skipped with a warning.
- Default: prompts once ("Apply these changes? [y/N]") before writing.
- If no matching template exists for an agent file: warns and skips that file.
- If all files rendered cleanly and no diffs were found: prints "No changes to apply." and
  exits 0. If rendering failed for one or more files: prints `"error: failed to render
  {filename}: {reason}"` to stderr for each failed file, then exits 1 when no changes were
  found. Partial success (some files changed, some errored) proceeds with the apply flow and
  exits 0, with errors already printed to stderr.
- Agent files with no frontmatter block (no opening `---`): warns and skips.

**Body-merge duplication risk (resolved, INFRA-202):** `_merge_body_sections`
previously deduped solely by exact `##`-heading string match. Target files
whose existing checklist items used bold-inline pseudo-headers (e.g.
`**1. HOOK PERFORMANCE**`) rather than true `##` headings were not recognized
as containing the canonical template's equivalent items, and the merge
appended a second, differently-numbered copy of the same content after the
file's terminal section instead of a clean no-op. Observed in
`.claude/agents/reviewer.md` and `.claude/agents/security-auditor.md`
(commit `85a6f52`, `sync-all --apply`; repaired by hand in `622309c`).
`_merge_body_sections` now matches on a normalized concept key
(`_heading_concept_key`) computed identically for a true `## ` heading and a
standalone `**N. TITLE**` pseudo-header line — stripping heading markers,
enumerator prefixes, bold/backtick emphasis, and casing/whitespace
differences — and builds the target's "already present" set by scanning the
entire target body (`_target_concept_keys`), not only its `## `-delimited
sections. A canonical checklist item already present under any covered
heading style is now a no-op, never a tail append; genuinely new template
sections are still appended additively (INFRA-202). Additionally, a template
context key absent from a project's `pairmode_context.json`/`state.json`
(e.g. `domain_isolation_rule` for flex itself, which has no domain-isolation
model) renders to `""` rather than raising `StrictUndefined` on the loose
full-template render. As of INFRA-203, `_collect_changes` re-renders, in
isolation, the raw template source of every section that would be newly
appended under a stricter context with all empty-valued keys removed; if that
stricter render raises `UndefinedError`, the file is surfaced as a render
error (naming the offending variable) and skipped rather than merged, so a
broken/empty checklist line (e.g. `` Does `` pass cleanly? ``) can no longer be
merged in silently.

**`pairmode_sync.py` — `sync-build` subcommand.**
Compares the target project's `CLAUDE.build.md` against the canonical `CLAUDE.build.md.j2`
template rendered with the project's `state.json` and `pairmode_context.json`. Prints a
unified diff. With `--apply`, writes the rendered template to the project's `CLAUDE.build.md`
after confirmation (or immediately with `--apply --yes`). With `--dry-run`, prints the diff
and exits without writing. Also seeds missing context gate keys in `.companion/state.json`
(BUILD-032, Phase 76): if `context_session_reset_at` or `context_current_tokens` are absent,
`--apply` writes a fresh-session baseline so the context gate does not false-block on first spawn.

CLI:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  sync-build --project-dir DIR [--dry-run] [--apply] [--yes]
```

Behaviour:
- Renders `CLAUDE.build.md.j2` with `project_name`, `build_command`, `test_command`,
  `migration_command` sourced from `state.json` and `pairmode_context.json` (graceful
  fallback when keys are absent).
- `--dry-run` or no `--apply`: prints diff and exits 0 without writing. Emits a warning
  line if context gate keys are missing.
- `--apply`: prints diff, prompts "Apply? [y/N]", writes on `y`. Seeds missing context
  gate keys after writing `CLAUDE.build.md`.
- `--apply --yes`: writes without prompting.
- If no changes: prints "No changes to apply." and exits 0.
- Applies a depth guard on `--project-dir` (fewer than 3 path components are rejected).

**`pairmode_sync.py` — `sync-all` subcommand.**
Sequences all three sync operations in a single CLI call: `sync.py` (methodology files)
→ `sync-agents` (agent frontmatter) → `sync-build` (CLAUDE.build.md). Safe by default:
without `--apply`, `sync.py` is skipped (it has no `--dry-run` flag) and the remaining
two commands run in dry-run mode. With `--apply`, all three are invoked. Fail-fast: if
any downstream command exits non-zero, the wrapper emits an error and exits with the same
status code; remaining commands are not invoked.

CLI:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  sync-all --project-dir DIR [--apply] [--yes]
```

Behaviour:
- `--dry-run` (default True): skips `sync.py`; runs `sync-agents` and `sync-build` in dry-run mode.
- `--apply`: runs all three; `sync-agents` without `--dry-run`; `sync-build` with `--apply`.
- `--yes` / `-y`: propagated to every downstream invocation.
- Depth guard (`_depth_guard_sync_build`) runs against `--project-dir` before any subprocess call.
- Per-command output is preceded by a `=== <label> ===` separator line.

**`pairmode_register.py` — `register`, `unregister`, `list-projects` subcommands.**
Manages the `registered_projects` list in flex's own `.companion/state.json`. All three
subcommands are registered in the `pairmode` CLI group via `pairmode_sync.py`.

CLI:
```bash
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  register --project-dir DIR
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  unregister --project-dir DIR
PYTHONPATH="${CLAUDE_SKILL_DIR}/../../.." uv run python "${CLAUDE_SKILL_DIR}/scripts/pairmode_sync.py" \
  list-projects
```

Behaviour:
- `register`: resolves `--project-dir` to an absolute path, applies `_depth_guard`
  (rejects paths with fewer than 3 components), appends to `registered_projects` if not
  already present; prints "already registered" and exits 0 if duplicate.
- `unregister`: resolves `--project-dir`, removes from list if present; prints "not
  registered" and exits 0 if absent.
- `list-projects`: prints one entry per line; prints "No projects registered." when list
  is empty or absent.
- All writes are atomic: temp file in same directory + `os.replace`.
- Reads and writes flex's own `.companion/state.json` (cwd-relative), not the target
  project's state.json.

### Per-project parameterization surface (INFRA-240)

The builder and reviewer procedure skills (`skills/pairmode/skills/builder/procedure.md`,
`skills/pairmode/skills/reviewer/procedure.md`) are **plugin-versioned** — shared, unrendered,
identical across every project that bootstraps pairmode 0.3 (see § Pairmode design above). This
means any project-specific fact baked directly into their prose (a hardcoded test command, a
fixed test-directory convention, one project's protected-file list) is silently wrong for every
*other* project that shares the same procedure skill. Facts that genuinely vary per project —
test command, test-directory convention, protected-file list, domain-isolation rule — must
instead live on a **rendered** per-project surface the procedure skills read at build/review
time, not on the shared skill text itself.

That rendered surface is the **Build standards** line in each project's own `CLAUDE.build.md`
(rendered from `skills/pairmode/templates/CLAUDE.build.md.j2`): `test_command`, `test_dir`,
`protected_paths`, and `domain_isolation_rule` are interpolated there from
`.companion/pairmode_context.json` (written by `bootstrap.py` at bootstrap time; `test_dir`
defaults to `"tests/"` when not supplied via `bootstrap.py --test-dir`) with `.companion/state.json`
as fallback — the same source `pairmode_sync.py`'s `_build_template_context()` already used for
`sync-build` re-rendering. `builder/procedure.md`'s and `reviewer/procedure.md`'s "When you are
done" / "Story test verification" / checklist items (TEST COVERAGE, PROTECTED FILES, BUILD GATE)
now point at this line instead of a literal invocation — this is what makes the builder's
declared input-contract line ("read `CLAUDE.build.md` for build standards and test command",
`builder/procedure.md` § Input contract) actually satisfiable: before this story the rendered
`CLAUDE.build.md.j2` carried no test-command field at all, so the contract's claim was
unbacked and the procedure's hardcoded flex literal was the *only* place the value actually
lived. A literal-string scan test (`tests/pairmode/test_procedure_skills.py`) asserts neither
procedure skill contains `tests/pairmode/`, the `-x -q` pytest flags, or flex's own enumerated
protected-file list (`skills/seed/scripts/`, `skills/companion/scripts/sidebar.py`,
`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`) verbatim; a synthetic-project
test (`tests/pairmode/test_bootstrap.py::TestSyntheticProjectPerProjectParameterization`)
bootstraps a non-flex-shaped project (`pnpm build`, `spec/` test dir) and confirms its own
rendered `CLAUDE.build.md` carries its own values, never flex's.

Out of scope for this story (deliberately): the procedure skills themselves remain
plugin-versioned and are never re-rendered per project — only the *values* they reference
became per-project, not the files. `hooks/`-layer conventions (hook thinness, the fixed
`$TMPDIR/companion.pipe` relay path) are genuinely identical across every project — they
describe the shared plugin code every project runs, not a per-project fact — and were left
as-is rather than parameterized.

### Pairmode non-negotiables

- Template context uses separate keys for brief.md and ideology.md must-preserve content:
  `must_preserve_str` (newline-joined string) for `brief.md.j2`; `must_preserve` (list)
  for `ideology.md.j2`. Do not merge these back into a single key.

- Lessons are append-only. Existing lesson entries may only have their `status` field updated.
- Two optional lesson fields were introduced in Phase 24 (L012) and are not yet supported by
  the `lesson.py` CLI — write them directly when appending:
  - `value_framing` (string) — the durable metric framing for efficiency-based lessons (e.g.,
    the efficiency ratio formula). Captures the objective that remains stable even as model
    prices and capabilities change.
  - `validation_phase` (string) — the phase ID that confirmed or revised the lesson. Points
    forward from the original lesson to its data-backed validation, enabling traceable
    methodology evolution.
- Templates must render correctly for projects with no prior Flex spec (blank-slate bootstrap).
- The deny list generator must include an inline comment on each generated rule linking it to
  the non-negotiable that produced it.
- Pairmode bootstrap must never overwrite existing project files without explicit user confirmation.
- Pairmode scripts that import sibling modules must either (a) use `sys.path` insertion to add
  the flex repo root at import time, or (b) be invoked with `PYTHONPATH` set to the flex
  repo root. SKILL.md invocations must document the required `PYTHONPATH` prefix.
- Callers of `parse_reconstruction_brief` that pass constraints to `ideology.md.j2` must
  normalize the `{name, rule}` schema returned by the parser to `{name, rule, protects,
  rationale, override_path}` before rendering. `bootstrap.py`'s `--from-reconstruction`
  branch does this; any new caller must replicate it. `parse_reconstruction_brief`
  intentionally returns the slim schema because the reconstruction brief does not capture
  those fields.

### Ideology enforcement: three-stage division of labor (INFRA-242)

0.2's reviewer ran a full 3-part ideology re-audit (conviction consistency,
constraint-rationale preservation, fingerprint awareness) against `docs/ideology.md`
on every single story diff. 0.3 initially dropped this from the per-story reviewer
entirely and moved it exclusively to the checkpoint-level `intent-reviewer`
(§ Pairmode build loop step 10), which runs once per phase rather than once per
story. INFRA-242 corrects this: the intent was never "the same check at a cheaper
cadence" — it is a genuine division of labor across three distinct pipeline stages,
each doing a different job:

1. **Spec-authoring time (primary enforcement)** — `spec-writer/procedure.md`
   Step 4a reads `docs/ideology.md` as a declared bounded input and checks the
   drafted `## Ensures`/`## Instructions` against `## Core convictions`,
   `## Accepted constraints`, and `## Prototype fingerprints` before the spec is
   written to `docs/stories/<RAIL>/<ID>.md`. Conflicts are resolved inline in the
   spec draft when possible (preferred — the spec-writer has full story-intent
   context) or flagged for the operator (`status: "revised"`) when they cannot be.
   A spec that is already ideology-consistent means the builder inherits that
   alignment structurally by implementing the spec faithfully — this is the load-
   bearing stage.

2. **Per-story review time (narrow drift check)** — `reviewer/procedure.md`
   checklist item 12 (IDEOLOGY DRIFT) is gated on out-of-spec diff content: a diff
   that exactly matches its spec-approved scope (`primary_files`/`touches` +
   `## Ensures`/`## Instructions`, already read for the RAIL SCOPE check) never
   re-reads `docs/ideology.md` at all — the check is a no-op on the common
   in-scope-and-clean path. Only content the diff introduces beyond what the spec
   called for is checked against `docs/ideology.md`, and only for whether that
   specific out-of-spec content independently violates a convictions/constraints/
   fingerprints entry. This is a drift check scoped to the gap between spec and
   diff, not a re-audit of the diff against the whole of `docs/ideology.md`.

3. **Checkpoint time (phase-wide backstop)** — the `intent-reviewer`
   (§ Pairmode build loop step 10) retains its existing phase-wide `IDEOLOGY DRIFT`
   section (`intent-reviewer/procedure.md`), unaffected by INFRA-242. It catches
   the case individual stories each pass their narrow checks but the phase as a
   whole trends away from a stated conviction or undermines a stated constraint —
   a pattern only visible in aggregate across the phase's stories, not from any
   single story's spec or diff.

### Auth policy integration

Before any auth-gated story (authentication, session handling, permission checks,
access-controlled resources) is built, the orchestrator must answer the auth model
classification question from `~/.claude/policies/auth-coexistence.md`.

**Policy files** — three files live at `~/.claude/policies/`:
- `auth-rbac.md` — role-based system controls (admin panels, org-level content)
- `auth-abac.md` — ownership and content-level access (user-authored content, shared workspaces)
- `auth-coexistence.md` — classification question + coexistence patterns (when both apply)

**Build loop integration:** A dedicated per-story auth check section between "Model evaluation" and "Step 1 — Spawn the builder" in `CLAUDE.build.md` gates every auth-gated story on an answered classification question, regardless of where it falls in the phase. The answer (RBAC / ABAC / both) must be recorded in the phase doc or `docs/architecture.md` before building that story.

**Optional spec review step (§ 0):** Before the first story in a phase, `CLAUDE.build.md` includes an optional "Spec review" step that spawns a `general-purpose` subagent to cold-eyes review the full phase spec against the actual codebase (catching mismatched signatures, missing imports, wrong call-site arguments, and references to non-existent symbols) before any builder time is spent. Recommended for phases with 3+ stories; skip for single-story hotfix or documentation-only phases.

**Pairmode equivalent of `spec.json non-negotiables`:** The policy files use
`spec.json non-negotiables` language. In pairmode-based projects (which use story files
+ `architecture.md` rather than a `spec.json`), the equivalent is a dedicated
`## Auth model` or `## Non-negotiables` section in `architecture.md` or the phase doc
that names: (a) the chosen auth model (RBAC / ABAC / both), (b) the enforcement layer
module, and (c) which resource types map to which model (for coexistence cases). This
section serves as the spec contract that reviewers check before accepting any auth-gated
story.

---

## Era 003 additive contract

This section records the binding methodology agreements for the `HARNESS001-ante1 … HARNESS005-main`
additive window, extended through HARNESS009-main. Authority: `docs/agreements/HARNESS001-ante1.md`, DP4 and DP7.

### (a) Four-point additive contract (DP4)

Scoped to the window `HARNESS001-main … HARNESS005-main`:

1. **Existing CLI surface frozen.** No rename / removal / flag-change to existing `flex_build.py`
   subcommands or their output contracts. Additions (notably `next-action`) are allowed.
   Consolidation / removal of old CLIs (`select-builder-model`, `next_story`, `check-*-gate`,
   `read-attempt-count`, …) happens only at or after the flip (HARNESS006).

2. **Resolver is pure-read.** `next-action` reads `state.json`, `effort.db`, the era/phase/story
   index, story status, and attempt counters; it writes nothing authoritative (any cache is
   disposable and never read back by the orchestrator). The orchestrator remains the sole writer
   of all shared state during the additive window. Note: `check_checkpoint_guards` (introduced in
   RESOLVER-008) calls `_run_build_gate_subprocess` when `gate_fn` is not injected — this is a
   subprocess call, not a state write. The pure-read constraint refers to `state.json`; the
   subprocess invocation is advisory-only and fails open on timeout or error.

3. **Fleet-facing surface frozen on `main`.** Consumer-facing templates (`CLAUDE.build.md.j2`,
   `agents/*.md.j2`), global hooks, and agent files do not change on `main` until the flip — a
   mid-era `sync` on `main` yields the unchanged 0.2.x loop, never half-built harness code.
   These evolve freely on `harness` (which the fleet never executes per DP1).

4. **Guard test.** A `tests/pairmode/` test snapshots the 0.2.x `flex_build.py` command/flag
   surface and asserts it stays a superset of that snapshot through HARNESS005 (additions are
   OK; removals and renames fail). Cross-reference RELEASE-003. The snapshot is rebaselined at
   the flip.

### (b) State-ownership table (DP7)

Single writer per shared-state surface during the additive window. The `next-action` resolver
is **read-only** on every row.

| Surface | Sole writer (additive window) | Resolver access |
|---------|-------------------------------|-----------------|
| `state.json` `context_*` (context tokens: `context_current_tokens`, `context_current_tokens_recorded_at`, `context_session_reset_at`) | orchestrator hooks (`post_tool_use.py` / `session_start.py`), frozen | read-only |
| `state.json` `checkpoint_steps` (dict, keyed by phase key; INFRA-283, CER-095.4) | orchestrator (`flex_build.py record-checkpoint-step`) — **the authority** as of INFRA-283: one completed-step list per in-flight phase, so concurrent phases checkpointing under one orchestrator cannot record or wipe one another's progress. `checkpoint-tag` removes only its own key (`steps.pop(effective_key, None)`); a legacy-shape `state.json` (no keyed record) is read correctly and upgraded to this shape on its next successful write — no migration command exists | read-only (`next_action.infer_position` reads the active phase's own entry directly by key when this record is present; never writes it) |
| `state.json` `checkpoint_step` | orchestrator (`flex_build.py record-checkpoint-step`); HARNESS009-main moved authority from LLM prose to CLI (RESOLVER-012); HARNESS015-main (RESOLVER-017) added reset-to-`[]` on `checkpoint-tag` completion, fixing a silent skip of the entire checkpoint sequence on every phase after the first; INFRA-260 (CER-083) — the resolver now honours this list only when the adjacent `checkpoint_phase` stamp is absent, empty, or matches the active phase's own key, so a list stamped for a *different* phase reads as `[]` instead of silently resuming a stale checkpoint. **As of INFRA-283 (CER-095.4), this is a derived mirror of `checkpoint_steps` above, not the authority** — written on every call (this call's own key's list on a non-terminal step; the sole remaining entry, or `[]` on ambiguity/exhaustion, on the terminal step) purely for readers outside this fix's scope, and the CER-083 mismatch rule above now applies only on the legacy path, before a keyed record exists | read-only (mismatched-stamp override on the legacy path only, still no write) |
| `state.json` `checkpoint_phase` | orchestrator (`flex_build.py record-checkpoint-step`), added INFRA-260 (CER-083); INFRA-265 (CER-077) — the value stamped is now resolved by an explicit precedence chain, not a single re-derivation: an explicit `--phase-key` first (validated against the index; a mismatched stamp is an error, not a choice, **on the legacy path only as of INFRA-283 — see below**), then the existing non-empty stamp, then `resolve_current_phase`'s candidate set only when it is unambiguous (more than one candidate errors on the terminal step, warns and stamps `""` on a non-terminal one) — every `record-checkpoint-step` call stamps the precedence-resolved key in the same atomic write that appends the step; the terminal `checkpoint-tag` branch resets it to `""` alongside the `checkpoint_step` reset. **As of INFRA-283 (CER-095.4), this is a derived mirror of `checkpoint_steps` above, not the authority**: once a keyed record exists, the stamp only ever names whichever phase wrote most recently, so a mismatch against a different explicit `--phase-key` is no longer evidence of an operator mistake and the A4 disagreement check (CER-077) is skipped — applying it unconditionally would reject a second phase's perfectly correct concurrent call, the exact bug this story closes | read-only (`next_action.infer_position` reads it only on the legacy path, to decide whether to honour or clear `checkpoint_step`; it never writes `checkpoint_phase`) |
| `docs/phases/index.md` phase status cell | orchestrator, via `flex_build.py record-checkpoint-step checkpoint-tag` (INFRA-239) — the `checkpoint-tag` step's `_mark_phase_complete_in_index` call writes `complete` to the just-tagged phase's row in the same CLI invocation that resets `checkpoint_step`, so the two writes never land in separate orchestrator turns; the standalone `mark-phase-complete` command (`cmd_mark_phase_complete`) shares the same write helper for direct/manual use but is no longer required in the checkpoint path | read-only (`_resolve_active_phase` / `resolve_current_phase` skip `complete`/`deferred`/`backlog` rows when selecting the active phase) |
| active era doc (`docs/eras/NNN-*.md`, `status: active`) `## Phases` ledger status cell | orchestrator, via `flex_build.py mark-phase-complete` / `record-checkpoint-step checkpoint-tag` (INFRA-267, CER-082) — both call `_mark_phase_complete_in_era_ledger` with the *same* phase key already passed to `_mark_phase_complete_in_index`, never a second re-derivation, so the ledger row and the index row flip in one invocation; the helper is a silent no-op (returns `False`, writes nothing, raises nothing) when `docs/eras/` is missing, no era doc is `active`, the active doc has no ledger heading/table, no row matches the key, or the row already reads `complete`, and it never edits a non-`active` era doc — a legacy era without a ledger row must not change the exit status of either command. The row itself is created by `phase_new.py` at scaffold time | read-only (`index_integrity` check 2c compares ledger rows against `docs/phases/index.md`; the resolver never reads or writes era docs) |
| active stories (`state.json` `current_stories`, keyed by story ID; INFRA-281/CER-095.2, superseding the single-slot `current_story`) | `story_context.py` — sole writer, via `set_current_story()` / `clear_current_story()`; `create-story-worktree` **adds** its story's key, `merge-story-worktree` / `discard-story-worktree` **remove only their own key**. The flat `current_story` mirror is a **derived** read compatibility shim for readers outside `scope_guard.py`'s scope (`hooks/session_start.py`, `global_session_check`, `skills/observability/api/src/routes/context.ts`, `subagent_transcript._story_accepts_late_bump`) — it is written only inside `set_current_story()`/`clear_current_story()`, never independently | read-only |
| `effort.db` | `hooks/post_tool_use.py` → `subagent_transcript.py` / `effort_recorder.py` (INFRA-236); `record_attempt.py` CLI for non-hook callers | read-only |
| `attempt_counter.json` (attempt counters) | `hooks/post_tool_use.py` → `subagent_transcript.record_attempt_from_transcript` → `flex_build.bump_attempt_count` on builder/reviewer FAIL (INFRA-237), **ungated** — the story was just spawned for, so it is active by construction, and gating it would risk dropping a real first FAIL; `subagent_transcript.reconcile_pending_attempts` → `flex_build.bump_attempt_count` as a *second, later* bump site for an async spawn's FAIL outcome that was only knowable after PostToolUse time (INFRA-258 — same function, same semantics, just a later call), **gated** since CER-091 defect 4 by `subagent_transcript._story_accepts_late_bump` — skipped when the story's own frontmatter `status` is `complete`/`merged`/`deferred`/`backlog`, or when the story is neither already counter-recorded nor `state.json`'s `current_story` (a reconciliation arriving arbitrarily later — possibly post-merge, possibly post-`/clear` — must not resurrect a counter file for a story nobody is building); `flex_build.py merge-story-worktree` → `flex_build.clear_attempt_count` on a successful land; the standalone `write-attempt-count` / `clear-attempt-count` CLI subcommands share the same underlying functions for direct/manual use but are no longer invoked from `CLAUDE.build.md.j2`'s loop | read-only |
| `.companion/effort_recording.log` (diagnostic trace, CER-091) | `subagent_transcript.log_recording_event` — sole writer, called once per `record_attempt_from_transcript` invocation on every return path (including its outer `except`), and once by `hooks/post_tool_use.py`'s `SendMessage` branch (`decision="observed:non-spawn-tool"`); append-only, size-capped at `RECORDING_LOG_MAX_BYTES` (262 144 bytes, truncate-and-restart with a `log-truncated` marker line); not gated on `effort_tracking` — the log's purpose is explaining why recording did or did not happen, including when tracking itself is off | read-only (`pairmode_effort.py` and manual `tail` only; no resolver reads it) |
| story `status` frontmatter | manual/advisory — `story_update.py` is the canonical CLI but no build-loop step calls it automatically; drift is caught after the fact by `flex_build.py check-index`'s git-commit status-drift check (RESOLVER-010), not prevented at write time | read-only |
| permission files (`docs/phases/permissions/<story_id>.json`) | orchestrator (`flex_build.py permissions-create`) | read-only |
| era/phase/story index (`docs/phases/index.md`) | orchestrator | read-only |
| commits + tags | reviewer / orchestrator (via `git`) | read-only |
| `next-action` resolver output | **reads all of the above; writes nothing** | — |

### (c) effort.db ≠ context-control invariant (DP7)

These two token surfaces measure fundamentally different things and must never cross-feed:

- **`effort.db`** = *retrospective cost* recorded by
  `subagent_transcript.record_attempt_from_transcript()` (INFRA-236) — the
  spawning subagent's own token usage: for synchronous spawns, read from its
  sidechain turns in the live session JSONL transcript; for async spawns
  (the current norm), the sidechain path finds nothing at PostToolUse time
  and tokens/outcome arrive via the INFRA-258 deferred reconciliation of the
  spawn's `output_file` transcript (see § Async-spawn effort recording).
  No longer sourced from agent-authored `<usage>`
  blocks (0.3's builder/reviewer `procedure.md` forbids that return format).
  Inputs: model selection, guardrail, rollups, cost display.
  **Never an input to a context-headroom or clear-seam decision.**

- **context-control** = the orchestrator's own *live window occupancy*
  (`context_current_tokens` + the `expected_step_tokens` window-growth constant). This is
  the **sole** basis for headroom / clear-seam decisions.

Rationale: subagent tokens never entered the orchestrator's window, so summing `effort.db`
to estimate headroom counts tokens that were never there. The thin harness widens this gap
further (per-step window growth ≈ return-block size, decoupled from story effort), so the
resolver must compute headroom *only* from context-control state and use `effort.db` *only*
for cost / model display.

### Codified comingling — FLAGGED FOR REMOVAL AT HARNESS006

`CLAUDE.build.md:320-326` compares `threshold − N` (remaining window) against the
`story-cost-estimate` effort.db median (`flex_build.py:834`) and advises `/clear` — exactly
the wrong cross-feed of the effort.db ≠ context-control invariant. The correct mechanism
already exists separately at `CLAUDE.build.md:696-750` (`context_current_tokens +
expected_step_tokens` vs threshold). The redesign at HARNESS006 deletes the comingled
advisory; the resolver/gate reports window occupancy only, and any effort-cost figure shown
is labelled cost (not headroom) and never compared to remaining window.

**This story (RELEASE-004) does NOT remove the comingled advisory at `CLAUDE.build.md:320-326`.
That removal is HARNESS006 scope (the gate rewrite).**

---

## Companion data files

`.companion/product.json` contains a `config` key pointing to an external config file path.
That config file contains `spec_location` — the path to the project's openspec directory.

`spec_reader.read_project_spec(companion_dir)` follows this two-hop path automatically:
1. Read `product.json["config"]` → path to external config file
2. Read `config["spec_location"]` → openspec root directory
3. Glob `<spec_location>/openspec/specs/*/spec.json` → all module specs

Returns `None` if `product.json` is missing or has no `config` key. Returns a dict with
`modules` (list of spec dicts) and `spec_location` (Path) if found.

`.companion/state.json` is written by the companion skill on every session start. Schema:

```json
{
  "pairmode_version": "1.0",
  "last_loaded_modules": ["module-name"],
  "current_stories": {
    "2.3": {
      "id": "2.3",
      "title": "optional title",
      "set_at": "2026-04-20T00:00:00+00:00"
    }
  },
  "current_story": {
    "id": "2.3",
    "title": "optional title",
    "set_at": "2026-04-20T00:00:00+00:00"
  },
  "checkpoint_steps": {
    "109": ["checkpoint-security", "checkpoint-intent"],
    "105": ["checkpoint-security"]
  },
  "checkpoint_step": ["checkpoint-security", "checkpoint-intent"],
  "checkpoint_phase": "109",
  "registered_projects": [
    "/absolute/path/to/project-a",
    "/absolute/path/to/project-b"
  ]
}
```

Fields:
- `pairmode_version` — set by `/flex:pairmode bootstrap`; the methodology version used
  to scaffold the project. Read by `/flex:pairmode audit` to compute the delta.
- `last_loaded_modules` — updated on every companion session start; lists the module names
  the user chose to load for that session.
- `current_stories` — **optional**; dict keyed by story ID (INFRA-281, CER-095.2). Each
  entry has the same shape as `current_story` below (`id`, optional `title`, `set_at`).
  This is the **authority**: with two builders in flight (parallel worktree dispatch),
  `state.json` can legitimately hold more than one active story, and only a keyed record
  can answer "which story is this write for?" per call — a single global slot cannot.
  `create-story-worktree` adds a key on stamp; `merge-story-worktree` /
  `discard-story-worktree` remove **only their own** key on teardown, never the whole
  dict — see § 9.5 for how `scope_guard.resolve_call_story()` consumes this. Absent
  when no story has ever been stamped in this state.json.
- `current_story` — **optional**; a **derived mirror** of one `current_stories` entry
  (whichever was written most recently, or re-pointed deterministically on a scoped
  clear — see `story_context.clear_current_story()`), kept only for backward
  compatibility with readers outside `scope_guard.py`'s scope: `hooks/session_start.py`,
  `global_session_check`, `skills/observability/api/src/routes/context.ts`, and
  `subagent_transcript._story_accepts_late_bump`. It is never written independently of
  `current_stories` — `set_current_story()` and `clear_current_story()` write both in
  the same atomic write, so the mirror can never diverge from the keyed record through a
  partial write. Present only when pairmode is active and the user confirmed which story
  they are working on (or a builder stamped one). Contains `id` (required), optional
  `title`, and `set_at` (UTC ISO-8601 timestamp). Absent when the user skips the prompt
  and no `current_stories` entry exists.
- `checkpoint_steps` — **optional**; dict keyed by phase key (INFRA-283, CER-095.4). Each
  entry is the list of completed checkpoint step IDs for that phase. This is the
  **authority**: with two phases checkpointing concurrently under one orchestrator, only
  a keyed record can answer "which phase is this step for?" per call — a single global
  slot cannot. Written only by `flex_build.py record-checkpoint-step`; `checkpoint-tag`
  removes only its own key on completion, never the whole dict. Absent when no phase has
  ever completed a checkpoint step in this state.json, or once the last in-flight phase's
  entry is popped by its own `checkpoint-tag`.
- `checkpoint_step` / `checkpoint_phase` — **optional**; as of INFRA-283, these are a
  **derived mirror** of one `checkpoint_steps` entry, written only by
  `record-checkpoint-step` on every call and never read by it to decide what to append.
  They exist for readers outside this fix's scope
  (`skills/observability/api/src/readers/resolverState.ts`,
  `skills/observability/ui/src/api/client.ts`), which still expect one flat list and one
  stamp. `checkpoint_step` is a `list[str]` of completed step IDs; `checkpoint_phase` is
  the phase key that list belongs to, or `""` when no single phase can be named
  unambiguously (see the architecture § Checkpoint prose above for the exact mirror rule).
- `context_story_tokens` — **optional**; dict keyed by story ID (e.g. `"INFRA-181"`);
  written by `flex_build.py set-context-tokens`. **Legacy after INFRA-182**: `decide()` no
  longer reads this field. Entries remain in state.json but are inert for gate enforcement.
  The per-story dict design was introduced by INFRA-180 and superseded by INFRA-182.
- `context_session_reset_at` — **optional**; UTC ISO-8601 timestamp string; written by
  `session_start.py` on `clear`/`startup`/`compact` (INFRA-245) via
  `session_reset.decide_reset()`. Used by
  `_is_stale()` in `context_budget.py` to detect whether
  `context_current_tokens_recorded_at` predates the last session reset; if so, `decide()`
  blocks with CONTEXT CHECK REQUIRED. Equal timestamps are treated as fresh (the
  SessionStart baseline sets both to the same value). INFRA-182.
- `context_current_tokens` — **optional**; integer; the live context window token count.
  Primary writer: `hooks/post_tool_use.py` (Task/Agent PostToolUse branch) via
  `context_budget.read_current_tokens()` after each completed spawn (INFRA-182).
  Also written by `flex_build.py set-context-tokens` as a manual override / debugging
  escape hatch; by the SessionStart hook reset on `clear`/`startup`; and seeded to `1`
  by `bootstrap.py::_record_state()` on new state creation (Phase 67 INFRA-174).
  Read by `context_budget.decide()` as the sole token source. Not written by the
  companion sidebar.
  **INFRA-251 writer-liveness root cause, fixed:** `context_budget.compute_context_tokens()`
  (the bounded reverse-scan the writer calls) did not filter on the transcript's
  `isSidechain` field. `PostToolUse` fires immediately after a `Task`/`Agent` tool call
  completes — i.e. immediately after the spawned subagent's own turns were appended to the
  *same* session JSONL as `isSidechain: true` entries, and before the orchestrator emits its
  own next turn. An un-filtered reverse scan therefore matched the subagent's own last
  `usage` block (its disposable context, unrelated to the orchestrator's window — see §
  effort.db ≠ context-control invariant, DP7, and `subagent_transcript.py`'s sibling
  `isSidechain: true`-only scan for the correct converse) instead of the orchestrator's own
  growth, reproducing the "writer dead in-session" symptom (frozen/wrong counter across
  repeated spawns). Fixed: `compute_context_tokens()` now skips `isSidechain: true` entries
  and finds the last **non-sidechain** assistant turn — the orchestrator's own last known
  value, correctly lagging by at most one hook-fire rather than silently substituting a
  subagent's number. Regression tests:
  `test_context_budget.py::test_compute_context_tokens_skips_trailing_sidechain_entry`,
  `test_context_budget.py::test_compute_context_tokens_skips_multiple_trailing_sidechain_entries`,
  `test_context_budget.py::test_compute_context_tokens_uses_own_turn_when_it_is_last`.
- `context_current_tokens_recorded_at` — **optional**; UTC ISO-8601 timestamp string;
  written alongside `context_current_tokens` by `post_tool_use.py` (Task/Agent branch),
  `flex_build.py set-context-tokens`, and `session_start.py` (SessionStart reset).
  Used by `_is_stale()` to detect whether the recorded count predates the last
  `context_session_reset_at`. INFRA-182.
- `context_current_tokens_ttl_minutes` — **optional**; integer; legacy field from the
  scalar TTL-based staleness check. No longer used after INFRA-182 replaced TTL-based
  staleness with `context_session_reset_at` comparison. Safe to leave in state.json.
- `expected_step_tokens` — **optional**; positive integer; the per-step context-growth
  constant `decide()` passes as `estimate_next_step_tokens()`'s `seeded_default` (the ceiling
  arithmetic is `context_current_tokens + expected_step_tokens > threshold * (1 +
  overrun_pct)`). **INFRA-251 decision — deliberately a static default, not derived from
  effort.db:** CER-053 and § effort.db ≠ context-control invariant (DP7) forbid deriving this
  window-growth constant from `effort.db` (a subagent's own retrospective cost must never
  feed an orchestrator context-headroom decision) — so `estimate_next_step_tokens()`'s
  three-tier effort.db waterfall (per-phase median / global median / seeded default) is
  permanently unreached from `decide()`, which always calls it with `db_path=None`; this is
  by design, not a dead recompute path to be revived. The maintained default is
  `context_model.THIN_HARNESS_STEP_TOKENS` (currently `5000`); `decide()` uses
  `state["expected_step_tokens"]` when present (a legitimate, intentional per-project
  override — see `bootstrap.py::_load_seed_expected_step_tokens()` and
  `sync.py`, both of which seed new/synced projects with the constant) and falls back to the
  constant when absent.
  **Era-2 fossil, correction path (not a decide()-time code change):** every fleet project's
  state.json was seeded weeks ago with a static `53000` (a rounded historical
  builder-attempt median from the pre-thin-harness design) that no writer has refreshed
  since — `pairmode_migrate.py`'s `to-030 --apply` subcommand already diagnoses and corrects
  this (`ERA2_STAMP = 53000` → `THIN_HARNESS_STEP_TOKENS`, its "B6" step, tested by
  `test_pairmode_migrate.py`), preserving any other explicit value as a deliberate custom
  override (`[WARN] custom expected_step_tokens=... value kept`). `decide()` intentionally
  does **not** special-case the literal `53000` at read time —
  `test_expected_step_tokens_source.py::test_context_budget_fallback_not_53000` asserts that
  literal never appears in `context_budget.py`, and several existing `decide()` tests
  legitimately seed `expected_step_tokens=53_000` as an honored per-project value — so the
  correction is applied once, at the state.json layer, via the migration tool, not
  re-derived on every `decide()` call. flex's own `.companion/state.json` (main checkout) and
  the wider fleet's stamped values are out of this story's/worktree's scope (phase-99
  explicitly excludes fleet projects; flex's own runtime state.json is not a
  `primary_files`/`touches` path for this story) — running `pairmode_migrate.py to-030
  --apply` against them is a separate, already-tooled operator action.
- `context_baseline_tokens` — **optional**; positive integer; operator-tunable per-project
  override for the fresh-session baseline written by the SessionStart `clear`/`startup`
  counter reset (Phase 68 INFRA-175). Read by `session_reset.decide_reset()`; when absent,
  non-numeric, or non-positive, the default `25_000` is used. Opt-in only — not seeded by
  `bootstrap.py`.
- `context_budget_user_turn_seq` — **optional**; integer; monotonic counter incremented by
  `hooks/user_prompt_submit.py` on every `UserPromptSubmit` event (treated as `0` when
  absent). The sole signal that a genuine human turn has occurred since a context-budget
  block. INFRA-192.
- `context_budget_acknowledged_user_turn_seq` — **optional**; integer; the value of
  `context_budget_user_turn_seq` at the moment `hooks/pre_tool_use.py` last wrote a block,
  written alongside `context_budget_acknowledged_at` in the same `write_text()` call.
  `None`/absent is treated as a pre-INFRA-192 upgrade grace period by `should_block()` and
  does not itself force a block. INFRA-193.
  **INFRA-251 era-2 regression, fixed:** the branch of `should_block()` that runs once a
  genuine turn has occurred (`user_turn_seq > acknowledged_user_turn_seq`) returned
  `not token_ok` — the opposite sign of the two branches beside it — so a retry with
  `context_current_tokens` unchanged from `acknowledged_at` (the common case: nothing has
  run between the block and the retry to grow the counter) stayed blocked forever, and
  `hooks/pre_tool_use.py` then re-stamped `context_budget_acknowledged_user_turn_seq` to the
  *current* turn-seq on that spurious re-block — discarding the operator turn that should
  have cleared it, so "Say: Continue building" in the block message could never actually
  succeed. This predates the RELEASE-059 fold and is believed to be a weeks-old, fleet-wide
  regression, never revisited while 0.3 harness work moved (era-2). Fixed by aligning the
  sign: `should_block()` now blocks iff genuine token growth (`current_tokens >=
  acknowledged_at + reprompt_margin`) has occurred since the acknowledgment, in every branch
  — a bare turn with no growth clears the gate (INFRA-251 Ensures #1); real growth still
  re-blocks (Ensures #2, the original INFRA-193 intent, now actually reachable).
  `hooks/pre_tool_use.py`'s unconditional re-stamp on every block is unchanged and remains
  correct post-fix: a *genuine* re-block (real growth past the margin) legitimately starts a
  fresh acknowledgment cycle at the new token level/turn. Regression tests:
  `test_context_budget.py::test_decide_exact_observed_sequence_block_then_user_turn_then_retry_passes`,
  `test_context_budget.py::test_should_block_suppresses_after_genuine_user_turn`,
  `test_context_budget.py::test_should_block_reblocks_after_genuine_user_turn_when_margin_crossed`,
  `test_pre_tool_use_hook.py::test_retry_after_user_prompt_submit_suppresses`,
  `test_pre_tool_use_hook.py::test_retry_after_user_prompt_submit_reblocks_when_margin_crossed`.
- `context_budget_user_turn_seq_fingerprint` — **optional**; string; sha256 hex digest of
  the identifying fields (`session_id` + `prompt`) of the most recently processed
  `UserPromptSubmit` event, written by `skills/pairmode/scripts/user_turn_seq.py`
  (`record_user_turn()`) in the same `write_text()` call as the
  `context_budget_user_turn_seq` increment it guards. INFRA-248: before every
  increment, `record_user_turn()` compares the incoming event's fingerprint against
  this stored value; a match means the event is a duplicate firing of the
  immediately-preceding `UserPromptSubmit` (e.g. a duplicate hook registration, the
  INFRA-247 scenario) and the increment is skipped. A mismatch (a genuinely new
  prompt) always increments and overwrites this key. Purely a same-event dedup
  signal — it is not consumed by `context_budget.should_block()` or any other
  gate-decision logic.
- `registered_projects` — **optional**; list of absolute paths to pairmode-scaffolded
  projects to include in cross-project drift detection. When present and non-empty,
  `/flex:pairmode review` runs `pairmode_drift_report --convergent` across all listed
  projects and surfaces convergence candidates for promotion to canonical templates.
  Not set by `bootstrap.py` — opt-in only. Each path is validated with `_depth_guard`
  before use (paths with fewer than 3 components are rejected).
  The canonical management path for this list is the `pairmode register` / `unregister` /
  `list-projects` subcommands (INFRA-070); hand-editing `state.json` is discouraged.
  The key is created on first `register` call when absent; it is never written by
  `bootstrap.py`. Each entry is a resolved absolute path string.

`.companion/attempt_counter.json` is an ephemeral single-record file read by
`flex_build.read_attempt_count` (composed by `next_action.infer_position`, RESOLVER-002).
Schema: `{"story_id": "RAIL-NNN", "attempt_count": N}`. It stores the current attempt
number for the active story so a `/clear` mid-phase does not reset the counter — this is
core build-loop control state, not observability, so its writer is independent of the
`effort_tracking` state.json flag (INFRA-237). It is bumped by
`flex_build.bump_attempt_count` (a mismatched `story_id` resets the count to 1 for the
new story), called from `subagent_transcript.record_attempt_from_transcript` — the same
`hooks/post_tool_use.py` Task/Agent delegated call that writes `effort.db` rows
(INFRA-236) — whenever a completed builder or reviewer spawn's own BUILD-RESULT /
REVIEW-RESULT reports `FAIL`. Since INFRA-258, `subagent_transcript.reconcile_pending_attempts`
is a *second* bump site, called both from `record_attempt_from_transcript` itself and
from `hooks/session_start.py`: because agent spawns are now asynchronous, a FAIL outcome
is frequently unknowable until a later PostToolUse event (or the next session's
SessionStart) reads the spawn's own completed output file — the bump still fires the
same way, just later; see § Effort tracking for the full mechanism. It is cleared by
`flex_build.clear_attempt_count`, called
from `flex_build.py merge-story-worktree` on a successful rebase + fast-forward merge
(reviewer PASS that actually lands). The `write-attempt-count` / `clear-attempt-count`
CLI subcommands remain available (and are exercised directly by
`tests/pairmode/test_flex_build_attempt_counter.py`) but are no longer invoked from
`CLAUDE.build.md.j2`'s loop pseudocode — the two call sites above own the writes.
Covered by the `.companion/` `.gitignore` rule — never committed.

Cross-reference (INFRA-257): `effort.db`'s per-row `attempt_number` column is a
*different* number, derived from a different source (`effort_db.next_attempt_number`
counting persisted `attempts` rows) — see § Effort tracking for its definition. The
two numbers are expected to diverge and neither is a "fix" for the other: this
counter resets on merge and counts failures since the last land, while
`attempt_number` never resets and counts lifetime spawns. A future reader should not
assume they must agree.

Pairmode is considered active when `.claude/settings.deny-rationale.json` exists in the
project root. The helper `skills/pairmode/scripts/story_context.py` provides:
- `is_pairmode_active(project_dir)` — returns True when the deny-rationale file is present.
- `set_current_story(companion_dir, story_id, title=None)` — writes the entry into
  `current_stories[story_id]` and the `current_story` mirror (same entry, one atomic
  write; INFRA-281) and returns the updated state dict.
- `get_current_story(companion_dir)` — returns the `current_story` mirror dict or None.
- `get_current_stories(companion_dir)` — returns the `current_stories` keyed dict
  (INFRA-281); derives a single-entry dict from the flat `current_story` when the state
  file predates this key, so a project mid-migration never reads as zero active stories.
- `clear_current_story(companion_dir, story_id=None)` — with `story_id`, removes only
  that entry from `current_stories` and re-points/removes the `current_story` mirror
  deterministically (INFRA-281); with `story_id=None` (the CLI's `--clear`), clears both
  keys entirely — today's "clear the slate" behaviour.
- `read_state(companion_dir)` / `write_state(companion_dir, state)` — low-level helpers.

---

## Hook architecture

**Non-negotiable: hooks are thin relays.**

Hooks must:
- Write a JSON message to `/tmp/companion.pipe`
- Exit in milliseconds
- Never make API calls
- Never write to spec files directly

**Documented exception — `hooks/pre_tool_use.py` (triple thin-delegate):**
`pre_tool_use.py` dispatches to three modules. As of RELEASE-020, the
`Task`/`Agent` branch also makes a fourth, read-only import — `flex_build`
(for `_story_path` / `_read_story_frontmatter`) alongside `scope_guard`
(for `resolve_call_story`, INFRA-281 — the per-call resolver superseding
`_read_current_story` here; ambiguous/ no-signal resolutions both fall back
to the documented `1.0` default rather than guessing) — solely to resolve
`flex_factor` before calling `decide()`; no state is written by this
resolution and no new dispatch branch is added.

- **`Task`/`Agent` → `context_budget.py` (CER-027, CER-039, CER-040, CER-049, INFRA-182, INFRA-199):**
  the dispatch is additionally scoped (INFRA-199) to
  `tool_input.subagent_type` ∈ {`builder`, `reviewer`, `loop-breaker`,
  `security-auditor`, `intent-reviewer`} — the five build-cycle subagent types.
  When `subagent_type` is absent or any other value (general-purpose / Plan /
  Explore / other spawns), the branch falls straight through to `sys.exit(0)`
  with no `context_budget` import/call, no block emission, and no state write.
  For an allowlisted `subagent_type`,
  the hook makes one delegated call: `decide(project_dir)` — reads
  `context_current_tokens` from state.json (written by `post_tool_use.py` after each
  completed Task/Agent spawn, or by the SessionStart baseline); the hook writes
  `context_budget_acknowledged_at` and `context_budget_acknowledged_user_turn_seq`
  (INFRA-193) to state.json in a single `write_text()` call when `result["block"]` is
  True. `decide()` itself is strictly read-only (D11).
  `post_tool_use.py` (PostToolUse Task/Agent branch) is the sole live writer of
  `context_current_tokens`; `set-context-tokens` remains as a manual override.
  Blocks with `CONTEXT CHECK REQUIRED` when `context_current_tokens` is absent or
  stale (recorded_at < context_session_reset_at); when `state.json` is malformed
  (CER-040). Does not write to the pipe. Accepts both `Task` (legacy) and `Agent`
  (current harness) — see CER-049.
- **`Edit`/`Write` → `scope_guard.py` (Phase 55):** decides whether to block
  a file write based on the active story's declared `primary_files`/`touches`.
  Read-only; no state writes. Fails open when state or permissions file absent.
- **`Read` → `cold_read_guard.py` (INFRA-196):** blocks a top-level orchestrator
  Read (`agent_type` absent from the payload) targeting `docs/stories/**` or
  `.claude/agents/**`, directing the orchestrator to pass the story ID to a
  builder/reviewer subagent instead of reading it cold. Read-only; no state
  writes. `docs/phases/**` and `docs/architecture.md` reads are never blocked.

As of INFRA-205 (`hooks/hooks.json`) and INFRA-206 (`bootstrap.py`'s downstream
registrar), all three dispatch branches above are actually reachable — prior to
Phase 93 (CER-065), the `Edit`/`Write` and `Read` branches were registered
nowhere in the `PreToolUse` matcher and were dead code in every project using
this plugin, including flex itself. As of INFRA-208, the downstream registrar
(`bootstrap.py` / `sync.py`) also wires the three load-bearing context-budget-
gate hooks — `UserPromptSubmit`, `SessionStart`, and `PostToolUse` `Task|Agent`
— into downstream `.claude/settings.json`, using the same by-command
find/migrate idempotency as the `PreToolUse` registrar (CER-067); the four
remaining companion/sidebar blocks (`Stop`, `PermissionRequest`/
`ExitPlanMode`, `PostToolUse` `Write|Edit|MultiEdit`, `SessionEnd`) remain
opt-in. Phase 95 (INFRA-208/INFRA-209) shipped this registrar generalization
and verified the fleet rollout — 13 of 14 in-scope projects already carried
the three registrations by the time INFRA-209 ran (no commits needed); `cora`
is formally excluded as a known carve-out, `anchor` remains excluded as a
non-pairmode-consumer sibling plugin repo. Phase 95's INFRA-222 additionally
fixed an escaped-pipe parsing bug in `next_action.py`'s checkpoint guard
(`_check_phase_completion`), a CER-066 recurrence.

As of INFRA-208, the downstream registrar (`_register_context_budget_hooks`,
invoked from both `bootstrap.py` and `sync.py` alongside
`_register_pretooluse_hook`) also wires the three load-bearing context-budget-
gate hooks — `UserPromptSubmit` (`user_prompt_submit.py`, INFRA-192),
`SessionStart` (`session_start.py`, INFRA-175), and `PostToolUse` matcher
`Task|Agent` (`post_tool_use.py`, INFRA-182) — into downstream
`.claude/settings.json`. Without these three, the `PreToolUse` context-budget
gate read state that nothing downstream ever produced or advanced (CER-067).
The four remaining companion/sidebar blocks (`Stop`, `PermissionRequest`/
`ExitPlanMode`, `PostToolUse` matcher `Write|Edit|MultiEdit`, `SessionEnd`)
remain opt-in and are not registered by this path.

**Dedupe-on-write (CER-081, INFRA-269):** both registrars are dedupe-on-write —
at most one inner hook entry per (event, command-basename) pair survives a
registrar run. Prior to INFRA-269, `_register_pretooluse_hook` and
`_register_context_budget_hooks` located their target block by an exact-command
scan, falling back to `_find_block_by_command_basename`'s in-place migration
only when the exact-command scan found nothing. That fallback was therefore
unreachable once a project already carried *both* a stale (e.g.
`/mnt/work/flex`-pointing) entry and a correct (`plugin_root`-pointing) entry
for the same hook file — the exact match short-circuited before the basename
fallback ever ran, so the stale sibling was never removed and both commands
executed independently on every event (Claude Code does not dedupe hooks
itself). INFRA-269 closes this by adding `_prune_stale_hook_entries`, called
after each registrar's find/migrate/append logic resolves the correct entry:
it removes every stale same-basename entry whose command is not the correct
one, and removes any block left with an empty `hooks` list. Placing the prune
after the correct entry is guaranteed present means a prune run can never
leave an event with zero flex hooks. `_find_block_by_command_basename`'s
"first match" in-place migration behaviour (still used when no correct entry
exists yet) is unchanged.

Two further instruments cover state this write-time fix cannot reach
retroactively: `pairmode_sync.py audit-hooks` is the retroactive cleaner and
periodic drift check for `.claude/settings.json` files that already carry
duplicate registrations from a pre-INFRA-269 registrar run — dry-run by
default (exits 1 if duplicates are found, 0 if clean), `--apply` removes them
using the same `_prune_stale_hook_entries` helper. `fleet_discovery.py`'s
`discover()` result gains a `duplicate_hooks` field (populated by
`_check_duplicate_hooks`, read-only with respect to scanned projects) as the
DP8 fleet-level signal that surfaces the condition before the fold; discovery
reports the condition, it does not enforce against it — `audit-hooks` is the
enforcing instrument.

All decision logic lives in the named modules; the hook is a thin dispatcher.

**Documented exception — `hooks/post_tool_use.py` Task/Agent branch (INFRA-182, INFRA-236):**
In addition to the file-change relay role, `post_tool_use.py` handles Task/Agent
PostToolUse events with two independently try/excepted delegated calls:

- Calls `context_budget.read_current_tokens(project_dir, session_id)` to read the live
  token count from the JSONL transcript (bounded reverse scan, `isSidechain: true` entries
  skipped — INFRA-251, see `context_current_tokens`'s writer-liveness note above). Writes
  `context_current_tokens` + `context_current_tokens_recorded_at` to state.json.
- Calls `subagent_transcript.record_attempt_from_transcript(project_dir, session_id,
  tool_input, tool_response, tool_use_id)` (INFRA-236) to read the spawn's own usage
  from its sidechain turns in the same transcript (synchronous spawns only — an async
  spawn's tool_response is launch metadata, so its row is recorded with NULL
  tokens/outcome plus `agent_id`/`output_file` spawn refs and backfilled later by the
  INFRA-258 reconciliation sweep, which also runs from this same call site), plus
  `tool_input`/`tool_response`/`state.json` for role/story/model/outcome. Writes one
  `attempts` row to `.companion/effort.db` via `effort_recorder.record_effort()` when
  the spawn is a recordable build-cycle role and `effort_tracking` is `true`. This is a
  distinct metric and a distinct store from the first call — see § effort.db ≠
  context-control invariant (DP7) — and must never be merged with it.
- Never blocks (no `decision: block` output). Exits silently on any failure in either call.

This write/read split means PreToolUse never reads JSONL directly — it reads only the
state.json value written by the most recent PostToolUse invocation or the SessionStart
baseline.

**Documented exception — `hooks/session_start.py` (CER-047 / Phase 68 INFRA-175;
extended INFRA-258):** `session_start.py` makes two bounded delegated calls: the
counter-reset dispatch below, and a best-effort
`subagent_transcript.reconcile_pending_attempts()` catch-up (INFRA-258) that backfills
tokens/outcome for async-spawn effort rows left unreconciled by a prior session —
bounded (RECONCILE_MAX_ROWS/LINES), wrapped in its own try/except, and unable to
affect the reset decision or exit status. The reset dispatch:

- **`source` ∈ {`clear`, `startup`} → `session_reset.py`:** resets the live context
  counter to a fresh-session baseline (`state["context_baseline_tokens"]` if set,
  else `25_000`). The hook writes `context_current_tokens`,
  `context_current_tokens_recorded_at`, and `context_session_reset_at` to state.json
  when `decide_reset()` returns a dict with `should_reset=True`; all decision logic
  lives in `session_reset.py`. (INFRA-180 changed the return type from `int | None`
  to `dict | None`.) Returns `None` for `resume` (the same window is restored — the
  stored counter is still correct, no reset needed).
- **`source == "compact"` → `session_reset.py` (INFRA-245):** also resets, to a
  separate post-compact baseline (`state["context_compact_baseline_tokens"]` if set,
  else `COMPACT_BASELINE_TOKENS` = `45_000`). Originally excluded (CER-047 — a stale
  counter over-blocks, which is fail-safe, so leaving it stale was a defensible
  no-op). Revisited at INFRA-245 because INFRA-241 (same phase) reconnects the
  PreToolUse gate to real build-cycle spawns: once that lands, a stale-high
  pre-compact count blocks exactly the spawn class whose completion would refresh
  it — a live deadlock, not just occasional over-caution. The baseline is a
  documented constant, not a transcript re-derivation: `decide_reset()` may not
  perform filesystem I/O (D11), and re-deriving the true post-compact count would
  require scanning the JSONL transcript for the first assistant `usage` entry after
  the `compact_boundary` marker — a change to the transcript-parsing surface this
  phase reserves for INFRA-241's drift-canary test alone. `45_000` is set above a
  directly-observed post-compact figure (~39k, dropped from ~166k pre-compact) so
  the fallback stays fail-safe (conservative/high) rather than risking under-block.

**Documented exception — `hooks/user_prompt_submit.py` (INFRA-192, INFRA-248):**
`user_prompt_submit.py` is a thin dispatcher for the `UserPromptSubmit` event —
as of INFRA-248 it performs no state.json I/O or decision logic itself; the
entire read-modify-write, including the idempotency guard, lives in
`skills/pairmode/scripts/user_turn_seq.py`:

- Every event → one delegated call, `user_turn_seq.record_user_turn(project_dir,
  data)`. That function computes a sha256 fingerprint of the event's
  `session_id` + `prompt`, compares it against the stored
  `context_budget_user_turn_seq_fingerprint`, and — unless the fingerprint
  matches the immediately-preceding event (a duplicate firing, e.g. a
  duplicate hook registration; INFRA-248) — increments
  `context_budget_user_turn_seq` and stores the new fingerprint, in a single
  `write_text()` call. No decision logic, no block/reason emission. This
  counter is the sole source of the human-turn signal consumed by
  `context_budget.should_block()` (INFRA-193).
- INFRA-248 audit finding: prior to INFRA-247's dedupe of the duplicate
  `UserPromptSubmit` registration (`hooks/hooks.json` + `.claude/settings.json`),
  every prompt fired this hook twice, unconditionally double-incrementing
  `context_budget_user_turn_seq`. This was confirmed as real corruption of
  that counter's absolute value, but it had **no functional effect** on
  `context_budget.should_block()` (`skills/pairmode/scripts/context_budget.py`),
  because that function compares `user_turn_seq` and
  `acknowledged_user_turn_seq` *ordinally* only (`<=` / `>`), never by
  magnitude — and both sides of the comparison were written from the same
  doubled counter, so the doubling was a uniform scale factor that left every
  ordinal comparison, past and future, unchanged. No `state.json` value
  correction was applied for this reason (see
  `docs/stories/INFRA/INFRA-248.md` Build notes for the full write-up); the
  fingerprint guard added here exists purely so a *future* duplicate
  registration degrades to inert noise instead of relying on this
  no-functional-effect property holding again by chance.

**Canonical hook-registration surface for flex itself (INFRA-247):**
flex registers its own pairmode hooks through exactly **one** active
mechanism: the plugin manifest, `hooks/hooks.json`. `.claude/settings.json`
no longer duplicates any pairmode hook registration; as of this story it
retains only the pytest-on-`.py`-edit `PostToolUse` hook (a project-local
dev-loop convenience hook, unrelated to pairmode) and the `permissions`
block.

Prior to this story, flex ran every pairmode hook **twice** per session:
once via `hooks/hooks.json` (registered whenever flex is enabled as a
plugin — true for every session in this repo, since flex dogfoods itself)
and once via a `.claude/settings.json` block that INFRA-233 added while the
working copy briefly lived at `/mnt/work/flex-harness` on the `fold-prep`
branch. RELEASE-059's fold brought that settings.json block into
`/mnt/work/flex` main verbatim, so it kept invoking
`uv run python /mnt/work/flex-harness/hooks/<name>.py` — a hardcoded sibling
absolute path into a *different checkout*, byte-identical to flex's own
hooks only by coincidence and with no mechanism keeping it so. This doubled
every SessionStart banner, PreToolUse/PostToolUse Task|Agent gate, and
UserPromptSubmit counter increment (the counter-doubling was audited
separately at INFRA-248 and found to have no functional effect on
`context_budget.should_block()`'s ordinal comparison, but was still real
corruption of the stored counter's absolute value).

Decision: the plugin manifest (`hooks/hooks.json`) is canonical for flex
itself, not `.claude/settings.json`. Rationale:
- `hooks/hooks.json` already fires reliably for every session in this repo
  — flex is always developed against itself as an installed/enabled plugin
  — so "the manifest might not fire" is not a real risk here (contrast with
  a downstream fleet project, which may not have flex installed as a
  plugin at all; that's why `bootstrap.py`/`sync.py` still write a
  settings.json block for *those* projects).
- `hooks/hooks.json` resolves every command through
  `${CLAUDE_PLUGIN_ROOT}`, never a hardcoded path, so it carries none of
  the cross-checkout drift risk that produced this defect.
- `hooks/hooks.json` already covers every hook the INFRA-233 dogfooding
  intent requires — `UserPromptSubmit` (`user_prompt_submit.py`),
  `SessionStart` (`session_start.py`), and the `PreToolUse`/`PostToolUse`
  `Task|Agent` context-budget gates (`pre_tool_use.py`,
  `post_tool_use.py`) — so retiring the settings.json copies drops no
  dogfooded coverage.
- Keeping a second, independently-maintained copy of the same
  registrations in two files is itself the defect class (this story); the
  fix is one canonical surface, not better deduplication logic across two
  live surfaces.

The remaining two registered hooks — `stop.py` and `session_end.py` — are plain pipe relays with no dispatch logic and no state.json writes. They do not require thin-delegation exception documentation.

The sidebar does all heavy work asynchronously. If the sidebar is not running, the pipe write
silently fails and the session continues normally — no data is lost because the session
transcript is always available for later mining.
See `docs/pipe-architecture.md` for the project-scoped pipe design, its backwards-compatibility guarantee, and what changed relative to the original single-pipe design.

**Protected-file classification** belongs in the sidebar, not in the hook.
The sidebar loads `.claude/settings.deny-rationale.json` lazily on first use (cached
per `cwd` for the lifetime of the sidebar process) and calls `_check_protected()` when
processing each `file_changed` event. The hook emits only `path` and `tool` — no
deny-rationale reads occur in the hook.

`spec_exception` pipe messages are produced by the sidebar's override prompt (when a developer provides a reason for overriding a protected file) and handled by the sidebar's pipe reader to write conflict records to the module's `spec.json`. The pipe message payload fields used by the handler: `type` (`"spec_exception"`), `path` (overridden file path), `non_negotiable` (the rule violated), `override_reason` (developer-supplied justification), `session_id` (Claude Code session identifier).

---

## Effort tracking

Effort tracking is the per-attempt record of how much compute each builder and
reviewer spawn consumed. It exists to make the cost of the build loop legible
without coupling that legibility to a specific pricing regime.

**Data model.** A single SQLite database lives at `.companion/effort.db` with
one `attempts` table. Each row captures one agent spawn: `story_id`, `phase`,
`rail`, `agent_role` (`builder` or `reviewer`), `model`, `attempt_number` —
the **lifetime spawn ordinal for a `(story_id, agent_role)` pair**, derived
at record time by `effort_db.next_attempt_number` from the count of existing
rows already recorded for that pair (INFRA-257) — `tokens_total`,
`tool_uses`, `duration_ms`, optional `outcome` (`PASS`/`FAIL`
for reviewer attempts), optional `backend` (`"anthropic"` or `"ollama"` —
populated by sidebar cross-skill recording; NULL for pairmode loop rows from
older builds), and a UTC timestamp. Pricing is intentionally absent
from the schema: dollar projections are computed at read time from a
user-maintained `pricing.json`, never persisted.

**Tokens as the primary metric.** Tokens are the unit of compute effort the
build loop actually spends. Dollars are an ephemeral projection through the
current pricing table; if a model's price changes tomorrow, the historical
record must not silently revalue past attempts. Recording tokens (and the model
that consumed them) keeps the historical record stable and lets cost analysis
re-run against any pricing snapshot the user chooses.

**`record_attempt.py --story-file` (recommended invocation for builder calls).** Pass
`--story-file docs/stories/RAIL/RAIL-NNN.md` to auto-fill `--story-id`, `--phase`,
`--rail`, and `--story-class` from the story file's YAML frontmatter. Explicitly-passed
flags still take precedence over auto-filled values. This eliminates the manual
transcription of phase/rail/story-class literals from the story file, closing the typo
surface that CER-015 identified. When `--story-file` is used and the frontmatter has no
`story_class` field, `story_class` defaults to `"code"` (consistent with the rest of the
toolchain). A missing or unparseable story file exits non-zero with a clear error.

**Enabling and disabling.** A one-line toggle in `.companion/state.json`:

```json
{ "effort_tracking": true }
```

Bootstrap auto-enables this for pairmode projects. `record_attempt.py` reads
the flag on every invocation and silently no-ops when it is absent or false,
so the orchestrator's recording steps are safe to run unconditionally.

**What it captures (Phase 22 scope).** Every builder spawn and every reviewer
spawn the orchestrator initiates during the build loop. Future phases will
extend the capture surface to seed and companion sessions; the schema and
toggle are designed to absorb that without migration.

**Cross-skill recording.** Seed and companion record their own LLM-call
effort via in-process wrappers (not orchestrator tool calls), since both
skills set `disable-model-invocation: true` and cannot be invoked as
subagents from the build orchestrator. The wrappers live inside each
skill's Python code (`mine_sessions.py`, `reconcile.py`, `sidebar.py`) and
call the same `effort_recorder` helper as `record_attempt.py`. Synthetic
`story_id` values (`seed:<session-id>`, `seed:reconcile`,
`sidebar:<story-id-or-no-story>`) distinguish cross-skill rows from
pairmode loop rows. `agent_role` values used by these wrappers:
`seed-miner`, `seed-reconcile`, `sidebar-extractor`. `phase` and `rail`
are left NULL for cross-skill rows because seed and sidebar work happens
outside the phases/rails model. The `backend` column (`"anthropic"` or
`"ollama"`) distinguishes the call path on sidebar rows.

**How to use it.** `pairmode_effort.py` provides six read-time views over the
recorded attempts:

- `pairmode_effort.py rollup` — totals by phase, rail, model
- `pairmode_effort.py rework` — stories/roles with `attempt_number > 1` (spawned
  more than once in total for that pair, including post-completion re-runs —
  NOT necessarily "this story failed review"; see the `attempt_number`
  derivation note below)
- `pairmode_effort.py expensive` — top N attempts by tokens
- `pairmode_effort.py models` — breakdown by model
- `pairmode_effort.py validate-rebalance` — evidence report for the
  sonnet-baseline-opus-on-demand methodology; see below.
- `pairmode_effort.py pending` — read-only diagnostic view (CER-091) over
  every row `pending_reconcilable` would still return, with an added
  `reason` column (`classify_pending_reason`) and `age_hours` per row. Opens
  the db via SQLite's `mode=ro` URI rather than `_connect_or_none`'s
  read-write connection, so an invocation is guaranteed to leave the db file
  byte-identical — the repair path is the separate `reconcile` sweep CLI
  below, never this view.

These are retrospective views. Future phases will add a real-time guardrail
that surfaces effort overruns mid-loop rather than only after the fact.

**`validate-rebalance` recommendation logic.** For each
`(story_class, agent_role, model)` cell in the DB the report computes:
sample size, PASS count, PASS rate, and median tokens. It then applies
this decision table (thresholds configurable via CLI flags or
`state["effort_validation_thresholds"]`):

| condition | recommendation |
|-----------|---------------|
| sample size < 5 | "insufficient data" |
| PASS rate ≥ 95 % | "rebalance confirmed for this cell" |
| PASS rate < 80 % | "consider upgrading this cell to opus" |
| sonnet PASS rate ≥ opus PASS rate AND sonnet median tokens < opus median | "consider further downgrade" |
| otherwise | "monitor — insufficient evidence" |

Configurable threshold keys under `state["effort_validation_thresholds"]`:
`min_sample` (int, default 5), `pass_rate_confirmed` (float 0–1, default 0.95),
`pass_rate_upgrade` (float 0–1, default 0.80), `token_ratio_limit` (float,
default 1.5).

**Decision-quality section (requires INFRA-050 data).** A second section of the
`validate-rebalance` report surfaces model-selection decision quality. For each
`model_selection_reason` value (`auto-downgrade`, `auto-baseline`,
`prompted-upgrade`, `user-override`) the report shows: frequency count and
percentage of total stories, PASS-on-first-attempt rate per path, average cost
per path (tokens × pricing), and an efficiency ratio defined as:

```
efficiency_ratio = (pass_rate / avg_cost) / (baseline_pass_rate / baseline_avg_cost)
```

where the `auto-baseline` path is the normalisation reference (ratio = 1.0).
A ratio > 1.0 means the path delivers more PASS-rate per dollar than the baseline.
The section is omitted when the `model_selection_reason` column is absent from
the DB (pre-INFRA-050 builds). The report surfaces evidence only — it does NOT
auto-update model selection. Methodology changes still require story specs.

**Real-time guardrail.** After each builder attempt, the orchestrator calls
`effort_db.check_guardrail()` with the rail and the just-completed attempt's
token count. The function queries the rail's median tokens-per-attempt across
recent PASS-outcome builder rows and compares the latest attempt against
`multiplier × median`. If the latest attempt exceeds that threshold, the
orchestrator surfaces a structured stderr warning before spawning the reviewer.
The guardrail is informational (exit 0), not blocking — the orchestrator
decides whether to pause and consult the user based on the warning text. The
default multiplier is `3.0`, configurable via
`state["effort_guardrail_multiplier"]`. Insufficient sample (< 3 PASS-outcome
builder rows for the rail within the lookback window) returns early without
firing, so new rails do not generate false positives.

**`checkpoint-report` phase scoping (INFRA-256).** `flex_build.py
checkpoint-report`'s `=== checkpoint cost rollup ===` step originally reused
`_query_effort_by_role` verbatim — the same lifetime, no-predicate query
`resolver-state`'s `effort_by_role` payload uses. That made the checkpoint
report db-lifetime-scoped while its heading claimed to answer "what did
*this phase* cost?" (an operator caught this at cp-100: the report read
`builder: 19 attempt(s)` for a phase whose three stories each took one
builder attempt — 19 was the lifetime count across every phase ever
recorded). `checkpoint-report` now derives the active phase's story IDs from
the phase doc's `## Stories` table (`_parse_phase_stories_with_status` — the
same phase-membership list the checkpoint gates already reason over) and
filters `attempts.story_id` against that list via
`_query_effort_by_story_ids`, printing a phase-scoped section first, then
the unchanged lifetime rollup underneath for historical context. Scoping is
keyed off `story_id` membership rather than either alternative that looks
simpler on the surface:
- **Not `attempts.phase`** — that column is nullable and unreliable in
  practice: cross-skill rows (seed, sidebar) leave it NULL by design (see
  "Cross-skill recording" above), and `record_attempt.py` only auto-fills it
  when invoked with `--story-file`. A phase filter keyed on this column would
  silently under-count any attempt recorded through a path that didn't pass
  `--story-file`.
- **Not a timestamp window** — a phase has no fixed start/end timestamp in
  the data model, and any window would mis-attribute an attempt run across a
  phase boundary, or one replayed later against an already-tagged phase.
Deriving membership from the phase doc's own `## Stories` table makes the
rollup exactly as correct as the phase manifest itself, with no separate
source of truth to drift out of sync. `resolver-state`'s `effort_by_role`
deliberately keeps the old lifetime-only behavior — it is a shipped read
contract for the observability SPA's cross-phase role-effort panel
(`skills/observability/api/src/readers/resolverState.ts`,
`skills/observability/ui/src/components/ContextMetrics.tsx`), whose purpose
is the whole-history view; only `checkpoint-report` is phase-scoped. Counts
printed by both sections are row counts (spawns), not `attempt_number`
values — `attempt_number` correctness for repeated same-story spawns is
INFRA-257's concern, not this scoping rule's.

**`attempt_number` derivation (INFRA-257).** Every `attempts` row written by
the pairmode build loop's hook-side recorder
(`subagent_transcript.record_attempt_from_transcript`, the sole per-attempt
writer since INFRA-236/237) used to carry `attempt_number = 1` regardless of
how many times the same story had been spawned, because the hook's
`record_effort(...)` call never passed an explicit `attempt_number` and
`effort_recorder.record_effort`'s signature defaults it to `1`. INFRA-257
fixes this by deriving the value at the hook call site — after the
`effort_tracking` early return, so a project with effort recording disabled
does zero additional db work — via `effort_db.next_attempt_number(path,
story_id, agent_role)`: `SELECT COUNT(*) FROM attempts WHERE story_id = ? AND
agent_role = ?`, plus one. This was chosen over
`.companion/attempt_counter.json` (the escalation ladder's own retry signal,
read by `flex_build.read_attempt_count`) for three reasons: (1) that counter
counts *failures*, not spawns — it is `0` until the first FAIL, so `counter +
1` would stamp `1` on both a first spawn and a second spawn following a
PASS-but-re-run, the exact ambiguity this story removes; (2) it is cleared on
a successful merge (`flex_build.clear_attempt_count`), so a later re-run of
an already-landed story would silently restart at `1` — a discontinuity the
operator explicitly ruled out; (3) it is a single-slot, single-story file
with no per-role dimension, while `attempt_number` must maintain independent
sequences per `(story_id, agent_role)` pair across all five
`RECORDABLE_SUBAGENT_ROLES`. The two numbers are therefore deliberately
divergent by design, not a bug to reconcile: the escalation ladder's
effective-attempt count resets on merge and measures "failures since the
last land"; `attempt_number` never resets and measures "spawns ever
recorded" for that pair. `.companion/attempt_counter.json`'s own writers,
readers, and semantics (`read_attempt_count`, `bump_attempt_count`,
`clear_attempt_count`, and `next_action.infer_position`'s escalation ladder)
are entirely unmodified by INFRA-257.

This changes the correct reading of `pairmode_effort.py rework`'s
`MAX(attempt_number) > threshold` predicate: it now means "this story/role
was spawned more than N times in total, including post-completion re-runs",
not "this story failed review N times" — adjusting the view's query or
threshold to match is separate, not-yet-built work.

No backfill is performed: historical rows written before INFRA-257 keep
`attempt_number = 1` permanently, with no migration and no repair
subcommand. Row counts (not `attempt_number` values) remain the correct way
to read historical effort — this is why INFRA-256's checkpoint rollup above
counts rows, not `attempt_number`, and continues to do so unchanged.

**Amended Phase 109 — INFRA-286 (CER-098).** The paragraph above described this
as a read-then-write with no transaction spanning both steps, accepted rather
than fixed because the era's no-nested-spawning invariant was said to keep
only one worker in flight at a time, so the race supposedly could not occur
in practice. That justification is retired: Phase 109's target capability is
parallel story builds under one orchestrator, so the loop is no longer serial
by construction. INFRA-284 (CER-096) closed
the underlying race directly — `effort_db.insert_attempt_derived` now derives
`attempt_number` as `COALESCE(MAX(attempt_number), 0) + 1` inside a single
`BEGIN IMMEDIATE` transaction, so two genuinely concurrent spawns for the same
`(story_id, agent_role)` pair can no longer read the same count and write the
same `attempt_number`. `next_attempt_number` survives unchanged as an
advisory, read-only helper for callers that only need an estimate (e.g.
display), not the derivation the recorder itself now uses.

**Async-spawn recording — deferred reconciliation (INFRA-258).** Agent
spawns are asynchronous in current Claude Code sessions: at PostToolUse time
the Task/Agent `tool_response` is launch metadata only (`isAsync: true`,
`status: "async_launched"`, `agentId`, `outputFile`) — never the completed
result. Two prior assumptions broke as a result: (1) the orchestrator's own
transcript no longer carries the spawned subagent's turns as `isSidechain:
true` entries (`extract_subagent_usage` finds nothing and returns
`_EMPTY_USAGE`), so `tokens_total`/`outcome` were recorded permanently
`NULL`; and (2) INFRA-237's FAIL-triggered `bump_attempt_count` — gated on
`outcome == "FAIL"` — could never fire, since no outcome is knowable at
PostToolUse time, silently disabling the retry/loop-breaker/human-pause
escalation ladder.

Recording is therefore two-phase. **Phase 1 (immediate, at PostToolUse
time):** `record_attempt_from_transcript` writes the row as before —
`tokens_total`/`outcome` are `NULL` for an async spawn, exactly as an
incomplete synchronous read would have been — and additionally extracts the
spawn's own `agent_id`/`output_file` from `tool_response` (handling both the
structured dict shape and the flattened text form) and persists them via
`effort_db.set_spawn_ref`. **Phase 2 (deferred reconciliation):**
`subagent_transcript.reconcile_pending_attempts` fetches up to
`RECONCILE_MAX_ROWS` (5) rows matching `(tokens_total IS NULL OR outcome IS
NULL) AND output_file IS NOT NULL` (`effort_db.pending_reconcilable` —
widened from the original `tokens_total IS NULL` by CER-091 defect 2/3, so a
partially-backfilled row is reachable again rather than permanently invisible
once tokens land) and, for each, reads the spawn's own `output_file` JSONL
directly via `read_completed_spawn` — streamed line-by-line (never
`read_text()`/`readlines()`, capped at `RECONCILE_MAX_LINES` = 20 000 lines)
— and writes the completed ones back via `effort_db.reconcile_attempt`, a
conditional `UPDATE ... WHERE id = ? AND (tokens_total IS NULL OR outcome IS
NULL)` that only ever touches the nine reconcilable columns (`tokens_total`,
`tokens_in`, `tokens_out`, `cache_read_tokens`, `cache_write_tokens`,
`duration_ms`, `outcome`, `notes`, `model`) — never `story_id`, `agent_role`,
`attempt_number`, `phase`, `rail`, or `ts`.

**Atomic tokens+outcome (CER-091 defect 2).** `reconcile_attempt` additionally
requires both `tokens_total` and `outcome` to be present and non-`None` in
the caller's `fields` before it performs any `UPDATE` at all
(`_ATOMIC_RECONCILE_FIELDS`); supplying `tokens_total` alone now returns
`False` and writes nothing. This closes the exact failure mode observed live:
row 344 (`phase:101`, intent-reviewer) committed `tokens_total = 6597` with
`outcome` permanently `NULL`, because `parse_worker_outcome` dropped the
intent-reviewer's honest `ALIGNED` verdict as unrecognised (fixed separately,
below) and the write proceeded anyway. Once both columns are non-`NULL` the
`(tokens_total IS NULL OR outcome IS NULL)` guard excludes the row from every
future `reconcile_attempt` call *and* every future `pending_reconcilable`
scan alike — single-shot on *fully reconciled*, not merely on `tokens_total`,
which is what makes an existing partial row repairable while still making a
double-bump on an already-reconciled row impossible.

**`ALIGNED` and `UNKNOWN` as recorded outcome values (CER-091 defects 2, 3).**
`parse_worker_outcome`'s recognised `REVIEW-RESULT` verdict set
(`RECOGNISED_REVIEW_VERDICTS`) is `{"PASS", "FAIL", "ALIGNED"}`, mirroring
`worker_result.py`'s `REVIEW_RESULT` schema enum — an intent-reviewer's
`ALIGNED` return is a legitimate outcome, not "no outcome yet", and dropping
it is exactly what stranded row 344. Separately, `include_quiescent=True`
retirement (below) writes `outcome = "UNKNOWN"` when a quiescent row's output
file has usable token data but no parseable verdict — `UNKNOWN` is a distinct
value from both, naming "we know this spawn finished producing output but
never got a clean result", never fabricated as `PASS`/`FAIL`/`ALIGNED`. Both
values are write-side only in this story — see `## Out of scope` in
`docs/stories/INFRA/INFRA-264.md`: `pairmode_effort.py models`'s PASS-rate
column and `validate-rebalance`'s recommendation logic still count only
`PASS`, so `ALIGNED`/`UNKNOWN` rows currently read as not-a-pass everywhere
until a follow-on read-side story teaches those queries about the wider
value set.

**Pending-reason classifier (CER-091 defect 3).**
`subagent_transcript.classify_pending_reason(row) -> str` is a pure function
(no writes, no db access — takes an already-fetched row dict) that names
exactly why a `pending_reconcilable` row has not completed, as one of nine
enumerated values: `no-output-file`, `file-missing`, `file-empty`,
`in-flight`, `not-terminated`, `no-usage`, `line-cap`, `no-outcome`, or
`reconcilable` (the next default sweep will complete it). It shares its file
walk with `read_completed_spawn` via a single streaming reader
(`_stream_spawn_output`) rather than a second, independently-written reader
— a second reader diverging from the first is exactly how
`read_completed_spawn`'s six indistinguishable `None` cases became
unattributable in the first place. Surfaced read-only via `pairmode_effort.py
pending` (see "How to use it" above).

**Completion detection.** `read_completed_spawn` treats a spawn as complete
only when the **last parseable** JSONL entry in its output file is `type ==
"assistant"` with `message.stop_reason == "end_turn"`. A last entry of
`stop_reason == "tool_use"`, a truncated/unparseable trailing line with no
earlier `end_turn` terminator, an empty file, a nonexistent path, or a file
with no usage data anywhere in it all yield `None` — an in-flight agent is
never reconciled, and a mid-write/truncated file is treated as still
in-flight rather than misread. `outcome`/`fail_cause` are parsed from the
final assistant text by the same, unmodified `parse_worker_outcome` the
synchronous path already used — the BUILD-RESULT/REVIEW-RESULT grammar
stays single-sourced. `duration_ms` is the millisecond delta between the
first and last parseable entry's `timestamp`, or `None` when either is
absent/unparseable.

**Reconciliation trigger points and their bounds.** Three trigger points now
invoke `reconcile_pending_attempts`, all best-effort where hook-sourced (own
`try/except`, never raise, never block the caller): (1)
`record_attempt_from_transcript` itself, immediately after the
`effort_tracking` early return and before it derives the new spawn's own
`attempt_number` — this is the next Task/Agent PostToolUse event, whenever it
next fires; (2) `hooks/session_start.py`, once per new session — the
earliest opportunity in the *next* session, covering the tail rows of a
session (the last reviewer, or the checkpoint gate workers) that would
otherwise never be swept, since the spawning session may end before another
Task/Agent PostToolUse event occurs; (3) an explicit operator-invoked CLI
(CER-091, live-observed trigger-coverage gap 2026-07-25 — an async builder
spawn's row sat `outcome = NULL` until a manual sweep was run by hand):

```bash
uv run python skills/pairmode/scripts/subagent_transcript.py reconcile \
  --project-dir . [--limit N] [--include-quiescent] [--json]
```

a thin `argparse` (stdlib-only — this module is imported by hooks and must
not gain a `click` dependency) shell over the *same*
`reconcile_pending_attempts` function the two hook call sites use — no
second reconciliation implementation exists in the tree. It lives on
`subagent_transcript.py` rather than `flex_build.py` deliberately: phase
104's `## Ordering` serialises `flex_build.py`-editing stories (INFRA-263,
INFRA-265, INFRA-267) separately from this story's group to avoid worktree
merge conflicts, and `subagent_transcript.py` already owns
`reconcile_pending_attempts` and was already a primary file of this story.
A `SessionEnd` sweep was considered and rejected in INFRA-258 and that
rejection still stands: `SessionEnd` is `async: true` with a 30 s timeout and
is not a guaranteed-to-complete surface, and the explicit CLI now covers the
same "reconcile the tail rows now" need deterministically instead. All three
trigger points are bounded by construction, not by convention: at most
`RECONCILE_MAX_ROWS` (5, overridable via `--limit` on the CLI) rows per
invocation, each output file capped at `RECONCILE_MAX_LINES` (20 000) lines
and never loaded into memory at once, everything gated behind the
`effort_tracking` early return, and neither hook call site is a new hook
registration — `hooks/post_tool_use.py` and `hooks/hooks.json` are
unchanged for these two triggers (the CLI is a third, no-hook path).

**Quiescent-row retirement (CER-091 defect 3, `include_quiescent`).**
`reconcile_pending_attempts` accepts a keyword-only `include_quiescent: bool
= False`; both hook call sites leave it at the default — a row is only ever
force-retired on the explicit operator-invoked sweep above, never
automatically. When `True`, a row whose `classify_pending_reason` is not
`reconcilable`/`in-flight`/`file-missing`/`no-output-file`, whose db row `ts`
is older than `QUIESCENT_AGE_SECONDS` (900s default) **and** whose
`output_file`'s own mtime is older than the same threshold, is reconciled
from whatever usage the file contains, with `outcome = "UNKNOWN"` when no
verdict is parseable and `notes` prefixed `reconciled-quiescent:` naming the
classifier reason. Age is checked twice — the row's own age and the file's
own mtime — because a row can be old while its agent is still actively
writing; reconciling a live agent is exactly what INFRA-258's completion
detection exists to prevent. A quiescent reconciliation never calls
`bump_attempt_count` — `UNKNOWN` is not `FAIL`, and a fabricated escalation
is worse than a missing one. A row with no usage data at all anywhere in its
output file is still skipped even under `include_quiescent` — there is
nothing truthful to write.

**Message-id dedupe (token summation).** A subagent's own JSONL contains
multiple entries per assistant message — streaming snapshots sharing one
`message.id`, with monotonically growing `output_tokens` (observed: message
`msg_011CdMLvCkdcMj13pJQryLmP` appearing three times with `output_tokens` 5,
5, 263 — only the last, 263, is the true total). Naively summing every
`usage` block double-counts. A single module-level helper,
`_sum_deduped_usage`, keys each assistant entry's usage by `message.id`
(last write wins) before summing; entries with no `message.id` are summed
individually under a synthetic unique key. Both the synchronous sidechain
path (`extract_subagent_usage`) and the async output-file path
(`read_completed_spawn`) route through this one helper, so the two report
the same metric under the same rules. **This changes token totals relative
to pre-INFRA-258 rows** — any row recorded before this fix that happened to
hit the streaming-duplicate shape may read higher than a row recorded after
it; no backfill is performed (see below), so a cross-era comparison should
treat this as a known discontinuity, not a regression.

**Checkpoint-worker attribution — the `phase:<phase_key>` synthetic id.**
`next_action.py`'s `checkpoint-security` / `checkpoint-intent` actions spawn
`security-auditor` / `intent-reviewer` (`CHECKPOINT_ROLES`) with `scalar=""`
— they belong to no single story — but their prompts enumerate the phase's
story ids (e.g. "...docs/phases/phase-101.md — stories INFRA-256 ...,
INFRA-257 ..."). The pre-INFRA-258 attribution path
(`_derive_story_id`/`_STORY_ID_RE`) took the first regex match in the
prompt, so an entire phase's checkpoint cost was silently stamped onto
whichever story happened to be named first (observed: effort.db ids
339–340, both `security-auditor`/`intent-reviewer` rows for the cp-101 gate,
stamped `story_id = INFRA-256`). `_derive_attribution` fixes this by routing
`CHECKPOINT_ROLES` through a dedicated branch that **never** consults
`_STORY_ID_RE` or `state.json["current_story"]`: it derives a phase key from
the prompt (the `docs/phases/phase-<key>.md` path pattern first, then a bare
`Phase <key>` mention; `<key>` matches `[A-Za-z0-9][A-Za-z0-9._-]*` with
trailing punctuation stripped, so both `101` and `HARNESS001-main` resolve)
and records `story_id = f"phase:{key}"` with the `phase` column set to
`key` and `rail` left `None`, or `story_id =
f"unattributed:{subagent_type}"` when no phase key is derivable. Because
`phase:`/`unattributed:` ids contain a `:`, `INFRA-256`'s per-story rollup
(`flex_build._query_effort_by_story_ids`, which filters `story_id IN
(<phase's story ids>)`) now correctly excludes checkpoint-worker rows, while
`effort_db.query_by_phase` still finds them via the `phase` column. Every
other role (`builder`, `reviewer`, `loop-breaker`) is unaffected — attribution
for them is exactly the pre-INFRA-258 `_derive_story_id` behaviour: prompt
story-id regex, then `state.json["current_story"]`, then
`unattributed:<role>`. This split is deliberately asymmetric with
`RECORDABLE_SUBAGENT_ROLES` (which still lists all five roles as
recordable) — a future reader should not "simplify" `CHECKPOINT_ROLES` away
without re-reading this paragraph; doing so silently reintroduces the
misattribution.

**Late counter bump.** When `reconcile_pending_attempts` resolves `outcome
== "FAIL"` for a row whose `story_id` is a real story id (no `:` — never a
`phase:` or `unattributed:` synthetic), it calls
`flex_build.bump_attempt_count(story_id, project_dir)` in its own
`try/except`, exactly as the synchronous path already did at PostToolUse
time for the (now rare) case where an outcome is known immediately. Because
`next_action.infer_position` re-reads `.companion/attempt_counter.json` on
every call rather than caching it, a bump that lands after an earlier
next-action read is still honoured by the *next* read — the escalation
ladder now escalates one loop iteration later than in the synchronous era.
This is a timing change, not a correctness regression: the ladder's meaning
(`bump_attempt_count`, `read_attempt_count`, `clear_attempt_count`, and
`next_action.infer_position`'s rows 5/6/7) is entirely unmodified by
INFRA-258. `effort_db.reconcile_attempt`'s `WHERE ... AND tokens_total IS
NULL` guard makes reconciliation single-shot per row, so a repeated
`<task-notification>` for an already-reconciled row cannot double-bump.

**Accepted losses.**
- With `effort_tracking` disabled there is no `effort.db` row to carry the
  `output_file`, so an async spawn's outcome is never knowable and the FAIL
  bump cannot fire for that project — INFRA-237's "the bump runs
  independent of `effort_tracking`" property does not survive async
  spawning. Fixing this would require a second durable pending-spawn store
  outside `effort.db`, which is a larger change than this fix-before-tag
  warrants; projects that disable effort tracking lose the automatic
  retry/loop-breaker escalation as a result.
- Rows 335–340 and any other pre-existing `NULL`-token rows are not
  repaired — no migration backfill, no repair subcommand, no manual
  `UPDATE`. They predate the `output_file` column and are therefore
  invisible to `pending_reconcilable` by construction, so the phase-101
  rollup gap for them is permanent.
- A row's `output_file` lives under `/tmp` and is not guaranteed to survive
  between sessions (eviction, reboot, disk pressure); a row whose
  `output_file` is gone by the time `reconcile_pending_attempts` next runs
  keeps its `NULL` tokens permanently. This residual loss is accepted rather
  than mirrored into a second durable store — `classify_pending_reason`
  names this specific case `file-missing`, so at least the loss is *visible*
  in `pairmode_effort.py pending` rather than an unattributable, indistinct
  `None` (CER-091 defect 3).
- A `SendMessage` continuation of an existing agent is logged
  (`log_recording_event(decision="observed:non-spawn-tool")`) but never
  recorded as an `attempts` row — deciding whether a continuation is a new
  attempt (and if so how `attempt_number` and its `output_file` would be
  derived for it) is a modelling question this story deliberately leaves
  open, not a defect (CER-091 § Out of scope).

**Pending-sweep index and age bound (INFRA-266, CER-088).** The
`pending_reconcilable` predicate is covered by a partial index,
`idx_attempts_pending`, created *after* `_MIGRATIONS` runs (not in
`_SCHEMA_INDICES`) because its `WHERE` clause references `output_file`, an
ALTER-added column that does not exist yet on the legacy (pre-INFRA-258)
databases the migrations upgrade — creating it earlier would crash `init_db`
on exactly those databases. The sweep also accepts an opt-in
`max_age_days` cutoff (`effort_db.PENDING_MAX_AGE_DAYS = 14`, since a `/tmp`
spawn-output file does not survive that long, so scanning for a row older
than the window is pure cost), but the cutoff is bound only at
`reconcile_pending_attempts`'s hook-sweep call site — `pending_reconcilable`
itself still defaults to no cutoff, because the shared query is also used
by diagnostics (e.g. a pending-row diagnostic) whose entire purpose is
surfacing permanently-pending rows; baking the cutoff into the query itself
would hide the exact rows such a diagnostic exists to find.

**Spawn-output containment (INFRA-266, CER-089).** `read_completed_spawn`
routes its `output_file` argument through `_contained_spawn_output` before
opening anything. Two containment rules exist: `--db-path` (below) raises
on escape, but spawn-output uses a looser accept/reject rule instead —
temp-root-contained with a `tasks` path component, not a raise — because the
value is harness-generated launch metadata rather than an operator-supplied
argument, and pinning the containment to the exact observed shape
(`claude-<uid>/<slug>/<session>/tasks/<hash>.output`) would make every row
uncontained the moment the harness changes its directory layout, silently
halting all reconciliation.

**`--db-path` containment (INFRA-266, CER-016).** `effort_db.resolve_db_path_arg`
is the single source for resolving an explicit `--db-path` CLI argument,
used by both `record_attempt.py` and `pairmode_effort.py` (previously each
did its own unguarded `Path(db_path)` join). It applies `_depth_guard` and
project-dir containment and raises `ValueError` on an escaping path — unlike
`resolve_effort_db_path`'s silent fallback for an escaping `state.json`
value (project-owned, recoverable), an operator who names a specific
`--db-path` must not have it silently redirected.

**Context health check.** At checkpoint, the orchestrator calls
`skills/pairmode/scripts/context_health.check_context_health(db_path, current_phase)`
to produce a per-phase retry burden signal. The function sums output tokens from
FAIL-outcome reviewer rows in the current phase, compares against a rolling
per-phase median (using `COALESCE(tokens_out, CAST(tokens_total * 0.15 AS INTEGER))`
to handle the NULL `tokens_out` column in current records), and returns one of:
`normal`, `elevated`, `high`, or `insufficient_data` (when fewer than 3 prior
phases have been recorded). The signal is informational only — it never blocks the
checkpoint. The result `message` field is written to the step 8 checkpoint report.
The module exposes three public functions: `phase_retry_burden`, `rolling_phase_median`,
`check_context_health`. All three are safe when the DB does not exist.

### Drift evidence scoring

`skills/pairmode/scripts/drift_evidence.py` provides token-efficiency evidence
for convergence candidates surfaced by `pairmode_drift_report.py --convergent`.

**Function:** `score_convergence_candidate(project_dirs, pattern_id) -> (score, justification)`

- Queries each project's `effort.db` for all `agent_role='builder'` rows with
  non-null, non-zero `tokens_total`.
- Returns `(None, "insufficient data")` when fewer than 5 total builder attempts
  are found across all projects (sample too small for meaningful comparison).
- When sufficient data is available, computes a normalised score in `[0.0, 1.0]`:
  - **score > 0.5** — pattern-associated projects show lower median builder tokens.
  - **score = 0.5** — no observable difference.
  - **score < 0.5** — pattern-associated projects show higher median builder tokens.
- Returns a one-line `justification` string (e.g. "Projects with this pattern show
  ~12% lower median builder tokens (n=18 attempts across 3 project(s))").

**Scoring methodology:** Pattern-associated projects are identified using `pattern_id`
as a substring of the project path (coarse proxy). When no projects match this
heuristic, the function falls back to comparing the lower-token half of projects
against the upper half. The score is computed as:

```
score = 1.0 - (pattern_median / (pattern_median + other_median))
```

**Known limits (document inline — do not treat score as ground truth):**
- Small samples (5–20 attempts) produce noisy estimates.
- Confounding factors: story complexity, model choice, and retry count all affect
  token costs independently of any pattern.
- The pattern-proxy (substring match on project path) is coarse; a more accurate
  signal would require explicit tagging of attempts with the candidate pattern.
- Correlation only — lower tokens for pattern-associated projects may reflect
  pre-existing simplicity of those projects rather than an effect of the pattern.

The score is surfaced as an annotation above each promotion prompt in
`lesson_review.py`'s `run_drift_promotion`. It is advisory only — the developer
makes the final promotion decision.

---

## Observability surface

Phase 63 ships a read-only observability SPA. Phase G (HARNESS007-main) refactors it to read
the **resolver state model** as the primary data source alongside `.companion/state.json` and
`.companion/effort.db`. Multi-repo support is first-class: one instance shows N registered repos.

**Architecture:** `skills/observability/` is a pnpm monorepo with `api/` (Fastify 5) and
`ui/` (Vite + React 19) workspaces. Registry at `~/.config/flex-observability/registry.json`.

**Vendored dependency payload (CER-090 / INFRA-261, phase 103):** the `node_modules` tree under
`skills/observability/` (and its `ui/node_modules`/`api/node_modules` symlink farms into
the workspace `.pnpm` store) is committed to git in full, deliberately — not installed at
build time. This keeps the UI build gate (`pnpm --filter @flex-obs/ui build`, exercised by
`tests/pairmode/test_observability_ui.py`) hermetic and network-free in every fresh
`create-story-worktree` checkout, with no manual repair step. `.gitignore` carries a scoped
override: the repo's global `dist/`/`build/` patterns (intended for *our* build output)
match at every depth and would otherwise exclude vendored packages' shipped `dist/`/`build/`
payload, so a `**/node_modules/**/dist/` / `**/node_modules/**/build/` negation re-includes
it, anchored to `node_modules` so it never un-ignores our own `ui/dist`/`api/dist`. The one
carved-out exception is node-gyp's compile intermediates under `better-sqlite3`
(`build/Release/obj/`, `build/Release/obj.target/`) — reproducible `.o` files, never loaded
at runtime, still ignored. The tree is a linux-x64 snapshot, including a compiled
`better_sqlite3.node` addon; other platforms run `pnpm rebuild better-sqlite3` rather than
reinstalling. The repair path for a broken vendored tree is `git checkout`, never
`pnpm install` — the latter can rewrite the lockfile and resolve different versions.

**Resolver state model** (`flex_build.py resolver-state --json`): pure-read subcommand added
in HARNESS007/OBS-001. Returns `{action, position, effort_by_role, index}`. The TS reader
`readers/resolverState.ts` calls it via `child_process.spawnSync` and parses the JSON. The SPA
renders next-action, position fields, per-role effort, and the resolver-owned phase index from
this model — not from orchestrator-written keys like `current_story` (retired as display source).

**API:** Six GET endpoints (read-only): `/api/repos`, `/api/repos/:id/system` (era → phase →
story tree), `/api/repos/:id/context` (tokens, thresholds, effort.db, resolver_state),
`/api/repos/:id/lessons`, `/api/user/memories`, `/api/user/policies`. All three payload routes
(`system`, `context`, `lessons`) use an in-flight promise dedup map to prevent thundering-herd
double-builds on concurrent cache misses (HARNESS007/INFRA-168).

**Read-only contract:** All routes are GET; no write handlers.

**`flex_factor`:** Story frontmatter field (default 1.0) overrides the effective context
ceiling: `threshold × (1 + overrun_pct) × flex_factor`. The `/context` route live-reads the
active story's frontmatter via `parseStoryFrontmatter` (HARNESS007/INFRA-166); source is
`"story-frontmatter"` when a story is active, `"default"` otherwise.

**Defect fixes shipped in HARNESS007:** D1 — `expected_step_tokens` shows provenance label
`"thin-harness return-block growth"` (OBS-003). D2 — `context_current_tokens: 0` treated as
absent; stale-badge surfaces genuinely idle projects (OBS-004). D3 — waypoints now return all
roles and outcomes, not only reviewer-FAIL rows; NULL outcome is passed through as null, not
mapped to FAIL (OBS-005/CER-055).

**CLI entry point:** `skills/observability/scripts/flex_observability.py` provides `register`,
`unregister`, `list`, `serve`. Before first `serve`, run
`cd skills/observability && pnpm install && pnpm --filter @flex-obs/api build`. Server binds
to `127.0.0.1:7777` (loopback, dev-local only).

---

## Fleet discovery

`skills/pairmode/scripts/fleet_discovery.py` is a **read-only** tool that scans candidate
project directories and detects two binding signals:

- **Signal 1 (scripts binding):** the project's `CLAUDE.build.md` contains a
  `pairmode_scripts_dir` that resolves under THIS flex checkout's `skills/pairmode/scripts`.
  This is the authoritative binding mechanic (DP5) — `pairmode_scripts_dir = Path(__file__).parent`
  is baked in at sync time.

- **Signal 2 (version binding):** the project's `.companion/state.json` has a
  `pairmode_version` key (the version-nag signal).

A project matched by either signal is reported; the report distinguishes "bound by scripts
path", "bound by version only", and "both".

**Default candidate set:** `registered_projects` from this checkout's `.companion/state.json`,
merged with the documented candidate names under the parent of the flex root. Overridable via
`--candidate-dir` (repeatable) or `--candidates-file`.

**Read-only contract:** the tool never opens any scanned project file for write. The only file
it writes is the snapshot under `docs/fleet-snapshot.md` in THIS repo, which is not a scanned
project.

**Pre-fold hard gate (DP8):** The authoritative pre-fold run of this tool is a **hard gate
immediately before the fold**. Under Option Y, the fold makes `/mnt/work/flex` the 0.3.0
checkout; any un-migrated bound project breaks at the fold. The fleet may change across the
era, so the pre-fold run (HARNESS006 / RELEASE-006 runbook) is what licenses the fold.

**`registered_projects` stays drift-opt-in:** the discovery tool never writes to
`registered_projects`. Manual seeding from discovery results is allowed; forced sync is not.

CLI:
```bash
uv run python skills/pairmode/scripts/fleet_discovery.py [OPTIONS]

Options:
  --candidate-dir PATH   Add a candidate directory to scan (repeatable)
  --candidates-file PATH Read candidate dirs from a file (one per line)
  --snapshot PATH        Write snapshot to this file (default: docs/fleet-snapshot.md)
  --no-snapshot          Skip writing the snapshot file
  --json                 Output JSON instead of human-readable text
```

---

## Layer rules for this codebase

| Layer | May import from | May not import from |
|-------|----------------|---------------------|
| hooks/ | stdlib, no flex modules | skills/, lessons/ |
| skills/*/scripts/ | stdlib, requirements.txt deps | hooks/ (sibling skills ok for shared utils) |
| tests/ | anything | — |

Hooks must never import from skills. Skills may not call hooks directly. Both communicate
only via the pipe.

The companion sidebar (`skills/companion/scripts/sidebar.py`) imports
`record_spec_exception` from `skills/pairmode/scripts/spec_exception.py`.
This cross-skill dependency is intentional and permitted under the "sibling skills ok
for shared utils" rule. It must be preserved when either module is modified.


---

## Phase documentation policy

Each phase gets its own file: `docs/phases/phase-N.md` (integer ID) or
`docs/phases/phase-PM025-main.md` (string predicate + suffix).

**Phase naming suffixes** — Projects that need to insert remediation or preflight phases
without breaking disk sort order can use suffix variants:
- `-ante[N]` — preflight prerequisite (sorts before `-main`; must complete first)
- `-main` — the primary phase
- `-post[N]` — follow-on remediation (sorts after `-main`; must complete before next)
- `-sec` — security prerequisite (same semantics as `-ante`, conventional security label)

Alphabetical order mirrors build order: `ante < main < post`. Checkpoint tags follow the
same naming: `cp-PM025-main`, `cp-PM025-post1`, etc. See `skills/pairmode/SKILL.md`
§ `/flex:pairmode phase-new` for the full suffix table and CLI flags.

**Proposed phases** — A phase conceived before it is literally the next build target uses
a proposed filename: `docs/phases/phase-proposed-<kebab-name>-YYYYMMDD-NNN.md`. Proposed
phases do not appear in the main phase table in `docs/phases/index.md`; they appear under
a `## Proposed phases (not yet sequenced)` section. When sequenced, stories are absorbed
into the next available sequential phase, the proposed file is deleted via `git rm`, and
the row is removed from the index. See `CLAUDE.build.md` § Proposed phases for the full
sequencing workflow.

- New phases are always created using `phase_new.py --phase-id ID [--suffix SUFFIX]`.
  Integer IDs produce `phase-N.md`; string predicates with suffixes produce
  `phase-PM025-main.md`.
- The monolithic `docs/phase-prompts.md` is the legacy format for Phases 1–7 (flex repo only).
  It is not extended with new phase content going forward.
- `docs/phases/index.md` is the canonical list of all phases and their status.
- Phase files are the source of truth for the builder/reviewer loop. The orchestrator reads
  only the current phase file — not the entire monolithic doc.
- When reviewing or building, read only the current phase file. This keeps token usage
  proportional to phase scope, not project history.

New projects bootstrapped after Phase 7 never receive `docs/phase-prompts.md`.
Existing projects using the monolithic format migrate incrementally: each new phase
becomes its own file; old phases stay in the monolithic doc as a historical record.


---

## Documentation currency policy

README.md and relevant docs are updated at every phase checkpoint — not as an afterthought,
but as a required checkpoint step before tagging.

**What must stay current:**
- `README.md` — feature list, status, usage/CLI examples, known limitations. If a phase adds
  or changes a user-facing capability, README reflects it before the checkpoint tag is applied.
- `docs/architecture.md` — updated by the intent-reviewer at each checkpoint (existing process).
- `docs/brief.md` — updated when project goals or constraints change.
- Any `docs/` file explicitly referenced in the phase spec.

**What is exempt:**
- Internal implementation notes that live in code comments or commit messages.
- Phase spec files themselves (`docs/phases/phase-N.md`) — these are maintained by the build
  process, not documentation to be polished.

**Enforcement:** `checkpoint-docs` — one of the four steps in the actual
`_CHECKPOINT_SEQUENCE` (`checkpoint-security` → `checkpoint-intent` →
`checkpoint-docs` → `checkpoint-tag`; see § 10 above) — is the documentation
review step before tagging. The `docs-reviewer` leaf worker checks that README
reflects the phase's shipped capabilities. A checkpoint with a stale README is
not complete. (This project's checkpoint sequence has never had 8 numbered
steps or a "Step 5" — that description belonged to an earlier, monolithic
0.2-era checkpoint prose block, superseded by the code-resident
`_CHECKPOINT_SEQUENCE` since HARNESS006.)

**Phase completion gate:** A phase cannot be checkpointed with silently
abandoned `planned` stories. Before tagging, all `planned` stories in the phase
manifest must be either `complete` or formally deferred — added to a
`## Deferred stories` section in the phase doc with a one-line reason and
status updated to `deferred`. This is enforced as one of the three
**pre-checkpoint guards** (`check_checkpoint_guards`: phase-completion, CER Do
Now, build gate) that must all pass *before* the four-step
`_CHECKPOINT_SEQUENCE` starts — it is a gate ahead of the sequence, not a
numbered step inside it. A forked phase (one interrupted by a pivot) documents
its deferred stories at fork time; the resuming phase references the origin in
a `**Parent phase:**` header line.

**Scope guidance:** Updates should be proportional. A phase that adds a new CLI flag needs one
line in README. A phase that adds a new workflow needs a paragraph. A phase that only fixes
internal bugs needs only a "version/status" line if anything.

---

## Build commands

```bash
# Run tests (pairmode unit tests only — not integration tests in tests/)
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q

# Run all tests
PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q

# Lint
PATH=$HOME/.local/bin:$PATH uv run ruff check skills/pairmode/scripts/ tests/pairmode/
```

---

## Protected files

These files are working and must not be modified without a stated reason:

- `hooks/` — all existing hook scripts and hooks.json
- `skills/seed/scripts/` — all seed scripts
- `skills/companion/scripts/sidebar.py` — companion sidebar
- `.claude-plugin/plugin.json` — plugin manifest
- `.claude-plugin/marketplace.json` — marketplace config
- `lessons/lessons.json` — append-only lessons store (once created in Phase 3)
