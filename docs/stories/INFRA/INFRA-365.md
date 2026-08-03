---
id: INFRA-365
rail: INFRA
title: Fix shadow-reviewer suggestions-file scope_guard block (checkpoint-security finding)
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase-118 checkpoint-security audit (HIGH finding): `skills/pairmode/skills/shadow-reviewer/procedure.md:67-70`
declares `<worktree>/.pairmode-suggestions.md` as the shadow-reviewer's sole output channel, but
`skills/pairmode/scripts/scope_guard.py:210` denies it. During a build the shadow-reviewer runs in
the story worktree, so `resolve_call_story` returns the active story ID; `.pairmode-suggestions.md`
is deliberately not in the story's `primary_files`/`touches` (it is gitignored and excluded from
story artifacts, INFRA-358), is not in `STANDING_SURFACES` (`scope_guard.py:55-58`), and
`pre_tool_use.py` routes every `Edit`/`Write` through `check_path` with no agent_type exemption.
Every `Write` the shadow-reviewer issues returns `not in story scope for <ID>: .pairmode-suggestions.md`
— the producer added by INFRA-358/359 cannot fire in live dispatch. INFRA-360's integration test does
not catch this because `tests/pairmode/test_next_action.py:3636` and `:3737` write the file with
`Path.write_text` directly, bypassing the hook and the enforcement layer entirely.

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
