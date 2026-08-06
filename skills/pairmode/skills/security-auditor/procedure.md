---
name: flex:security-auditor-procedure
description: Security audit procedure for the Era 003 security-auditor worker (WORKER-008). Canonical source for the security checklist, bounded inputs, and REVIEW-RESULT return format.
version: "0.1.0"
---

# Security Auditor — Procedure

This document is the **plugin-versioned procedure skill** for the security-auditor
worker (WORKER-008, HARNESS003-main). It is the single source of the security audit
procedure. The thin agent shell delegates to this skill; no audit logic lives in the
shell.

---

## Shell instruction

If you are a thin agent shell loading this procedure, your complete instruction is:

> Load `skills/pairmode/skills/security-auditor/procedure.md`. Run the security
> audit for phase `{scalar}`. Return the result as JSON matching the `REVIEW-RESULT`
> schema.

Where `{scalar}` is the phase identifier passed to you by the orchestrator.

---

## Role

You are the security auditor for the current checkpoint. You scan for security
issues — key exposure, path traversal, hook violations, pipe contract violations,
and spec-safety violations. You do not write code. You do not fix findings. You
report with precision and decide. You are cold-eyes.

---

## Input contract (DP1.3 — input-bound property)

You read **only**:

1. The diff: `git diff HEAD` (or the phase diff at checkpoint)
2. The story spec: `docs/stories/<RAIL>/<ID>.md` for the story under audit
3. The `hooks/` directory: all hook scripts
4. Targeted repository searches (`grep`/`rg`/`Glob`) over source files, scoped
   to identifiers the phase diff introduces or changes, **for the DATA-FLOW
   INTEGRITY check (check 7) only** (INFRA-290). This is a deliberate, minimal
   widening of DP1.3 — tracing a field's writers and readers is unperformable
   without searching for the field. The prohibition is unchanged for loop
   runtime state: `state.json` contents, effort database records, and
   transcripts of prior attempts remain off-limits; a code search is not a
   read of that state.

You **must not** request or rely on accumulated orchestrator state, prior-attempt
transcripts, effort database records, `state.json` contents, or any context outside
these declared categories. The audit is **input-bound**: the diff, the story spec,
the `hooks/` directory, and the check-7-scoped source searches.

---

## Before auditing

Read `docs/architecture.md` in full. Pay particular attention to:
- Hook architecture (thin relays, no API calls)
- Pipe contract (hooks write only to pipe, never to spec files)
- Layer rules (hooks/ may not import from skills/)

---

## Security checklist

Run every item. Classify findings using the CRITICAL/HIGH/MEDIUM/LOW scale.

### 1. HOOK PERFORMANCE (CRITICAL if violated)

Do any files in `hooks/` make network calls, spawn API calls, or perform blocking
operations that take more than a few milliseconds?

Hooks are thin relays only. Any blocking logic in a hook is CRITICAL.

**Documented thin-delegation exceptions — do NOT flag these (BUILD-041):**

The following hooks are authorized thin dispatchers with permitted imports and
state.json writes. They do not violate the thin-relay contract.

- `hooks/pre_tool_use.py` — dispatches Task/Agent → `context_budget.py`
  (CER-027/CER-049) and Edit/Write → `scope_guard.py` (Phase 55), including
  the `scope_guard.resolve_call_story` lookup (INFRA-281); dispatches Read →
  `cold_read_guard.py` (INFRA-196); dispatches Bash → `reviewer_bash_guard.py`
  (INFRA-324 reviewer-role git-subcommand allowlist enforcement — fails open
  for every non-`reviewer` `agent_type`); calls `state_utils.update_state_json`
  for its own writes; and calls `flex_build`'s `_story_path` /
  `_read_story_frontmatter` helpers to resolve the active story's frontmatter.
  Authorized state.json writes: `context_budget_acknowledged_at` (on block
  only) and `context_budget_acknowledged_user_turn_seq` (INFRA-193).
- `hooks/post_tool_use.py` — pipe relay for Write/Edit/MultiEdit; dispatches
  Task/Agent → `context_budget.py` (INFRA-182), including
  `context_budget.record_step_growth` (INFRA-254); reads session-scoped state
  via `session_state`. It also delegates post-hoc effort recording to
  `subagent_transcript` (INFRA-236) — the hook never parses or stores
  transcript content itself, it only forwards the call to that module.
  Authorized state.json writes: the live context-token count and its
  recorded-at timestamp, `context_current_tokens_source` (INFRA-374 — records
  which code path produced the count), plus `context_step_growth_samples` and
  `expected_step_tokens` (INFRA-254).
- `hooks/session_start.py` — dispatches source `clear`/`startup` →
  `session_reset.py` (CER-047/INFRA-175); reads and writes session-scoped
  state via `session_state` (INFRA-285); and on startup runs the
  `subagent_transcript.reconcile_pending_attempts` sweep (INFRA-258) to
  reconcile attempts left pending by a prior session — the hook never reads
  or replays transcript content itself, it only calls the delegate to
  reconcile database rows. Also calls `session_lifecycle.agent_staleness_notice`
  (INFRA-323 § F) with values already read from the state dict and
  `session_state.session_view` — a single pure call, wrapped in its own
  best-effort try/except, that reads (never writes) the
  `agent_surfaces_written_at`/`agent_surfaces_written_by` stamp and returns at
  most one advisory line. Authorized state.json writes:
  the context-token count baseline, its recorded-at timestamp, and the
  session-reset timestamp.
- `hooks/user_prompt_submit.py` — dispatches every `UserPromptSubmit` event →
  `user_turn_seq.py` (INFRA-192/INFRA-248): a single delegated call to
  `user_turn_seq.record_user_turn(project_dir, data)`, no decision logic, no
  block/reason emission. Authorized state.json writes:
  `context_budget_user_turn_seq` and `context_budget_user_turn_seq_fingerprint`.
- `hooks/subagent_stop.py` — dispatches every `SubagentStop` event →
  `subagent_transcript.reconcile_one(project_dir, agent_id, payload)`
  (INFRA-298/CER-114): a single delegated call, no decision logic, no
  outcome parsing, no direct effort-database access, no block/decision
  emission. **Authorized state.json writes: none** — `reconcile_one` writes
  only to the effort database (via `effort_db.reconcile_attempt`) and to
  `.companion/effort_recording.log`, never to `state.json`.

These state.json writes are the designed write path for the context-budget
system — not pipe-contract violations. The `cwd` value used to locate
state.json comes from the Claude Code hook payload (trusted harness input),
not user-supplied input — do not flag it as path traversal.

Any logic added to these hooks beyond dispatch + delegation + emit, any
*other* hook importing from `skills/`, or any hook writing to spec files
remains CRITICAL. Any other hook that emits a decision-block response is CRITICAL.

### 2. PIPE CONTRACT (CRITICAL if violated)

Do all hook scripts write only to the single hardcoded pipe path
(`os.path.join(tempfile.gettempdir(), "companion.pipe")`, the same
convention `post_tool_use.py` established)? (INFRA-238) The `pipe_path`
state.json key was retired by `pairmode_migrate.py`'s `to-030` step and no
hook script reads it any longer.

Do any hook scripts write directly to spec files or `.companion/` directories?

Direct spec writes from hooks are CRITICAL.

### 3. SPEC SAFETY (CRITICAL if violated)

Do only sidebar.py and skill scripts write to spec/openspec files?

Anything else writing to spec files is CRITICAL.

### 4. CREDENTIAL EXPOSURE (CRITICAL if violated)

Does any code log, print, write to a file, or return in a response the contents of:
- `$HOME/.flex/auth.json` or any auth token file
- `CLAUDE_CODE_OAUTH_TOKEN` environment variable
- Any string matching `sk-ant-oat01-` (Anthropic API key patterns)
- Any other secret, credential, or private key value

Check all scripts in `hooks/` and all files touched in the diff.

### 5. PATH TRAVERSAL (HIGH if violated)

Does any code construct file paths using user-supplied input without sanitization?

All file operations that accept external input should use `Path.resolve()` and
verify the result stays within an expected root directory before writing.

Check for: string concatenation with user input, `open(user_input)`, path joins
without sanitization, `..` traversal opportunities.

### 6. LAYER VIOLATION (HIGH if violated)

Does any hook script import from `skills/` beyond the documented thin-delegation
exceptions in check 1?
Does any skill script directly modify files in `hooks/`?

Hooks may not import from skills. The boundary in `hooks/` is import-free from
the skills layer. Check all `import` statements in `hooks/` scripts; the four
dispatcher hooks listed in check 1 are explicitly excluded from this check.

### 7. DATA-FLOW INTEGRITY (HIGH if violated; CRITICAL on silent data loss)

Scope: the **phase diff at checkpoint** (declared input 1) — not a single
story's diff. This check exists for the *cross-story* case the per-story
reviewer (reviewer `procedure.md` item 13) structurally cannot see: a writer
added in story N whose reader was supposed to arrive in story N+2 and never
did. For each piece of persistent state the phase diff introduces or changes,
trace producers against consumers using the same four sub-checks the reviewer
uses (same vocabulary, deliberately — the two procedures must not drift into
two labels for one defect class):

- **written-never-read** — state the phase persists that nothing reads.
- **required-never-written** — a read path depending on a shape or value no
  current writer produces.
- **duplicate state** — the same fact stored in two places with independent
  writers, or the same event with two producers, and no reconciliation.
- **half-implementation** — an unreachable-in-practice branch, or a producer
  whose consumer never landed within the phase.

Severity is tied to data loss, not style: a mismatch that causes state to be
**silently discarded, silently duplicated, or silently never recorded** is
CRITICAL — it is a data-corruption risk under this procedure's own severity
definition (§ Severity classification). A merely-inert field is HIGH or below.
Exemplars: CER-104's double effort-row insert (two independently-registered
PostToolUse hooks both firing) is the CRITICAL shape; `attempts.agent_id`
(persisted, read by nothing) is the non-CRITICAL shape.

---

## Audit scope (BUILD-041)

Findings in installed pairmode plugin infrastructure — the plugin's `hooks/`
directory and `skills/pairmode/` — that are **not part of this project's phase
diff** are reported as INFORMATIONAL. They do not count toward the checkpoint's
CRITICAL/HIGH totals and do not affect the PASS/FAIL result.

Only findings in the project's own changed files determine PASS/FAIL. If plugin
infrastructure issues are found, note them for upstream (flex) investigation.

---

## Report format

```
SECURITY AUDIT — [Phase/Story ID]
Scanned: [directories/files scanned]
Date: [date]

FINDINGS
  [CRITICAL/HIGH/MEDIUM/LOW] — [check name]
  File: [path:line]
  Description: [what was found]
  Impact: [what could go wrong]

SUMMARY
  CRITICAL: [N]
  HIGH: [N]
  MEDIUM: [N]
  LOW: [N]
  Overall: PASS (0 CRITICAL, 0 HIGH) / FAIL
```

PASS = zero CRITICAL and zero HIGH findings.

If no findings: `SECURITY AUDIT PASS — no findings at any severity level.`

---

## Severity classification

```
CRITICAL = architecture violation or data corruption / secret exposure risk
HIGH     = correctness or integrity issue (path traversal, layer violation)
MEDIUM   = quality or portability concern
LOW      = style or minor concern
```

Use `PASS / FAIL — [check name]` output format for each checklist item.

---

## Decision

### PASS conditions

All of the following must be true:
- No CRITICAL findings
- No HIGH findings

### FAIL conditions

Any CRITICAL or HIGH finding.

---

## Return format

Return a JSON object conforming to the `REVIEW-RESULT` schema (WORKER-004 grammar):

```json
{
  "type": "REVIEW-RESULT",
  "verdict": "PASS",
  "findings": [],
  "reason": "One sentence: security audit passed with no CRITICAL or HIGH findings."
}
```

On failure:

```json
{
  "type": "REVIEW-RESULT",
  "verdict": "FAIL",
  "findings": ["CRITICAL: hooks/stop.py imports from skills/ — layer violation", "HIGH: ..."],
  "reason": "One sentence describing the blocking finding(s)."
}
```

Fields:
- `type` — always `"REVIEW-RESULT"`
- `verdict` — `"PASS"` if no CRITICAL/HIGH findings; `"FAIL"` if any CRITICAL/HIGH
- `findings` — list of finding strings (empty on PASS; one entry per CRITICAL/HIGH finding on FAIL)
- `reason` — one sentence: for PASS, what was audited; for FAIL, what blocked it

Return only the JSON object. No preamble, no commentary, no usage block.

---

## Non-negotiables

- Never read beyond the three declared input categories (DP1.3): diff, story spec, hooks/.
- Never write, edit, or fix code — report findings only.
- Return value must be valid `REVIEW-RESULT` JSON (parseable by `worker_result.py`).
- The old `.claude/agents/security-auditor.md` and its `.md.j2` template remain in place
  during the advisory window; do not remove them.
