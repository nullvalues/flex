---
id: INFRA-227
rail: INFRA
title: Port Model-upgrade prompts subsection into CLAUDE.build.md.j2 sync template
status: complete
phase: "97"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches: []
---

## Context

INFRA-226 added a "Model-upgrade prompts" subsection to flex-harness's own
root `CLAUDE.build.md` (mandating that any `await-user` model-choice gate
leave a free-text/"Other" path so an operator can key in a model not in
`model_selector.py`'s enumerated tiers — the fable/forqsite incident).
Confirmed this session: that subsection was **never ported** into
`skills/pairmode/templates/CLAUDE.build.md.j2` — the Jinja2 template
`sync-all` actually renders into every downstream fleet project's
`CLAUDE.build.md`. `tests/pairmode/test_flip_dogfood.py`'s 40-line ceiling
check only asserts against the root file; nothing enforces the template
stays in sync with it. Confirmed by direct diff: the two files are
otherwise an exact match modulo Jinja2 placeholders — only the seven-line
"Model-upgrade prompts" block is missing from the template.

Practical consequence: every fleet project that syncs to pairmode 0.3.0
(before or after this story) gets a `CLAUDE.build.md` missing this rule,
until this story lands. forqsite (already migrated, `PM065-main`/
`INFRA-020`) is a live instance of exactly this gap and needs its own
already-rendered `CLAUDE.build.md` patched directly as a separate,
out-of-band fix — not part of this story's scope (this story only fixes
the source template for future syncs).

## Requires

- INFRA-226 complete (confirmed this session) — the root `CLAUDE.build.md`'s
  "Model-upgrade prompts" subsection is the exact source text this story
  ports.

## Ensures

- `skills/pairmode/templates/CLAUDE.build.md.j2` gains a "Model-upgrade
  prompts" subsection, placed in the same relative position (immediately
  after the build-loop `while true` code block, before `## Checkpoint`) as
  the root `CLAUDE.build.md`'s equivalent section.
- The ported text is character-identical to the root file's version, except
  it contains no `{{ pairmode_scripts_dir }}`/other Jinja2 placeholders
  (the source section has none to begin with — verified this session).
- No other line in `CLAUDE.build.md.j2` is modified — the diff against the
  root `CLAUDE.build.md` (`diff CLAUDE.build.md
  skills/pairmode/templates/CLAUDE.build.md.j2`) shows only Jinja2-variable
  differences after this change, no content differences.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes
  (this is a template-only change; no existing test should need updating,
  but run the suite to confirm nothing renders the template in a way this
  addition breaks).

## Instructions

1. Open both `CLAUDE.build.md` (repo root) and
   `skills/pairmode/templates/CLAUDE.build.md.j2` side by side.
2. Copy the "Model-upgrade prompts" section (the `## Model-upgrade prompts`
   heading and its paragraph) from the root file into the template, in the
   same relative position (between the build-loop code block and
   `## Checkpoint`).
3. Do not alter any other line in the template — this is a pure insertion.
4. Run `diff CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2`
   and confirm the only remaining differences are Jinja2 placeholder
   substitutions (project name, `pairmode_scripts_dir`, default branch),
   not content.
5. Run the full test suite and confirm green.

## Out of scope

- Patching any already-synced downstream project's `CLAUDE.build.md`
  (e.g. forqsite) — that is separate, direct, per-project remediation, not
  part of this template fix.
- Adding a test that asserts the template and root file stay in sync
  (worth a future story, not required here — flagged as a follow-on
  consideration, not built now).
- Any other content change to the template beyond this one insertion.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: full suite green; manual `diff` confirms the template and root
`CLAUDE.build.md` match except for Jinja2 placeholders.
