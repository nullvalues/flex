---
id: INFRA-308
rail: INFRA
title: Plugin-manifest skill guard: glob-derived expectations with anti-vacuity floor
status: complete
phase: "115"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_plugin_manifest.py
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`tests/pairmode/test_plugin_manifest.py` guards the invariant that every
top-level skill's frontmatter `name:` is **bare** — no `flex:` prefix — because
Claude Code already namespaces an installed plugin's skills as
`<plugin.json name>:<skill name>`, so a frontmatter name that bakes in the
prefix produces a doubled `/flex:flex:*` command (INFRA-292). The guard is
correct but its input is a hand-written dictionary: `_EXPECTED_SKILL_NAMES`
(`tests/pairmode/test_plugin_manifest.py:30-35`) hardcodes exactly the four
skills that existed when INFRA-291 wrote it (`seed`, `companion`, `pairmode`,
`observability`), and `test_skill_md_names_are_bare_not_double_namespaced`
(`:84-100`) iterates only that dictionary. A fifth top-level skill would ship
completely unguarded: nothing fails, nothing warns, and the `flex:` regression
the test exists to catch simply stops being checked for the new skill. That is
CER-109 — a written-never-read shape in reverse, where the codebase grows a
file the guard was supposed to cover and the guard silently narrows.

The fix is to derive the expectation set from the filesystem instead of
restating it: glob `skills/*/SKILL.md`, take the expected bare name from each
file's parent directory basename. That makes the guard self-maintaining — a
fifth skill is covered the moment its directory exists. The cost of deriving
expectations from the thing being tested is vacuity: a glob that matches
nothing produces an empty loop and a green test, which is strictly worse than
the hardcoded dictionary it replaced. So the derivation must ship with an
**anti-vacuity floor** — the derived set is asserted non-empty and at least as
large as today's four — in the same story, not as a follow-on.

This is the smallest story in Phase 115 and it touches one test file. It
drains CER-109 (LOW, filed by the phase-111 security audit) and closes the
last observability-rail guard defect before the 0.3.1 backlog truth pass in
INFRA-310.

## Requires

- `tests/pairmode/test_plugin_manifest.py` exists and defines
  `_REPO_ROOT` (`:28`), `_EXPECTED_SKILL_NAMES` (`:30-35`),
  `_frontmatter_name` (`:38-42`), `_read_marketplace` (`:45`), `_read_plugin`
  (`:51`), `_flex_marketplace_entry` (`:55`), and three tests:
  `test_marketplace_flex_source_is_local_relative` (`:62`),
  `test_plugin_and_marketplace_names_agree` (`:73`), and
  `test_skill_md_names_are_bare_not_double_namespaced` (`:84`).
- `_EXPECTED_SKILL_NAMES` is consumed at exactly one site — `:85`. Verify
  before building: `grep -rn '_EXPECTED_SKILL_NAMES' tests/ skills/` returns
  only `:30` and `:85`.
- `skills/*/SKILL.md` matches exactly four files today —
  `skills/companion/SKILL.md`, `skills/observability/SKILL.md`,
  `skills/pairmode/SKILL.md`, `skills/seed/SKILL.md` — and each carries a bare
  `name:` equal to its directory basename.
- Nested `SKILL.md` and `procedure.md` files under `skills/pairmode/` —
  `skills/pairmode/gate_worker/SKILL.md` (`name: flex:gate-worker-procedure`)
  and the eight `skills/pairmode/skills/*/procedure.md` files (all
  `name: flex:*-procedure`) — deliberately carry prefixed names. They are
  plugin-versioned procedure skills, not installed top-level skills, and the
  single-level `skills/*/SKILL.md` glob must not reach them.
- The recorded `main` baseline for the full suite is 4116/211; this story's
  edits must not move either number except by the tests it adds.

## Ensures

**1. Expectations are derived, not restated.** `_EXPECTED_SKILL_NAMES` is gone
from the module. In its place a helper — e.g.
`_derive_expected_skill_names(root: pathlib.Path) -> dict[str, str]` — returns
a mapping of each `skills/*/SKILL.md` path found under `root` to the expected
bare name, where the expected name is the **parent directory's basename**
(`skills/seed/SKILL.md` → `"seed"`). Iteration order is deterministic
(`sorted(...)`). The glob is single-level `skills/*/SKILL.md` — not `**` — so
`skills/pairmode/gate_worker/SKILL.md` and the nested
`skills/pairmode/skills/*/procedure.md` files are not matched.
`grep -c '_EXPECTED_SKILL_NAMES' tests/pairmode/test_plugin_manifest.py`
returns `0`.

**2. The helper is root-parameterised so it is testable against a fixture.**
`_derive_expected_skill_names` takes the repository root as an argument and
does not close over `_REPO_ROOT`. The real-repo test passes `_REPO_ROOT`; the
fixture tests pass a `tmp_path`. Likewise, the per-file bare-name checking is
reachable with a non-`_REPO_ROOT` root — either because
`test_skill_md_names_are_bare_not_double_namespaced` delegates to a
root-taking helper (e.g. `_assert_skill_names_bare(root)`), or by an
equivalent factoring. No test may require mutating the real `skills/`
directory.

**3. The `flex:`-prefix regression is still caught — proven, not assumed.** A
new test builds a `tmp_path` fixture tree containing
`skills/widget/SKILL.md` with frontmatter `name: flex:widget`, runs the
bare-name check against that root inside `pytest.raises(AssertionError)`, and
asserts the raised message names `widget`. A companion case with
`name: widget` passes cleanly. This is the assertion CER-109 says a fifth
skill would ship without.

**4. A fifth skill is auto-covered — proven by fixture.** A test builds a
`tmp_path` tree with five `skills/<name>/SKILL.md` files (the four current
names plus a fifth, e.g. `widget`), calls
`_derive_expected_skill_names(tmp_path)`, and asserts the returned mapping has
five entries and that the fifth's expected name is `"widget"` — i.e. the
derived set gained a member with no edit to the test module. A second
assertion in the same test (or an adjacent one) gives the fifth skill a
`flex:widget` name and asserts the bare-name check fails for it, so
"auto-covered" means covered by the *guard*, not merely present in a dict.

**5. Anti-vacuity floor: an empty or shrunken glob must fail.** A test asserts
against the real repository that
`_derive_expected_skill_names(_REPO_ROOT)` is **non-empty** and has
`len(...) >= 4`, with an assertion message stating that a glob matching
nothing (or fewer files than the four known top-level skills) means the
derivation is broken, not that the repo is clean. The same test asserts
`"pairmode"` is among the derived names — a single named canary so a glob that
silently resolves against the wrong root cannot satisfy the count alone. The
`>= 4` floor is a floor, not an equality: adding a fifth skill must not fail
this test.

**6. The parity assertions are untouched.**
`test_marketplace_flex_source_is_local_relative` and
`test_plugin_and_marketplace_names_agree`, and the helpers
`_read_marketplace`, `_read_plugin`, `_flex_marketplace_entry` and
`_frontmatter_name`, are unchanged — same names, same bodies, same assertion
messages. `git diff` on the file shows no edit inside `:38-81` other than
whatever the removal of `_EXPECTED_SKILL_NAMES` above it requires. The
INFRA-291/INFRA-292 rationale in the module docstring is retained and extended
with one sentence naming CER-109 and the derivation.

**7. No file outside the test module changes.**
`git diff --name-only HEAD` lists exactly
`tests/pairmode/test_plugin_manifest.py`. No `skills/*/SKILL.md` is edited, no
CER row is annotated here (INFRA-310 owns the backlog pass), and
`docs/architecture.md` is not touched — this story changes a test's input
derivation, not a documented architectural contract.

**8. Suite green.** `tests/pairmode/` runs green, once **without** `-x`, at no
worse than the recorded 4116/211 baseline plus this story's new tests. Any
failure must be shown to reproduce on clean `HEAD` before it is attributed
elsewhere.

## Instructions

You are the builder. This is a single-file change; do not widen it.

**1. Read the file first.** Line numbers in `## Requires` are anchors, not
coordinates. Confirm `_EXPECTED_SKILL_NAMES` still has exactly one consumer
before removing it.

**2. Replace the dictionary with a derivation.** Write
`_derive_expected_skill_names(root)` using
`sorted(root.glob("skills/*/SKILL.md"))`, keying by the path (absolute or
repo-relative — pick one and use it consistently in assertion messages) and
valuing by `path.parent.name`. Keep the module stdlib-only: `json`,
`pathlib`, `re` are already imported; add nothing beyond `pytest` for
`pytest.raises`. Do **not** use `**` — the single-level glob is load-bearing
(`## Requires`, nested-skill note); add a one-line comment saying so, naming
`skills/pairmode/gate_worker/SKILL.md` as the file the single level excludes
and why (it is a plugin-versioned procedure skill whose `flex:`-prefixed name
is correct).

**3. Factor the bare-name check to take a root.** The existing loop body —
the `actual_name == expected_name` assertion and the `":" not in actual_name`
assertion, both with their current messages — moves into a root-taking helper.
`test_skill_md_names_are_bare_not_double_namespaced` becomes a one-line call
against `_REPO_ROOT`. Preserve both assertion messages verbatim; they carry
the INFRA-292 rationale and are the only place it is written down in this
module.

**4. Write the fixture tests.** A small factory helper that writes
`root/skills/<name>/SKILL.md` with a given frontmatter name keeps the three
fixture tests (Ensures 3, 4) short. Frontmatter must match what
`_frontmatter_name`'s regex expects (`^name:\s*(\S+)\s*$`, MULTILINE) — write
a real `---`-delimited block, not a bare line, so the fixture exercises the
same parse path as the repo files.

**5. Write the anti-vacuity test last** (Ensures 5), against `_REPO_ROOT`.
Its assertion message is the point: it must tell a future reader that a green
empty glob is the failure mode being prevented. Cite CER-109 in it.

**6. Ideology note (Step 4a — resolved inline, no conflict).** The
anti-vacuity floor exists because of *"Never silently pass contradictions"*:
a guard that derives its expectations from the tree it guards can pass by
finding nothing, which is precisely the false confidence that constraint names
as worse than no system at all — so the derivation ships with its own floor in
the same story rather than as a follow-on. *"Rationale-bearing decisions over
bare rules"* is why steps 2, 3 and 5 all insist the reasoning (single-level
glob, INFRA-292 messages, the vacuity failure mode) is written into comments
and assertion messages rather than left implicit in the code shape. No
constraint or prototype fingerprint is contradicted: the change is Python,
pytest, stdlib-only, and touches no hook, pipe, or state-writing path.

## Tests

Run from the story worktree root. The target file first:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_plugin_manifest.py -q 2>&1 | tail -20
```

Then the adjacent doc/skill guards, to catch collateral damage:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_plugin_manifest.py \
  tests/pairmode/test_skill_md.py \
  tests/pairmode/test_version_match.py \
  tests/pairmode/test_docs.py \
  -q 2>&1 | tail -20
```

(Skip any of the above that does not exist in the tree; do not create it.)

Then the full suite **without `-x`**, so a known failure cannot mask a new one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -20
```

Machine-checkable Ensures:

```bash
# 1 — the hardcoded dict is gone
grep -c '_EXPECTED_SKILL_NAMES' tests/pairmode/test_plugin_manifest.py        # 0

# 1 — single-level glob only, no recursive form
grep -c 'skills/\*\*' tests/pairmode/test_plugin_manifest.py                  # 0
grep -c 'skills/\*/SKILL.md' tests/pairmode/test_plugin_manifest.py           # >= 1

# 6 — the parity tests still exist by name
grep -c 'def test_marketplace_flex_source_is_local_relative' \
  tests/pairmode/test_plugin_manifest.py                                      # 1
grep -c 'def test_plugin_and_marketplace_names_agree' \
  tests/pairmode/test_plugin_manifest.py                                      # 1

# 7 — one file changed
git diff --name-only HEAD                                                     # exactly the test file
```

Acceptance:

- every new test passes, and the three pre-existing tests pass with no edit to
  their assertion messages;
- the fixture tests in Ensures 3 and 4 fail loudly if the derivation or the
  bare-name check is removed — confirm by deleting the check locally, watching
  them fail, and restoring it (report that you did this);
- the full suite is green at the 4116/211 baseline plus the new tests.

## Out of scope

- **Extending the guard to nested procedure skills**
  (`skills/pairmode/skills/*/procedure.md`,
  `skills/pairmode/gate_worker/SKILL.md`). Their `flex:`-prefixed names are
  correct: they are loaded by path as plugin-versioned procedure documents,
  not installed as top-level plugin skills, so the doubled-namespace defect
  INFRA-292 describes does not apply to them. The single-level glob is the
  boundary, and Ensures 1 pins it.
- **The skill-count parity assertion in the doc-currency sweep.** INFRA-305
  (Phase 114, CER-112) pins prose claims of "four skills" against
  `len(glob('skills/*/SKILL.md'))` in the documentation tests. That is a
  different test file with a different subject (docs vs. manifest); this story
  does not add, move, or depend on it, and does not touch `docs/brief.md`,
  `docs/reconstruction.md`, or `README.md`.
- **Annotating the CER-109 row RESOLVED.** INFRA-310 executes the backlog
  truth pass for the whole era; annotating here would split the record across
  two commits and two stories.
- **Validating `SKILL.md` frontmatter beyond `name:`** (description, version,
  required sections). The module's subject is the manifest/namespace
  invariants from INFRA-291/292; a general frontmatter schema check for skills
  is a new capability and belongs in its own story if it is wanted.
- **Deriving `plugin.json` or `marketplace.json` expectations from the
  filesystem.** Those two assertions compare two committed manifests against
  each other, which is already derivation-free in the right way; Ensures 6
  freezes them.
