---
id: INFRA-197
rail: INFRA
title: "story_new.py phase-manifest glob — support suffixed phase filenames (CER-062)"
status: complete
phase: "87"
story_class: code
primary_files:
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_story_new.py
---

# INFRA-197 — story_new.py phase-manifest glob — support suffixed phase filenames (CER-062)

## Context

Surfaced via an external report from the radar project (fable-orchestrated
build): `story_new.py --phase MU020` created the story file correctly but
silently failed to add the new row to the phase manifest's Stories table,
requiring the operator to add it by hand.

`_append_to_phase` (`skills/pairmode/scripts/story_new.py:127-137`) resolves
the target phase manifest with two glob attempts, in order:

1. `{phase}-*.md` — treats the `--phase` value itself as the filename prefix
   (matches, e.g., a hypothetical `MU020-something.md`).
2. `phase-{phase}.md` — exact match only (matches `phase-MU020.md`).

Neither matches a **suffixed** phase manifest — filenames of the form
`phase-<phase_id>-<suffix>.md` — which is the naming convention
`phase_new.py --phase-id --suffix` produces (see CER-038,
`docs/cer/backlog.md`). When no glob matches, `_append_to_phase` returns
`False` and the caller (`cmd_new` / the CLI entry point) does not surface an
error distinguishing "no phase manifest found" from "found but couldn't
parse" — the operator only notices the Stories table wasn't updated by
reading the phase doc afterward.

Logged as CER-062 in `docs/cer/backlog.md` (Do Later) and pulled forward into
Phase 87 as a low-effort, directly-related fix.

## Acceptance criteria

1. `story_new.py --phase <phase_id>` successfully appends the new story row
   to the Stories table of a phase manifest named `phase-<phase_id>-<suffix>.md`
   (suffixed form), in addition to the two filename shapes already supported.

2. The existing two supported shapes (`{phase}-*.md` and exact
   `phase-{phase}.md`) continue to work unchanged — no regression on
   `test_phase_flag_appends_row_to_existing_table` or
   `test_phase_flag_creates_stories_section_if_absent`
   (`tests/pairmode/test_story_new.py`).

3. If multiple phase manifests match the phase id ambiguously (e.g. both a
   suffixed and unsuffixed file exist for the same id), behavior is
   deterministic — pick the first match from `sorted()` glob results and do
   not crash. Document the tie-break in a code comment only if the ambiguity
   is realistically reachable; do not add new CLI flags to resolve it.

4. `story_new.py` still returns/prints the existing "added to phase X" /
   silent-fallthrough behavior consistently — no change to caller-facing
   output contract beyond fixing the match itself. (Surfacing a warning on
   fallthrough is explicitly out of scope — see below.)

5. New test(s) added to `tests/pairmode/test_story_new.py` covering the
   suffixed-filename case (e.g. `phase-87-widget.md` or similar), verifying
   the story row lands in that file's Stories table.

6. Full build gate green:
   `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`

## Implementation guidance

- Add a third glob attempt in `_append_to_phase`, tried between (or after)
  the existing two: `phase-{phase}-*.md`. Use `sorted(glob.glob(...))` for
  determinism if more than one candidate can match.
- Keep the existing two glob attempts and their order; only add the new one
  — do not restructure the function's control flow beyond what's needed to
  insert a third lookup.
- `phase` here is the `--phase` CLI argument value (e.g. `"MU020"`, `"87"`)
  — same variable already in scope, no new sanitization needed since this
  story doesn't change how `phase` is validated upstream.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

### Out of scope

- Surfacing a warning/error when `_append_to_phase` falls through to `False`
  (no manifest found at all) — that's a separate, broader silent-failure
  question not limited to the suffixed-filename case. Leave as a future
  finding if it recurs.
- Any change to `phase_new.py`'s `--phase-id`/`--suffix` naming convention
  itself (CER-038) — this story only teaches `story_new.py` to recognize the
  existing convention.
- Ambiguity-resolution CLI flags (e.g. `--phase-file <exact path>`) — not
  needed unless the sorted-first-match tie-break proves insufficient in
  practice.
