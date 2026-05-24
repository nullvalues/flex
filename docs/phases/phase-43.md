# flex — Phase 43: Replace DB-based context budget gate with orchestrator context check

← [Phase 42: Context budget session-relative token tracking](phase-42.md)

## Goal

The context budget gate in Phase 39 was built to prevent context overrun by summing
tokens from the effort DB and comparing against a threshold. Phase 42 added
session-relative tracking to fix the re-fire-after-clear false positive.

Both fixes addressed symptoms of the wrong design: the effort DB records token spend
for **analysis and reporting**, not for runtime context monitoring. Claude already
knows its own context state. The check should use that directly — compare the
current context window token count against the configured threshold, and halt with a
resume prompt if over. No DB query, no session-start tracking, no script invocation
in the build loop.

The `context_budget_check.py` script remains as an external analysis tool (not
removed). The session-start tracking added in INFRA-110/111 is dead code once the
loop no longer invokes the script — it is stripped.

**Two stories:**

| ID | Title | Status |
|----|-------|--------|
| INFRA-112 | Replace script-based context budget check in `CLAUDE.build.md.j2` with orchestrator context check | planned |
| INFRA-113 | Remove session-start tracking from `context_budget_check.py` | planned |

**Story dependencies:** independent; may be built in parallel.

---

## Stories

### Story INFRA-112 — Replace script-based context budget check in `CLAUDE.build.md.j2` with orchestrator context check

**Rail:** INFRA | **story_class:** methodology

#### Requires

- `skills/pairmode/templates/CLAUDE.build.md.j2` contains:
  - A "Record session start" block (lines ~143–162) with the Python snippet that
    writes `context_budget_session_start` to state.json.
  - A `## Context budget check (between stories)` section that invokes
    `context_budget_check.py` via bash and branches on exit code.
- `CLAUDE.build.md` mirrors the same two blocks.

#### Ensures

**`skills/pairmode/templates/CLAUDE.build.md.j2`**

1. The "Record session start" block (the `**Record session start** (once per build
   session…)` paragraph, its bash snippet, and the "On resume after a `/clear`"
   sentence) is **removed entirely** from the build loop preamble.

2. The `## Context budget check (between stories)` section is **replaced** with the
   following natural-language instruction (no bash invocation, no exit-code branching):

   ```
   ## Context budget check (between stories)

   After every story's PASS or FAIL handling completes — before advancing to the
   next story or entering the checkpoint sequence:

   1. Read `context_budget_threshold` from `.companion/state.json`
      (default: 120 000 if absent or unset).
   2. Compare your current context window token count against the threshold.
      Your context token count is visible in Claude Code via `/context`.
   3. If your context is **at or above** the threshold, surface the following
      prompt **verbatim** — do not add editorial commentary, reasoning, or a
      recommendation. Wait for user response before spawning the next builder
      or entering the checkpoint sequence.

      CONTEXT BUDGET — [story RAIL-NNN] just completed.
      Context is at approximately [N] tokens (threshold: [T]).

      Continuing risks context compaction mid-story. Options:

      1. **Proceed** — continue building in this session; budget acknowledged.
         Say: "Continue building"

      2. **Clear and resume** — run /clear, then in the fresh session:
         Say: "Continue building Phase X from story RAIL-NNN"

   4. If below the threshold: proceed normally.
   ```

3. No other sections are modified.

**`CLAUDE.build.md`** (flex's own)

Apply the identical two changes directly — no `pairmode_sync sync-build`.

#### Instructions

**`skills/pairmode/templates/CLAUDE.build.md.j2`**

- Delete the "Record session start" block. It begins with
  `**Record session start** (once per build session, before the first builder):`
  and ends with the "On resume after a `/clear`" sentence (including the blank
  line that follows). The next heading after deletion is `### Pre-story schema gate`.

- Replace the entire `## Context budget check (between stories)` section — from
  that heading through the final `- Exit 2 (IO error): …` line and the trailing
  `---` divider — with the new natural-language block from Ensures #2. Preserve
  the trailing `---` divider.

**`CLAUDE.build.md`**

Apply the same two deletions/replacements directly. Verify the file matches the
template output for these sections.

#### Tests

No test file expected for this methodology story.

The reviewer verifies:
1. `CLAUDE.build.md.j2` does **not** contain `context_budget_session_start`.
2. `CLAUDE.build.md.j2` does **not** contain a bash invocation of
   `context_budget_check.py`.
3. `CLAUDE.build.md.j2` contains `## Context budget check (between stories)` with
   the `/context` reference and the four-step natural-language instruction.
4. `CLAUDE.build.md` mirrors all changes (same two absences, same new section).
5. Full test suite passes: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.

`TEST RUN: methodology story — no test file expected`

---

### Story INFRA-113 — Remove session-start tracking from `context_budget_check.py`

**Rail:** INFRA | **story_class:** code

#### Requires

- `skills/pairmode/scripts/context_budget_check.py` contains:
  - `_load_session_start_from_state(project_dir: Path) -> str | None`
  - `since: str | None = None` param on `_sum_tokens_for_phase`
  - `--since` argparse argument
  - `since=` field in the stdout line
- `tests/pairmode/test_context_budget_check.py` has 9 tests, including tests 7–9
  that cover session-start behaviour, and `_create_db` accepts an optional `ts` param.

#### Ensures

**`skills/pairmode/scripts/context_budget_check.py`**

1. `_load_session_start_from_state` is **removed**.

2. `_sum_tokens_for_phase(db_path, phase)` signature reverts to no `since` param.
   The body uses only the cumulative query:
   ```python
   cur.execute(
       "SELECT COALESCE(SUM(COALESCE(tokens_total, 0)), 0) FROM attempts WHERE phase = ?",
       (phase,),
   )
   ```

3. The `--since` argparse argument is **removed**.

4. The `since` resolution block in `main()` (the `if args.since … else … _load_session_start_from_state` lines) is **removed**.

5. The stdout line reverts to:
   `context_budget phase=<p> tokens=<t> threshold=<n> status=<ok|over>`
   (no `since=` field).

6. The module docstring and all remaining behaviour (exit codes 0/1/2, threshold
   priority, DB resolution, `--threshold` arg, `--project-dir` arg) are
   preserved unchanged.

**`tests/pairmode/test_context_budget_check.py`**

7. Tests 7 (`test_session_start_excludes_pre_session_tokens`), 8
   (`test_since_arg_overrides_state_session_start`), and 9
   (`test_missing_session_start_falls_back_to_cumulative`) are **removed**.
   The file returns to 6 tests.

8. The `_create_db` helper reverts to its pre-Phase-42 signature — no `ts`
   parameter. Its INSERT uses a fixed timestamp constant (any valid ISO-8601
   value; e.g. `"2026-01-01T00:00:00+00:00"`).

9. Tests 1–6 are preserved unchanged in behaviour (they may require trivial
   updates if they passed `ts` explicitly — remove those call-site arguments
   if so).

#### Instructions

**`skills/pairmode/scripts/context_budget_check.py`**

1. Delete the `_load_session_start_from_state` function in full.
2. Remove the `since: str | None = None` parameter from `_sum_tokens_for_phase`
   and collapse the body to the single cumulative `cur.execute` call.
3. Remove the `--since` `add_argument` block from the parser.
4. Remove the `since` resolution block from `main()` (the `if args.since …`
   block and the `since_label` / `since=` parts of the print statement).
5. Update the stdout `print` to omit the `since=` field.
6. Verify the module docstring no longer mentions `--since` or session-start.

**`tests/pairmode/test_context_budget_check.py`**

1. Delete test functions 7, 8, 9.
2. Revert `_create_db`: remove the `ts` parameter, hardcode a constant timestamp
   in the INSERT.
3. Remove any `ts=…` keyword arguments from calls to `_create_db` in tests 1–6
   if they were added.

#### Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_context_budget_check.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Exactly 6 tests in `test_context_budget_check.py` must pass. Full suite must pass.

---

Tag: `cp43-orchestrator-context-check`
