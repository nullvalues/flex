---
id: INFRA-352
rail: INFRA
title: Add sync-narratives to pairmode_sync.py, reusing INFRA-332's add-missing-file path
status: complete
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
touches:
  - tests/pairmode/test_pairmode_sync.py
  - skills/pairmode/SKILL.md
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-351 (this phase) adds `NARRATIVE_FILES` and bootstrap-time scaffolding for the nine
harness-role narratives, but bootstrap only runs once, at fresh-install time — it does nothing for
a project already bootstrapped before `NARRATIVE_FILES` existed. INFRA-332 (Phase 116) hit and
fixed the identical gap for `.claude/agents/`: `sync-agents` only rewrote files already on disk,
with no path to *add* a file that existed only as a template. `_collect_missing_agent_files`
(`pairmode_sync.py:781`) is the fix — it enumerates `bootstrap.AGENT_FILES` against what's on disk,
renders and writes anything missing, and fires the INFRA-323 `RESTART REQUIRED` notice on
additions. This story is the same fix for `NARRATIVE_FILES`, reusing that exact mechanism rather
than duplicating it.

## Requires

- INFRA-351 must land first: `bootstrap.NARRATIVE_FILES` must exist before this story has anything
  to enumerate against.

## Ensures

1. A new `sync-narratives` command (or an extension of `sync-agents` that also covers
   `NARRATIVE_FILES` — decide based on which reads more naturally against `pairmode_sync.py`'s
   existing `sync-all` invocation order documented at the top of the file; either is acceptable as
   long as it's a single, non-duplicated code path) enumerates `bootstrap.NARRATIVE_FILES` against
   `docs/narratives/<ROLE>/` and adds any missing file, rendered identically to a fresh bootstrap.
2. Reuses `_collect_missing_agent_files`'s actual logic (generalize the helper to take the
   file-list and a role-directory-shape parameter, or extract a shared helper both call) — does
   **not** hand-duplicate the enumeration/render logic a second time.
3. Fires the same `RESTART REQUIRED` notice (INFRA-323) on any addition, via the existing
   `_emit_restart_notice` call site — no second notice mechanism.
4. `--dry-run` reports what would be added without writing; declining a confirm-prompt writes
   nothing (forbidden-proxy case, matching INFRA-332's own test shape).
5. Updating an existing narrative file's content (as opposed to adding a missing one) is
   **explicitly out of scope for this story** — see Out of scope.
6. `skills/pairmode/SKILL.md` and `docs/architecture.md` document the new command alongside
   `sync-agents`'s existing documentation.
7. Full `tests/pairmode/` suite green.

## Instructions

1. Read `_collect_missing_agent_files` (`pairmode_sync.py:781`) and `sync_agents`
   (`pairmode_sync.py:873`) in full before writing anything — the goal is genuine reuse, not a
   parallel implementation that happens to look similar.
2. Generalize the shared logic (file-list enumeration + render + write + restart-notice) so both
   `sync-agents` and the new narrative path call the same core function with different
   file-list/directory-shape parameters, rather than two independently-maintained copies — this
   phase's own cold-eyes-review precedent (`docs/build-loop-cold-eyes-review-20260801.md`, F7) is
   a direct warning about what happens when a reader and a writer (or two writers) drift.
3. Wire the new path into `sync-all`'s existing invocation order (documented near the top of
   `pairmode_sync.py`) at whatever position makes sense given `sync-agents`' current position in
   that order.
4. Add tests mirroring INFRA-332's own coverage shape: add-missing-files-matches-fresh-bootstrap,
   dry-run-reports-without-writing, confirm-prompt-declined-writes-nothing.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_sync.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green.

## Out of scope

- Updating/re-rendering an already-present narrative file's content (that's a content-authoring
  decision, not a missing-file backfill — leave existing narrative files untouched by this story's
  sync path, same posture `sync-agents` itself takes toward pre-existing drift per INFRA-332's own
  Evidence section).
- OPERATOR's narrative sync (INFRA-353 defines its own seed-then-extend mechanism, which may or
  may not reuse this same sync path — decide there, not here).
