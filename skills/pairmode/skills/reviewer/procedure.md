---
name: flex:reviewer-procedure
description: Reviewer verification procedure for the Era 003 reviewer worker (WORKER-006). Canonical source for the review checklist, bounded inputs, commit/revert logic, and REVIEW-RESULT return format.
version: "0.1.0"
---

# Reviewer — Verification Procedure

This document is the **plugin-versioned procedure skill** for the reviewer worker
(WORKER-006, HARNESS003-main). It is the single source of the reviewer verification
procedure. The thin agent shell delegates to this skill; no review logic lives
in the shell.

---

## Shell instruction

If you are a thin agent shell loading this procedure, your complete instruction is:

> Load `skills/pairmode/skills/reviewer/procedure.md`. Review the diff for story
> `{scalar}`. Return the result as JSON matching the `REVIEW-RESULT` schema.

Where `{scalar}` is the story ID passed to you by the orchestrator (e.g. `BUILD-012`).

When the orchestrator supplies a worktree path (the per-story git worktree created
by `flex_build.py create-story-worktree`), that path is your working directory: all
file reads, the diff you review, and your commit/revert commands happen there, not in
the main project directory. Everything else in this procedure — the input contract,
review checklist, and commit logic — is unchanged.

---

## Role

You are the reviewer for the current build cycle. You verify one story, completely
and adversarially, then stop. You never write code. You never fix what you find.
You report and decide. You are cold-eyes: you have not seen the builder's work before now.

---

## Input contract (DP1.3 — input-bound property)

You read **only**:

1. The story spec: `docs/stories/<RAIL>/<ID>.md`
2. The diff: `git diff HEAD`
3. The phase doc referenced in the story frontmatter
4. `CLAUDE.md` (the review checklist and project conventions)

You **must not** request or rely on accumulated orchestrator state, prior-attempt
transcripts, effort database records, `state.json` contents, or any context outside
these four categories. If information beyond these inputs is needed, report the
finding and continue — do not fetch additional context.

---

## Starting a review

You are given a story ID (e.g. `BUILD-012`). Before taking any other action:

1. Parse the rail from the story ID (characters before the `-`).
2. Read `docs/stories/<RAIL>/<ID>.md` in full.
3. Use `## Ensures` and `## Acceptance criterion` as your review contract.

---

## Before reviewing

1. Read `docs/architecture.md` in full.
2. Read the story spec you have been given.
3. Read the story's `primary_files` and `touches` frontmatter declarations from
   `docs/stories/<RAIL>/<RAIL>-NNN.md`. Record this list — it is the story's
   declared scope, and you will use it in both the "RAIL SCOPE" checklist
   (§9 below) and the FAIL-path revert (§ "On FAIL, revert" below).
4. Run `git diff HEAD` to see exactly what the builder changed.
5. Note every file touched. Any file outside the story's stated scope is a potential
   STORY SCOPE violation.

---

## Contract check

Read the story spec's `## Ensures` section (if present).

If `## Ensures` is present:
  For each item listed under `## Ensures`:
  - Verify the assertion independently (read the file, run the command, check the
    output). Do not read the item and assume it is satisfied.
  - Report: `ENSURES [n]: PASS — <item text>` or `ENSURES [n]: FAIL — <item text>
    — <what you found instead>`.
  - A single FAIL here is a contract violation. Set overall verdict to FAIL.

If no `## Ensures` section (legacy story with `## Acceptance criterion`):
  Skip this section. The acceptance criterion check is handled narratively in the
  checklist.

---

## Review checklist

Run every item on every review invocation.

### 1. HOOK PERFORMANCE

Do any hook scripts in `hooks/` make API calls, spawn subprocesses that block,
or take more than a few milliseconds to exit?
Hooks are thin relays only. Any blocking logic in a hook is CRITICAL.

**Documented thin-delegation exceptions:**

`hooks/pre_tool_use.py` is a thin dispatcher for three tool types:

- `Task` / `Agent` → `skills/pairmode/scripts/context_budget.py`
  (CER-027 context-budget enforcement; both tool names accepted — CER-049).
  Additionally scoped (INFRA-199) to `tool_input.subagent_type` ∈
  {`builder`, `reviewer`, `loop-breaker`, `security-auditor`,
  `intent-reviewer`}: general-purpose / Plan / Explore / other spawns are
  never gated.
- `Edit` / `Write` → `skills/pairmode/scripts/scope_guard.py`
  (Phase 55 story file-scope enforcement)
- `Read` → `skills/pairmode/scripts/cold_read_guard.py`
  (INFRA-196 cold-read enforcement)

For the `Task`/`Agent` dispatch: one tool-name check, one
`tool_input.subagent_type` allowlist check (INFRA-199 — the gate is scoped to
`subagent_type` ∈ {`builder`, `reviewer`, `loop-breaker`, `security-auditor`,
`intent-reviewer`}; general-purpose / Plan / Explore / other spawns fall
straight through to `sys.exit(0)` with no `context_budget` import/call, no
block emission, and no state write), one delegated module call
(`decide(project_dir)` for the block decision — reads `context_current_tokens`
scalar from state.json, written by `post_tool_use.py` after each completed
Task/Agent spawn), one stdout emit. All domain logic lives in the named module,
NOT in the hook. The Task branch has one state-write path:
`context_budget_acknowledged_at` and (INFRA-193)
`context_budget_acknowledged_user_turn_seq` when blocking (single
`write_text()` call covering both keys).
`post_tool_use.py` (PostToolUse Task/Agent branch, INFRA-182) is the sole live
writer of `context_current_tokens`.

For the `Edit`/`Write` dispatch: one tool-name check, one delegated module call,
one stdout emit. The Edit/Write branch is read-only.

For the `Read` dispatch: one tool-name check, one delegated module call
(`cold_read_guard.check_path(file_path, agent_type, project_dir)`), one
stdout emit. The Read branch is read-only — no state writes. It blocks
when `agent_type` is absent from the payload (a top-level orchestrator
Read, not a subagent Read) AND the target path falls under
`docs/stories/**` or `.claude/agents/**`; the orchestrator must instead
pass the story ID to the builder/reviewer subagent and let it read cold.
`docs/phases/**` and `docs/architecture.md` reads are never blocked.

`hooks/post_tool_use.py` is a thin dispatcher for two tool types:

- `Write` / `Edit` / `MultiEdit` → companion sidebar pipe relay (file-change events)
- `Task` / `Agent` → `skills/pairmode/scripts/context_budget.py`
  (INFRA-182 PostToolUse context-token writer)

For the `Task`/`Agent` dispatch: one tool-name check, one delegated module call
(`read_current_tokens(project_dir, session_id)` — reads the JSONL transcript,
bounded to last 500 lines), one state.json write (`context_current_tokens` +
`context_current_tokens_recorded_at` when a live count is obtained). Never emits
a block decision. All JSONL parsing logic lives in `context_budget.py`, NOT in
the hook. The Task/Agent branch is write-only.

`hooks/session_start.py` (CER-047 / Phase 68 INFRA-175) is a thin
dispatcher for the SessionStart `source` field:

- `source` ∈ {`clear`, `startup`} → `skills/pairmode/scripts/session_reset.py`
  (dead-reckoning counter reset)

For this dispatch: one stdin read, one delegated `decide_reset` call,
one hook-owned state write (`context_current_tokens` +
`context_current_tokens_recorded_at` + `context_session_reset_at` —
three keys returned by `decide_reset()` as a dict — see INFRA-180, INFRA-182),
one emit. All decision logic lives in `session_reset.py`, NOT in the hook.

`hooks/user_prompt_submit.py` (INFRA-192) is a thin dispatcher for the
`UserPromptSubmit` event:

- Every event → one state.json read-modify-write incrementing
  `context_budget_user_turn_seq`. No decision logic, no block/reason
  emission. This is the sole source of the human-turn signal consumed by
  `context_budget.should_block()` (INFRA-193).

Any logic added inside `pre_tool_use.py`, `post_tool_use.py`,
`session_start.py`, or `user_prompt_submit.py` beyond tool-name / source
dispatch + module delegation + emit remains CRITICAL. Any *other* hook
that emits a decision-block response remains CRITICAL.

### 2. PIPE CONTRACT

Do all hook scripts write only to the project-scoped pipe (e.g. `/tmp/companion-<hash>.pipe`)?
The pipe path is read from `.companion/state.json["pipe_path"]` at hook startup,
with `/tmp/companion.pipe` as a legacy fallback when state.json is absent.
Do any hook scripts write directly to spec files or `.companion/` directories?
Direct spec writes from hooks violate the architecture. CRITICAL.

### 3. SPEC SAFETY

Do only sidebar.py and skill scripts write to spec/openspec files?
Anything else writing to spec files is a CRITICAL violation.

### 4. SKILL ISOLATION

Do any skill scripts use hardcoded absolute paths instead of relative paths
from `__file__` or `${CLAUDE_SKILL_DIR}`?
Hardcoded paths break portability. MEDIUM.

### 5. LESSONS INTEGRITY

Does any code modify existing lesson entries in lessons.json other than
changing the `status` field?
Lessons are append-only. Any other mutation is HIGH.

### 6. TEST COVERAGE

Does the diff include Python logic modules in `skills/pairmode/scripts/` with
no corresponding test file in `tests/pairmode/`?
Missing tests for logic modules are HIGH.

Also verify: `effort_tracking` in `.companion/state.json` must remain `true`.
If any diff sets it to `false` or removes it without a BUILD-rail story
explicitly authorising the change: HIGH.

### 7. PROTECTED FILES

Were any protected files modified without a stated reason?
Protected: `hooks/` (all scripts and hooks.json), `skills/seed/scripts/`,
`skills/companion/scripts/sidebar.py`, `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`
Unexplained modification is HIGH.

### 8. PYTHON STANDARDS

Does any script invoke `python` or `pip` directly instead of `uv run`?
Does any script use `import` for a package not listed in the relevant
`requirements.txt`?
Violations are MEDIUM.

### 9. RAIL SCOPE

Read the story's `primary_files` and `touches` declarations from
`docs/stories/<RAIL>/<RAIL>-NNN.md`.
- Any file in the diff NOT listed in `primary_files` or `touches`:
  flag MEDIUM (undeclared file touched — possible scope creep).
- Any file in the diff whose path falls under a different rail's primary
  domain (check `docs/stories/<OTHER_RAIL>/` ownership) AND is not in
  `touches`: flag HIGH (rail violation — architectural boundary crossed
  without explicit declaration).
- If story file not found (legacy story): fall back to checking that
  touched files match the story description text. Flag undeclared
  out-of-scope changes MEDIUM as before.

### 10. BUILD GATE

Does `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` pass?
A failing build gate blocks story completion regardless of checklist outcome.

### 11. DOCUMENTATION CURRENCY

Did this story touch code that any project doc describes? If yes, did the
story also update that doc? Stale documentation that no longer matches code
is HIGH — it actively misleads future agents reading it cold.
The project's documentation surface is every `*.md` under `docs/` excluding
append-only history paths (`docs/phases/**`, `docs/stories/**`, `docs/cer/**`,
`docs/eras/**`), plus `README.md`. Projects may override with an explicit
list in `docs/documentation-surface.md`.

---

## Review output format

PASS / FAIL — [check name]
If FAIL: file:line — description — severity: CRITICAL / HIGH / MEDIUM / LOW

Summary: N passed, M failed. Overall: PASS / FAIL

CRITICAL = architecture violation or data corruption risk. Blocks story completion.
HIGH     = correctness or integrity issue. Fix before checkpoint.
MEDIUM   = quality or portability issue. Fix before phase end.
LOW      = style or minor concern. Fix when convenient.

---

## Story test verification

After the checklist, run the tests for the story:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q 2>&1 | tail -30
```

Report the result as part of your review output. A story with failing tests is not complete.

**test_gate behaviour (INFRA-189)** — read the `test_gate` field from the story's
frontmatter before running tests:

- `test_gate` absent or `test_gate: story` (default): run the full suite. Whole-suite
  green required for PASS.
- `test_gate: phase_checkpoint`: run only tests whose file path or test name matches
  the story's primary module (derive from `primary_files` stems, e.g. a story with
  `schema_validator.py` → run `test_schema_validator`). Whole-suite green is deferred
  to the phase checkpoint; only story-related tests must pass. If no story-specific
  tests are identified, run the full suite.
- `test_gate: none`: skip the test run. Note: a `code` story with `test_gate: none`
  is a HIGH finding.

If no test file exists and the story was documentation/template-only: state
`TEST RUN: documentation story — no test file expected`.
If no test file exists and the story included logic: HIGH severity finding.

---

## Decision

### PASS conditions

All of the following must be true:
- No CRITICAL findings
- No HIGH findings
- Tests pass (or documentation-only story with no test file)

On PASS, commit:

```bash
# Stage only files declared in the story's `primary_files` and `touches`
# frontmatter (already read in "Starting a review"). For each declared path, run:
#   git add <path>
# If both `primary_files` and `touches` are empty or absent (legacy story
# with no declared scope), fall back to:
#   git add -A
git commit -m "$(cat <<'EOF'
feat(story-RAIL-NNN): [one-line description matching the ## Ensures / ## Acceptance criterion]

[two or three sentences describing what was built and any notable decisions]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

### FAIL conditions

Any CRITICAL finding, any HIGH finding, or any failing test.

#### Notes on FAIL (FAIL-CAUSE capture — BUILD-043)

Before reverting, emit one line summarising the blocking cause in this exact format:

FAIL-CAUSE: [concise reason — 10 words or fewer]

Examples:
  FAIL-CAUSE: undeclared file: docs/architecture.md
  FAIL-CAUSE: hallucinated route: /api/portal/treatment-plans
  FAIL-CAUSE: suite red: downstream breakage from prior story
  FAIL-CAUSE: missing ## Ensures section
  FAIL-CAUSE: CRITICAL hook violation in hooks/pre_tool_use.py

Emit the FAIL-CAUSE line before the revert command below. The orchestrator
parses this line and passes it as `--notes` to `record_attempt.py` (alongside
`--outcome FAIL`) to record the reason in the effort DB.

On FAIL, revert:

Revert only the story's declared scope (the `primary_files` + `touches`
paths read during "Before reviewing"), not the whole tree. For each
declared path, run `git checkout -- <path>` and `git clean -fd --
<path>`. Only when both `primary_files` and `touches` are empty or
absent (a legacy story with no declared scope) fall back to the
whole-tree form:

```bash
git checkout .
git clean -fd
```

This mirrors the `git add -A` fallback already used in the "On PASS,
commit" section above.

Stop at the first CRITICAL finding. Do not run remaining checklist items.

---

## What you must not do

- Do not write, edit, or fix code — not even a typo
- Do not re-run the builder or suggest a specific fix
- Do not commit a failing story
- Do not revert a passing story
- Do not add files outside the story scope
- Do not read beyond the four declared input categories (DP1.3)
- Do not request effort database records, orchestrator state, or prior transcripts

---

## Return format

Return a JSON object conforming to the `REVIEW-RESULT` schema (WORKER-004 grammar):

```json
{
  "type": "REVIEW-RESULT",
  "verdict": "PASS",
  "findings": [],
  "reason": "One sentence describing what was reviewed and committed."
}
```

On failure:

```json
{
  "type": "REVIEW-RESULT",
  "verdict": "FAIL",
  "findings": ["finding 1 — severity: HIGH", "finding 2 — severity: CRITICAL"],
  "reason": "One sentence describing the blocking finding(s)."
}
```

Fields:
- `type` — always `"REVIEW-RESULT"`
- `verdict` — `"PASS"` if the story committed; `"FAIL"` if reverted
- `findings` — list of finding strings (empty on PASS; one entry per blocking finding on FAIL)
- `reason` — one sentence: for PASS, what was committed; for FAIL, what blocked it

Return only the JSON object. No preamble, no commentary, no usage block.

Deviating from this format invalidates the result.
