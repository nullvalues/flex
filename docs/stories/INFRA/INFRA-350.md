---
id: INFRA-350
rail: INFRA
title: De-couple pairmode tests from operator gpg-signing config
status: complete
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/resolver_fixtures.py
  - tests/pairmode/test_flex_build.py
touches:
  - tests/pairmode/test_next_story.py
  - tests/pairmode/test_flex_build_mark_phase_complete.py
  - tests/pairmode/test_stage_integration.py
  - tests/pairmode/test_checkpoint_step.py
model: sonnet  # lower: mechanical, single-pattern fixture edit across six test files
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-157 (LOW), filed from `docs/build-loop-cold-eyes-review-20260801.md`'s §5 (opus finding M8):
137 pairmode tests fail headless (no interactive gpg agent available for pinentry) because they
shell out to real `git commit` and inherit the operator's global `commit.gpgsign` config; all 137
pass with `commit.gpgsign=false`. This is not hypothetical: this exact failure mode hit live in this
session while committing the artifacts for this very phase (`git commit` failed with "gpg: signing
failed: Operation cancelled" on the first attempt, resolved only because the operator was available
at a keyboard to unlock the agent). A CI or any headless/background build session would read red
for a non-reason. Same general class as CER-146 (a different environment-coupling axis — cwd path
substring matching rather than signing config).

Fix direction: the affected tests should set `commit.gpgsign=false` (or an equivalent
no-signing config) scoped to their own throwaway git fixture repos — never the operator's real
global config — so the tests verify actual git-commit behavior without depending on whether an
interactive pinentry is available in the environment they happen to run in.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

1. **The six fixture files that create real git repos and shell out to real `git commit`.**
   Located by `grep -rn '"commit"' tests/pairmode/` at spec time; all six are declared in this
   story's `primary_files`/`touches`:

   | file | git-init helper | real-commit call sites |
   |---|---|---|
   | `tests/pairmode/resolver_fixtures.py` | ~L91 | 2 |
   | `tests/pairmode/test_next_story.py` | ~L33 | 2 |
   | `tests/pairmode/test_flex_build.py` | ~L1244 (`_init_repo`-style helper + `_git()` at ~L1260) | 9 |
   | `tests/pairmode/test_flex_build_mark_phase_complete.py` | `_init_git_repo_with_tag` ~L229 (env-var identity, also creates a `git tag`) | 1 |
   | `tests/pairmode/test_stage_integration.py` | ~L56 | 5 |
   | `tests/pairmode/test_checkpoint_step.py` | ~L64 | 1 |

   Re-run that grep before editing; if it names a seventh file, add it to `touches:` (record it in
   a `## Scope widenings` table with a reason) and fix it too — the Ensures below are written
   against "every git-repo-init helper in `tests/pairmode/`", not against a frozen list of six.
2. **Git ≥ 2.32** on the build host, for `GIT_CONFIG_GLOBAL` / `GIT_CONFIG_SYSTEM` support (used
   by the Tests section's forced-signing verification run). Confirm with `git --version`.
3. **Baseline suite count** recorded before any edit (`uv run pytest tests/pairmode/ -q` collected/
   passed counts), so the reviewer can confirm no test was deleted, skipped, or xfailed to reach
   green.
4. **`tests/pairmode/test_stage_integration.py` conflict check.** INFRA-336 owns that file's
   stage-to-stage harness. If INFRA-336 is in flight (unmerged worktree), build this story after
   it lands to avoid a worktree conflict; if it has already landed, proceed.

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

1. **Every fixture git repo disables commit signing locally.**
   `grep -rn 'commit.gpgsign' tests/pairmode/` returns at least one hit in each of the six files
   named in Requires 1, and each hit sets the value to `false` in a repo-local `git config`
   invocation (or an equivalent repo-scoped mechanism) executed in the same helper that ran
   `git init` for that repo, before that repo's first commit.
   *Forbidden proxy:* a single hit in one shared helper that the other five files do not route
   through — the reviewer checks per-file presence, not total count.
2. **Tag signing is disabled wherever a fixture creates a tag.**
   `tests/pairmode/test_flex_build_mark_phase_complete.py`'s `_init_git_repo_with_tag` (and any
   other fixture that runs `git tag`, per `grep -rn '"tag"' tests/pairmode/`) also sets
   `tag.gpgsign=false` repo-locally.
   *Forbidden proxy:* relying on `git tag` being unsigned by default — an operator with
   `tag.gpgSign = true` in `~/.gitconfig` reproduces the exact failure this story closes.
3. **No test writes to the operator's real git config.**
   `grep -rn -- '--global' tests/pairmode/` and `grep -rn -- '--system' tests/pairmode/` return
   zero hits in any `git config` invocation, and no test writes to `~/.gitconfig` or
   `$XDG_CONFIG_HOME/git/config`.
   *Forbidden proxy:* `git config --global commit.gpgsign false` anywhere, even "temporarily
   restored in a finally block" — mutating the operator's machine is not an acceptable fix.
4. **The full suite passes with signing forced on and gpg guaranteed to fail.**
   The forced-signing command in `## Tests` (a throwaway `GIT_CONFIG_GLOBAL` containing
   `commit.gpgsign = true`, `tag.gpgsign = true`, and `gpg.program = /bin/false`, plus
   `GIT_CONFIG_SYSTEM=/dev/null`) exits 0 with the same passed count as the baseline run.
   This is the load-bearing check: if any fixture still inherits signing config, `/bin/false`
   makes it fail deterministically with no pinentry involved.
   *Forbidden proxy:* "passes on my machine with gpgsign unset" — an unset-signing run proves
   nothing, because the pre-fix code also passes there.
5. **The ordinary suite still passes with the baseline count.**
   `uv run pytest tests/pairmode/ -q` (no `-x`) exits 0 with a passed count ≥ the Requires-3
   baseline and a collected count equal to it.
   *Forbidden proxy:* reaching green by deleting, `skip`ping, or `xfail`ing any git-touching
   test, or by replacing a real `git commit` shell-out with a mock — these tests exist to
   exercise real git behavior and must continue to do so.
6. **No production code changed.** `git diff --name-only` against the story's base contains only
   paths under `tests/pairmode/` (plus this story file and any phase-index bookkeeping the build
   loop itself writes). No file under `skills/pairmode/scripts/` is modified.
   *Forbidden proxy:* teaching `flex_build.py` or any other harness script to pass
   `--no-gpg-sign` — the harness commits into the operator's real repo, where signing is the
   operator's deliberate choice and must be preserved.

## Instructions

1. Re-run `grep -rn '"commit"' tests/pairmode/` and `grep -rn '"init"' tests/pairmode/` to confirm
   the Requires-1 inventory. Every repo created by `git init` inside `tests/pairmode/` is in scope,
   whether or not that specific repo currently commits — a later test may add a commit to it.
2. In each git-init helper, immediately after `git init -q` and alongside the existing
   `git config user.email` / `git config user.name` lines, add a repo-local:

   ```
   git config commit.gpgsign false
   ```

   and, for helpers that also create tags, `git config tag.gpgsign false`. Use the same
   `subprocess.run([...], cwd=str(<repo>), check=True)` call shape already used by the surrounding
   `git config` lines in that file, including the same `env=env` argument where the file's helper
   already threads one (`test_flex_build_mark_phase_complete.py`).
3. **Prefer repo-local config over per-command `--no-gpg-sign` flags.** Rationale, and this is the
   deciding constraint: several of these tests invoke `flex_build.py` subcommands
   (`create-story-worktree`, `merge-story-worktree`, `mark-phase-complete`) which make their *own*
   git commits inside the fixture repo and its worktrees. A flag on the test's own `git commit`
   calls would not cover those; repo-local config does, because a linked worktree shares the main
   repo's `.git/config`. Do not chase the harness's internal commit calls with flags.
4. `test_flex_build_mark_phase_complete.py` sets identity through `GIT_AUTHOR_*`/`GIT_COMMITTER_*`
   environment variables rather than `git config`. Keep that pattern; add the signing config as a
   `git config` call in the same helper (there is no `GIT_*` env equivalent for `commit.gpgsign`).
5. Where a file creates more than one repo (e.g. `test_flex_build.py`'s main-repo and worktree
   fixtures), make sure every distinct `git init` gets the config. Linked worktrees created via
   `git worktree add` inherit the parent's config and need no separate call.
6. Do not add an autouse conftest fixture that mutates global git state, and do not set
   `GIT_CONFIG_GLOBAL` from inside the test code — the fix must be visible at each fixture site,
   per Ensures 1's per-file check, and must not change what other tests inherit from the
   environment.
7. Do not modify any file under `skills/pairmode/scripts/`.
8. Ideology-alignment note (Step 4a): the ideology's "Never silently pass contradictions" and
   "test framework is free to change" entries are unaffected — this story changes fixture
   environment scoping only. Instruction 5's "no mocking of real `git commit`" and Ensures 5's
   forbidden proxy were written to preserve the *rationale* of these tests (they exist to verify
   real git behavior), not merely to keep the suite green.

## Tests

Baseline (record counts first, per Requires 3):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Forced-signing verification — the load-bearing run for Ensures 4:

```bash
TMPGIT=$(mktemp -d)
printf '[commit]\n\tgpgsign = true\n[tag]\n\tgpgsign = true\n[gpg]\n\tprogram = /bin/false\n' > "$TMPGIT/gitconfig"
PATH=$HOME/.local/bin:$PATH \
  GIT_CONFIG_GLOBAL="$TMPGIT/gitconfig" \
  GIT_CONFIG_SYSTEM=/dev/null \
  uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Reviewer greps (Ensures 1–3, 6):

```bash
grep -rn 'commit.gpgsign' tests/pairmode/
grep -rn 'tag.gpgsign' tests/pairmode/
grep -rn -- '--global\|--system' tests/pairmode/
git diff --name-only | grep -v '^tests/pairmode/\|^docs/'
```

Acceptance:
- Both pytest runs exit 0 with the same passed count; collected count unchanged from baseline.
- Note: run the suite without `-x` so a pre-existing known failure cannot mask a new one.
- The first grep shows a hit in all six Requires-1 files; the second shows a hit in every file
  that runs `git tag`; the third returns nothing; the fourth returns nothing.

## Out of scope

- Any other environment-coupling axis in the suite — notably CER-146's cwd path-substring
  matching, which is the same *class* of defect but a different mechanism and a separate CER.
- Changing how `flex_build.py` (or any harness script) commits into the operator's real
  repository; operator signing preferences there are deliberate and stay untouched.
- Adding CI configuration, a CI-only git config profile, or a `conftest.py` global git-environment
  fixture. This story fixes the fixtures at their creation sites and nothing else.
- Converting any real-git test to a mocked/faked git; the real shell-outs are the point.
- Spec-preflight note (INFRA-190/191): the scan warns
  `Constant 'GIT_CONFIG_GLOBAL' referenced in story but no definition found in source tree`.
  Intentional and left as-is — `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` are git's own environment
  variables used only in the `## Tests` verification command, not project constants; nothing in
  this repo defines or should define them. No `scope:` findings were reported.
- `tests/pairmode/` files that reference git but never create a repo or commit
  (`test_hook_view.py`, `test_templates.py`, the `*_isolation.py` files, etc.) — matched by a
  loose grep on "git" but out of scope here.
