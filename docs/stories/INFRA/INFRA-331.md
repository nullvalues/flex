---
id: INFRA-331
rail: INFRA
title: Agent registration completeness — spec-writer template; register spec-writer/docs-reviewer/gate-worker in dispatch
status: draft
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/agents/spec-writer.md.j2
  - CLAUDE.build.md
touches:
  - skills/pairmode/scripts/bootstrap.py
  - skills/pairmode/scripts/audit.py
  - .claude/agents/spec-writer.md
  - .claude/agents/docs-reviewer.md
  - .claude/agents/gate-worker.md
  - tests/pairmode/test_bootstrap.py
  - tests/pairmode/test_procedure_skills.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-137 (AG-13, `docs/closeout-agreements-20260729.md`): three of the eight
`templates/agents/` roles are not dispatchable. `spec-writer` has a
fully-specced procedure (`skills/pairmode/skills/spec-writer/procedure.md`,
WORKER-013) and a live, non-advisory dispatch action — `next_action.py`'s
`ACTIONS`/`_SPAWN_ACTIONS` include `spawn-spec-writer`, and `resolve_next_action`
Row-2 emits it (model="opus", reason="needs-spec") for any stub story — but
no `templates/agents/spec-writer.md.j2` was ever written, so the role has no
shell to scaffold. `docs-reviewer` (`docs-reviewer.md.j2`, INFRA-325) and
`gate-worker` (`gate-worker.md.j2`, RELEASE-010) do have templates and are
both in `bootstrap.py`'s `AGENT_FILES` list (`bootstrap.py:91-99`) — but
neither file exists in flex's own `.claude/agents/`, confirmed live this
session (only `builder.md`, `intent-reviewer.md`, `loop-breaker.md`,
`reconstruction-agent.md`, `reviewer.md`, `security-auditor.md` are present).
`CLAUDE.build.md`'s `ACTION_SUBAGENT_TYPE` map has an entry for
`checkpoint-docs → docs-reviewer` but none for `spawn-gate-worker` or
`spawn-spec-writer` at all.

Live consequence, same session: dispatching this phase's own
`checkpoint-docs` step fell back to a generic `claude` subagent because
`docs-reviewer` was not an available Agent-tool type.

This story fixes the **template and dispatch-map** side of the gap only.
Backfilling the missing files into flex's own (and other already-bootstrapped
projects') `.claude/agents/` is INFRA-332 — a fixed template alone does not
reach an existing project (CER-138); do not attempt any sync/backfill
mechanism in this story.

## Requires

1. `docs-reviewer.md.j2` (`templates/agents/docs-reviewer.md.j2`) as the
   structural exemplar for the new `spec-writer.md.j2` — same frontmatter
   shape, same "Inputs / Procedure / Return" body structure, same absolute
   procedure-path rendering via `pairmode_scripts_dir` (INFRA-304 pattern —
   do not hardcode a relative path).
2. `skills/pairmode/skills/spec-writer/procedure.md` — read it in full before
   writing the shell; the shell's Inputs/Return sections must match what the
   procedure actually declares (bounded inputs: stub story file, phase doc,
   active era doc, one format exemplar; `SPEC-RESULT{status: "done"|"revised"}`
   return per `docs/architecture.md:47-48`).
3. `bootstrap.py`'s `AGENT_FILES` list (`:91-99`) and its docstring comment
   block above it (`:75-90`) — add the ninth entry following the existing
   comment convention (the docs-reviewer comment explains why it was added;
   do the same for spec-writer).
4. `audit.py`'s `CANONICAL_FILES`-mirroring list (`:53`, per the comment at
   `:40` — "docs-reviewer.md ... is an eighth thin shell ... this list must
   stay mirrored with CANONICAL_FILES in audit.py") — add the ninth entry
   there too, in the same mirrored order as `bootstrap.py`.
5. `CLAUDE.build.md`'s `ACTION_SUBAGENT_TYPE` line — the single-line map
   literal near the top of the Build loop section. Add
   `spawn-gate-worker: gate-worker` and `spawn-spec-writer: spec-writer`.
6. Baseline suite count before starting (run `uv run pytest tests/pairmode/ -q --tb=no 2>&1 | tail -5`).

## Ensures

1. **`spec-writer.md.j2` exists** at `templates/agents/spec-writer.md.j2`,
   structurally matching `docs-reviewer.md.j2`'s pattern: `name: spec-writer`
   frontmatter, `tools:` scoped to what the spec-writer procedure actually
   needs (Read/Write/Edit/Bash/Grep/Glob — verify against the procedure, do
   not guess), a `model:` frontmatter default, a body that points at
   `{{ pairmode_scripts_dir }}/../../../skills/pairmode/skills/spec-writer/procedure.md`
   rendered absolute (not relative — INFRA-304's fixed pattern), and a
   "Return" section describing the `SPEC-RESULT` schema. **Correct signal:**
   the template renders without Jinja errors against a fixture context and
   the rendered output opens the correct absolute procedure path; **forbidden
   proxy:** a template that merely exists but omits the absolute-path
   rendering (would silently regress CER-122/INFRA-304's fix for the ninth
   shell).
2. **`bootstrap.py` scaffolds it.** `AGENT_FILES` gains
   `(".claude/agents/spec-writer.md", "agents/spec-writer.md.j2")`, and a
   fresh `bootstrap --apply` on a scratch fixture project produces
   `.claude/agents/spec-writer.md` alongside the existing eight.
3. **`audit.py` tracks it.** The mirrored list gains the matching entry; a
   fresh-bootstrapped fixture project audits clean (no MISSING finding for
   spec-writer, docs-reviewer, or gate-worker).
4. **`ACTION_SUBAGENT_TYPE` covers all eight spawn/checkpoint-shaped
   actions that map to a `templates/agents/` role, minus
   `reconstruction-agent`** (a separate skill, out of scope — do not add it;
   `spawn-reviewer` stays present per its existing CER-074 note that it is
   never emitted by `resolve_next_action` but remains in `ACTIONS` for
   orchestrator dispatch). Concretely: `spawn-gate-worker: gate-worker` and
   `spawn-spec-writer: spec-writer` are added; the six existing entries are
   unchanged.
5. **Regression test.** `tests/pairmode/test_procedure_skills.py` (or a
   parametrized extension of it, matching how it already covers the other
   six shells' procedure-pointer rendering per CER-122) gains spec-writer as
   a seventh covered shell.
6. **Suite green.** Full run without `-x`; baseline + added tests, no
   regressions.

## Instructions

1. Read `docs-reviewer.md.j2` and the spec-writer procedure first; do not
   invent the shell's tool list or Return schema from memory.
2. Add the template, then the three registration points (`bootstrap.py`,
   `audit.py`, `CLAUDE.build.md`) in that order — each is independently
   testable.
3. Do not touch `pairmode_sync.py` or attempt to backfill any already-
   bootstrapped project's `.claude/agents/` in this story — that is
   INFRA-332, deliberately sequenced after this one so the template exists
   first.
4. Do not add a `select_gate_worker_model`/`select_spec_writer_model`
   function to `model_selector.py` here — that is INFRA-333.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py tests/pairmode/test_procedure_skills.py tests/pairmode/test_templates.py -q 2>&1 | tail -15
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative check: grep
`.claude/agents/` post-fixture-bootstrap for exactly nine `.md` files
(eight existing + spec-writer), and grep `CLAUDE.build.md` for both new
`ACTION_SUBAGENT_TYPE` keys.

## Out of scope

- Backfilling flex's, flex-harness's, or any fleet project's existing
  `.claude/agents/` directory (INFRA-332).
- Any `model_selector.py` function or model-tier design for these three
  roles (INFRA-333).
- Any escalation-ladder change for any `story_class` (INFRA-334).
- The work→agent-type classification doc (INFRA-335).
- `reconstruction-agent` — separate skill, not part of this dispatch map.
