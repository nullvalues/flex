---
id: INFRA-319
rail: INFRA
title: "Portable hook-command paths: plugin-root/settings.local registration, migrate rewrite of machine-absolute and pre-rename hook commands, audit finding"
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/hook_view.py
  - skills/pairmode/scripts/pairmode_migrate.py
touches:
  - skills/pairmode/scripts/sync.py
  - skills/pairmode/scripts/pairmode_sync.py
  - skills/pairmode/scripts/fleet_discovery.py
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_hook_view.py
  - tests/pairmode/test_pairmode_sync.py
  - tests/pairmode/test_pairmode_migrate.py
  - tests/pairmode/test_fleet_discovery.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-319.md
  - tests/pairmode/test_sync.py
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

**Pulled from CER-127** (`docs/cer/backlog.md`, operator-flagged 2026-07-29,
"fleet portability"). It is a live HIGH: registering a freshly-cloned project
with the observability UI on 2026-07-29 hard-blocked every prompt with

```
UserPromptSubmit ... /usr/bin/python3: can't open file
'/mnt/work/flex-harness/hooks/user_prompt_submit.py': [Errno 2] No such file or directory
```

Two distinct defects sit behind that one error, and the story must not conflate
them.

**Defect 1 — staleness.** Repos that went through the 0.2.x → 0.3.0 migration
still carry pre-rename `/mnt/work/flex-harness/hooks/*` commands in their
committed `.claude/settings.json`. `MIGRATION_RULES` (`pairmode_migrate.py:96`)
has fourteen rules and **none of them touches `.claude/settings.json`'s `hooks`
block** — rule 12 (`:215-223`) rewrites `.claude/settings.deny-rationale.json`
strings only. The registrars in `bootstrap.py` do carry a basename-based
in-place migration (`_find_block_by_command_basename`, used at `:481-486` and
`:620-630`) that *would* repair a stale command, but only when `bootstrap`/`sync`
is re-run on that project — which the migration campaign does not guarantee, and
which a fresh clone by definition has not done before its first prompt fires.

**Defect 2 — machine-boundness, which the repair in Defect 1 does not fix.**
Both registrars deliberately write an **absolute resolved path** computed from
`plugin_root` — `_register_pretooluse_hook` at `:445-446`
(`command = f"uv run python {pre_tool_use_path}"`) and
`_register_context_budget_hooks` at `:592-593`, with `plugin_root` supplied by
`sync.py:623` as `Path(__file__).resolve().parent.parent.parent.parent`. The
docstring at `:433-434` states the choice explicitly: *"computed from
plugin_root, never from `${CLAUDE_PLUGIN_ROOT}`"*. That decision is **correct and
must be preserved** — `${CLAUDE_PLUGIN_ROOT}` is expanded by Claude Code for
commands declared in a *plugin's* `hooks/hooks.json`, not for commands a project
writes into its own `.claude/settings.json`; emitting the literal token there
substitutes one unresolvable path for another. This story therefore does **not**
implement CER-127's fix direction (a) as literally worded.

The real defect in (a) is not the absolute path — it is that a machine-bound
absolute path is written into a **committed, shared** file. `.claude/settings.json`
is tracked in every fleet repo (confirmed: `git ls-files .claude/` in this repo
lists `settings.json`). A per-machine value in a shared file is portable for
exactly one machine. flex already has the right surface for per-machine values:
`.claude/settings.local.json`, which `permission_scope.py:93/:126` writes to,
`bootstrap.py:126` writes allow rules to, `scope_guard.py:39` treats as
machine-local, and `hook_view.py:154` already reads as the
`HOOK_SOURCE_SETTINGS_LOCAL` source. The merged view therefore already sees hooks
registered there — no detector loses coverage by the move.

**A third, smaller gap surfaced while spec'ing.** `_register_context_budget_hooks`
skips a spec when an installed plugin already provides the same
`(event, basename)` pair (INFRA-288/CER-104, `:579-603`).
`_register_pretooluse_hook` has **no such skip** — it registers `pre_tool_use.py`
unconditionally, so a project that gets `PreToolUse` from the flex plugin *and*
from settings runs it twice per event. That is the exact CER-104 shape INFRA-288
closed for the other three events, left half-closed on the fourth. Closing it here
is in scope because it is the same registrar surface this story already edits, and
because "prefer the plugin's `${CLAUDE_PLUGIN_ROOT}` entry over a settings-level
absolute path" is precisely CER-127's portability intent, correctly expressed.

**Relation to the recorded architecture.** `docs/architecture.md:2543-2560`
already records that flex's *own* hooks are canonically the plugin manifest, and
that `bootstrap.py`/`sync.py` still write a settings block for downstream fleet
projects "which may not have flex installed as a plugin at all". This story does
not reverse that; it refines it — downstream projects still get a settings-level
registration, but into the machine-local file, and only when no plugin already
provides the hook.

## Requires

Re-verified against the working tree at spec time (2026-07-29, `main` @
`2586ad4c`). A builder finding any anchor moved should re-locate by symbol name,
not line number, and note the drift in its report.

- `bootstrap.py::_register_pretooluse_hook` (`:427-512`) builds
  `command = f"uv run python {pre_tool_use_path}"` from
  `plugin_root / "hooks" / "pre_tool_use.py"` (`:445-446`) and writes the whole
  settings document at `:509-512`. It has **no** plugin-source skip.
- `bootstrap.py::CONTEXT_BUDGET_HOOK_SPECS` (`:529-533`) — three specs:
  `UserPromptSubmit`/`hooks/user_prompt_submit.py`/matcher `None`;
  `SessionStart`/`hooks/session_start.py`/`None`;
  `PostToolUse`/`hooks/post_tool_use.py`/`"Task|Agent"`.
- `bootstrap.py::_register_context_budget_hooks` (`:536-655`) computes
  `command = f"uv run python {hook_path}"` (`:592-593`), skips plugin-provided
  pairs (`:579-603`), and writes at `:652-655`.
- `bootstrap.py::_prune_stale_hook_entries` and `_find_block_by_command_basename`
  are the dedupe / in-place-migration helpers (CER-081, INFRA-269);
  `pairmode_sync.py:52` imports `_prune_stale_hook_entries` from `bootstrap`.
- `sync.py:623-625` resolves
  `plugin_root = Path(__file__).resolve().parent.parent.parent.parent` and calls
  both registrars in that order.
- `hook_view.py` exposes `HOOK_SOURCE_SETTINGS` / `HOOK_SOURCE_SETTINGS_LOCAL` /
  `HOOK_SOURCE_PLUGIN` (`:43-45`), `hook_sources()` (`:133`), `merged_hook_view()`
  (`:188`), `duplicate_hook_groups()` (`:245`). It is **stdlib-only** by contract
  (module docstring) — no `click`, no third-party import may be added.
- `pairmode_sync.py::audit_hooks` (`:1130-1311`) is the per-project audit CLI;
  `_audit_duplicate_hooks` (`:1100-1119`) delegates to
  `hook_view.duplicate_hook_groups(hook_view.merged_hook_view(project_dir))`.
- `fleet_discovery.py::_check_duplicate_hooks` (`:293`) is the fleet-scan twin.
- `pairmode_migrate.py::cmd_to_030` (`:907-918`) declares `--project-dir`
  (required) and `--apply` (flag). Its body is a sequence of banner-commented
  blocks (B5 state seed, B6 `expected_step_tokens`, B4 `pipe_path`, INFRA-290
  `context_story_tokens`, …), each echoing `[apply]` / `[would]` lines.
- `MIGRATION_RULES` has exactly **14** entries with sequential ids 1..14, pinned
  by `test_pairmode_migrate.py::test_migration_rules_has_14_entries` (`:737`) and
  `::test_migration_rules_ids_are_sequential_1_to_14` (`:740`).
- `.claude/settings.local.json` is ignored on this developer's machine via the
  **global** git ignore (`~/.config/git/ignore`), **not** via this repo's
  `.gitignore` — confirmed by `git check-ignore -v`. A fresh clone by another
  user has no such global rule. This is load-bearing for § Ensures A4.
- Baseline: `main`'s suite is green — 4116 passed, 211 skipped. A
  `test_observability_ui` failure inside a story worktree is the known CER-090
  vendored-payload gap: fix by `rsync`-ing the payload from the main checkout,
  **never** by `pnpm install`.

**Sibling-story coordination inside Phase 114.** INFRA-303 also edits
`skills/pairmode/scripts/pairmode_migrate.py` and also annotates
`docs/cer/backlog.md`. The two are compatible only if this story obeys § Ensures
B1: **do not add a `MigrationRule`** and do not renumber — INFRA-303 § Ensures A3
pins the 14-entry count, and a fifteenth rule breaks its tests. Hook-path repair
lands as a new `to-030` block instead. On `docs/cer/backlog.md`, edit only the
CER-127 row. No sibling story is a build-order prerequisite; if INFRA-303 has
already merged when this builds, re-read `cmd_to_030` for its
`--keep-expected-step-tokens` option before touching the command's option list.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/test_sync.py | sync.py is in the story's touches list and INFRA-319 changes its hook-registration target file, breaking TestSyncRegistersPreToolUseHook's existing assertions | 2026-07-30T20:52:51Z |

## Ensures

### A — portable registration: plugin first, machine-local second, committed file never

**A1.** `_register_pretooluse_hook` gains the same plugin-source skip
`_register_context_budget_hooks` already has (`:579-603`): before registering, it
computes the plugin-provided `(event, basename)` set from
`hook_view.merged_hook_view(...)` filtered to `HOOK_SOURCE_PLUGIN`, and if
`("PreToolUse", "pre_tool_use.py")` is present it echoes one skip line naming
CER-104 and CER-127, and returns without writing. The computation is wrapped in
`try/except` and degrades to `set()` on any failure — failing closed here would
leave a project with **no** gate hook, which is strictly worse than a duplicated
one (the same rationale the sibling function's docstring records).

**A2.** Both registrars write their hook entries to
`<project>/.claude/settings.local.json`, not `<project>/.claude/settings.json`.
The target path is derived from exactly one helper used by both; the file is
created (with `parents=True`) when absent, and an existing `settings.local.json`
is read, merged, and rewritten with the same `json.dumps(data, indent=2) + "\n"`
shape used today.

**A3.** Non-hook writes are unaffected. `_merge_allow_rules` and every other
settings writer keep their current target files; `git diff` shows no change to
which file permission/allow rules land in. Only the `hooks` block moves.

**A4.** The registrars ensure `.claude/settings.local.json` is ignored **by the
project's own `.gitignore`**, not by a global ignore: if `<project>/.gitignore`
exists and contains no entry matching `.claude/settings.local.json`, the line is
appended (idempotently — a second run appends nothing); if `.gitignore` does not
exist, it is created containing that single entry. A malformed or unreadable
`.gitignore` is a silent skip, never an exception. Tests assert idempotency
across two consecutive runs and assert the entry is present after a run against a
project with no `.gitignore`.

**A5.** The command string is **unchanged in shape**:
`uv run python <absolute path under plugin_root>`. No `${CLAUDE_PLUGIN_ROOT}`
literal is emitted into any settings file by any registrar. A test asserts
`"${CLAUDE_PLUGIN_ROOT}" not in` the written `settings.local.json` text.

**A6.** Every existing behaviour of both registrars is preserved on the new target
file: by-command block lookup, `_find_block_by_command_basename` in-place
migration, matcher upgrade to `PRETOOLUSE_MATCHER`, idempotent inner-entry append,
and the `_prune_stale_hook_entries` sweep after the correct entry is guaranteed
present. Existing registrar tests are retargeted, not deleted.

**A7.** Migration on re-run: when a project's committed `.claude/settings.json`
already holds a flex hook entry for a given `(event, basename)`, a registrar run
**removes** it from `settings.json` — pruning any block left with an empty `hooks`
list, as `_prune_stale_hook_entries` already does — *after* the correct entry
exists in `settings.local.json`. The ordering is load-bearing and asserted: at no
point in the sequence does the project have zero registrations for that pair.
Unrelated entries in `settings.json` — e.g. the project-local
`PostToolUse Edit|Write` pytest hook this repo itself carries — are left
byte-identical.

### B — `to-030`: repair already-migrated repos

**B1.** No `MigrationRule` is added and no rule id changes. `MIGRATION_RULES`
still has 14 sequential entries and INFRA-303's
`test_migration_rules_has_14_entries` /
`test_migration_rules_ids_are_sequential_1_to_14` pass unmodified. The repair
lands as a new banner-commented block inside `cmd_to_030`.

**B2.** `cmd_to_030` gains a block (naming CER-127 and INFRA-319 in its banner
comment) that scans `<project>/.claude/settings.json`'s `hooks` tree for entries
whose command basename is one of the five flex hook basenames —
`pre_tool_use.py`, `post_tool_use.py`, `user_prompt_submit.py`,
`session_start.py`, `session_end.py` — and classifies each as:

- **stale pre-rename** — the command contains `flex-harness` (the
  `/mnt/work/flex-harness/hooks/*` shape named in CER-127); or
- **machine-absolute** — the command contains an absolute path token (starting
  `/`) that is not under the scanned project directory; or
- **portable** — anything else; left untouched.

**B3.** For each non-portable entry, and only under `--apply`, the block
(a) removes the entry from `.claude/settings.json`, pruning any block left with an
empty `hooks` list and any event left with an empty block list, and (b) writes the
corresponding correct entry into `.claude/settings.local.json` through the *same*
§ A2 helper the registrars use, with the locally-resolved `plugin_root` — so there
is exactly one construction site for a hook command in the codebase. A dry run
echoes one `[would]` line per entry naming the event, the basename and the
classification, and writes nothing; asserted by byte-comparing both settings files
before and after.

**B4.** When `plugin_root` cannot be resolved for the target project (flex is not
locally available to `to-030`), the block **removes nothing** and echoes a single
`[WARN]` line saying the stale entry was left in place because no correct
replacement could be constructed. Removing a broken hook without replacing it is
still a behaviour change to a repo `to-030` cannot verify; leaving it plus a WARN
is the safe arm. A test pins this.

**B5.** The block is a no-op — no output line, no write — on a project whose
`.claude/settings.json` has no `hooks` key, is unparseable, or holds only
portable/unrelated entries. `to-030` stays total: a malformed settings file never
raises out of the command.

**B6.** Every other `to-030` step behaves byte-identically to today (B5 state
seed, B6 `expected_step_tokens`, B4 `pipe_path`, `context_story_tokens` removal,
version bump). A test pins at least one other step still firing alongside the new
block.

### C — audit: machine-absolute hook paths are a finding

**C1.** `hook_view.py` gains a stdlib-only public function —
`machine_absolute_hook_entries(view, project_dir)` (name indicative) — returning
one dict per **offending** entry with keys `event`, `basename`, `command`,
`source`, `path`, and `reason` (`"stale-flex-harness"` or `"machine-absolute"`).
It is **total**: malformed input returns `[]`, never raises. No `click` and no
third-party import is added to the module.

**C2.** The rule it applies:

| entry | flagged? |
|---|---|
| `source == "plugin"`, command holds `${CLAUDE_PLUGIN_ROOT}` | no — the portable shape |
| `source == "settings.local"`, absolute path | no — machine-local file, a machine-bound value is correct there |
| `source == "settings"`, absolute path outside the project dir | **yes** — `"machine-absolute"` |
| `source == "settings"`, command contains `flex-harness` | **yes** — `"stale-flex-harness"` (flagged even if it would otherwise pass) |
| relative or `$CLAUDE_PROJECT_DIR`-rooted command | no |
| non-flex basename (e.g. a project's own pytest hook) | no — flex does not police unrelated hooks |

The project directory is a parameter, never inferred from `os.getcwd()`.

**C3.** `pairmode_sync.py::audit_hooks` reports the findings: after its existing
duplicate-group output, it echoes one line per offending entry naming the event,
the basename, the source file and the reason, plus a one-line remedy pointing at
`to-030` (§ B). Zero findings changes nothing about today's output. The audit is
**report-only** — `audit-hooks --apply`'s existing cleaner is not extended to
rewrite hook paths; § B owns the write path.

**C4.** `fleet_discovery.py`'s scan reports the same finding class alongside its
existing duplicate-hook finding, in the same dict-of-strings shape, reaching it
through `hook_view` — `fleet_discovery` and `pairmode_sync` must not gain a
dependency on each other (that independence is `hook_view`'s stated reason for
existing).

**C5.** A test runs the audit against a fixture reproducing the exact CER-127
shape — a committed `settings.json` holding
`uv run python /mnt/work/flex-harness/hooks/user_prompt_submit.py` — and asserts
one finding with `reason == "stale-flex-harness"`; the same fixture with that
entry in `settings.local.json` instead produces zero findings.

### D — documentation

**D1.** `docs/architecture.md`'s hook-registration material (the
plugin-manifest-is-canonical decision at `:2543-2560` and the dedupe-on-write note
at `:2380-2400`) is amended with four to eight sentences recording: that
downstream settings-level registration now targets `.claude/settings.local.json`;
why (`.claude/settings.json` is committed, so a machine-absolute path in it is
portable for exactly one machine — CER-127's live failure); that
`${CLAUDE_PLUGIN_ROOT}` remains **not** usable in a project's own settings file
and the absolute-path construction is therefore retained; and that the plugin
entry now wins for all four events, not three.

**D2.** The note explicitly states the CER-127 fix direction that was **not**
taken and why — emitting `${CLAUDE_PLUGIN_ROOT}` into `.claude/settings.json`
would not expand — so a later reader does not re-propose it.

**D3.** No new persistent schema object is introduced; `schema_introduces` stays
`false` and Phase 114's § Schema delivery table owes this story no row.
`.claude/settings.local.json` is a pre-existing surface, not a new one.

### E — backlog

**E1.** The CER-127 row in `docs/cer/backlog.md` is annotated
`**RESOLVED INFRA-319 (Phase 114)**` with a short statement of what landed:
plugin-first registration into `.claude/settings.local.json` (A), a `to-030`
repair block for already-migrated repos (B), and an audit finding class (C).

**E2.** The annotation states plainly that fix direction (a) was delivered as
"machine-bound value moved out of the committed file", **not** as
"`${CLAUDE_PLUGIN_ROOT}` in settings.json", and says why. An annotation implying
the literal (a) shipped would put a false statement into the permanent record.

**E3.** No other backlog row is edited and no row is deleted —
`git diff docs/cer/backlog.md` touches exactly one row.

### F — tests and suite

**F1.** New tests exist for each of: A1 (PreToolUse plugin skip), A2 (target
file), A4 (`.gitignore` entry — created, and idempotent), A5 (no
`${CLAUDE_PLUGIN_ROOT}` literal), A7 (committed-file eviction with the unrelated
`PostToolUse Edit|Write` entry preserved), B3 (dry run writes nothing / apply
relocates), B4 (unresolvable `plugin_root` → WARN, no removal), B5 (no-op shapes),
C2 (each table row), C5 (the live CER-127 fixture).

**F2.** Existing registrar, sync, hook-view, fleet-discovery and migrate tests are
**retargeted, not deleted**. Any test asserting a hook command landed in
`settings.json` is updated to `settings.local.json` with a docstring line naming
INFRA-319; duplicate-detection tests still pass unchanged, since the merged view
already spans `settings.local`.

**F3.** `tests/pairmode/test_hooks_json.py` passes untouched — this repo's own
plugin manifest (`hooks/hooks.json`) is not edited by this story.

**F4.** Full suite green, run **once without `-x`** so a pre-existing failure
cannot mask a new one, against the `main` baseline of 4116 passed / 211 skipped
plus this story's additions.

## Instructions

You are the builder. Work only in this repository, inside your story worktree. Do
not write to `/mnt/work/flex-harness` or any path outside the project root
(`scope_guard` will deny it). Do not edit `hooks/hooks.json` or
`docs/phases/index.md`.

Build in order **A → B → C → D → E**, running the focused suites after each of A,
B and C, then the full suite without `-x` at the end.

**A — registrars.** Start in `bootstrap.py`. Extract the settings-file resolution
into one small helper (e.g. `_hook_settings_path(project_dir)` returning
`<project>/.claude/settings.local.json`) so both registrars and § B share exactly
one definition of where a hook command is written — the point of this story is one
construction site, not three. Lift the plugin-skip computation out of
`_register_context_budget_hooks` into a shared helper and call it from
`_register_pretooluse_hook` too (A1), keeping the `try/except → set()` degradation
exactly as the existing docstring describes. Then add the § A7 eviction pass over
the committed `settings.json`, running **after** the correct entry is written to
`settings.local.json`; reuse `_prune_stale_hook_entries`' empty-block cleanup shape
rather than writing a second pruner. Add the `.gitignore` guard (A4) as a small
total helper.

`sync.py:623-625` computes the settings path it hands the registrars — adjust
those call sites so the moved target is honoured, but do **not** change
`plugin_root`'s derivation.

**B — `to-030`.** Add the block to `cmd_to_030` after the existing
`context_story_tokens` block, in the file's `# ---` banner style. Classify first,
echo second, write only under `--apply` — and route the write through the § A
helper, never through a second inline `f"uv run python {…}"`. Do **not** add a
`MigrationRule`; INFRA-303 pins the count at 14 (§ Requires). Extend
`test_pairmode_migrate.py`'s `_invoke_030` / `_build_030_project` helpers rather
than writing a parallel fixture.

**C — audit.** Put the classifier in `hook_view.py` (stdlib-only, total) so both
`pairmode_sync.audit_hooks` and `fleet_discovery` consume it without depending on
each other. Wire the reporting into both. Do not extend `audit-hooks --apply` to
rewrite paths; report-only there, § B owns writes.

**D/E — docs and backlog.** Amend the architecture material named in D1 and
annotate exactly the CER-127 row. Append the annotation to the existing Finding
cell as sibling rows do; do not reword the original finding text.

**Ideology-alignment note (Step 4a, resolved inline).** `docs/ideology.md`
§ Accepted constraints — *"Never silently pass contradictions"* — reads directly on
§ B4: an unresolvable `plugin_root` must produce a visible `[WARN]`, never a quiet
skip, and must never remove a hook it cannot replace. § Core convictions —
*"rationale-bearing decisions over bare rules"* — is why D2 and E2 both record the
fix direction that was **rejected** and its reason, not only the one that shipped:
the CER row's literal wording proposes a change that would not work, and the record
must say so or the next reader re-proposes it.

## Tests

```bash
# Focused — registrars and hook view
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_bootstrap.py tests/pairmode/test_hook_view.py -q

# Focused — sync, fleet discovery, migrate
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_pairmode_sync.py tests/pairmode/test_fleet_discovery.py \
  tests/pairmode/test_pairmode_migrate.py -q

# Full suite — once, WITHOUT -x, so a pre-existing failure cannot mask a new one
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

**Acceptance:**

- Both focused runs green, including every new test named in F1.
- Full suite green against the `main` baseline of 4116 passed / 211 skipped plus
  this story's new tests. No new failures.
- `test_hooks_json.py` passes untouched (F3).
- A `test_observability_ui` failure is worktree-only (CER-090). Fix by `rsync`-ing
  the vendored payload from the main checkout; never `pnpm install`. State in the
  build report that it does not reproduce on a clean `main` checkout.

**New tests required** (names indicative):

- `test_pretooluse_registration_skipped_when_plugin_provides_it`
- `test_hook_registration_targets_settings_local_json`
- `test_hook_registration_never_emits_plugin_root_token`
- `test_hook_registration_appends_gitignore_entry_idempotently`
- `test_hook_registration_evicts_committed_settings_entry_preserving_unrelated_hooks`
- `test_to030_dry_run_leaves_both_settings_files_byte_identical`
- `test_to030_relocates_stale_flex_harness_hook_command`
- `test_to030_warns_and_keeps_entry_when_plugin_root_unresolvable`
- `test_to030_hook_block_noop_on_unparseable_settings`
- `test_machine_absolute_hook_entries_classification_matrix` (C2)
- `test_audit_hooks_reports_cer127_shape_and_clears_when_moved_local` (C5)

## Out of scope

- **Emitting `${CLAUDE_PLUGIN_ROOT}` into a project's `.claude/settings.json` —
  rejected, not deferred.** The token is expanded for commands declared in a
  plugin's own `hooks/hooks.json`, not for a project's settings file; writing it
  there substitutes one unresolvable path for another. This is CER-127's literal
  fix direction (a); the rejection is recorded in § Ensures D2/E2 rather than
  silently omitted.
- **Editing `hooks/hooks.json`.** flex's own plugin manifest is already portable
  (`${CLAUDE_PLUGIN_ROOT}` throughout) and is the canonical surface for this repo
  per `docs/architecture.md:2543-2560`. Untouched.
- **Adding a fifteenth `MigrationRule`.** INFRA-303 (same phase) pins the count
  and the sequential ids; the repair lands in `to-030` instead (§ B1).
- **Extending `audit-hooks --apply` to rewrite hook commands.** The audit reports;
  `to-030` writes. One write path, per § C3.
- **Registering the four opt-in companion-sidebar hooks** (`stop.py`,
  `session_end.py`, `PostToolUse Write|Edit|MultiEdit`, `ExitPlanMode`).
  INFRA-208 deliberately excluded them from `CONTEXT_BUDGET_HOOK_SPECS`; that
  decision is unchanged. `session_end.py` / `stop.py` appear only in § C's
  basename list, as things to *flag* if already registered with a machine-absolute
  path.
- **Running the repair across the fleet.** This story ships the tooling and its
  tests. Dispatching `to-030` at the six fleet repos is a campaign action, not
  builder work.
- **Fast-forwarding `/mnt/work/flex-harness`.** Operator-run release-channel
  promotion, outside the project root.
