---
id: INFRA-261
rail: INFRA
title: Track the full vendored observability node_modules payload — un-gitignore build//dist under vendored trees so fresh story worktrees pass the UI build gate (CER-090)
status: draft
phase: "103"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - .gitignore
  - tests/pairmode/test_vendored_payload_tracked.py
touches:
  - docs/architecture.md
  - skills/observability/node_modules
  - skills/observability/ui/node_modules
  - skills/observability/api/node_modules
---

## Context

`skills/observability/` is a vendored pnpm monorepo: its `node_modules` tree is
committed to git rather than installed at build time, so the UI build gate
(`tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`,
which shells out to `pnpm --filter @flex-obs/ui build`) is hermetic and needs no
network. That intent is already recorded as operator guidance — repair a broken
observability tree with `git checkout`, never with `pnpm install`.

The tree is only **partially** committed. `.gitignore` lines 6–7 carry the global
Python-project patterns `dist/` and `build/`, which are directory patterns with no
leading slash and therefore match at *every* depth — including inside vendored
packages. So `@tanstack/react-query`'s `build/` (its entire compiled JS and `.d.ts`
payload), `@tanstack/query-core`'s `build/`, and the `dist/` directories of ~50
other `.pnpm` packages are excluded from git. Verified at spec time:

- `git ls-files skills/observability/node_modules | wc -l` → **5721** tracked files
- `git status --ignored --short skills/observability/node_modules` → **52** ignored
  directories, containing **1626** files (~36 MB) that git has never seen
- no nested `.gitignore` exists anywhere inside the vendored trees, so `.gitignore`
  lines 6–7 are the sole cause

The main checkout works only because those files exist **untracked on disk**, left
behind by the original `pnpm install`. Every fresh `git worktree` — which is what
`create-story-worktree` makes for every pairmode story — gets the tracked subset
only. `tsc -b` then fails with TS2307 module-not-found, `pnpm --filter @flex-obs/ui
build` exits non-zero, and `test_ui_build_emits_dist_index_html` FAILs the build
gate for *every* story in the repo, regardless of what that story touched. During
phase 102 the orchestrator worked around this twice by rsyncing the payload from
the main worktree into the story worktree by hand; INFRA-258's spec even carries a
standing "known pre-existing failure permitted" clause for exactly this test. Both
are symptom management. This story removes the cause.

**Why the fix is a scoped negation and not a blanket one.** gitignore's
parent-directory rule ("it is not possible to re-include a file if a parent
directory of that file is excluded") means a file-level negation cannot rescue a
file whose containing directory was excluded as a directory — the negation must
match the *directory*. Verified empirically in a scratch repo and then against this
repo with `git ls-files --others --ignored --exclude-from=<candidate>`: negating the
two directory patterns, scoped to `node_modules`, produces exactly the intended
result. It must also stay narrow in the other direction: `skills/observability/ui/dist/`
and `skills/observability/api/dist/` are *our own* build output and must remain
ignored, which rules out a broad `!skills/observability/**`.

**Why `**/node_modules/**` rather than naming the observability root.** The repo has
three vendored roots today (`skills/observability/node_modules`, `ui/node_modules`,
`api/node_modules` — the latter two being symlink farms into the workspace `.pnpm`
store), confirmed with `find . -name node_modules -not -path '*/node_modules/*'`.
A `node_modules`-generic pattern covers all three and any future one, while
un-ignoring strictly less than a path-anchored `!skills/observability/node_modules/**`
would (which would also drag in the node-gyp intermediates below). Anything inside
a `node_modules` directory is by definition vendored dependency payload, never our
own build output, so the generic form is the *narrower* claim, not the broader one.

**The one carve-out.** `better-sqlite3`'s `build/Release/` is 18 MB, of which 15 MB
is `obj/` and `obj.target/` — node-gyp compile intermediates (`.o` files), never
loaded at runtime and reproducible from source that is already tracked. Those two
directories stay ignored. The 2.2 MB compiled addon `better_sqlite3.node` beside
them **is** committed, because the API loads it at runtime and a fresh worktree must
not need a native rebuild. Net payload to commit: **1615 files, ~23 MB**.

## Requires

- The main checkout (`/mnt/work/flex`) still holds the complete vendored payload on
  disk. Verified at spec time: `git ls-files --others --ignored --exclude-standard
  skills/observability | wc -l` is non-zero and the `@tanstack/react-query` `build/`
  directory is populated. If the main checkout has itself lost the payload, **stop
  and flag** — regenerating it with `pnpm install` changes the tree's content and is
  a different story with different acceptance.
- `.gitignore` lines 6–7 are still exactly `dist/` and `build/`, and no other
  pattern in the file matches anything under a vendored `node_modules` (verified at
  spec time by running the candidate `.gitignore` through `git ls-files --others
  --exclude-from=`).
- No nested `.gitignore` file exists inside any vendored `node_modules` tree
  (verified: `find skills/observability/*/node_modules skills/observability/node_modules
  -name .gitignore` returns nothing). A nested one would need separate handling.
- `pnpm`, `node`, `git` (≥ 2.30, for `--path-format`) and `rsync` are on PATH.
- INFRA-262 (CER-092, `story_new.py` frontmatter) is **not** a prerequisite; the two
  phase-103 stories are independent.

## Ensures

1. `.gitignore` gains exactly one new block, appended at the **end** of the file
   (after `flex_eph/`), containing exactly these four patterns:

   ```
   !**/node_modules/**/dist/
   !**/node_modules/**/build/
   **/node_modules/**/build/Release/obj/
   **/node_modules/**/build/Release/obj.target/
   ```

   Lines 1–32 of the existing file are otherwise untouched: `git diff .gitignore`
   for the story shows **additions only** — no pattern deleted, edited, or reordered,
   and in particular the global `dist/` and `build/` patterns on lines 6–7 remain
   exactly as they are.
2. The block carries inline comments recording (a) that it is a deliberate
   last-match-wins override of the global patterns above and must not be "tidied
   away", (b) CER-090 / INFRA-261 as the reason, (c) that the global `dist/`/`build/`
   patterns target *our* build output while inside a vendored `node_modules` they
   wrongly exclude shipped package payload, and (d) that the two `obj`/`obj.target`
   re-ignores are node-gyp compile intermediates — rebuildable, never loaded at
   runtime, ~15 MB.
3. Our own build output stays ignored: after the change, `git check-ignore -q
   skills/observability/ui/dist` and `git check-ignore -q skills/observability/api/dist`
   both exit 0.
4. The vendored payload is fully tracked. From the repo root:
   - `git ls-files --others --exclude-standard -- skills/observability` prints
     **nothing** (no file under the vendored roots is untracked-and-unignored);
   - `git ls-files --others --ignored --exclude-standard --directory -- skills/observability`
     prints exactly these five entries and no others:
     `skills/observability/api/dist/`, `skills/observability/ui/dist/`,
     `skills/observability/scripts/__pycache__/`,
     `…/better-sqlite3@*/node_modules/better-sqlite3/build/Release/obj/`, and the
     matching `…/obj.target/`.
5. The compiled native addon is tracked: `git ls-files -- '*better_sqlite3.node'`
   prints at least one path under `skills/observability/node_modules`.
6. No node-gyp intermediate is committed: `git ls-files -- 'skills/observability/**/build/Release/obj/**'`
   and `… 'skills/observability/**/build/Release/obj.target/**'` both print nothing.
7. The work lands as **three** commits on the story branch, in this order, each
   scoped to one concern:
   1. `.gitignore` only — no other path in the commit;
   2. the vendored payload only — `git show --name-only` for this commit lists
      **only** paths containing a `/node_modules/` segment;
   3. the guard test plus `docs/architecture.md` — no path under `node_modules`.
   The payload commit is expected to be large (~1600 files changed, ~23 MB); that is
   the intended outcome, not a defect, and its isolation into its own commit is what
   keeps commits 1 and 3 reviewable.
8. The payload commit's message body states the file count, the approximate byte
   size, and one sentence on why the tree is vendored, so a future reader of `git
   log` does not have to reconstruct the reason from the diff.
9. Payload content is **copied from the main checkout, never regenerated**: no
   `pnpm install`, `pnpm add`, `pnpm rebuild`, or `npm` command is run at any point
   in the story. Consequence assertion: after commit 2, `git status --porcelain --
   skills/observability` in the story worktree is empty, and neither
   `skills/observability/pnpm-lock.yaml` nor any `package.json` under
   `skills/observability` appears in any of the three commits.
10. Nothing outside `node_modules` is un-ignored repo-wide by the `.gitignore`
    change: the set of untracked-and-unignored files repo-wide
    (`git ls-files --others --exclude-standard .`) is empty both before and after
    commit 1 + commit 2.
11. A new test file `tests/pairmode/test_vendored_payload_tracked.py` exists,
    shells out to `git` with `cwd` at the repo root, mutates nothing, and skips
    cleanly (`pytest.skip`) when `git` is unavailable or the tree is not a git
    repository. It contains at least these four tests:
    - `test_no_vendored_payload_is_gitignored` — every entry returned by
      `git ls-files --others --ignored --exclude-standard --directory` under the
      vendored roots must match the module-level allow-list, whose only members are
      the `build/Release/obj/` and `build/Release/obj.target/` suffixes; the failure
      message prints the offending paths.
    - `test_no_untracked_files_under_observability` — `git ls-files --others
      --exclude-standard -- skills/observability` is empty (this is the invariant
      that "a fresh worktree equals the main checkout").
    - `test_every_vendored_build_or_dist_dir_has_tracked_files` — for every directory
      named `build` or `dist` that exists on disk under a vendored `node_modules` and
      is not allow-listed, `git ls-files -- <dir>` returns at least one path. This is
      the direct regression anchor for the TS2307 cause.
    - `test_gitignore_still_ignores_our_own_build_output` — `git check-ignore` exits
      0 for `skills/observability/ui/dist` and `skills/observability/api/dist`.
12. The allow-list in that test file carries a comment explaining *why* node-gyp
    intermediates are the only permitted exception, so a later agent cannot widen it
    without confronting the reason.
13. The vendored-root discovery in the test is derived (glob for `node_modules`
    directories under `skills/`), not a hard-coded list of three paths, so a fourth
    vendored root added later is covered automatically.
14. **Fresh-worktree acceptance proof.** From the story worktree, after all three
    commits, a throwaway detached worktree is created outside the repo
    (`git worktree add --detach "$VERIFY" HEAD`), and **with no rsync, no `cp`, no
    `pnpm install`, and no other repair run inside it**:
    - `pnpm --filter @flex-obs/ui build` run from `$VERIFY/skills/observability`
      exits 0;
    - `$VERIFY/skills/observability/ui/dist/index.html` exists and contains the
      literal `flex observability`;
    - `uv run pytest tests/pairmode/test_observability_ui.py -q` run from `$VERIFY`
      is fully green;
    - the throwaway worktree is then removed (`git worktree remove --force` +
      `git worktree prune`) and does not appear in `git worktree list`.
15. The transcript of Ensures 14 (commands and their key output lines, including the
    `pnpm build` exit status and the pytest summary line) is appended to this story
    file under a new `## Acceptance proof` heading. This is the story's proof of
    close for CER-090 — a green suite in the main checkout is *not* sufficient,
    because the main checkout is precisely the environment where the bug is
    invisible.
16. `tests/pairmode/test_observability_ui.py` is **not modified**. It must pass
    unmodified, in both the main checkout and the fresh worktree.
17. Full `tests/pairmode/` suite passes in the story worktree, run **without** `-x`,
    with **no permitted failures**. Specifically, `test_ui_build_emits_dist_index_html`
    — carried as a "known pre-existing failure" by INFRA-258 and INFRA-259 — now
    passes; if it still fails, the story is not complete.
18. `docs/architecture.md` gains a short **Vendored dependency payload** note in the
    observability section (~line 2404, adjacent to the existing "`skills/observability/`
    is a pnpm monorepo" paragraph) recording: that the `node_modules` tree is
    committed in full, deliberately; that the reason is hermetic builds in fresh
    story worktrees with no manual repair; the `.gitignore` scoping rule and its
    node-gyp exception; that the tree is a linux-x64 snapshot including a compiled
    `better_sqlite3.node`, and that other platforms run `pnpm rebuild better-sqlite3`
    rather than reinstalling; and that the repair path for a broken tree is
    `git checkout`, never `pnpm install`.
19. The existing `--untracked-files=no` bullet in `docs/architecture.md` (~line 599),
    which justifies that flag by "the vendored `node_modules` payload (CER-090) shows
    as untracked noise", is re-read and corrected: after this story the payload is
    tracked, so that stated reason no longer holds. The **flag itself is not changed**
    — only the prose that explains it, and only to whatever it is now actually true
    of. If the flag's justification survives for an unrelated reason, say which.
20. No change is made to any `skills/observability` source file, `package.json`,
    `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `vite.config.ts`, or `tsconfig`:
    `git diff --name-only <base>..HEAD -- skills/observability` lists only paths
    containing a `/node_modules/` segment.
21. The other-vendored-tree question is answered explicitly, not assumed: the builder
    re-runs `find . -name node_modules -not -path '*/node_modules/*'` and records the
    result in the `## Acceptance proof` section. If it returns anything beyond the
    three observability roots, that root's payload is committed under the same
    patterns in the same commit 2 (no `.gitignore` change is needed for it — that is
    the point of the `node_modules`-generic form).

## Instructions

1. **Read before editing.** `.gitignore` in full (32 lines);
   `tests/pairmode/test_observability_ui.py` around line 290
   (`test_ui_build_emits_dist_index_html` — the gate this story fixes; do not touch
   it); `docs/architecture.md` lines ~595–608 and ~2400–2440; the CER-090 row in
   `docs/cer/backlog.md`. Do **not** read the vendored tree's contents — it is
   1600+ files of third-party payload and reading it is pure context burn.

2. **Rehydrate the payload into the story worktree first.** Your worktree does not
   have the untracked payload — that absence *is* the bug. Resolve the main checkout
   from the shared git dir rather than hard-coding a path:

   ```bash
   MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
   echo "$MAIN"                      # expect the main checkout, not this worktree
   test "$MAIN" != "$(git rev-parse --show-toplevel)" || { echo "not a linked worktree"; exit 1; }
   for d in node_modules ui/node_modules api/node_modules; do
     rsync -a "$MAIN/skills/observability/$d/" "skills/observability/$d/"
   done
   ```

   Use `rsync -a` (or `cp -a`), **never** `rsync -L` — the `ui/` and `api/` trees are
   symlink farms pointing at `../../node_modules/.pnpm/...`, and dereferencing them
   would duplicate the whole store and produce a tree that differs from the main
   checkout. Do **not** run `pnpm install`: it can rewrite the lockfile and resolve
   different versions, which breaks Ensures 9. Sanity-check before continuing:

   ```bash
   ls skills/observability/node_modules/.pnpm/@tanstack+react-query@*/node_modules/@tanstack/react-query/build/ | head
   ```

   That directory must be non-empty; it is the exact one whose absence produces the
   TS2307 failure.

3. **Edit `.gitignore`.** Append the block at the end of the file — after
   `flex_eph/`, not inline next to lines 6–7. Placement at the end is load-bearing
   twice over: gitignore is last-match-wins, so the negations must come after the
   patterns they override, and physical separation makes the override relationship
   visible to the next reader instead of looking like a contradiction on adjacent
   lines. Write it as:

   ```
   # Vendored dependency payload (CER-090 / INFRA-261) — deliberate override of the
   # global dist/ and build/ patterns above. Those target *our* build output; inside a
   # vendored node_modules they also exclude shipped package payload (compiled JS and
   # .d.ts), which leaves every fresh git worktree unable to run `pnpm --filter
   # @flex-obs/ui build`. Do not remove these lines to "clean up" the file.
   !**/node_modules/**/dist/
   !**/node_modules/**/build/
   # ...except node-gyp compile intermediates (~15 MB of .o files): rebuildable, never
   # loaded at runtime. The compiled addon beside them (better_sqlite3.node) IS tracked.
   **/node_modules/**/build/Release/obj/
   **/node_modules/**/build/Release/obj.target/
   ```

4. **Verify the patterns before staging anything.** Run all four and compare against
   Ensures 3, 4, 6 and 10:

   ```bash
   git check-ignore -v skills/observability/ui/dist skills/observability/api/dist
   git ls-files --others --ignored --exclude-standard --directory -- skills/observability
   git ls-files --others --exclude-standard -- skills/observability | wc -l   # expect ~1615
   git ls-files --others --exclude-standard . | grep -v '^skills/observability/' # expect empty
   ```

   If the second command lists anything beyond the five entries in Ensures 4, or the
   first does not report both paths as ignored, **stop and flag** — the pattern is
   wrong and committing the payload on top of a wrong pattern is expensive to undo.

5. **Commit 1 — `.gitignore` alone.**
   `fix(INFRA-261): scope global build//dist ignores away from vendored node_modules (CER-090)`.
   Stage only `.gitignore`; confirm with `git diff --cached --name-only`.

6. **Commit 2 — the payload alone.**

   ```bash
   git add -A skills/observability
   git diff --cached --name-only | grep -v '/node_modules/' || true   # must print nothing
   git diff --cached --stat | tail -1
   ```

   Only commit once that grep is empty. Message:
   `chore(INFRA-261): commit vendored observability node_modules payload`, with a body
   giving the file count and byte size and one sentence on why the tree is vendored
   (hermetic UI build gate, no network at test time). Expect ~1600 files; the size is
   expected and is exactly why this is its own commit.

7. **Commit 3 — the guard test and the docs.** Write
   `tests/pairmode/test_vendored_payload_tracked.py` per Ensures 11–13. Shape it like
   the other subprocess-driven tests in `tests/pairmode/` (resolve `FLEX_ROOT` via
   `Path(__file__).resolve().parents[2]`, `subprocess.run(..., capture_output=True,
   text=True, cwd=str(FLEX_ROOT))`). Keep the allow-list a module-level constant with
   the comment Ensures 12 requires. Then apply the `docs/architecture.md` edits from
   Ensures 18 and 19. Commit as
   `test(INFRA-261): guard the vendored payload against re-ignoring; document the policy`.

8. **Run the acceptance proof (Ensures 14).** This is the story's actual deliverable
   — do not substitute a green main-checkout suite for it.

   ```bash
   VERIFY=$(mktemp -d /tmp/infra261-verify-XXXXXX)
   git worktree add --detach "$VERIFY" HEAD
   ( cd "$VERIFY/skills/observability" && pnpm --filter @flex-obs/ui build ); echo "build exit=$?"
   grep -c 'flex observability' "$VERIFY/skills/observability/ui/dist/index.html"
   ( cd "$VERIFY" && PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_observability_ui.py -q 2>&1 | tail -5 )
   git worktree remove --force "$VERIFY" && git worktree prune && git worktree list
   ```

   Nothing may be copied into `$VERIFY` first. If the build fails there, the fix is
   incomplete — find the still-ignored path with
   `git ls-files --others --ignored --exclude-standard --directory -- skills/observability`
   in the main checkout, widen the pattern, and redo commits 1–2. Paste the transcript
   into a new `## Acceptance proof` section at the end of this story file, together
   with the `find . -name node_modules` output required by Ensures 21.

9. **Do not modify:** `tests/pairmode/test_observability_ui.py` (making it pass by
   editing it would re-hide the defect), the global `dist/`/`build/` patterns on
   `.gitignore` lines 6–7, any `skills/observability` source file, `pnpm-lock.yaml`,
   any `package.json`, `pnpm-workspace.yaml`, or
   `skills/pairmode/scripts/flex_build.py`'s worktree-creation path. If making the
   fresh worktree build appears to require changing `create-story-worktree` to copy
   ignored files, **stop and flag** — that is the workaround this story exists to
   delete.

10. **Note on `touches` and the permission artifact.** The three `node_modules` roots
    are listed in this story's `touches` for provenance, but `scope_guard.check_path`
    matches allowed paths **exactly**, not by prefix, so those entries authorise
    nothing on their own — and 1600 individual paths cannot be enumerated in
    frontmatter. That is deliberate and safe: the payload is moved by shell (`rsync`,
    `git add`), not by `Write`/`Edit`, so the Write/Edit-path guard is never the
    mechanism in play. Do not attempt to Write or Edit files inside `node_modules`.

11. **Ideology note (Step 4a, resolved inline).** Checked against `docs/ideology.md`.
    No conviction or accepted constraint is contradicted — this story changes no
    runtime code, so the hook/pipe/sidebar constraints and the single-writer rule are
    untouched. One conviction actively shapes the instructions: *"we prefer
    rationale-bearing decisions over bare rules, because a constraint without a reason
    will be violated by the first agent that encounters a situation the rule author
    did not anticipate."* Four un-annotated gitignore negations that appear to
    contradict the patterns six lines above them are precisely the kind of thing a
    future cleanup deletes — and the failure it reintroduces (every story worktree
    silently unbuildable) is invisible in the main checkout. Hence Ensures 2, 12 and
    18: the reason is written into the `.gitignore` itself, into the guard test's
    allow-list, and into `docs/architecture.md`, not only into this story file.

## Tests

Targeted — the new guard:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_vendored_payload_tracked.py -q 2>&1 | tail -20
```

Lock-in — the gate this story fixes, unmodified:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_observability_ui.py -q 2>&1 | tail -20
```

Full suite, without `-x` so nothing is masked:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance: all three fully green, **with no permitted failures** — including
`test_ui_build_emits_dist_index_html`, which previous stories carried as a known
pre-existing failure and which this story exists to fix.

Plus the fresh-worktree run from Instructions 8, whose transcript goes into
`## Acceptance proof`. A green suite in the story worktree alone does **not**
satisfy this story: the story worktree will have had the payload rsynced into it in
Instructions 2, so it cannot distinguish "the payload is committed" from "the
payload happens to be on disk". Only the throwaway worktree can.

**Spec-preflight note (Step 7).** The scan exits 0 with two constant warnings,
`VERIFY` and `XXXXXX`. Both are false positives: they are a shell variable and an
`mktemp` template inside the Instructions 8 command block, not codebase constants.
No route or constant referenced in this story is hallucinated.

## Out of scope

- **Un-vendoring the tree** — deleting `node_modules` from git and running
  `pnpm install --frozen-lockfile` as a test fixture instead. It is a real
  alternative and it would make the repo far smaller, but it makes the build gate
  network- and registry-dependent, which is the property the vendoring was chosen
  for. If revisited, it is its own story with its own acceptance, not a variation
  smuggled in here.
- **Committing the node-gyp intermediates** (`build/Release/obj/`, `obj.target/`,
  ~15 MB). Deliberately still ignored.
- **Slimming the vendored tree** — dropping the ~5.9 MB of `.map` source maps, or
  pruning packages the UI does not import. A partial tree is the exact defect class
  being fixed here; any trimming must be a separate, separately-verified decision.
- **Making the vendored tree cross-platform.** `better_sqlite3.node` is a linux-x64
  binary. Multi-arch vendoring, or a per-platform rebuild step, is not attempted;
  the limitation is documented (Ensures 18) instead.
- **Changing `create-story-worktree`** to copy ignored files into new worktrees.
  That is the workaround this story deletes, not a complement to it.
- **Changing the `--untracked-files=no` flag** in the release-channel promotion
  procedure. Only its explanatory prose is corrected (Ensures 19).
- **Repo-size remediation** — `git gc`, history rewriting, LFS, or shallow-clone
  guidance. The payload commit grows the repo by ~23 MB and that is accepted.
- **CER-092 / INFRA-262** (`story_new.py` stub frontmatter). Same phase, independent
  story, no shared files.
- **Adding a CI job** that builds the UI from a clean clone. The guard test plus the
  one-time fresh-worktree proof cover the invariant; continuous enforcement is a
  separate concern.

## Acceptance proof

Other-vendored-tree check (Ensures 21) — only the three known observability roots exist:

```
$ find . -name node_modules -not -path '*/node_modules/*'
./skills/observability/node_modules
./skills/observability/ui/node_modules
./skills/observability/api/node_modules
```

Fresh-worktree acceptance proof (Ensures 14), run after all three commits, with no
rsync/cp/pnpm-install/repair inside the throwaway worktree:

```
$ VERIFY=$(mktemp -d /tmp/infra261-verify-XXXXXX)
$ git worktree add --detach "$VERIFY" HEAD
Preparing worktree (detached HEAD f3112720)
HEAD is now at f3112720 test(INFRA-261): guard the vendored payload against re-ignoring; document the policy

$ ( cd "$VERIFY/skills/observability" && pnpm --filter @flex-obs/ui build ); echo "build exit=$?"
> @flex-obs/ui@0.1.0 build /tmp/infra261-verify-0mwWC9/skills/observability/ui
> tsc -b && vite build

vite v6.4.3 building for production...
transforming...
✓ 87 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.49 kB │ gzip:  0.32 kB
dist/assets/index-C3Nm2bbC.css   20.65 kB │ gzip:  4.87 kB
dist/assets/index-C16_rfeH.js   258.24 kB │ gzip: 78.11 kB
✓ built in 1.65s
build exit=0

$ grep -c 'flex observability' "$VERIFY/skills/observability/ui/dist/index.html"
1

$ ( cd "$VERIFY" && PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_observability_ui.py -q 2>&1 | tail -5 )
Installed 16 packages in 10ms
.....................................                                    [100%]
37 passed in 6.94s

$ git worktree remove --force "$VERIFY" && git worktree prune && git worktree list
/mnt/work/flex                                a8309ff3 [main]
/mnt/work/flex-harness                        5759033f [fold-prep]
/mnt/work/flex/.pairmode-worktrees/INFRA-261  f3112720 [pairmode/INFRA-261]
```

The throwaway worktree no longer appears in `git worktree list` after removal.

Note: two stray `.claude/settings.local.json` files were found inside
`node_modules/.pnpm/nanoid@3.3.12/.../nanoid/.claude/` and
`node_modules/.pnpm/thread-stream@4.2.0/.../thread-stream/.claude/` during rehydration —
artifacts of a prior agent session having run inside those vendored package directories, not
real npm package payload (neither nanoid nor thread-stream ship a `.claude/` directory
upstream). They were deleted from the story worktree before committing the payload so they
do not leak into the tracked tree or widen the guard test's allow-list; they were untracked
in the main checkout both before and after this story and are unaffected by this story's
`.gitignore` change either way.
