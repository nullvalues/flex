---
id: RELEASE-016
rail: RELEASE
title: Fold merge — fold-prep → main, tag v0.3.0
status: planned
phase: "HARNESS016-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/harness-cutover-runbook.md
---

## Requires

- RELEASE-015 complete with a PASSING (not blocked) gate result.
- `/mnt/work/flex-harness` and `/mnt/work/flex` are two linked git worktrees of
  the *same* repository (`/mnt/work/flex/.git/worktrees/flex-harness`) — not
  separate clones. `main`'s commits are already present in `fold-prep`'s object
  store after RELEASE-014; this story only needs to make them reachable from
  `main`'s branch tip.
- `/mnt/work/flex` working tree is clean and on `main`.
- `skills/pairmode/scripts/_version.py` on `fold-prep` already reads
  `PAIRMODE_VERSION = "0.3.0"` (finalized, no `-dev` suffix).
- **Known conflict (found via cold-eyes review 2026-07-21):** after
  RELEASE-019's second reconciliation, `main` and `fold-prep` each
  independently built story INFRA-208 / CER-067 (~1 hour apart, same day) —
  both add a `_register_context_budget_hooks()` function to `bootstrap.py`
  wiring `UserPromptSubmit`/`SessionStart`/`PostToolUse Task|Agent` hooks
  downstream. `main`'s commit is `66fcc87`; `fold-prep`'s is `83bdd4e`. They
  are functionally equivalent but not textually identical (`fold-prep`'s
  version additionally uses `state_utils._atomic_write_json` for the
  settings-file write and has marginally larger test coverage), so this is a
  real merge conflict on `bootstrap.py`, `sync.py`, and
  `test_bootstrap.py` — not one RELEASE-014/019 already resolved.

## Ensures

- On `/mnt/work/flex`, `main` contains the full `fold-prep` history via
  `git merge --no-ff fold-prep -m "Era 003: fold fold-prep to main, pairmode 0.3.0"`.
  This merge is expected to conflict on exactly the INFRA-208 duplicate
  described in Requires; every other commit should already be reconciled by
  RELEASE-014/RELEASE-019 and should apply conflict-free.
- The INFRA-208 conflict is resolved by keeping `fold-prep`'s
  `_register_context_budget_hooks()` implementation (`83bdd4e`) in full and
  discarding `main`'s duplicate (`66fcc87`) — do not hand-merge the two
  functions together. After resolution, `bootstrap.py` contains exactly one
  definition of `_register_context_budget_hooks()` and `CONTEXT_BUDGET_HOOK_SPECS`,
  matching `fold-prep`'s pre-merge content; the merge commit message notes
  that `main`'s independent INFRA-208 build was superseded by `fold-prep`'s,
  so the loss doesn't later read as an accidental drop of main work.
- No unresolved conflict markers remain anywhere in the tree after
  resolution.
- Annotated tag `v0.3.0` exists on the merge commit and is pushed along with
  `main`.
- Post-merge, `/mnt/work/flex`'s `_version.py` and `SKILL.md` frontmatter both
  read 0.3.0 — this is what flips the `global_session_check.py` version-nag
  hook for any still-un-migrated project.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes on
  `/mnt/work/flex` main after the merge, before pushing.
- `docs/harness-cutover-runbook.md`'s Final fold sequence steps referencing
  branch `harness` are corrected to `fold-prep` (should already be done by
  RELEASE-015; verify here and fix if missed).

## Instructions

Execute the runbook's Final fold sequence steps 1–2 with the corrected ref
name (`fold-prep`, not `harness`), from `/mnt/work/flex`. When the merge
conflicts on `bootstrap.py` / `sync.py` / `test_bootstrap.py` (INFRA-208,
see Requires), resolve by taking `fold-prep`'s side of
`_register_context_budget_hooks()` and its spec/tests wholesale — do not
attempt to combine the two implementations. Run the test suite between
merge and push. Do not perform re-sync (RELEASE-017) or worktree removal
(RELEASE-018) in this story. Take this story at a fresh context seam.

## Tests

- `git -C /mnt/work/flex merge-base --is-ancestor fold-prep main` exits 0.
- `git -C /mnt/work/flex describe --tags` at `main` resolves to `v0.3.0`.
- `grep -c "_register_context_budget_hooks" /mnt/work/flex/skills/pairmode/scripts/bootstrap.py`
  shows exactly one function definition (no duplicate/leftover from `main`'s
  `66fcc87`).
- Full suite green on `/mnt/work/flex` `main`.
