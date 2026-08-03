---
id: INFRA-376
rail: INFRA
title: Close shadow-reviewer Bash-bypass and bootstrap operator-note escaping gaps (CER-163)
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

CER-163 (LOW): three sub-HIGH observations from the Phase-118 checkpoint-security re-audit, after
INFRA-365/366 closed the two HIGH findings: (1) flex's own `.claude/agents/shadow-reviewer.md` was
never synced via `sync-agents`, so the shadow-reviewer role INFRA-358/359 built is currently
unreachable in this repo's own checkout — a dogfood gap, not a downstream-project issue; (2) the
shadow-reviewer's agent-shell template (`skills/pairmode/templates/agents/shadow-reviewer.md.j2`)
grants `tools: [Read, Bash]`, so a real dispatched shadow-reviewer could append to
`.pairmode-suggestions.md` via a `Bash` heredoc/append instead of `Edit`/`Write`, bypassing
`scope_guard.py`'s `pre_tool_use.py` enforcement entirely — INFRA-365 only closed the `Edit`/`Write`
route; (3) `bootstrap.py` interpolates the free-text `--operator-note` CLI value into a
frontmatter-bearing markdown file (`OPERATOR-010-project.md`) unescaped, so a note containing `---`
or YAML-special characters could corrupt that file's frontmatter block. Files:
`.claude/agents/shadow-reviewer.md` (missing), `skills/pairmode/templates/agents/shadow-reviewer.md.j2`,
`skills/pairmode/scripts/bootstrap.py`.

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
