---
id: INFRA-370
rail: INFRA
title: Auto-derive model_selector.py's test file into touches: when the module is touched (CER-145)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
  - skills/pairmode/skills/spec-writer/procedure.md
touches:
  - tests/pairmode/test_story_new.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-145 (LOW): three consecutive Phase 116 stories against
`skills/pairmode/scripts/model_selector.py` (INFRA-333, INFRA-334, and their common test
companion) each omitted `tests/pairmode/test_model_selector.py` from `touches:`, even though it is
the direct unit-test file for the story's own `primary_files:` module. Each time the builder
wrote/updated the tests anyway, the reviewer correctly flagged the file as undeclared scope and
left it uncommitted, and the orchestrator had to widen `touches:` after the fact to avoid losing
coverage (INFRA-333 commit cf94af3c, INFRA-334 commit 8cbf3abf). The spec-writer procedure has no
rule auto-including a `primary_files:` module's conventional test path
(`tests/pairmode/test_<module>.py`) in `touches:`. Fix direction: either the spec-writer procedure
auto-derives and includes the primary module's test file, or `story_new.py`'s scaffolding does it
mechanically before spec-writer elaboration runs. Files named:
`skills/pairmode/skills/spec-writer/procedure.md`, `skills/pairmode/scripts/story_new.py`.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- No prior story is a hard prerequisite. **File-overlap ordering:** INFRA-367 (CER-117) and
  INFRA-380 (CER-62) also edit `skills/pairmode/scripts/story_new.py` in the same phase. Build
  serially with respect to those two (any order); this story touches only argument parsing plus a
  new derivation helper, not the rail-creation prompt (INFRA-367) or `_append_to_phase`'s
  phase-manifest glob (INFRA-380).

## Ensures

1. `skills/pairmode/scripts/story_new.py` exposes a module-level derivation helper (name it
   `derive_test_paths`) that, given a list of repo-relative primary-file paths and a project
   directory, returns the repo-relative path `tests/pairmode/test_<stem>.py` for each `.py` primary
   file whose conventional test file **exists on disk**, deduped and in input order. A primary file
   whose conventional test file does not exist contributes nothing; a non-`.py` primary file
   contributes nothing.
2. `story_new.py` accepts a repeatable `--primary-file` option. When supplied, the scaffolded story
   file's frontmatter contains the given paths under `primary_files:` and, under `touches:`, every
   path returned by `derive_test_paths` for them.
   **Forbidden proxy:** printing a hint/warning naming the test file while the written frontmatter
   still omits it — the assertion is on the bytes of the generated story file's `touches:` list.
3. Derivation never duplicates: a test path already present in `primary_files:` or already listed in
   `touches:` appears exactly once in the generated frontmatter.
4. Scaffolding with no `--primary-file` behaves exactly as before this story — same generated
   frontmatter, same `primary_files`/`touches` keys as the current template emits, no invented
   entries.
5. `skills/pairmode/skills/spec-writer/procedure.md` § Step 4 "Drafting rules" gains a rule stating
   that for each `primary_files:` entry, the conventional unit-test path
   (`tests/pairmode/test_<stem>.py`) must appear in `touches:` when that file exists, and that
   `touches:` may be extended for this reason (resolving the apparent tension with the same
   section's "preserve the existing frontmatter exactly" line, which already carries Step 7's
   `scope:`-finding exception).
6. `tests/pairmode/test_story_new.py` contains tests covering Ensures 1-4.
7. Full `tests/pairmode/` suite green.

## Instructions

1. Add `derive_test_paths(primary_files, project_dir)` to `story_new.py`. Keep it pure and
   filesystem-read-only: map `<any>/<stem>.py` → `tests/pairmode/test_<stem>.py`, keep it only if
   `project_dir / candidate` exists, dedupe preserving order. This project's tests all live flat
   under `tests/pairmode/`; do not attempt to mirror arbitrary source subtrees.
2. Add a repeatable `--primary-file` argument to `story_new.py`'s CLI and thread its values into the
   story-file frontmatter render alongside the derived `touches:` entries. Merge into whatever the
   template already emits for `touches:` rather than replacing it, and dedupe against
   `primary_files:` (Ensures 3).
3. Do not change the interactive rail-creation prompt or `_append_to_phase` — those are INFRA-367's
   and INFRA-380's surfaces in this same phase.
4. Add the drafting rule to `procedure.md` § Step 4 (Ensures 5). One or two sentences; this file is
   the spec-writer's own contract and INFRA-357's brevity counter-instruction applies to edits of it
   as much as to specs written from it.
5. Add tests to `tests/pairmode/test_story_new.py`: derivation with an existing test file, with a
   missing test file, with a non-`.py` primary file, dedupe when the test path is already declared,
   and a no-`--primary-file` invocation asserting the generated frontmatter is unchanged. Assert on
   generated file contents (parse the frontmatter), not on stdout.

Ideology note: the fix is placed in mechanical scaffolding *and* the written procedure rather than
the procedure alone, preserving "codifying policy over implicit convention" — a prose-only rule is
exactly the implicit convention that failed three consecutive times in Phase 116.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green, including the new derivation and no-`--primary-file` regression tests.

## Out of scope

- Retroactively widening `touches:` on already-complete stories (INFRA-333/INFRA-334 and any other
  historical omission). This story changes future scaffolding and future spec drafting only.
- Adding the derivation as a blocking gate in `flex_build.py spec-preflight` or the reviewer's scope
  check. Preflight already emits informational `scope:` findings for paths named in the story body;
  making omission a hard failure is a separate decision and belongs in a CER, not here.
- Any test-path convention other than flat `tests/pairmode/test_<stem>.py` (e.g. mirrored source
  subtrees, integration-test directories, non-Python primary files).
