---
id: INFRA-440
rail: INFRA
title: Merge fold-prep to main; disposition of flex-harness clone and stale remote branches
status: draft
phase: "145"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/phases/phase-proposed-retire-harness-release-channel-20260804-001.md
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The `flex-harness` release channel is being retired: with the local marketplace
cache serving plugin content, a second long-lived branch that only ever receives
`cp-NNN` promotion merges is confusing at best (operator decision, 2026-08-04).
This story is the repo-bookkeeping half of Phase 145 — fold the `fold-prep`
branch down into `main`, then dispose of the `flex-harness` checkout and the
stale branches. The sibling story INFRA-441 owns the tooling/docs repoint.

Two facts about the current repo state determine the mechanics here, and both
differ from what the phase doc's one-line Goal implies. They were verified at
spec time and the builder must re-verify (§ Instructions step 1):

1. **`/mnt/work/flex-harness` is not a separate clone — it is a linked git
   worktree of `/mnt/work/flex`** (`git worktree list` from either path lists
   both; both report the same `origin`, `git@github.com:nullvalues/flex`).
   Disposition is therefore `git worktree remove`, not deleting a clone, and
   `fold-prep`/`harness`/`era2`/`era3-methodology`/`pairmode`/`pr-squashed` are
   branches of *this* repo, not a foreign one.
2. **`fold-prep`'s only content commit is a rebrand, not an asset.** Across the
   33 commits in `main..fold-prep`, 32 are `cp-NNN` promotion merges and one is
   INFRA-332's agent backfill. Its entire diff against `main` is 6 lines in
   `.claude/agents/{docs-reviewer,gate-worker,spec-writer}.md`, each replacing
   the string `flex` with `flex-harness`. Merging that content *into* `main`
   would leave flex's own agent shells describing themselves as belonging to a
   project that this phase is deleting. So the merge preserves fold-prep's
   **ancestry**, not its tree: `git merge -s ours`.

## Requires

- **INFRA-441 complete and merged first.** This story removes
  `/mnt/work/flex-harness` from disk, and the build loop's own worker prompts
  and `CLAUDE.build.md` still resolve skills through that path until INFRA-441
  repoints them. Removing the directory first breaks the loop mid-phase. The
  phase doc's Stories table lists 440 before 441; the build order is the
  reverse.
- `/mnt/work/flex-harness` reports a clean tree (`git status --porcelain`
  empty). If it is dirty, stop and report — do not `--force`.

## Ensures

- `git merge-base --is-ancestor fold-prep HEAD` exits 0 on the story branch,
  and `git diff HEAD^1 HEAD` emits nothing — fold-prep's history is folded in
  with zero file-content change. Forbidden proxy: a merge that reports success
  while rewriting the agent shells; `grep -rc 'flex-harness project'
  .claude/agents/` must report 0 for every file.
- `git rev-parse --verify archive/<b>` exits 0 for each of `era2`,
  `era3-methodology`, `pairmode`, `pr-squashed`, `harness`, `fold-prep`, and
  each resolves to the SHA that branch pointed at before this story ran.
- `git worktree list` contains no `/mnt/work/flex-harness` entry and the path
  does not exist on disk.
- `git branch --list fold-prep harness` emits nothing.
- `/mnt/work/archive/flex-harness-companion/effort.db` exists.
- `docs/phases/phase-proposed-retire-harness-release-channel-20260804-001.md`
  is absent from the worktree and from `git ls-files`, and no tracked file
  under `docs/` still names it.
- The builder made no network mutation: `git ls-remote --heads origin` still
  lists all six branches. Forbidden proxy: treating the § Operator handoff
  block as builder work and deleting remote branches during the build.

## Instructions

1. Re-verify the two Context facts before touching anything:
   `git worktree list`, `git log --oneline main..fold-prep | wc -l` (expect 33),
   `git diff main fold-prep -- .claude/agents/ | head -40` (expect only
   `flex` → `flex-harness` string edits), and
   `git rev-list --count main..harness` (expect 0 — `harness` is already fully
   contained in `main`, so it needs archiving and deleting, never merging).
   If any expectation fails, stop and report rather than improvising.
2. Record the pre-deletion SHAs, then create local archive tags so every
   deletion below is reversible:
   `git tag archive/era2 origin/era2` and the same for `era3-methodology`,
   `pairmode`, `pr-squashed` (these four exist only as `origin/*` refs), plus
   `git tag archive/harness harness` and `git tag archive/fold-prep fold-prep`.
3. Fold fold-prep into the story branch (which reaches `main` through the normal
   build-loop merge — do **not** check out or commit to `main` directly):
   `git merge -s ours fold-prep -m "merge(INFRA-440): fold flex-harness release channel into main (ancestry only)"`.
   `-s ours` is load-bearing: it records the merge so the 33 commits are not
   orphaned, while leaving the tree byte-identical, per Context fact 2.
4. Preserve the harness checkout's gitignored build-cost data before removing
   it: `mkdir -p /mnt/work/archive/flex-harness-companion` and copy
   `/mnt/work/flex-harness/.companion/effort.db` there (shell `cp`; the path is
   outside the project root, so `Write`/`Edit` will be refused).
5. `git worktree remove /mnt/work/flex-harness` (no `--force`; see § Requires),
   then `git worktree prune`, then `git branch -d fold-prep harness` — both are
   ancestors of HEAD after step 3, so `-d` suffices and `-D` is never needed.
6. `git rm docs/phases/phase-proposed-retire-harness-release-channel-20260804-001.md`
   — Phase 145 now carries its content, so the proposed-phase file is
   superseded. Then `grep -rn 'phase-proposed-retire-harness-release-channel'
   docs/` and repoint any surviving reference to `docs/phases/phase-145.md`
   (one-line edits only; leave the other five `phase-proposed-*` files alone).
7. Leave the § Operator handoff commands below unexecuted, and quote them
   verbatim in the build report so the orchestrator can run them at commit time.

### Operator handoff (not builder work)

Run after this story's merge is pushed. Tags go first so every branch deletion
stays recoverable:

```bash
git push origin archive/era2 archive/era3-methodology archive/pairmode \
  archive/pr-squashed archive/harness archive/fold-prep
git push origin --delete fold-prep harness era2 era3-methodology pairmode pr-squashed
```

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green. This is a repo-mechanics story with no code surface, so it
introduces no unit test; the suite runs as a regression check that removing the
`/mnt/work/flex-harness` worktree broke no path-dependent test. The story's own
acceptance is the § Ensures shell assertions, which the reviewer runs directly.

## Out of scope

- Repointing `CLAUDE.build.md`, `docs/architecture.md`, worker prompts, or any
  other consumer of the `/mnt/work/flex-harness` path at the marketplace-cache
  install — that is INFRA-441, and it lands **before** this story.
- Deleting the other five `docs/phases/phase-proposed-*.md` files; only the
  retire-harness-release-channel one is superseded by Phase 145.
- Rewriting or squashing the 32 `cp-NNN` promotion merges — they are folded in
  as-is under `-s ours` and left in history.

<!-- Proportionality note (procedure § 4d): this spec runs long for a one-file
     story because its real surface is irreversible git state (a linked
     worktree, six branches, a shared remote) that leaves no diff to review, and
     because two verified repo facts contradict the phase doc's one-line Goal. -->

## Spec-writer note — returned `revised`

Three points need operator confirmation before a builder runs this:

1. **`-s ours` vs. the phase Goal.** The Goal says "preserving INFRA-332's 3
   agent files", but those files' only content is a `flex` → `flex-harness`
   rebrand (Context fact 2). This spec preserves their *history* and discards
   their *content*. Confirm that reading, or say so if the 6 lines were meant to
   land in `main`.
2. **Build order inverted.** § Requires puts INFRA-441 first, against the phase
   table's order, because this story deletes the path the build loop still uses.
3. **Remote deletions deferred.** Six remote-branch deletions on the shared
   `origin` are handed to the operator (§ Operator handoff) rather than run by
   the builder.
