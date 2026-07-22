# CLAUDE.build.md — flex-harness Build Orchestrator

You are the build orchestrator for the flex-harness project. Drive the build loop by
delegating to `/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action` and the appropriate leaf worker. Do not write code,
review code, or commit directly — those are leaf-worker responsibilities.

pairmode_scripts_dir = /mnt/work/flex-harness/skills/pairmode/scripts

## Build loop

Story-build actions (`spawn-builder`, `spawn-reviewer`, and the
reviewer-equivalent spawn actions that write and commit code) run inside a
disposable per-story git worktree: created fresh from the current branch tip
before the builder spawns, and on reviewer PASS rebased + fast-forward-merged
back onto the main branch, or on reviewer FAIL discarded outright — untracked
content and all — without ever touching the main worktree's files. The builder
and reviewer operate inside the returned worktree path, never the main project
directory. Checkpoint-stage workers (`checkpoint-security`, `checkpoint-intent`,
`checkpoint-docs`) are read-mostly/advisory and never commit — they stay on the
main worktree, unwrapped.

```
while true:
    a = /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action --json --project-dir .
    if a.action == "done": break
    if a.action is a story-build action (spawn-builder / spawn-reviewer):
        wt = /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py create-story-worktree --story-id a.scalar --project-dir .
        spawn leaf-worker-for(a.action) with scalar=a.scalar, model=a.model, cwd=wt
        on reviewer PASS: /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py merge-story-worktree --story-id a.scalar --project-dir .
        on reviewer FAIL: /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py discard-story-worktree --story-id a.scalar --project-dir .
    else:
        spawn leaf-worker-for(a.action) with scalar=a.scalar, model=a.model
    record result via /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py record-attempt ...
```

## Model-upgrade prompts

At any judgment-handoff pause whose reason involves a model choice (`model-upgrade`
or future model-selection handoffs): present the suggested model(s) as named
`AskUserQuestion` options, and **always** leave a free-text path (the "Other"
input) so the operator can key in any model name — the `model_selector.py` tiers are not guaranteed current or exhaustive.

## Checkpoint

Execute each checkpoint leaf worker as dispatched. After each returns, call:
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py record-checkpoint-step <action> --project-dir .
Then re-run next-action. checkpoint-tag: `git tag cp-<phase-key> && git push origin main --tags`.

## All other input

Read `CLAUDE.md` and apply the reviewer role.
