---
id: INFRA-263
rail: INFRA
title: Fix record-attempt click alias to forward the full option set (CER-071, CER-073)
status: draft
phase: "104"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
touches:
  - tests/pairmode/test_flex_build_record_attempt_alias.py
  - docs/cer/backlog.md
  - docs/architecture.md
  - CHANGELOG.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`flex_build.py record-attempt` (RELEASE-009, `skills/pairmode/scripts/flex_build.py:2338-2358`)
is a delegating alias to `record_attempt.py`. Its body is correct — it builds
`[sys.executable, record_attempt.py, *forwarded]` and exits with the child's return code —
but its **Click declaration is empty**:

```python
@flex_build.command("record-attempt")
@click.pass_context
def cmd_record_attempt(ctx: click.Context, **kwargs: object) -> None:
```

No `context_settings`, no options, no variadic argument. Click therefore parses the
subcommand's argv itself against an option set containing only the auto-added `--help`,
and rejects every real flag *before* the body ever runs. The body's
`sys.argv[sys.argv.index("record-attempt") + 1:]` is dead code in practice.

Reproduced on clean HEAD during this story's recon (2026-07-25):

```
$ python skills/pairmode/scripts/flex_build.py record-attempt \
    --project-dir p --story-id INFRA-263 --agent-role builder
Usage: flex_build.py record-attempt [OPTIONS]
Error: No such option: --project-dir            # exit 2
```

while the identical invocation against the delegate directly succeeds:

```
$ python skills/pairmode/scripts/record_attempt.py \
    --project-dir p --story-id INFRA-263 --agent-role builder --attempt-number 1 --outcome PASS
recorded attempt for INFRA-263 (agent=builder, attempt=1)   # exit 0
```

**CER-071 and CER-073 are duplicate filings of this one defect** (backlog lines 71 and 59):
CER-071 diagnosed it as "the alias declares its own narrower option set instead of passing
`*args` through, unlike `create-story-worktree`"; CER-073 reports the live hit on forqsite's
first Era-3 story cycle (2026-07-22) and prescribes the fix used here —
`context_settings={"ignore_unknown_options": True}` plus a variadic passthrough argument, plus
a test that a full real record-attempt flag set round-trips through the alias. Both rows are
closed by this story.

Why it matters now rather than "eventually": the alias is the *documented* entry point.
`docs/architecture.md`'s flex_build.py CLI surface (line 56) lists `record-attempt` as the
"single entry point ... so the orchestrator template can call a single entry point";
`docs/agreements/HARNESS006-main.md:71` and `docs/stories/INFRA/INFRA-224.md:143` both show
`flex_build.py record-attempt ...` as the loop's recording step. Every downstream orchestrator
that follows the documentation literally gets exit 2 and must discover the
`record_attempt.py` path itself — which is precisely the coupling the alias exists to remove.
flex's own `CLAUDE.build.md` currently records via
`subagent_transcript.record_attempt_from_transcript()` rather than this CLI, which is the only
reason flex itself has not been blocked; that makes this a fleet-facing defect that flex's own
green build loop cannot detect. Fixing it before the fleet campaign is the phase-104 goal
("make attempt recording ... provably correct before the fleet campaign").

Two secondary gains fall out of the same edit, and both are deliberate rather than incidental:

- Dropping `sys.argv` in favour of Click's collected argument tuple removes the
  argument-truncation window flagged as a LOW in RELEASE-009's security audit
  (`docs/checkpoints.md:12` — "`sys.argv.index` argument-truncation in `cmd_record_attempt`"):
  `sys.argv.index` finds the *first* occurrence of the literal string `record-attempt`, so a
  value that happens to equal the subcommand name (e.g. `--notes record-attempt`) silently
  truncates the forwarded argv.
- Forwarding `--help` to the delegate (rather than letting Click answer it from the alias's
  empty option set) means `record-attempt --help` prints the option list users actually need.
  Today it prints `Usage: flex_build.py record-attempt [OPTIONS]` with no options at all —
  actively misleading, and the thing that made CER-071's reporter conclude the option set was
  "narrower" rather than absent.

## Requires

- `skills/pairmode/scripts/flex_build.py` still contains `cmd_record_attempt`
  (`@flex_build.command("record-attempt")`, ~line 2338) with the empty declaration described
  above, and `record_attempt.py` sits in the same `skills/pairmode/scripts/` directory.
- `record_attempt.py` is runnable as a standalone script (it self-inserts repo root and
  scripts dir into `sys.path` at lines 22-24), verified in recon above. The alias does not
  need to set `PYTHONPATH`.
- `docs/cer/backlog.md` contains CER-071 and CER-073 in the **Do Later** section, both
  unresolved (no `RESOLVED` marker in the Finding cell).
- `tests/pairmode/` passes on clean HEAD, with the single known pre-existing
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` failure acceptable **only**
  if it reproduces on clean HEAD.
- No in-flight edit to `flex_build.py` from a sibling phase-104 story. Per the phase doc's
  Ordering section, INFRA-263 builds **first** of the `flex_build.py` group (263 → 264 → 265
  → 266 → 267), so this story owns the file for its cycle.

## Ensures

1. `cmd_record_attempt` in `skills/pairmode/scripts/flex_build.py` is declared with
   `context_settings={"ignore_unknown_options": True}` and `add_help_option=False` on its
   `@flex_build.command("record-attempt")` decorator, and carries a variadic
   `@click.argument(..., nargs=-1, type=click.UNPROCESSED)` that collects everything after the
   subcommand name.

2. The function body contains no reference to `sys.argv` (verifiable: `sys.argv` does not
   appear between the `def cmd_record_attempt` line and the start of the next top-level
   `@flex_build.command` decorator). The forwarded argv is built from the variadic argument
   tuple only.

3. The forwarded command remains `[sys.executable, <scripts_dir>/record_attempt.py, *args]`
   executed via `subprocess.run(..., check=False)` with **no** `shell=True`, and the alias
   exits with the child's `returncode`.

4. **Full-flag round-trip (the CER-073 acceptance test).** Invoking the alias as a subprocess
   in a `tmp_path` project whose `.companion/state.json` contains `{"effort_tracking": true}`,
   with the full documented flag set —
   `--project-dir`, `--story-id`, `--phase`, `--rail`, `--agent-role`, `--model`,
   `--attempt-number`, `--tokens-total`, `--tokens-in`, `--tokens-out`,
   `--cache-read-tokens`, `--cache-write-tokens`, `--tool-uses`, `--duration-ms`,
   `--outcome`, `--notes`, `--story-class`, `--model-selection-reason`, `--ts`, `--db-path`
   — exits 0, and `effort_db.query_by_story(db_path, story_id)` returns exactly one row whose
   `phase`, `rail`, `model`, `tokens_total`, `tokens_in`, `tokens_out`,
   `cache_read_tokens`, `cache_write_tokens`, `tool_uses`, `duration_ms`, `outcome`, `notes`,
   `story_class`, `model_selection_reason` and `ts` equal the values passed on the command
   line.

5. **The exact reproducer from recon passes.** `record-attempt --project-dir <tmp> --story-id
   INFRA-263 --agent-role builder` exits 0 and its combined output does not contain
   `No such option`.

6. **`--story-file` forwarding works**, proving the delegate's `click.Path(exists=True)`
   options resolve against the inherited cwd: given a story file on disk with `id`, `phase`,
   `rail`, `story_class` frontmatter, `record-attempt --project-dir <tmp> --story-file <path>
   --agent-role builder` exits 0 and the written row's `story_id` matches the file's
   frontmatter `id`.

7. **`--help` is forwarded, not answered locally.** `record-attempt --help` exits 0 and its
   stdout contains `--story-id`, `--agent-role` and `--usage-block` (i.e. it is
   `record_attempt.py`'s help, not the alias's empty option list).

8. **Delegate errors surface unchanged, with the delegate's exit code.** Omitting the
   delegate's required option (`record-attempt --project-dir <tmp> --story-id X`, no
   `--agent-role`) exits 2 and the output contains `--agent-role`; a bogus flag
   (`--no-such-flag`) exits 2 with the delegate's `No such option: --no-such-flag`, produced
   by `record_attempt.py` (output mentions `record_attempt.py`, not
   `flex_build.py record-attempt`).

9. **No regression to the group surface.** `flex_build.py --help` exits 0 and still lists
   `record-attempt` in its command list.

10. `tests/pairmode/test_flex_build_record_attempt_alias.py` exists and contains named tests
    covering Ensures 4, 5, 6, 7, 8 and 9 — one test per assertion, each invoking the CLI as a
    real subprocess (not `CliRunner`), so the argv path under test is the one downstream
    orchestrators actually exercise.

11. `docs/cer/backlog.md`: **both** CER-071 and CER-073 Finding cells end with a bold
    `**RESOLVED Phase 104 — INFRA-263 …**` note naming `cmd_record_attempt` in
    `skills/pairmode/scripts/flex_build.py`, the `ignore_unknown_options` + variadic-passthrough
    fix, and the new test file; and both rows' `Phase` column contains `104`. Neither row is
    deleted or moved out of its section (the backlog is append/annotate-only). CER-073's note
    additionally states that it is a duplicate filing of CER-071 and that both closed together.

12. `CHANGELOG.md` has an entry in the top-most unreleased/pairmode section naming INFRA-263,
    CER-071 and CER-073, stating that `flex_build.py record-attempt` now forwards its full
    option set (previously exited 2 on every documented invocation) and that
    `record-attempt --help` now shows `record_attempt.py`'s options. It flags the change as
    fixing a downstream-facing defect.

13. `docs/architecture.md`'s flex_build.py CLI-surface paragraph (line ~56, the clause reading
    "record-attempt added in RELEASE-009 (HARNESS012-main) — Click alias delegating to
    record_attempt.py, so the orchestrator template can call a single entry point") is amended
    in place to state that the alias is a **transparent passthrough**: it declares no options
    of its own, forwards all arguments including `--help` to `record_attempt.py`, and exits
    with the delegate's exit code (INFRA-263). No other section of architecture.md is changed.

14. `tests/pairmode/` passes (run without `-x`; the known pre-existing
    `test_observability_ui.py::test_ui_build_emits_dist_index_html` failure is acceptable only
    if it reproduces on clean HEAD).

## Instructions

1. **Rewrite the alias declaration** in `skills/pairmode/scripts/flex_build.py` (~line 2338).
   Target shape:

   ```python
   @flex_build.command(
       "record-attempt",
       context_settings={"ignore_unknown_options": True},
       add_help_option=False,
   )
   @click.argument("args", nargs=-1, type=click.UNPROCESSED)
   def cmd_record_attempt(args: tuple[str, ...]) -> None:
   ```

   Drop `@click.pass_context` and the `**kwargs: object` signature — neither is used once the
   variadic argument exists. The three pieces are jointly load-bearing and none is optional:
   `ignore_unknown_options` stops Click erroring on `--story-id`; `type=click.UNPROCESSED`
   stops Click from applying any conversion/`-`-prefix heuristics to the collected tokens;
   `add_help_option=False` is what lets `--help` reach the delegate (Ensures 7) instead of
   being intercepted by Click's auto-added option.

2. **Replace the `sys.argv` slice with the argument tuple.** The body becomes:

   ```python
   result = subprocess.run(
       [sys.executable, str(record_script), *args],
       check=False,
   )
   sys.exit(result.returncode)
   ```

   Keep `import subprocess  # noqa: PLC0415` local and keep resolving
   `record_script = Path(__file__).parent / "record_attempt.py"` exactly as today — the
   sibling-path resolution is not the defect. Do not add `shell=True`, do not join into a
   string, and do not set `PYTHONPATH` (recon confirms `record_attempt.py` self-inserts its
   import paths).

3. **Update the docstring.** State that the command is a transparent passthrough: no options
   of its own, `ignore_unknown_options` + `UNPROCESSED` variadic, `--help` forwarded to the
   delegate, exit code propagated. Reference `RELEASE-009` (origin) **and** `INFRA-263
   (CER-071, CER-073)`, and add a one-line warning that adding any `@click.option` to this
   command would re-introduce the defect — that comment is the guard against a future "tidy-up"
   reverting the fix.

4. **Do not add a `--` separator requirement.** Callers must be able to write
   `record-attempt --story-id X ...` verbatim as documented; a form that only works as
   `record-attempt -- --story-id X` does not satisfy Ensures 5 and would leave every existing
   doc reference wrong.

5. **New test file `tests/pairmode/test_flex_build_record_attempt_alias.py`.** Follow the
   subprocess pattern in `tests/pairmode/test_flex_build_attempt_counter.py` (module-level
   `_REPO_ROOT` / `_SCRIPT`, a `_run(*args)` helper using
   `subprocess.run([sys.executable, str(_SCRIPT), *args], capture_output=True, text=True,
   env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)})`). Use a real subprocess rather than
   `CliRunner` deliberately: `CliRunner` would exercise the parser but not the delegation, and
   the delegation is the half that was already correct. For the project fixture, mirror
   `tests/pairmode/test_record_attempt.py::_enable_tracking` — write
   `tmp_path/.companion/state.json` containing `{"effort_tracking": true}` (the `.companion/`
   directory also satisfies the depth guard used elsewhere in flex_build). Read rows back with
   `from skills.pairmode.scripts import effort_db` → `effort_db.query_by_story(db_path, story_id)`.
   Write one test per Ensures 4-9, named for the assertion (e.g.
   `test_full_flag_set_round_trips_through_alias`,
   `test_reproducer_from_cer_073_exits_zero`, `test_story_file_flag_is_forwarded`,
   `test_help_is_forwarded_to_delegate`, `test_delegate_errors_propagate_exit_code`,
   `test_group_help_still_lists_record_attempt`). Assert on exit codes and DB contents, and in
   the negative cases assert on substrings of `stdout + stderr` (Click writes usage errors to
   stderr).

6. **Assert the absence of the old bug, not just the presence of the new behaviour.** In at
   least one test, include a case that would have passed under the `sys.argv.index` slice but
   is wrong: forward `--notes record-attempt` and assert the stored `notes` is exactly
   `record-attempt` and every later flag still landed (this pins the argument-truncation LOW
   from RELEASE-009's security audit closed).

7. **Annotate both CER rows** in `docs/cer/backlog.md`. Append a bold `**RESOLVED Phase 104 —
   INFRA-263 …**` sentence to the end of each Finding cell and set each row's `Phase` column
   to `104`, following the in-file precedent (e.g. CER-072's `**RESOLVED Phase 97 — INFRA-230
   …**`). Both rows stay in Do Later where they are — the backlog is annotate-only, findings
   are never deleted or relocated. CER-071's note should also record that its "root cause not
   yet diagnosed" line is now answered: the declaration was empty, not narrow.

8. **Docs and changelog.** Amend the single architecture.md clause named in Ensures 13 in place
   — add one sentence to the existing `record-attempt` clause; do not restructure the CLI-surface
   paragraph or touch any other section. Add the `CHANGELOG.md` entry of Ensures 12 to the
   top-most pairmode section, following the style of neighbouring entries.

9. **Ideology alignment (Step 4a, checked):** no conflict found, and one constraint is actively
   served. `Never silently pass contradictions` — today the alias fails *loudly* but at the
   wrong layer, and the failure is invisible to flex's own green suite because flex records via
   `subagent_transcript` instead of this CLI; the new tests move the contract into the suite so
   the documented surface and the executable surface cannot diverge again. `Hooks are thin
   relays only` and `Sidebar owns all state writes` are untouched: no hook is modified, and the
   alias remains a pure argv relay that performs no writes of its own — `record_attempt.py`
   stays the sole writer of `effort.db`. One adjustment worth naming: the fix deliberately keeps
   the alias a *passthrough* rather than re-declaring `record_attempt.py`'s ~20 options on the
   alias (which would also make the documented invocations work). Duplicating the option set
   would create a second, drift-prone definition of the same contract and violate the
   single-source conviction that `codifying policy over implicit convention` protects — every
   future flag added to `record_attempt.py` would silently be rejected by the alias until
   someone remembered to mirror it. Passthrough makes drift structurally impossible.

10. **Spec-preflight note.** `spec-preflight` flags `UNPROCESSED` as an unresolvable constant.
    That is a false positive and is intentional: `click.UNPROCESSED` is a Click library
    constant, not a flex-defined one, so it has no definition in this source tree.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build_record_attempt_alias.py -q 2>&1 | tail -30
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_record_attempt.py tests/pairmode/test_pairmode_sync.py tests/pairmode/test_flex_build.py -q 2>&1 | tail -30
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -30
```

Acceptance:

- The new alias test file is green, with every case in Ensures 4-9 present and passing.
- The three adjacent files (delegate tests, template-sync tests, the main flex_build suite) are
  green — the alias change must not disturb `test_pairmode_sync.py`'s
  `test_rendered_template_record_attempt_uses_absolute_path`.
- Full `tests/pairmode/` run (deliberately **without** `-x`, so a real failure is not masked by
  the known one) shows no new failures; only
  `test_observability_ui.py::test_ui_build_emits_dist_index_html` may fail, and only if it
  reproduces on clean HEAD.
- Manual confirmation recorded in Build notes — the recon reproducer, now passing:

  ```bash
  mkdir -p /tmp/ra-check/.companion
  printf '{"effort_tracking": true}' > /tmp/ra-check/.companion/state.json
  PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
    record-attempt --project-dir /tmp/ra-check --story-id INFRA-263 \
    --agent-role builder --attempt-number 1 --outcome PASS
  PATH=$HOME/.local/bin:$PATH uv run python skills/pairmode/scripts/flex_build.py \
    record-attempt --help | head -5
  ```

  The first prints `recorded attempt for INFRA-263 (agent=builder, attempt=1)` and exits 0;
  the second prints `record_attempt.py`'s usage line and option list.

## Out of scope

- **Re-declaring `record_attempt.py`'s option set on the alias.** Rejected in Instructions 9;
  the alias stays a passthrough.
- **Any change to `record_attempt.py` itself** — its CLI, its frontmatter auto-fill, its
  `effort_db` writes, and the four async recording defects are all untouched here. The async
  recording defects belong to INFRA-264 (CER-091); effort-DB hardening belongs to INFRA-266
  (CER-088/089/016). If the alias tests surface a delegate-side bug, file it, do not fix it in
  this story.
- **Auditing flex_build.py's other alias commands** (`create-story-worktree`,
  `merge-story-worktree`, `discard-story-worktree`, …). CER-071 notes they work as documented;
  they declare their own options and call Python functions in-process rather than delegating to
  a sibling script, so they are a different shape and not affected. A general
  passthrough-alias helper is not introduced — `record-attempt` is the only delegating alias.
- **Re-wiring flex's own build loop to call this CLI.** `CLAUDE.build.md` records via
  `subagent_transcript.record_attempt_from_transcript()`; whether the loop should call the CLI
  instead is an INFRA-237-adjacent question, not this story's.
- **`CLAUDE.build.md.j2` / template changes.** The rendered template no longer contains a
  `record-attempt` CLI line (verified by grep), so no template edit is needed; the existing
  `test_pairmode_sync.py` absolute-path assertion is left exactly as it is.
- **Rewriting the doc references** in `docs/agreements/HARNESS006-main.md:71` and
  `docs/stories/INFRA/INFRA-224.md:143`. Those are historical records and, after this fix, they
  are correct as written — the whole point is that the documented invocation now works.
- **The effort-tracking-disabled path.** Whether `record_attempt.py` should print something
  louder when `effort_tracking` is false is a delegate concern, unchanged here.
