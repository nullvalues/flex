---
id: BUILD-013
rail: BUILD
title: Minimal agent return surface
status: complete
phase: "52"
story_class: methodology
primary_files:
  - CLAUDE.build.md
  - CLAUDE.build.md.j2
  - .claude/agents/builder.md
  - .claude/agents/reviewer.md
touches:
  - skills/pairmode/templates/agents/builder.md.j2
  - skills/pairmode/templates/agents/reviewer.md.j2
---

# BUILD-013 — Minimal agent return surface

## Background

Builder and reviewer agents currently return their full output to the
orchestrator: implementation notes, checklist results, test output, and commit
messages. The orchestrator reads and summarises these, accumulating per-story
content in its context. After a few stories, most of the orchestrator's context
window is prior agent output that has no routing value.

The orchestrator needs only two things from each agent: did it succeed, and how
many tokens did it use. Everything else — checklist detail, test output,
implementation notes — belongs inside the agent's own context and should not be
returned.

## Ensures

- Builders end their output with a structured result block:
  ```
  BUILD-RESULT: DONE
  SUMMARY: [one sentence — what was implemented]
  <usage>...</usage>
  ```
- Reviewers end their output with a structured result block:
  ```
  REVIEW-RESULT: PASS
  SUMMARY: [one sentence — what passed]
  <usage>...</usage>
  ```
  or on failure:
  ```
  REVIEW-RESULT: FAIL
  SUMMARY: [one sentence — what blocked, e.g. "test_context_health_cli failed"]
  <usage>...</usage>
  ```
- `CLAUDE.build.md` Step 1 parses `BUILD-RESULT` and `SUMMARY` only from the
  builder's return. It does not read or summarise any other builder output.
- `CLAUDE.build.md` Step 2 parses `REVIEW-RESULT` and `SUMMARY` only. The
  `<usage>` block is still extracted for `record_attempt.py`.
- Both agent prompts explicitly state: "Your full checklist / implementation
  detail is for your own use. Do not include it in the final output to the
  orchestrator. End with the structured result block only."
- `CLAUDE.build.md.j2` and both agent `.j2` templates updated to match.

## Out of scope

- Changes to what the orchestrator passes to agents (BUILD-012).
- The `/context` gate (BUILD-014).
- Changes to `record_attempt.py` — it still receives the same `<usage>` fields.

## Instructions

### 1. Update `agents/builder.md`

Add at the end of the builder instructions:

```
## Final output to orchestrator

Your checklist, implementation notes, and test output are for your own use.
Do not include them in your final message to the orchestrator.

End your final message with exactly:

BUILD-RESULT: DONE
SUMMARY: [one sentence describing what was implemented]
<usage>
total_tokens: N
...
</usage>
```

### 2. Update `agents/reviewer.md`

Add at the end of the reviewer instructions:

```
## Final output to orchestrator

Your checklist results and test output are for your own use.
Do not include them in your final message to the orchestrator.

End your final message with exactly:

REVIEW-RESULT: PASS
SUMMARY: [one sentence — what passed and was committed]
<usage>
total_tokens: N
...
</usage>

Or on failure:

REVIEW-RESULT: FAIL
SUMMARY: [one sentence — what blocked, e.g. which test failed or which check]
<usage>
total_tokens: N
...
</usage>
```

### 3. Update `CLAUDE.build.md` Steps 1 and 2

Step 1 parse block: replace "parse its tool-result for the `<usage>` block"
with "parse `BUILD-RESULT`, `SUMMARY`, and the `<usage>` block. Discard all
other builder output."

Step 2 parse block: replace "parse its final message for the same `<usage>`
block" with "parse `REVIEW-RESULT`, `SUMMARY`, and the `<usage>` block.
`REVIEW-RESULT: PASS` means committed; `REVIEW-RESULT: FAIL` means reverted."

### 4. Update both `.j2` templates

Mirror all changes to the Jinja2 templates.

## Tests

`TEST RUN: methodology story — no logic module.`

Acceptance verified by: orchestrator output showing only the structured result
block parsed from agent returns, with no checklist or implementation detail
appearing in orchestrator context.
