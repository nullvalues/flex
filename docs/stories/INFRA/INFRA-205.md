---
id: INFRA-205
rail: INFRA
title: "Register the Edit|Write and Read PreToolUse matchers in hooks/hooks.json so scope_guard and cold_read_guard dispatch branches fire, plus a regression test asserting hooks.json PreToolUse matchers are a superset of pre_tool_use.py's dispatched tool_name values"
status: planned
phase: "93"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/hooks.json
  - tests/pairmode/test_hooks_json.py
touches: []
---

# INFRA-205 — Register the `Edit|Write` and `Read` PreToolUse matchers in `hooks/hooks.json` and add a matcher/dispatch superset regression test

## Context

`hooks/pre_tool_use.py` is a thin dispatcher with three `tool_name` branches
(`hooks/pre_tool_use.py:64,92,106`):

- `tool_name in ("Task", "Agent")` → `context_budget.py` (the context-budget gate)
- `tool_name in ("Edit", "Write")` → `scope_guard.py` (Phase 55, story-file-scope
  enforcement)
- `tool_name == "Read"` → `cold_read_guard.py` (INFRA-196, orchestrator cold-read
  blocking)

But `hooks/hooks.json`'s `PreToolUse` array registers **only one** matcher block,
`"matcher": "Task|Agent"` (`hooks/hooks.json:26-37`), pointing at
`python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py`. There is no `Edit|Write`
block and no `Read` block. Because Claude Code only invokes a `PreToolUse` hook
for tool calls whose name matches a registered matcher, the `scope_guard.py` and
`cold_read_guard.py` branches are **unreachable dead code in every project using
this plugin, including flex itself** — two documented enforcement mechanisms
(story-file-scope enforcement and orchestrator cold-read blocking) have almost
certainly never executed on any project.

This is the exact contrast with the `PostToolUse` array immediately below in the
same file (`hooks/hooks.json:38-59`), which correctly carries **two** separate
matcher blocks (`"Write|Edit|MultiEdit"` and `"Task|Agent"`) for
`post_tool_use.py`. The pipe-delimited multi-tool matcher is the established
idiom in this file.

Root cause (from CER-065, already diagnosed — do not re-diagnose): `hooks.json`'s
`PreToolUse` block was created `Task`-only in INFRA-128 when the hook only handled
the context-budget gate; two later stories each added a new dispatch branch to the
Python source without touching the registration manifest — INFRA-139 (`Edit`/`Write`
→ `scope_guard.py`) and INFRA-196 (`Read` → `cold_read_guard.py`). Neither commit
touched `hooks/hooks.json`, and no test asserted that `hooks.json`'s registered
matchers are a superset of the `tool_name` branches `pre_tool_use.py` actually
dispatches on, so both gaps shipped silently. This story closes the `hooks.json`
half of CER-065 and adds the missing regression guard. (INFRA-206 handles the
`bootstrap.py` registrar half separately; this story does **not** touch
`bootstrap.py`.)

## Protected file justification

Per CLAUDE.md item 7 (PROTECTED FILES), `hooks/` (all scripts and `hooks.json`)
is protected and any modification requires a stated reason.

This story modifies `hooks/hooks.json`. **Justification:** it closes CER-065. The
two `pre_tool_use.py` dispatch branches added in prior stories —
`scope_guard.py` (Phase 55 / INFRA-139) and `cold_read_guard.py` (INFRA-196) —
were never reachable because their `PreToolUse` matcher was never registered in
`hooks.json`. Adding the `Edit|Write` and `Read` matcher blocks is the minimal
change that makes the already-shipped enforcement code actually fire. No hook
*script* is modified by this story; the change is confined to the registration
manifest (plus a new, non-protected test file). `hooks/pre_tool_use.py` is
referenced read-only by the new test and is **not** modified.

## Ensures

1. **`Edit|Write` matcher block registered.** `hooks/hooks.json`'s `PreToolUse`
   array gains a matcher block `"matcher": "Edit|Write"` whose single inner hook
   is `{"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py", "timeout": 5}`
   — byte-identical command/timeout to the existing `Task|Agent` block, mirroring
   the two-block `PostToolUse` convention already in the same file.

2. **`Read` matcher block registered.** The `PreToolUse` array likewise gains a
   `"matcher": "Read"` block with the same single inner hook command/timeout.

3. **Existing `Task|Agent` block unchanged.** The pre-existing `"Task|Agent"`
   `PreToolUse` block (`hooks/hooks.json:26-37`) is preserved verbatim, and every
   other top-level hook array (`Stop`, `PermissionRequest`, `PostToolUse`,
   `SessionEnd`, `SessionStart`, `UserPromptSubmit`) is left byte-for-byte
   unchanged. `hooks.json` remains valid JSON.

4. **All three `pre_tool_use.py` dispatch branches are now reachable.** After the
   change, every `tool_name` literal `pre_tool_use.py` dispatches on
   (`"Task"`, `"Agent"`, `"Edit"`, `"Write"`, `"Read"`) is covered by at least one
   registered `PreToolUse` matcher.

5. **New matcher/dispatch superset regression test.** A new test in
   `tests/pairmode/test_hooks_json.py` parses (a) the set of `tool_name` string
   literals `hooks/pre_tool_use.py` actually dispatches on and (b) the set of
   tool names registered across `hooks/hooks.json`'s `PreToolUse` matchers
   (splitting each `matcher` on `|`), and asserts the dispatched set is a subset
   of the registered set. A future fourth dispatch branch added to the Python
   source without a matching `hooks.json` update fails this test. The dispatched
   literals are extracted by **scanning the actual `pre_tool_use.py` source**
   (not a hand-duplicated list — a hand-duplicated list would not have caught the
   original bug).

6. **`hooks/pre_tool_use.py` is not modified.** This story references the hook
   script read-only from the test; it makes no change to any hook *script*. (Only
   `hooks/hooks.json` — the manifest — is modified, per the protected-file
   justification above.)

7. **Full pairmode suite passes; no existing test weakened.**
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.
   Existing hook tests (`test_hooks.py`, `test_pre_tool_use_hook.py`,
   `test_pre_tool_use_scope_guard.py`, `test_cold_read_guard.py`) remain green and
   are not weakened.

## Instructions

- **Edit `hooks/hooks.json`.** In the `PreToolUse` array, after the existing
  `"Task|Agent"` block, add two sibling matcher blocks — `"Edit|Write"` and
  `"Read"` — each with the identical single inner hook the `Task|Agent` block
  uses:

  ```json
  {
    "type": "command",
    "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py",
    "timeout": 5
  }
  ```

  Use separate blocks (one per matcher family), mirroring the existing
  `PostToolUse` two-block layout in the same file rather than collapsing into a
  single combined `"Task|Agent|Edit|Write|Read"` matcher — this keeps the file's
  established idiom and keeps each dispatch family independently editable. Match
  the file's existing 2-space indentation and preserve the trailing newline.

- **Add `tests/pairmode/test_hooks_json.py`** (new file — there is currently no
  test that reads `hooks.json` content directly; this is the first). The filename
  mirrors the existing `test_hooks.py` structural-hook-test naming. The test must:

  1. Resolve the repo root the same way `test_hooks.py` does
     (`Path(__file__).resolve().parent.parent.parent`), then read
     `hooks/hooks.json` and `hooks/pre_tool_use.py`.
  2. **Extract the dispatched `tool_name` literals from the `pre_tool_use.py`
     source text** (do not import/execute the hook). Scan for the two dispatch
     shapes actually used in `main()`:
     - `tool_name in ( ... )` — collect every quoted string inside the tuple
       (currently `("Task", "Agent")` and `("Edit", "Write")`).
     - `tool_name == "..."` — collect the single quoted literal (currently
       `"Read"`).
     A small regex over the source is sufficient (e.g. capture the `(...)` after
     `tool_name in` and the string after `tool_name ==`, then pull the quoted
     substrings). Assert the extracted set is non-empty (guards against a regex
     that silently matches nothing, which would make the superset check vacuous).
  3. Parse `hooks.json`, take `hooks["PreToolUse"]`, and build the registered-tool
     set by splitting each block's `matcher` on `"|"`.
  4. Assert `dispatched <= registered` (every dispatched `tool_name` is covered by
     a registered matcher), with an assertion message listing any uncovered
     literals so a future regression names the missing matcher.
  5. Optionally also assert the three specific expected literals are covered
     (`Edit`, `Write`, `Read`) as a readable smoke check, but the superset
     assertion driven by the source scan is the primary guard.

- Do **not** modify `hooks/pre_tool_use.py`, `bootstrap.py`, or any other hook
  script. Do not add a documenting comment to `pre_tool_use.py` — the regression
  test (which scans the live source) is the enforcement surface, so no in-source
  comment is needed and none is added (keeps this story off the protected hook
  *scripts*).

## Tests

`story_class: code` — a real behavior change (new matcher blocks) plus a new
regression guard. Run the gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

New cases in `tests/pairmode/test_hooks_json.py`:

- `test_pretooluse_matchers_cover_all_dispatched_tool_names` — the core CER-065
  regression: scan `pre_tool_use.py` for dispatched `tool_name` literals, parse
  `hooks.json` `PreToolUse` matchers, assert dispatched ⊆ registered. This test
  must **fail** against the pre-fix `hooks.json` (Task|Agent only) and **pass**
  after the two new blocks are added.
- `test_pretooluse_source_scan_finds_expected_literals` — assert the source scan
  extracts a non-empty set containing at least `Task`, `Agent`, `Edit`, `Write`,
  `Read` (guards against a scan regex that silently matches nothing and makes the
  superset check vacuously true).
- `test_pretooluse_edit_write_and_read_blocks_use_canonical_command` — assert the
  two new blocks' inner hook command equals
  `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py` with `timeout: 5`,
  matching the existing `Task|Agent` block.

### Out of scope

- `bootstrap.py`'s `_register_pretooluse_hook` and downstream
  `.claude/settings.json` registration — that is INFRA-206. This story does not
  touch `bootstrap.py` or `tests/pairmode/test_bootstrap.py`.
- Retroactively fixing already-bootstrapped downstream projects' existing
  `settings.json` files.
- Any change to `pre_tool_use.py`'s dispatch logic, the `scope_guard.py` /
  `cold_read_guard.py` domain modules, or their existing behavior tests.
- Modifying any other `PreToolUse`/`PostToolUse`/other-event block in
  `hooks.json` beyond adding the two new `PreToolUse` blocks.
