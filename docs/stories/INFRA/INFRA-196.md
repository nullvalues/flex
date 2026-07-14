---
id: INFRA-196
rail: INFRA
title: "Cold-read enforcement hook — block orchestrator Read of story/agent files"
status: planned
phase: "87"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - hooks/pre_tool_use.py
  - skills/pairmode/scripts/cold_read_guard.py
  - CLAUDE.md
  - skills/pairmode/templates/CLAUDE.md.j2
touches:
  - tests/pairmode/test_pre_tool_use_hook.py
  - tests/pairmode/test_cold_read_guard.py
---

## Requires

- Current (buggy) behavior, verified directly in this repo:
  - `hooks/pre_tool_use.py` dispatches only on `tool_name in ("Task", "Agent")`
    (delegates to `context_budget.decide`) and `tool_name in ("Edit", "Write")`
    (delegates to `scope_guard.check_path`). There is no `Read` branch — `Read`
    calls fall through to the final `sys.exit(0)` with no gating at all.
  - `CLAUDE.build.md`'s documented builder/reviewer spawn contract: "Spawn the
    `builder` subagent with: The story ID only... Do not pass story text, file
    contents, or git history. The builder reads its own story spec and any
    context it needs" and, for the reviewer, "The story ID only... The
    reviewer reads its own story spec cold." Neither role's spawn step
    instructs the orchestrator to `Read` `docs/stories/**` or
    `.claude/agents/**` itself first.
  - Confirmed externally (caddy project, live incident): the orchestrator
    `Read` `docs/phases/phase-1-edge-host-bootstrap.md`,
    `docs/stories/EDGE/EDGE-001.md`, `docs/architecture.md`, and both
    `.claude/agents/builder.md` / `.claude/agents/reviewer.md` role files
    directly into its own context, then hand-inlined that content into
    manually-constructed Agent prompts, on a one-line-diff story. This
    repeated three times (two `/clear` + identical-prompt retries) because
    the failure mode was orchestrator behavior, not story complexity or
    template drift — `sync-all` had already run between attempts and changed
    nothing relevant.
  - Verified empirically in this repo (temporary debug hook, added and
    reverted within one session, `git diff` on the touched settings file
    confirmed clean afterward): the PreToolUse hook payload includes an
    `agent_type` key (alongside `agent_id`) when, and only when, the
    triggering tool call originates from inside a spawned subagent's own
    tool-use loop. A top-level orchestrator's own tool call has no
    `agent_type` key in the payload at all. Subagent tool calls DO route
    through the parent session's PreToolUse hooks (this was the open
    question going in) — they are not exempt.
  - `CLAUDE.build.md` has legitimate, documented orchestrator-level reads of
    `docs/phases/**` and `docs/architecture.md`: "3.5 Phase doc boundary
    scan" ("Read the embedded section in the phase doc"), the phase
    completion check ("Read the Stories table in the phase doc"), and
    checkpoint-time intent-review doc updates ("Apply its recommended
    changes to `docs/phases/phase-N.md`... and `/docs/architecture.md`").
    These must keep working — this story does not gate `docs/phases/**` or
    `docs/architecture.md`, only `docs/stories/**` and `.claude/agents/**`,
    which have no such documented orchestrator-level precedent anywhere in
    `CLAUDE.build.md`.
  - `skills/pairmode/scripts/scope_guard.py::check_path` is the existing
    precedent for a hook-delegated guard module's shape:
    `check_path(...) -> tuple[bool, str]`, fails open on any read/parse
    error, takes `project_dir` as a `str | Path`.
  - `CLAUDE.md`'s "Documented thin-delegation exceptions" section
    (checklist item 1, HOOK PERFORMANCE) enumerates every existing
    `pre_tool_use.py` / `post_tool_use.py` / `session_start.py` /
    `user_prompt_submit.py` dispatch branch by name. Any new dispatch branch
    not described there reads as undocumented hook logic and is a CRITICAL
    finding under that checklist item — this story must add the new `Read`
    branch to that enumeration, not just to the hook script.

## Ensures

- New module `skills/pairmode/scripts/cold_read_guard.py` exposes
  `check_path(file_path: str | Path, agent_type: str | None, project_dir: str | Path) -> tuple[bool, str]`:
  - If `agent_type` is a non-empty string: returns `(True, "subagent read — allowing")`
    unconditionally, without inspecting `file_path`.
  - Otherwise, normalises `file_path` relative to `project_dir` (same
    absolute/relative handling as `scope_guard._normalise` — path-traversal
    escape returns `(False, "path escapes project root")`).
  - If the normalised path falls under `docs/stories/` or `.claude/agents/`
    (prefix match on the normalised POSIX path): returns
    `(False, reason)` where `reason` names the violated contract and the
    correct alternative, e.g. `"orchestrator must not Read docs/stories/** "
    "directly — pass the story ID to the builder/reviewer subagent and let "
    "it read cold"`.
  - Any other path: returns `(True, "not a protected orchestrator-read path")`.
  - Fails open (returns `(True, reason)`) on any unexpected exception, matching
    `scope_guard.py`'s fail-open behavior.
- `hooks/pre_tool_use.py` gains one new `elif tool_name == "Read":` branch,
  matching the existing dispatch shape exactly: one delegated call to
  `cold_read_guard.check_path(file_path=data.get("tool_input", {}).get("file_path", ""), agent_type=data.get("agent_type"), project_dir=Path(data.get("cwd") or "."))`,
  one `print(json.dumps({"decision": "block", "reason": reason}))` when not
  allowed, `sys.exit(0)` either way. No other logic in the branch — this
  keeps the hook a thin dispatcher per `CLAUDE.md` checklist item 1.
- `CLAUDE.md`'s "Documented thin-delegation exceptions" section gains a new
  bullet for the `Read` dispatch, in the same style as the existing
  `Task`/`Agent` and `Edit`/`Write` bullets under `hooks/pre_tool_use.py`:
  names the delegated module and function, states the branch is read-only,
  and states the block condition (`agent_type` absent from the payload AND
  path under `docs/stories/**` or `.claude/agents/**`).
- `skills/pairmode/templates/CLAUDE.md.j2` gets the same bullet added (the
  canonical template other pairmode projects sync from), so projects that
  run `pairmode sync` after this story pick up the documentation update.
  `hooks/pre_tool_use.py` itself is referenced by other projects via
  absolute path (e.g. caddy's `.claude/settings.json` points at
  `/mnt/work/flex/hooks/pre_tool_use.py`), so the enforcement itself is live
  for every pairmode project immediately on merge — this story's `CLAUDE.md`
  changes are catching the documentation up to already-live behavior, not
  gating a rollout.
- `docs/phases/**` and `docs/architecture.md` are unaffected — reads of
  those paths, with or without `agent_type` present, are never blocked by
  this story's logic.
- New tests in `tests/pairmode/test_cold_read_guard.py` cover: orchestrator
  read (`agent_type=None`) of a `docs/stories/**` path is blocked; same for
  `.claude/agents/**`; subagent read (`agent_type="general-purpose"` or any
  non-empty string) of the same paths is allowed; orchestrator read of an
  unrelated path (e.g. `docs/phases/phase-1.md`, `README.md`) is allowed;
  path-traversal escape is blocked regardless of `agent_type`; malformed/
  missing `project_dir` fails open.
- New tests in `tests/pairmode/test_pre_tool_use_hook.py` cover: a `Read`
  tool-use payload with no `agent_type` key and a `docs/stories/**`
  `file_path` produces a `{"decision": "block", ...}` stdout emit; the same
  payload with an `agent_type` key present produces no emit (exit 0, no
  stdout); a `Read` payload for an unrelated path produces no emit.

## Test plan

`PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cold_read_guard.py tests/pairmode/test_pre_tool_use_hook.py -x -q`

Full suite gate before checkpoint: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`
