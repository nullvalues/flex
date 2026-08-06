---
id: INFRA-408
rail: INFRA
title: Close shadow-reviewer scope_guard cwd-resolution gap (CER-176/177/201)
status: draft
phase: "138"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/reviewer_bash_guard.py
  - skills/pairmode/scripts/scope_guard.py
touches:
  - tests/pairmode/test_reviewer_bash_guard.py
  - tests/pairmode/test_scope_guard.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

Phases 126 and 127 closed the shadow reviewer's Bash-guard bypass and its
worktree-path scope_guard gap, but two holes in the same confinement boundary
survived. `git diff --no-index` takes filesystem paths outside any repository,
so it slips past the reviewer Bash denylist's repo-scoped reasoning (CER-176).
And `scope_guard.check_path` resolves the story's worktree from the current
working directory; when the shadow reviewer runs with cwd at the main checkout
rather than its own per-story worktree, resolution falls through to cwd-relative
paths and the harness-owned allow-list prefixes, so a write can land in a
different story's worktree or a harness path instead of being confined to
exactly `.pairmode-suggestions.md` (CER-177, duplicated as CER-201; one fix).
Both are confinement escapes on a guard whose only value is that it cannot be
routed around.

## Requires

Phase 126 (CER-174) and Phase 127 (CER-175) complete — this story extends the
guard behaviour those stories established rather than reintroducing it.

## Ensures

For the shadow-reviewer role, `reviewer_bash_guard` denies any `git` invocation
carrying `--no-index` (in any argument position, and in its `=`-joined form),
and `scope_guard.check_path` allows exactly one write target —
`<story-worktree>/.pairmode-suggestions.md` — denying every other path
including another story's worktree, the harness-owned allow-list prefixes, and
any path reached by cwd-relative fallback when cwd is outside the story's own
worktree.

Forbidden proxy: a warning or log line about an out-of-worktree resolution while
the call still returns allowed; the guard must fail closed and the write must be
absent.

## Instructions

1. In `reviewer_bash_guard.py`, extend the shadow-reviewer git handling so
   `--no-index` is denied on its own terms — do not rely on the existing
   repo-relative path checks, which `--no-index` mode makes inapplicable. Match
   the flag as a token and in `--no-index=...` form.
2. In `scope_guard.py`'s `check_path`, when the role is shadow reviewer, derive
   the permitted worktree root from the story context rather than from cwd, and
   deny (fail closed) when the resolved path is not exactly
   `<story-worktree>/.pairmode-suggestions.md`. Do not let the harness allow-list
   prefixes or a cwd-relative fallback widen the shadow reviewer's grant; the
   allow-list remains in force for non-shadow-reviewer roles unchanged.
3. Add regression tests to both test files covering: `--no-index` denial in each
   argument form; a plain allowed `git` invocation still permitted; the single
   permitted suggestions path allowed; and denial of (a) another story's worktree
   suggestions path, (b) a harness allow-list prefix path, and (c) a relative
   path evaluated with cwd set to the main checkout.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_reviewer_bash_guard.py tests/pairmode/test_scope_guard.py -q
```
Acceptance: green, including the new denial cases. Then confirm no regression
across the suite:
```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

## Out of scope

- Any change to the non-shadow-reviewer roles' scope grants or to the harness
  allow-list contents — this story narrows only the shadow reviewer's path.
- Broader auditing of other `git` subcommands that accept out-of-repo paths
  (e.g. `git apply --directory`); only `--no-index` is closed here, and a wider
  sweep belongs in its own CER.
