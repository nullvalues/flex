---
id: INFRA-202
rail: INFRA
title: "Harden _merge_body_sections to recognize canonical sections already present under non-## heading styles and never duplicate-append"
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

# INFRA-202 — Harden `_merge_body_sections` to recognize canonical sections already present under non-`##` heading styles and never duplicate-append

## Context

On 2026-07-16, a routine `/flex:pairmode sync-all --apply` run against flex
itself (commit `85a6f52`, "catch flex up to canonical pairmode methodology")
silently corrupted `.claude/agents/reviewer.md` and
`.claude/agents/security-auditor.md`. It appended a second, out-of-order,
lowercased copy of the canonical reviewer checklist — `**1. protected files**`,
`**6. rail scope ...**`, `**5b. constraint rationale preservation**`,
`**2.5 story spec**`, `**3. build gate**`, `**5. ideology alignment**`, and
more — past the file's terminal `## Final output to orchestrator` section. The
corruption had to be hand-repaired without a spec in commit `622309c` as an
emergency bootstrap-paradox fix, because the corrupted files govern flex's own
review loop.

The defect is in `skills/pairmode/scripts/pairmode_sync.py`. The body-merge
path is:

- `_parse_body_sections` (lines 176-213) recognizes a "section" only when a
  line begins with the literal prefix `## `. Everything else is treated as
  section *content* or preamble.
- `_merge_body_sections` (lines 216-250) builds `target_headings` as the set of
  exact `## `-heading strings present in the target (line 230), then appends
  every template section whose exact heading string is not in that set
  (lines 233-237, 247-248).

flex's live `reviewer.md` expresses its individual checklist items as
bold-inline pseudo-headers — `**1. HOOK PERFORMANCE**`, `**2. PIPE CONTRACT**`,
`**7. PROTECTED FILES**`, etc. (verified in the current on-disk file, lines
61-210) — nested as *content* under the single real `## Review checklist`
heading. The canonical template's equivalent items carry different numbering
and casing (`**1. PROTECTED FILES**`, `**9. STORY SCOPE**`, `**2.5 STORY
SPEC**`, …). Because those items are not `## ` headings and never match by
exact string, `_merge_body_sections` classifies each canonical item as "absent
from the target" and appends a full duplicate copy at the tail of the file
instead of performing a clean no-op.

This is a live, repeatable, silent correctness bug. It fires on any routine
`sync-agents`/`sync-all --apply` run, and it corrupts any downstream pairmode
project whose agent files express canonical checklist items under a heading
style other than an exact `## ` string match — not just flex. It must be fixed
now because the tool exists specifically to propagate flex's builder/reviewer
methodology, and it is currently destroying the very files that methodology
lives in.

## Ensures

1. **Same-concept recognition across heading styles.** `_merge_body_sections`
   no longer decides "already present?" by exact `## `-heading string equality.
   It compares template sections against the target on a normalized
   *concept key* derived from heading text, computed identically for both a
   true `## ` heading and a standalone bold-inline pseudo-header line. The
   normalization is defined exactly as:
   a. Strip leading/trailing whitespace from the line.
   b. Remove a leading `## ` / `#` marker if present.
   c. If the remaining text is wholly wrapped in bold markers (the entire
      stripped line matches `^\*\*(.+?)\*\*:?$`), unwrap to the inner text.
   d. Remove a leading enumerator token matching the regex
      `^\d+(\.\d+)?[a-z]?[.)]?\s+` (this covers `1. `, `2.5 `, `5a. `,
      `13b. `, `10) `).
   e. Strip a trailing `:`.
   f. Strip any remaining inline emphasis / backtick characters (`*`, `_`,
      `` ` ``).
   g. Lowercase and collapse all internal whitespace runs to a single space.

   Under this rule, a target line `**1. HOOK PERFORMANCE**` and a template
   heading `## 1. Hook performance` both normalize to `hook performance` and
   are recognized as the same concept; a target `**2.5 STORY SPEC**` and a
   template `## 2.5 Story spec` both normalize to `story spec`.
2. **Whole-body scan for the target's present concepts.** The set of concept
   keys considered "already present in the target" is built by scanning the
   *entire* target body — not only its `## `-delimited sections — for both
   `## ` heading lines and standalone bold-inline pseudo-header lines (a line
   whose stripped content matches `^\*\*(.+?)\*\*:?$`). Inline bold spans that
   are part of a prose sentence (i.e. the line is not wholly a single bold
   span) are not treated as pseudo-headers and do not contribute keys.
3. **Never duplicate-append a recognized concept.** Given a target whose body
   contains `**1. PROTECTED FILES**\n...` and a template section
   `## 1. Protected files\n...`, `_merge_body_sections` recognizes them as the
   same concept and does not append the template section. The reviewer.md /
   security-auditor.md corruption from commit `85a6f52` cannot recur: a
   canonical checklist item already present under any covered heading style is
   a no-op, never a tail append.
4. **Conservative-only behavior change.** The new matching can only *suppress*
   appends that the old code would have made; it can never cause a new append
   that the old code would have skipped. Sections genuinely absent from the
   target (no matching concept key under any style) are still appended exactly
   as before, preserving the additive-propagation feature.
5. **Target content is never rewritten.** The story only changes the
   append/skip decision. Existing target sections, their casing, their
   numbering, and project-specific sections are preserved byte-for-byte; the
   target's own heading style is never normalized on disk.
6. **Regression test grounded in the real incident.** A new test uses a
   reviewer.md-shaped target body (canonical checklist items expressed as
   `**N. TITLE**` pseudo-headers under a `## Review checklist` heading) merged
   against a template body whose equivalent items appear as `## N. Title`
   sections, and asserts zero duplicate appends — reproducing exactly the
   `85a6f52` corruption shape and proving it is now a no-op.
7. **Full pairmode suite green.** `PATH=$HOME/.local/bin:$PATH uv run pytest
   tests/pairmode/ -x -q` passes with zero failures, including the existing
   `TestMergeBodySections` cases in `tests/pairmode/test_pairmode_sync.py`.

## Instructions

- Edit only `_merge_body_sections` and its supporting helpers in
  `skills/pairmode/scripts/pairmode_sync.py` (lines 216-250, plus one or two
  new module-level helper functions). Do not change `sync_agents`, `sync-build`,
  `sync-all`, or `_collect_changes` control flow in this story.
- Add a pure helper, e.g. `_heading_concept_key(line: str) -> str | None`,
  implementing the normalization defined in Ensures #1. It returns the
  normalized key for a `## ` heading line or a standalone `**...**`
  pseudo-header line, and `None` for any other line (so callers can skip
  non-heading lines).
- Add a helper, e.g. `_target_concept_keys(body: str) -> set[str]`, that walks
  every line of the target body, calls `_heading_concept_key`, and collects the
  non-`None` results into a set. This replaces the current
  `target_headings = {heading for heading, _content in target_sections}`
  construction (line 230), which only sees `## `-level sections.
- In `_merge_body_sections`, keep parsing the *template* into
  `(heading_line, content)` sections via `_parse_body_sections` (the template's
  canonical sections are still authored as `## ` headings). For each template
  section, compute its concept key from `heading_line` via
  `_heading_concept_key`; append the section only if that key is not in the
  target's concept-key set. Preserve the existing append formatting (blank-line
  separator, trailing-newline guard at lines 244-248) unchanged.
- Guard the enumerator regex so it does not strip a leading numeral that is
  actually part of the heading's meaning when no `.`/`)` delimiter and trailing
  space follow it; the `^\d+(\.\d+)?[a-z]?[.)]?\s+` form already requires a
  trailing whitespace boundary, which is the intended safeguard — do not loosen
  it to match bare digits.
- Update the `docs/architecture.md` "Body-merge duplication risk" note (lines
  668-682) to state that `_merge_body_sections` now matches on a normalized
  concept key across `## ` and `**N. TITLE**` styles and no longer duplicate-
  appends recognized items; keep the historical incident reference
  (`85a6f52` / `622309c`) but reframe it as resolved rather than "tracked as
  follow-on work, not yet fixed."

## Tests

`story_class: code` — real branching-logic change to the merge decision. Run
the full gate:

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Add these cases to `TestMergeBodySections` in
`tests/pairmode/test_pairmode_sync.py` (unit-level, calling
`_merge_body_sections` directly):

- `test_pseudo_header_target_matches_template_h2_no_duplicate` — target body
  contains `**1. HOOK PERFORMANCE**\n...content...\n` under a
  `## Review checklist` heading; template body contains
  `## 1. Hook performance\n...content...\n`. Assert the merged body does not
  gain a second `Hook performance` heading and that `merged.count("Hook
  performance")` (case-insensitive concept) does not increase — the merge is a
  no-op for that concept.
- `test_numbering_and_case_differences_still_match` — target
  `**7. PROTECTED FILES**`, template `## 1. Protected files`; assert no append
  (both normalize to `protected files`).
- `test_enumerated_subsection_ids_match` — target `**5b. constraint rationale
  preservation**`, template `## 5b. Constraint rationale preservation`; assert
  no append.
- `test_reviewer_md_incident_shape_is_noop` — a multi-item fixture mirroring
  the `85a6f52` corruption: a reviewer.md-shaped target body with the full
  `**N. TITLE**` checklist plus a terminal `## Final output to orchestrator`
  section, merged against a template body carrying the canonical items as
  `## N. Title` sections. Assert nothing is appended after `## Final output to
  orchestrator` and no canonical concept appears twice.
- `test_genuinely_new_section_still_appended` — template `## Brand new
  section` whose concept key is absent from the target under any style; assert
  it is still appended (guards against over-suppression / Ensures #4).
- `test_inline_bold_in_prose_is_not_a_pseudo_header` — a target line like
  `This is **important** context.` must not register `important` as a present
  concept, so a template `## Important` section is still appended.

Add one CLI-level regression to `tests/pairmode/test_sync_agents.py` (or
`test_pairmode_sync.py` alongside `test_sync_agents_renders_with_full_context`)
that drives `_collect_changes` with a synthetic reviewer-shaped agent file and
a synthetic template, asserting the produced `new_content` contains no
duplicated canonical checklist item.

### Out of scope

- The empty/missing-variable degenerate-render failure in the body-merge path
  (the `` Does `` pass cleanly? `` artifact from an empty `build_command`).
  That is a distinct code path and is fixed by INFRA-203; this story does not
  add any loud-failure or empty-content guard.
- `sync-build`'s whole-file-overwrite mechanism
  (`build_file.write_text(rendered, ...)`, line 681). That is a separate,
  non-section-merge code path and is not touched here.
- Re-running `sync-agents`/`sync-all` against flex or any other project as part
  of this story. This story changes the tool's logic and its tests only; it
  performs no propagation run.
- Retroactively editing `.claude/agents/reviewer.md` or
  `.claude/agents/security-auditor.md`. Both were already hand-repaired in
  commit `622309c`; this story does not touch them.
- Any change to the `next-action` resolver or Era 003 harness work — unrelated.
