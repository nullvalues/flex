---
id: BUILD-032
rail: BUILD
title: "sync-build seeds context gate state on --apply"
status: planned
phase: "76"
story_class: feature
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
touches:
  - tests/pairmode/test_pairmode_sync.py
---

# BUILD-032 — sync-build seeds context gate state on --apply

**Phase:** 76
**Rail:** BUILD

## Background

`sync-build --apply` is the migration tool for bringing projects up to the current
pairmode template. After Phase 74/75, it updates `CLAUDE.build.md` to describe the
new PostToolUse/PreToolUse context gate design — but leaves `.companion/state.json`
untouched.

Projects that predate Phase 68 (SessionStart hook) have no `context_session_reset_at`
key. If they also have a stale high `context_current_tokens` from an old session, the
`decide()` staleness check cannot detect the staleness (the check is `recorded_at <
reset_at`; with no `reset_at`, the stale value looks fresh). Result: false-positive
hard blocks on every spawn, at well below actual context usage.

Projects with no PostToolUse history at all have no `context_current_tokens`; `decide()`
hard-blocks immediately.

Both failure modes are silent — the operator sees "Context budget hit" with no indication
the real cause is a missing or stale state key.

## What to build

Add a `_seed_context_gate_state(project_dir, state_path, dry_run)` helper to
`pairmode_sync.py` and call it from `sync_build()` after the CLAUDE.build.md write.

### Seeding logic

On `--apply`, after writing CLAUDE.build.md:

1. Load `state.json` (or start with `{}` if absent).
2. Determine whether seeding is needed:
   - **Needs seed** if `context_session_reset_at` is absent, OR
   - **Needs seed** if `context_current_tokens` is absent.
3. If seeding is needed:
   - Set `context_session_reset_at` = now (UTC ISO-8601)
   - Set `context_current_tokens` = 25000 (SessionStart baseline — same value the
     SessionStart hook uses)
   - Set `context_current_tokens_recorded_at` = same timestamp as `context_session_reset_at`
     (equal timestamps = fresh per the staleness rule)
   - Write state.json
   - Emit: `  seeded: context gate state (context_current_tokens=25000, reset_at=<ts>)`
4. If not needed (both keys present): no write, no output.

### Dry-run behavior

On `--dry-run` or without `--apply`: if seeding would be needed, emit a warning line
before the diff output:

```
warning: state.json missing context gate keys — run with --apply to seed
  missing: context_session_reset_at
  missing: context_current_tokens   ← only if also absent
```

Do not write state.json in dry-run mode.

### Edge cases

- `state.json` does not exist: create it with only the three context gate keys
  (do not create other keys).
- `.companion/` directory does not exist: create it before writing state.json.
- `context_session_reset_at` present but `context_current_tokens` absent: seed
  `context_current_tokens` = 25000 with `recorded_at` = now. Do not overwrite
  the existing `context_session_reset_at`.
- `context_current_tokens` present but `context_session_reset_at` absent: seed
  `context_session_reset_at` = now. Do not overwrite `context_current_tokens`
  or `recorded_at` (the existing value, whatever it is, will now appear stale
  since `recorded_at` will predate the new `reset_at`; this triggers a normal
  hard-block → PostToolUse writes real count after first spawn completes — safe
  degraded path). Emit the seeded line noting which key was added.

## Acceptance criteria

1. `sync-build --apply` on a project with missing `context_session_reset_at` and
   stale `context_current_tokens`: seeds all three keys; emits seeded line; project
   can spawn an agent without a false-positive block.
2. `sync-build --apply` on a project with both keys already present: no write to
   state.json, no seeded output.
3. `sync-build --apply` on a project with no state.json: creates `.companion/state.json`
   with the three context gate keys only.
4. `sync-build` (no `--apply`) on a project needing seeding: emits warning lines before
   diff; does not write state.json.
5. `sync-build --apply` on a project with only `context_session_reset_at` missing:
   seeds only that key; does not alter `context_current_tokens` or `recorded_at`.
6. `sync-build --apply` on a project with only `context_current_tokens` missing:
   seeds `context_current_tokens` = 25000 and `recorded_at` = now; does not alter
   `context_session_reset_at`.
7. All existing `sync-build` tests continue to pass.

## Tests

Add to `tests/pairmode/test_pairmode_sync.py`:

- `test_sync_build_apply_seeds_missing_context_gate_state` — both keys absent
- `test_sync_build_apply_no_seed_when_keys_present` — both keys present, no write
- `test_sync_build_apply_creates_state_json_if_absent` — no state.json at all
- `test_sync_build_dry_run_emits_warning_not_write` — dry-run with missing keys
- `test_sync_build_apply_seeds_only_missing_reset_at` — only reset_at absent
- `test_sync_build_apply_seeds_only_missing_current_tokens` — only current_tokens absent
