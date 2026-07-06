# CLAUDE.md — flex

## Project context

flex — a Claude Code plugin whose primary feature is **pairmode**: a
structured builder/reviewer workflow with effort tracking, per-story schema
gates, context budget checks, and model selection per attempt. The companion
memory layer (sidebar, `spec.json`, lessons) is the supporting infrastructure
that pairmode sits on top of.

Stack: Python 3.11+ / uv / Rich (TUI) / Anthropic SDK.

Pairmode is shipped and in continuous use on this repo. Current build activity
lives in numbered phase files under `/docs/phases/`; see
`/docs/phases/index.md` for the current phase.

Build sessions are governed by `CLAUDE.build.md`; all other input applies the reviewer role.

## Review checklist

Apply the checklist in the reviewer procedure skill.
See `skills/pairmode/skills/reviewer/procedure.md`.

## Review output format

PASS / FAIL — [check name]
If FAIL: file:line — description — severity: CRITICAL / HIGH / MEDIUM / LOW

Summary: N passed, M failed. Overall: PASS / FAIL

CRITICAL = architecture violation or data corruption risk. Blocks story completion.
HIGH     = correctness or integrity issue. Fix before checkpoint.
MEDIUM   = quality or portability issue. Fix before phase end.
LOW      = style or minor concern. Fix when convenient.

## Story test verification

After the checklist, run the tests for the story:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q 2>&1 | tail -30
```

Report the result as part of your review output. A story with failing tests is not complete.

If no test file exists and the story was documentation/template-only: state
`TEST RUN: documentation story — no test file expected`.
If no test file exists and the story included logic: HIGH severity finding.

## Loop-breaker mode

Invoked with: LOOP-BREAKER: [error] | FILE: [file:line] | TRIED: [what failed]

- Ignore the previous approach entirely
- Analyse the error cold, from first principles
- Propose ONE alternative approach with clear reasoning
- Do not reproduce the failing code
- If the error involves a protected file, say so and propose a different path
