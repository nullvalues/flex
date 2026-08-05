---
id: INFRA-392
rail: INFRA
title: Scaffold EXEMPLAR-000.md into downstream projects via bootstrap/sync/audit (CER-171)
status: complete
phase: "124"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/sync.py
  - skills/pairmode/scripts/audit.py
  - docs/exemplars/EXEMPLAR-000.md
touches:
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_sync.py
  - tests/pairmode/test_audit.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

`docs/exemplars/EXEMPLAR-000.md` is the spec-writer procedure's frozen bounded
input 4 (`skills/pairmode/skills/spec-writer/procedure.md` § Input contract
item 4, INFRA-363) — every spec-writer run on every flex-bootstrapped project
reads exactly this file for structural format. It exists in flex's own repo
only because INFRA-363 hand-authored it directly; it was never added to
`bootstrap.py`'s `SCAFFOLD_FILES`/`AGENT_FILES`/`NARRATIVE_FILES`,
`sync.py`'s backfill path, or `audit.py`'s `CANONICAL_FILES`/`SCAFFOLD_FILES`
(zero `EXEMPLAR` hits across all three). A downstream project's spec-writer
run degrades gracefully to a built-in section-list fallback when the file is
absent, but the gap is silent and permanent — no bootstrap, sync, or audit
path can ever surface or fix it (CER-171; same "structurally excluded from
scaffolding" shape as `.pairmode-overrides`, CER-165). This story closes the
gap end-to-end: `bootstrap.py` scaffolds the file for new projects,
`sync.py` can backfill it for existing projects missing it (already true for
free once it is registered in `audit.py`'s `CANONICAL_FILES`, since
`sync.py`'s `_dest_to_template` resolves against that same list), and
`audit.py` flags it MISSING/INCONSISTENT like any other canonical file.

## Requires

- CER-171 filed in `docs/cer/backlog.md` (this story's own filing).
- `docs/exemplars/EXEMPLAR-000.md` exists in this repo (INFRA-363) as the
  source of the new template's literal content.

## Ensures

- `docs/exemplars/EXEMPLAR-000.md` is registered as a `CANONICAL_FILES`
  entry in `skills/pairmode/scripts/audit.py` (not `SCAFFOLD_FILES` — its
  content is harness-owned and frozen, not project-specific prose a project
  should freely diverge on), with destination path
  `docs/exemplars/EXEMPLAR-000.md` and template
  `docs/exemplars/EXEMPLAR-000.md.j2`.
- `skills/pairmode/templates/docs/exemplars/EXEMPLAR-000.md.j2` exists and,
  rendered with no context variables, is byte-identical to the current
  `docs/exemplars/EXEMPLAR-000.md` content (a literal copy — no Jinja
  variables — matching the file's own frozen contract).
- Running `bootstrap.py` against a fresh project directory (no pre-existing
  `docs/exemplars/EXEMPLAR-000.md`) creates
  `<project>/docs/exemplars/EXEMPLAR-000.md` with that same content.
- Running `bootstrap.py` against a project directory that already has a
  `docs/exemplars/EXEMPLAR-000.md` does not overwrite it (mirrors
  `AGENT_FILES`'s skip-if-exists-unless-forced contract) — either reuse the
  existing `--force-agents` flag for this file or add an equivalently-scoped
  new flag; whichever is chosen, the skip/force behaviour must be covered by
  a test.
- `skills/pairmode/scripts/audit.py audit --project-dir <project>` against a
  project directory with no `docs/exemplars/EXEMPLAR-000.md` reports it as
  MISSING (via the existing `CANONICAL_FILES` comparison pass — no bespoke
  check needed once the registry entry exists).
- `skills/pairmode/scripts/sync.py sync --project-dir <project> --yes`
  against a project directory with no `docs/exemplars/EXEMPLAR-000.md`
  creates it with the canonical content (via the existing
  `_dest_to_template`/missing-file backfill path — no bespoke sync logic
  needed once the registry entry exists).
- A new regression test, modeled on
  `TestCanonicalFilesAgentFilesConsistency` (`tests/pairmode/test_audit.py`),
  asserts `docs/exemplars/EXEMPLAR-000.md` is present in `audit.py`'s
  `CANONICAL_FILES` destination set.

## Instructions

1. Create `skills/pairmode/templates/docs/exemplars/EXEMPLAR-000.md.j2` as a
   literal copy of the current `docs/exemplars/EXEMPLAR-000.md` content — no
   Jinja `{{ }}` interpolation. This mirrors the "frozen, harness-owned,
   never hand-diverged" contract `NARRATIVE_FILES` and `AGENT_FILES` already
   use for content that must stay identical fleet-wide.
2. In `skills/pairmode/scripts/bootstrap.py`, scaffold the new file for a
   fresh project. The simplest shape that satisfies Ensures is to add a
   `("docs/exemplars/EXEMPLAR-000.md", "docs/exemplars/EXEMPLAR-000.md.j2")`
   entry to a registry that gets the same skip-if-exists-unless-forced
   treatment `AGENT_FILES` already gets (either add it to `AGENT_FILES`
   directly, or introduce a small parallel list reusing the same write loop
   and `--force-agents` flag) — trust ordinary engineering judgment on
   which is tidier; either is acceptable as long as skip/force behaviour is
   tested.
3. In `skills/pairmode/scripts/audit.py`, add
   `("docs/exemplars/EXEMPLAR-000.md", "docs/exemplars/EXEMPLAR-000.md.j2")`
   to `CANONICAL_FILES`. No other change to `audit.py` should be required —
   `audit_project`'s existing `CANONICAL_FILES` comparison pass (section
   splitting, MISSING/INCONSISTENT/EXTRA classification) already covers any
   new `CANONICAL_FILES` entry generically.
4. `skills/pairmode/scripts/sync.py` imports `CANONICAL_FILES` from
   `audit.py` and its `_dest_to_template`/missing-file backfill path already
   handles any `CANONICAL_FILES` entry generically — confirm this by test
   (Tests below) rather than adding new sync.py logic; if the confirming
   test reveals a gap, fix it minimally rather than special-casing this one
   file.
5. Add a comment at the new `CANONICAL_FILES`/bootstrap-registry entries
   cross-referencing this story (INFRA-392/CER-171), mirroring the existing
   `AGENT_FILES`/`CANONICAL_FILES` mirroring comments already in both files.
6. Tests: add coverage to `tests/pairmode/test_bootstrap.py` (file created
   on fresh bootstrap; skipped when already present unless forced — model on
   the existing `shadow-reviewer.md` scaffold tests, e.g.
   `test_shadow_reviewer_agent_shell_created`), `tests/pairmode/test_audit.py`
   (MISSING reported when absent; new file present in `CANONICAL_FILES`,
   modeled on `TestCanonicalFilesAgentFilesConsistency`), and
   `tests/pairmode/test_sync.py` (sync backfills the file when missing).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py tests/pairmode/test_audit.py tests/pairmode/test_sync.py -q
```
Acceptance: green, including the new EXEMPLAR-000.md scaffold/audit/sync
tests described in Instructions step 6.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q --tb=no
```
Acceptance: full suite green (no regression to `CANONICAL_FILES`/`sync`
consumers elsewhere).

## Out of scope

- Backfilling `docs/exemplars/EXEMPLAR-000.md` into any real downstream
  project's repo (a `sync`/`sync-all` operational run against the live
  fleet) — this story only builds the mechanism; running it fleet-wide is a
  separate operational step.
- Changing `EXEMPLAR-000.md`'s own content, or the spec-writer procedure's
  bounded-input contract — this story only makes the existing frozen file
  reproducible via bootstrap/sync/audit, it does not touch what the file
  says.
- Adding a second exemplar file or any exemplar-rotation mechanism —
  INFRA-363 already deliberately rejected rotation; this story preserves
  the single-frozen-file design.
