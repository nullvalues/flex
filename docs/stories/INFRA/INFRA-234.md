---
id: INFRA-234
rail: INFRA
title: Drop redundant Write(docs/phases/permissions/**) deny rule from settings.json — Write(path) rules aren't matched by the permission engine
status: complete
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - .claude/settings.json
touches: []
---

## Context

Session startup this session printed a permission-rule syntax warning for
this repo's own tracked `.claude/settings.json`:

```
Permission deny rule (.claude/settings.json): Write(docs/phases/permissions/**)
is not matched by file permission checks — only Edit(path) rules are.
Use Edit(docs/phases/permissions/**) instead
```

The permission engine only matches `Edit(path)` rules against file-editing
tools (which include Write) — a bare `Write(path)` rule is never evaluated
and is pure dead weight. Confirmed by direct inspection: the deny list
already carries `Edit(docs/phases/permissions/**)` immediately above the
broken `Write(docs/phases/permissions/**)` line, so the intended
protection (deny writes/edits under `docs/phases/permissions/**`) is
already fully in force via the `Edit(...)` rule — the `Write(...)` line is
strictly redundant, not a missing protection.

Sibling repo `/mnt/work/flex` has the equivalent bug (a matching stale
`Write(docs/phases/permissions/**)` deny rule, plus several `Write(path)`
allow rules in its own untracked `settings.local.json`) but is out of
scope here: it's a separate git checkout this session cannot write to, and
its local file is untracked and unaffected by this repo's fold merge
(RELEASE-059). Both repos' own `settings.local.json` files are also out of
scope — gitignored/untracked personal state, and this repo's own copy is
moot regardless since RELEASE-061 (later in this phase) retires this
entire worktree once the fold lands. Only this repo's tracked
`settings.json` survives the fold merge into `main`, so it's the only file
worth a story here.

## Ensures

- `.claude/settings.json`'s `permissions.deny` array no longer contains the
  `Write(docs/phases/permissions/**)` line.
- `Edit(docs/phases/permissions/**)` (already present, already correct)
  remains untouched, immediately where it was.
- No other line in `.claude/settings.json` — hooks, allow list, any other
  deny entry — changes.
- No startup permission-rule warning for this file after the fix.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes
  (run without `-x`; report every failure, confirm only the known CER-070
  environmental one remains) — this change touches no Python source.

## Instructions

1. Remove the single line `"Write(docs/phases/permissions/**)"` from the
   `permissions.deny` array in `.claude/settings.json`.
2. Confirm the JSON is still valid and the diff touches exactly that one
   line.
3. Run the full test suite without `-x` and confirm the only failure is
   the known CER-070 environmental one.
4. Commit only `.claude/settings.json`.

## Out of scope

- `/mnt/work/flex`'s equivalent `settings.json` deny rule and
  `settings.local.json` allow rules — separate checkout, resolved in that
  project's own session.
- Either repo's `settings.local.json` (untracked, personal, and moot here
  given RELEASE-061 worktree retirement).
- Any other permission rule, hook, or settings content in this file.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental
failure — run without `-x` and report every failure seen, not just the
first. Manually confirm the `.claude/settings.json` diff is exactly the
one-line removal described in Ensures.
