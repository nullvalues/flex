---
id: INFRA-269
rail: INFRA
title: Hook-registration dedupe with audit subcommand and DP8 duplicate-hook check (CER-081)
status: complete
phase: "105"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/pairmode_sync.py
  - skills/pairmode/scripts/fleet_discovery.py
touches:
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_pairmode_sync.py
  - tests/pairmode/test_fleet_discovery.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-269.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase 105 de-risks the fleet campaign before Phase 106 drives migration from
flex. The single largest live defect blocking that campaign is CER-081: every
already-migrated project is running **two copies of every flex hook**, one from
the stale `/mnt/work/flex` checkout and one from `/mnt/work/flex-harness`.

The mechanism is precise. `bootstrap.py`'s two registrars —
`_register_pretooluse_hook` and `_register_context_budget_hooks` — locate the
target block by scanning for an inner hook entry whose `command` string equals
the computed absolute command. Only when that exact-command scan finds nothing
do they fall back to `_find_block_by_command_basename`, which is the in-place
migration path INFRA-228 added for the 0.2.0 → 0.3.0 plugin-root move. The
fallback is therefore reachable **only while the correct block is absent**. A
project that already has both a stale `/mnt/work/flex`-pointing entry *and* a
correct `/mnt/work/flex-harness`-pointing entry short-circuits on the exact
match, never reaches the basename fallback, and keeps the stale entry forever.
INFRA-228 fixed the forward path and left the retroactive state untouched.

Claude Code does not deduplicate or override hooks: both registered commands
execute independently on every event. So each of these projects runs the
*pre-migration* code path alongside the current one — reintroducing every bug
already fixed on the harness line (INFRA-246's reviewer-spawn context-budget
gate, INFRA-236's effort recording) and producing duplicate, racing writes to
`.companion/state.json` and `effort.db` from two different code versions. This
was confirmed on all four migrated fleet projects surveyed (aab, asp, coherra,
forqsite): two blocks per event across `PreToolUse`, `UserPromptSubmit`,
`SessionStart`, and `PostToolUse`. They were hand-cleaned in that session; no
code fix was applied, so the next survey will find the same state on any
project that was not hand-touched.

CER-081 names three fix directions and this story builds all three, because
each covers a gap the others do not:

1. **Registration dedupe** — stop creating the state. The registrars must
   remove *all* stale same-basename entries for an event, not just migrate when
   the correct block is absent.
2. **An audit subcommand** — clean the state that already exists on the eight
   migrated projects, and serve afterwards as a periodic drift check. Fixing
   the registrar alone does not help a project until someone re-runs
   `sync-all --apply` there.
3. **A DP8 discovery check** — make the condition *visible* fleet-wide. The
   pre-fold `fleet_discovery.py` run is the authoritative gate before the fold;
   it currently reports binding signals only and would pass a fleet where every
   project is double-firing.

This is the phase's first story and the ordering constraint (`docs/phases/phase-105.md`
§ Ordering) puts it ahead of INFRA-270, which touches `fleet_discovery.py` next.

## Requires

- No prior story in phase 105 is a prerequisite; INFRA-269 is first in the
  phase's build order. INFRA-270 edits `fleet_discovery.py` after this story,
  so this story's discovery changes land first and 270 rebases onto them.
- `skills/pairmode/scripts/bootstrap.py` exposes, at spec-time anchors (locate
  by name, never by line): `PRETOOLUSE_MATCHER` (337, value
  `"Task|Agent|Edit|Write|Read"`), `_find_block_by_command_basename` (340),
  `_register_pretooluse_hook` (361), `CONTEXT_BUDGET_HOOK_SPECS` (451, a
  3-tuple of `{"event", "hook_file", "matcher"}` dicts for `UserPromptSubmit` /
  `hooks/user_prompt_submit.py` / `None`, `SessionStart` /
  `hooks/session_start.py` / `None`, `PostToolUse` / `hooks/post_tool_use.py` /
  `"Task|Agent"`), and `_register_context_budget_hooks` (458). Both registrars
  build their command as `f"uv run python {path}"`, read the settings file with
  a `json.JSONDecodeError` → `{}` fallback, and write
  `json.dumps(data, indent=2) + "\n"`.
- `_find_block_by_command_basename(block_list, basename)` returns the **first**
  `(block, entry)` pair whose `command.rsplit("/", 1)[-1] == basename`, or
  `None`. It has no all-matches variant today — that absence is the bug.
- `skills/pairmode/scripts/pairmode_sync.py` defines a `@click.group("pairmode")`
  named `pairmode_cli` (999) and registers six subcommands via `add_command`
  (1004-1013): `sync-agents`, `sync-build`, `sync-all`, plus `register`,
  `unregister`, `list-projects` imported from `pairmode_register`. `sync_all`
  (915) chains downstream commands by `subprocess.run` with fail-fast on a
  non-zero exit, and follows the safe-by-default `--dry-run` / `--apply` /
  `--yes` flag convention.
- `skills/pairmode/scripts/fleet_discovery.py` exposes `_check_signal1` (103),
  `_check_signal2` (154), `discover` (175), `_write_snapshot` (221) and a
  single `@click.command()` `cli` (310) with `--candidate-dir`,
  `--candidates-file`, `--snapshot`, `--no-snapshot`, `--json`. `discover`
  returns dicts keyed `path, signal1, signal1_value, signal2, signal2_value,
  binding` and **skips any directory matching neither signal**. `_write_snapshot`
  emits a `## Pre-fold gate notice (DP8)` section and a `## Discovered fleet`
  section.
- `fleet_discovery.py` is read-only with respect to scanned projects; three
  existing tests pin this (`test_discover_does_not_modify_fixture_files`,
  `test_check_signal1_does_not_write`, `test_check_signal2_does_not_write`,
  `test_snapshot_does_not_write_to_scanned_project`). That constraint is
  absolute and this story does not relax it.
- Test files that exist and must be extended, not replaced:
  `tests/pairmode/test_bootstrap.py` (hook-registration tests live in a class
  around lines 3267-3900, including
  `test_register_pretooluse_hook_migrates_stale_plugin_root` and
  `test_context_budget_hooks_migrate_stale_plugin_root` — the in-place
  migration behaviour this story must **not** regress),
  `tests/pairmode/test_pairmode_sync.py`, `tests/pairmode/test_fleet_discovery.py`.
- `tests/pairmode/test_cli_surface_freeze.py` snapshots only `flex_build.py`'s
  group and asserts the live surface is a **superset**: new subcommands are
  explicitly allowed (`test_additions_are_allowed`). This story adds no
  `flex_build.py` subcommand, so the fixture needs no regeneration.
- `docs/cer/backlog.md` contains a `CER-081` row whose `Phase` cell reads `98`.
- Known environmental failure inside fresh story worktrees:
  `tests/pairmode/test_observability_ui.py::test_ui_build_emits_dist_index_html`
  (CER-090). Not caused by this story.

## Ensures

**A. Registration dedupe — the registrars remove every stale same-basename entry.**

1. `bootstrap.py` defines `_find_all_entries_by_command_basename(block_list: list[dict], basename: str) -> list[tuple[dict, dict]]`
   returning **every** `(block, entry)` pair in document order whose
   `command.rsplit("/", 1)[-1] == basename`, and `[]` when none match. The
   existing `_find_block_by_command_basename` still exists and still returns the
   first pair or `None`.
2. `bootstrap.py` defines `_prune_stale_hook_entries(block_list: list[dict], basename: str, keep_command: str) -> int`
   which removes every inner hook entry whose command basename equals
   `basename` and whose command is **not** equal to `keep_command`, removes any
   block left with an empty `hooks` list, and returns the number of entries
   removed. It never removes an entry whose basename differs from `basename`.
3. After `_register_pretooluse_hook(settings_path, plugin_root)` runs against a
   settings file containing **both** a block whose command is
   `uv run python <plugin_root>/hooks/pre_tool_use.py` and a separate block
   whose command is `uv run python /mnt/work/flex/hooks/pre_tool_use.py`, the
   resulting `hooks.PreToolUse` list contains **exactly one** inner hook entry
   whose command basename is `pre_tool_use.py`, and that entry's command is the
   `plugin_root` one.
4. The same call leaves untouched any `PreToolUse` block whose entries all have
   a different basename (e.g. a local `my_guard.py` hook): that block is still
   present, with the same matcher and the same inner hooks, after the call.
5. After `_register_context_budget_hooks(settings_path, plugin_root)` runs
   against a settings file where each of `UserPromptSubmit`, `SessionStart` and
   `PostToolUse` holds both a `plugin_root`-pointing block and a stale
   `/mnt/work/flex`-pointing block for the same hook file, each of the three
   event lists contains **exactly one** inner hook entry for that event's
   basename, and it is the `plugin_root` one.
6. The same call leaves any unrelated sibling `PostToolUse` block (e.g. a local
   pytest-runner hook with a different basename) present and unmodified.
7. Both registrars remain idempotent: running either twice in a row against the
   same settings file produces byte-identical output on the second run.
8. Both registrars still perform the pre-existing in-place migration when only a
   stale entry exists and no correct entry does — the entry's command is
   rewritten in place and no new block is appended. The existing tests
   `test_register_pretooluse_hook_migrates_stale_plugin_root` and
   `test_context_budget_hooks_migrate_stale_plugin_root` pass unchanged.
9. `_register_pretooluse_hook` still sets the surviving block's `matcher` to
   `PRETOOLUSE_MATCHER`, and `_register_context_budget_hooks` still sets each
   surviving block's matcher to that spec's matcher when the spec's matcher is
   not `None` (and adds no `matcher` key when it is `None`).
10. Neither registrar raises on a settings file that is absent, empty, or
    contains invalid JSON; the existing `json.JSONDecodeError` → `{}` fallback
    is preserved and a settings file whose `hooks` value is not a dict, or whose
    event value is not a list, is treated as absent rather than crashing.

**B. `pairmode_sync.py audit-hooks` — audit and clean an existing project.**

11. `pairmode_sync.py` registers a subcommand named exactly `audit-hooks` on
    `pairmode_cli`, so
    `uv run python skills/pairmode/scripts/pairmode_sync.py audit-hooks --help`
    exits 0 and prints its help. `pairmode_cli` still exposes all six
    pre-existing subcommands.
12. `audit-hooks` accepts `--project-dir` (default `.`), `--dry-run` (default
    true), `--apply` (default false, overrides `--dry-run`), and `--yes` / `-y`
    — the same flag names and safe-by-default semantics as `sync-all`.
13. Without `--apply`, `audit-hooks` writes nothing: the target
    `.claude/settings.json` is byte-identical before and after the invocation,
    even when duplicates are found.
14. On a project whose `.claude/settings.json` holds two entries with the same
    command basename under one event, `audit-hooks` prints a line naming the
    event, the basename, and both full commands, and exits **1** in dry-run
    mode (duplicates found) — so it is usable as a drift check in a shell
    conditional.
15. On a project with no duplicate hook registrations, `audit-hooks` exits
    **0** and prints a line stating no duplicates were found.
16. With `--apply`, `audit-hooks` removes every duplicate so that each
    (event, command-basename) pair retains exactly one entry, removes any block
    left with an empty `hooks` list, writes the file with
    `json.dumps(data, indent=2) + "\n"`, and exits **0**.
17. When `--apply` must choose which of several same-basename entries to keep,
    it keeps the one whose command path is under this checkout's plugin root
    (the flex root that `pairmode_sync.py` itself resolves from `__file__`); if
    none is, it keeps the first in document order. The kept command is printed.
18. `audit-hooks --apply` on a project with no duplicates leaves the settings
    file byte-identical and exits 0 (idempotent).
19. `audit-hooks` never touches any key of `.claude/settings.json` outside
    `hooks`: `permissions`, `env`, and any unknown top-level keys survive a
    `--apply` run byte-for-byte in value (allowing only re-serialisation
    formatting from the shared `json.dumps(..., indent=2)` write).
20. `audit-hooks` on a project with no `.claude/settings.json` exits 0, writes
    nothing, and prints a line saying there is no settings file to audit — it
    does not create one.

**C. DP8 discovery check — duplicates are visible fleet-wide.**

21. `fleet_discovery.py` defines `_check_duplicate_hooks(project_dir: Path) -> list[dict]`
    returning one dict per duplicated (event, basename) pair with keys `event`,
    `basename`, and `commands` (the list of full command strings, in document
    order), and `[]` when the project has no `.claude/settings.json`, an
    unparseable one, or no duplicates. It never writes to `project_dir`.
22. Each dict `discover()` returns gains a `duplicate_hooks` key holding that
    list. `discover()`'s existing keys (`path`, `signal1`, `signal1_value`,
    `signal2`, `signal2_value`, `binding`) and its rule of skipping directories
    that match neither signal are unchanged.
23. `fleet_discovery.py --json` output includes `duplicate_hooks` for every
    fleet entry; the top-level shape stays `{"flex_root": ..., "fleet": [...]}`.
24. The human-readable (non-`--json`) output prints, for any project with a
    non-empty `duplicate_hooks`, a line beginning `DUPLICATE HOOKS` naming the
    project and each duplicated event, and prints a fleet-level summary line
    giving the count of projects with duplicates.
25. `_write_snapshot` emits a `## Duplicate hook registrations (CER-081)`
    section listing each affected project and its duplicated events, or an
    explicit "none found" line when the fleet is clean. The existing
    `## Pre-fold gate notice (DP8)` and `## Discovered fleet` sections and
    their content are unchanged.
26. `fleet_discovery.py` remains read-only with respect to scanned projects:
    the four existing read-only tests still pass, and a new test asserts
    `_check_duplicate_hooks` does not modify or create any file under a scanned
    project directory.
27. `fleet_discovery.py`'s CLI exit status is unchanged (0 on a successful
    scan) — the duplicate check is reported, not enforced, at discovery time.
    The enforcing instrument is `audit-hooks` (Ensures 14).

**D. Documentation and backlog.**

28. `docs/architecture.md` documents, in the section covering pairmode hook
    registration / `bootstrap.py`, that hook registration is
    **dedupe-on-write**: at most one entry per (event, command-basename) pair
    survives a registrar run, and stale same-basename entries pointing at a
    different plugin root are removed rather than left as siblings (CER-081,
    INFRA-269). It also names `pairmode_sync.py audit-hooks` as the retroactive
    cleaner and periodic drift check, and `fleet_discovery.py`'s
    `duplicate_hooks` field as the DP8 fleet-level signal.
29. `docs/cer/backlog.md`'s `CER-081` row ends with a bolded
    `**RESOLVED phase 105 (INFRA-269) — ...**` note naming all three fixes
    (registrar dedupe, `audit-hooks`, DP8 `duplicate_hooks` check), and its
    `Phase` cell reads `105` instead of `98`. The original finding text is not
    deleted or re-worded.

## Instructions

Build in the order A → B → C → D. A and C are independent; B should reuse A's
pruning helper rather than re-implementing it, so build A first.

**Ideology note (Step 4a, `docs/ideology.md`):** no conflict; nothing resolved
inline. The *"hooks are thin relays only"* and *"sidebar owns all state writes"*
constraints are respected — this story changes only *which* hook commands are
registered, never what a hook does, and every write is performed by a skill
script (`bootstrap.py`, `pairmode_sync.py`), never by a hook.
`fleet_discovery.py` stays read-only with respect to scanned projects, which is
the same single-writer discipline. The story is a direct application of
*"never silently pass contradictions"*: two hook blocks for one event is exactly
a contradiction the system currently passes silently, and Ensures 14/24/25 make
it loud.

### A — `bootstrap.py` registrar dedupe

1. Add `_find_all_entries_by_command_basename(block_list, basename)` directly
   beneath `_find_block_by_command_basename`, mirroring its docstring style and
   its `command.rsplit("/", 1)[-1] == basename` full-segment match (not
   `endswith` — a bare suffix test false-positives on `my_pre_tool_use.py`).
   Keep `_find_block_by_command_basename` as-is: the in-place migration path
   (Ensures 8) still wants "first match" semantics and re-expressing it in terms
   of the new helper is optional, not required.
2. Add `_prune_stale_hook_entries(block_list, basename, keep_command) -> int`
   beneath it. Implementation: iterate the blocks; for each, filter its `hooks`
   list to drop entries whose command basename equals `basename` and whose
   command `!= keep_command`; count the drops; then remove from `block_list`
   any block whose `hooks` list is now empty. Mutate the passed list in place
   (both call sites hold it via `hooks_top.setdefault(...)`) and return the
   count. Guard non-dict blocks and non-list `hooks` values by skipping them —
   a hand-edited settings file must not crash the registrar (Ensures 10).
3. In `_register_pretooluse_hook`, after the block is resolved and the command
   appended (i.e. after the `already_registered` append and before the write),
   call
   `_prune_stale_hook_entries(pre_tool_use_list, pre_tool_use_path.name, command)`.
   Placing the prune **after** the existing find/migrate/append logic is
   deliberate: it means the correct entry is guaranteed to exist before anything
   is deleted, so a prune can never leave the event with zero flex hooks. Do not
   restructure the exact-command scan or the basename fallback — they still
   carry Ensures 7 and 8.
4. Make the identical change inside `_register_context_budget_hooks`'s per-spec
   loop: after the inner-hooks append for that spec, call
   `_prune_stale_hook_entries(event_list, hook_path.name, command)`. The
   basename is per-spec (`user_prompt_submit.py`, `session_start.py`,
   `post_tool_use.py`), which is what isolates each event's hook from unrelated
   sibling blocks (Ensures 6).
5. Do not change `PRETOOLUSE_MATCHER` or `CONTEXT_BUDGET_HOOK_SPECS`. Do not
   add or remove entries from `CONTEXT_BUDGET_HOOK_SPECS` — the four
   deliberately-excluded companion-sidebar hooks (INFRA-208) stay excluded and
   are out of scope.
6. Do not change the `bootstrap()` call sites (around lines 1299-1308) or the
   dry-run message text — the registrars keep their signatures.

### B — `pairmode_sync.py audit-hooks`

7. Add the subcommand as a module-level `@click.command("audit-hooks")`
   function named `audit_hooks`, and register it with
   `pairmode_cli.add_command(audit_hooks)` alongside the existing three
   `add_command` calls (before the `pairmode_register` import block, to keep
   the sync-owned commands grouped). Options exactly as Ensures 12: mirror
   `sync_all`'s option definitions verbatim so the help text and defaults match
   the rest of the group.
8. Factor the audit itself into a pure helper,
   `_audit_duplicate_hooks(settings_path: Path) -> list[dict]`, returning one
   dict per duplicated (event, basename) pair — `{"event", "basename",
   "commands"}` — so the command function only does I/O, printing and exit
   codes. This is the same shape `fleet_discovery._check_duplicate_hooks`
   returns (Ensures 21); the two are twins and each should carry a comment
   naming the other. **Do not import `fleet_discovery` from `pairmode_sync` or
   vice versa** — a fleet-scanning module and a per-project sync module must not
   take a dependency on each other for a dozen lines of dict grouping.
9. For the `--apply` path, reuse `bootstrap._prune_stale_hook_entries` by
   importing it (`from bootstrap import _prune_stale_hook_entries`) — the
   sibling-script import style already used for
   `from pairmode_register import register, unregister, list_projects`. Choose
   `keep_command` per Ensures 17: prefer the entry whose command path is under
   the flex root resolved from `pairmode_sync.py`'s own `__file__` (walk up from
   `Path(__file__).resolve()` past `scripts/`, `pairmode/`, `skills/`), else the
   first in document order. Print the kept command and each removed command.
10. Honour `--yes`: when duplicates are found in `--apply` mode and `--yes` was
    not passed, prompt with `click.confirm("Apply? [y/N]", default=False,
    prompt_suffix="")` — the same prompt shape `sync_build` uses — and exit 0
    without writing if declined.
11. Exit codes are load-bearing (Ensures 14/15/16): dry-run with duplicates →
    `sys.exit(1)`; dry-run clean → 0; `--apply` that cleaned successfully → 0;
    no settings file → 0. Do not raise `click.ClickException` for the
    duplicates-found case — its exit code is 1 too but its `Error:` prefix
    misreports a successful audit as a failure.
12. Write with `json.dumps(data, indent=2) + "\n"`, matching both registrars.
    Do not reorder keys, do not sort, do not add a `sort_keys=True`.
13. Do **not** wire `audit-hooks` into `sync_all`'s invocation chain. `sync-all`
    is fail-fast on non-zero exits and `audit-hooks` deliberately exits 1 on a
    finding, so chaining it would abort every sync on a project with pre-existing
    duplicates. Keep it a standalone command; the campaign runbook calls it
    explicitly.

### C — `fleet_discovery.py` DP8 duplicate check

14. Add `_check_duplicate_hooks(project_dir)` beside `_check_signal2`,
    following the same defensive shape those two use: return `[]` on a missing
    file, and catch `(json.JSONDecodeError, OSError)` → `[]`. Read
    `project_dir / ".claude" / "settings.json"`, walk `data.get("hooks", {})`
    per event, group inner-hook commands by
    `command.rsplit("/", 1)[-1]`, and emit a dict for each basename with more
    than one command. Skip non-dict/non-list shapes rather than raising.
15. In `discover()`, call it for each directory that matched at least one signal
    (i.e. after the `if not s1 and not s2: continue` guard — an unbound project
    is not part of the fleet and must not be scanned) and add
    `"duplicate_hooks": _check_duplicate_hooks(d)` to the result dict.
16. In `cli()`'s non-JSON branch, print a `DUPLICATE HOOKS` line per affected
    project inside the existing per-project loop, and a fleet summary line
    (e.g. `Projects with duplicate hooks: N`) alongside the existing
    `Bound projects found:` line. The `--json` branch needs no change beyond
    what step 15 already puts in the dicts (Ensures 23).
17. In `_write_snapshot`, append the new `## Duplicate hook registrations
    (CER-081)` section after `## Discovered fleet`. Do not modify the
    `## Pre-fold gate notice (DP8)` text — that block is the fold gate's own
    statement of authority and is quoted elsewhere.
18. Do not change `fleet_discovery.py`'s exit status or add a `--fail-on-duplicates`
    flag. Discovery reports; `audit-hooks` enforces (Ensures 27).

### D — docs and backlog

19. Make the `docs/architecture.md` edit (Ensures 28). Locate the existing
    section that covers `bootstrap.py`'s hook registration (search for
    `PRETOOLUSE_MATCHER` or `_register_context_budget_hooks`); extend it rather
    than opening a new top-level section.
20. Append the `CER-081` RESOLVED note and set its `Phase` cell to `105`
    (Ensures 29). Match the in-file convention used by other resolved rows
    (e.g. CER-082's `**RESOLVED phase 104 (INFRA-267) — ...**`). The backlog is
    append-only history: do not delete or re-word the original finding.

## Tests

Run from the story worktree root with `PATH=$HOME/.local/bin:$PATH`.

**1. New/extended unit tests.** Add to the existing files — no new test module:

- `tests/pairmode/test_bootstrap.py` (alongside the existing hook-registration
  tests):
  - `test_register_pretooluse_hook_removes_stale_sibling_block` — settings with
    both a `plugin_root` block and a `/mnt/work/flex` block; after the call,
    exactly one `pre_tool_use.py` entry remains and it is the `plugin_root`
    one (Ensures 3). This is the CER-081 regression test.
  - `test_register_pretooluse_hook_preserves_unrelated_basename_block` —
    Ensures 4.
  - `test_context_budget_hooks_remove_stale_sibling_blocks` — all three events
    doubled; one entry each afterwards (Ensures 5).
  - `test_context_budget_hooks_preserve_unrelated_posttooluse_block` —
    Ensures 6.
  - `test_register_hooks_idempotent_after_dedupe` — run each registrar twice;
    second run produces byte-identical output (Ensures 7).
  - `test_prune_stale_hook_entries_removes_emptied_block` — direct unit test of
    `_prune_stale_hook_entries` (Ensures 2), including the return count.
  - `test_registrars_tolerate_malformed_hooks_shape` — `hooks` is a list, or an
    event value is a string; no exception (Ensures 10).
  - The existing `test_register_pretooluse_hook_migrates_stale_plugin_root` and
    `test_context_budget_hooks_migrate_stale_plugin_root` must pass unchanged
    (Ensures 8) — do not edit them.
- `tests/pairmode/test_pairmode_sync.py`:
  - `test_audit_hooks_registered_on_group` — `"audit-hooks" in pairmode_cli.commands`
    and all six pre-existing names still present (Ensures 11).
  - `test_audit_hooks_dry_run_writes_nothing_and_exits_1` — via
    `click.testing.CliRunner`; settings byte-identical, `result.exit_code == 1`
    (Ensures 13, 14).
  - `test_audit_hooks_clean_project_exits_0` — Ensures 15.
  - `test_audit_hooks_apply_removes_duplicates` — Ensures 16, asserting one
    entry per (event, basename) and no empty blocks.
  - `test_audit_hooks_apply_keeps_local_plugin_root_entry` — Ensures 17.
  - `test_audit_hooks_apply_is_idempotent` — Ensures 18.
  - `test_audit_hooks_preserves_non_hook_keys` — a settings file with
    `permissions` and an unknown key; both survive `--apply` (Ensures 19).
  - `test_audit_hooks_no_settings_file_exits_0` — Ensures 20.
- `tests/pairmode/test_fleet_discovery.py` (extend the existing `fleet` fixture
  or add a sibling fixture with a duplicated-hook project):
  - `test_check_duplicate_hooks_finds_doubled_event` — Ensures 21.
  - `test_check_duplicate_hooks_empty_for_clean_project` and
    `_for_missing_settings` and `_for_unparseable_settings` — Ensures 21.
  - `test_discover_includes_duplicate_hooks_key` — every result dict has the
    key; existing keys unchanged (Ensures 22).
  - `test_json_output_includes_duplicate_hooks` — Ensures 23.
  - `test_text_output_reports_duplicate_hooks` — Ensures 24.
  - `test_snapshot_has_duplicate_hooks_section` — Ensures 25, and assert the
    `## Pre-fold gate notice (DP8)` text is still present verbatim.
  - `test_check_duplicate_hooks_does_not_write` — Ensures 26, matching the
    existing read-only tests' assertion style.
  - `test_cli_exit_status_unchanged_with_duplicates` — Ensures 27.

**2. Targeted run** — the three touched test files plus the CLI-surface guard:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_bootstrap.py \
  tests/pairmode/test_pairmode_sync.py \
  tests/pairmode/test_fleet_discovery.py \
  tests/pairmode/test_cli_surface_freeze.py -q 2>&1 | tail -20
```

Acceptance: all green.

**3. Full suite, without `-x`** (a known pre-existing failure must not mask a
real one — run to completion and compare the failure set against the CER-090
baseline):

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance: green except, inside a worktree only,
`test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-090). Any
other failure blocks the story.

**4. CLI smoke — the new subcommand is reachable and safe:**

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  audit-hooks --help
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/pairmode_sync.py \
  audit-hooks --project-dir . ; echo "exit=$?"
git status --porcelain .claude/settings.json
```

Acceptance: `--help` exits 0 and lists `--project-dir`, `--dry-run`, `--apply`,
`--yes`. The dry-run invocation exits 0 or 1 depending on this repo's own
settings state, and `git status --porcelain` prints **nothing** — dry-run wrote
nothing (Ensures 13).

**5. DP8 discovery smoke — the new field appears, nothing is written to any
scanned project:**

```bash
PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/fleet_discovery.py \
  --json --no-snapshot 2>&1 | head -40
```

Acceptance: exits 0; every entry under `"fleet"` carries a `"duplicate_hooks"`
key. Pass `--no-snapshot` so the smoke run does not rewrite
`docs/fleet-snapshot.md` in the worktree; if you do want to see the snapshot
section, write it to a throwaway path with `--snapshot /tmp/fleet-smoke.md`.

**6. End-to-end dedupe proof on a synthetic project** (throwaway dir — do
**not** run the registrars against this repo's `.claude/settings.json`):

```bash
PATH=$HOME/.local/bin:$PATH uv run python -c "
import sys, json, pathlib, shutil
sys.path.insert(0, 'skills/pairmode/scripts')
d = pathlib.Path('/tmp/hookdedupe'); shutil.rmtree(d, ignore_errors=True)
(d / '.claude').mkdir(parents=True)
s = d / '.claude' / 'settings.json'
s.write_text(json.dumps({'hooks': {'PreToolUse': [
  {'matcher': 'Task|Agent|Edit|Write|Read', 'hooks': [
     {'type': 'command', 'command': 'uv run python /mnt/work/flex-harness/hooks/pre_tool_use.py'}]},
  {'matcher': 'Task', 'hooks': [
     {'type': 'command', 'command': 'uv run python /mnt/work/flex/hooks/pre_tool_use.py'}]},
]}}, indent=2))
import bootstrap
bootstrap._register_pretooluse_hook(s, pathlib.Path('/mnt/work/flex-harness'))
data = json.loads(s.read_text())
cmds = [h['command'] for b in data['hooks']['PreToolUse'] for h in b['hooks']
        if h['command'].rsplit('/', 1)[-1] == 'pre_tool_use.py']
assert cmds == ['uv run python /mnt/work/flex-harness/hooks/pre_tool_use.py'], cmds
print('OK: stale block removed ->', cmds)"
```

Acceptance: prints `OK: stale block removed -> [...]`. The identical command
against pre-story `HEAD` fails the assertion with two commands — that contrast
is the story's headline evidence and belongs in the BUILD-RESULT notes.

## Out of scope

- **Retroactively cleaning the eight migrated fleet projects.** This story ships
  the *tool* (`audit-hooks`); running it across the fleet is Phase 106's
  migration campaign. Cross-repo writes from this build are forbidden regardless.
- **Registering the four deliberately-excluded companion-sidebar hooks** (Stop,
  PermissionRequest/ExitPlanMode, PostToolUse Write|Edit|MultiEdit, SessionEnd —
  INFRA-208). Whether a downstream project runs the companion sidebar is a
  separate product decision; `CONTEXT_BUDGET_HOOK_SPECS` is unchanged here.
- **Deduplicating hooks at *runtime* inside the hook scripts themselves** (e.g.
  a lock or a first-writer-wins guard in `pre_tool_use.py`). That would put
  blocking logic in a hook, which `docs/ideology.md` § *Hooks are thin relays
  only* forbids with no override path. Registration-time dedupe is the correct
  layer.
- **Making `fleet_discovery.py` fail the fold on duplicates.** DP8's fold gate
  is an operator judgment reading the snapshot; wiring an exit code into it
  changes the gate's semantics and belongs to the fold story, not here
  (Ensures 27 pins the exit status as unchanged).
- **Auditing anything other than duplicate hook registrations** — stale
  `permissions` deny/allow entries, orphaned `env` keys, and `hooks.json`
  drift are all real drift classes and none of them are this subcommand's job.
- **`registered_projects` seeding or Signal-1 false negatives** — that is
  INFRA-270's scope (CER-058, CER-059), the next story in this phase, which
  edits the same file.
- **Backporting the dedupe to the 0.2.x line on `main`.** The registrars change
  behaviour on write; per era 003 § *Versioning & compatibility* the breaking
  window is closed and this is additive, but deciding whether to fast-track it
  to `main` is the operator's call at fold time, not this builder's.
