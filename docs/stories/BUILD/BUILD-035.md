---
id: BUILD-035
rail: BUILD
title: "orchestrator pre-flight offload: CLAUDE.build.md + template sync"
status: complete
phase: "78"
story_class: code
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches:
  - tests/pairmode/test_pairmode_sync.py
auth_gated: false
schema_introduces: false
---

# BUILD-035 — orchestrator pre-flight offload: CLAUDE.build.md + template sync

**Phase:** 78
**Rail:** BUILD

## Background

INFRA-184 and BUILD-034 deliver the infrastructure and CLIs. This story wires
them into the orchestrator by rewriting the three pre-story gate sections in
`CLAUDE.build.md` and its Jinja2 template. Once the template is updated,
`sync-build --apply` propagates the change to every registered upstream repo
automatically — no per-project manual edits.

Depends on INFRA-184 and BUILD-034.

## Ensures

1. The `## Auth check (conditional — per story)` section in `CLAUDE.build.md`
   is replaced with a single CLI call:
   ```
   PATH=$HOME/.local/bin:$PATH uv run python .../flex_build.py \
     check-auth-gate RAIL-NNN --project-dir .
   ```
   The orchestrator acts on exit code: 0 → proceed, 1 → stop and surface the
   printed block to the user, wait for resolution.

2. The `### Pre-story schema gate` section is replaced with:
   ```
   PATH=$HOME/.local/bin:$PATH uv run python .../flex_build.py \
     check-schema-gate RAIL-NNN --project-dir .
   ```
   Same exit-code protocol.

3. The `### Pre-story stub gate` section is replaced with:
   ```
   PATH=$HOME/.local/bin:$PATH uv run python .../flex_build.py \
     check-stub RAIL-NNN --project-dir .
   ```
   Same exit-code protocol.

4. In all three cases, the orchestrator prints the CLI's stdout verbatim when
   exit 1. It does not read the story file to compose its own message.

5. The same changes are applied to `CLAUDE.build.md.j2` so that upstream repos
   receive the offloaded pre-flight section when they run `sync-build --apply`.

6. `sync-build --dry-run` on a project with the old inline gate sections shows
   a non-empty diff (confirming the template change is detected).

7. `sync-build --apply` on a project with the old inline gate sections writes
   the updated `CLAUDE.build.md` with the CLI-call sections.

8. No other sections of `CLAUDE.build.md` or `CLAUDE.build.md.j2` are changed.

9. The story-read step that previously preceded model evaluation is removed.
   The orchestrator no longer reads any story file during pre-flight; it reads
   only CLI output lines.

## Out of scope

- Implementing the CLIs (BUILD-034).
- Adding the frontmatter fields (INFRA-184).
- Running `sync-build` against registered upstream repos — that is an operator
  action after this phase checkpoints.

## Instructions

### CLAUDE.build.md

Replace the three gate sections (lines ~308–468) with the CLI-call equivalents.
Preserve all surrounding prose, section headings, and the ordering:
Auth check → Schema gate → Stub gate.

The new format for each gate is:

```
### [Gate name]

Run this check **once per story**, [position description].

```bash
PATH=$HOME/.local/bin:$PATH uv run python /mnt/work/flex/skills/pairmode/scripts/flex_build.py \
  [check-stub|check-schema-gate|check-auth-gate] RAIL-NNN --project-dir .
```

Replace `RAIL-NNN` with the current story ID.

- Exit 0: gate passes — proceed silently.
- Exit 1: gate blocked — surface the printed message to the user and stop.
  When resolved, say: "Continue building"
```

Remove the inline prose describing the judgment logic (delegation language
patterns, schema-object definition, auth-gated definition) — that logic now
lives in the CLI. The section can reference the CLI as the canonical source.

Also remove the now-unnecessary step where the orchestrator reads the story
spec before model evaluation. The orchestrator's pre-story block becomes:

1. Context gate (unchanged)
2. `check-auth-gate` CLI
3. `check-schema-gate` CLI  
4. `check-stub` CLI
5. `check-story-scope` CLI (unchanged)
6. Spawn builder

### CLAUDE.build.md.j2

Apply the identical changes to the Jinja2 template. The template uses
`{{ project_dir }}` or the literal flex path (whichever pattern the template
already uses for the flex_build.py invocation path — match it).

## Tests

### test_pairmode_sync.py

- `test_sync_build_dry_run_detects_old_gate_sections` — create a temp project
  with a `CLAUDE.build.md` containing the old inline stub-gate prose; assert
  `sync-build --dry-run` reports a non-empty diff.
- `test_sync_build_apply_replaces_old_gate_sections` — same setup with `--apply`;
  assert written file contains `check-stub` and not the old delegation-language prose.
