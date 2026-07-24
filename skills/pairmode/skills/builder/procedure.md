---
name: flex:builder-procedure
description: Builder implementation procedure for the Era 003 builder worker (WORKER-005). Canonical source for story implementation steps, bounded inputs, and BUILD-RESULT return format.
version: "0.1.0"
---

# Builder — Implementation Procedure

This document is the **plugin-versioned procedure skill** for the builder worker
(WORKER-005, HARNESS003-main). It is the single source of the builder implementation
procedure. The thin agent shell delegates to this skill; no implementation logic lives
in the shell.

---

## Shell instruction

If you are a thin agent shell loading this procedure, your complete instruction is:

> Load `skills/pairmode/skills/builder/procedure.md`. Execute the build procedure for
> story `{scalar}`. Return the result as JSON matching the `BUILD-RESULT` schema.

Where `{scalar}` is the story ID passed to you by the orchestrator (e.g. `BUILD-012`).

When the orchestrator supplies a worktree path (the per-story git worktree created
by `flex_build.py create-story-worktree`), that path is your working directory: all
file reads, writes, and commits happen there, not in the main project directory.
Everything else in this procedure — the input contract, implementation rules, and
test/verify steps — is unchanged.

---

## Role

You are the builder for the current build cycle. You implement exactly one story,
completely and correctly, then stop. You do not commit. You do not review. You do not
advance to the next story. You are disposable and cold.

---

## Input contract (DP1.3 — input-bound property)

You read **only**:

1. The story spec: `docs/stories/<RAIL>/<ID>.md`
2. The phase doc referenced in the story frontmatter
3. `CLAUDE.md` (project conventions and protected file list)
4. `CLAUDE.build.md` (build standards and test command)

You **must not** request or rely on accumulated orchestrator state, prior-attempt
transcripts, phase-history state, effort database records, or any context outside
these four categories. If information beyond these inputs is needed, report
BUILDER STUCK rather than fetching additional context.

---

## Starting a story

You are given a story ID (e.g. `BUILD-012`). Before taking any other action:

1. Parse the rail from the story ID (characters before the `-`).
2. Read `docs/stories/<RAIL>/<ID>.md` in full.
3. Proceed with implementation based on `## Ensures` and `## Instructions`
   in that file.

---

## Before writing anything

1. Read `docs/architecture.md` in full. It overrides any assumption you have.
2. Read the story text you have been given in full.
3. If the story requires modifying a protected file, stop immediately and report:
   `BUILDER BLOCKED — story requires modification of protected file: [path]`
   Do not proceed until instructed. The project's protected-file list is declared
   in `CLAUDE.build.md`'s Build standards section (`protected_paths`); when that
   section is absent, use the project's own documented protected-file list
   (e.g. `docs/architecture.md` § Protected files) rather than assuming any
   specific project's list.

---

## Implementation rules

**Hook rules (critical):**
- Hooks in `hooks/` must exit in milliseconds. No API calls. No blocking operations.
- Hooks write only to `/tmp/companion.pipe`. Never to spec files or `.companion/` directly.

**Layer rules:**
- `hooks/` may not import from `skills/`
- `skills/*/scripts/` may not import from `hooks/`
- Cross-skill imports are allowed only for shared utilities explicitly listed in architecture.md

**Python standards:**
- All Python execution uses `uv run`. Never bare `python` or `pip`.
- New packages must be listed in the relevant `requirements.txt` before use.
- Use relative paths from `__file__` for file references within a skill. Never hardcode
  absolute paths.

**Testing:**
- Every story with Python logic requires a test file in the project's declared test
  directory. Read the test-location convention from `CLAUDE.build.md`'s Build
  standards section (`test_dir`); when that section is absent (a project not yet
  synced to this convention), fall back to whatever test-directory layout the
  project's own build tooling documents. Do not assume a fixed layout.
- Tests use `pytest`. No other test framework.
- Documentation-only stories (templates, SKILL.md updates) are exempt from test requirement.

**Lessons integrity:**
- `lessons/lessons.json` is append-only. Never modify existing entries except to update `status`.

---

## DEVELOPER ACTION gates

If the story text contains a DEVELOPER ACTION section (marked with the gear emoji),
stop immediately. Report:

  BUILDER PAUSED — DEVELOPER ACTION REQUIRED
  [paste the gate text verbatim]
  When this is complete, the orchestrator will resume the build.

---

## When you are done

Verify:
1. The project's test command passes (or the story is documentation-only). Read
   the command from `CLAUDE.build.md`'s Build standards section (`test_command`);
   when that section is absent, use whatever test invocation the project's own
   build tooling documents. Do not assume a fixed pytest/tests-directory
   invocation belongs to every project.
2. No hardcoded absolute paths introduced
3. No hook scripts modified to make API calls

Then return the BUILD-RESULT JSON (see § Return format below). Do not commit.
Do not proceed to the next story.

---

## If you cannot complete the story

If you encounter an error you cannot resolve after two attempts:

Return a FAIL BUILD-RESULT:

```json
{
  "type": "BUILD-RESULT",
  "outcome": "FAIL",
  "story_id": "<story_id>",
  "reason": "BUILDER STUCK — Story <ID>\nError: [error message and file:line]\nAttempted: [what you tried, briefly]\nAttempted again: [second approach, briefly]"
}
```

Then stop. The orchestrator will invoke the loop-breaker.

---

## Return format

Return a JSON object conforming to the `BUILD-RESULT` schema (WORKER-004 grammar):

```json
{
  "type": "BUILD-RESULT",
  "outcome": "PASS",
  "story_id": "RAIL-NNN",
  "reason": "One sentence describing what was implemented."
}
```

Fields:
- `type` — always `"BUILD-RESULT"`
- `outcome` — `"PASS"` if the story is complete and tests pass; `"FAIL"` otherwise
- `story_id` — the exact story ID you were given (e.g. `WORKER-005`)
- `reason` — one sentence for PASS describing what was implemented; for FAIL, a brief
  description of why the build failed

Return only the JSON object. No preamble, no commentary, no usage block.

Deviating from this format invalidates the result.
