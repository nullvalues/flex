---
id: INFRA-255
rail: INFRA
title: scope_guard relative-path containment — resolve and contain all file_path inputs before glob/permission checks
status: draft
phase: "100"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/scope_guard.py
touches:
  - tests/pairmode/test_scope_guard.py
  - docs/architecture.md
---

## Context

INFRA-253 closed the fail-open hole for *protected* paths mid-story, making
`docs/phases/permissions/<story_id>.json` the single authorization surface.
The cp100 checkpoint-security gate then found the hole one layer down: the
guard's normaliser never resolves relative input, so the protected-path glob
match — and every scope comparison after it — runs against an attacker-chosen
string rather than a real repo-relative identity.

`skills/pairmode/scripts/scope_guard.py::_normalise()` (lines 200-207) resolves
and contains only `p.is_absolute()` inputs (`p.resolve().relative_to(project)`,
`None` on escape). A **relative** `file_path` is returned verbatim via
`_norm_str()`, which does nothing but strip a leading `./` — with no
`resolve()`, no containment check against the project root, and no rejection of
`..` components. `_is_protected()` then `fnmatch`es that unresolved string, so
`../../../etc/passwd` matches none of `PROTECTED_GLOBS` and falls straight
through the fail-open returns (`no active story — allowing`, `no permissions
file for <story> — allowing`, `empty allowed_paths … — allowing`). Verified
live against `check_path()` from its `pre_tool_use` call sites (lines 47 and
57). Impact: an Edit/Write issued with a relative traversal path bypasses scope
enforcement entirely and can write outside the project root.

A second defect sits in the same path: `_norm_str()`'s
`s.lstrip("./") if s.startswith("./")` strips *every* leading `.` and `/`
character, not one `./` prefix — so `./../../etc/passwd` normalises to
`etc/passwd`, laundering a traversal into an innocuous-looking repo-relative
string.

This is the era-003 fail-closed-at-the-boundary contract and the project's
`Never silently pass contradictions` constraint applied to the guard's own
input: a path the guard cannot confidently identify must not be allowed.

## Requires

- INFRA-253 complete: `check_path()`'s protected-path fail-closed branches
  (`missing` / `malformed` / empty `allowed_paths`) exist as written.
- `tests/pairmode/test_scope_guard.py` exists and passes on clean HEAD.
- No other in-flight edit to `skills/pairmode/scripts/scope_guard.py`.

## Ensures

1. `_normalise(file_path, project)` resolves **every** input — relative and
   absolute alike — to an absolute path before any further processing:
   relative inputs are resolved against the project root returned by
   `_resolve_main_project_root()` (the same `project` value `check_path()`
   already computes and passes), absolute inputs are resolved as today.
2. `_normalise()` returns `None` for any input whose resolved absolute path is
   not the project root or a descendant of it — covering relative traversal
   (`../../../etc/passwd`), disguised traversal (`./../../etc/passwd`), and
   absolute out-of-root paths (`/etc/passwd`) identically.
3. `_norm_str()` no longer uses `str.lstrip("./")`: a leading `./` is removed at
   most once (prefix removal, not character-class stripping), so a path whose
   first segments are dots is never silently rewritten into a bare
   repo-relative-looking string. `_norm_str("./../../etc/passwd")` does not
   return `"etc/passwd"`.
4. `check_path()`'s **no-active-story** branch fails closed on an
   unresolvable/escaping path: when `_normalise()` returns `None` it returns
   `(False, "path escapes project root")` — it no longer falls through to
   `return True, "no active story — allowing"`.
5. `check_path()`'s active-story branch keeps its existing
   `(False, "path escapes project root")` return for `None`, and that deny now
   also fires for relative traversal input (previously absolute only).
6. No fail-open return in `check_path()` is reachable with a `file_path` that
   resolves outside the project root, in any guard state: no active story;
   active story with permissions artifact `missing`; active story with artifact
   `malformed`; active story with `ok` status and empty `allowed_paths`; active
   story with a populated `allowed_paths`.
7. Existing in-root behaviour is unchanged and regression-tested: an in-root
   relative path (`skills/pairmode/scripts/scope_guard.py`), the same path with
   a `./` prefix, and the equivalent absolute path all normalise to the same
   repo-relative string and produce the same allow/deny verdict as before this
   story, including the `.pairmode-worktrees/<active-story-id>/…` prefix
   stripping performed by `_strip_worktree_prefix()`.
8. A protected path expressed relatively with traversal segments that land back
   inside the repo (e.g. `docs/../hooks/pre_tool_use.py`) is recognised as
   protected — it normalises to `hooks/pre_tool_use.py` and is denied under the
   INFRA-253 fail-closed rules rather than escaping `PROTECTED_GLOBS` on a
   string mismatch.
9. `tests/pairmode/test_scope_guard.py` covers, as named tests:
   - relative traversal (`../../../etc/passwd`) → deny, in each of the five
     guard states listed in Ensures 6;
   - `./`-disguised traversal (`./../../etc/passwd`) → deny;
   - absolute out-of-root (`/etc/passwd`) → deny, no active story and active
     story alike;
   - normal in-root relative, `./`-prefixed, and absolute paths → same verdict
     as pre-story behaviour (allow where previously allowed);
   - traversal-back-into-root protected path (Ensures 8) → deny;
   - worktree-prefixed relative path for the active story still resolves to its
     stripped repo-relative identity and matches `allowed_paths`.
10. `docs/architecture.md`'s scope-enforcement / protected-files section states
    the input-normalisation contract: all `file_path` inputs are resolved
    (relative against the project root) and contained against the project root
    *before* any glob or permissions comparison, and any path resolving outside
    the root is denied in every guard state including no-active-story — with the
    rationale that glob matching on an unresolved string is not a security
    boundary.
11. `tests/pairmode/` passes (the known pre-existing
    `test_observability_ui.py::test_ui_build_emits_dist_index_html` failure is
    acceptable if it reproduces on clean HEAD).

## Instructions

1. **Rewrite `_normalise()`** (`skills/pairmode/scripts/scope_guard.py`,
   lines 200-207) so both branches converge on one code path:

   - Build the absolute candidate: `p = Path(file_path)`; if `p` is not
     absolute, `p = project / p`.
   - `resolved = p.resolve()` — `resolve()` is non-strict on Python 3.11 and
     works for paths that do not exist yet (Write creates new files), and it
     collapses `..` segments, so `..` need not be rejected by string inspection
     *before* resolution. Do not make a naive `".." in path` string check the
     primary defence; the containment test after resolution is the defence. A
     pre-resolution `..` check may be added only as a redundant belt-and-braces
     guard, never as a replacement.
   - Contain it: `resolved.relative_to(project)` inside `try/except ValueError`,
     returning `None` on `ValueError`. `project` is already `.resolve()`d by
     `check_path()` before it is passed in, so both sides of the comparison are
     resolved and the check is symmetric. Use `Path.relative_to`; do not use a
     string `startswith` on the path text (`/proj-evil` would prefix-match
     `/proj`).
   - Return `_norm_str()` of the resulting relative path.
   - `resolve()` follows symlinks, so a repo-internal symlink pointing outside
     the root now denies. That is the intended fail-closed reading — state it in
     the function docstring so a later agent does not "fix" it back.

   **Choice of resolution base (decide-and-document):** resolve relative inputs
   against `project` — the main-checkout root from
   `_resolve_main_project_root()` — not against the raw `project_dir` cwd. This
   preserves today's semantics exactly for the common case (a relative path from
   a build spawn is already repo-relative and was previously passed through
   verbatim), keeps `allowed_paths` matching and `_strip_worktree_prefix()`
   working unchanged, and avoids regressing the no-active-story protected check
   (resolving against a worktree cwd would turn `hooks/x.py` into
   `.pairmode-worktrees/<id>/hooks/x.py`, which no longer matches
   `PROTECTED_GLOBS` in the branch that does not strip the prefix). Record this
   rationale in the `_normalise()` docstring.

2. **Fix `_norm_str()`**: replace
   `s.lstrip("./") if s.startswith("./") else s` with a single-prefix removal
   (`s.removeprefix("./")` or an explicit slice). Keep the `Path(p).as_posix()`
   normalisation. Add a one-line comment naming the `lstrip` character-class bug
   so it is not reintroduced.

3. **Fail-close the no-active-story branch** in `check_path()` (lines 45-55):
   compute `relative_path = _normalise(file_path, project)` as today, then
   immediately `if relative_path is None: return False, "path escapes project
   root"` before the `_is_protected()` check and before the
   `no active story — allowing` return. Use the same reason string as the
   active-story branch so the two denies are indistinguishable to callers.

4. **Leave the rest of `check_path()` structurally alone.** The INFRA-253
   protected/fail-closed logic, `_strip_worktree_prefix()`,
   `_read_allowed_paths()`, and `_resolve_main_project_root()` are not in scope
   and must not be refactored. This story changes input normalisation and the
   one missing `None` guard, nothing else.

5. **Tests** — extend `tests/pairmode/test_scope_guard.py`. Use `tmp_path` for
   the fake project root (writing `.companion/state.json` and
   `docs/phases/permissions/<story>.json` the way the existing tests do), and
   parametrise the traversal cases over the five guard states so Ensures 6 is
   covered mechanically rather than by five hand-copied tests. Assert on the
   boolean verdict and on the reason string for denies. Include direct unit
   tests for `_normalise()` and `_norm_str()` alongside the `check_path()`
   integration cases — the string-laundering bug in Ensures 3 is only visible at
   the helper level.

6. **Docs** — update the scope-enforcement / protected-files section of
   `docs/architecture.md` (the section INFRA-253 amended with the fail-closed
   contract) per Ensures 10. Add the normalisation contract as a short
   subsection next to the existing fail-closed statement; do not restructure the
   surrounding document.

7. **Ideology alignment (Step 4a, checked):** no conflict found. The change is
   contained to a skill script — hooks stay thin relays (the hook still only
   calls `check_path()` and relays its verdict), the sidebar remains the sole
   state writer (this story writes no state), and the `Never silently pass
   contradictions` constraint is exactly what the fail-closed containment
   implements. No drafted instruction contradicts a conviction, an accepted
   constraint, or a "No"/"Conditional" prototype fingerprint.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_scope_guard.py -q 2>&1 | tail -30
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance:

- `test_scope_guard.py` green, including every case named in Ensures 9.
- Full `tests/pairmode/` run (note: no `-x`, so a later real failure is not
  masked by the known one) shows no new failures; the pre-existing
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` failure is
  acceptable only if it reproduces on clean HEAD.
- Manual confirmation recorded in Build notes: from a Python REPL with no active
  story set, `scope_guard.check_path("../../../etc/passwd", ".")` returns
  `(False, "path escapes project root")`.

## Out of scope

- Any change to `PROTECTED_GLOBS` membership, or to the INFRA-253
  missing/malformed/empty fail-closed branches.
- Applying `_strip_worktree_prefix()` in the no-active-story branch, or any
  other change to worktree-prefix semantics.
- The `pre_tool_use` hook itself (`hooks/`) — the hook's call sites at lines 47
  and 57 of the guard are unchanged; no hook edit is required, and none is in
  this story's scope.
- `.claude/settings.json` / `settings.local.json` deny lists — INFRA-253 settled
  the settings.json end-state doctrine; this story writes neither file.
- Symlink policy beyond the `resolve()`-follows-symlinks consequence noted
  above: no allow-list for intentional out-of-root symlinks is built here. If
  one is ever needed it is a separate story.
- Normalising or containing paths in any other consumer (`permissions-create`,
  reviewer scope checks, `index_integrity.py`); this story hardens
  `scope_guard.py` only.
