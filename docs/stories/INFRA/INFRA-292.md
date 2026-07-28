---
id: INFRA-292
rail: INFRA
title: De-namespace SKILL.md skill names (flex:X -> X) to fix doubled /flex:flex:* plugin commands
status: draft
phase: "111"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/seed/SKILL.md
  - skills/companion/SKILL.md
  - skills/pairmode/SKILL.md
  - skills/observability/SKILL.md
touches:
  - skills/pairmode/scripts/pairmode_migrate.py
  - tests/pairmode/test_plugin_manifest.py
  - tests/pairmode/test_pairmode_migrate.py
  - docs/stories/INFRA/INFRA-292.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This is the second of Phase 111's two packaging-repair defects, both found on a
fresh-machine plugin install. INFRA-291 fixed the install failing outright
(marketplace `source`); this one fixes what the operator sees *after* a
successful install: every flex skill surfaces as `/flex:flex:seed`,
`/flex:flex:companion`, `/flex:flex:pairmode`, `/flex:flex:observability`.

The cause is a doubled namespace. Claude Code namespaces an installed plugin's
skills as `<plugin-name>:<skill-name>`, and `.claude-plugin/plugin.json`
already declares `"name": "flex"`. All four `skills/*/SKILL.md` frontmatters
additionally bake the plugin prefix into the *skill* name
(`name: flex:seed`, `name: flex:companion`, `name: flex:pairmode`,
`name: flex:observability`), so the prefix is applied twice.

The fix is to make the frontmatter names bare (`seed`, `companion`,
`pairmode`, `observability`). The installed command shape then becomes
`/flex:<skill>` — which is exactly the string that roughly forty existing
references across the repo already assume (`audit.py`, `lesson_utils.py`,
`global_session_check.py`, `pairmode_status.py`, `sidebar.py`, `README.md`,
`docs/brief.md`, the SKILL.md body section headers, the Jinja templates). None
of those strings change: they are already correct and only became wrong *in
practice* because the frontmatter added a second prefix. This story is
therefore a four-line frontmatter correction plus one downstream ripple, not a
rename campaign — resist the urge to touch any `/flex:*` string.

The one ripple is `skills/pairmode/scripts/pairmode_migrate.py`. Migration
rule 8 (the anchor→flex rewrite applied to sibling projects) contains
`(r"\bname:\s*anchor:seed\b", "name: flex:seed")`, which would stamp the same
doubled-namespace defect into every downstream repo migrated from anchor. It
must produce the bare `name: seed`.

Recon already performed for the builder (do not redo it):

- The only `name: flex:*` frontmatter values in the repo outside the four
  target files are the nested procedure skills
  (`skills/pairmode/skills/*/procedure.md`,
  `skills/pairmode/gate_worker/SKILL.md`). Those are loaded by path, not
  installed as top-level plugin skills, and are **out of scope** (see below).
- No test asserts a literal `name: flex:*` frontmatter value.
  `tests/pairmode/test_skill_md.py`'s `flex:` hits are body section headers
  (`### \`/flex:pairmode bootstrap\``) and stay correct.
  `tests/pairmode/test_global_session_check.py:110` writes
  `name: flex:pairmode` only as inert fixture text — the parser under test
  reads `pairmode_version:`, never `name:` — so it may be left alone or
  updated for tidiness; either passes.
- `tests/pairmode/test_pairmode_migrate.py` builds anchor-era fixtures
  containing `name: anchor:seed` (lines ~119 and ~476) but asserts nothing
  about the rewritten value today.

## Requires

- INFRA-291 complete (already landed on `main` as `b9288e66`): the plugin must
  actually install from a local checkout before the installed skill names are
  observable.
- `.claude-plugin/plugin.json` declares `"name": "flex"` (unchanged by this
  story — it is the outer half of the namespace and is on CONTRIBUTING.md's
  protected-file list).
- Working tree clean at HEAD on `main`.

## Ensures

1. `skills/seed/SKILL.md` frontmatter has `name: seed`;
   `skills/companion/SKILL.md` has `name: companion`;
   `skills/pairmode/SKILL.md` has `name: pairmode`;
   `skills/observability/SKILL.md` has `name: observability`. Each value
   contains no `:` character.
2. Every other frontmatter key in those four files is byte-identical to HEAD —
   in particular `skills/pairmode/SKILL.md` still carries
   `pairmode_version: "0.3.0"`, and `description`, `allowed-tools`,
   `argument-hint`, and `disable-model-invocation` are unchanged wherever
   present. `PATH=$HOME/.local/bin:$PATH uv run pytest
   tests/pairmode/test_version_match.py -q` stays green.
3. No `/flex:` command string anywhere in the repo is altered. `git diff
   --unified=0 HEAD -- ':!docs/stories'` contains no line that adds or removes
   a `/flex:` token; the SKILL.md body H1 headings (`# flex:pairmode`,
   `# flex:observability`) and all `### \`/flex:pairmode <sub>\`` section
   headers are unchanged.
4. `skills/pairmode/scripts/pairmode_migrate.py` rule 8's seed-name pattern
   rewrites to the bare form: the replacement string is `name: seed`, not
   `name: flex:seed`. `grep -c 'name: flex:seed'
   skills/pairmode/scripts/pairmode_migrate.py` returns 0.
5. `tests/pairmode/test_plugin_manifest.py` gains a test that reads all four
   real `skills/*/SKILL.md` files from the repo (not fixtures, matching that
   file's existing `_REPO_ROOT` idiom), parses the `name:` frontmatter line
   with stdlib only, and asserts each equals the expected bare name and
   contains no `:`. The test fails if reverted to `name: flex:seed`.
6. `tests/pairmode/test_pairmode_migrate.py` gains (or extends) an assertion
   that after rule 8 runs against a fixture containing `name: anchor:seed`,
   the migrated file contains `name: seed` and does **not** contain
   `name: flex:seed`.
7. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` completes
   with no failures other than the known pre-existing
   `test_observability_ui.py::test_ui_build_emits_dist_index_html`
   worktree-only failure (acceptable only if it reproduces on clean HEAD).

## Instructions

1. Edit the `name:` line of each of the four top-level SKILL.md files to its
   bare form. Change nothing else in those files — not the description, not the
   body, not the H1 heading. Four single-line edits total.

2. In `skills/pairmode/scripts/pairmode_migrate.py`, change rule 8's pattern
   tuple `(r"\bname:\s*anchor:seed\b", "name: flex:seed")` so the replacement
   is `"name: seed"`. Leave the regex itself and every other rule untouched —
   in particular rule 8's second pattern (`/anchor:seed` → `/flex:seed`) is
   *correct* and must stay, because that one rewrites an invocation string, not
   a frontmatter name.

3. Add the SKILL.md-name guard to `tests/pairmode/test_plugin_manifest.py`
   rather than a new file: that module already exists to guard exactly this
   class of fresh-install packaging invariant (INFRA-291), is stdlib-only, and
   already reads the shipped files via `_REPO_ROOT`. Give it a docstring
   sentence naming the defect it prevents (doubled `/flex:flex:*` namespace)
   and the reason bare names are correct (Claude Code prefixes with the
   `plugin.json` name). Parse the frontmatter with a small regex or a
   line-scan; do not add a YAML dependency.

4. Add the migrate-rule assertion to `tests/pairmode/test_pairmode_migrate.py`
   by extending the existing rule-8 exercise (the fixtures at ~line 119 and
   ~line 476 already write `name: anchor:seed`) rather than building a new
   fixture tree.

5. Do not run any `claude plugin` command, and do not attempt to verify the
   installed command shape from inside this repo — the invariant is asserted
   statically by the tests above. Verification against a real install is the
   operator's, at checkpoint.

6. Ideology note (Step 4a, resolved inline): `docs/ideology.md` § Free to
   change says "file layout within `skills/` — the public interface is the
   SKILL.md contract, not the internal directory structure." This story changes
   that public contract deliberately, so the instructions above pin the change
   to the frontmatter `name:` key only and require the tests in Ensures 5–6 to
   record the new contract — preserving the "codify policy over implicit
   convention" conviction rather than leaving the corrected naming rule as
   tribal knowledge. No conviction or accepted constraint is contradicted; the
   hook-pipe-sidebar constraints are untouched by this story.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_plugin_manifest.py \
  tests/pairmode/test_pairmode_migrate.py \
  tests/pairmode/test_skill_md.py \
  tests/pairmode/test_version_match.py -q
```

Then the full suite, without `-x` so the known pre-existing failure does not
mask a real one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:** the targeted run is fully green; the full run reports no
failures except `test_observability_ui.py::test_ui_build_emits_dist_index_html`
if and only if that failure also reproduces on clean HEAD.

## Out of scope

- **The nested procedure skills.** `skills/pairmode/skills/*/procedure.md`
  (`flex:builder-procedure`, `flex:reviewer-procedure`,
  `flex:spec-writer-procedure`, `flex:security-auditor-procedure`,
  `flex:intent-reviewer-procedure`, `flex:loop-breaker-procedure`,
  `flex:checkpoint-docs-procedure`) and `skills/pairmode/gate_worker/SKILL.md`
  (`flex:gate-worker-procedure`) keep their prefixed names. They are loaded by
  file path by leaf workers, not surfaced as installed plugin commands, so they
  exhibit no doubling. Renaming them would be a separate, riskier change.
- **Any `/flex:<skill>` invocation string** in scripts, docs, templates, or
  SKILL.md bodies. All ~40 are already correct post-fix.
- **`docs/phase-prompts.md:40` and `docs/phases/phase-36.md:116`**, which quote
  `name: flex:pairmode` / `name: flex:seed` as historical planning text. These
  are archival records of what was decided then; they are not read by any tool.
- **`.claude-plugin/plugin.json`** — the `"name": "flex"` outer namespace is
  correct and the file is protected.
- **README/CONTRIBUTING install-flow documentation** — INFRA-291's scope.
- **Any migration or re-sync of downstream repos** already carrying the doubled
  name from a prior `migrate-from-anchor` run. Fixing the rule stops the bleed;
  remediating existing consumers is fleet work (Phase 106), not this story.
