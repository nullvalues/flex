---
id: INFRA-200
rail: INFRA
title: "Remove flex-specific hook exception paragraph from canonical CLAUDE.md.j2 template"
status: complete
phase: "89"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/CLAUDE.md.j2
touches:
  - tests/pairmode/test_templates.py
  - tests/pairmode/test_sync.py
  - tests/pairmode/test_audit.py
---

# INFRA-200 — Remove flex-specific hook exception paragraph from canonical CLAUDE.md.j2 template

## Context

`skills/pairmode/templates/CLAUDE.md.j2` is the generic, project-agnostic
template every pairmode project's `CLAUDE.md` is bootstrapped from
(`bootstrap.py:48`, `SCAFFOLD_FILES`) and later drift-checked against
(`audit.py:33`, `CANONICAL_FILES`). Lines 35-42 of that template embed a
"Documented thin-delegation exception" paragraph under the PROTECTED FILES
checklist item, naming `hooks/pre_tool_use.py`, `cold_read_guard.py`, and
flex-internal story ID INFRA-196.

`bootstrap.py`'s `SCAFFOLD_FILES` list (lines 45-54) never includes anything
under `hooks/` — hook scripts are never copied into a target project. Instead
`_register_pretooluse_hook` (`bootstrap.py:308-`) wires
`.claude/settings.json` to invoke the hook by the flex plugin's own absolute
install path. Consequently no project bootstrapped from this template will
ever have a local `hooks/pre_tool_use.py` file, or a story numbered
INFRA-196 — those identifiers are meaningful only inside the flex repo
itself. Every project synced from the current template inherits a checklist
paragraph describing infrastructure and a ticket ID that don't exist for it,
which a reviewer subagent cannot evaluate meaningfully.

`/mnt/work/flex/CLAUDE.md` (this repo's own hand-maintained file, not
generated fresh from this template on each sync) legitimately keeps this
content — expanded well past what's in the template, covering
`post_tool_use.py`, `session_start.py`, and `user_prompt_submit.py` dispatch
too — because those hooks are real, version-controlled files in this repo.
This story does not touch `/mnt/work/flex/CLAUDE.md`.

## Ensures

1. **Paragraph removed from the template.** `skills/pairmode/templates/CLAUDE.md.j2`'s
   PROTECTED FILES checklist item (currently item 1, lines ~31-42) no longer
   contains the "Documented thin-delegation exception" paragraph naming
   `hooks/pre_tool_use.py`, `cold_read_guard.py`, or `INFRA-196`. The
   surrounding instruction — "Were any protected files modified without a
   stated reason? Unexplained modification is HIGH." — is preserved verbatim.
2. **No other template content changed.** Session modes, Review checklist
   items 2-4 (STORY SCOPE, BUILD GATE, DOCUMENTATION CURRENCY), Review output
   format, Story test verification, and Loop-breaker mode sections are
   byte-for-byte unchanged.
3. **`/mnt/work/flex/CLAUDE.md` untouched.** This story does not edit the
   flex repo's own `CLAUDE.md` — it keeps its full, flex-specific hook
   documentation regardless of what the generic template now contains.
4. **Existing template/sync/audit tests still pass** with no test relying on
   the removed paragraph's presence in `CLAUDE.md.j2` render output. If any
   test in `tests/pairmode/test_templates.py`, `tests/pairmode/test_sync.py`,
   or `tests/pairmode/test_audit.py` asserts on that paragraph's text, update
   the assertion to match the trimmed template rather than deleting test
   coverage.
5. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- In `skills/pairmode/templates/CLAUDE.md.j2`, delete the
  "**Documented thin-delegation exception:** ..." paragraph currently at
  lines 35-42 (the block beginning `` `hooks/pre_tool_use.py`'s `Read` ``
  and ending `... reads are never blocked.`), including its blank
  separator lines, so PROTECTED FILES reads as:

  ```
  1. PROTECTED FILES
     Were any protected files modified without a stated reason?
     Unexplained modification is HIGH.

  2. STORY SCOPE
  ```

  Do not renumber or otherwise alter items 2-4.
- Search `tests/pairmode/test_templates.py`, `tests/pairmode/test_sync.py`,
  and `tests/pairmode/test_audit.py` for any assertion referencing
  `cold_read_guard`, `INFRA-196`, `pre_tool_use.py`, or the
  "thin-delegation exception" text against `CLAUDE.md.j2` render output.
  Update matches to reflect the trimmed template; do not weaken unrelated
  assertions.
- Do not edit `/mnt/work/flex/CLAUDE.md`, `hooks/pre_tool_use.py`,
  `skills/pairmode/scripts/cold_read_guard.py`, `docs/architecture.md`, or
  any other template file (`CLAUDE.build.md.j2`, agent templates).
- Do not add a `.pairmode-overrides` entry for this repo — this story
  removes the source of drift rather than suppressing an audit finding.

## Tests

`story_class: doc` — a template prose trim with no new logic. Run the full
gate to confirm no existing test depended on the removed paragraph's text:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Re-syncing or re-bootstrapping any downstream (non-flex) project that
  already has the stale paragraph in its `CLAUDE.md`. That project's own
  session flagged the drift and can pull the fix via its normal audit/sync
  flow once this template change ships; no cross-project action is taken by
  this story.
- Any change to `hooks/pre_tool_use.py`, `cold_read_guard.py`, or their
  behavior. This is a documentation-template fix only.
- Adding a generic (non-flex-specific) description of Read-blocking behavior
  to the template in place of the removed paragraph. The generic PROTECTED
  FILES instruction is sufficient for downstream projects; no replacement
  content is scoped by this story.
