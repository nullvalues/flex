---
id: INFRA-300
rail: INFRA
title: "Duplicate-hook detection precision: matcher-aware keying and actionable classification"
status: complete
phase: "113"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/hook_view.py
  - skills/pairmode/scripts/fleet_discovery.py
  - skills/pairmode/scripts/pairmode_sync.py
touches:
  - tests/pairmode/test_hook_view.py
  - tests/pairmode/test_fleet_discovery.py
  - tests/pairmode/test_pairmode_sync.py
  - docs/harness-cutover-runbook.md
  - docs/architecture.md
  - docs/cer/backlog.md
  - docs/stories/INFRA/INFRA-300.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The fleet migration campaign re-blocks on a detector, not on a defect.
`RELEASE-064` evidence point **E3** asserts that a migrated project's hooks are
a single block per event, and its mechanical form is
`fleet_discovery.py`'s `Projects with duplicate hooks: 0`. Post-cp-110 that
line reads **16 of 16** — every fleet project — while lumin's own
`.claude/settings.json` is provably clean (`RELEASE-064.md:713-720`: one block,
one command per event, produced by the sync itself). CER-110 was filed to
decide whether that signal is genuine duplication or a discovery artefact, and
to settle the E3 assertion's future form.

**The diagnosis is already done — do not redo it.** The 16/16 signal is two
false positives, both proven against
`~/.claude/plugins/marketplaces/claude-plugins-official/` and re-verified live
at spec time (2026-07-29):

- **(a) `security_reminder_hook.py` ×6** — one plugin (`security-guidance`)
  registering the *same* script under `PostToolUse` six times. Corrected shape
  (the plan's sketch said "six blocks"; the file says otherwise): **two**
  `PostToolUse` blocks — one with `"matcher": "Edit|Write|MultiEdit|NotebookEdit"`
  holding a single entry, and one with `"matcher": "Bash"` holding **five**
  inner entries discriminated only by an `"if"` predicate
  (`Bash(git commit:*)`, `Bash(git push:*)`, `Bash(gt create:*)`,
  `Bash(gt modify:*)`, `Bash(gt submit:*)`). `merged_hook_view` records
  `matcher` but not `if`, and `duplicate_hook_groups` discards `matcher`
  entirely — so six distinct triggers collapse into one "duplicate" group.
- **(b) `session-start.sh` ×2** — two *unrelated* plugins
  (`explanatory-output-style`, `learning-output-style`) each shipping their own
  `hooks-handlers/session-start.sh`. Both commands are byte-identical strings
  (`bash "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/session-start.sh"`), so the
  **source file path is the only discriminator** — two different scripts that
  merely share a basename, not one script registered twice.

Neither is a pairmode duplicate; neither is prunable (`audit-hooks --apply`
never writes another install's `hooks.json`, by design — INFRA-288 B9). Because
both plugin files live under the operator's home, every project in the fleet
sees them, which is exactly why the count is 16/16 rather than 1/16.

Two live constraints make the plan's one-line "add matcher to the key" fix
**wrong as stated**, and this story's design routes around both:

1. **Matcher equality would blind the real CER-104 shape.** flex's own
   `hooks/hooks.json` registers `post_tool_use.py` under
   `"Task|Agent|SendMessage"`, while `bootstrap.CONTEXT_BUDGET_HOOK_SPECS`
   (`bootstrap.py:529-533`) registers the settings-level entry under
   `"Task|Agent"`. Those matcher strings differ but *overlap* — the hook still
   fires twice per `Task` event and doubles every effort row. A strict
   `(event, matcher, basename)` key would report that as clean.
2. **Path equality would blind it too.** The whole point of basename grouping
   (B5) is that a settings entry's absolute path and a plugin entry's
   unexpanded `${CLAUDE_PLUGIN_ROOT}` command must keep matching.

The resolution is that the refinement is **confined to all-plugin groups** —
groups with no settings-level member are the only ones this story changes.
Settings-touching groups behave byte-identically to today, so no existing
detection is weakened, and the two false-positive shapes (both purely
plugin-side) disappear. On top of that, `actionable` classification gives the
E3 assertion a form that survives the operator installing a new third-party
plugin next month: **"Projects with actionable duplicate hooks: 0"**, written
into `docs/harness-cutover-runbook.md`. That runbook line is the deliverable
CER-110 actually asks for.

This story gates `RELEASE-071`: the campaign runs its CLIs from
`/mnt/work/flex-harness`, so the fix is invisible to the campaign until it is
promoted to that channel (§ Ensures 10).

## Requires

- `hook_view.merged_hook_view` (`hook_view.py:188-241`) records `event`,
  `matcher` (`str | None`), `command`, `basename`, `source`, `path` per entry;
  it does **not** record the entry-level `"if"` predicate.
- `hook_view.duplicate_hook_groups` (`hook_view.py:246-290`) groups by
  `(event, basename)` only — `matcher` and `path` are read into the view and
  then discarded — and emits `{event, basename, commands, sources}` for every
  bucket with more than one member.
- `hook_view.HOOK_SOURCE_SETTINGS == "settings"`,
  `HOOK_SOURCE_SETTINGS_LOCAL == "settings.local"`,
  `HOOK_SOURCE_PLUGIN == "plugin"` (asserted by
  `tests/pairmode/test_hook_view.py` `TestSourceConstants`).
- Consumers, all reading the same group dicts:
  - `fleet_discovery._check_duplicate_hooks` (`fleet_discovery.py:293-312`),
    result field `duplicate_hooks` (`:373`), CLI line
    `Projects with duplicate hooks: {n}` (`:606-607`), per-project
    `DUPLICATE HOOKS:` line (`:602-604`), snapshot section
    `## Duplicate hook registrations (CER-081)` (`:484-494`).
  - `pairmode_sync._audit_duplicate_hooks` (`pairmode_sync.py:1100-1119`) and
    the `audit-hooks` CLI (`:1130-1292`): exits 0 with
    `no duplicate hook registrations found`, else prints one `DUPLICATE:` line
    per group and exits 1 under dry-run (`:1187-1196`); `--apply` prunes
    settings-level files only (`:1230-1292`).
  - `bootstrap._register_context_budget_hooks` (`bootstrap.py:583-603`) builds
    its plugin-registered skip set from `merged_hook_view` keyed on
    `(event, basename)` — **not** from `duplicate_hook_groups`.
- Live fixture sources, re-verified 2026-07-29 and pinned in § Instructions:
  `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/hooks/hooks.json`
  and the `explanatory-output-style` / `learning-output-style` pair.
- No sibling story in phase 113 is a prerequisite; INFRA-300 is independent.

## Ensures

1. `merged_hook_view` records one additional key per entry, `predicate` — the
   entry-level `"if"` value when it is a `str`, otherwise `None` — alongside
   the existing six keys. Every existing key keeps its current name, value and
   ordering semantics (source order: settings, settings.local, plugins); a test
   asserts the full key set is exactly
   `{event, matcher, command, basename, source, path, predicate}`.

2. `duplicate_hook_groups` buckets by `(event, basename)` exactly as today, and
   then refines a bucket **only when no member's `source` is `settings` or
   `settings.local`** (an all-plugin bucket). Refinement is two rules:
   - **R1 (multi-plugin split):** the bucket is partitioned by member `path`,
     so two plugins shipping the same basename land in different partitions.
   - **R2 (distinct-trigger drop):** within each partition, a member whose
     `(matcher, predicate)` pair is unique among that partition's members is
     dropped; only members sharing an identical `(matcher, predicate)` with at
     least one other member survive.
   A partition is emitted only if two or more members survive. Buckets
   containing a settings-level member are emitted unrefined — matcher and path
   are never applied to them, because matcher strings legitimately differ and
   overlap across sources (`Task|Agent` vs `Task|Agent|SendMessage`, see
   § Context).

3. Each emitted group dict keeps `event`, `basename`, `commands` and `sources`
   with unchanged names, semantics and view-order (the INFRA-288 output
   contract), and gains four parallel/derived keys: `matchers` (list, parallel
   to `commands`), `predicates` (list, parallel), `paths` (list, parallel), and
   `actionable` (bool). `actionable` is `True` iff at least one member's
   `source` is `settings` or `settings.local`; every all-plugin group is
   `actionable: False`. `duplicate_hook_groups` remains total — malformed input
   yields `[]`.

4. `pairmode_sync audit-hooks` (dry-run) exits **1 if and only if** at least one
   returned group has `actionable: True`. Actionable groups print the existing
   `DUPLICATE: event=… basename=… sources=… commands=…` line unchanged.
   Non-actionable groups print a distinct informational line beginning
   `PLUGIN-INTERNAL:` that names the event, basename and the distinct source
   paths, and state that flex never writes another install's `hooks.json`. A
   project whose only groups are non-actionable exits **0**. A project with no
   groups at all still prints `no duplicate hook registrations found` and exits
   0.

5. `audit-hooks --apply` skips non-actionable groups entirely — they never
   reach the prune loop — and its behaviour on actionable groups (plugin entry
   wins; settings and settings.local pruned; plugin `hooks.json` never opened
   for write) is unchanged, proven by the existing `--apply` tests still
   passing untouched.

6. `fleet_discovery` reports both counts, from `duplicate_hooks` group dicts:
   - `Projects with actionable duplicate hooks: {n}` — counts projects with at
     least one `actionable: True` group. This exact string replaces
     `Projects with duplicate hooks: {n}` at `fleet_discovery.py:607`.
   - `Projects with plugin-internal duplicate hooks (non-actionable): {m}` on
     its own line.
   The per-project `DUPLICATE HOOKS: …` line is emitted only for actionable
   groups; a project with only non-actionable groups gets a
   `plugin-internal duplicate hooks:` line naming the events instead. The
   `duplicate_hooks` result-dict key still carries **all** groups (each with its
   `actionable` flag) — no key is removed and no group is silently dropped from
   the JSON output.

7. The snapshot section `## Duplicate hook registrations (CER-081)`
   (`fleet_discovery.py:484-494`) carries both categories under separate
   sub-headings, with the actionable one first and an explicit
   `_No actionable duplicate hook registrations found._` when empty.

8. The two live shapes are pinned as tmpdir fixtures (fake home — never the
   real `~/.claude/`), reproducing the verbatim structures recorded in
   § Instructions:
   - **Shape (a):** one plugin `hooks.json` whose `PostToolUse` holds an
     `Edit|Write|MultiEdit|NotebookEdit` block with one entry plus a `Bash`
     block with five entries differing only by `"if"` →
     `duplicate_hook_groups` returns `[]`.
   - **Shape (b):** two distinct plugin `hooks.json` files under different
     plugin directories, each with an identical `SessionStart` command string
     whose basename is `session-start.sh"` → `duplicate_hook_groups` returns
     `[]`.
   A third, **negative-control** fixture proves the refinement did not go too
   far: one plugin file registering the same basename twice under the *same*
   `(matcher, predicate)` still yields one group, with `actionable: False`.

9. Regression floor — all three are asserted by tests that must pass unmodified
   in substance:
   - The cross-source CER-104 shape still groups: settings absolute command +
     plugin `${CLAUDE_PLUGIN_ROOT}` command, same basename, **different**
     matchers (`Task|Agent` vs `Task|Agent|SendMessage`) → one group with
     `actionable: True`.
   - The settings-only parity shape (two same-basename entries in
     `settings.json`) still groups, `actionable: True`.
   - `bootstrap._register_context_budget_hooks`'s plugin-registered skip set
     stays keyed on `(event, basename)` — deliberately coarser than the group
     key, because a plugin registering the script for the event at all is
     reason enough not to add a settings-level entry (§ Out of scope).

10. **Channel-promotion criterion (F-form, INFRA-293 § Ensures F3/F4 pattern;
    orchestrator-run, not builder-run).** After this story merges to `main`,
    the change is ff-merged to the `/mnt/work/flex-harness` release channel and
    the fleet scan is re-run **from the channel**:

    ```bash
    PATH=$HOME/.local/bin:$PATH uv run python \
      /mnt/work/flex-harness/skills/pairmode/scripts/fleet_discovery.py \
      discover --no-snapshot
    ```

    Acceptance: the output contains `Projects with actionable duplicate hooks: 0`.
    The run date, the channel commit it was run at, and both counts are recorded
    in phase 113's CP-113 cold-eyes checklist. **`RELEASE-071` must not be
    dispatched before that record exists** — the campaign runs its CLIs from the
    channel, so an unpromoted fix is invisible to E3.

11. `docs/harness-cutover-runbook.md` records the settled E3 assertion under the
    § Pre-fold discovery gate (DP8) material: the campaign asserts
    **`Projects with actionable duplicate hooks: 0`**, with a two-sentence note
    that plugin-internal duplicates are reported but never gate a migration
    because flex never writes another install's `hooks.json`. `grep -c
    "Projects with actionable duplicate hooks: 0"
    docs/harness-cutover-runbook.md` returns at least 1.

12. `docs/architecture.md`'s merged-hook-view passage (`:2414-2432`) records the
    refined grouping rule, the actionable/non-actionable split, the
    exit-code semantics, and — with its rationale — why matcher and path are
    applied to all-plugin groups only.

13. `docs/cer/backlog.md`'s CER-110 row is annotated `RESOLVED (INFRA-300)`
    with the two false-positive shapes named in one sentence each and the
    settled E3 assertion quoted.

14. Full suite green, run **without `-x`**, modulo the known pre-existing
    `test_observability_ui` failure that reproduces on clean `HEAD`. The
    § Evidence for that known failure is a before/after comparison, not an
    assertion that it passes.

## Instructions

Work in `skills/pairmode/scripts/` and the three test files named in
`touches`. Do not commit; the orchestrator holds all commits.

**Step 1 — `hook_view.merged_hook_view`.** Add `predicate` to the entry dict:
`predicate = entry.get("if")`, coerced to `None` unless it is a `str` (same
isinstance discipline the `matcher` read already uses at `:220-222`). Add one
docstring line naming the key and CER-110. Nothing else in this function
changes — no path resolution, no env expansion (the B3 pure-read contract).

**Step 2 — `hook_view.duplicate_hook_groups`.** Keep the existing
`(event, basename)` bucketing loop and its isinstance guards. Collect
`matcher`, `predicate` and `path` alongside `commands`/`sources` in the same
append order. After the loop, for each bucket:

- Compute `actionable = any(source in (HOOK_SOURCE_SETTINGS,
  HOOK_SOURCE_SETTINGS_LOCAL) for source in bucket["sources"])`.
- If `actionable`, emit the bucket unrefined when it has ≥2 members.
- If not actionable, apply R1 then R2 from § Ensures 2 and emit each surviving
  partition with ≥2 members, preserving view order within the partition.

Write the rationale into the docstring in the module's existing voice: the
refinement is confined to all-plugin buckets **because** matcher strings
legitimately differ *and overlap* across sources (`Task|Agent` settings-side vs
`Task|Agent|SendMessage` plugin-side for `post_tool_use.py`) and because a
settings absolute path can never equal a plugin's `${CLAUDE_PLUGIN_ROOT}`
command path — applying either discriminator across sources would silently
restore the cross-source blindness the module exists to remove (B5). Keep the
function total: the whole body stays inside its `try` / `except: return []`.

*(Ideology note — resolved inline: `docs/ideology.md` § Accepted constraints
"Never silently pass contradictions" makes narrowing a detector the risky
direction. The narrowing is therefore scoped so that no settings-touching group
can ever be dropped, and the dropped plugin-side groups are still **printed**
as `PLUGIN-INTERNAL:` / snapshot lines rather than suppressed — reported, just
not gating. Nothing is silently passed.)*

**Step 3 — `pairmode_sync`.** `_audit_duplicate_hooks` keeps its signature and
its "derive project dir from `settings_path.parent.parent`" behaviour; update
its docstring for the new keys. In `audit_hooks`, split the returned list into
actionable and non-actionable, print the existing `DUPLICATE:` lines for the
former and `PLUGIN-INTERNAL: event=… basename=… paths=[…] — plugin-owned;
flex never writes another install's hooks.json` for the latter, then
`sys.exit(1)` under dry-run only if the actionable list is non-empty. In the
`--apply` path, iterate the actionable list only. Update the command docstring
(`:1156-1169`) to state the new exit-code rule.

**Step 4 — `fleet_discovery`.** `_check_duplicate_hooks` is unchanged apart
from its docstring (new keys, actionable semantics). Change the summary lines
at `:602-607` and the snapshot section at `:484-494` per § Ensures 6 and 7.
Leave the `duplicate_hooks` result key carrying every group.

**Step 5 — fixtures.** Pin the two live shapes verbatim. Shape (a), from
`security-guidance/hooks/hooks.json` — `PostToolUse` holds two blocks:

```json
{"matcher": "Edit|Write|MultiEdit|NotebookEdit",
 "hooks": [{"type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/sg-python.sh\" \"${CLAUDE_PLUGIN_ROOT}/hooks/security_reminder_hook.py\""}]}
```

and a `{"matcher": "Bash", "hooks": [ … ]}` block whose five entries carry the
identical command string above and differ only in `"if"`:
`Bash(git commit:*)`, `Bash(git push:*)`, `Bash(gt create:*)`,
`Bash(gt modify:*)`, `Bash(gt submit:*)`. Note in the test docstring that the
derived basename is `security_reminder_hook.py"` **including the trailing
double-quote** — `command.rsplit("/", 1)[-1]` on a quoted multi-argument
command — and that this crude derivation is INFRA-288 contract, deliberately
not changed here.

Shape (b): two plugin directories under the fake home, each with
`hooks/hooks.json` containing

```json
{"hooks": {"SessionStart": [{"hooks": [{"type": "command",
  "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/session-start.sh\""}]}]}}
```

— identical command strings, different files. Every fixture uses `tmp_path`
with an explicit fake `home=`; the existing `_no_env_plugin_hooks` autouse
fixture in `test_hook_view.py:22-26` must remain in force so the operator's own
`FLEX_PLUGIN_HOOKS` never leaks in. No test may read the real
`~/.claude/plugins/`.

**Step 6 — docs.** Runbook (§ Ensures 11), architecture (§ Ensures 12), backlog
row (§ Ensures 13). Then run the suite per § Tests.

**Do not** attempt to make `fleet_discovery` prune, warn about, or otherwise
act on plugin-owned registrations. Reporting is the whole remit.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest \
  tests/pairmode/test_hook_view.py \
  tests/pairmode/test_fleet_discovery.py \
  tests/pairmode/test_pairmode_sync.py -q 2>&1 | tail -30
```

Then the full suite, **without `-x`** so the known failure cannot mask a new
one:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

New/updated tests required:

- `test_hook_view.py` — `predicate` key present and typed (Ensures 1); shape
  (a) fixture → `[]`; shape (b) fixture → `[]`; negative control (same plugin
  file, same `(matcher, predicate)`, twice) → one group `actionable: False`;
  cross-source CER-104 shape with *different overlapping matchers* → one group
  `actionable: True`; existing `TestSettingsOnlyParity` cases still pass with
  the four new keys added; `duplicate_hook_groups(None)` and
  `duplicate_hook_groups([{"nonsense": True}, 42])` still `== []`.
- `test_pairmode_sync.py` — plugin-only fleet exits **0** with a
  `PLUGIN-INTERNAL:` line on stdout; actionable duplicate still exits **1**;
  `--apply` leaves a non-actionable-only project's `settings.json` byte-identical;
  the existing `--apply` tests (`:1620-1930`) pass unchanged.
- `test_fleet_discovery.py` — both summary lines present with correct counts;
  a project with only plugin-internal groups contributes 0 to the actionable
  count; snapshot text contains both sub-headings.

Acceptance: the three named files are green, and the full-suite run shows no
failure other than the known `test_observability_ui` one, with a before/after
`git stash`-based comparison recorded in the story's evidence.

## Out of scope

- **Renaming or reworking basename derivation.** `command.rsplit("/", 1)[-1]`
  yields `security_reminder_hook.py"` with a trailing quote for shell-quoted
  multi-argument commands. It is crude, it is the INFRA-288 contract, and
  changing it would alter cross-source matching. Filed as an observation in the
  test docstring, not fixed here.
- **`bootstrap._register_context_budget_hooks`'s skip key.** It stays
  `(event, basename)`. Making it matcher-aware would let flex add a
  settings-level `Task|Agent` `PostToolUse` entry alongside the plugin's
  `Task|Agent|SendMessage` one — re-creating the exact CER-104 double-recording
  bug INFRA-288 fixed.
- **Pruning, disabling or warning on plugin-owned hook registrations.** flex
  never writes another install's files (INFRA-288 B9); non-actionable groups are
  reported and nothing more.
- **Any change to `RELEASE-064`'s recorded evidence.** Its E3 adjudication
  stands as the historical record; only the *future* assertion form is settled
  here, in the runbook.
- **Resolving hook command paths / expanding `${CLAUDE_PLUGIN_ROOT}`.** The
  merged view stays a pure read.
- **The `SubagentStop` registration** (INFRA-298) and any other new hook event.
