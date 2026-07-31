# CLAUDE.build.md — flex-harness Build Orchestrator

You are the build orchestrator for the flex-harness project. Drive the build loop by
delegating to `/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action` and the appropriate leaf worker. Do not write code,
review code, or commit directly — those are leaf-worker responsibilities.

pairmode_scripts_dir = /mnt/work/flex-harness/skills/pairmode/scripts

## Build loop

Story-build actions (`spawn-builder`, `spawn-reviewer`, and the reviewer-equivalent spawn actions that write and commit code) run inside a disposable per-story git worktree: created fresh from the current branch tip before the builder spawns, and on reviewer PASS rebased + fast-forward-merged back onto the main branch, or on reviewer FAIL discarded outright — untracked content and all — without ever touching the main worktree's files. The builder and reviewer operate inside the returned worktree path, never the main project directory. Checkpoint-stage workers (`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`) are read-mostly/advisory and never commit — they stay on the main worktree, unwrapped. Planning-doc writes are not worktree-scoped: `phase_new.py` appends a `| <phase> | <title> | planned |` row to the active era doc's phase ledger (its `Phases` section) on every scaffold, so any commit of scaffolded planning docs stages `docs/eras/` alongside `docs/phases/` and `docs/stories/` — an unstaged ledger row is silent working-tree drift (CER-082). **One iteration per story (CER-074):** the loop polls `next-action` once per story — the builder spawn, the reviewer spawn, and the merge or discard all happen inside that single iteration; `next-action` never emits `spawn-reviewer`, and the orchestrator dispatches the reviewer itself after the builder returns. Do not re-poll `next-action` between the builder's return and the merge: a story counts as passed only once its `story-<ID>` commit reaches the main branch, which only the merge creates — so a mid-story poll reads the finished attempt as failed and re-dispatches a wasteful second builder over a good build.

`leaf-worker-for(a.action)` spawns `Task`/`Agent` with `subagent_type` resolved from `a.action` via the fixed map below (never `general-purpose` for a story-build/checkpoint action — an unresolved `general-purpose` spawn is invisible to the context-budget gate, INFRA-199/INFRA-241); `model=a.model` always overrides an agent's frontmatter `model:` default (see `docs/architecture.md` § Spawn contract):

ACTION_SUBAGENT_TYPE = {spawn-builder: builder, spawn-reviewer: reviewer, spawn-loop-breaker: loop-breaker, spawn-security-auditor: security-auditor, spawn-intent-reviewer: intent-reviewer, checkpoint-security: security-auditor, checkpoint-intent: intent-reviewer, checkpoint-docs: docs-reviewer}  # INFRA-325 adds checkpoint-docs: docs-reviewer — the role was fully specced (WORKER-011) but had no scaffolded shell or dispatch entry until this story; other spawn/checkpoint actions keep their own existing dispatch, out of INFRA-241 scope

```
while true:
    a = /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action --json --project-dir .
    if a.action == "done": break
    if a.action is a story-build action (spawn-builder / spawn-reviewer):
        wt = /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py create-story-worktree --story-id a.scalar --project-dir .  # also stamps current_story + generates docs/phases/permissions/<scalar>.json (INFRA-238)
        spawn leaf-worker-for(a.action) with subagent_type=ACTION_SUBAGENT_TYPE[a.action], scalar=a.scalar, model=a.model, cwd=wt
        on reviewer PASS: /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py merge-story-worktree --story-id a.scalar --project-dir .  # also clears the attempt counter (INFRA-237) and the current_story/permissions stamps (INFRA-238)
        on reviewer FAIL: /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py discard-story-worktree --story-id a.scalar --project-dir .  # also clears the current_story/permissions stamps (INFRA-238)
    else:
        spawn leaf-worker-for(a.action) with subagent_type=ACTION_SUBAGENT_TYPE[a.action], scalar=a.scalar, model=a.model  # INFRA-328: for spawn-loop-breaker, a.reason carries the double-fail story's most recent recorded fail_cause (or "" if none found); build the LOOP-BREAKER: [error] | FILE: [file:line] | TRIED: [what failed] prompt (CLAUDE.md § Loop-breaker mode) from it before spawning, extracting a FILE: value from a.reason when it names one
    # effort-attempt recording AND the attempt counter are both fully hook-side
    # (INFRA-236, INFRA-237): hooks/post_tool_use.py's Task/Agent branch calls
    # subagent_transcript.record_attempt_from_transcript() after every spawn, deriving
    # tokens/model/outcome from the live transcript and the spawn's own
    # tool_input/tool_response, writing an effort.db row AND bumping
    # .companion/attempt_counter.json on a FAIL outcome — no separate orchestrator-side
    # recording step needed.
```

## Model-upgrade prompts

At any judgment-handoff pause whose reason involves a model choice (`model-upgrade`
or future model-selection handoffs): present the suggested model(s) as named
`AskUserQuestion` options, and **always** leave a free-text path (the "Other"
input) so the operator can key in any model name — the `model_selector.py` tiers are not guaranteed current or exhaustive.

## Checkpoint

Execute each checkpoint leaf worker as dispatched. After each returns, call:
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py record-checkpoint-step <action> --project-dir . --phase-key <phase-key>
After the three gate workers complete, call `/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py checkpoint-report --project-dir .` and print its output verbatim (cost rollup + next-phase pointer) before checkpoint-tag. Then re-run next-action. checkpoint-tag (mandated order, CER-083): 1) `record-checkpoint-step checkpoint-tag --project-dir . --phase-key <phase-key>` (resets checkpoint_step; marks the phase complete in `docs/phases/index.md` **and** flips its row in the active `docs/eras/` doc's phase ledger, INFRA-267), then commit both paths — `git add docs/phases/index.md docs/eras/` — before tagging; 2) `git tag cp-<phase-key> && git push origin main --tags`; 3) promote: `git -C /mnt/work/flex-harness merge --ff-only cp-<phase-key>` (see docs/architecture.md § Release channel — flex-harness). A raw `git tag` alone, skipping step 1, is forbidden: `record-checkpoint-step` is idempotent and safely re-runnable if step 2 fails after it, but if the order reverses, step 1's skip is silent and the next phase's gates are lost. `--phase-key <phase-key>` on every call is what stops the wrong phase being marked complete (CER-077): it is the explicit source of truth `record-checkpoint-step`'s precedence chain checks first, ahead of any re-derivation from `docs/phases/index.md`.

## All other input

Read `CLAUDE.md` and apply the reviewer role.
