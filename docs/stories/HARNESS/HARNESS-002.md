---
id: HARNESS-002
rail: HARNESS
title: Dogfood flip — apply thin loop + retire agent templates
status: complete
phase: "HARNESS006-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/agents/
  - tests/pairmode/test_flip_dogfood.py
touches:
  - .claude/agents/
---

## Context

The dogfood flip (agreements HARNESS006-main.md DP2): apply the reduced template to flex's own
`CLAUDE.build.md` and retire the old per-project agent `.md.j2` templates. After this story,
flex builds itself using the thin dispatch loop. The end-to-end dogfood verification (one story
arc on the new loop) is recorded as part of this story's acceptance.

> Note: this story legitimately modifies the live `CLAUDE.build.md` and deletes files under
> `skills/pairmode/templates/agents/` and `.claude/agents/`. These are protected/sensitive paths;
> the modification is the *purpose* of this story. The reviewer enforces the explicit declaration.

## Requires

- HARNESS-001 complete: the reduced `.j2` template exists.
- All leaf workers present: WORKER-004 through WORKER-014, RESOLVER-007 through RESOLVER-009.

## Ensures

- **`CLAUDE.build.md` (flex's own)** is updated to the thin dispatch loop by running
  `flex_build.py sync-build --apply --project-dir .` (or equivalent manual apply). The result
  must match the HARNESS-001 template output within Jinja2 variable substitution.
- **Old agent `.md.j2` source templates removed** from `skills/pairmode/templates/agents/`:
  `builder.md.j2`, `reviewer.md.j2`, `loop-breaker.md.j2`, `security-auditor.md.j2`,
  `intent-reviewer.md.j2`. (`reconstruction-agent.md.j2` is NOT removed.)
- **Old rendered agent files removed** from `.claude/agents/`:
  `builder.md`, `reviewer.md`, `loop-breaker.md`, `security-auditor.md`, `intent-reviewer.md`.
  (`.claude/agents/reconstruction-agent.md` is NOT removed.)
- **`sync-agents` updated** to render the new `-worker` shell files (if applicable) instead of
  the old agent `.md.j2` templates. At minimum, `sync-agents` must not error on the removal.
- **End-to-end dogfood arc**: one story from the current plan is built through a complete
  build-loop iteration using the new `CLAUDE.build.md`. The arc is recorded as a note in the
  story `## Context` or a file at `docs/dogfood-HARNESS-002.md`. The arc must complete without
  requiring a manual intervention to restore the old loop.
- **`tests/pairmode/test_flip_dogfood.py`** asserts deterministically:
  - The live `CLAUDE.build.md` is ≤40 non-blank lines (same line-count gate as HARNESS-001).
  - The live `CLAUDE.build.md` contains "next-action".
  - `skills/pairmode/templates/agents/builder.md.j2` does NOT exist.
  - `.claude/agents/builder.md` does NOT exist.
  - `skills/pairmode/skills/builder/procedure.md` DOES exist (the replacement).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes on the new loop.

## Instructions

- Run `sync-build --apply` (or the equivalent manual copy of the template rendered output) to
  update `CLAUDE.build.md`. Verify the result matches the HARNESS-001 template.
- Remove the five old `.md.j2` template files and five old rendered `.claude/agents/*.md` files.
  Git-track the deletions.
- If `sync-agents` references the removed `.md.j2` templates, update its template list to
  reference the new procedure skill shells (or skip those agent types if sync-agents is not yet
  adapted to the leaf-worker pattern — that adaptation can be a HARNESS-002 touch).
- The dogfood arc: build the next planned story (whichever is next after HARNESS-002 in the
  phase) using the new `CLAUDE.build.md`. Record the outcome.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flip_dogfood.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: live `CLAUDE.build.md` reduced to ≤40 lines; legacy agent templates + rendered files
removed; procedure skills are the rendered set; `ACTIONS` fully covered; full suite green;
end-to-end arc recorded.

### Out of scope

- `expected_step_tokens` re-source — HARNESS-003.
- Version finalize / Signal-1 / RELEASE-002 reconcile / the git fold — RELEASE-007 + operator.
- Fleet Phases 2–3 migration (operator, post-fold).
- `reconstruction-agent` — not removed.
