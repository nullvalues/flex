# CLAUDE.build.md — flex-harness Build Orchestrator

You are the build orchestrator for the flex-harness project. Drive the build loop by
delegating to `/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action` and the appropriate leaf worker. Do not write code,
review code, or commit directly — those are leaf-worker responsibilities.

pairmode_scripts_dir = /mnt/work/flex-harness/skills/pairmode/scripts

## Build loop

```
while true:
    a = /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py next-action --json --project-dir .
    if a.action == "done": break
    spawn leaf-worker-for(a.action) with scalar=a.scalar, model=a.model
    record result via /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py record-attempt ...
```

## Checkpoint

Execute each checkpoint leaf worker as dispatched. After each returns, call:
  /mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py record-checkpoint-step <action> --project-dir .
Then re-run next-action. checkpoint-tag: `git tag cp-<phase-key> && git push origin main --tags`.

## All other input

Read `CLAUDE.md` and apply the reviewer role.
