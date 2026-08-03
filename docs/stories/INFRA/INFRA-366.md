---
id: INFRA-366
rail: INFRA
title: Guard bootstrap's OPERATOR-010 extension write against silent overwrite (checkpoint-security finding)
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phase-118 checkpoint-security audit (HIGH finding): `skills/pairmode/scripts/bootstrap.py:1733`
writes `docs/narratives/OPERATOR/OPERATOR-010-project.md` with an unguarded
`operator_extension_dest.write_text(...)`. Every sibling write in the same function goes through
`_write_file` (`bootstrap.py:266-294`), which prompts `"{dest} already exists. Overwrite?"` and
returns `False` on decline. Re-running bootstrap against an existing project with a non-blank
`--operator-note` silently destroys a hand-extended `OPERATOR-010` narrative — a doc-of-record this
phase itself establishes (`docs/architecture.md` § Harness-role narratives) — while every other file
in the same run prompts. The `dry_run` branch is handled but the overwrite guard is not.

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
