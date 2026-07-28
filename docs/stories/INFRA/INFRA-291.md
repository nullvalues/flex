---
id: INFRA-291
rail: INFRA
title: "Marketplace plugin source: local-relative ./ instead of github clone; README/CONTRIBUTING install-flow correction"
status: complete
phase: "111"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - .claude-plugin/marketplace.json
touches:
  - README.md
  - CONTRIBUTING.md
  - tests/pairmode/test_plugin_manifest.py
  - docs/stories/INFRA/INFRA-291.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This is the first of Phase 111's two packaging-repair stories, and the one that
makes the plugin **installable at all** from a local checkout. Both defects
surfaced on a fresh-machine install; this one blocks the install outright,
INFRA-292 (doubled `/flex:flex:*` namespace) only degrades it once installed.

`.claude-plugin/marketplace.json` declares the flex plugin's source as

```json
"source": { "source": "github", "repo": "nullvalues/flex" }
```

The actual install flow an operator uses against a checkout is
`claude plugin marketplace add ./flex` followed by
`claude plugin install flex@nullvalues-flex`. With a `github` source, the
second command ignores the checkout that was just added and clones the
published GitHub repo instead — so a developer testing local changes installs
someone else's (or an older) tree, silently. `"source": "./"` resolves
relative to the **marketplace root**, which is the directory containing
`.claude-plugin/marketplace.json` — the repo root in both cases — so the same
value is correct whether the marketplace was added from a local path or from
GitHub. The operator already applied this exact hotfix uncommitted on a second
machine; landing it here makes that hotfix redundant rather than a permanent
local divergence.

The documentation propagated the same breakage. `README.md:88-95` instructs
`claude code plugin install path/to/flex` and `claude code plugin install
./flex` — neither is a real command: Claude Code has no `plugin` subcommand
under `code`, and `claude plugin install` takes a `<plugin>@<marketplace>`
identifier, not a filesystem path. Anyone following the README cannot install
flex at all. `README.md:99-100` and the `README.md:141` section heading both
say "three skills"; there are four (`seed`, `companion`, `pairmode`,
`observability`) and the table at `README.md:143-151` already lists all four,
so the prose contradicts the table two lines below it.

`.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json` are both on
`CONTRIBUTING.md`'s protected-file list (`CONTRIBUTING.md:102-103`) — the two
CONTRIBUTING references the dossier flags. This story modifies one of them, so
it carries the required `## Protected file justification` section below, and
the reviewer is expected to check that justification against the diff rather
than flag the edit HIGH.

## Requires

- The repo is at a `HEAD` where `.claude-plugin/marketplace.json` contains
  `"repo": "nullvalues/flex"` inside `plugins[0].source`. Verify:
  `grep -n 'nullvalues/flex' .claude-plugin/marketplace.json` prints a line.
- `.claude-plugin/plugin.json` exists, its `name` is `flex` and its `version`
  is `0.3.0`; `marketplace.json`'s top-level `name` is `nullvalues-flex` and
  `plugins[0].version` is `0.3.0`.
- `tests/pairmode/test_version_match.py` exists and contains
  `_read_marketplace_flex_version`, which loads `marketplace.json` and asserts
  the flex entry's `version` equals the release core of `PAIRMODE_VERSION`.
  This story must not disturb it.
- `README.md` contains an `## Installation` section with a fenced `bash` block
  at ≈ lines 87-95, the sentence beginning `The plugin registers three skills:`
  at ≈ line 99, and the heading `## The three skills` at ≈ line 141.
- `CONTRIBUTING.md` contains the protected-file bullet list including
  `.claude-plugin/marketplace.json` at ≈ line 103.
- No dependency on INFRA-292. The two stories touch disjoint files
  (`marketplace.json`/`README.md`/`CONTRIBUTING.md` here; `skills/*/SKILL.md`
  and `pairmode_migrate.py` there) and may build in either order. The README
  strings this story writes use the `/flex:<skill>` form, which is the form
  INFRA-292 makes correct and which every existing doc already uses — so no
  README text written here needs revisiting after INFRA-292 lands.

## Ensures

Every assertion is checkable from the diff or by running the command given.

### A — the marketplace source is local-relative

**A1. The github source object is gone.** `.claude-plugin/marketplace.json`'s
`plugins[0].source` is the JSON string `"./"` — not an object. Verified by:

```bash
PATH=$HOME/.local/bin:$PATH uv run python -c \
  "import json;d=json.load(open('.claude-plugin/marketplace.json'));print(repr(d['plugins'][0]['source']))"
# ./
```

and `grep -c 'nullvalues/flex' .claude-plugin/marketplace.json` returns `0`.

**A2. Nothing else in the manifest changes.** The diff to
`.claude-plugin/marketplace.json` touches only the `source` key of the single
`plugins[0]` entry. `name` (`nullvalues-flex`), `owner`, `metadata`, and the
plugin entry's `name` (`flex`), `description` and `version` (`0.3.0`) are
byte-identical to `HEAD`. `.claude-plugin/plugin.json` is not modified at all.

**A3. The file remains valid JSON with the repo's existing formatting.**
Two-space indentation, one trailing newline, no comments, no key reordering.
`python -m json.tool` round-trips it without error.

**A4. The version guard still passes.**
`tests/pairmode/test_version_match.py::test_marketplace_flex_version_matches_pairmode_release_core`
passes unmodified — the test file is not edited by this story.

### B — the change is guarded by a test

**B1. A plugin-manifest test file exists.**
`tests/pairmode/test_plugin_manifest.py` exists and is collected by pytest.
(This file does not exist in the tree today; `spec-preflight` flagging it as
an unverifiable reference is expected and intentional — this story creates it.)

**B2. It asserts the source is local-relative.** It contains a test named
`test_marketplace_flex_source_is_local_relative` which loads
`.claude-plugin/marketplace.json`, selects the plugin entry whose `name` is
`flex`, and asserts its `source` is exactly the string `"./"`. The assertion
message states *why*: a `github` source makes
`claude plugin marketplace add <local-path>` install the published repo
instead of the added checkout.

**B3. It asserts the manifests agree on the plugin name.** A second test
asserts `plugin.json`'s `name` equals the `name` of the `marketplace.json`
plugin entry (`flex`) — the invariant that makes
`claude plugin install flex@nullvalues-flex` resolve, and the same invariant
INFRA-292 depends on for its `/flex:<skill>` namespacing.

**B4. The tests read the real repo files, not fixtures.** The module resolves
the repo root from `__file__` (the same idiom as
`tests/pairmode/test_version_match.py`'s `_REPO_ROOT`) and does not create
temporary copies — the point is to guard the shipped manifest.

### C — the README install flow is correct

**C1. No `claude code plugin` string survives anywhere in the repo's
documentation.** `grep -rn 'claude code plugin' README.md CONTRIBUTING.md`
returns nothing (exit 1).

**C2. The `## Installation` bash block gives the two real commands, in order.**
The fenced block contains, as separate commands,
`claude plugin marketplace add ./flex` and
`claude plugin install flex@nullvalues-flex`, with the `git clone
https://github.com/nullvalues/flex` line retained as the step that produces the
`./flex` directory. The block's comments state that `marketplace add` takes a
path (or a GitHub repo) and that `plugin install` takes
`<plugin>@<marketplace>` and never a path.

**C3. Both install paths are shown.** The block (or immediately adjacent prose)
also gives the from-GitHub form —
`claude plugin marketplace add nullvalues/flex` followed by the same
`claude plugin install flex@nullvalues-flex` — and states that the same
`"source": "./"` in the manifest serves both, because it resolves relative to
the marketplace root.

**C4. The `Requirements:` line is preserved** verbatim
(`Requirements: Claude Code, Python 3.11+, uv.`).

**C5. The skill count is four in both places.**
`grep -c 'three skills' README.md` returns `0`. The sentence at ≈ line 99 names
all four skills — `/flex:seed`, `/flex:companion`, `/flex:pairmode`,
`/flex:observability` — and the heading at ≈ line 141 reads
`## The four skills`. The table beneath that heading is not reordered or
otherwise edited.

**C6. No stale internal anchor.** `grep -rn '#the-three-skills' .` (excluding
`node_modules/` and `.git/`) returns nothing; if any link to the renamed
heading exists in `README.md` or `CONTRIBUTING.md`, it is updated in the same
diff.

**C7. The "Marketplace installation is available for registered users"
sentence is either kept accurate or removed.** With `"source": "./"` the local
marketplace add is the documented primary path; the sentence must not imply
local installation is unavailable. Builder's choice — but the resulting prose
must not contradict C2.

### D — CONTRIBUTING's protected-file references are correct

**D1. The protected-file list still names both manifests.**
`CONTRIBUTING.md:102-103`'s bullets for `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` are retained. They are not removed, and the
protected-file mechanism is not weakened to make this story's edit easier.

**D2. The `marketplace.json` bullet gains a pointer to the source
convention.** Its text is extended (not replaced) to state that the plugin
entry's `source` must stay `"./"` so local marketplace adds install the
checkout rather than cloning GitHub, citing `INFRA-291`. This is what stops the
next contributor "fixing" it back to a `github` source.

**D3. No other CONTRIBUTING section is edited.** The diff to `CONTRIBUTING.md`
is confined to the two bullets in D1/D2.

### E — cross-cutting

**E1. `schema_introduces` stays `false`.** No table, migration, or persistent
state object is introduced, so `docs/phases/phase-111.md` § Schema delivery
owes no row.

**E2. No code outside `tests/` changes.** The diff contains no edit to any file
under `skills/`, `hooks/`, or `docs/` other than this story file. In
particular `skills/pairmode/scripts/pairmode_migrate.py` is untouched — that is
INFRA-292's file.

**E3. `docs/architecture.md` is not edited.** The marketplace source is a
packaging detail, not a documented architectural decision; `architecture.md`'s
existing mentions (`:134`, `:1703`, `:3447`) describe the file's role, not its
`source` value, and remain true. `touches` therefore correctly omits it.

**E4. The full suite is green** (`tests/pairmode/`), run once **without `-x`**
so a pre-existing failure cannot mask a new one.

## Instructions

You are the builder. Work only in this repository, inside your story worktree.
Build in order A → B → C → D; run the suite after B and again at the end.

**0. Re-read before editing.** The line numbers in this spec are anchors, not
coordinates. Read `.claude-plugin/marketplace.json`, `README.md`'s
`## Installation` and `## The three skills` sections, and `CONTRIBUTING.md`'s
protected-file list as they exist *now* before changing anything.

**1. (A) Change the source.** In `.claude-plugin/marketplace.json`, replace

```json
      "source": {
        "source": "github",
        "repo": "nullvalues/flex"
      },
```

with

```json
      "source": "./",
```

Touch nothing else in the file. Do not bump the version — the version is
governed by `test_version_match.py` and by the `HARNESS001-ante1` agreement
that plugin and pairmode versions bump together; an incidental bump here
breaks that pairing.

**2. (B) Write the guard test.** Create
`tests/pairmode/test_plugin_manifest.py`. Follow
`tests/pairmode/test_version_match.py`'s idiom for locating the repo root and
loading the two manifests; do not import from it (keep the modules
independent). Two tests: the `source == "./"` assertion (B2) and the
plugin-name agreement (B3). Put the *reason* in each assertion message, not
only in a comment — this is the file a future contributor will hit when they
try to restore the github source, and the message is the only explanation they
will see.

**3. (C) Rewrite the README install block.** Replace the two fake commands.
The block should read as a sequence a reader can paste:

```bash
# Clone the repo, then register it as a local marketplace
git clone https://github.com/nullvalues/flex
claude plugin marketplace add ./flex

# Install the plugin from that marketplace
claude plugin install flex@nullvalues-flex
```

plus the from-GitHub variant (C3). Keep the `Requirements:` line. Then fix the
skill count in the sentence below the block and in the `## The three skills`
heading (C5) — the table under that heading already lists four skills and must
not be touched.

Do **not** rewrite `docs/brief.md` or `docs/reconstruction.md`, which carry the
same "three skills" claim. They are out of scope (see § Out of scope); the
dossier scopes this story to the install-flow documentation.

**4. (D) Amend CONTRIBUTING.** Extend the `marketplace.json` bullet with the
source-convention note (D2). Leave the rest of the protected-file section
alone.

**5. Protected file justification.** `.claude-plugin/marketplace.json` is on
the protected list. The `## Protected file justification` section below is the
required statement; the reviewer checks it against the diff. Do not remove the
file from the protected list to avoid the check — the protection is doing its
job here, and D2 strengthens it.

**6. Ideology note (Step 4a — checked, resolved inline, no conflict).** Two
entries shaped this spec. *"Rationale-bearing decisions over bare rules"* is
why B2's assertion message and D2's CONTRIBUTING note are Ensures rather than
niceties: `"source": "./"` looks like an omission to anyone who does not know
that a `github` source defeats local marketplace adds, and the "obvious fix"
of restoring the repo URL is exactly the regression this story exists to
prevent — the reason has to live next to the value. *"Never silently pass
contradictions"* is why the change is guarded by a test at all rather than
being a one-line JSON edit: an install path that silently installs a different
tree than the one you are editing is precisely the false confidence that
constraint protects against. The *"Hooks are thin relays"* and *"Sidebar owns
all state writes"* constraints are not touched — nothing here runs on a hook
path or writes state. No conflict required flagging.

## Protected file justification

**File:** `.claude-plugin/marketplace.json` (protected per
`CONTRIBUTING.md:103`).

**Reason:** The file's `plugins[0].source` is the defect. A `github` source
makes `claude plugin install flex@nullvalues-flex` clone the published repo
even when the marketplace was added from a local checkout, so a local install
never installs local changes. The fix is confined to that one key
(`"source": "./"`); every other field — marketplace `name`, `owner`,
`metadata`, and the plugin entry's `name`, `description` and `version` — is
unchanged, and `.claude-plugin/plugin.json` is not touched. The version
invariant guarded by `tests/pairmode/test_version_match.py` is unaffected, and
a new guard test (`tests/pairmode/test_plugin_manifest.py`) plus a
`CONTRIBUTING.md` note make the constraint explicit so the value is not
reverted by a later contributor.

## Tests

Run from the story worktree root.

New and adjacent tests first:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_plugin_manifest.py \
  tests/pairmode/test_version_match.py \
  -q 2>&1 | tail -30
```

Then the full suite **without `-x`**:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Machine-checkable Ensures:

```bash
# A1 — source is the local-relative string
PATH=$HOME/.local/bin:$PATH uv run python -c \
  "import json;d=json.load(open('.claude-plugin/marketplace.json'));assert d['plugins'][0]['source']=='./';print('ok')"
grep -c 'nullvalues/flex' .claude-plugin/marketplace.json      # 0

# A3 — still valid JSON
PATH=$HOME/.local/bin:$PATH uv run python -m json.tool .claude-plugin/marketplace.json > /dev/null && echo ok

# C1 — the nonexistent command is gone
grep -rn 'claude code plugin' README.md CONTRIBUTING.md        # no output, exit 1

# C2 — the real commands are present
grep -c 'claude plugin marketplace add' README.md              # >= 1
grep -c 'claude plugin install flex@nullvalues-flex' README.md # >= 1

# C5 — skill count corrected
grep -c 'three skills' README.md                               # 0
grep -c '## The four skills' README.md                         # 1

# D2 — the convention is recorded where the protection lives
grep -n 'INFRA-291' CONTRIBUTING.md                            # one line
```

Acceptance:

- both new tests in `tests/pairmode/test_plugin_manifest.py` pass;
- `tests/pairmode/test_version_match.py` passes with no edit to it (A4);
- every grep above returns the stated result;
- the full suite is green. If a failure appears, verify it reproduces on clean
  `HEAD` before attributing it elsewhere, and say so explicitly in the build
  result.

## Out of scope

- **Skill-name de-namespacing (`/flex:flex:*`).** INFRA-292's entire subject.
  No `skills/*/SKILL.md` frontmatter and no
  `skills/pairmode/scripts/pairmode_migrate.py` line is touched here. The
  README strings written by this story use `/flex:<skill>`, which is correct
  both before and after INFRA-292.
- **Any version bump.** `plugin.json` and `marketplace.json` stay at `0.3.0`.
  Version movement is governed by the `HARNESS001-ante1` agreement and its
  match-guard test, not by a packaging repair.
- **Publishing, releasing, or tagging the plugin**, and any change to how the
  GitHub-hosted marketplace is consumed beyond documenting the command (C3).
- **The "three skills" claim in `docs/brief.md:10` and
  `docs/reconstruction.md:12`.** Same stale count, different documents with
  different audiences and a different review path; the dossier scopes this
  story to the install-flow docs. File it to the CER backlog if it should be
  fixed — do not widen the diff.
- **`docs/architecture.md`'s marketplace references** (`:134`, `:1703`,
  `:3447`). They describe the file's role, which does not change.
- **Weakening or reorganising `CONTRIBUTING.md`'s protected-file mechanism.**
  Only the two bullets in D1/D2 are in scope; the justification requirement
  itself stays exactly as written.
- **An automated install smoke test** (actually invoking `claude plugin
  marketplace add` / `claude plugin install` in CI). That needs a Claude Code
  binary in the test environment and its own reversibility argument; the
  manifest-shape guard in B is the check this story ships.
