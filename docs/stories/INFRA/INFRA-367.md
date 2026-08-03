---
id: INFRA-367
rail: INFRA
title: Add non-interactive rail-creation flags to story_new.py (CER-117)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_story_new.py
  - skills/pairmode/SKILL.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-117 (LOW): `story_new.py` prompts interactively (`Rail X does not exist. Create it? [Y/n]`)
when the target rail doesn't exist yet, which aborts under a non-interactive orchestrator unless
the prompt is piped `yes`. Fix direction: add a `--create-rail` (or `--yes`) flag so
scripted/orchestrated invocations can bypass the prompt. File: `skills/pairmode/scripts/story_new.py`
(the rail-creation prompt path). Surfaced by RELEASE-067 E12 (new-2), 2026-07-29.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- No prior story is a hard prerequisite. **Ordering only:** INFRA-380 (CER-62) edits a different
  function in the same file (`_append_to_phase`'s phase-manifest glob). Build the two serially, or
  rebase before merging, to avoid a spurious conflict in `story_new.py`.
- `skills/pairmode/scripts/story_new.py` still contains the interactive rail-creation prompt
  (`Rail X does not exist. Create it? [Y/n]`) at build time.

## Ensures

1. `story_new.py` accepts a `--create-rail` flag and a `--yes` / `-y` flag. `--yes` implies
   `--create-rail`; either one alone suffices to create a missing rail.
2. With `--create-rail` (or `--yes`), invoking `story_new.py` for a story whose rail directory does
   not exist creates `docs/stories/<RAIL>/`, writes the story file, and exits 0 **without reading
   stdin at all**. Verifiable with stdin closed/empty (no `yes |` pipe).
   **Forbidden proxy:** a run that only *appears* non-interactive because a TTY check happened to
   default to yes, or because stdin was pre-fed — the assertion is that the prompt is never issued
   when the flag is present.
3. Without either flag, and with stdin **not** a TTY, the missing-rail case exits non-zero with a
   message naming `--create-rail` (or `--yes`) as the fix. It does not hang, does not consume an
   unrelated line of stdin, and does not create the rail directory.
   **Forbidden proxy:** silently auto-creating the rail whenever stdin is not a TTY — that turns a
   typo'd rail into a new directory with no human in the loop.
4. Without either flag and with an interactive stdin, existing behaviour is byte-unchanged: the same
   prompt text, `Y` default, and abort-on-`n` path as before this story.
5. When the rail directory already exists, `--create-rail` / `--yes` are no-ops — the run behaves
   identically to a run without them.
6. `tests/pairmode/test_story_new.py` covers Ensures 2, 3, and 5.
7. Full `tests/pairmode/` suite green.

## Instructions

1. Add `--create-rail` (store_true) and `--yes` / `-y` (store_true) to `story_new.py`'s argparse
   setup. Resolve them to a single internal boolean (`--yes` OR `--create-rail`) at one place, and
   consult only that boolean at the rail-creation branch — do not scatter two flag checks through
   the prompt path.
2. At the missing-rail branch, gate on that boolean first: if set, create the directory and continue
   with no prompt. If not set, branch on `sys.stdin.isatty()` — TTY keeps today's prompt verbatim,
   non-TTY prints an error naming the flag and exits non-zero (do not fall through to `input()`,
   which is what makes the current code abort opaquely under an orchestrator).
3. Keep the flags help-text explicit that they only affect rail creation, not any other confirmation
   the script may add later.
4. Add the tests in Ensures 6 to `tests/pairmode/test_story_new.py`, driving the script in-process
   (or via subprocess with stdin closed) rather than by piping `yes`. Assert on directory/file
   existence and exit code, not on captured stdout.

Ideology note: the non-TTY-without-flag case is made an explicit error rather than an implicit
auto-create, to preserve the "never silently pass contradictions" constraint — creating a rail is a
structural decision, so it stays opt-in via an explicit flag rather than inferred from the absence
of a terminal.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green, including the new flag-bypasses-prompt and non-TTY-without-flag-errors tests.

## Out of scope

- Any other interactive prompt in `story_new.py` or in sibling scripts (`phase_new.py`,
  `bootstrap.py`). Only the rail-creation prompt is in scope; other prompts found while working here
  are CER material, not inline fixes.
- INFRA-380's `_append_to_phase` phase-manifest glob fix (CER-62), even though it lives in the same
  file.
- A project-wide `--non-interactive` mode or config switch. This story adds two local flags only.

## Spec notes

- `primary_files:` is absent from this story's frontmatter (the stub was scaffolded without it).
  Per the spec-writer procedure this is a human-review signal, so this spec returns `revised`:
  confirm `skills/pairmode/scripts/story_new.py` as the primary file before building.

## Evidence

- CER-117 was already resolved by `feat(story-INFRA-301): non-interactive scaffolding flags +
  phase-registration warning surfacing` (commit `e27232d6`, 2026-07-30), one day after the CER
  was surfaced (2026-07-29) and before this stub (INFRA-367, phase 119) was drafted. This is a
  stale/duplicate backlog re-filing, not a live gap.
- Verified `skills/pairmode/scripts/story_new.py` at build time against every Ensures item with
  zero production-code changes required:
  - Ensures 1: `--create-rail`/`--no-create-rail` (tri-state, `default=None`) and `--yes`/`-y`
    are both present (lines 314–330); `yes or create_rail is True` gates rail creation at one
    call site (line 388).
  - Ensures 2: the `create_rail is True or yes` branch (lines 388–394) creates the rail
    directory and continues with no call to `click.prompt`/`input()` anywhere on that path —
    confirmed by `test_create_rail_flag_creates_no_prompt` / `test_yes_flag_creates_no_prompt`
    invoked with `input=None`.
  - Ensures 3: the no-flag branch (lines 395–415) catches `click.Abort`/`EOFError` from
    `click.prompt` on a closed/EOF stdin and exits 1 with a message naming `--create-rail`,
    without creating the rail dir — confirmed by
    `test_missing_rail_no_flags_eof_stdin_exits_1_with_actionable_message`. (Documented design
    choice, `docs/architecture.md` § story_new.py non-interactive scaffolding contract: EOF/Abort
    detection is used instead of a pre-emptive `sys.stdin.isatty()` gate, because Click's
    `CliRunner` — and every legitimate piped-stdin caller — presents a non-TTY stdin even when
    real interactive input follows, so an `isatty()` gate would reject working callers.)
  - Ensures 4: the TTY/interactive path (lines 402–418) is untouched — same prompt text, `Y`
    default, abort-on-`n` behaviour as before INFRA-301/this story.
  - Ensures 5: the flag checks live entirely inside `if not rail_dir.is_dir():` (line 380), so
    when the rail already exists the flags are structurally inert. Added
    `test_create_rail_flag_is_noop_when_rail_already_exists` and
    `test_yes_flag_is_noop_when_rail_already_exists` to `tests/pairmode/test_story_new.py` to
    close the gap between this Ensures item and the existing test file (the prior no-prompt test
    for an existing rail didn't pass either flag).
  - Ensures 6: `tests/pairmode/test_story_new.py::TestNonInteractiveRailCreation` covers Ensures
    2, 3, and 5 (the last two tests added by this story).
  - Ensures 7: full `tests/pairmode/` suite green — 4872 passed, 211 skipped.
- `skills/pairmode/SKILL.md` (lines ~644–668) and `docs/architecture.md` (§ story_new.py
  non-interactive scaffolding contract, ~line 1771) already document the CER-117 fix; no
  documentation change was needed.
- Net change for this story: two new no-op regression tests in
  `tests/pairmode/test_story_new.py`. No change to `skills/pairmode/scripts/story_new.py`,
  `skills/pairmode/SKILL.md`, or `docs/architecture.md`.
