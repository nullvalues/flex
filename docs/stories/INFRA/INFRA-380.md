---
id: INFRA-380
rail: INFRA
title: Match suffixed phase filenames in story_new.py's phase-manifest lookup (CER-62)
status: complete
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_story_new.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-62 (MEDIUM): `story_new.py`'s `_append_to_phase` phase-manifest lookup
(`skills/pairmode/scripts/story_new.py:127-137`) only matches two filename shapes — `{phase}-*.md`
and exact `phase-{phase}.md`. Suffixed phase manifests of the form `phase-<phase_id>-<suffix>.md`
(the naming convention `phase_new.py --phase-id --suffix` produces, per CER-038) match neither
glob, so `story_new.py --phase MU020` silently returns `False` from `_append_to_phase` and the new
story is never added to the phase's Stories table — with no error surfaced to the caller. This was
confirmed live on the Repo-L project (fable-orchestrated build), where the operator had to add the
Stories table rows by hand. Fix: add a third glob `phase-{phase}-*.md` (or generalize to
`*{phase}*.md`) alongside the two existing globs, and consider surfacing a warning when
auto-registration falls through to `False` instead of failing silently. Story files are still
created correctly under this bug — only the phase manifest's Stories table drifts until manually
reconciled. File: `skills/pairmode/scripts/story_new.py:127-137` (`_append_to_phase`).

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- No prior story. INFRA-367 (CER-117) edits a different function in the same file
  (`story_new.py`'s interactive rail-creation prompt); if it lands first, rebase rather than
  reconciling by hand.

## Ensures

1. `_append_to_phase` in `skills/pairmode/scripts/story_new.py` locates a phase manifest named
   `phase-<phase>-<suffix>.md` (e.g. `phase-MU020-worldbuilding.md` for `--phase MU020`) in
   addition to the two shapes it already matches (`<phase>-*.md`, `phase-<phase>.md`), and appends
   the new story's row to that file's Stories table.
2. Matching is anchored on the phase id, not a substring sweep: a phase id that is a strict prefix
   of another does not match the longer one's manifest — a request for `119` does not match
   `phase-1190-*.md` or `phase-2119-*.md`.
   **Forbidden proxy:** a broad `*<phase>*.md` glob that happens to pass the suffixed-name test
   while also matching unrelated phase ids.
3. When more than one file matches, selection is deterministic (sorted), so repeated runs against
   the same tree pick the same manifest.
4. When no manifest matches, `_append_to_phase` still returns `False` **and** the caller surfaces a
   visible warning to stderr/stdout naming the phase whose manifest was not found; the story file
   itself is still created. **Forbidden proxy:** returning `False` with no operator-visible output,
   which is exactly the silent-drift failure CER-62 recorded.
5. `tests/pairmode/test_story_new.py` contains a test that creates a `phase-<id>-<suffix>.md`
   manifest, runs the story-creation path against it, and asserts the new story ID appears in that
   file's Stories table — plus a test for the not-found warning (Ensures 4) and a negative test for
   Ensures 2.
6. Full `tests/pairmode/` suite green.

## Instructions

1. In `_append_to_phase` (`skills/pairmode/scripts/story_new.py`, ≈lines 127-137), add the
   `phase-{phase}-*.md` glob alongside the two existing patterns. Do not replace the existing
   patterns and do not generalize to `*{phase}*.md` — the loose form breaks Ensures 2 by matching
   phase ids that merely contain the requested one as a substring.
2. Collect candidates from all patterns, de-duplicate, and sort before choosing, so multi-match
   behaviour is deterministic rather than dependent on filesystem iteration order.
3. Where the caller handles a `False` return from `_append_to_phase`, print a warning that names
   the phase and the searched directory. Do not raise or exit non-zero — story creation itself
   succeeded and must keep succeeding; the point is that the fall-through stops being invisible.
   This follows the ideology's "never silently pass contradictions" constraint: the fix makes the
   failure legible rather than merely making the common case work.
4. Add the tests from Ensures 5 to `tests/pairmode/test_story_new.py`, following the existing
   tmp-path fixtures in that file. Assert on the manifest file's contents and on captured output,
   not on internal call counts.
5. Touch only `_append_to_phase` and its immediate caller's warning path. Leave the interactive
   rail-creation prompt alone — that is INFRA-367's scope, in the same file.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green, including the new suffixed-manifest, negative-match, and
warning-on-no-match tests.

## Out of scope

- Retroactively reconciling any phase manifest whose Stories table already drifted under this bug
  (including the Repo-L project's) — this story fixes the lookup, not existing drift.
- Changing `phase_new.py`'s suffixed-filename naming convention (CER-038) or the Stories-table row
  format itself.
- The `--create-rail`/`--yes` non-interactive flags in the same file (INFRA-367).
