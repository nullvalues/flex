---
id: INFRA-203
rail: INFRA
title: "Make empty/missing-variable template renders in the sync-agents body-merge path fail loudly instead of merging empty content"
status: complete
phase: "91"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/pairmode_sync.py
touches:
  - tests/pairmode/test_pairmode_sync.py
  - tests/pairmode/test_sync_agents.py
  - docs/architecture.md
---

# INFRA-203 — Make empty/missing-variable template renders in the `sync-agents` body-merge path fail loudly instead of merging `""` content

## Context

The same `/flex:pairmode sync-all --apply` run that triggered INFRA-202
(commit `85a6f52`, hand-repaired in `622309c`) also merged a nonsensical,
empty-substitution checklist line into flex's own agent files. The appended,
corrupted reviewer content included the line `` Does `` pass cleanly? `` — a
canonical template line of the form `` Does `{{ build_command }}` pass
cleanly? `` rendered with `build_command == ""`. A similar empty-variable
artifact (`"Does any data access code fail to enforce: ?"`) came from
`domain_isolation_rule` being empty for flex, which declares no
domain-isolation model.

The relevant code in `skills/pairmode/scripts/pairmode_sync.py`:

- `_build_template_context` (lines 275-299) pre-populates *every* template
  variable with a graceful fallback: `build_command`, `test_command`,
  `migration_command`, and `domain_isolation_rule` default to `""` and
  `protected_paths` defaults to `[]` when absent from both
  `.companion/pairmode_context.json` and `.companion/state.json`.
- `_collect_changes` (lines 339-412) renders each agent template twice with
  that context, both under `jinja2.StrictUndefined`:
  1. **Frontmatter render** (lines 386-390): `_render_template_frontmatter`
     renders the whole template and extracts the frontmatter. On any
     `TemplateError`/`ValueError` it appends to `render_errors` and `continue`s.
     The CLI later prints `error: failed to render {filename}: {reason}` to
     stderr and exits 1 (lines 471-484). **This path already works.**
  2. **Full-body render** (lines 393-402): `_render_full_template` renders the
     whole template again to extract the body for section merging. Its
     `except (jinja2.TemplateError, ValueError):` branch **silently swallows
     the failure to `template_body = ""`** and populates *no* `render_errors`
     entry (lines 397-402).

Two facts must be kept distinct:

- **The genuinely-undefined-variable case already fails loudly** — but via the
  *frontmatter* render, not the full-body render. Because
  `_render_template_frontmatter` renders the entire template (frontmatter +
  body) under `StrictUndefined`, a template body that references a variable not
  present in the context *at all* raises there first and is surfaced correctly
  (this is exactly what `test_sync_agents_exits_nonzero_on_render_failure`
  exercises). The `except` branch at lines 397-402 is therefore practically
  unreachable for truly-undefined variables and is a latent silent-failure
  path only.
- **The actual corruption is NOT an undefined variable — it is a
  defined-but-empty one.** Because `_build_template_context` supplies
  `build_command = ""` (a *defined* key), `StrictUndefined` never fires. Both
  renders *succeed*, and the empty string is interpolated into the body,
  producing degenerate content (`` Does `` pass cleanly? ``) that
  `_merge_body_sections` then merges into the target. This is the specific gap
  INFRA-203 must close: an empty/degenerate variable substitution in the
  body-merge path currently produces a silent, corrupting write instead of a
  loud failure.

This is silent, repeatable, and affects any downstream project whose
`pairmode_context.json`/`state.json` omits a variable that its agent templates
reference in the body. It must be fixed now for the same reason as INFRA-202:
the tool corrupts the methodology files it exists to propagate.

## Ensures

1. **No silent full-render swallow.** The `except (jinja2.TemplateError,
   ValueError)` branch in `_collect_changes` that currently sets
   `template_body = ""` (lines 397-402) no longer swallows the failure. When
   `_render_full_template` raises for an agent file, that file is appended to
   `render_errors` as `(agent_file.name, str(exc))` and skipped (`continue`),
   exactly mirroring the frontmatter-render failure path. No bodyless/degraded
   merge is ever produced from a raised full render.
2. **Defined-but-empty body variables fail loudly.** When both renders
   *succeed* only because a body-referenced template variable resolved to an
   empty value supplied by `_build_template_context`'s `""`/`[]` fallback
   (e.g. `build_command`, `domain_isolation_rule`, `protected_paths`), and that
   empty value would be interpolated into a section the body-merge is about to
   append to the target, the file is reported as a render error and skipped —
   never merged. Concretely: an agent template body containing
   `` Does `{{ build_command }}` pass cleanly? `` with `build_command == ""`
   in context causes that file to be surfaced as a render error, not written.
3. **Loud CLI behavior: stderr, exit 1, no write.** For every file caught by
   Ensures #1 or #2, `sync-agents` prints `error: failed to render {filename}:
   {reason}` to stderr (existing loop, lines 472-473). A degenerate file is
   never included in `changes`, so it is never written to disk — its on-disk
   content is byte-for-byte unchanged. When no other file produced a clean
   change, the run exits 1 (existing behavior, lines 476-482). The `{reason}`
   for the empty-variable case names the offending variable(s) so an operator
   can populate `pairmode_context.json` or apply the body change by hand.
4. **Legitimately-empty variables that never reach an appended section do not
   spuriously fail.** The empty-variable guard is scoped to content the
   body-merge would actually *add* to the target. A variable that is empty but
   only appears inside a section already present in the target (and therefore
   not appended — see INFRA-202's matching) does not, by itself, force a
   failure. This prevents over-blocking projects such as flex whose templates
   reference empty variables inside already-present sections.
5. **The already-working undefined-variable path is preserved.** The
   frontmatter-render `StrictUndefined` failure path (lines 386-390) is
   unchanged; `test_sync_agents_exits_nonzero_on_render_failure` still passes
   with the same `exit_code == 1` and `"failed to render"` assertions.
6. **Regression tests grounded in the real incident.** New tests reproduce the
   `` Does `` pass cleanly? `` corruption shape — a reviewer/security-auditor-
   shaped agent file plus a template whose body interpolates an empty
   `build_command` into a section that would be appended — and assert the file
   is surfaced as a render error, is not written, and the run exits 1.
7. **Full pairmode suite green.** `PATH=$HOME/.local/bin:$PATH uv run pytest
   tests/pairmode/ -x -q` passes with zero failures, including the existing
   `test_sync_agents_renders_with_full_context` and
   `test_no_changes_message_only_when_clean` cases.

## Instructions

- Edit `_collect_changes` in `skills/pairmode/scripts/pairmode_sync.py`
  (lines 339-412), plus one new module-level helper. Do not change the CLI's
  existing `render_errors` printing / exit-code logic (lines 471-484) — reuse
  it. Do not alter `_build_template_context`'s fallbacks (lines 291-299); the
  fix lives in the body-merge path, not in the context builder.
- **Close the silent swallow (Ensures #1):** replace the body of the
  `except (jinja2.TemplateError, ValueError):` branch at lines 397-402. Instead
  of `template_body = ""`, do
  `render_errors.append((agent_file.name, str(exc)))` and `continue` — so a
  raised full-template render is surfaced identically to a raised frontmatter
  render, and no file is written from a failed body render.
- **Detect defined-but-empty body substitutions (Ensures #2 and #4):** after a
  *successful* full render, determine whether the body-merge would append a
  section whose rendered content depends on an empty-valued context variable.
  Implement it as follows:
  - Build a `body_strict_context` from `context` by removing every key whose
    value is empty (`""`, `[]`, `None`). Re-render the *full template* with a
    fresh `jinja2.Environment(undefined=jinja2.StrictUndefined,
    keep_trailing_newline=True)` using `body_strict_context`. If this raises
    `jinja2.UndefinedError`, the template body genuinely references a variable
    this project supplies only as an empty fallback.
  - Scope the failure to appended content: only treat that `UndefinedError` as
    a render error for this file if the section(s) that `_merge_body_sections`
    would newly append (the template sections absent from the target under
    INFRA-202's concept-key matching) are the ones referencing the empty
    variable. The simplest correct implementation: compute the set of sections
    `_merge_body_sections` would add, and re-run the strict body render over
    just those appended sections' template source; if the strict render of the
    to-be-appended content raises `UndefinedError`, append
    `(agent_file.name, reason)` to `render_errors` and `continue` (skip the
    file). `reason` must name the undefined variable(s), e.g.
    `"body section '<heading>' interpolates empty variable '<name>'"`.
  - If no to-be-appended section depends on an empty variable, proceed with the
    existing merge and write path unchanged.
- Keep the two code paths clearly separated in comments so the distinction in
  this story's Context (frontmatter StrictUndefined vs. body-merge empty-value)
  survives future edits.
- Update `docs/architecture.md`:
  - The `sync-agents` "Body propagation" bullet (lines 641-651) currently says
    body-render failure "will silently fall back to no-op for that file" and
    frontmatter sync still proceeds. Revise it to state that, since INFRA-203,
    a body render that fails — whether by `StrictUndefined` on a truly-missing
    variable or by an empty-valued variable feeding a to-be-appended section —
    is surfaced as a render error to stderr, the file is skipped (not written),
    and the run exits 1 when no other file changed.
  - The "Body-merge duplication risk" note (lines 668-682): update the second
    half (the `domain_isolation_rule`/empty-`""` paragraph) to state that an
    empty-valued variable feeding an appended section now fails loudly rather
    than merging a broken/empty checklist line.

## Tests

`story_class: code` — real new failure branch in the body-merge path. Run the
full gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Add these cases (CLI-level via `CliRunner` with `pairmode_sync.TEMPLATES_DIR`
patched, mirroring `test_sync_agents_exits_nonzero_on_render_failure` in
`tests/pairmode/test_pairmode_sync.py`; unit-level tests may call
`_collect_changes` directly, as `test_sync_agents_renders_with_full_context`
does):

- `test_empty_build_command_in_appended_section_fails_loudly` — a synthetic
  agent file whose body lacks the canonical `## Test run` section, plus a
  template whose `## Test run` body contains
  `` Does `{{ build_command }}` pass cleanly? ``, with `build_command` absent
  from `state.json`/`pairmode_context.json` (so it resolves to `""`). Assert
  `_collect_changes` returns this file in `render_errors` (not `changes`), and
  that the CLI exits 1 with `"failed to render"` on stderr and the agent file
  on disk is unchanged.
- `test_empty_variable_in_existing_section_does_not_fail` — the same empty
  `build_command`, but the target already contains an equivalent `## Test run`
  section (so it would not be appended). Assert the file is NOT reported as a
  render error and any independent frontmatter change still applies cleanly
  (Ensures #4 / no over-blocking).
- `test_full_render_exception_populates_render_errors` — a template that
  renders frontmatter cleanly but raises during the full-body render path;
  assert the file lands in `render_errors` (Ensures #1), never in `changes`,
  and is not written. (If a natural trigger for a full-render-only exception is
  hard to construct given both renders share context, assert the branch via a
  targeted `unittest.mock` patch of `_render_full_template` raising
  `jinja2.TemplateError`.)
- `test_undefined_variable_still_fails_via_frontmatter_path` — retain/extend
  coverage equivalent to the existing
  `test_sync_agents_exits_nonzero_on_render_failure`, confirming a
  truly-undefined body variable still exits 1 (Ensures #5). Do not weaken or
  delete that existing test.
- `test_reviewer_incident_empty_build_command_not_written` — a reviewer-shaped
  fixture reproducing the `85a6f52` `` Does `` pass cleanly? `` artifact;
  assert the corrupt line is never written to the agent file and the run fails
  loudly.

### Out of scope

- The heading-style / duplicate-append matching fix (recognizing
  `**N. TITLE**` pseudo-headers as the same concept as `## N. Title`). That is
  INFRA-202. This story assumes INFRA-202's concept-key matching when scoping
  the empty-variable guard to "sections that would be appended," but does not
  itself implement or modify that matching logic.
- Changing `_build_template_context`'s fallback defaults (lines 291-299) from
  `""`/`[]` to something else, or making `sync-build` reject empty variables.
  `sync-build`'s whole-file-overwrite path (line 681) is a different mechanism
  and is not touched here.
- Re-running `sync-agents`/`sync-all` against flex or any downstream project.
  This story changes tool logic and tests only.
- Retroactively editing `.claude/agents/reviewer.md` or
  `.claude/agents/security-auditor.md` — already hand-repaired in `622309c`.
- Any change to the `next-action` resolver or Era 003 harness work — unrelated.
