<!-- FROZEN EXEMPLAR (INFRA-363). This file is the spec-writer procedure's bounded
     input 4 (`skills/pairmode/skills/spec-writer/procedure.md` § Input contract,
     item 4). It replaces the old "one recent complete story" rotating exemplar,
     which was self-reinforcing: today's longest spec became tomorrow's format
     reference regardless of the surrounding prose (INFRA-357's Forbidden-proxy
     finding; INFRA-363's Context). Changing which story serves as the exemplar is
     now a deliberate, reviewable edit to this one file — never an automatic
     consequence of what shipped most recently.

     This is a purpose-built exemplar, modeled tightly on this project's own
     shipped-story shape (frontmatter + the six required body sections), chosen
     specifically to demonstrate the rule this project's early preamble-lineage
     doc stated and later lost: "a story is right-sized when its acceptance
     criterion fits in one sentence." The `## Ensures` section below is exactly
     one sentence. `## Instructions` is scoped to only what a builder could not
     already infer from ordinary engineering judgment. Read this file for its
     *structural format* — section order, granularity, and proportion — not as a
     story awaiting a build. -->

---
id: EXEMPLAR-000
rail: EXEMPLAR
title: Strip trailing slash from --path in example_tool.py normalize
status: complete
phase: "0"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/example_tool.py
touches:
  - tests/pairmode/test_example_tool.py
---

## Context

`example_tool.py normalize --path P` is meant to canonicalize a project path before
it is written into `state.json`, but a trailing slash on `P` currently survives
untouched, so `--path /mnt/work/foo/` and `--path /mnt/work/foo` produce two
different keys for the same project. This has already caused one duplicate
registration in the fleet (the same failure shape as CER-058, on a smaller
surface). The fix is a single normalization step at the one place paths enter
the tool.

## Requires

None — the bug is isolated to `example_tool.py`'s own path handling.

## Ensures

`example_tool.py normalize --path P` returns the same normalized string for `P`,
`P/`, and `P//`, and every other path shape (relative, `~`-prefixed, already
normalized) is returned unchanged.

## Instructions

1. In `example_tool.py`'s `normalize` command, strip trailing `/` characters from
   `--path` (via `.rstrip("/")`, guarding against reducing a bare `"/"` to `""`)
   before the value is used anywhere else in the function.
2. Add tests to `tests/pairmode/test_example_tool.py` covering the three
   trailing-slash shapes in `## Ensures` plus one already-normalized control case.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_example_tool.py -q
```
Acceptance: green, including the new trailing-slash cases.

## Out of scope

- Normalizing paths anywhere else in the codebase that already do their own
  path handling (e.g. `pairmode_register.py`'s own resolution) — this story
  fixes only `example_tool.py normalize`'s own input handling.
- Rejecting invalid paths (nonexistent, non-absolute) — `normalize` only
  canonicalizes shape; validating existence is a separate concern this story
  does not touch.
