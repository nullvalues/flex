---
id: BUILD-041
rail: BUILD
title: "security-auditor: add pairmode hook exceptions + audit scope rule"
status: complete
phase: "82"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/agents/security-auditor.md.j2
touches:
  - .claude/agents/security-auditor.md
---

# BUILD-041 — security-auditor: add pairmode hook exceptions + audit scope rule

## Context

The security-auditor agent (template and live file) contains stale hook-integrity
rules that predate the thin-delegation exceptions introduced across CER-027 through
Phase 68. The live rules still state:

> "A hook that does anything other than relay to the pipe is a CRITICAL violation."

This is no longer accurate. Three hooks are documented thin dispatchers with
explicitly authorized imports and state.json writes:

- `hooks/pre_tool_use.py` — dispatches Task/Agent → `context_budget.py` (CER-027/CER-049)
  and Edit/Write → `scope_guard.py` (Phase 55). Authorized state.json write:
  `context_budget_acknowledged_at` on block.
- `hooks/post_tool_use.py` — dispatches Write/Edit/MultiEdit → pipe relay;
  Task/Agent → `context_budget.py` (INFRA-182). Authorized state.json writes:
  `context_current_tokens`, `context_current_tokens_recorded_at`.
- `hooks/session_start.py` — dispatches source `clear`/`startup` → `session_reset.py`
  (CER-047/INFRA-175). Authorized state.json writes: `context_current_tokens`,
  `context_current_tokens_recorded_at`, `context_session_reset_at`.

These are all documented in flex's CLAUDE.md review checklist item 1, but the
auditor agent has not been updated to match.

**Consequence:** any pairmode-bootstrapped project running the security-auditor at
checkpoint time (including radar) flags 6 CRITICAL findings and 1 HIGH finding in
the pairmode infrastructure hooks — false positives that block every downstream
checkpoint. Confirmed in radar Phase MU010 audit (2026-07-01).

There is also a second gap: neither the template nor the live file contain an
**audit-scope rule**. The auditor currently reports findings in installed plugin
infrastructure (the flex `hooks/` directory living on the developer's machine,
outside the project's own diff) at the same severity level as findings in the
project's own changed code. Plugin infrastructure findings should be reported as
INFORMATIONAL and excluded from the checkpoint PASS/FAIL tally.

Additionally, the live file `.claude/agents/security-auditor.md` lists the wrong
hook files in check 1 (`hooks/stop.py`, `hooks/exit_plan_mode.py`,
`hooks/session_end.py`) and omits `hooks/pre_tool_use.py` and
`hooks/session_start.py` — the two hooks that actually contain dispatch logic.

## Acceptance criteria

1. In `skills/pairmode/templates/agents/security-auditor.md.j2`, **check 1 (HOOK
   INTEGRITY)** is rewritten to:
   - Name the actual hooks to check (all five: `pre_tool_use.py`,
     `post_tool_use.py`, `session_start.py`, `stop.py`, and `exit_plan_mode.py`).
   - Add a **Documented thin-delegation exceptions** block that enumerates all
     three authorized dispatchers with their authorized imports, authorized
     state.json write keys, and source references (CER-027/CER-049, INFRA-182,
     CER-047/INFRA-175).
   - State that `cwd`-derived state.json path construction in hook payloads is
     not flaggable as path traversal — `cwd` comes from the Claude Code harness,
     not user/network input.
   - Retain the rule that any logic beyond dispatch + delegation + emit, any
     *other* hook importing from `skills/`, and any hook writing to spec files
     remains CRITICAL.

2. In the same template, **check 5 (LAYER VIOLATION)** is updated to match: hooks
   listed in check 1's exception block are explicitly excluded from the layer-
   violation flag.

3. A new **Audit scope** section is added to the template (after the priorities
   list, before the report format) stating:
   - Findings in installed pairmode plugin infrastructure (the plugin's `hooks/`
     and `skills/pairmode/`) that are **not part of this project's phase diff**
     are reported as INFORMATIONAL and do not count toward the checkpoint's
     CRITICAL/HIGH totals or PASS/FAIL result.
   - Only findings in the project's own changed files determine PASS/FAIL.

4. `.claude/agents/security-auditor.md` (the flex live file) receives equivalent
   edits:
   - Check 1 hook list corrected to `hooks/pre_tool_use.py`,
     `hooks/post_tool_use.py`, `hooks/session_start.py`, `hooks/stop.py`,
     `hooks/exit_plan_mode.py`.
   - Same thin-delegation exceptions block added.
   - Same audit-scope section added.
   - Check 5 updated to match.

5. No other section of either file changes.

## Implementation guidance

- In the `.j2` template, check 1 currently reads:
  ```
  Do any files in `hooks/` make network calls, import from `skills/`, or write to
  any location other than `/tmp/companion.pipe`?

  A hook that does anything other than relay to the pipe is a CRITICAL violation.
  ```
  Replace with the new text (see below). The template uses no Jinja variables in
  check 1 or check 5, so no variable plumbing is needed.

- In the live file, check 1 currently lists four hook files and says the same
  rule verbatim. Replace with the corrected list and new rule text.

**Draft text for check 1 (both files):**

```markdown
### 1. HOOK INTEGRITY (CRITICAL if violated)

Do any files in `hooks/` make network calls, or contain domain logic beyond
tool-name / source dispatch, one delegated module call, and one emit?

Check every import and every file write in:
`hooks/pre_tool_use.py`, `hooks/post_tool_use.py`, `hooks/session_start.py`,
`hooks/stop.py`, `hooks/exit_plan_mode.py`

**Documented thin-delegation exceptions — do NOT flag these:**

The following hooks are authorized thin dispatchers with permitted imports and
state.json writes. They do not violate the thin-relay contract.

- `hooks/pre_tool_use.py` — dispatches Task/Agent → `context_budget.py`
  (CER-027/CER-049) and Edit/Write → `scope_guard.py` (Phase 55). Authorized
  state.json write: `context_budget_acknowledged_at` (on block only).
- `hooks/post_tool_use.py` — pipe relay for Write/Edit/MultiEdit; dispatches
  Task/Agent → `context_budget.py` (INFRA-182). Authorized state.json writes:
  `context_current_tokens`, `context_current_tokens_recorded_at`.
- `hooks/session_start.py` — dispatches source `clear`/`startup` →
  `session_reset.py` (CER-047/INFRA-175). Authorized state.json writes:
  `context_current_tokens`, `context_current_tokens_recorded_at`,
  `context_session_reset_at`.

These state.json writes are the designed write path for the context-budget
system — not pipe-contract violations. The `cwd` value used to locate
state.json comes from the Claude Code hook payload (trusted harness input),
not user-supplied input — do not flag it as path traversal.

Any logic added to these hooks beyond dispatch + delegation + emit, any
*other* hook importing from `skills/`, or any hook writing to spec files
remains CRITICAL.
```

**Draft text for check 5 update:**

```markdown
### 5. LAYER VIOLATION (HIGH if violated)

Does any hook script import from `skills/` beyond the documented thin-delegation
exceptions in check 1?
Does any skill script directly modify files in `hooks/`?

Check all imports in `hooks/` scripts; the three dispatcher hooks listed in
check 1 are explicitly excluded from this check.
```

**Draft text for the audit scope section (insert after check 6, before report format):**

```markdown
---

## Audit scope

Findings in installed pairmode plugin infrastructure — the plugin's `hooks/`
directory and `skills/pairmode/` — that are **not part of this project's phase
diff** are reported as INFORMATIONAL. They do not count toward the checkpoint's
CRITICAL/HIGH totals and do not affect the PASS/FAIL result.

Only findings in the project's own changed files determine PASS/FAIL. If plugin
infrastructure issues are found, note them for upstream (flex) investigation.
```

## Tests

Documentation/template story — no logic module changed, no test file expected.
Reviewer states `TEST RUN: documentation story — no test file expected`.

Manual verification:

```bash
# Confirm exceptions block present in template
grep -n "thin-delegation exceptions" \
  skills/pairmode/templates/agents/security-auditor.md.j2

# Confirm audit scope section present in template
grep -n "Audit scope" \
  skills/pairmode/templates/agents/security-auditor.md.j2

# Confirm live file updated with corrected hook list
grep -n "pre_tool_use\|session_start" .claude/agents/security-auditor.md

# Confirm live file has exceptions block
grep -n "thin-delegation exceptions" .claude/agents/security-auditor.md

# Confirm live file has audit scope section
grep -n "Audit scope" .claude/agents/security-auditor.md
```

## Out of scope

- Modifying any other hook or skill script.
- Changes to `CLAUDE.md` checklist item 1 (already correct and authoritative).
- Propagating the updated template to downstream projects (radar etc.) via
  `pairmode sync` — that is the downstream operator's responsibility after this
  story lands. The fix to radar's blocked checkpoint can be applied immediately
  by the operator as a documented false-positive override referencing flex
  CLAUDE.md checklist item 1.
