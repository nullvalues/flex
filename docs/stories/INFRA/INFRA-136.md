---
id: INFRA-136
rail: INFRA
title: "`pairmode_sync.py sync-all` wrapper subcommand and SKILL.md entry"
status: complete
phase: "54"
story_class: code
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
  - skills/pairmode/SKILL.md
touches:
  - tests/pairmode/test_pairmode_sync.py
---

# INFRA-136 — `pairmode_sync.py sync-all` wrapper subcommand and SKILL.md entry

## Background

Pairmode currently exposes three independent sync entry points that the
orchestrator (or a human operator) must remember to invoke in the right order
when refreshing a project against the canonical methodology:

1. `skills/pairmode/scripts/sync.py` — rewrites methodology files
   (`CLAUDE.md`, `docs/*`, scaffold templates) based on the audit delta. It
   has no dry-run mode; it always applies. Invoked as a standalone script with
   `--project-dir` and `--yes`.
2. `pairmode_sync.py sync-agents` — re-renders the frontmatter of
   `.claude/agents/*.md` from canonical Jinja2 templates. Supports `--dry-run`
   and `--yes`.
3. `pairmode_sync.py sync-build` — diffs and (with `--apply`) rewrites
   `CLAUDE.build.md` from `CLAUDE.build.md.j2`. Defaults to dry-run; takes
   `--apply` and `--yes`.

Each is correct in isolation, but the orchestration sequence — "methodology sync,
then agent frontmatter, then CLAUDE.build.md" — is ceremony that today lives in
the operator's head and in SKILL.md prose. Every time it gets done manually,
there's risk of doing it in the wrong order, forgetting one of the three, or
running the wrong combination of flags across the trio.

Era 001's INFRA rail is shifting deterministic ceremony out of orchestrator
prose and into versioned, testable CLI code. A `sync-all` wrapper subcommand
on `pairmode_sync.py` is the natural home: it lives next to its two siblings,
shares their flag vocabulary, and can be invoked as a single CLI call.

The three downstream commands must remain individually callable — operators
frequently want to run just `sync-build`, or just `sync-agents`, without
touching the others. `sync-all` is a wrapper, not a replacement.

## Ensures

### `sync-all` subcommand

- A new `sync-all` click command is registered on the existing `pairmode_cli`
  group in `skills/pairmode/scripts/pairmode_sync.py`, alongside `sync-agents`
  and `sync-build`.
- Flags match the safe-by-default `sync-build` posture:
  - `--project-dir PATH` (default `"."`, `click.Path(file_okay=False)`).
  - `--dry-run` flag, default `True` — safe by default.
  - `--apply` flag — when present, overrides dry-run (mirrors `sync-build`).
  - `--yes` / `-y` flag — suppresses confirmation prompts; propagated to each
    downstream invocation.
- `_depth_guard_sync_build` runs against the resolved `--project-dir` before
  any downstream call.
- Downstream invocation order is fixed: `sync.py` → `sync-agents` → `sync-build`.
- Each downstream command is invoked as a subprocess via `subprocess.run`,
  letting stdout/stderr stream through to the terminal.
- Per-command output is preceded by a labeled header line:
  ```
  === sync (methodology files) ===
  === sync-agents (agent frontmatter) ===
  === sync-build (CLAUDE.build.md) ===
  ```
- `sync.py` has no `--dry-run` flag. The wrapper handles this asymmetry:
  - In dry-run mode (the default): `sync.py` is **skipped**; the wrapper emits
    `skipped: sync.py does not support --dry-run; pass --apply to run it`.
  - In `--apply` mode: `sync.py` is invoked with `--project-dir <dir>` and
    `--yes` if `--yes` was passed.
- `sync-agents` is always invoked. `--dry-run` is passed in dry-run mode;
  omitted when applying. `--yes` propagated when present.
- `sync-build` is always invoked. `--dry-run` passed in dry-run mode; `--apply`
  passed when applying. `--yes` propagated when present.
- The wrapper does not open its own confirmation prompt — confirmation is
  delegated to the downstream commands' own prompts (which respect `--yes`).
- If any downstream subprocess exits non-zero, the wrapper emits an error line
  on stderr identifying the failing command and exits non-zero with the same
  status code. Remaining commands in the chain are not invoked (fail fast).
- If all three succeed, the wrapper exits 0.

### SKILL.md entry

- `skills/pairmode/SKILL.md` gains a `### /flex:pairmode sync-all` section
  after `### /flex:pairmode sync-build` and before
  `### /flex:pairmode register / unregister / list-projects`.
- The section follows the format used by `sync-build` and `sync-agents`:
  invocation note callout block, **When to use**, **What it does** (covering
  the fixed order, dry-run skip of `sync.py`, delegation of confirmation,
  fail-fast behaviour), **CLI invocation**, **Flags**.
- The top-of-file `## Commands` summary gains `sync-all` alongside the other
  sync commands.

## Out of scope

- Adding a `--dry-run` flag to `sync.py` (separate, larger change).
- Parallelising the three downstream commands.
- Adding a combined audit-and-sync command.
- Modifying the existing `sync-agents` or `sync-build` subcommands.
- Removing or deprecating direct invocations of the three individual commands.

## Instructions

### 1. Add `sync_all` command to `pairmode_sync.py`

Add the new command above the `# --- CLI group ---` block (or after
`cmd_sync_build`, following the existing ordering convention). Decorator
and options mirror `sync-build`'s safe-by-default pattern:

- `--project-dir` (default `"."`, `click.Path(file_okay=False, dir_okay=True)`)
- `--dry-run` (is_flag=True, default=True)
- `--apply` (is_flag=True, default=False)
- `--yes` / `-y` (is_flag=True, default=False)

Function body:
1. Resolve `project_dir` to an absolute `Path`.
2. Call `_depth_guard_sync_build(project_path)`.
3. Derive `effective_apply = bool(apply)` (when `--apply` is set, dry-run mode
   is off regardless of `--dry-run`'s value — match `sync-build`'s logic).
4. Build a list of three `(label, argv, skip_in_dry_run)` tuples for the
   downstream invocations. Use `sys.executable` + the absolute path to each
   script for portability. For `sync-agents` and `sync-build`, build the
   argv so they invoke `pairmode_sync.py` directly with the appropriate
   subcommand name and flags. Append `--yes` to any argv when `yes=True`.
5. Iterate the tuples. For each: print the `=== <label> ===` header; if
   `skip_in_dry_run and not effective_apply`, print the skip notice and
   continue; otherwise call `subprocess.run(argv, check=False)` and on
   non-zero returncode print the error to stderr and `sys.exit(returncode)`.

### 2. Register the command

After `pairmode_cli.add_command(sync_build)`, add
`pairmode_cli.add_command(sync_all)`.

### 3. Update the module docstring

Add `sync-all` to the brief command list and add one usage example line.

### 4. SKILL.md — commands index

In the `## Commands` list, add `sync-all` next to the other sync commands.

### 5. SKILL.md — new section

Add the `### /flex:pairmode sync-all` section after `sync-build`, following
its structure. The **What it does** subsection must explicitly cover: fixed
invocation order, the `sync.py` dry-run skip, delegation of confirmation,
and fail-fast chain halt on non-zero exit.

### 6. Tests

Add test functions to `tests/pairmode/test_pairmode_sync.py`. Mock
`subprocess.run` in `pairmode_sync` to intercept downstream invocations
without spawning real processes. Each test asserts on recorded argv lists,
exit codes, and expected stdout/stderr content.

## Tests

Tests in `tests/pairmode/test_pairmode_sync.py`:

1. `test_sync_all_dry_run_default_skips_sync_py_and_passes_dry_run_to_others`
   — invoke with `--project-dir` only (dry-run default); assert `sync.py` not
   invoked, `sync-agents` invoked with `--dry-run`, `sync-build` invoked with
   `--dry-run`; assert exit 0; assert stdout contains all three headers and the
   `skipped:` notice.
2. `test_sync_all_apply_invokes_all_three_in_order` — invoke with `--apply`;
   assert all three invoked in order; assert no `--dry-run` in any argv;
   assert `sync-build` argv contains `--apply`; assert exit 0.
3. `test_sync_all_yes_propagates_to_all_in_apply_mode` — invoke with
   `--apply --yes`; assert every recorded argv contains `--yes`.
4. `test_sync_all_yes_in_dry_run_propagates_to_sync_agents_and_sync_build`
   — invoke with `--yes` only; assert `sync.py` skipped; assert
   `sync-agents` and `sync-build` argv each contain `--yes` and `--dry-run`.
5. `test_sync_all_halts_on_sync_py_failure` — mock `sync.py` to return
   exit 2 with `--apply`; assert `sync-agents` and `sync-build` not invoked;
   assert wrapper exits 2; assert stderr contains `halting chain`.
6. `test_sync_all_halts_on_sync_agents_failure` — mock `sync-agents` to exit
   1; assert `sync.py` invoked, `sync-agents` invoked, `sync-build` not;
   assert wrapper exits 1.
7. `test_sync_all_halts_on_sync_build_failure` — mock `sync-build` to exit 3;
   assert all three invoked; wrapper exits 3.
8. `test_sync_all_depth_guard_rejects_shallow_dir` — invoke with
   `--project-dir /tmp`; assert non-zero exit; assert no subprocess invoked.
9. `test_sync_all_project_dir_defaults_to_cwd` — invoke without
   `--project-dir`; assert downstream argvs include `--project-dir` set to
   resolved cwd.
10. `test_sync_all_header_separators_present_in_order` — invoke with
    `--apply`; assert stdout contains the three `=== … ===` headers in
    the correct order.
11. `test_sync_all_registered_on_pairmode_cli` — assert `"sync-all"` in
    `pairmode_cli.commands` (introspection only).
