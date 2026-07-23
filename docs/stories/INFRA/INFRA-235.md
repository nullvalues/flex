---
id: INFRA-235
rail: INFRA
title: Stop generating invalid Write(path) permission rules — permission engine only matches Edit(path) for file-editing tools
status: planned
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/permission_scope.py
  - skills/pairmode/scripts/denylist_deriver.py
touches:
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_permission_scope.py
  - tests/pairmode/test_phase2_coverage.py
  - tests/pairmode/test_denylist_deriver.py
  - tests/pairmode/test_sync_deny_list.py
  - docs/architecture.md
---

## Context

INFRA-234 removed a broken `Write(docs/phases/permissions/**)` deny rule
from this repo's own `.claude/settings.json` (Claude Code's permission
engine only matches `Edit(path)` against file-editing tools, including
Write — a bare `Write(path)` rule is never evaluated). That fix patched
one already-generated artifact by hand. Direct inspection of the
generators this session found the bug is not one-off — it's baked into
three call sites, all still live:

1. **`bootstrap.py:80-83` (`DEFAULT_DENY`)** — the exact same broken pair
   (`Edit(docs/phases/permissions/**)` + `Write(docs/phases/permissions/**)`)
   is written into every project's `.claude/settings.json` by
   `bootstrap.py:1094`, on both fresh `bootstrap` and `sync-all` for
   existing projects. Confirmed via `tests/pairmode/test_bootstrap.py:1066-1069`,
   which currently *asserts* both entries are present.
2. **`permission_scope.py:69,82` (`write_story_permissions`)**, called live
   from `flex_build.py write-permissions` for every story build — for each
   `primary_files`/`touches` entry it appends both `Edit(path)` and
   `Write(path)` to `.claude/settings.local.json`'s allow list. This is the
   exact generator that produced the original `settings.local.json`
   warnings (`Write(hooks/post_tool_use.py)`,
   `Write(skills/pairmode/templates/CLAUDE.md.j2)`,
   `Write(tests/pairmode/test_templates.py)`, etc.) — it fires on every
   story, not just historically. Confirmed via
   `tests/pairmode/test_permission_scope.py` (multiple `assert "Write(...)" in allow`).
3. **`denylist_deriver.py:41` (`_DENY_TOOLS = ("Edit", "Write")`)** —
   spec-derived deny rules (from a module's `non_negotiables`) emit one
   `Edit(path/**)` and one `Write(path/**)` deny entry per protected path.
   Confirmed via `tests/pairmode/test_phase2_coverage.py:268-269,454-455`.

Left unfixed, every remaining fold-migration (`sync-all`/`to-030` against
the 14 still-pending fleet projects — see `phase-97.md`'s Deferred
stories) will write the broken `DEFAULT_DENY` pair into each project's
`settings.json`, and every story built anywhere (this repo included, going
forward) will keep emitting fresh `Write(path)` allow-rule noise via
`write-permissions`. This story fixes the root cause before the remaining
fleet migrations run, rather than hand-patching the same warning in 14
more repos after the fact.

## Requires

- INFRA-234 complete (confirmed merged this session) — establishes the
  precedent this story generalizes: `Edit(path)` alone is correct,
  `Write(path)` is dead weight.

## Ensures

- `bootstrap.py::DEFAULT_DENY` contains only
  `"Edit(docs/phases/permissions/**)"` — the `Write(...)` sibling line is
  removed.
- `permission_scope.py::write_story_permissions` appends only
  `Edit(path)` (never `Write(path)`) for each `primary_files`/`touches`
  entry. The existing `Read(path)` rule for `touches` entries is
  unaffected.
- `denylist_deriver.py::_DENY_TOOLS` is `("Edit",)` — `derive_denylist`
  emits exactly one deny dict per protected path (`Edit(path/**)`), not
  two.
- No other behavior of any of the three functions changes: dedup,
  idempotency, comment-stripping (INFRA-211), merge-with-existing-rules,
  and the `_is_subsumed`/superseded-entry pruning logic in `bootstrap.py`
  are all unaffected except for the narrower rule set they now operate on.
- `tests/pairmode/test_bootstrap.py`, `test_permission_scope.py`,
  `test_phase2_coverage.py`, and `test_sync_deny_list.py` are updated so
  every assertion of the form `assert "Write(<path>)" in <allow|deny|patterns>`
  tied to these three generators is removed or flipped to
  `assert "Write(<path>)" not in ...` as appropriate, and every
  `assert "Edit(<path>)" in ...` sibling assertion is kept. Do not touch
  test assertions for `Write(path)` entries that originate from anywhere
  else (e.g. hand-authored fixture data unrelated to these three
  generators, or `_is_subsumed`/pruning tests that exercise legacy
  `Write(...)` entries already present in a project's *existing*
  `settings.json` before this story's fix — those pruning paths must keep
  working on old data even though nothing generates new `Write(...)`
  entries going forward).
- `docs/architecture.md`'s description of the permission-rule generation
  behavior (if it documents the Edit/Write pairing) is updated to match.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` passes
  (run without `-x`; report every failure, confirm only the known CER-070
  environmental one remains).

## Instructions

1. In `bootstrap.py`, remove `"Write(docs/phases/permissions/**)"` from
   `DEFAULT_DENY`, leaving only the `Edit(...)` entry.
2. In `permission_scope.py::write_story_permissions`, remove the
   `new_rules.append(f"Write({raw})")` line from both the `primary_files`
   loop and the `touches` loop (two call sites), leaving the `Edit(...)`
   append and (for `touches`) the `Read(...)` append untouched.
3. In `denylist_deriver.py`, change `_DENY_TOOLS: tuple[str, ...] = ("Edit", "Write")`
   to `_DENY_TOOLS: tuple[str, ...] = ("Edit",)`.
4. Search each of the four listed test files for every assertion
   referencing a `Write(...)` rule produced by these three generators and
   update per the Ensures section above. Read each failing assertion's
   surrounding test to confirm it's actually testing one of these three
   generators (not unrelated fixture/pruning data) before changing it.
5. Grep `docs/architecture.md` for any description of Edit/Write rule
   pairing in the permission-generation section; update it if present.
6. Run the full test suite without `-x` and confirm the only failure is
   the known CER-070 environmental one.
7. Commit only the six files listed in `primary_files`/`touches` that
   actually changed.

## Out of scope

- Any change to `.claude/settings.json` or `.claude/settings.local.json`
  in *this* repo — those were already fixed by INFRA-233/INFRA-234 (this
  story only stops future regeneration of the bug, it doesn't re-touch
  already-clean files).
- Pruning or migrating already-existing `Write(path)` entries in any
  *other* fleet project's settings files — that happens naturally the
  next time each project's `sync-all` runs against this story's fixed
  `bootstrap.py`/`permission_scope.py`, which is out of scope for this
  story (this story only fixes the generator source).
- Any change to `_is_subsumed`, the superseded-entry pruning list, or any
  other bootstrap.py/sync logic not directly tied to Edit/Write rule
  generation.
- `/mnt/work/flex`'s equivalent bug — separate checkout, resolved in that
  project's own session per INFRA-234's Out of scope note.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental
failure — run without `-x` and report every failure seen, not just the
first. Manually confirm no remaining generator in `bootstrap.py`,
`permission_scope.py`, or `denylist_deriver.py` emits a `Write(path)`
permission rule.
