---
id: HARNESS-001
rail: HARNESS
title: Thin dispatch loop + `CLAUDE.build.md.j2` template reduction
status: complete
phase: "HARNESS006-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - tests/pairmode/test_template_reduction.py
touches: []
---

## Context

The first story of the flip (agreements HARNESS006-main.md DP1): reduce the `CLAUDE.build.md.j2`
template to the thin dispatch loop. The live `CLAUDE.build.md` for flex is NOT touched here —
that is the dogfood flip (HARNESS-002). Only the template source changes. All downstream
consumers get the thin loop at their next `sync-build --apply`.

The thin dispatch loop replaces hundreds of lines of prose procedure with ~20 lines that
delegate entirely to `flex_build.py next-action` and the leaf workers established in
HARNESS001–005.

## Requires

- WORKER-014 complete (HARNESS005 done): all leaf workers exist; the resolver action vocabulary
  is complete (`SCHEMA_VERSION == 4`).

## Ensures

- `skills/pairmode/templates/CLAUDE.build.md.j2` is reduced to ≤40 lines (excluding blank lines
  and Jinja2 comments). Contains:
  1. A header identifying it as the flex `CLAUDE.build.md` (orchestrator role, one sentence).
  2. **`## Build loop`** — the thin dispatch loop (≈10 lines):
     ```
     while true:
         a = flex_build.py next-action --json --project-dir .
         if a.action == "done": break
         spawn leaf-worker-for(a.action) with scalar=a.scalar, model=a.model
         record result via flex_build.py record-attempt ...
     ```
  3. **`## Checkpoint`** — one stanza: "The resolver emits checkpoint-security,
     checkpoint-intent, checkpoint-docs, checkpoint-tag in sequence. Execute each leaf worker
     as dispatched. checkpoint-tag: run `git tag cp-<phase-key> && git push origin harness --tags`."
  4. **`## Spec mode`** — one stanza: "The resolver emits spawn-spec-writer when the next
     story is a stub. Spawn the spec-writer leaf worker. On SPEC-RESULT{status: "revised"},
     surface to user. On "done", re-run next-action."
  5. **`## All other input`** — "Read `CLAUDE.md` and apply the reviewer role."
  - All multi-page prose procedure, examples, gate descriptions, and model-selection tables
    are **removed** from the template.
- `tests/pairmode/test_template_reduction.py` asserts:
  - The rendered template (via Jinja2 rendering with minimal context vars) is ≤40 non-blank lines.
  - The rendered template contains "next-action" and "leaf-worker".
  - The rendered template does NOT contain the old procedure-section headings (e.g.
    `"## Build loop" with >5 line body`, `"## Gate checks"`, `"await-user"` in prose form).
  - The template renders without Jinja2 errors given minimal context vars.
- The live `CLAUDE.build.md` in the flex repo is NOT modified (that is HARNESS-002).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_template_reduction.py -x -q`
  passes.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Rewrite the template from scratch using the five-stanza structure above. Do not attempt to
  surgically edit the existing template — it is too prose-heavy for incremental reduction.
- Use Jinja2 variables only for the project name / phase context if the template currently
  uses them; keep the template as close to plain text as possible.
- The test may use `jinja2.Environment(loader=jinja2.FileSystemLoader(...)).get_template(...)
  .render(...)` with minimal dummy context vars to check line count and keyword presence.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_template_reduction.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: template ≤40 non-blank lines; five-stanza structure present; old procedure headings
absent; Jinja2 renders without error; live `CLAUDE.build.md` unchanged; suite green.

### Out of scope

- Applying the template to the live `CLAUDE.build.md` (HARNESS-002 dogfood flip).
- Removing old agent `.md.j2` templates (HARNESS-002).
- CER-053 re-source (HARNESS-003).
