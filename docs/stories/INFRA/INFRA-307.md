---
id: INFRA-307
rail: INFRA
title: "Vendored payload guards: dot-claude tolerance pattern; delete test_extension.node; enumerate native binaries"
status: complete
phase: "115"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_vendored_payload_tracked.py
  - docs/architecture.md
touches:
  - .gitignore
  - skills/observability/node_modules/.pnpm/better-sqlite3@12.10.0/node_modules/better-sqlite3/build/Release/test_extension.node
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-307.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-261 (CER-090, phase 103) made the observability `node_modules` tree
tracked payload rather than an install step, and shipped
`tests/pairmode/test_vendored_payload_tracked.py` as the guard that keeps it
that way. Two findings from the cp-103 checkpoint say the guard is not yet
telling the truth about what it protects.

**CER-093 — the guard fails on other people's files.** Its central assertion
(`test_no_vendored_payload_is_gitignored`) demands that *every*
ignored-and-untracked path under `skills/observability` appear in a
hand-maintained allow-list of five literals. That is exactly right for the
defect it was built to catch — repo `.gitignore` patterns silently swallowing
vendored package payload — and exactly wrong for noise arriving from outside
the repo. Upstream npm packages sometimes ship a `.claude/` directory inside
their published tarball; a *machine-local* git exclude then makes those files
ignored-but-untracked, and the guard fails on a path nobody in this repo chose.
That is not a hypothetical: at cp-103 it fired live on `nanoid@3.3.12` and
`thread-stream@4.2.0` under `skills/observability/node_modules/.pnpm`, and the
"fix" was to delete the directories at checkpoint — a repair that lasts until
the next `pnpm` operation restores them. The mechanism is still live on this
machine today: `~/.config/git/ignore` contains `**/.claude/settings.local.json`
(git's default `core.excludesFile`), so any such directory is ignored the
moment it appears. A guard whose green state depends on the absence of files
it does not control is a guard the next person learns to re-run until it
passes.

**CER-094 — the payload contains a binary nobody justified.** INFRA-261's
architecture note names one native addon: `better_sqlite3.node`. `git ls-files`
returns eight tracked `.node` binaries, and one of them —
`…/better-sqlite3/build/Release/test_extension.node` — is a second gyp target
(`binding.gyp` `targets[1]`, sources `deps/test_extension.c`) that exists only
to exercise better-sqlite3's own `loadExtension` test suite. The API loads
`better_sqlite3.node` and nothing else
(`lib/database.js:48` — `require('bindings')('better_sqlite3.node')`). So the
repo tracks a 15 KB executable that no code path in this project reaches, and
the architecture doc's enumeration is wrong by omission.

The two halves are the same sentence: **the payload guard should assert what we
actually decided, and tolerate what we did not.** One widens the guard where it
was over-strict about foreign files; the other narrows the payload where it was
under-examined about executable ones. The third piece — an assertion that the
tracked `.node` set equals an enumerated, justified set — is what stops this
finding from recurring: after this story a payload refresh that brings in a new
native binary fails a test instead of arriving unread.

## Requires

- **INFRA-302 (phase 114) is complete and merged.** It edits the same test
  module. Build against its **post-merge** shape, in which
  `tests/pairmode/test_vendored_payload_tracked.py` already contains:
  - a fourth member of `ALLOWED_IGNORED_EXACT`, the exact string
    `"skills/observability/ui/tsconfig.tsbuildinfo"` — **no trailing slash**,
    because `git ls-files --others --ignored --directory` prints a bare file
    path without one while the other three entries are directories;
  - a third numbered category in the module-level allow-list comment block
    (currently `:29-45`) explaining that file;
  - two new tests asserting that path is untracked and `check-ignore`-clean.

  INFRA-302 § Ensures G4 binds it to that and nothing more: it does **not**
  touch `ALLOWED_IGNORED_SUFFIXES`, `_vendored_roots`, the `.node` binaries, or
  any existing test body. Those are this story's surface, and this story must
  likewise **not** remove, reorder or restructure 302's exact entry, its comment
  paragraph, or its two tests. If INFRA-302 has not merged when this story is
  dispatched, stop and say so rather than re-implementing its half.
  (`docs/stories/INFRA/INFRA-302.md` §§ Requires, Ensures D3/G4, Out of scope.)

- `tests/pairmode/test_vendored_payload_tracked.py` (pre-302 line numbers —
  re-read, do not trust them) defines `ALLOWED_IGNORED_SUFFIXES` (`:45-48`,
  matched with `str.endswith`), `ALLOWED_IGNORED_EXACT` (`:50-54`, matched with
  `in`), the allow-list comment block (`:28-44`), `_require_git` (`:73`),
  `_git` (`:80`), `_vendored_roots` (`:89-103`), and four tests:
  `test_no_vendored_payload_is_gitignored` (`:106`, whose offending-path filter
  is `:124-130`), `test_no_untracked_files_under_observability` (`:138`),
  `test_every_vendored_build_or_dist_dir_has_tracked_files` (`:158`) and
  `test_gitignore_still_ignores_our_own_build_output` (`:200`).

- The guard's live input is exactly five lines today
  (`git ls-files --others --ignored --exclude-standard --directory -- skills/observability`):
  `skills/observability/api/dist/`, the two `better-sqlite3`
  `build/Release/obj*/` dirs, `skills/observability/scripts/__pycache__/`,
  `skills/observability/ui/dist/`. After INFRA-302 it is those five plus
  `skills/observability/ui/tsconfig.tsbuildinfo`. Re-run before building.

- **The CER-093 mechanism, re-verified 2026-07-29.** `~/.config/git/ignore`
  (git's default `core.excludesFile`; `git config --get core.excludesFile`
  returns nothing, so the default applies) contains
  `**/.claude/settings.local.json`. No `.claude` directory currently exists
  anywhere under `skills/observability` (`find skills/observability -type d
  -name .claude` → empty) — they were deleted at cp-103, so **the failure
  cannot be reproduced by observation and must be reproduced synthetically**
  (§ Instructions step 1). Creating
  `…/.pnpm/nanoid@3.3.12/node_modules/nanoid/.claude/settings.local.json` and
  re-running the guard command yields **two** new lines, not one:

  ```
  skills/observability/node_modules/.pnpm/nanoid@3.3.12/node_modules/nanoid/.claude/
  skills/observability/node_modules/.pnpm/nanoid@3.3.12/node_modules/nanoid/.claude/settings.local.json
  ```

  Both shapes must be tolerated (§ Ensures A2). The closeout plan's sketch
  assumed one; it is two.

- The repo's own `.gitignore` ignores `.claude/story_scope.json` only
  (`:26`) — **not** `.claude/`. The repo is not the source of this ignore rule;
  a machine-local exclude file is. Any fix that edits `.gitignore` to "handle
  `.claude`" is addressing the wrong file.

- **Eight `.node` binaries are tracked** (`git ls-files | grep '\.node$'`), all
  under `skills/observability/node_modules/.pnpm/`:
  `@rollup+rollup-linux-x64-gnu@4.61.1` and `-musl@4.61.1`
  (`rollup.linux-x64-{gnu,musl}.node`); `@tailwindcss+oxide-linux-x64-gnu@4.3.0`
  and `-musl@4.3.0` (`tailwindcss-oxide.linux-x64-{gnu,musl}.node`);
  `lightningcss-linux-x64-gnu@1.32.0` and `-musl@1.32.0`
  (`lightningcss.linux-x64-{gnu,musl}.node`); and
  `better-sqlite3@12.10.0/node_modules/better-sqlite3/build/Release/` holding
  both `better_sqlite3.node` and `test_extension.node`.

- `test_extension.node` is a distinct node-gyp target: `binding.gyp` declares
  `targets[1]` `target_name: 'test_extension'` with
  `sources: ['deps/test_extension.c']` under a `sqlite3 == ""` condition. The
  runtime loader references only the other one
  (`better-sqlite3/lib/database.js:48`). `grep -rn 'test_extension'` across the
  repo outside that package returns only docs (`docs/phases/phase-103.md`,
  `phase-107.md`, `phase-115.md`, `docs/cer/backlog.md`,
  `docs/stories/INFRA/INFRA-275.md`, `INFRA-302.md`, this file) — **no code,
  test, or config in this project names it.**

- Its sibling bookkeeping files are tracked and stay tracked:
  `build/test_extension.target.mk`, and the make dependency stubs
  `build/Release/.deps/Release/test_extension.node.d`,
  `.deps/Release/obj.target/test_extension.node.d`,
  `.deps/Release/obj.target/test_extension/deps/test_extension.o.d`
  (§ Out of scope).

- `.gitignore`'s vendored-payload block (`:31-40`) carries the CER-090
  negations `!**/node_modules/**/dist/`, `!**/node_modules/**/build/`, a "Do not
  remove these lines to clean up the file" comment, and beneath them the two
  re-exclusions `**/node_modules/**/build/Release/obj/` and
  `**/node_modules/**/build/Release/obj.target/` — the direct precedent for
  § Ensures B2.

- `docs/architecture.md`'s **Vendored dependency payload (CER-090 / INFRA-261,
  phase 103)** paragraph (≈ `:3286-3302`) is the enumeration surface. It
  currently names only `better_sqlite3.node` ("including a compiled
  `better_sqlite3.node` addon"), names the `obj/`/`obj.target/` carve-out, and
  states the repair path is `git checkout`, never `pnpm install`. INFRA-302
  extends this same paragraph with the `tsconfig.tsbuildinfo` exclusion — build
  on top of that text, do not replace it.

- **Suite baseline, main checkout, 2026-07-29:** `uv run pytest tests/pairmode/
  -q` → `4116 passed, 211 skipped`. **There is no known failing test on main.**
  The "known `test_observability_ui` failure" is worktree-only (CER-090's
  incomplete payload); its remedy is to rsync the payload from the main
  checkout, **never** `pnpm install` (`docs/architecture.md:3299-3301`).
  See § Tests.

## Ensures

Grouped by item. Every assertion is checkable from the diff, by running the
command given, or by running the named test. § Ensures E is the one deliberate
exception — an evidence block, not an assertion — and states its own
verification path.

### A — `.claude/` tolerance, as a pattern

**A1. The tolerance is a compiled pattern, not literals.** The test module
gains a module-level `ALLOWED_IGNORED_PATTERNS: tuple[re.Pattern[str], ...]`
containing exactly one entry:

```python
ALLOWED_IGNORED_PATTERNS = (
    re.compile(r"(?:^|/)node_modules/(?:.*/)?\.claude/"),
)
```

No package name, version, or `.pnpm` store path appears in the pattern. Adding
`nanoid`, `thread-stream`, or any other literal to any allow-list constant is a
FAIL of this story, not an implementation of it: the whole point of CER-093 is
that the set of upstream packages shipping a `.claude/` directory is not
knowable in advance. Pinned by a test asserting the pattern's source string
contains none of `nanoid`, `thread-stream`, `.pnpm`, `@`.

**A2. Both printed shapes are tolerated.** The pattern matches the directory
form (`…/nanoid/.claude/`) and the file form
(`…/nanoid/.claude/settings.local.json`), because
`git ls-files --others --ignored --directory` emits both (§ Requires). Pinned
by a test that feeds both literal strings to the classifier and asserts each is
allowed.

**A3. The tolerance is anchored under `node_modules`.** A `.claude/` directory
that is *not* below a `node_modules/` segment is **not** tolerated — e.g.
`skills/observability/.claude/settings.local.json` must still be reported as
offending. Rationale, commented: this story tolerates *other people's* files
inside vendored packages; a `.claude/` directory in our own source tree is our
decision and must be confronted, not absorbed. Pinned by a test asserting that
string is classified offending.

**A4. Classification is one named function, used by the one test that filters.**
The module defines `_is_allowed_ignored(line: str) -> bool` returning
`line in ALLOWED_IGNORED_EXACT or line.endswith(ALLOWED_IGNORED_SUFFIXES) or
any(p.search(line) for p in ALLOWED_IGNORED_PATTERNS)`, and
`test_no_vendored_payload_is_gitignored`'s offending-path comprehension
(pre-302 `:124-130`) calls it instead of inlining the two membership tests. The
three constants keep their existing semantics — exact match, suffix match,
regex search — and the function's docstring names all three plus CER-093. The
extraction exists so § Ensures A1-A3 can be tested directly rather than only
through a `git` invocation whose input this repo does not control.

**A5. The comment block records the mechanism, the live hits, and the
boundary.** The module-level allow-list comment (pre-302 `:28-44`; post-302 it
carries a third numbered category from INFRA-302) gains a fourth numbered
category for the pattern, stating in this order: (a) upstream npm packages can
ship a `.claude/` directory inside their published tarball; (b) a
**machine-local** exclude file — `~/.config/git/ignore` on the machine where
this fired, git's default `core.excludesFile` — then makes those files
ignored-but-untracked, so the repo's own `.gitignore` is not the cause and
editing it is not the cure; (c) the live hits at cp-103 were `nanoid@3.3.12`
and `thread-stream@4.2.0` (named as history, **not** encoded in the pattern —
A1); (d) this is not the CER-090 defect class, because CER-090 is *our*
patterns hiding *vendored payload*, whereas this is *someone else's* file that
was never payload; (e) A3's boundary — outside `node_modules`, a `.claude/`
directory is still a finding.

**A6. The existing four tests keep their names and their strictness.** No
existing test in the module is renamed, deleted, or weakened; in particular
`test_no_untracked_files_under_observability` is **unchanged** — a `.claude/`
directory that is *not* ignored on some other machine still fails it, which is
correct (an unignored, untracked file under `skills/observability` breaks
worktree parity regardless of who wrote it). Say this in a one-line comment so
the asymmetry between the two guards reads as deliberate.

### B — `test_extension.node` leaves the payload

**B1. The binary is gone from git and from disk.**
`git ls-files -- 'skills/observability/**/test_extension.node'` prints nothing,
and the file does not exist on disk. Use `git rm -f` (not `--cached`): unlike
INFRA-302's tsbuildinfo, this is not a regenerable local cache we want to keep
— leaving it untracked and unignored would fail
`test_no_untracked_files_under_observability`, and leaving it untracked and
ignored while still on disk would ship a dormant unreviewed executable. It is
reproducible on demand via `pnpm rebuild better-sqlite3`.

**B2. A rebuild cannot resurrect it as a guard failure.** `.gitignore` gains
one re-exclusion line, `**/node_modules/**/build/Release/test_extension.node`,
placed with the existing `obj/`/`obj.target/` re-exclusions **below** the
CER-090 negation block, with a two-line comment giving the reason: it is
better-sqlite3's second gyp target (`binding.gyp` `targets[1]`), used only by
that package's own `loadExtension` test suite, never loaded by this project;
`pnpm rebuild better-sqlite3` regenerates it, and without this line the rebuild
would leave an untracked-and-unignored file that fails the payload guard.
`git check-ignore -q` on the path exits 0. The negation lines above are
**byte-identical** (verified by `git diff .gitignore`).

**B3. The suffix allow-list carries it, with its reason.**
`ALLOWED_IGNORED_SUFFIXES` gains the exact member
`"build/Release/test_extension.node"` — a suffix, not an exact path, so it
holds across better-sqlite3 version bumps that change the `.pnpm` directory
name. `ALLOWED_IGNORED_EXACT` is **not** touched (INFRA-302 owns its only new
member; § Requires). The allow-list comment block's category 1 (node-gyp
intermediates) is extended, or a fifth category added, to cover it — builder's
choice, but the text must say it is *the rebuild artifact of a deleted
binary*, not payload.

**B4. Two guard assertions pin the removal.** New tests assert (a)
`git ls-files` on the path is empty and (b) `git check-ignore -q` on it exits
0. Both skip under the module's existing `_require_git()` convention. Together
they make a future re-add fail a test rather than resurface at a security
audit.

**B5. Nothing else in the payload moves.** No other file is deleted or
untracked. `git diff --stat` shows the binary's deletion and no other change
under `skills/observability/node_modules/`. In particular the tracked
bookkeeping siblings (`build/test_extension.target.mk` and the three
`.deps/**/test_extension*.d` stubs) are untouched — § Out of scope.

**B6. `test_every_vendored_build_or_dist_dir_has_tracked_files` still passes.**
`build/Release/` retains tracked files (`better_sqlite3.node`, `sqlite3.a`,
`.deps/…`), so removing one file does not make the directory invisible to a
fresh worktree.

### C — the native-binary inventory becomes an assertion

**C1. The expected set is enumerated in code, version-insensitively.** The
module defines `EXPECTED_TRACKED_NATIVE_BINARIES: frozenset[str]` holding
exactly **seven** version-stripped paths, and a helper
`_strip_pnpm_version(path: str) -> str` that removes the trailing `@<version>`
from the `.pnpm/<segment>/` component only (`segment.rsplit("@", 1)[0]`, which
leaves scoped names like `@rollup+rollup-linux-x64-gnu` intact and is a no-op
for paths with no `.pnpm/` component). The seven, in the store's order:

| # | Version-stripped path (under `skills/observability/node_modules/.pnpm/`) | Why it is tracked |
|---|---|---|
| 1 | `@rollup+rollup-linux-x64-gnu/node_modules/@rollup/rollup-linux-x64-gnu/rollup.linux-x64-gnu.node` | Rollup 4's native core; Vite loads it during the UI build gate. glibc variant. |
| 2 | `@rollup+rollup-linux-x64-musl/node_modules/@rollup/rollup-linux-x64-musl/rollup.linux-x64-musl.node` | Same, musl variant — selected at load time by libc detection. |
| 3 | `@tailwindcss+oxide-linux-x64-gnu/node_modules/@tailwindcss/oxide-linux-x64-gnu/tailwindcss-oxide.linux-x64-gnu.node` | Tailwind 4's Rust engine; the UI build's CSS pipeline. glibc variant. |
| 4 | `@tailwindcss+oxide-linux-x64-musl/node_modules/@tailwindcss/oxide-linux-x64-musl/tailwindcss-oxide.linux-x64-musl.node` | Same, musl variant. |
| 5 | `lightningcss-linux-x64-gnu/node_modules/lightningcss-linux-x64-gnu/lightningcss.linux-x64-gnu.node` | Lightning CSS transform/minify, pulled in by the Tailwind/Vite pipeline. glibc variant. |
| 6 | `lightningcss-linux-x64-musl/node_modules/lightningcss-linux-x64-musl/lightningcss.linux-x64-musl.node` | Same, musl variant. |
| 7 | `better-sqlite3/node_modules/better-sqlite3/build/Release/better_sqlite3.node` | The API's SQLite addon; loaded at runtime by `require('bindings')('better_sqlite3.node')` (`lib/database.js:48`). |

Each of 1-6 is an optional, platform-gated dependency of its parent package
(`rollup`/`lightningcss` declare a per-platform `optionalDependencies` map;
only the two `linux-x64` variants resolved into this snapshot). The builder
writes each one-line justification from what the package actually declares —
check the parent `package.json` — rather than copying this table verbatim if it
disagrees with the tree.

**C2. The set is asserted, both directions.** A new test
`test_tracked_native_binaries_match_enumerated_set` derives the live set from
`git ls-files -- skills/observability` (filtering `endswith(".node")`), maps
each through `_strip_pnpm_version`, and asserts equality with
`EXPECTED_TRACKED_NATIVE_BINARIES`. The failure message must name both
directions explicitly — *unexpected binaries* ("a payload refresh added a native
binary that no one has justified; enumerate it in `docs/architecture.md` and add
it here, or delete it") and *missing binaries* ("an expected native binary is no
longer tracked; the payload is incomplete and a fresh worktree will fail to
build"). It skips under `_require_git()`.

**C3. Version bumps do not fail it; new binaries do.** The version-stripping is
deliberate and commented: a patch bump of `rollup` must not fail an unrelated
story, but a *new* native binary — or a *new package* shipping one — must.
Pinned by two tests over `_strip_pnpm_version` directly: one asserting
`…/.pnpm/@rollup+rollup-linux-x64-gnu@4.61.1/…` and the same path with
`@9.9.9` map to the same key, and one asserting a path with an added
`@some-pkg@1.0.0/…/foo.node` segment does **not** collapse into any expected
member.

**C4. The count is pinned as an anti-vacuity floor.** The same test asserts
`len(EXPECTED_TRACKED_NATIVE_BINARIES) == 7` and that the derived live set is
non-empty, so a mis-scoped `git ls-files` returning nothing cannot pass by
matching an empty expectation.

**C5. `test_extension.node` is absent from the expected set** — its absence is
the assertion that closes CER-094, and a comment above the constant says so.

### D — the record

**D1. The architecture vendoring note enumerates every tracked `.node`.**
`docs/architecture.md`'s **Vendored dependency payload** paragraph (≈
`:3286-3302`, as extended by INFRA-302) is **extended, not rewritten**: its
current "including a compiled `better_sqlite3.node` addon" phrasing is replaced
by a short enumeration of all seven tracked native binaries with C1's one-line
justifications (a compact list is fine; no new `##`-level heading), plus a
sentence recording that `test_extension.node` was deleted by this story as a
better-sqlite3 test fixture that no flex code path loads. It states that the
enumeration is machine-checked by
`tests/pairmode/test_vendored_payload_tracked.py::test_tracked_native_binaries_match_enumerated_set`,
so the doc and the test must be updated together. Cites `INFRA-307, CER-094`.

**D2. The same note carries the `.claude/` caveat.** One or two sentences
recording that upstream packages may ship `.claude/` directories, that a
machine-local git exclude can make them ignored-but-untracked, that the payload
guard tolerates them by pattern under any `node_modules` root and only there,
and that this is deliberately *not* handled by editing the repo `.gitignore` —
the repo is not the source of the ignore rule. Cites `INFRA-307, CER-093`.

**D3. CER-093 carries a RESOLVED note.** `docs/cer/backlog.md`'s CER-093 row
(`:66`) gains a bolded `**RESOLVED Phase 115 — INFRA-307 …**` note appended to
its Finding cell, naming the pattern, the `node_modules` anchoring, and the
architecture caveat. It must not claim the guard is now immune to environmental
noise in general — it claims that *this* class (`.claude/` artifact
directories inside vendored packages) no longer fails it. The row is not
deleted or moved (`docs/cer/backlog.md:6-7`).

**D4. CER-094 carries a RESOLVED note recording which branch was taken.** The
CER-094 row (`:67`) gains a bolded `**RESOLVED Phase 115 — INFRA-307 …**` note
stating that the row's second option was chosen — deletion, not
justify-and-keep — with the reason (separate gyp target, no loader in this
project) and the fact that the remaining seven binaries are now enumerated in
the architecture note *and* asserted by test.

### E — fresh-worktree evidence (recorded, not asserted)

The point of E is that the payload is only genuinely proven from a checkout
that contains exactly what git tracks. A deletion that is fine in the main
checkout — where the file may still sit on disk from a previous build — proves
nothing.

**E1. A fresh worktree cut from clean `HEAD` builds the API and loads
better-sqlite3.** After B lands, the builder cuts a worktree from the story
branch tip and, from that worktree, records verbatim:

```bash
git worktree add /tmp/infra307-fresh HEAD
cd /tmp/infra307-fresh/skills/observability
pnpm --filter @flex-obs/api build
node -e "const D=require('better-sqlite3'); const d=new D(':memory:'); console.log(d.prepare('select 1 as x').get());"
ls -l node_modules/.pnpm/better-sqlite3@*/node_modules/better-sqlite3/build/Release/
```

Acceptance: the build succeeds, the `node -e` prints `{ x: 1 }`, and the `ls`
listing shows `better_sqlite3.node` present and `test_extension.node` absent.
This is CER-094's actual question — does removing it break anything — answered
by execution rather than by reading `binding.gyp`.

**E2. The UI build gate is run in the same fresh worktree, and its remedy is
recorded if needed.** Run `tests/pairmode/test_observability_ui.py` there. If
it fails, that is CER-090's incomplete vendored payload, **not** this story:
rsync the payload from the main checkout, re-run, and record both the failure
and the remedy verbatim. **Never** run `pnpm install`
(`docs/architecture.md:3299-3301` — it can rewrite the lockfile and resolve
different versions). Do not weaken, skip or xfail the test.

**E3. The full suite is run in the fresh worktree, without `-x`.** Paste the
pytest tail (passed/skipped counts) and the elapsed time. Acceptance is *same
counts as the main-checkout run in § Tests* — on `610af2a3` main has no failing
test, so "green modulo known failures" is not an acceptable report.

**E4. The `.claude/` tolerance is exercised against real `git`, then cleaned
up.** In the fresh worktree, create
`skills/observability/node_modules/.pnpm/nanoid@3.3.12/node_modules/nanoid/.claude/settings.local.json`,
run the guard command and
`uv run pytest tests/pairmode/test_vendored_payload_tracked.py -q`, paste both
outputs (the two new ignored lines; the test passing), then `rm -rf` the
directory and paste `git status --porcelain -- skills/observability` showing it
clean. Automated coverage is § Ensures A2 over literal strings; this item
exists because a pattern that has only ever been matched against hand-written
strings has never met `git`. Do **not** leave the directory behind, and do
**not** create it in the main checkout.

### F — cross-cutting

**F1. INFRA-302's surface is intact.** `git diff` on
`tests/pairmode/test_vendored_payload_tracked.py` shows 302's
`ALLOWED_IGNORED_EXACT` entry, its comment paragraph, and its two tests present
and unmodified. `ALLOWED_IGNORED_EXACT` gains no member in this story.

**F2. No other module is edited.** The diff touches only the files listed in
`primary_files` and `touches`. No `skills/pairmode/scripts/**` change, no other
test module, no `skills/observability/api/**` or `ui/**` source, no `.gitignore`
line outside the one added re-exclusion and its comment.

**F3. `schema_introduces` stays `false`.** No table, no persistent state, no
management-surface row owed in `docs/phases/phase-115.md` § Schema delivery.

**F4. The full test suite is green**, run once **without `-x`**
(`tests/pairmode/`), against the § Requires baseline of `4116 passed, 211
skipped` plus the additions from INFRA-296/301/302/306. The new tests raise the
passed count; the skipped count must not rise. If any test fails, verify it
reproduces on clean `HEAD` **in the same worktree** before attributing it
elsewhere, and say so explicitly in the build result.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order A → B → C → then E, and write D last against what actually
shipped.

**0. Re-read before you write.** The line numbers in this spec are anchors, not
coordinates, and INFRA-302 has since moved some of them. Confirm INFRA-302 is
in your `HEAD` (`git log --oneline | grep INFRA-302`); if it is not, stop and
say so. Read, as they exist *now*:
`tests/pairmode/test_vendored_payload_tracked.py` in full (it is short);
`.gitignore:1-45`; `docs/architecture.md`'s Vendored dependency payload
paragraph. Re-run the § Requires commands: the ignored-paths listing, `git
ls-files | grep '\.node$'`, and `find skills/observability -type d -name
.claude`.

**1. (A) The tolerance.** Reproduce the failure first, synthetically, so you
have seen it: create the `nanoid` `.claude/settings.local.json` shown in
§ Requires, run
`uv run pytest tests/pairmode/test_vendored_payload_tracked.py -q`, confirm
`test_no_vendored_payload_is_gitignored` FAILs and note **both** offending
lines. Then add `import re`, `ALLOWED_IGNORED_PATTERNS`, `_is_allowed_ignored`,
and rewire the offending-path comprehension to call it. Add A5's comment
category. Re-run: it passes. Remove the synthetic directory before you commit —
`git status --porcelain -- skills/observability` must be clean.

Do **not** approach this by editing `.gitignore` or by narrowing the guard's
`git ls-files` scope. The first addresses the wrong file (§ Requires: the
ignore rule is machine-local); the second would blind the guard to the CER-090
defect class it exists for.

**2. (B) The deletion.** In one commit: `git rm -f` the binary; add the
`.gitignore` re-exclusion line with its two-line comment, placed beside the
existing `obj/`/`obj.target/` re-exclusions and **without touching** the
negation lines above them; add the `ALLOWED_IGNORED_SUFFIXES` member and its
comment text; add B4's two tests. Then run
`git ls-files --others --ignored --exclude-standard --directory -- skills/observability`
and confirm the output is the previous six lines (five plus INFRA-302's) and no
more — the deleted binary must not appear, because it is no longer on disk.

**3. (C) The inventory.** Add `_strip_pnpm_version`,
`EXPECTED_TRACKED_NATIVE_BINARIES` (seven members, version-stripped), and
`test_tracked_native_binaries_match_enumerated_set` with C2's two-directional
failure message. Add C3's two `_strip_pnpm_version` unit tests and C4's floor
assertions. Derive the seven strings by running the § Requires `git ls-files`
command and stripping — do not hand-type them from this spec, and reconcile any
disagreement in favour of the tree (then say so in your build result).

**4. (E) The evidence.** Run E1-E4 last, from a real fresh worktree, and paste
the outputs into the build result. Do not create `.claude` directories in the
main checkout.

**5. (D) The prose.** Write D1 and D2 against the shipped code, then D3 and D4.
Resist overclaiming in both CER notes: CER-093 becomes *this class of
environmental noise is tolerated*, not *the guard is environment-proof*;
CER-094 records *which* of its two options was taken and why.

**6. Sequencing notes.** (a) INFRA-302 is upstream — build against its
post-merge shape and leave its entry, comment and tests alone (§ Ensures F1).
(b) INFRA-306 is a phase-115 sibling touching
`skills/observability/api/src/**`; it does not touch this story's files, but if
it has already landed, run E1's `pnpm --filter @flex-obs/api build` against the
merged tree, not a stale one. (c) INFRA-310 is strictly last across the era and
performs the backlog truth pass; the CER-093/094 notes in D3/D4 are **yours**,
not 310's — 310 audits that every row carries a disposition, it does not write
this one for you.

**7. Spec-preflight note.** `spec-preflight` on this story reports two constant
warnings — `ALLOWED_IGNORED_PATTERNS` (§ Ensures A1) and
`EXPECTED_TRACKED_NATIVE_BINARIES` (§ Ensures C1) — "referenced in story but no
definition found in source tree". Both are **intentional**: this story creates
them. They must resolve after the build; re-running `spec-preflight` clean is a
cheap self-check that you named them exactly as specced.

**8. Ideology note (Step 4a — resolved inline, no conflict).** Three entries
shaped this spec. *"Never silently pass contradictions"* (`docs/ideology.md`,
§ Accepted constraints) is the whole shape of A: the tempting fix for CER-093 —
narrow the guard's scope, or delete the offending directories at each
checkpoint — makes a real class of finding stop being reported, which is the
false confidence that constraint names as worse than no system at all. The
chosen fix widens the allow-list *only* along a stated axis (`.claude/` under
`node_modules`) and keeps everything else, including A3's boundary and A6's
untouched second guard, strict. C is the same constraint applied forward: an
unenumerated native binary arriving in a payload refresh currently passes
silently, and after this story it cannot. *"We prefer rationale-bearing
decisions over bare rules"* (§ Core convictions) is why A5, B2 and C3/C5 are
Ensures rather than niceties — a bare regex, a bare ignore line and a bare
version-stripping rule each read as arbitrary to the next reader, and the
obvious "cleanup" of any of them is a regression. *"Hooks are thin relays only"*
and *"Sidebar owns all state writes"* were checked and do not bind: no hook, no
`.companion/` state, and no writer of any kind is touched by this story.

## Tests

Run from the story worktree root. After item A:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_vendored_payload_tracked.py -q 2>&1 | tail -20
```

After items B and C, the guard plus its neighbours:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_vendored_payload_tracked.py \
  tests/pairmode/test_observability_context_api.py \
  tests/pairmode/test_observability_ui.py \
  tests/pairmode/test_docs.py \
  -q 2>&1 | tail -30
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**, so nothing is masked:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
# A1/A4 — the pattern and the classifier exist; no package literals
grep -n 'ALLOWED_IGNORED_PATTERNS\|def _is_allowed_ignored' \
  tests/pairmode/test_vendored_payload_tracked.py
grep -c 'nanoid\|thread-stream' tests/pairmode/test_vendored_payload_tracked.py  # only inside the comment block

# B1 — the binary is gone from git and disk
git ls-files -- 'skills/observability/**/test_extension.node'   # empty
ls skills/observability/node_modules/.pnpm/better-sqlite3@*/node_modules/better-sqlite3/build/Release/

# B2 — a rebuild would be ignored, not offending
git check-ignore -q \
  skills/observability/node_modules/.pnpm/better-sqlite3@12.10.0/node_modules/better-sqlite3/build/Release/test_extension.node \
  && echo ignored

# B5/C — exactly seven tracked native binaries remain
git ls-files | grep -c '\.node$'   # 7

# F1/F2 — nothing else moved
git diff --stat
git diff .gitignore
git diff tests/pairmode/test_vendored_payload_tracked.py

# D3/D4 — the CER rows are closed
grep 'CER-093' docs/cer/backlog.md | grep -c 'RESOLVED Phase 115'   # 1
grep 'CER-094' docs/cer/backlog.md | grep -c 'RESOLVED Phase 115'   # 1
```

Evidence commands for § Ensures E, run in a fresh worktree cut from the story
branch tip (outputs pasted into the build result):

```bash
git worktree add /tmp/infra307-fresh HEAD
cd /tmp/infra307-fresh/skills/observability
pnpm --filter @flex-obs/api build
node -e "const D=require('better-sqlite3'); const d=new D(':memory:'); console.log(d.prepare('select 1 as x').get());"
ls -l node_modules/.pnpm/better-sqlite3@*/node_modules/better-sqlite3/build/Release/
cd /tmp/infra307-fresh
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_observability_ui.py -q 2>&1 | tail -10
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
```

Acceptance:

- every new test from A1-A6, B1-B6, C1-C5 passes;
- every pre-existing test in
  `tests/pairmode/test_vendored_payload_tracked.py` — including INFRA-302's two
  — passes under its original name (A6, F1);
- the full suite is green against the § Requires baseline (`4116 passed, 211
  skipped` on `610af2a3`, plus the additions from INFRA-296/301/302/306), with
  the passed count higher and the skipped count unchanged;
- `git ls-files | grep -c '\.node$'` returns `7`;
- § Ensures E1-E4 are recorded in the build result, including the `{ x: 1 }`
  from the `node -e` load and the clean
  `git status --porcelain -- skills/observability` after E4's cleanup.

**On the "known failure".** There is no failing test on main as of 2026-07-29.
If `tests/pairmode/test_observability_ui.py` fails in your worktree, that is
CER-090's incomplete vendored payload: rsync the payload from the main
checkout, **never** run `pnpm install`, re-run, and record what you did (E2).

## Out of scope

- **Deleting `test_extension.node`'s tracked bookkeeping siblings** —
  `build/test_extension.target.mk` and the three
  `.deps/**/test_extension*.d` make-dependency stubs. They are small text files
  generated from `binding.gyp`, which still declares the target; removing them
  would leave the tracked makefile tree inconsistent with the source that
  produces it, for no gain. The binary is what CER-094 asked about, and the
  binary is what goes.
- **Removing any other native binary, or re-examining whether both the `gnu`
  and `musl` variants are needed.** C1 enumerates and justifies all seven; a
  narrowing decision (e.g. dropping musl variants to shrink the payload) is a
  separate call with its own portability evidence, and would make the snapshot
  host-specific in a way INFRA-261 deliberately avoided.
- **Editing `.gitignore` to handle `.claude/` directories,** or adding a repo
  ignore rule for them. The ignore rule is machine-local
  (`~/.config/git/ignore`); adding a repo-level one would change the meaning of
  `.claude/` for every checkout and every downstream project that copies this
  file, to fix a problem the repo did not cause.
- **Any general "environmental noise" tolerance** — a `.gitattributes`-driven
  scheme, a `FLEX_ALLOW_IGNORED` env var, or reading the user's global excludes
  and subtracting them. Each of those makes the guard's green state depend on
  more machine-local configuration, which is the direction CER-093 is
  complaining about. One stated pattern, one stated axis.
- **Making `test_no_untracked_files_under_observability` tolerate `.claude/`
  too** (A6). An untracked *and unignored* file under `skills/observability`
  breaks worktree parity whoever wrote it; that guard stays strict.
- **Pinning binary content** — checksums, size assertions, or a signature
  check on the tracked `.node` files. C2 asserts the *set*, which is what
  CER-094 asked for; content attestation for vendored binaries is a real but
  much larger question (provenance, rebuild reproducibility) and belongs to its
  own story.
- **Automating the architecture-note ↔ test-constant relationship** (generating
  one from the other). D1 states they must be updated together and C2's failure
  message says so; a generator is a third source of truth for a seven-line
  list.
- **CER-090's payload-completeness question in general** — whether a fresh
  worktree can build the UI with no manual rsync. This story records the
  evidence (E2, E3); the row is already annotated RESOLVED at cp-103
  (`docs/cer/backlog.md:213`) and re-opening it is not this story's business.
- **Any further `docs/cer/backlog.md` grooming** beyond the CER-093 and CER-094
  rows named in D3/D4. The era's remaining rows are closed by their own
  stories, and the backlog truth pass is INFRA-310.
- **INFRA-302's `tsconfig.tsbuildinfo` half** — its `ALLOWED_IGNORED_EXACT`
  entry, its comment paragraph and its two tests (§ Requires, § Ensures F1).
