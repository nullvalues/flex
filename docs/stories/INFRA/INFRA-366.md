---
id: INFRA-366
rail: INFRA
title: Guard bootstrap's OPERATOR-010 extension write against silent overwrite (checkpoint-security finding)
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_bootstrap.py
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

- INFRA-353 complete (it introduced the `OPERATOR-010-project.md` extension write this story guards).

## Ensures

1. The `OPERATOR-010-project.md` write in `bootstrap.py` goes through the same `_write_file` helper
   as its sibling writes in that function, passing the same dry-run/force arguments the siblings
   pass. No bare `.write_text(` call remains on the operator-extension path.
2. Re-running bootstrap with a non-blank operator note against a project where
   `docs/narratives/OPERATOR/OPERATOR-010-project.md` already exists prompts before writing, and on
   decline leaves that file's contents byte-identical to what they were before the run.
   **Forbidden proxy:** printing a warning (or recording a skip) while the write happens anyway —
   the assertion is on the file's post-run bytes, not on any emitted message.
3. Blank-note and fresh-project behaviour is unchanged: a blank note still writes no extension file
   at all, and a first-time write on a project with no existing `-010` file still succeeds without
   an extra prompt.
4. Dry-run still performs no write (whether the file pre-exists or not).
5. Full `tests/pairmode/` suite green.

## Instructions

1. In `bootstrap.py`, replace the unguarded `operator_extension_dest.write_text(...)` (≈line 1733)
   with a `_write_file` call matching the sibling writes in the same function. Do not reimplement
   the exists/prompt/decline logic inline — `_write_file` (≈lines 266-294) already owns it; this is
   the "single writer for a behaviour" shape the surrounding code already uses.
2. Fold the existing `dry_run` special-casing into that call if `_write_file` already handles
   dry-run (the siblings' usage is the reference); remove the now-redundant branch rather than
   leaving two dry-run guards on the same path.
3. Add tests to `tests/pairmode/test_bootstrap.py` covering Ensures 2-4: pre-existing extension file
   with the overwrite declined (contents unchanged), pre-existing file with overwrite accepted
   (contents replaced), no pre-existing file (written, no prompt path failure), and dry-run (no
   file on disk). Assert on file contents/existence, not on captured stdout.

Ideology note: the fix routes through `_write_file` rather than adding a bespoke guard, preserving
the "never silently pass contradictions" constraint (an overwrite of a doc-of-record is exactly the
class of silent action that constraint protects against) and keeping one writer for the
prompt-before-clobber behaviour.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_bootstrap.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green, including the new decline-preserves-contents test.

## Out of scope

- Auditing the rest of `bootstrap.py` for other unguarded writes — this story fixes only the
  `OPERATOR-010` extension path named in the audit finding. Any further unguarded write found while
  working here should be filed as a CER, not fixed inline.
- Any merge/append semantics for an existing `OPERATOR-010` file (e.g. appending the new note as a
  further numbered section). Prompt-and-overwrite parity with the sibling writes is the whole scope.
