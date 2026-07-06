---
id: INFRA-201
rail: INFRA
title: "Backlog hygiene: mark CER-013/015/032/033/052 resolved"
status: draft
phase: "HARNESS011-main"
story_class: documentation
auth_gated: false
schema_introduces: false
primary_files:
  - docs/cer/backlog.md
touches: []
---

## Acceptance criterion

- **CER-013, CER-015, CER-032, CER-033, CER-052** each have a `**RESOLVED ...**` note
  appended to their backlog entry explaining why they are resolved by Era 3 work.
- The resolution notes are accurate (verified against the current harness branch state).
- No other backlog entries are modified.
- `TEST RUN: documentation story — no test file expected`.

## Instructions

Append a `**RESOLVED ...**` note to each of the five entries in `docs/cer/backlog.md`:

- **CER-013**: `**RESOLVED cp-HARNESS001-main / HARNESS006-main — CLAUDE.build.md.j2 was rewritten from scratch as the thin dispatch loop; the fallback-policy pointer is not relevant to the thin-loop template and was intentionally omitted.**`
- **CER-015**: `**RESOLVED cp-HARNESS006-main — The thin dispatch loop template has no record_attempt.py example; the hardcoded placeholder literals are absent from the rewritten template.**`
- **CER-032**: `**RESOLVED cp-HARNESS006-main — The thin dispatch loop template has no record_attempt.py or extended usage block; the missing columns finding does not apply to the rewritten template.**`
- **CER-033**: `**RESOLVED cp-HARNESS002-main — builder.md.j2, reviewer.md.j2, .claude/agents/builder.md, and .claude/agents/reviewer.md were deleted by the dogfood flip (HARNESS-002); the legacy verbose output blocks no longer exist.**`
- **CER-052**: `**RESOLVED cp-HARNESS009-main (Phase 75) — _derive_transcript_path() applies is_relative_to((home / ".claude").resolve()) at context_budget.py:116; the containment check is live. Resolved note was not written at checkpoint time.**`
