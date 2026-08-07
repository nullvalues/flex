---
id: INFRA-415
rail: INFRA
title: Oracle-verify scope-widening frontmatter writes (CER-222)
status: complete
phase: "144"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_flex_build_permissions_widen.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

CER-222: `flex_build.py`'s `_append_touches_entry` (~line 1007-1018, the
mid-build `permissions-widen` path) writes an agent-widened path bare into a
story's `touches:` frontmatter block — `new_item = f"  - {path}"` — with no
verification against the real reader. `story_new.py` already solved the
identical problem for the *create-time* write to the same `touches:` block
(INFRA-412's `_yaml_block_scalar`/`_oracle_render`, CER-214/215/216): render
each representable candidate (bare, `"`-quoted, `'`-quoted), feed it back
through `schema_validator._parse_frontmatter`, and only emit a candidate that
round-trips byte-identical, raising rather than guessing when none does.
`_append_touches_entry` was never routed through that oracle, so it silently
reopens the same corruption class (embedded ` #`, a trailing `---`, a
bracket-prefixed value, etc.) at the one write site that fires on every
scope-widening event during an active build — per the phase Goal, scope
widening is now one of this project's most common re-build patterns (roughly
every other story), so this path is more load-bearing than the sibling
CER-221 fix, not less. This story closes that gap by making
`_append_touches_entry` call the same shared oracle `story_new.py` already
exports, and by deciding — for the first time on this call path — exactly
what `permissions-widen` does when a widened path is unrepresentable: refuse
loudly via `PermissionsWidenError`, never write a corrupted `touches:` block.

## Requires

- `story_new._yaml_block_scalar` and its underlying `_oracle_render` exist
  and are importable from `skills/pairmode/scripts/story_new.py` (INFRA-412,
  already shipped).
- `flex_build.PermissionsWidenError` exists (already shipped, INFRA-320 § B).

## Ensures

- `_append_touches_entry`'s `new_item` is built by calling
  `story_new._yaml_block_scalar(path)` (imported at module level in
  `flex_build.py`, e.g. `from story_new import _yaml_block_scalar`) instead
  of the bare `f"  - {path}"` interpolation — the emitted list-item text for
  any representable path is byte-identical to what `_yaml_block_scalar`
  returns, not a hand-rolled reconstruction of it.
- For an ordinary representable path — a normal repo-relative path with no
  special YAML characters (e.g. `skills/pairmode/scripts/foo.py`), a path
  containing a literal space (e.g. `docs/some dir/notes.md`), and a path
  containing a `#` that is *not* preceded by a space (e.g.
  `skills/pairmode/scripts/pkg#1.py`, which is not a YAML comment
  introducer and round-trips bare) — `widen_story_scope` still writes the
  path into the story's `touches:` block exactly as before this story
  (Ensures 1 of the pre-existing `test_flex_build_permissions_widen.py`
  suite continues to pass unmodified), the `## Scope widenings` row is still
  appended, and the regenerated permissions artifact at
  `docs/phases/permissions/<story_id>.json` still lists the path in
  `allowed_paths` — i.e. routing through the oracle does not regress, slow,
  or add friction to the common successful-widening path.
- For a path that does not round-trip through `schema_validator._parse_frontmatter`
  as a block-sequence item — at minimum a path containing a literal ` #`
  (space-hash: an unquoted YAML comment introducer,
  e.g. `docs/some dir/note #1.md`), and a path with an embedded real newline
  — `story_new._yaml_block_scalar` raises `ValueError`; `_append_touches_entry`
  (or its caller `_widen_frontmatter_touches`) catches that `ValueError` and
  re-raises `flex_build.PermissionsWidenError`, naming the unrepresentable
  path verbatim in the message (e.g. via `repr(path)`) and stating that the
  path could not be safely written into `touches:`.
- When that `PermissionsWidenError` is raised, **no file on disk changes**:
  the story spec file is byte-identical before and after the call (no
  partial `touches:` write, no `## Scope widenings` row added), and
  `docs/phases/permissions/<story_id>.json` is not created/modified. Forbidden
  proxy (INFRA-314): a corrupted or partially-written `touches:` entry that
  merely fails a later validation pass is not acceptable — the write itself
  must never happen.
- `flex_build.py`'s `cmd_permissions_widen` (the `permissions-widen` CLI
  command) surfaces that `PermissionsWidenError` the same way it already
  surfaces every other refusal on this path (§ B2's protected-path/
  out-of-root refusals): caught by the existing `except PermissionsWidenError`
  clause, echoed to stderr as `permissions-widen: <message>`, and the process
  exits with status 1 — never an uncaught traceback, and never a 0 exit with
  the corrupted-write forbidden proxy from the previous bullet.
- A regression test exercises the unrepresentable-path refusal end-to-end
  through `widen_story_scope` (or the CLI), asserting: `PermissionsWidenError`
  (or, for the CLI, non-zero exit) is raised/returned, the story file is
  unchanged, and no permissions artifact is written.
- A regression test exercises at least the three representable path shapes
  named above (normal path, space-bearing path, non-comment `#`-bearing
  path) through `widen_story_scope`, asserting each is written into
  `touches:` and readable back out — i.e. the story file's `touches:` list,
  re-parsed via `schema_validator._parse_frontmatter`, contains the exact
  original path string (not a quoted or otherwise mangled form) for every
  case where a bare rendering round-trips.

## Instructions

1. In `skills/pairmode/scripts/flex_build.py`, add a module-level import of
   the shared oracle: `from story_new import _yaml_block_scalar` (placed
   alongside the file's other sibling-module imports, e.g. near the
   `schema_validator`/`table_utils` imports). `story_new.py` lives in the
   same `skills/pairmode/scripts/` directory, which `flex_build.py` already
   adds to `sys.path` at module load, so no new path setup is needed.
2. In `_append_touches_entry` (~line 1007-1018), replace
   `new_item = f"  - {path}"` with a call that renders `path` through the
   oracle and converts a `ValueError` into a `PermissionsWidenError`:
   ```python
   try:
       new_item = f"  - {_yaml_block_scalar(path)}"
   except ValueError as exc:
       raise PermissionsWidenError(
           f"cannot represent widened path {path!r} in touches: {exc}"
       ) from exc
   ```
   Keep the rest of `_append_touches_entry`'s block-splicing logic
   (block-key detection, insertion-after-`primary_files`, etc.) unchanged —
   only the `new_item` construction changes.
3. Confirm (by reading, no code change expected) that `PermissionsWidenError`
   raised inside `_append_touches_entry` propagates unmodified through
   `_widen_frontmatter_touches` and `widen_story_scope` up to
   `cmd_permissions_widen`'s existing `except PermissionsWidenError as exc:`
   handler (~line 1262) — that handler already echoes `permissions-widen:
   {exc}` to stderr and exits 1, so no change is needed there unless reading
   confirms otherwise.
4. Add tests to `tests/pairmode/test_flex_build_permissions_widen.py`
   (the existing home of `widen_story_scope`/`permissions-widen` tests —
   not `test_flex_build.py`, which does not currently cover this function):
   - One test per representable path shape named in `## Ensures` (plain
     path, space-bearing path, non-comment `#`-bearing path): call
     `widen_story_scope`, assert the path lands verbatim in `touches:`, and
     assert `schema_validator._parse_frontmatter` (or an equivalent read of
     the story file) recovers the exact original path string.
   - One test for an unrepresentable path (a ` #`-bearing path is the
     simplest reliable trigger): assert `PermissionsWidenError` is raised,
     the story file is byte-identical before/after, and no permissions
     artifact file is created.
   - One CLI-level test (`CliRunner`, mirroring
     `test_permissions_widen_refuses_protected_path_naming_the_glob`)
     confirming an unrepresentable `--path` exits non-zero with the path
     named in `result.output`, not an uncaught traceback.
5. Do not touch `story_new.py` itself — this story only wires
   `flex_build.py`'s existing writer through the already-shipped oracle
   function; `_yaml_block_scalar`'s own behaviour and tests are out of
   scope (see `## Out of scope`).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_permissions_widen.py tests/pairmode/test_flex_build.py -q
```
Acceptance: green, including the new representable-path and
unrepresentable-path-refusal cases, and every pre-existing
`test_flex_build_permissions_widen.py` case (in particular the block-style
append, ordering, idempotency, dry-run, and worktree-artifact tests)
continues to pass unmodified.

## Out of scope

- CER-221 (the sibling `story_new.py`/`_append_to_phase` pipe-escaping fix
  for the phase-manifest Stories-table title) — tracked separately as
  INFRA-414 in this same phase.
- Changing `story_new._yaml_block_scalar`/`_oracle_render`'s own rendering
  or refusal behaviour — this story only calls the existing function; any
  gap in the oracle itself is a `story_new.py`-scoped fix, not this story's.
- CER-223..228 (the other reference-fragility findings from the same
  investigation — phase-manifest/era-doc/index.md writers, and the
  systemic "no codebase invariant" finding) — filed to the CER backlog,
  not in scope here.
- Adding a `permissions-widen --force`/override flag to allow writing an
  unrepresentable path anyway — the fix direction is refuse, not
  best-effort-corrupt; no override path is being added.
