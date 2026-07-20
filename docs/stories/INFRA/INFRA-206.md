---
id: INFRA-206
rail: INFRA
title: "Widen bootstrap.py's _register_pretooluse_hook to register the full Task|Agent + Edit|Write + Read matcher set into downstream projects' .claude/settings.json, migrating the stale \"Task\"-only block in place while preserving idempotency"
status: complete
phase: "93"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - tests/pairmode/test_bootstrap.py
touches: []
---

# INFRA-206 — Widen `_register_pretooluse_hook` to register the full `Task|Agent` + `Edit|Write` + `Read` matcher set into downstream projects' `.claude/settings.json`

## Context

`bootstrap.py`'s `_register_pretooluse_hook(settings_path, plugin_root)`
(`skills/pairmode/scripts/bootstrap.py:309-355`) is the registrar that wires the
`PreToolUse` hook into a **non-plugin bootstrapped** project's
`.claude/settings.json` (call site at `bootstrap.py:1119`). It uses the absolute
resolved path of `pre_tool_use.py` and merges idempotently by command string.

It is further behind than `hooks/hooks.json` was (see INFRA-205 / CER-065): it
finds-or-creates a single block with `"matcher": "Task"` — not even
`"Task|Agent"` (it predates the CER-049 `Task`→`Agent` rename) — and never
registers an `Edit|Write` or `Read` matcher at all. So every downstream project
bootstrapped through this path has the same dead-code gap as flex itself did: the
`scope_guard.py` and `cold_read_guard.py` dispatch branches never fire, and under
current harnesses even the context-budget gate may miss `Agent`-named spawns
because the matcher is bare `"Task"`.

This story widens `_register_pretooluse_hook` so newly-bootstrapped (or
re-bootstrapped) downstream projects get the full matcher set. It must:

- preserve **idempotency** — re-running bootstrap must not duplicate entries;
- **not orphan** a project that already carries the old stale `"Task"`-only block
  from a prior bootstrap — that block must be migrated forward, not left behind as
  a dead sibling.

This story does **not** modify `hooks/hooks.json` or `hooks/pre_tool_use.py`
(that is INFRA-205's job — `bootstrap.py` is a separate registrar for downstream
projects). `bootstrap.py` is **not** in CLAUDE.md item 7's protected list
(only `hooks/`, `skills/seed/scripts/`, `skills/companion/scripts/sidebar.py`,
`.claude-plugin/*`), so no protected-file justification is required for this
story.

### Existing test surface this fix must migrate in lockstep

`tests/pairmode/test_bootstrap.py`'s `TestRegisterPreToolUseHook`
(`test_bootstrap.py:2985-3086`) has three tests, all of which currently locate
the hook block by `b.get("matcher") == "Task"`:

- `test_register_pretooluse_hook_writes_entry` — asserts a `"Task"` matcher block
  exists and contains the `uv run python <pre_tool_use.py>` command.
- `test_register_pretooluse_hook_idempotent` — asserts calling twice yields
  **exactly one** entry with that command in the `"Task"` block.
- `test_register_pretooluse_hook_preserves_other_hooks` — pre-populates a `"Task"`
  block holding a *different* command (`uv run python /some/other/hook.py`) and
  asserts both the pre-existing command and the new command are present after the
  call.

Because the chosen fix changes the matcher string away from bare `"Task"`, all
three assertions that key on `matcher == "Task"` must be updated in lockstep (see
Instructions), and their **intent** — idempotency, and preservation of unrelated
pre-existing hook commands — must be retained, not weakened.

## Chosen approach (idempotency handling)

**Widen the existing block's matcher in place to a single combined matcher block,
`"Task|Agent|Edit|Write|Read"`, matched/deduped by command — not by matcher
string.** Rationale:

- The story title mandates "migrating the stale `Task`-only block in place while
  preserving idempotency" — in-place migration, not orphaned siblings.
- All three dispatch families route to the **same** command
  (`uv run python <pre_tool_use.py>`), so in a downstream `settings.json` a single
  combined matcher block is the simplest faithful registration; there is no
  per-family command difference that would justify three sibling blocks here.
  (This intentionally differs from `hooks/hooks.json`'s three-separate-block
  layout — that file is edited by hand and benefits from per-family separation;
  `settings.json` is machine-merged and benefits from a single canonical block
  that is trivial to find and dedupe.)
- Keying the find/dedupe on the **command string** (not the matcher literal)
  makes migration and idempotency both work: a legacy `"Task"`-only block, a
  legacy `"Task|Agent"` block, or an already-migrated combined block are all
  found by their inner command, upgraded to the canonical matcher in place, and
  the command is never duplicated. Searching by `matcher == "Task"` would break
  idempotency the moment the matcher is widened (the second run would no longer
  find the block and would append a duplicate).

## Ensures

1. **Canonical combined matcher registered.** After `_register_pretooluse_hook`
   runs against a fresh (or absent) `settings.json`, `hooks.PreToolUse` contains a
   single block whose `matcher` is `"Task|Agent|Edit|Write|Read"` and whose inner
   hooks include `{"type": "command", "command": "uv run python <abs pre_tool_use.py>"}`
   (command computed from `plugin_root`, absolute — unchanged from today).

2. **All three dispatch families covered.** The registered matcher, split on
   `"|"`, is a superset of the `tool_name` literals `pre_tool_use.py` dispatches
   on (`Task`, `Agent`, `Edit`, `Write`, `Read`) — closing the downstream half of
   CER-065.

3. **Idempotent.** Calling `_register_pretooluse_hook` twice (or N times) yields
   **exactly one** block carrying the `pre_tool_use.py` command and **exactly one**
   copy of that command inside it. The matcher remains the canonical combined
   string (not re-widened, re-appended, or duplicated).

4. **Stale `"Task"`-only block migrated in place, not orphaned.** If
   `settings.json` already contains a `PreToolUse` block whose matcher is the
   legacy `"Task"` (or `"Task|Agent"`) **and** whose inner hooks contain the
   `pre_tool_use.py` command, that same block's `matcher` is upgraded in place to
   `"Task|Agent|Edit|Write|Read"`; no second block for the same command is
   created.

5. **Unrelated pre-existing hooks preserved.** Any pre-existing hook entry with a
   *different* command (e.g. another tool's hook) is preserved — whether it lives
   in the migrated block or a sibling `PreToolUse` block — exactly as the current
   `test_register_pretooluse_hook_preserves_other_hooks` requires.

6. **This story does NOT modify `hooks/hooks.json` or `hooks/pre_tool_use.py`.**
   The change is confined to `bootstrap.py` (registrar logic) and
   `tests/pairmode/test_bootstrap.py` (migrated/added tests). No protected file is
   touched.

7. **Future-only effect.** The fix changes only what *future* bootstrap /
   re-bootstrap runs write; it does not retroactively rewrite an
   already-bootstrapped project's existing `settings.json` on disk (that would
   require re-running bootstrap there). This is stated explicitly in Out of scope.

8. **Full pairmode suite passes; no existing bootstrap test weakened.**
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes. The
   three existing `TestRegisterPreToolUseHook` tests are migrated (not deleted or
   weakened) and their idempotency / preserve-unrelated intent is retained.

## Instructions

- **Edit `_register_pretooluse_hook`** in `skills/pairmode/scripts/bootstrap.py`
  (`bootstrap.py:309-355`). Keep the command computation
  (`command = f"uv run python {pre_tool_use_path}"`) and the read/parse/create-file
  scaffolding unchanged. Replace the find-or-create-by-`matcher == "Task"` logic
  (`bootstrap.py:332-350`) with:

  1. Define a module-level constant for the canonical matcher, e.g.
     `PRETOOLUSE_MATCHER = "Task|Agent|Edit|Write|Read"`, with a short comment
     cross-referencing CER-065 / INFRA-205 (the `hooks.json` counterpart) and
     `pre_tool_use.py`'s three dispatch families so the two registration surfaces
     stay conceptually linked.
  2. **Find the target block by command, not by matcher.** Scan
     `pre_tool_use_list` for the block whose inner `hooks` already contain an entry
     with `command == command` (the `pre_tool_use.py` command). This finds a
     legacy `"Task"` block, a legacy `"Task|Agent"` block, or an already-migrated
     combined block alike.
  3. If such a block is found, set its `matcher = PRETOOLUSE_MATCHER` (in-place
     migration — idempotent when already canonical) and ensure the command appears
     exactly once in its inner hooks (do not append a duplicate).
  4. If no block carries the command, create one:
     `{"matcher": PRETOOLUSE_MATCHER, "hooks": [{"type": "command", "command": command}]}`
     and append it.
  5. Preserve the existing idempotency guard for the inner command (append the
     `{"type": "command", "command": command}` entry only if not already present).
  6. Keep the trailing-newline write behavior (`json.dumps(data, indent=2) + "\n"`)
     unchanged.

  Also update the function docstring (`bootstrap.py:310-316`) to describe the
  combined-matcher registration and the by-command find/migrate semantics.

- **Migrate `TestRegisterPreToolUseHook`** in `tests/pairmode/test_bootstrap.py`
  (`test_bootstrap.py:2985-3086`) in lockstep — do not weaken intent:
  - Change the three tests' block lookups from `b.get("matcher") == "Task"` to
    locate the block by the presence of the `uv run python <pre_tool_use.py>`
    command (or by `matcher == "Task|Agent|Edit|Write|Read"`), so they follow the
    canonical matcher.
  - `test_register_pretooluse_hook_writes_entry`: additionally assert the block's
    `matcher` is `"Task|Agent|Edit|Write|Read"` and that splitting it on `"|"`
    yields a superset of `{Task, Agent, Edit, Write, Read}`.
  - `test_register_pretooluse_hook_idempotent`: keep the "exactly one command
    after two calls" assertion; additionally assert there is exactly one block
    carrying the command and the matcher is not re-widened/duplicated.
  - `test_register_pretooluse_hook_preserves_other_hooks`: keep the pre-populated
    `"Task"` block with the unrelated command; after the call assert both the
    unrelated command **and** the `pre_tool_use.py` command survive, and that the
    stale `"Task"` matcher was migrated to the canonical combined string (i.e.
    verify the in-place migration path, not orphaning).
  - Add a new test, e.g. `test_register_pretooluse_hook_migrates_stale_task_block`,
    that pre-populates a legacy `{"matcher": "Task", "hooks": [{command: <pre_tool_use.py command>}]}`
    block, runs the registrar once, and asserts the resulting `PreToolUse` array
    has exactly one block carrying the command with matcher
    `"Task|Agent|Edit|Write|Read"` (no orphaned `"Task"`-only sibling remains).

- Do **not** modify `hooks/hooks.json`, `hooks/pre_tool_use.py`, or the
  `_merge_deny_list` / `_merge_allow_rules` / call-site sequencing at
  `bootstrap.py:1102-1129`.

## Tests

`story_class: code` — real registrar behavior change plus migrated/added tests.
Run the gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Cases (in `tests/pairmode/test_bootstrap.py`, `TestRegisterPreToolUseHook`):

- `test_register_pretooluse_hook_writes_entry` (migrated) — combined matcher +
  superset assertion.
- `test_register_pretooluse_hook_idempotent` (migrated) — exactly one block /
  one command after repeated calls; matcher not duplicated.
- `test_register_pretooluse_hook_preserves_other_hooks` (migrated) — unrelated
  command preserved; stale `"Task"` matcher migrated in place.
- `test_register_pretooluse_hook_migrates_stale_task_block` (new) — legacy
  `"Task"`-only block carrying the command is upgraded in place to the canonical
  combined matcher with no orphaned sibling.

## Out of scope

- `hooks/hooks.json` and `hooks/pre_tool_use.py` — the plugin-side manifest fix
  and the matcher/dispatch superset regression test are INFRA-205.
- **Retroactively fixing already-bootstrapped downstream projects.** This story
  changes only what *future* bootstrap / re-bootstrap runs write into
  `.claude/settings.json`; it does not scan for or rewrite existing on-disk
  `settings.json` files in projects bootstrapped before this change. Migrating
  those in bulk (e.g. via `pairmode sync`) is a separate concern, not addressed
  here.
- Splitting the downstream registration into three sibling blocks to mirror
  `hooks.json` — a single combined matcher block is intentionally chosen for the
  machine-merged `settings.json` (see Chosen approach).
- Any change to the `_register_pretooluse_hook` command form (`uv run python
  <abs path>`), the plugin-root computation, or the deny-list / allow-rules merge
  logic.
