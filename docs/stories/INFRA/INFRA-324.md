---
id: INFRA-324
rail: INFRA
title: Bash dispatch/allowlist for reviewer subagent git commands (reviewer FAIL-path improvisation gap)
status: draft
phase: "114"
story_class: code
auth_gated: false
schema_introduces: false
touches:
  - hooks/pre_tool_use.py
  - hooks/hooks.json
  - skills/pairmode/scripts/reviewer_bash_guard.py
  - skills/pairmode/skills/reviewer/procedure.md
  - tests/pairmode/test_reviewer_bash_guard.py
  - tests/pairmode/test_pre_tool_use_hook.py
  - docs/architecture.md
  - docs/phases/phase-114.md
  - docs/stories/INFRA/INFRA-324.md
  - skills/pairmode/skills/security-auditor/procedure.md
---

<!-- SPEC-WRITER NOTE (frontmatter): `touches:` is block-style per CER-115 —
     flow-style `[a, b]` parses as a string and crashes
     create-story-worktree's `generate_permissions_artifact`. `hooks/**` is a
     PROTECTED path (`scope_guard.PROTECTED_GLOBS`, `scope_guard.py:32-40`)
     and is therefore satisfiable only via this explicit declaration plus a
     valid permissions artifact (INFRA-253) — deliberate, not an oversight.
     `docs/cer/backlog.md` is NOT touched: this story was routed directly
     into phase 114 by explicit operator instruction on 2026-07-29, not
     pulled from an existing CER backlog row (no CER filed for this finding). -->

## Context

An operator-run investigation into another project ("ddi") surfaced a real
finding about this repo's own reviewer procedure while triaging an unrelated
report. During a DESIGN-002 story review, the reviewer subagent — on its own
initiative, on a FAIL verdict — attempted `git reset --hard main` and a
`git revert` inside the story worktree. Neither command is sanctioned by the
reviewer procedure; the sandbox blocked both attempts, so nothing was lost.

Investigation (2026-07-29) confirmed the following:

1. `skills/pairmode/skills/reviewer/procedure.md`'s "On FAIL, revert" section
   (around line 511-527) sanctions exactly two commands, scoped to the
   story's declared `primary_files`/`touches`: `git checkout -- <path>` and
   `git clean -fd -- <path>`, with a whole-tree `git checkout .` /
   `git clean -fd` fallback reserved for legacy stories with no declared
   scope. `git reset --hard <ref>` and `git revert` are never sanctioned
   anywhere in the procedure. The reviewer improvised something more
   aggressive than its own documented contract.

2. INFRA-223 (`docs/stories/INFRA/INFRA-223.md`) deliberately narrowed the
   FAIL-path revert from a blanket `git checkout . && git clean -fd` after
   that exact command deleted untracked content in an earlier incident
   (RELEASE-022) — and its own text already names the structural gap this
   story closes: "The reviewer is an LLM following prose, not a shell
   script." That gap was never closed.

3. `hooks/pre_tool_use.py` is a thin dispatcher with branches for
   `Task`/`Agent` (→ `context_budget.py`), `Edit`/`Write` (→
   `scope_guard.py`), and `Read` (→ `cold_read_guard.py`). There is no
   `Bash` branch at all (confirmed by reading the full `main()` function,
   `hooks/pre_tool_use.py:115-219`). Nothing enforces which git subcommands
   a reviewer (or any) subagent may run — the only thing standing between
   "reviewer decides to run `git reset --hard main`" and it actually
   happening is the ambient sandbox/permission layer, which flex does not
   own or control.

4. Blast radius is bounded by unrelated, already-shipped isolation
   (INFRA-224): the orchestrator's `discard-story-worktree`
   (`skills/pairmode/scripts/flex_build.py`, around line 4028+, called on
   every reviewer FAIL per `CLAUDE.build.md`'s build loop) runs
   `git worktree remove --force` then `git branch -D` unconditionally,
   wiping the entire disposable worktree and branch regardless of what the
   reviewer did inside it. A reviewer running `git reset --hard main` or
   `git revert` could therefore only ever have damaged the disposable
   worktree/branch about to be discarded anyway — never the main tree. This
   story closes the enforcement gap defensively; it is not a response to
   any actual data loss.

The `hooks/pre_tool_use.py` payload already carries `agent_type` for
subagent-issued tool calls (used today by the `Read` branch's
`cold_read_guard.check_path(agent_type=...)` call) — the same field is
available for a new `Bash` branch to identify reviewer-issued commands.

5. **Scope widened mid-build (2026-07-30):** a builder attempted this story
   as originally scoped (guard module + `pre_tool_use.py` dispatch branch
   only) and hit BUILDER BLOCKED. The dispatch branch was built correctly,
   but `hooks/hooks.json`'s `PreToolUse` array has no matcher entry for
   `Bash` — only `Task|Agent`, `Edit|Write`, and `Read` are registered
   (`hooks/hooks.json:26-57`) — so the new branch is unreachable dead code
   in production; `pre_tool_use.py` is never invoked for a `Bash` tool call
   at all. `hooks/hooks.json` is a PROTECTED path
   (`scope_guard.PROTECTED_GLOBS`) and was not declared in this story's
   original `touches:`, so the builder correctly refused to edit it and
   stopped rather than improvising. The operator reviewed the finding and
   explicitly approved widening this story's scope to include
   `hooks/hooks.json`, so the guard is wired in and live in the same story
   rather than deferred to a follow-up story. See `touches:` and the new
   `Bash` matcher requirements in Ensures/Instructions below.

## Requires

- `hooks/pre_tool_use.py`'s existing `Read` branch pattern (dispatch by
  `tool_name`, read `agent_type` from the payload) as the model for the new
  `Bash` branch.
- `skills/pairmode/scripts/scope_guard.py`'s `check_path(...) -> (allowed,
  reason)` signature and fail-open-on-error convention as the model for the
  new module's `check_command(...) -> (allowed, reason)` signature.
- `skills/pairmode/skills/reviewer/procedure.md`'s existing "On FAIL,
  revert" sanctioned command set (the two scoped forms + the legacy
  whole-tree fallback) as the authoritative allowlist source — do not
  invent a different allowlist than what the procedure already documents.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| skills/pairmode/skills/security-auditor/procedure.md | test_hook_delegations_are_documented_exceptions requires reviewer_bash_guard named in the security-auditor exception block for the new Bash dispatch branch | 2026-07-31T03:13:18Z |

## Ensures

- A new module `skills/pairmode/scripts/reviewer_bash_guard.py` exists,
  exporting `check_command(command: str, agent_type: str | None) -> tuple[bool, str]`.
- `check_command` returns `(True, ...)` immediately (fails open, no
  inspection) whenever `agent_type != "reviewer"` — this guard governs the
  reviewer role only, per this story's scope; it must never gate a builder,
  loop-breaker, security-auditor, or orchestrator-issued Bash call.
- For `agent_type == "reviewer"`, `check_command` parses whether `command`
  invokes `git` and, if so, which subcommand. Non-git commands always pass
  (`True`).
- Allowlisted git subcommands/forms for the reviewer role: `git checkout --
  <path>` (or whole-tree `git checkout .` fallback), `git clean -fd --
  <path>` (or whole-tree `git clean -fd` fallback), `git add`, `git commit`,
  `git diff`, `git status`, `git log`. Each returns `(True, ...)`.
- Blocked git subcommands/forms for the reviewer role: `git reset` (any
  form, including `--hard`), `git revert`, `git rebase`, `git push`, `git
  branch -D` / `git branch --delete --force`, and any invocation carrying a
  bare `--force` or `-f` flag that isn't one of the two sanctioned `git
  clean -fd` forms above. Each returns `(False, reason)` with a reason
  string naming the blocked subcommand and pointing at
  `discard-story-worktree` as the correct mechanism for a full revert.
- `hooks/pre_tool_use.py` gains a new `elif tool_name == "Bash":` branch
  (added to the existing `Task`/`Agent` → `Edit`/`Write` → `Read` chain,
  same fail-open-on-import/exception style as the other branches) that
  calls `reviewer_bash_guard.check_command(command=..., agent_type=...)`
  and, on `allowed is False`, prints the existing
  `{"decision": "block", "reason": reason}` JSON and exits 0 — matching the
  exact block-response shape the `Edit`/`Write` and `Read` branches already
  use.
- `skills/pairmode/skills/reviewer/procedure.md`'s "On FAIL, revert"
  section gains one sentence noting that the sanctioned command set above
  is now enforced by `hooks/pre_tool_use.py`'s `Bash` dispatch, not prose
  alone — cross-referencing this story.
- `docs/architecture.md`'s hook-dispatch description (wherever
  `hooks/pre_tool_use.py`'s branches are currently documented) is updated
  to list the new `Bash` branch alongside the existing three.
- `tests/pairmode/test_reviewer_bash_guard.py` exists and covers: each
  allowlisted form returns `True`; each blocked subcommand returns `False`
  with a non-empty reason; a non-`"reviewer"` `agent_type` (including
  `None`) always returns `True` regardless of command content; a non-git
  command always returns `True`.
- `tests/pairmode/test_pre_tool_use_hook.py` gains at least one test
  exercising the new `Bash` branch end-to-end (payload with
  `tool_name="Bash"`, `agent_type="reviewer"`, a blocked command → hook
  prints a block decision; an allowed command or non-reviewer `agent_type`
  → hook exits 0 with no block decision printed).
- No existing test in `tests/pairmode/` regresses (full suite run without
  `-x`, per this project's pytest-no-x-before-merge convention).
- `hooks/hooks.json`'s `PreToolUse` array gains a new matcher entry for
  `Bash`, appended after the existing `Read` entry
  (`hooks/hooks.json:47-56`), following the exact same shape as the other
  three `PreToolUse` entries: `{"matcher": "Bash", "hooks": [{"type":
  "command", "command": "python3
  ${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py", "timeout": 5}]}` — same
  script invocation, same `"type": "command"`, same `timeout: 5` as
  `Task|Agent`, `Edit|Write`, and `Read`. Without this entry the new `Bash`
  dispatch branch in `hooks/pre_tool_use.py` is never invoked and the guard
  does not run in production — this is the entry that closes the gap
  discovered mid-build (see Context, item 5).

## Instructions

1. Read `skills/pairmode/scripts/scope_guard.py` and
   `skills/pairmode/scripts/cold_read_guard.py` in full for the established
   `check_*(...)  -> (allowed, reason)` module pattern (fail-open on
   exception, plain functions, no classes) before writing the new module.
2. Read `skills/pairmode/skills/reviewer/procedure.md`'s full "On FAIL,
   revert" section (search for that heading) to pull the exact sanctioned
   command forms verbatim — do not paraphrase or invent a different
   allowlist.
3. Write `skills/pairmode/scripts/reviewer_bash_guard.py` implementing
   `check_command` per the Ensures above. Parse the command defensively
   (e.g. tokenize and look for a `git` invocation and its first
   non-flag argument as the subcommand) — do not attempt full shell
   parsing; a reasonable, well-tested heuristic is sufficient given this is
   a defense-in-depth guard behind the sandbox, not the sole line of
   defense.
4. Add the `Bash` branch to `hooks/pre_tool_use.py`, matching the existing
   branches' style (import inside a `try`/`except`, fail open on any
   exception, same block-response JSON shape). Update the module docstring
   at the top of the file (which currently lists Task/Agent, Edit/Write,
   Read) to mention the new Bash branch.
5. Add the cross-reference sentence to
   `skills/pairmode/skills/reviewer/procedure.md`'s "On FAIL, revert"
   section.
6. Update `docs/architecture.md` wherever the hook-dispatch contract is
   documented.
7. Write `tests/pairmode/test_reviewer_bash_guard.py` and extend
   `tests/pairmode/test_pre_tool_use_hook.py` per the Ensures above.
8. Add the `Bash` matcher entry to `hooks/hooks.json`'s `PreToolUse` array
   per the Ensures above — mirror the existing `Task|Agent`, `Edit|Write`,
   and `Read` entries exactly (same `command`/`type`/`timeout` shape),
   appending it after the `Read` entry so `hooks/pre_tool_use.py`'s new
   `Bash` branch is actually reachable in production.
9. Run `uv run pytest tests/pairmode/ -q` (no `-x`) and confirm no
   regressions.

## Tests

`uv run pytest tests/pairmode/test_reviewer_bash_guard.py
tests/pairmode/test_pre_tool_use_hook.py -q` plus a full
`uv run pytest tests/pairmode/ -q` (no `-x`) run before merge.
