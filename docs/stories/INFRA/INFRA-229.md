---
id: INFRA-229
rail: INFRA
title: Reword Model-upgrade prompts section to avoid banned await-user phrase in CLAUDE.build.md.j2
status: complete
phase: "97"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
touches: []
---

## Context

INFRA-226 added a "Model-upgrade prompts" subsection to the root
`CLAUDE.build.md`, and INFRA-227 ported it verbatim into
`skills/pairmode/templates/CLAUDE.build.md.j2`. The section's text reads
"At any `await-user` action whose reason involves a model choice...". This
directly contains the literal substring `await-user`, which
`tests/pairmode/test_template_reduction.py::test_old_prose_absent` bans from
the rendered template (a HARNESS-001 anti-regression test preventing the old,
pre-flip verbose gate-based prose from creeping back in).

This was not caught by either INFRA-226's or INFRA-227's own build/review
cycles because both ran `uv run pytest tests/pairmode/ -x -q` — the `-x` flag
stops at the **first** failure. The pre-existing, already-known
`test_observability_ui.py::test_ui_build_emits_dist_index_html` (CER-070)
failure sorted before `test_template_reduction.py` in the collected test
order, so `-x` halted there and neither builder/reviewer ever actually
reached (or saw) this second, real failure. Confirmed this session by
running the specific test directly against the current fold-prep tip: it
fails, reproducibly, right now.

## Requires

- INFRA-226 and INFRA-227 complete (confirmed present this session, both
  contributing the `await-user` phrase now tripping the banned-phrase test).

## Ensures

- The "Model-upgrade prompts" section in **both** `CLAUDE.build.md` (repo
  root) and `skills/pairmode/templates/CLAUDE.build.md.j2` is reworded to
  preserve its exact meaning (any judgment-handoff pause whose reason
  involves a model choice must let the operator key in an arbitrary model
  name) **without** using the literal substring `await-user` anywhere in
  the reworded text. Suggested phrasing: replace "any `await-user` action
  whose reason involves a model choice" with "any judgment-handoff pause
  whose reason involves a model choice" (matching the existing
  "judgment-handoff" vocabulary already used elsewhere in this codebase,
  e.g. `next_action.py`'s docstring describing rows 3/4/7) — or an
  equivalent rewording that avoids the banned substring.
- `tests/pairmode/test_template_reduction.py::test_old_prose_absent[await-user]`
  passes.
- The root `CLAUDE.build.md` and the template remain in content-sync per
  INFRA-227's established invariant: `diff CLAUDE.build.md
  skills/pairmode/templates/CLAUDE.build.md.j2` shows only Jinja2-placeholder
  differences, no content differences, after this reword.
- `tests/pairmode/test_flip_dogfood.py::test_live_build_md_non_blank_line_count`
  still passes (the root file must stay at or under the 40-non-blank-line
  ceiling — the reword must not add net length).
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` (no `-x`)
  passes in full, so any further masked failure is caught this time —
  do not use `-x` for this story's own verification run.

## Instructions

1. In both `CLAUDE.build.md` (repo root) and
   `skills/pairmode/templates/CLAUDE.build.md.j2`, find the "Model-upgrade
   prompts" section and reword the sentence containing `await-user` so the
   literal substring no longer appears anywhere in either file, while
   preserving the exact same meaning. Keep the edit minimal — this is a
   wording fix, not a rewrite of the section.
2. Make the identical wording change in both files (they must stay in sync
   per INFRA-227's invariant).
3. Run `diff CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2`
   and confirm only Jinja2 placeholders differ.
4. Run `grep -rn "await-user" CLAUDE.build.md skills/pairmode/templates/CLAUDE.build.md.j2`
   and confirm zero matches in either file.
5. Run the full test suite **without** `-x` (per this story's own Tests
   section) and confirm it is fully green modulo the one already-known,
   already-tracked CER-070 environmental failure — report explicitly if any
   other failure surfaces, rather than assuming only CER-070 exists.

## Out of scope

- Any other content change to either file beyond this one reword.
- Fixing the underlying `-x`-masks-failures process gap itself (worth a
  future story/lesson — this story only fixes the concrete regression it
  caused).
- Any change to `test_template_reduction.py`'s banned-phrase list.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: full suite green except the known CER-070 environmental
failure — run without `-x` and report every failure seen, not just the
first.
