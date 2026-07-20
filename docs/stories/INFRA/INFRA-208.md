---
id: INFRA-208
rail: INFRA
title: "Generalize bootstrap.py downstream hook registration to wire the three load-bearing context-budget-gate hooks (UserPromptSubmit, SessionStart, PostToolUse Task|Agent) into .claude/settings.json alongside the existing PreToolUse registration — through both the bootstrap and sync.py call sites, mirroring _register_pretooluse_hook's by-command find/migrate idempotency, deferring the four companion/sidebar blocks as opt-in"
status: complete
phase: "95"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/sync.py
  - tests/pairmode/test_bootstrap.py
touches:
  - docs/architecture.md
---

# INFRA-208 — Generalize downstream hook registration to wire the context-budget-gate hooks (`UserPromptSubmit`, `SessionStart`, `PostToolUse` `Task|Agent`)

## Context

`skills/pairmode/scripts/bootstrap.py` has exactly **one** hook-registration
function, `_register_pretooluse_hook` (`bootstrap.py:317-379`), and it is the
**only** registrar ever called during either bootstrap (call site
`bootstrap.py:1137-1143`) or sync/sync-all (call site `sync.py:613-616`). Flex's
own canonical `hooks/hooks.json` registers **six event types across ten blocks**
(`Stop`, `PermissionRequest`/`ExitPlanMode`, `PreToolUse` ×3, `PostToolUse` ×2,
`SessionEnd`, `SessionStart`, `UserPromptSubmit`), but every downstream
bootstrapped project's `.claude/settings.json` only ever receives the
`PreToolUse` block — confirmed by inspecting the full fleet (CER-067).

The consequence is that the context-budget gate is **decorative** in every
downstream project, because the three hooks that write and advance the state it
reads never fire:

- **`user_prompt_submit.py` (INFRA-192)** never fires, so
  `context_budget_user_turn_seq` never increments. The
  "genuine-new-turn-since-last-block" requirement INFRA-193 built specifically
  to close the CER-047 self-clearing bug can **never** be satisfied by a normal
  reply in any downstream project.
- **`session_start.py`** reset (`session_reset.py`) never fires, so
  `context_current_tokens` never resets on `/clear`.
- **`post_tool_use.py`'s `Task`/`Agent` branch (INFRA-182)** never fires, so
  `context_current_tokens` is never written from a live transcript read — the
  gate reads a value nothing downstream ever produces.

Live symptom (CER-067): an agent working in the `asp` repo reported the budget
gate "can never self-clear via a normal 'Continue building' reply" and applied an
**undocumented, self-reinvented workaround** (forging
`context_budget_acknowledged_at` and `context_budget_acknowledged_user_turn_seq`
directly into `state.json`) to unstick it, noting it had "hit this before." No
such workaround exists anywhere in flex's docs — a broken mechanical gate is
being silently defeated across sessions.

This story is the direct lineal successor to **INFRA-206**, which widened
`_register_pretooluse_hook` to register the full `PreToolUse`
`Task|Agent|Edit|Write|Read` matcher set by-command with in-place migration. This
story keeps that same registrar family and idempotency discipline, but
**generalizes registration** so downstream `.claude/settings.json` also gets the
three load-bearing budget-gate hooks.

`bootstrap.py` and `sync.py` are **not** in CLAUDE.md item 7's protected list
(only `hooks/`, `skills/seed/scripts/`, `skills/companion/scripts/sidebar.py`,
`.claude-plugin/*`), so no protected-file justification is required. This story
does **not** modify `hooks/hooks.json` or any hook script — those are already
correct; the gap is purely in the downstream registrar.

### The three hooks to register (all confirmed thin, safe-to-blanket-register dispatchers)

Verified against the hook sources and against `hooks/hooks.json`:

- **`UserPromptSubmit`** — `hooks/user_prompt_submit.py`. No matcher in
  `hooks.json` (fires unconditionally per event). Write-only: one state.json
  read-modify-write incrementing `context_budget_user_turn_seq`. Never emits a
  decision, never blocks. No-ops when `.companion/state.json` is absent (not a
  pairmode repo) — safe to register in any project.
- **`SessionStart`** — `hooks/session_start.py`. No matcher in `hooks.json`.
  Delegates the counter-reset decision to `session_reset.py`; prints a status
  block. Returns early (emits nothing) when `pairmode_version` is unset — safe to
  register in any project.
- **`PostToolUse` `Task|Agent`** — `hooks/post_tool_use.py`. Matcher
  `Task|Agent`. Write-only: reads the JSONL transcript via
  `context_budget.read_current_tokens()` and writes `context_current_tokens`.
  Never blocks; exits silently on any failure.

### The `PostToolUse` sibling-block requirement

A downstream project may already carry its **own** `PostToolUse` block for an
unrelated purpose — confirmed in the fleet, where most projects have a local
pytest-runner `PostToolUse` hook (typically matcher `Edit|Write` or
`Write|Edit|MultiEdit`) that has nothing to do with flex. The new `Task|Agent`
`PostToolUse` block must be added as a **sibling** block alongside any existing
`PostToolUse` block(s) for other matchers — never merged into or replacing them —
exactly mirroring how flex's own `hooks.json` keeps `PostToolUse`'s
`Write|Edit|MultiEdit` and `Task|Agent` as two separate blocks (`hooks.json:58-79`).
The by-command find (below) makes this automatic: an unrelated pytest hook carries
a different inner command, so it is never mistaken for our `Task|Agent` block.

## Chosen approach (registrar generalization + per-hook idempotency)

Generalize registration by adding a small, uniform per-event registrar helper (or
a table-driven loop) that both call sites invoke, keeping `_register_pretooluse_hook`'s
proven INFRA-206 semantics for each event:

- **Find the target block by inner command, not by matcher or event name alone.**
  For each event, scan the event's block list for a block whose inner `hooks`
  already contain an entry with the computed absolute command
  (`uv run python <abs hook path>`). This is what makes re-registration
  idempotent and survives a future matcher change (the exact reason INFRA-206
  keyed on command, not matcher).
- **`UserPromptSubmit` and `SessionStart` register with no `matcher` field** —
  they fire unconditionally per event in `hooks.json`, so their block is
  `{"hooks": [{"type": "command", "command": <cmd>}]}` with no matcher. Simpler
  than `PreToolUse`. By-command find still applies (a block carrying that hook's
  command is found and left in place; otherwise appended).
- **`PostToolUse` `Task|Agent` registers as a sibling block** with
  `matcher: "Task|Agent"`, found by-command so any pre-existing local
  `PostToolUse` block (pytest runner, etc.) is preserved untouched as a separate
  sibling — mirroring `hooks.json`'s two-block `PostToolUse` layout.
- **Both call sites flow through the generalized path.** `bootstrap.py:1137-1143`
  and `sync.py:613-616` both currently call `_register_pretooluse_hook`; both must
  call whatever generalized function/set of functions this story introduces, so
  bootstrap and sync/sync-all produce identical registration.

The command form (`uv run python <abs resolved hook path>`, computed from
`plugin_root`, never `${CLAUDE_PLUGIN_ROOT}`), the file read/parse/create
scaffolding, and the trailing-newline write behavior
(`json.dumps(data, indent=2) + "\n"`) are all carried over unchanged from
`_register_pretooluse_hook`.

### Why the four companion/sidebar blocks are deliberately NOT registered

The four remaining canonical blocks are **explicitly deferred as opt-in**, with
stated reason:

- **`Stop`** (`hooks/stop.py`)
- **`PermissionRequest`/`ExitPlanMode`** (`hooks/exit_plan_mode.py`)
- **`PostToolUse` `Write|Edit|MultiEdit`** (`hooks/post_tool_use.py` file-change
  relay)
- **`SessionEnd`** (`hooks/session_end.py`)

These are **companion-sidebar relays**, not part of context-budget-gate
correctness. `PostToolUse` `Write|Edit|MultiEdit` and `Stop` pipe file-change /
turn-end events to the companion sidebar; `PermissionRequest`/`ExitPlanMode` and
`SessionEnd` are likewise sidebar/lifecycle-oriented. Whether a downstream project
runs the companion sidebar at all is a **separate product decision**; blanket-
registering these would scope-creep a correctness fix into a sidebar-adoption
decision, and would (for the `PostToolUse` file-change relay) add a second flex
`PostToolUse` block that most downstream projects have no sidebar to consume.
Registering them remains a future opt-in story, not this one.

## Ensures

1. **`UserPromptSubmit` registered.** After the generalized registrar runs against
   a fresh (or absent) `settings.json`, `hooks.UserPromptSubmit` contains a block
   (no `matcher` field) whose inner hooks include
   `{"type": "command", "command": "uv run python <abs user_prompt_submit.py>"}`.

2. **`SessionStart` registered.** `hooks.SessionStart` contains a block (no
   `matcher` field) whose inner hooks include
   `{"type": "command", "command": "uv run python <abs session_start.py>"}`.

3. **`PostToolUse` `Task|Agent` registered as a sibling.** `hooks.PostToolUse`
   contains a block whose `matcher` is `"Task|Agent"` and whose inner hooks
   include `{"type": "command", "command": "uv run python <abs post_tool_use.py>"}`.
   Any pre-existing `PostToolUse` block for a different matcher/command (e.g. a
   local pytest runner) is preserved unchanged as a separate sibling — not merged,
   not replaced.

4. **`PreToolUse` registration unchanged.** The existing INFRA-206 `PreToolUse`
   `Task|Agent|Edit|Write|Read` combined-matcher registration continues to work
   exactly as before (canonical matcher, by-command migrate, idempotent).

5. **Both call sites covered.** Registration flows identically through
   `bootstrap.py`'s registration step (`bootstrap.py:1137-1143`) and `sync.py`'s
   call site (`sync.py:613-616`); both invoke the generalized registrar, so
   sync/sync-all on an already-bootstrapped project adds the three new hooks the
   same way a fresh bootstrap does.

6. **Idempotent per hook.** Running the registrar twice (or N times) yields, for
   each of the four events, **exactly one** block carrying that hook's command and
   **exactly one** copy of the command inside it. No block is duplicated, and
   matchers are not re-widened or re-appended. By-command find guarantees this.

7. **The four companion/sidebar blocks are NOT registered.** `Stop`,
   `PermissionRequest`/`ExitPlanMode`, `PostToolUse` `Write|Edit|MultiEdit`, and
   `SessionEnd` are absent from a freshly-registered `settings.json` (unless a
   project already carries them from another source, in which case they are left
   untouched). A test asserts they are not added by this registrar.

8. **This story does NOT modify `hooks/hooks.json` or any `hooks/` script.** The
   change is confined to `bootstrap.py` / `sync.py` (registrar logic),
   `tests/pairmode/test_bootstrap.py` (migrated/added tests), and a currency
   update to `docs/architecture.md`. No protected file is touched.

9. **Future-only effect.** The fix changes only what *future* bootstrap /
   re-bootstrap / sync runs write; it does not retroactively rewrite an
   already-bootstrapped project's on-disk `settings.json`. Rolling the fix out
   across the existing fleet is INFRA-209.

10. **Full pairmode suite passes; no existing bootstrap test weakened.**
    `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes. The
    four existing `TestRegisterPreToolUseHook` tests (INFRA-206) still pass
    unchanged.

## Instructions

- **Add a generalized registrar in `skills/pairmode/scripts/bootstrap.py`.**
  Keep `_register_pretooluse_hook` and the `PRETOOLUSE_MATCHER` constant
  (`bootstrap.py:309-379`) intact as the `PreToolUse` case. Introduce a uniform
  per-event registration helper — either a table-driven
  `_register_context_budget_hooks(settings_path, plugin_root)` that iterates a
  small spec list, or three thin `_register_*` functions that share one internal
  by-command upsert helper. Recommended spec entries:

  | event | hook file | matcher |
  |---|---|---|
  | `UserPromptSubmit` | `hooks/user_prompt_submit.py` | (none) |
  | `SessionStart` | `hooks/session_start.py` | (none) |
  | `PostToolUse` | `hooks/post_tool_use.py` | `"Task|Agent"` |

  For each entry:
  1. Compute `command = f"uv run python {plugin_root / hook_file}"` (absolute
     resolved path — same form as `_register_pretooluse_hook`).
  2. `event_list = data.setdefault("hooks", {}).setdefault(event, [])`.
  3. **Find the block by command, not by matcher/event alone:** scan `event_list`
     for a block whose inner `hooks` already contain an entry with
     `command == command`. If found, that is the target block (leave sibling
     blocks for other commands untouched).
  4. If not found, append a new block: `{"matcher": matcher, "hooks": []}` when a
     matcher is specified, else `{"hooks": []}` (no `matcher` key for
     `UserPromptSubmit`/`SessionStart`).
  5. When a matcher is specified, set the target block's `matcher` in place
     (idempotent when already canonical). When no matcher is specified, do not add
     a `matcher` key.
  6. Append `{"type": "command", "command": command}` to the block's inner hooks
     **only if** no entry with that command already exists (idempotency guard —
     identical to `_register_pretooluse_hook:369-374`).
  7. Reuse the same file read/parse/create scaffolding and the trailing-newline
     write (`json.dumps(data, indent=2) + "\n"`). Prefer a single read → mutate
     all four events → single write, so one call registers `PreToolUse` +
     the three new hooks together and writes once.

  Add module docstring/comment cross-references to INFRA-192 / INFRA-175 /
  INFRA-182 (the three hooks) and CER-067 (why they must be downstream-registered),
  mirroring the INFRA-206 comment block at `bootstrap.py:309-314`.

- **Wire both call sites.** Replace / extend the `_register_pretooluse_hook` call
  at `bootstrap.py:1143` and at `sync.py:616` so both invoke the generalized
  registrar (either the single combined function, or `_register_pretooluse_hook`
  followed by `_register_context_budget_hooks`). Update the adjacent dry-run echo
  at `bootstrap.py:1140-1141` and the section comment at `bootstrap.py:1136-1137`
  to reflect that the budget-gate hooks are now registered too. Do **not** disturb
  the `_merge_deny_list` / `_merge_allow_rules` / `_prune_superseded_deny_entries`
  sequencing around either call site.

- **Do NOT register the four deferred blocks.** No `Stop`,
  `PermissionRequest`/`ExitPlanMode`, `PostToolUse` `Write|Edit|MultiEdit`, or
  `SessionEnd` entries. Add a comment at the registrar naming the four deferred
  blocks and the reason (companion-sidebar relays; separate product decision;
  out of scope for the correctness fix).

- **Add tests in `tests/pairmode/test_bootstrap.py`** (new class, e.g.
  `TestRegisterContextBudgetHooks`, alongside the existing
  `TestRegisterPreToolUseHook` at `test_bootstrap.py:2988`). Reuse the
  `_plugin_root()` / `_find_block_with_command()` helper pattern. Cover:
  - `test_registers_user_prompt_submit` — after the call, `UserPromptSubmit` has a
    matcher-less block carrying the `user_prompt_submit.py` command.
  - `test_registers_session_start` — same for `SessionStart` /
    `session_start.py`.
  - `test_registers_posttooluse_task_agent` — `PostToolUse` has a block with
    matcher `"Task|Agent"` carrying the `post_tool_use.py` command.
  - `test_posttooluse_task_agent_is_sibling_of_existing_block` — pre-populate a
    `PostToolUse` block for a local pytest hook (e.g. matcher `"Edit|Write"`,
    command `uv run python /some/pytest_runner.py`); after the call, assert **both**
    blocks exist (the pytest block unchanged, plus the new `Task|Agent` block), and
    the pytest command was neither moved nor duplicated.
  - `test_context_budget_hooks_idempotent` — call twice; for each of the three new
    events assert exactly one block carrying the hook command and exactly one copy
    of the command.
  - `test_does_not_register_deferred_blocks` — after the call, assert `Stop`,
    `PermissionRequest`, `SessionEnd` are absent, and `PostToolUse` contains **no**
    block for the `Write|Edit|MultiEdit` file-change relay command
    (`post_tool_use.py` under a `Write|Edit|MultiEdit` matcher is not added).
  - `test_pretooluse_still_registered_alongside` — a single registrar invocation
    leaves the INFRA-206 `PreToolUse` `Task|Agent|Edit|Write|Read` block intact.

- **Update `docs/architecture.md`** (currency only): the paragraph at
  `architecture.md:1064-1068` frames the "downstream registrar" (INFRA-206) as
  wiring only the three `PreToolUse` branches. Add a sentence (or extend that
  paragraph) noting that as of INFRA-208 the downstream registrar also wires the
  three context-budget-gate hooks (`UserPromptSubmit`, `SessionStart`,
  `PostToolUse` `Task|Agent`) into downstream `settings.json`, and that the four
  companion/sidebar blocks remain opt-in. Keep the edit minimal and scoped to
  reflecting current behavior — no structural rewrite.

## Tests

`story_class: code` — real registrar behavior change plus new tests. Run the
gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

New cases in `tests/pairmode/test_bootstrap.py` (`TestRegisterContextBudgetHooks`):

- `test_registers_user_prompt_submit`
- `test_registers_session_start`
- `test_registers_posttooluse_task_agent`
- `test_posttooluse_task_agent_is_sibling_of_existing_block`
- `test_context_budget_hooks_idempotent`
- `test_does_not_register_deferred_blocks`
- `test_pretooluse_still_registered_alongside`

Existing `TestRegisterPreToolUseHook` (INFRA-206) must continue to pass unchanged.

## Out of scope

- **The four companion/sidebar blocks** (`Stop`, `PermissionRequest`/`ExitPlanMode`,
  `PostToolUse` `Write|Edit|MultiEdit`, `SessionEnd`) — deliberately deferred as
  opt-in (see Chosen approach). A future story may register them behind a
  sidebar-adoption flag.
- **Retroactively fixing already-bootstrapped fleet projects.** This story changes
  only what future bootstrap / sync runs write; rolling the new registrations out
  across the existing fleet's on-disk `settings.json` files is **INFRA-209**.
- `hooks/hooks.json` and any `hooks/` script — already correct; the gap is only in
  the downstream registrar.
- Any change to the command form (`uv run python <abs path>`), the plugin-root
  computation, or the deny-list / allow-rules merge logic.
