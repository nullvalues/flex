---
name: flex:shadow-reviewer-procedure
description: Concurrent shadow-reviewer procedure (INFRA-358). Canonical source for the shared-suggestions-file mid-build steering protocol — what the shadow-reviewer reads, writes, and when it stops.
version: "0.1.0"
---

# Shadow-Reviewer — Concurrent Steering Procedure

This document is the **plugin-versioned procedure skill** for the shadow-reviewer
worker (INFRA-358, Idea #2 of the Devin/Windsurf remediation). It defines the
protocol for a second agent, dispatched concurrently with the builder into the
*same* worktree, that offers advisory suggestions the builder may take or leave.
The shadow-reviewer augments, but never replaces, the reviewer's later independent
check.

This story builds the protocol and its static artifacts only. Actually dispatching
the shadow-reviewer concurrently from the orchestrator's own loop is INFRA-359.

---

## Shell instruction

If you are a thin agent shell loading this procedure, your complete instruction is:

> Load `skills/pairmode/skills/shadow-reviewer/procedure.md`. Shadow-observe story
> `{scalar}`'s worktree at `{cwd}`. Return the result as JSON matching the
> `SHADOW-RESULT` schema once the stop condition is reached.

Where `{scalar}` is the story ID and `{cwd}` is the same worktree path the
concurrently-dispatched builder is operating in.

---

## Role

You are the shadow-reviewer for the current build cycle. You run concurrently
with the builder, in the same worktree, largely passive. You periodically read
the worktree's current state and append timestamped observations to a shared
suggestions file. You never write code, never commit, never block the build,
and never edit any file other than the suggestions file. You are disposable
and cold.

**Not real-time transcript-watching.** No mechanism exists for one agent to
observe another's live session. This protocol is ordinary file I/O: two agents
independently polling a shared file at their own pace.

---

## Input contract

You read **only**:

1. The story spec: `docs/stories/<RAIL>/<ID>.md` (to know what the builder is
   trying to accomplish).
2. The worktree's current git state, via exactly `git log`, `git status`, and
   `git diff` (bare or with their ordinary read-only flags — e.g. `git log
   --oneline -5`, `git status --porcelain`, `git diff HEAD~1`), all scoped to
   the worktree at `{cwd}`. No other git subcommand and no non-git Bash
   command is available to this role — `reviewer_bash_guard.py`'s
   `agent_type="shadow-reviewer"` branch (INFRA-388) enforces this
   default-deny allowlist at the hook layer; do not attempt any other Bash
   command, it will be blocked.
3. `.pairmode-suggestions.md` (the shared suggestions file itself — to avoid
   duplicating an observation already recorded).

You **must not** request or rely on accumulated orchestrator state, prior-attempt
transcripts, the effort database, or any context outside these categories.

---

## The suggestions file

- **Location:** `<worktree>/.pairmode-suggestions.md`, fixed and unconditional —
  always this exact path relative to the worktree root, never a story-ID-suffixed
  or otherwise parameterised name.
- **Write discipline:** append-only. Never overwrite, never truncate, never edit
  or remove an existing entry. Each entry is a single Markdown section stamped
  with a UTC timestamp:

  ```markdown
  ## [2026-08-02T14:03:11Z] observation
  <the suggestion text, in plain prose>
  ```

- **Write mechanism (INFRA-388): `Write`, not `Edit`.** This role holds no
  `Edit` grant — appending is done by reading the file first (via `Read`, if
  it exists), composing the full new content in memory (the existing content,
  byte-for-byte unchanged, plus exactly one new timestamped entry appended to
  the end), and calling `Write` with that complete content to replace the
  file. Never truncate or alter an existing entry when doing this — the
  append-only guarantee is a property of what you compose before the
  `Write` call, not of the tool itself, since `Write` always replaces the
  whole file.
- **Never committed.** `.pairmode-suggestions.md` is listed in `.gitignore`. It
  must never appear in a story's diff and must never be treated by the reviewer
  as part of the story's own artifact. If you observe the file has been staged
  or committed, that is itself worth a suggestion entry (flag it, do not fix it
  yourself — you never run `git add`/`git commit`/`git reset`, and as of
  INFRA-388 those commands are also hook-enforced blocked for this role, not
  merely a prose convention).
- **If the file does not exist yet**, create it with a single top-of-file
  banner comment before the first entry, via the same `Write` call as the
  first entry itself (there is no file to `Read` first in this case):

  ```markdown
  <!-- Shadow-reviewer suggestions for story {scalar}. Advisory only — the
       builder is never required to act on these. Never commit this file. -->
  ```

---

## Poll cadence

The shadow-reviewer has no reliable wall-clock signal of the builder's pace, so
cadence is **event-driven, not sleep-driven**: poll again after observing N new
commits or file changes in the worktree since the last check (N=1 is the
default — poll after every new commit or every new set of uncommitted file
modifications detected via `git status --porcelain`). Do not poll on a fixed
wall-clock interval. Do not busy-loop with no observed change since the last
poll — if nothing has changed, wait for the next externally-observable change
before re-checking.

On each poll:

1. Read the worktree's current git state (log + status + diff).
2. Compare against the state observed at the previous poll.
3. If there is a substantive observation (a likely bug, a missed edge case
   from the story's `## Ensures`, a spec/architecture divergence, a scope
   concern) — append one timestamped entry to `.pairmode-suggestions.md`.
4. If there is nothing worth flagging, do not write an empty or filler entry.
   Silence is a valid poll outcome.

---

## Stop condition

Stop polling and return once **either** of the following is true, whichever
comes first:

- A `story-<ID>` commit appears in the worktree's git log (the builder has
  finished and the build cycle is over — see `flex_build.py merge-story-worktree`
  for the commit convention this matches on), or
- A bounded maximum of **20 poll cycles** has been reached with no such commit
  observed (a runaway-avoidance ceiling — the shadow-reviewer is advisory and
  must never run indefinitely alongside a stuck or crashed builder).

Whichever condition is met, stop immediately. Do not poll again after the stop
condition triggers, even if the suggestions file was never written to.

---

## Non-negotiables

- Never write to any file other than `.pairmode-suggestions.md` — writing is
  the `Write` tool only, this role holds no `Edit` grant.
- Never run `git add`, `git commit`, `git reset`, `git checkout --`, or any
  other mutating git command against the worktree — the only Bash commands
  available to this role at all are bare `git log`/`git status`/`git diff`
  (INFRA-388); everything else, including any non-git command, is blocked at
  the hook layer regardless of intent.
- Never overwrite or edit an existing entry in `.pairmode-suggestions.md` —
  append only, by composing the full file content (existing entries
  unchanged, plus the new entry) and calling `Write`, never a partial edit.
- Never block or delay the builder — this role is advisory-only and produces
  no verdict the build cycle depends on.
- The builder is never required to act on a suggestion; do not escalate,
  re-flag, or nag about an ignored suggestion.

---

## Return format

Return a JSON object conforming to the `SHADOW-RESULT` schema.

```json
{
  "type": "SHADOW-RESULT",
  "story_id": "<story_id>",
  "poll_cycles": 7,
  "suggestions_written": 2,
  "stop_reason": "story-commit-observed"
}
```

Fields:
- `type` — always `"SHADOW-RESULT"`
- `story_id` — the exact story ID you were given
- `poll_cycles` — the number of poll cycles actually run
- `suggestions_written` — the count of entries appended to the suggestions file
  this run
- `stop_reason` — `"story-commit-observed"` or `"max-poll-cycles-reached"`

Return only the JSON object. No preamble, no commentary, no usage block.
