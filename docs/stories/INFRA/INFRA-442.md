---
id: INFRA-442
rail: INFRA
title: doctor-state command: repair orphaned stamps, worktrees, permissions artifacts; frontmatter/table cross-check
status: draft
phase: "146"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_flex_build_doctor_state.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

A session that dies mid-story leaves four artifacts behind with no recovery path:
`.pairmode-worktrees/<ID>/` (plus its `pairmode/<ID>` branch), the
`current_stories[<ID>]` stamp in `.companion/state.json`, the flat `current_story`
mirror, and `docs/phases/permissions/<ID>.json`. `claimed_story_ids()`
(flex_build.py ~606-640, consumed at ~1319 and by `next_action.infer_position`)
then reports the story as claimed forever — CER-236/F1, the "build blocked after
context clear" shape. The only existing repair, `clear-stale-stories`
(~2440-2541), clears state.json stamps and nothing else, so the operator is left
in a *worse* state: the stamps are gone, the worktree is not, and the retry's
`create-story-worktree` dies on "worktree already exists" (~4829) needing hand git
surgery — CER-237/F2. This story adds one `doctor-state` command that classifies
every story with any claim artifact and, under `--apply`, performs the *complete*
teardown+clear set `discard-story-worktree` already performs (~5101-5121) rather
than a third partial one.

**F3 (CER-238) is subsumed by this story**, per the phase Goal's own wording
("...and cross-checks frontmatter against the phase table"): a story's frontmatter
`status:` versus its phase-doc Stories-table Status cell is doctor-state's third
check. It does not belong to INFRA-443 (session-start detection, which consumes
this story's classifier) or INFRA-444 (gate-verdict invalidation). F5 (era-ledger
reconciliation) is not in this story.

## Requires

None. `claimed_story_ids`, `entry_is_fresh`/`STATE_STORY_MAX_AGE_HOURS`,
`_teardown_story_worktree`, `_residue_lines`, `_clear_active_story`,
`clear_permissions_artifact`, `_clear_gate_verdict`,
`_parse_phase_stories_with_status`, `update_story_status`, and
`update_phase_story_status` all already exist in the tree and are reused, not
reimplemented.

## Ensures

1. `flex_build.py doctor-state --project-dir P` with no other flags exits 0 and
   performs zero writes: against a project holding an orphaned worktree, a stale
   `current_stories` stamp, a `current_story` mirror and a permissions artifact,
   all four artifacts still exist byte-identically after the run, and each is
   named on a `[would] repair` line. Forbidden proxy: printing `[would]` lines
   while any artifact was in fact removed.
2. **F1 regression.** Given a real `.pairmode-worktrees/<ID>/` worktree on branch
   `pairmode/<ID>`, a stale `current_stories[<ID>]` entry, a `current_story`
   mirror naming `<ID>`, and `docs/phases/permissions/<ID>.json`, a single
   `doctor-state --apply` run leaves all of: the worktree directory absent,
   `git branch --list pairmode/<ID>` empty, `<ID>` absent from
   `get_current_stories(companion_dir)`, the mirror no longer naming `<ID>`, the
   permissions artifact absent, and `claimed_story_ids(P) == set()`.
3. **F2 regression.** Starting from the exact post-`clear-stale-stories --apply`
   state — worktree directory and branch present, permissions artifact present,
   *no* state.json stamps at all — `doctor-state --apply` removes worktree,
   branch and artifact, and a subsequent `create-story-worktree --story-id <ID>`
   exits 0. Forbidden proxy: a run that clears stamps (or reports success) while
   the worktree directory survives.
4. A *fresh* `current_stories[<ID>]` entry (per `entry_is_fresh` against the same
   `STATE_STORY_MAX_AGE_HOURS` the scope guard uses, overridable by
   `--max-age-hours`) retains everything: `--apply` leaves that story's worktree,
   stamp and permissions artifact untouched and reports it on an `in-flight` line.
5. **F3 cross-check.** A story whose frontmatter `status:` disagrees with its
   phase-doc Stories-table Status cell is reported on a `status-drift <ID>
   frontmatter=<a> table=<b>` line in *both* modes. `--apply` alone never
   rewrites either surface; `--sync-status frontmatter` writes the frontmatter
   value into the table cell, `--sync-status table` writes the table value into
   the frontmatter, and neither is applied without that explicit flag. Forbidden
   proxy: `--apply` silently picking a winner.
6. `diagnose_state(project_path)` returns the classification (`orphans`,
   `in_flight`, `status_drift`) and performs no writes and no `git` mutations;
   the command is a thin printer over it, and it returns empty lists rather than
   raising when `.pairmode-worktrees/`, `.companion/`, `docs/phases/permissions/`
   or `docs/stories/` are absent.
7. When `_teardown_story_worktree` returns residue for an orphan, that story's
   remaining artifacts (stamps, permissions artifact, gate verdict) are left
   untouched, `_residue_lines` output is printed to stderr, and the command exits
   1. Report mode exits 0 on every input; `--apply` exits 0 when every attempted
   repair completed.

## Instructions

1. Register `doctor-state` in `skills/pairmode/scripts/flex_build.py` with
   `@flex_build.command("doctor-state")`, placed beside `permissions-gc` /
   `clear-stale-stories` and following their shape exactly: a pure classifier
   function plus a thin printing command (the `collectable_permission_artifacts`
   / `cmd_permissions_gc` precedent at ~1280-1399). Options: `--project-dir`,
   `--max-age-hours` (same defaulting rationale as `clear-stale-stories` — the
   CLI and the guard must never disagree about "stale"), `--apply`, and
   `--sync-status` (`click.Choice(["frontmatter", "table"])`, default none).
2. `diagnose_state(project_path, *, max_age_hours=None)` builds its candidate ID
   set from the union of `claimed_story_ids()`, `current_stories` keys, the
   `current_story` mirror ID, and parsable `docs/phases/permissions/*.json`
   stems. Classify with a **whitelist of reasons to retain**, mirroring
   `collectable_permission_artifacts`' rationale — retain when a fresh keyed
   entry (or a fresh mirror naming the ID) exists, or when anything needed to
   classify is unreadable; everything else is an orphan. A worktree directory
   with no stamp at all is an orphan: that is precisely F2's post-partial-repair
   state.
3. Under `--apply`, repair each orphan with the same ordered set
   `discard-story-worktree` performs (~5101-5121): `_teardown_story_worktree`
   first (only when the directory exists), then — only if it returned no residue
   — `_clear_active_story`, `clear_permissions_artifact`, `_clear_gate_verdict`.
   When the mirror names the story and no keyed entry exists, additionally call
   `clear_current_story(companion_dir, None)` (the legacy shape, same reasoning
   as `_clear_stale_stories_body`'s C4). Do **not** call
   `mark_recently_discarded` — no attempt is being adjudicated here. The
   residue-first ordering is deliberate: clearing stamps while the worktree
   survives is the exact failure this story exists to remove.
4. Status drift: for each phase doc, pair `_parse_phase_stories_with_status`'s
   rows against each story file's frontmatter `status:`; report mismatches.
   Repair only under `--sync-status`, via `update_phase_story_status`
   (`frontmatter` wins) or `update_story_status` (`table` wins). Requiring an
   explicit winner is the ideology's override path applied here — an auto-flip to
   `complete` would make `next_action` skip an unbuilt story, so the contradiction
   is surfaced, never silently resolved (§ Accepted constraints, "Never silently
   pass contradictions").
5. Add `tests/pairmode/test_flex_build_doctor_state.py`, following
   `tests/pairmode/test_flex_build_permissions_gc.py`'s harness (CliRunner + a
   temp project) — that file is read as a model only and is deliberately not in
   this story's declared scope (spec-preflight `scope:` finding, intentional).
   Ensures 2 and 3 must use a real `git worktree add`-created
   worktree, not a bare `mkdir` — the whole point of the F2 regression is that
   `git worktree remove` runs and the retry's `create-story-worktree` then
   succeeds.
6. Spec-writer note: this stub's frontmatter has no `primary_files:` field;
   `skills/pairmode/scripts/flex_build.py` is the primary file and was added to
   `touches:` instead (the procedure permits widening `touches:` only). Set
   `primary_files:` before building.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_doctor_state.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green, including the F1 and F2 regression cases (Ensures 2, 3).
Run the full suite without `-x` so a real failure is not masked by an earlier one.

## Out of scope

- Session-start invocation of this command or its classifier — INFRA-443 consumes
  `diagnose_state`; this story ships the command and the pure function only.
- Clearing a gate verdict on *spec revision* — INFRA-444. This story clears a
  verdict only as part of an orphan's full teardown.
- F5, era-ledger reconciliation against `docs/phases/index.md`
  (`_mark_phase_complete_in_era_ledger`) — not part of doctor-state here.
- A `next-action --diagnose` provenance mode, and any change to
  `clear-stale-stories` or `permissions-gc`, which keep their current narrower
  contracts.
