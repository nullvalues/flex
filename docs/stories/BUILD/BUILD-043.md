---
id: BUILD-043
rail: BUILD
title: "Reviewer FAIL reason capture via --notes"
status: complete
phase: "83"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/agents/reviewer.md.j2
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - .claude/agents/reviewer.md
  - tests/pairmode/test_flex_build.py
---

## Requires

- `record_attempt.py` already accepts `--notes TEXT` (the option is declared and passed through to `effort_db.insert_attempt`).
- The `notes` column already exists in the `attempts` table (`skills/pairmode/scripts/effort_db.py`).
- The reviewer template (`skills/pairmode/templates/agents/reviewer.md.j2`) exists; its FAIL path runs `git checkout .` with no cause emission before reverting.

## Ensures

- `grep -n "Before reverting, emit one line" skills/pairmode/templates/agents/reviewer.md.j2` returns at least one match.
- `grep -n "FAIL-CAUSE:" skills/pairmode/templates/agents/reviewer.md.j2` returns at least one match appearing before `git checkout` in line order.
- `grep -n "Before reverting, emit one line" .claude/agents/reviewer.md` returns at least one match (live flex reviewer updated).
- `grep -n "FAIL-CAUSE" skills/pairmode/templates/CLAUDE.build.md.j2` returns at least one match.
- `grep -n "\-\-notes" skills/pairmode/templates/CLAUDE.build.md.j2` returns a match in proximity to `--outcome FAIL` (within the same reviewer record_attempt block).

## Instructions

**1. Update `skills/pairmode/templates/agents/reviewer.md.j2` — FAIL path.**

In the FAIL decision block (before the `git checkout .` revert command), insert:

```markdown
Before reverting, emit one line summarising the blocking cause in this exact format:

FAIL-CAUSE: [concise reason — 10 words or fewer]

Examples:
  FAIL-CAUSE: undeclared file: docs/architecture.md
  FAIL-CAUSE: hallucinated route: /api/portal/treatment-plans
  FAIL-CAUSE: suite red: downstream breakage from prior story
  FAIL-CAUSE: missing ## Ensures section
  FAIL-CAUSE: CRITICAL hook violation in hooks/pre_tool_use.py

Emit the FAIL-CAUSE line before the revert command below. The orchestrator
parses this line to record the reason in the effort DB.
```

Do not change any other section of the template.

**2. Update `.claude/agents/reviewer.md` (live flex reviewer).**

Apply the identical insertion to the FAIL path in the live file, before its `git checkout .` command.

**3. Update `skills/pairmode/templates/CLAUDE.build.md.j2` — Step 2 reviewer result block.**

After the reviewer returns, the orchestrator now parses a `FAIL-CAUSE:` line in addition to `REVIEW-RESULT` and `SUMMARY`. Update the FAIL handling block:

- Extract `fail_cause` from the reviewer output: the value of the `FAIL-CAUSE:` line, or empty string if absent.
- In the `record_attempt.py` invocation for the reviewer on FAIL, append `--notes "$fail_cause"` after `--outcome FAIL`.

Example updated invocation comment in the template:

```bash
# On FAIL: capture FAIL-CAUSE and pass as --notes
# fail_cause=$(line starting with "FAIL-CAUSE:" from reviewer output, stripped of prefix, or "")
PATH=$HOME/.local/bin:$PATH uv run python {{ pairmode_scripts_dir }}/record_attempt.py \
  --story-file docs/stories/RAIL/RAIL-NNN.md \
  --agent-role reviewer \
  --model claude-sonnet-4-6 \
  --attempt-number 1 \
  --outcome FAIL \
  --notes "$fail_cause" \
  --model-selection-reason $reason \
  --project-dir .
```

**4. No changes to `record_attempt.py` or `effort_db.py`** — both already support `--notes`.

## Tests

Add to `tests/pairmode/test_flex_build.py`:

- `test_reviewer_template_contains_fail_cause_instruction` — read `skills/pairmode/templates/agents/reviewer.md.j2`; assert `"Before reverting, emit one line"` is present; assert `"FAIL-CAUSE:"` appears before `"git checkout"` by line number.
- `test_build_template_passes_notes_on_reviewer_fail` — read `skills/pairmode/templates/CLAUDE.build.md.j2`; assert `"--notes"` appears in proximity to `"FAIL"` (both within the same 30-line window or via regex).
- `test_live_reviewer_contains_fail_cause_instruction` — read `.claude/agents/reviewer.md`; assert `"Before reverting, emit one line"` is present.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build.py -x -q -k "fail_cause or fail_notes"
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
