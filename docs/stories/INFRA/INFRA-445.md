---
id: INFRA-445
rail: INFRA
title: diagnose_state scoping fix: exclude closed-phase/historical orphans, validate state.json-derived story IDs, bound SessionStart scan cost
status: draft
phase: "146"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - skills/pairmode/scripts/flex_build.py
  - tests/pairmode/test_flex_build_doctor_state.py
  - tests/pairmode/test_session_orphan_notice.py
  - docs/architecture.md
narrative_roles: []
---

<!-- Scope note: the scaffold deliberately omits `primary_files:` for draft
     stories (story_new.py, INFRA-370); this story's declared write scope is
     carried entirely by `touches:` above, matching INFRA-443/INFRA-444's own
     choice on this phase. -->

## Context

Phase 146's checkpoint-security audit (2026-08-08) FAILed on `diagnose_state`
(`flex_build.py` ~2578, shipped by INFRA-442, consumed unmodified by
INFRA-443's `orphan_state_notice`). Its orphan classification only recognises
a *fresh* `state.json` stamp as a retain reason, so a long-completed story
whose `docs/phases/permissions/<ID>.json` was never cleared has no retain
signal and is classified an orphan even though it is just old committed
history. `status_drift` has the matching defect: it globs every
`docs/phases/*.md`, including phases long checkpointed and closed, rather than
scoping to phases still open. Measured live on this repo: 118 orphans and 59
status-drift rows, every one historical (e.g. `BUILD-024..BUILD-028`
permissions artifacts with `has_worktree=False`, `has_stale_stamp=False`;
`BUILD-001` frontmatter `complete` vs. `phase-18.md`'s table `planned`). The
consequence is not cosmetic: INFRA-443's `orphan_state_notice` now emits a
non-`None` advisory on every SessionStart in this repo permanently with zero
signal, and its suggested repair (`doctor-state --apply` / `--sync-status`),
if actually run, would unlink 118 git-tracked permissions artifacts and
rewrite Status cells across roughly 100 already-checkpointed phase docs —
because `clear_permissions_artifact` is called unconditionally per orphan,
never gated on whether the phase is still active. A classifier that produces
this much false-positive noise is exactly the "never silently pass
contradictions" conviction's inverse failure mode: an operator who cannot
trust the signal will stop reading it, which is worse than no signal at all.

The audit also found the candidate-ID set `diagnose_state` builds
(~2638) is inconsistently validated: `claimed_story_ids()` and the
permissions-filename scan are both checked against `_STORY_ID_RE`, but
`current_stories` keys and `current_story.id` read straight from
`state.json` are not, even though all four can reach `--apply`'s destructive
calls (`_teardown_story_worktree`'s `git worktree remove --force`/`git branch
-D`, and `clear_permissions_artifact`'s `unlink`) — neither of which applies
the `resolve()`-plus-`relative_to(root)` containment check `_story_path`
already establishes as this codebase's guard for this threat class.

Finally, `hooks/session_start.py`'s delegated `orphan_state_notice` call does
a full-repo scan (163 phase-doc reads plus a frontmatter read per table row
today) on every SessionStart — currently fast (0.164s warm-cache) but
unbounded in cost as project history accumulates. The audit's judgment is
that this should resolve as a consequence of the orphan/drift scoping fix
above, not as a separate code change; this story must verify that is actually
true rather than assume it.

## Requires

INFRA-442, INFRA-443, and INFRA-444 complete: `diagnose_state(project_path,
*, max_age_hours=None)` (`flex_build.py`), `session_orphan_notice.
orphan_state_notice(project_dir)`, and the SessionStart delegation in
`hooks/session_start.py` all exist and currently ship the unscoped,
partially-unvalidated classification this story corrects. `_STORY_ID_RE`,
`_story_path`'s containment-check pattern, `_teardown_story_worktree`,
`clear_permissions_artifact`, and phase-status parsing already used elsewhere
in `flex_build.py` (e.g. `_parse_phase_stories_with_status`, consumed by the
frontmatter/table cross-check INFRA-442 added) all exist and are reused, not
reimplemented, by this story.

## Ensures

1. Given a closed/checkpointed phase's story with a stale
   `docs/phases/permissions/<ID>.json` artifact and no `state.json` stamp
   (`has_worktree=False`, `has_stale_stamp=False` — the live BUILD-024..028
   shape), `diagnose_state`'s returned `orphans` list contains no entry for
   that story. **Forbidden proxy:** filtering it out only in
   `orphan_state_notice`'s rendering while `diagnose_state`'s own `orphans`
   list still includes it — the scoping must live in `diagnose_state` itself,
   since `doctor-state --apply` reads that same list directly.
2. Given a closed/checkpointed phase whose story frontmatter `status:`
   mismatches that phase doc's Stories-table Status cell (the live BUILD-001
   shape), `diagnose_state`'s `status_drift` list contains no entry for that
   story/phase pair. A story belonging to a phase still open by the same
   active-phase signal, with the same frontmatter/table mismatch, still
   appears in `status_drift` — the fix scopes by phase openness, not by
   silencing the check.
3. A story whose own frontmatter `status:` is not one of `complete`,
   `merged`, `deferred`, `backlog` (or a phase doc whose Stories-table Status
   cell for it is not one of those) is still classified exactly as
   `diagnose_state` classifies it today (orphan when the existing
   worktree/stamp/permissions conditions hold, in-flight when a fresh stamp
   exists, drift when frontmatter and table disagree) — this story narrows
   what counts as *closed*, it does not change any classification rule for
   open work.
4. `diagnose_state`'s candidate-ID set, when `state.json`'s `current_stories`
   or `current_story.id` contains a value that does not match
   `_STORY_ID_RE` (e.g. `"; rm -rf /"` or `"../../etc"`), excludes that value
   entirely: it appears in none of `orphans`, `in_flight`, `status_drift`,
   and under `--apply` neither `_teardown_story_worktree` nor
   `clear_permissions_artifact` is ever invoked with it (asserted via a spy/
   monkeypatch on both functions, not by inspecting the returned
   classification alone).
5. A regression test asserts that `orphan_state_notice`'s (and, transitively,
   `diagnose_state`'s) status-drift scan never opens a closed/complete
   phase's `.md` file: given a fixture with N closed phases and one open
   phase, a file-access spy (wrapping `Path.read_text`/`open` for the fixture
   tree) records zero reads against the closed phases' files during the
   scan. **Forbidden proxy:** reading every phase file and discarding closed
   ones from the result — the scoping must select which phase files to open
   *before* opening them (drive the glob from an active-phase ID set, not
   from `docs/phases/*.md` unconditionally), since that is what actually
   bounds the SessionStart hook's cost as history accumulates.

## Instructions

1. In `flex_build.py`'s `diagnose_state` (~2578), before either the orphan
   classification or the `status_drift` scan, derive an active-phase ID set
   by reusing the existing phase-status parsing this file already applies
   for the frontmatter/table cross-check (`_parse_phase_stories_with_status`
   or whichever function it currently calls for that purpose — read that
   function's actual signature and behaviour in `flex_build.py` before
   wiring it in; do not reimplement phase-status parsing from scratch). A
   story/phase pair counts as still open when its own frontmatter `status:`
   is not in `{complete, merged, deferred, backlog}` **or** the phase doc's
   Stories-table Status cell for it is not in that same set — reuse
   whichever of these two checks the existing function already exposes
   rather than adding a second, parallel implementation.
2. Use the active-phase ID set to scope both fixes:
   - Orphan classification: a candidate whose owning phase/story is not in
     the active set is never added to `orphans` (Ensures 1).
   - `status_drift`: replace the unconditional `docs/phases/*.md` glob with
     one restricted to only the phase files belonging to the active set —
     the closed-phase `.md` files must not be opened at all, not merely
     filtered out of the result (Ensures 5). If phase openness is not
     knowable without opening the phase file (chicken-and-egg), resolve it
     via `docs/phases/index.md`'s own Phase table Status column first (it
     is already scanned once, cheaply, elsewhere in this codebase) to build
     the active-phase-file allow-list, then only open files on that list.
3. In the same function, filter all four candidate-ID sources —
   `claimed_story_ids()`, the permissions-filename scan, `current_stories`
   keys, and `current_story.id` — through `_STORY_ID_RE` before they enter
   the candidate set, matching the validation the first two sources already
   receive (Ensures 4). Do this at the point the four sources are unioned,
   not deep inside the classification logic, so every downstream consumer
   (orphan, in-flight, drift, and `--apply`'s teardown/clear calls) sees only
   validated IDs.
4. Do not modify `_teardown_story_worktree`, `clear_permissions_artifact`,
   `doctor-state`'s CLI contract, or `session_orphan_notice.py`'s rendering
   logic — this story tightens what `diagnose_state` classifies and what
   candidate IDs reach it; it does not change what happens once something is
   classified an orphan.
5. Ideology note (resolved inline, § Accepted constraints "Hooks are thin
   relays only"): this fix lives entirely in `flex_build.py`'s
   `diagnose_state`; `hooks/session_start.py` and `session_orphan_notice.py`
   need no code change — the hook's scan cost drops as a direct consequence
   of `diagnose_state` itself touching fewer files, not because the hook
   gained new logic.
6. Append one or two sentences to `docs/architecture.md`'s existing
   `diagnose_state`/`flex_build.py` entry (the INFRA-442 clause) noting the
   active-phase scoping rule and the four-source ID validation, in place —
   do not restate the whole entry, mirror INFRA-444's append-in-place
   convention.
7. Tests: extend `tests/pairmode/test_flex_build_doctor_state.py` with
   fixtures for Ensures 1-4 (closed-phase stale-permissions story is not an
   orphan; closed-phase frontmatter/table mismatch is not drift; open-phase
   equivalents of both are still detected as a regression control; a
   malformed `current_stories`/`current_story.id` entry is excluded
   everywhere and never reaches `_teardown_story_worktree`/
   `clear_permissions_artifact` via monkeypatch spies). Add the closed-phase
   file-access regression test (Ensures 5) either there or in
   `tests/pairmode/test_session_orphan_notice.py`, whichever fixture harness
   is the better fit — reuse the existing `git worktree add` /
   `_write_phase` / `_write_story` style fixtures already used by
   INFRA-442/443's tests rather than inventing a new one.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_doctor_state.py tests/pairmode/test_session_orphan_notice.py -q
```
Acceptance: green, including all five new Ensures cases and the pre-existing
open-phase/in-flight regression cases from INFRA-442/443.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: full suite green, run without `-x` so a real failure is not
masked by an earlier one.

## Spec-preflight note

`spec-preflight` flags `docs/phases/index.md` and `hooks/session_start.py` as
named in `## Ensures`/`## Instructions` but absent from `touches:`. Both are
intentional and read-only for this story: `docs/phases/index.md` is
referenced as the cheap phase-status source `diagnose_state` may consult
(Instructions step 2), and `hooks/session_start.py` is referenced only to
state explicitly that it needs no code change (Instructions step 5). Neither
file is written by this story, so neither belongs in `touches:`.

## Out of scope

- Changing any classification rule for stories/phases that are still open —
  this story narrows what counts as *closed* history; it does not alter
  orphan/in-flight/drift criteria for active work (Ensures 3).
- Any change to `doctor-state`'s CLI contract, `--apply`'s repair behaviour,
  or `session_orphan_notice.py`'s advisory rendering — those are
  INFRA-442/443's surface; this story only tightens `diagnose_state`'s input
  scoping and ID validation.
- Actually running `doctor-state --apply`/`--sync-status` against this
  repo's present 118/59 historical findings — this story fixes the
  classifier so they stop being misclassified going forward; draining any
  genuinely-open drift that remains after the fix is a separate operational
  action, not part of this spec.
- A general phase-doc archival/index redesign — this story reuses the
  existing phase-status parsing and `docs/phases/index.md` Phase table; it
  does not introduce a new archival scheme.
</content>
