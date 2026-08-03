---
id: INFRA-374
rail: INFRA
title: Wire the missing context_current_tokens_source writer in post_tool_use.py (CER-135)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-135 (LOW): `context_current_tokens_source` (introduced by INFRA-321 § C6) has only two of its
three intended writers stamped — `user_turn_seq.record_user_turn()` (stamps
`"user-prompt-submit"`) and `flex_build.py`'s `set-context-tokens`/`bump-context-tokens` (stamps
`"manual"`). The third and highest-frequency writer, `hooks/post_tool_use.py`'s Task/Agent branch —
the write path that runs after every builder/reviewer/auditor spawn — does not stamp
`"post-tool-use"`, because `hooks/**` is a protected path and INFRA-321 explicitly named this edit
as the one exception requiring a hook change, instructing the builder to report `BUILDER BLOCKED`
rather than touch it directly (which is what happened). Consequence is observability-only: a
`context_current_tokens` value most recently written by PostToolUse currently carries no source
stamp, and `context_budget.decide()` doesn't gate on this field either way, so there's no
functional gap. Fix direction: a small hook-scoped story adding the one-line stamp
(`state["context_current_tokens_source"] = "post-tool-use"`) inside `post_tool_use.py`'s existing
Task/Agent read-modify-write, mirroring the write already added to `user_turn_seq.record_user_turn`,
plus a regression test asserting the stamp appears after a Task/Agent PostToolUse observation.
File: `hooks/post_tool_use.py`.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires
<!-- Prior stories, system state, or file conditions that must hold before building. -->

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

## Instructions

## Tests
