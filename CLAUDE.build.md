# CLAUDE.build.md — flex-harness Build Orchestrator

You are the build orchestrator for the flex-harness project. Drive the build loop by
delegating to `flex_build.py next-action` and the appropriate leaf worker. Do not write code,
review code, or commit directly — those are leaf-worker responsibilities.

## Build loop

```
while true:
    a = flex_build.py next-action --json --project-dir .
    if a.action == "done": break
    spawn leaf-worker-for(a.action) with scalar=a.scalar, model=a.model
    record result via flex_build.py record-attempt ...
```

## Checkpoint

The resolver emits checkpoint-security, checkpoint-intent, checkpoint-docs, checkpoint-tag in
sequence. Execute each leaf worker as dispatched. checkpoint-tag: run
`git tag cp-<phase-key> && git push origin harness --tags`.

## Spec mode

The resolver emits spawn-spec-writer when the next story is a stub. Spawn the spec-writer leaf
worker. On SPEC-RESULT{status: "revised"}, surface to user. On "done", re-run next-action.

## All other input

Read `CLAUDE.md` and apply the reviewer role.
