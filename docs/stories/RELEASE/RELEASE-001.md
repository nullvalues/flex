---
id: RELEASE-001
rail: RELEASE
title: "Dev-line & rollback anchor (DP1, DP2)"
status: complete
phase: "HARNESS001-ante1"
story_class: methodology
primary_files:
  - docs/stories/RELEASE/RELEASE-001.md
touches:
---

# RELEASE-001 — Dev-line & rollback anchor (DP1, DP2)

## Context

Era 003 makes a breaking change to flex's skills and bootstrapped build loop.
Because the fleet consumes flex from a single shared checkout and runs skill
scripts directly from the working tree, even uncommitted edits in
`/mnt/work/flex` can break fleet builds. Before any refactor code lands, the
dev line must be isolated and a named rollback anchor must exist.

This story is **operator-executed git plumbing**, not a builder story. It
DOCUMENTS the procedure and its acceptance — it does not itself run git, and no
source-code edits are produced. The only file this story owns is this spec.

Per **DP1** (✅ AGREED — Option B + additive discipline): harness development
happens on a `harness` branch in a `git worktree` at `/mnt/work/flex-harness`,
so `/mnt/work/flex` stays on `main` (fleet-facing, stable) and the fleet can
physically never execute harness code (different path = hard barrier). The
worktree's `CLAUDE.build.md` is regenerated via `sync-build` with
`pairmode_scripts_dir=/mnt/work/flex-harness/skills/pairmode/scripts` so
flex-in-worktree exercises the worktree's own scripts/tests, fully isolated
from the fleet.

Per **DP2** (✅ AGREED): tag the current `main` HEAD as `v0.2.0` — flex's first
semver tag, the named "what the fleet runs today" rollback anchor, distinct
from the `cpNN-…` checkpoint tags. Branch topology (`stable/0.2` etc.) is
resolved in DP5 (no `stable/0.2` branch — `main` *is* the stable line); the
`v0.2.0` tag is needed under any topology.

## Acceptance criteria

1. A `harness` branch exists, created from the current `main` HEAD.

2. A git worktree exists at `/mnt/work/flex-harness`, checked out to the
   `harness` branch (`git worktree list` shows it bound to `harness`).

3. The worktree's `CLAUDE.build.md` has been regenerated via `sync-build`
   such that its `pairmode_scripts_dir` is
   `/mnt/work/flex-harness/skills/pairmode/scripts` (NOT
   `/mnt/work/flex/skills/pairmode/scripts`). This makes flex-in-worktree run
   the worktree's scripts, isolating it from the fleet.

4. A `v0.2.0` annotated tag exists at the current `main` HEAD (flex's first
   semver tag; the fleet rollback anchor). `git tag --list 'v0.2.0'` is
   non-empty and `git rev-parse v0.2.0` resolves to the `main` HEAD commit at
   tag time.

5. `main` is untouched by this story: still on the 0.2.x line, no version bump,
   no source changes. The only working-tree artifact attributable to this story
   on `main` is this spec doc itself.

## Implementation guidance

This procedure is run by the **operator** (not a builder subagent). The exact
command sequence:

```bash
# From /mnt/work/flex, on main, working tree clean.

# 1. Tag the fleet rollback anchor at current main HEAD (DP2).
git -C /mnt/work/flex tag -a v0.2.0 -m "flex 0.2.0 — fleet rollback anchor (DP2, HARNESS001-ante1)"

# 2. Create the harness branch + worktree from main HEAD (DP1).
#    `git worktree add <path> -b <branch>` creates the branch and the worktree
#    in one step. Use the existing `harness` branch from step 1 form if it was
#    pre-created; otherwise let worktree add create it:
git -C /mnt/work/flex worktree add /mnt/work/flex-harness -b harness

# 3. Regenerate the worktree's CLAUDE.build.md so its pairmode_scripts_dir
#    points at the WORKTREE's scripts (DP1 isolation). sync-build derives
#    pairmode_scripts_dir from Path(__file__).parent of the syncing checkout,
#    so run it from the worktree's own scripts against the worktree dir:
PATH=$HOME/.local/bin:$PATH uv run python \
  /mnt/work/flex-harness/skills/pairmode/scripts/pairmode_sync.py sync-build \
  --project-dir /mnt/work/flex-harness --apply --yes
```

Notes for the operator:
- Step 3 MUST be run from `/mnt/work/flex-harness/skills/pairmode/scripts` (the
  worktree's copy), because `sync-build` bakes `pairmode_scripts_dir =
  Path(__file__).parent` of whichever checkout runs it (verified, DP5 binding
  mechanic). Running it from `/mnt/work/flex` would bake the wrong path.
- `main` carries NO version bump in this story; the bump is RELEASE-002 and
  lands on `harness` only (DP3 timing).
- The `harness` branch is where every breaking refactor (HARNESS001-main
  onward) is built; ante1's additive/doc stories still land on `main`.

## Tests

Methodology / operator-procedure story — no test file expected. Verification is
by git inspection (no pytest):

```bash
# Harness branch + worktree exist (AC1, AC2)
git -C /mnt/work/flex branch --list harness
git -C /mnt/work/flex worktree list | grep flex-harness

# Worktree's CLAUDE.build.md points at the worktree's scripts (AC3)
grep -n "pairmode_scripts_dir" /mnt/work/flex-harness/CLAUDE.build.md
# Expect: /mnt/work/flex-harness/skills/pairmode/scripts

# Rollback anchor tag exists at main HEAD (AC4)
git -C /mnt/work/flex tag --list 'v0.2.0'
git -C /mnt/work/flex rev-parse v0.2.0

# main untouched / still 0.2.x (AC5)
grep -n "PAIRMODE_VERSION" /mnt/work/flex/skills/pairmode/scripts/_version.py
# Expect: 0.2.0 on main
```

### Out of scope

- The version bump to `0.3.0-dev` / `0.3.0` (RELEASE-002, harness-only).
- Any `stable/0.2` branch — DP5 settled that `main` is the stable line; no such
  branch is created.
- The final fold (`harness → main`), `v0.3.0` tag, and worktree removal —
  authored in RELEASE-006, executed at/after HARNESS006.
