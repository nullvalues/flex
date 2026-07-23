---
id: INFRA-238
rail: INFRA
title: Restore active-story stamping and story-scope enforcement in the worktree loop; retire stale pipe_path reads
status: planned
phase: "98"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/scope_guard.py
  - hooks/pre_tool_use.py
touches:
  - CLAUDE.build.md
  - hooks/stop.py
  - hooks/session_end.py
  - hooks/exit_plan_mode.py
  - hooks/session_start.py
  - skills/pairmode/scripts/pairmode_status.py
  - skills/pairmode/skills/reviewer/procedure.md
  - docs/architecture.md
  - tests/pairmode/test_scope_guard.py
---

## Context

0.2's `CLAUDE.build.md.j2` stamped the active story before every build spawn
(`story_context.py --set` at `:466`) and cleared it after
(`--clear` at `:690`), alongside `permissions-create`/`write-permissions`
(`:462-464`) and `clear-permissions` (`:691`). 0.3's template does none of this: this
repo's own live `.companion/state.json` has no `current_story` key. Consequences,
confirmed by direct code read this session:

- `scope_guard.py:36,61-65` reads `state["current_story"]["id"]`; absent means it
  fails open for every non-`PROTECTED_GLOBS` path — the Phase 55 per-story Edit/Write
  file-scope enforcement (exercised manually this session via `story_context.py
  --set`/`flex_build.py permissions-create` for INFRA-234/235, since nothing does it
  automatically) is otherwise inert.
- `hooks/pre_tool_use.py`'s RELEASE-020 `flex_factor` resolution
  (added 2026-07-21, this week) calls `scope_guard._read_current_story` and always
  falls back to 1.0 with no active story — a feature shipped days ago is dead on
  arrival because of this exact gap.
- `docs/phases/permissions/` generation has also lapsed in practice: files stop at
  `RELEASE-006.json` while stories run past RELEASE-040.
- `docs/architecture.md:229-234` still documents all of this as live.

Per-story git worktrees (INFRA-224, Phase 96) provide *structural* revert-on-FAIL
(discard the whole worktree) but do not enforce *mid-story* scope — a builder can
wander outside its declared `primary_files`/`touches` inside the worktree and nothing
stops it until the reviewer's advisory RAIL SCOPE checklist item catches it after the
fact (as happened harmlessly this session on INFRA-235's undeclared
`test_denylist_deriver.py` touch). Restoring the enforcement layer needs an explicit
decision on whether it applies inside a worktree's own cwd (which has no
`.companion/` of its own) or only in the main checkout.

Separately (operator decision, folding audit item A4 into this story): `hooks/stop.py`,
`session_end.py`, `exit_plan_mode.py`, `session_start.py`, and
`pairmode_status.py` all still read `state["pipe_path"]`, while
`pairmode_migrate.py`'s `to-030` step actively deletes that key on migration, and
`post_tool_use.py` has hardcoded the pipe location (`tempfile.gettempdir() +
"companion.pipe"`) instead. Post-migration, five files read a key that no longer
exists; `reviewer/procedure.md:197-203` still documents project-scoped pipes in prose.

## Requires

- Explicit decision (first Instruction step below) on worktree-cwd applicability
  before implementing the enforcement wiring, since it changes where state gets
  read/written.
- **Amended after adversarial review**: worktrees live at
  `<project>/.pairmode-worktrees/<story-id>/` — inside the main checkout
  (`flex_build.py`'s worktree-path helper) — so `scope_guard.py` *can* resolve
  `state.json` from the main root regardless of cwd (a git worktree carries a `.git`
  pointer file back to the main repo; no new provisioning needed just to find state).
  But finding state isn't sufficient: a path edited inside the worktree
  (`.pairmode-worktrees/<ID>/skills/foo.py`) will never match an `allowed_paths` entry
  generated from `primary_files: [skills/foo.py]` unless `_normalise` explicitly
  strips the `.pairmode-worktrees/<ID>/` prefix before comparing. Without that
  stripping, "restored" enforcement either blocks every worktree edit (if failing
  closed) or fails open again (if the normalised path just doesn't match and the
  fail-open branch swallows the miss) — decide which failure mode `_normalise`
  currently produces and treat the prefix-stripping fix as required scope, not
  optional polish.

## Ensures

- `create-story-worktree` (or an equivalent deterministic step called immediately
  around it) stamps `current_story` and generates the story's permission artifact
  (`docs/phases/permissions/<ID>.json`) before the builder spawns; `merge-story-worktree`
  and `discard-story-worktree` clear both afterward.
- A concrete test: an Edit call to a file outside the story's declared
  `primary_files`/`touches`, issued during a build spawn, is blocked by
  `scope_guard.py` — with an explicit, tested answer to whether this applies when the
  spawn's cwd is the worktree path (not the main checkout).
- A second concrete test, distinct from the above: an Edit call to a file that IS
  inside the story's declared scope, but addressed via its worktree-relative path
  (`.pairmode-worktrees/<ID>/<declared-path>`), is correctly *allowed* — proving the
  `.pairmode-worktrees/<ID>/` prefix is stripped before the `allowed_paths` comparison,
  not just that out-of-scope edits are blocked.
- RELEASE-020's `flex_factor` resolves the real story-specific value (not the 1.0
  fallback) during an active build spawn.
- `docs/phases/permissions/` generation resumes for current and future stories (or, if
  deliberately retired in favor of the worktree-scoped mechanism, `architecture.md` is
  updated to say so explicitly rather than silently going stale again).
- All five files reading `pipe_path` are updated to the single hardcoded pipe
  convention `post_tool_use.py` already uses; dead `pipe_path` branches removed;
  `reviewer/procedure.md:197-203` updated to match.
- `docs/architecture.md:229-234` updated to describe the actual implemented flow.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes (run without
  `-x`; confirm only the known CER-070 environmental failure remains).

## Instructions

1. Decide and document: does story-scope enforcement apply to Edit/Write calls whose
   cwd is a per-story worktree? (Recommended: yes — resolve `state.json` from the
   main checkout path regardless of cwd, since the worktree structurally lives inside
   the main project directory; no `.companion/` symlinking needed.) Implement the
   `.pairmode-worktrees/<ID>/` prefix-stripping in `_normalise` required by the
   amended Requires section above — this is the part that actually makes enforcement
   work inside a worktree, not just the state-resolution piece.
2. Add the stamping/clearing calls to `CLAUDE.build.md.j2`'s pseudocode around
   `create-story-worktree`/`merge-story-worktree`/`discard-story-worktree`, or fold
   them into those `flex_build.py` commands directly if that avoids new template prose
   (preferred, consistent with INFRA-237's CLI-side approach).
3. Restore `docs/phases/permissions/` generation for stories past RELEASE-006, or
   formally retire it with an architecture.md note explaining the replacement.
4. Standardize `hooks/stop.py`, `session_end.py`, `exit_plan_mode.py`,
   `session_start.py`, `pairmode_status.py` on the hardcoded pipe path; remove the
   `pipe_path` state-key branches.
5. Update `docs/architecture.md` and `reviewer/procedure.md`'s stale passages.
6. Add scope-guard block/allow test coverage including the worktree-cwd case from
   step 1.
7. Run the full test suite without `-x`; confirm only the known CER-070 failure
   remains.

## Out of scope

- Any change to `PROTECTED_GLOBS` itself or the fail-closed protected-path behavior
  (INFRA-196) — already working, untouched.
- INFRA-236 (effort recording), INFRA-237 (attempt counter) — adjacent state-lifecycle
  gaps, separate stories.
- Redesigning `flex_factor` itself — this story only restores its input, not its
  formula.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental failure; new
coverage for the worktree-cycle state lifecycle and the scope-guard block/allow
matrix under both main-checkout and worktree cwd.
