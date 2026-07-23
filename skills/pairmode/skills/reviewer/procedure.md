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
5. `CLAUDE.build.md` (the Build standards section — test command,
   test-location convention, protected-file list, domain-isolation rule; these
   are per-project facts, not hardcoded into this procedure — see checklist
   items 6, 7, and 10 below)
6. `docs/architecture.md` — read in full; it is the architectural contract every
   review is checked against (see "Before reviewing" below).
7. The project documentation surface, for the DOCUMENTATION CURRENCY check
   (checklist item 11): every `*.md` under `docs/` excluding the append-only
   history paths (`docs/phases/**`, `docs/stories/**`, `docs/cer/**`,
   `docs/eras/**`), plus `README.md` — or the explicit list in
   `docs/documentation-surface.md` when a project provides one.
8. `docs/ideology.md` (INFRA-242) — read **conditionally**, only when the
   IDEOLOGY DRIFT check (checklist item 12) finds out-of-spec diff content.
   An in-scope, spec-clean diff never reads this file.

You **must not** request or rely on accumulated orchestrator state, prior-attempt
transcripts, effort database records, or `state.json` contents — the loop's runtime
state is off-limits. If information beyond these declared inputs is needed, report
the finding and continue — do not fetch additional context.

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
- `Task` / `Agent` → `skills/pairmode/scripts/context_budget.py` (INFRA-182
  PostToolUse context-token writer) AND
  `skills/pairmode/scripts/subagent_transcript.py` (INFRA-236 effort-attempt
  writer) — neither call ever reads agent-authored prose for its data.

For the `Task`/`Agent` dispatch: one tool-name check, then two independently
try/excepted delegated module calls (a failure in either must never block or
affect the other), one stdout emit (none — this branch is silent; it only
writes state and exits 0). Never emits a block decision.

The first delegated call, `read_current_tokens(project_dir, session_id)`
(`context_budget.py`) — reads the live JSONL session log, bounded to last
500 lines — feeds one state.json write: `context_current_tokens` +
`context_current_tokens_recorded_at`, when a live count is obtained.

The second delegated call,
`record_attempt_from_transcript(project_dir, session_id, tool_input,
tool_response, tool_use_id)` (`subagent_transcript.py`) — reads the
just-completed spawn's own usage from that same live session log (a
DIFFERENT metric than the first call's orchestrator-window count; never
merged with it — see DP7 in `docs/architecture.md`), plus
`tool_input`/`tool_response`/`state.json` for role/story/model/outcome —
feeds one write to the effort database: a single attempt row via
`effort_recorder.record_effort`, when `tool_input.subagent_type` is a
recordable build-cycle role and `effort_tracking` is `true`.

All parsing and DB-write logic lives in the two named modules, never in
the hook. The Task/Agent branch writes to two different stores
(`state.json` and the effort database) via its two calls — it is not purely
write-only-to-one-place, but every write is delegated; the hook itself
performs no parsing or decision logic.

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

Do all hook scripts write only to the single hardcoded pipe path
(`os.path.join(tempfile.gettempdir(), "companion.pipe")`, the same
convention `post_tool_use.py` established)? (INFRA-238) The `pipe_path`
state.json key was retired by `pairmode_migrate.py`'s `to-030` step and no
hook script reads it any longer.
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

Does the diff include Python (or other) logic modules with no corresponding
test file in the project's declared test directory? Read the test-location
convention from `CLAUDE.build.md`'s Build standards section (`test_dir`); do
not assume any specific project's fixed test-directory layout applies
universally.
Missing tests for logic modules are HIGH.

Also verify: `effort_tracking` in `.companion/state.json` must remain `true`.
If any diff sets it to `false` or removes it without a BUILD-rail story
explicitly authorising the change: HIGH.

### 7. PROTECTED FILES

Were any protected files modified without a stated reason?
Protected: read the project's protected-file list from `CLAUDE.build.md`'s
Build standards section (`protected_paths`); when that section is absent or
empty, fall back to the project's own documented protected-file list (e.g.
`docs/architecture.md` § Protected files). Do not assume any specific
project's list applies universally.
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

Does the project's test command — read from `CLAUDE.build.md`'s Build
standards section (`test_command`); fall back to the project's own documented
test invocation when that section is absent — pass?
A failing build gate blocks story completion regardless of checklist outcome.

### 11. DOCUMENTATION CURRENCY

Did this story touch code that any project doc describes? If yes, did the
story also update that doc? Stale documentation that no longer matches code
is HIGH — it actively misleads future agents reading it cold.
The project's documentation surface is every `*.md` under `docs/` excluding
append-only history paths (`docs/phases/**`, `docs/stories/**`, `docs/cer/**`,
`docs/eras/**`), plus `README.md`. Projects may override with an explicit
list in `docs/documentation-surface.md`.

### 12. IDEOLOGY DRIFT — narrow, spec-gated (INFRA-242)

This is **not** a full re-audit of the diff against `docs/ideology.md` (that
check moved to spec-authoring time — see `spec-writer/procedure.md` Step 4a —
and to the checkpoint-level `intent-reviewer`, which remains the phase-wide
backstop, unaffected by this check). This check is scoped narrowly to the gap
between the story's own spec and the diff, not the gap between the diff and
the whole of `docs/ideology.md`.

**Gate — determine whether this check activates at all:**

Using the `primary_files`/`touches` declarations and the `## Ensures`/
`## Instructions` sections already read for RAIL SCOPE (§9) and the Contract
check above, classify every changed hunk in `git diff HEAD` as either:
- **in-spec** — the file is declared in `primary_files`/`touches` AND the
  change is plausibly what `## Ensures`/`## Instructions` called for, or
- **out-of-spec** — the file is undeclared (already flagged separately under
  RAIL SCOPE), OR the file is declared but the diff adds something beyond
  what `## Ensures`/`## Instructions` asked for (e.g. an unrequested
  refactor, an added dependency, a new code path not named in the spec).

If every hunk is in-spec: **PASS — IDEOLOGY DRIFT (skipped, diff matches
spec-approved scope)**. Do not read `docs/ideology.md` for this check — the
whole point of the spec-time move (INFRA-242) is that an in-scope, spec-clean
diff inherits its ideology alignment structurally from the spec, so re-reading
`docs/ideology.md` here is redundant cost with no signal.

If any hunk is out-of-spec: read `docs/ideology.md` (skip with a note if it
does not exist) and check only the out-of-spec hunks — not the whole diff —
against `## Core convictions`, `## Accepted constraints`, and
`## Prototype fingerprints`:
- Out-of-spec content that also violates a convictions/constraints entry:
  FAIL — IDEOLOGY DRIFT (HIGH).
- Out-of-spec content that alters a fingerprint marked "No" without
  acknowledgment: FAIL — IDEOLOGY DRIFT (LOW).
- Out-of-spec content that is ideology-neutral: no IDEOLOGY DRIFT finding
  (the out-of-spec content itself is still flagged under RAIL SCOPE /
  STORY SCOPE as applicable — this check only adds an ideology-specific
  finding when the drift also independently violates ideology).

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
<test_command from CLAUDE.build.md's Build standards section> 2>&1 | tail -30
```

Read the actual command to run from `CLAUDE.build.md`'s Build standards section
(`test_command`); fall back to the project's own documented test invocation when
that section is absent. Do not assume every project uses the same test runner
or directory layout — those are per-project values, not universal ones.

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

Emit the FAIL-CAUSE line before the revert command below, for human
readability in the mid-response text. This line is never read back by the
orchestrator — it exists solely for the human operator watching the
transcript live. Also populate the `fail_cause` field (INFRA-236) in the
returned `REVIEW-RESULT` JSON with the same text — that field, not the
line above, is the actual data contract: the orchestrator only observes
the final JSON object, so `subagent_transcript.py`'s
`record_attempt_from_transcript()` (called from `hooks/post_tool_use.py`'s
Task/Agent branch, never by the reviewer itself) reads `fail_cause` from
`tool_response` to populate `record_attempt.py`'s `--notes` (alongside
`--outcome FAIL`) in the effort database row.

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
- Do not read beyond the declared input categories (DP1.3)
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
  "reason": "One sentence describing the blocking finding(s).",
  "fail_cause": "concise reason — 10 words or fewer"
}
```

Fields:
- `type` — always `"REVIEW-RESULT"`
- `verdict` — `"PASS"` if the story committed; `"FAIL"` if reverted
- `findings` — list of finding strings (empty on PASS; one entry per blocking finding on FAIL)
- `reason` — one sentence: for PASS, what was committed; for FAIL, what blocked it
- `fail_cause` — optional (INFRA-236). Present on FAIL, absent on PASS. The same
  concise reason as the mid-response `FAIL-CAUSE:` line (see § "Notes on FAIL"
  above) — that line stays for human readability, but this JSON field is the
  actual data contract: the orchestrator only observes the final
  return-format-only JSON object, never any earlier line of the response, so
  it reads `fail_cause` here and passes it as `--notes` to `record_attempt.py`.

Return only the JSON object. No preamble, no commentary, no usage block.

Deviating from this format invalidates the result.
