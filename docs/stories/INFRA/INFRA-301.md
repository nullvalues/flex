---
id: INFRA-301
rail: INFRA
title: "Non-interactive scaffolding: create-rail flag; surface phase-manifest registration failures"
status: complete
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_story_new.py
  - skills/pairmode/SKILL.md
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`story_new.py` is the scaffolding CLI every rail passes through, and it still has two
hostile-to-automation behaviours that surfaced during the RELEASE-067 proving cycle.

First (CER-117): when the requested rail directory does not exist, the CLI calls
`click.prompt("Rail {rail} does not exist. Create it? [Y/n]", ...)` at
`skills/pairmode/scripts/story_new.py:328-332`. Under a non-interactive orchestrator with
no stdin attached, `click.prompt` hits EOF, raises `click.Abort`, and the command dies with
a bare `Aborted!` and exit 1 — no indication that the cause was a missing rail or that
piping `yes` would have fixed it. The only workaround today is to pipe input, which is a
caller-side hack around a missing flag. Every other non-interactive-capable CLI in this
repo already carries the escape hatch: `bootstrap.py:1044-1050` defines
`--yes` / `-y` as `is_flag=True, default=False` with help text "Auto-confirm all prompts.
Use for non-interactive/CI invocations." `story_new.py` has no equivalent.

Second (CER-062, residual): the phase-manifest glob half of CER-062 was already fixed by
INFRA-197 — `_append_to_phase` now tries all three filename shapes (`{phase}-*.md` at
`:140-141`, exact `phase-{phase}.md` at `:143-146`, suffixed `phase-{phase}-*.md` at
`:150-152`) and the architecture doc records those shapes at `docs/architecture.md:1273`.
What CER-062 also asked for — "consider surfacing a warning when auto-registration falls
through to `False` rather than failing silently" — is only half done. The CLI path
(`:362-370`) does warn, but the message names only the phase, not the story that failed to
register, so an orchestrator scraping stderr cannot tell which story drifted. The
programmatic API `create_story()` discards the return value outright at `:251`
(`_append_to_phase(resolved, phase, story_id, title)` with no assignment), so
`lesson_review.py`'s drift-promotion path (`lesson_review.py:301-302`, which defaults
`create_story_fn` to the real `story_new.create_story`) can silently create a story that
never appears in any phase manifest. That is exactly the "never silently pass
contradictions" constraint in `docs/ideology.md` being violated by omission: the phase
manifest and the story tree diverge and nothing says so.

This story closes both: an explicit non-interactive contract for rail creation, and a
single warning text emitted by both entry points when phase registration falls through.

## Requires

- `skills/pairmode/scripts/story_new.py` exists with:
  - `_append_to_phase(project_dir, phase, story_id, title) -> bool` at `:138`, with its
    three glob shapes at `:140-141`, `:143-146`, `:150-152` and its `return False` at
    `:153-154`.
  - `create_story(...)` (programmatic API) at `:196`, whose docstring already states
    "The rail directory is created automatically if it does not exist (no prompt)", and
    which discards `_append_to_phase`'s return at `:251`.
  - the `story_new` click command at `:261-370`, with the rail-creation
    `click.prompt` at `:328-332`, the decline branch `sys.exit(0)` at `:333-335`, and the
    phase-registration warning at `:362-370`.
- `skills/pairmode/scripts/bootstrap.py:1044-1050` defines the repo's `--yes` / `-y`
  convention (`is_flag=True, default=False`, help "Auto-confirm all prompts. Use for
  non-interactive/CI invocations.") — this story mirrors it, it does not invent a new one.
- `tests/pairmode/test_story_new.py` exists, with the `invoke()` helper at `:20-23` that
  defaults `input="Y\n"`, and `TestNewRailPrompt` at `:103-135` asserting: decline (`n`)
  exits 0 and creates no directory; accept (`Y`) creates directory and story; an existing
  rail needs no input.
- No sibling story in Phase 114 is a prerequisite. INFRA-301 is independent of INFRA-302,
  303, 304; INFRA-305 (the doc-currency sweep) runs strictly last in the phase and does not
  gate this one.
- Baseline: `main`'s full suite is green — 4116 passed, 211 skipped. There is no accepted
  pre-existing failure on `main`. If the suite is run from a story worktree and
  `test_observability_ui` fails, that is the CER-090 vendored-payload gap in the worktree
  copy, not a code defect: fix it by rsyncing the payload from the main checkout. Never run
  `pnpm install` to repair it.

## Ensures

1. `story_new` (the click command) gains a tri-state boolean flag pair
   `--create-rail/--no-create-rail` bound to one parameter (`create_rail`) with
   `default=None`, so "unspecified" is distinguishable from both "yes" and "no".
2. `--create-rail` (or `create_rail is True`): a missing rail directory is created with no
   prompt, the era Rails table is still updated via `_find_era` + `_add_rail_to_era` exactly
   as the current accept-branch does, and the command exits 0.
3. `--no-create-rail` (or `create_rail is False`): a missing rail directory is **not**
   created, no story file is written, a message naming the rail and the flag is written to
   stderr, and the command exits **non-zero** (exit 1). Asserted by test: the rail directory
   does not exist afterwards and `result.exit_code == 1`.
4. When `create_rail is None` and the rail is missing, the existing interactive prompt is
   preserved verbatim as the default path — same prompt string
   (`Rail {rail} does not exist. Create it? [Y/n]`), same `default="Y"`,
   `show_default=False`, same decline semantics (`n` → `Aborted.` → **exit 0**). The two
   existing `TestNewRailPrompt` tests at `tests/pairmode/test_story_new.py:106-124` pass
   unmodified.
5. `--yes` / `-y` is added as an `is_flag=True, default=False` option whose help text
   states it auto-confirms prompts for non-interactive/CI use, mirroring
   `bootstrap.py:1044-1050`. When `--yes` is passed and `create_rail` is `None`, it implies
   `--create-rail`: the rail is created with no prompt and the command exits 0. Asserted by
   test invoking with `--yes` and `input=None`.
6. `--yes` together with `--no-create-rail` is a contradiction: the command writes a message
   to stderr naming both flags and exits 1 **before** creating any directory or story file.
   Asserted by test (no rail dir, no story file, exit 1).
7. Non-interactive stdin with no rail-creation flag produces an **explicit, actionable
   error** rather than click's bare `Aborted!`: the `click.prompt` call is wrapped so that
   `click.Abort` and `EOFError` are caught, and the handler writes a single stderr line that
   names (a) the missing rail, (b) that stdin was not interactive, and (c) both
   `--create-rail` and `--yes` as the fix, then exits 1. Asserted by a test invoking with a
   missing rail and `input=""` (EOF): `result.exit_code == 1`, stderr/output contains the
   rail name and the string `--create-rail`, and the rail directory was not created.
8. **Decision, stated explicitly:** non-interactivity is detected by catching the prompt's
   EOF/`Abort`, **not** by pre-emptively testing `sys.stdin.isatty()`. Rationale recorded in
   a code comment naming CER-117: click's `CliRunner` and every legitimate piped-stdin
   invocation both present a non-TTY stdin, so an `isatty()` gate would reject working
   callers (including this story's own test suite) as a side effect. The comment must state
   this, not merely reference the CER.
9. A single module-level helper produces the phase-registration-failure warning text —
   e.g. `_phase_registration_warning(story_id: str, phase: str) -> str` — so the CLI and
   the programmatic API cannot drift. The text names **both** the story ID and the phase
   (the current CLI text at `:367-370` names only the phase).
10. The CLI path at `:362-370` emits that helper's text to stderr when `_append_to_phase`
    returns `False`, and the command still exits **0**.
11. `create_story()` no longer discards the return at `:251`: it captures the `bool` and,
    when `False`, emits the same helper text to stderr (`click.echo(..., err=True)`), then
    still returns the created story `Path` — it does not raise. Asserted by a test that calls
    `create_story(..., phase="999")` against a project with no phase-999 manifest and
    asserts the returned path exists and the warning text was emitted.
12. **Decision, stated explicitly in a code comment and in `docs/architecture.md`:** a
    failed phase-manifest registration is a **warning, not an error** — both entry points
    stay on their success path (CLI exit 0; `create_story` returns the `Path`). Rationale:
    the story file itself was written correctly and is the durable artifact; the manifest row
    is derived state an operator or `check-index` can reconcile. Failing the command would
    strand a correctly-written story behind a non-zero exit and push callers toward
    ignoring the exit code entirely. This is a deliberate departure from "fail loudly" and
    must be written down, not inferred.
13. `_append_to_phase`'s three glob shapes at `:140-141`, `:143-146`, `:150-152` are
    unchanged — byte-identical lookup order and patterns, including the CER-062/INFRA-197
    comment at `:147-149`. Pinned by a test that registers a story into each of the three
    manifest filename shapes and asserts the row lands.
14. `skills/pairmode/SKILL.md`'s `/flex:pairmode story` section (`:633-665`) documents
    `--create-rail/--no-create-rail` and `--yes`/`-y` under "Inputs expected", and step 3 of
    "What it does" is corrected to describe the flag-first / prompt-fallback / explicit
    non-interactive-error behaviour instead of the unconditional prompt it currently claims.
15. `docs/architecture.md` records the non-interactive scaffolding contract and the
    warning-not-error decision from Ensures 12, adjacent to the existing `_append_to_phase`
    glob-shape note at `:1273`.
16. Full test suite green with no `-x`: `4116+ passed, 211 skipped`, zero failures. There is
    no accepted pre-existing failure to exempt.

## Instructions

1. **Flags.** On the `story_new` click command (`story_new.py:261-288`) add, after
   `--project-dir`:
   - `@click.option("--create-rail/--no-create-rail", "create_rail", default=None, help=...)`
     — the `default=None` is load-bearing; it is what makes "unspecified → prompt" possible.
   - `@click.option("--yes", "-y", is_flag=True, default=False, help="Auto-confirm all
     prompts. Use for non-interactive/CI invocations.")` — copy the shape and intent from
     `bootstrap.py:1044-1050`; do not invent different help wording.
   Add both to the function signature.
2. **Conflict check first.** Immediately after the existing `project-dir` and rail-name
   guards (`:291-324`), and before any filesystem mutation, reject `--yes` combined with
   `--no-create-rail` (`yes and create_rail is False`) with a stderr message naming both
   flags and `sys.exit(1)`. Placing it here is what satisfies Ensures 6's "before creating
   any directory or story file".
3. **Rail-creation branch.** Replace the body of `if not rail_dir.is_dir():` (`:327-342`)
   with a three-way resolution, keeping the existing `mkdir` + `_find_era` +
   `_add_rail_to_era` tail shared by all creating paths:
   - `create_rail is False` → stderr message naming the rail and `--no-create-rail`,
     `sys.exit(1)`.
   - `create_rail is True or yes` → create, no prompt.
   - otherwise → the existing `click.prompt` call, unchanged in wording, default, and
     `show_default`, wrapped in `try: ... except (click.Abort, EOFError):`. The handler
     writes the explicit non-interactive error (Ensures 7) and `sys.exit(1)`. Keep the
     `answer.strip().lower() == "n"` decline branch exactly as-is, including its
     `click.echo("Aborted.")` and `sys.exit(0)` — existing tests assert exit 0 there.
   Add the comment required by Ensures 8 above the `except` clause: name CER-117 and state
   why `sys.stdin.isatty()` is deliberately not used (CliRunner and piped stdin are both
   non-TTY, so an isatty gate would reject working callers).
   Note the asymmetry deliberately: interactive `n` exits 0 (a human cancelled), while
   `--no-create-rail` exits 1 (a script asserted a precondition that did not hold). Record
   this one-liner in the flag's help text so the difference is discoverable.
4. **Shared warning text.** Add a module-level helper near `_append_to_phase`:

   ```python
   def _phase_registration_warning(story_id: str, phase: str) -> str:
       """Single source of the phase-manifest registration-failure warning (CER-062)."""
   ```

   Its text must name the story ID and the phase and say the story file was still created —
   e.g. `f"  Warning: {story_id} was created but could not be registered in a phase manifest for phase '{phase}' — add the Stories-table row manually."`
   Exact wording is the builder's, but story ID, phase, and "created" must all appear.
5. **Wire both call sites.** At `:362-370` replace the inline warning string with
   `click.echo(_phase_registration_warning(story_id, phase), err=True)`; the success branch
   (`Added to Phase {phase}`) and the exit-0 fall-through are unchanged. At `:250-251` in
   `create_story`, capture the return and emit the same helper text via
   `click.echo(..., err=True)` when it is `False`; do not raise, do not change the return
   type. Add the Ensures-12 warning-not-error comment at one of the two sites and
   cross-reference it from the other.
6. **Do not touch `_append_to_phase`'s lookup logic.** The three globs and the
   CER-062/INFRA-197 comment stay byte-identical. This story surfaces the `False`; it does
   not change when `False` happens.
7. **Docs.** Update `skills/pairmode/SKILL.md` `/flex:pairmode story` (Inputs expected list
   and "What it does" step 3), and add the architecture note near `docs/architecture.md:1273`.
8. **Ideology-alignment note (Step 4a, resolved inline).** `docs/ideology.md`'s "Never
   silently pass contradictions" constraint drove the shape of Ensures 9-12: the divergence
   between story tree and phase manifest is surfaced on stderr from both entry points rather
   than dropped, which satisfies the constraint's rationale (the system must catch what
   humans and agents forget) without adopting a hard failure that would strand a correctly
   written story file. No conviction, constraint, or prototype fingerprint is contradicted;
   the "Python everywhere" fingerprint is preserved.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Run the full suite **without** `-x`, so a real failure later in the run cannot be masked.

New coverage in `tests/pairmode/test_story_new.py` (extend `TestNewRailPrompt`, or add a
sibling class `TestNonInteractiveRailCreation`):

- `--create-rail` with `input=None` on a missing rail → exit 0, rail dir exists, story file
  exists, era Rails table updated.
- `--no-create-rail` on a missing rail → exit 1, rail dir absent, no story file, stderr
  names the rail.
- `--yes` with `input=None` on a missing rail → exit 0, rail dir exists.
- `--yes --no-create-rail` → exit 1, rail dir absent, message names both flags.
- Missing rail, no flags, `input=""` (EOF) → exit 1, output contains the rail name and
  `--create-rail`, rail dir absent, and the output is **not** the bare `Aborted!`.
- Existing `TestNewRailPrompt` cases (`n` → exit 0 no dir; `Y` → dir + story; existing rail
  → no prompt) pass **unmodified** — do not edit them.
- `create_story(..., phase="999")` with no matching manifest → returns an existing `Path`,
  and the warning text (containing the story ID and `999`) reached stderr. Capture via
  `capsys`.
- CLI `--phase 999` with no matching manifest → exit **0**, warning text contains the story
  ID and `999`.
- Three-shape glob pin: one test each for `999-something.md`, `phase-999.md`, and
  `phase-999-suffix.md` manifests — the story row lands in each.

Acceptance: `tests/pairmode/` fully green (baseline 4116 passed, 211 skipped, zero failures)
with the new cases added. A `test_observability_ui` failure means the run happened in a
worktree with an incomplete vendored payload (CER-090) — rsync the payload from the main
checkout and re-run; it is not a signal about this story, and `pnpm install` is never the
fix.

## Out of scope

- Changing **when** `_append_to_phase` returns `False` — the glob shapes are settled by
  INFRA-197 and stay byte-identical. This story only surfaces the failure.
- Making phase-registration failure a hard error (non-zero exit / raised exception).
  Explicitly rejected in Ensures 12 with rationale; revisit only if an operator decides a
  story file without a manifest row should be unbuildable.
- Auto-creating a missing phase manifest when `--phase` names one that does not exist —
  phase authoring belongs to `phase_new.py` (`docs/architecture.md`, INFRA-243), not to
  `story_new.py`.
- An `--assume-no` / global non-interactive env var (e.g. `FLEX_NONINTERACTIVE`) covering
  every prompt in the toolchain. This story adds the flag pair to `story_new.py` only.
- `isatty()`-based non-interactivity detection anywhere in the toolchain — rejected here for
  the reason in Ensures 8; if a future story wants it, it must first solve the CliRunner /
  piped-stdin false positive.
- Any change to `lesson_review.py`'s drift-promotion flow beyond it inheriting the new
  `create_story` warning for free.
- The `--yes` flag on any other script (`pairmode_sync.py`, `era_transition.py`,
  `flex_build.py`, `pairmode_migrate.py` already have their own).
- Sibling Phase 114 work: worktree provisioning (INFRA-302), migration rules (INFRA-303),
  `spec_preflight` containment (INFRA-304), doc-currency sweep (INFRA-305).
- Annotating the CER-117 / CER-062 backlog rows as RESOLVED — INFRA-305 owns the backlog
  annotation pass for this phase.
