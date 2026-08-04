---
id: INFRA-386
rail: INFRA
title: Fold to-030 stale-flex-harness repair into sync-all as a fifth step
status: draft
phase: "121"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
  - skills/pairmode/scripts/pairmode_migrate.py
touches:
  - tests/pairmode/test_pairmode_sync.py
  - tests/pairmode/test_pairmode_migrate.py
  - skills/pairmode/SKILL.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`pairmode_sync.py sync-all` runs four subprocess steps (sync.py → sync-agents →
sync-narratives → sync-build) and never repairs stale `/mnt/work/flex-harness/...`
hardcoded hook commands left in a downstream repo's committed
`.claude/settings.json`. That repair lives in a different script entirely —
`pairmode_migrate.py`'s `to-030` — so every fleet repo needs a second, manual,
easily-forgotten command (the manual `to-030 --apply` runs already done on
forqsite and ud). This story folds the repair into `sync-all` so one command
leaves a repo fully current. `to-030` is a full 0.2.x→0.3.0 normalizer, not a
narrow hook fixer, so folding the *whole* command in would fire unrelated
side-effects (`expected_step_tokens` rewrite, `context_story_tokens` removal,
`effort_tracking` backfill) on every sync-all run across ~14 repos. The chosen
resolution is a new `--hooks-only` mode on `to-030` that runs the hook-repair
portion alone, which is what `sync-all` invokes.

## Requires

None — `to-030`'s hook repair is already self-contained and order-independent
w.r.t. plugin registration (`bootstrap.py`'s `_register_pretooluse_hook` itself
consults `_plugin_registered_hook_pairs()` and either skips settings-level
registration or constructs the correct plugin-root-relative entry).

## Ensures

1. `pairmode_migrate.py to-030 --hooks-only` runs the stale-flex-harness /
   machine-absolute hook repair and **none** of `to-030`'s other normalization
   steps (no `state.json` seeding, no `expected_step_tokens` rewrite, no
   `pipe_path` notice, no `context_story_tokens` removal, no `effort_tracking`
   backfill). Forbidden proxy: the other steps still run but print nothing.
2. `--hooks-only` composes with `--apply` and defaults to dry-run like the rest
   of `to-030`; `--keep-expected-step-tokens` remains accepted but is inert under
   `--hooks-only` (the step it suppresses does not run), and `sync-all` therefore
   gains **no** new flag for it.
3. `sync_all` invokes exactly five steps, in this order: sync.py, sync-agents,
   sync-narratives, sync-build, then `pairmode_migrate.py to-030 --hooks-only`
   as the fifth and last. The `--apply`/`--yes` propagation applied to the first
   four is applied identically to the fifth.
4. `to-030 --hooks-only` exits 0 when its only adverse outcomes are `[WARN]`
   conditions (stale `session_end.py` entries left in place per INFRA-208; a
   stale entry retained because `plugin_root` is not locally valid), and exits
   non-zero only on a hard failure (project dir missing, `settings.json`
   unreadable or malformed). The fifth step participates in `sync_all`'s existing
   fail-fast contract unchanged — a non-zero returncode echoes the error and
   `sys.exit(returncode)`. Forbidden proxy: exempting the fifth step from
   fail-fast by ignoring its returncode.
5. Running `sync-all --apply` twice in a row against an already-repaired repo
   leaves `.claude/settings.json` and `.claude/settings.local.json`
   byte-identical after the second run, and the fifth step's dry-run output on
   such a repo reports no pending hook changes. Forbidden proxy: "exits 0 / no
   error" while re-writing or duplicating hook entries.
6. Every prose statement of the "four sync operations" contract reads five:
   `pairmode_sync.py`'s module docstring, its `sync_all` docstring, and
   `skills/pairmode/SKILL.md`'s `### /flex:pairmode sync-all` section (numbered
   step list, "Always invoked" language, restart-notice text). No remaining hit
   in those files describes the sync-all step count as four.

## Instructions

1. In `pairmode_migrate.py`'s `cmd_to_030`, add a `--hooks-only` flag that
   short-circuits every normalization step except the stale-hook repair block.
   Default behaviour (flag absent) must stay byte-identical.
2. While there, confirm `cmd_to_030`'s exit code on the WARN-only paths. If any
   WARN path currently returns non-zero, change it to 0 — WARN is explicitly not
   a failure (Ensures 4) — and note the behaviour change in the commit body.
3. In `pairmode_sync.py`'s `sync_all`, append the fifth step using the existing
   cross-script subprocess pattern (the same shape already used to shell out to
   `sync.py`), targeting `pairmode_migrate.py` with
   `to-030 --project-dir <dir> --hooks-only` plus the run's `--apply`/`--yes`
   flags. Order it **last**: the four existing steps rewrite methodology docs,
   agent frontmatter and `CLAUDE.build.md` and never touch settings.json hook
   entries, so the new step is disjoint from them; placing it last means a
   fail-fast halt in an earlier step leaves settings.json untouched, and the four
   existing steps keep their current relative order.
4. Update the two existing tests — `test_sync_all_apply_invokes_all_four_in_order`
   and `test_sync_all_yes_in_dry_run_propagates_to_all_four` — to assert five
   steps in order (rename to `..._all_five_...`), and add one new test asserting
   the fifth step's argv carries `to-030`, `--hooks-only` and the propagated
   flags. In `tests/pairmode/test_pairmode_migrate.py`, add coverage for
   Ensures 1 (other steps skipped under `--hooks-only`) and Ensures 5 (a second
   `--apply` run is a no-op).
5. Update the prose surfaces named in Ensures 6.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_sync.py tests/pairmode/test_pairmode_migrate.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green. Run the full suite without `-x` so a real failure is not
masked by an earlier known one.

## Out of scope

- Applying the repair across the 13 remaining fleet repos — that is INFRA-387.
- Folding `audit-hooks`, or any other `pairmode_migrate.py` command, into
  `sync-all`; only the `to-030` hook-repair portion is added here.
- Fixing the stale `session_end.py` entries `to-030` warns about and leaves in
  place (INFRA-208) — the WARN behaviour is preserved as-is.
- Retiring `to-030` as a standalone command; it keeps its full-normalizer
  behaviour for one-time 0.2.x→0.3.0 migrations.
