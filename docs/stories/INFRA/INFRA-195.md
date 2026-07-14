---
id: INFRA-195
rail: INFRA
title: "Checklist-item-level section granularity in audit/sync"
status: planned
phase: "87"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/scripts/sync.py
touches:
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_sync.py
  - tests/pairmode/test_sync_agents.py
  - .pairmode-overrides
---

## Requires

- Current (buggy) behavior, verified directly in this repo:
  - `audit.py::_SECTION_RE = re.compile(r"^(##+ .+|---)$", re.MULTILINE)`
    (`skills/pairmode/scripts/audit.py:253`) — the only section-boundary
    patterns recognised are `##`/`###`+ markdown headers and bare `---`
    separator lines.
  - `audit.py::_split_sections` (`audit.py:256`) uses `_SECTION_RE` to key
    the whole document into sections. Canonical checklist templates
    (`skills/pairmode/templates/agents/reviewer.md.j2`,
    `builder.md.j2`, `security-auditor.md.j2`, `intent-reviewer.md.j2`)
    number their checklist items with a bold-marker convention —
    `**1. PROTECTED FILES**`, `**2.5 STORY SPEC**`, `**5a. Conviction
    consistency**`, `**3. BUILD GATE**` — each on its own line, nested
    inside one large `## Review checklist` (or equivalent) H2 section that
    runs uninterrupted from the checklist's own header to the next H2.
    None of these bold markers are independently addressable section keys
    today.
  - Confirmed externally (coherra project): a project that hand-customizes
    one checklist bullet (there, BUILD GATE — extending the canonical
    single `{{ test_command }}` to
    `pnpm -r --if-present build && pnpm -r --if-present test`, plus a
    matching custom "## Test run" block) has no way to pin just that bullet.
    `.pairmode-overrides` only supports section keys produced by
    `_split_sections`, so the sole available key covers the entire
    `## Review checklist` body (all ~10 items). Declaring an override there
    would silently opt the whole checklist out of future canonical updates.
    Not declaring it means the next `sync` run detects the whole section as
    INCONSISTENT and overwrites it wholesale with canonical — reverting the
    hand-fix. This is what happened: `pairmode sync` silently dropped the
    build step back to a test-only gate.
  - `sync.py::_split_by_h2` (`sync.py:100`) — fast path used by
    `_replace_section_in_file`/`_append_section_to_file`, splits only on
    `^## ` lines (top-level H2). Its H3+ fallback (`sync.py:162-188`) scans
    for lines whose `.lstrip("#")` differs from the line (i.e. requires a
    literal leading `#`). Bold markers (`**N. LABEL**`) do not start with
    `#`, so today even if a bold-marker section key existed, sync's
    replace/append logic could not locate or patch it — it would silently
    fall through to "not found" and leave the file unchanged (see
    `_replace_section_in_file`'s final `return project_text` at
    `sync.py:173` for the no-match case).
  - `.pairmode-overrides` (project-root file, documented at
    `/mnt/work/coherra/.pairmode-overrides` and equivalent files in other
    synced projects) currently only shows `##`/`###` header examples in its
    format comment — it has no example of pinning a single checklist
    bullet, because doing so isn't possible today.

## Ensures

- A new boundary pattern recognises bold numbered checklist markers as
  section boundaries, in addition to (not instead of) the existing
  `##+ ` header and `---` separator boundaries. The pattern matches the
  full range of numbering styles already in use across the canonical
  templates: `**1. LABEL**`, `**2.5 LABEL**`, `**5a. LABEL**`,
  `**5b. LABEL**`, `**5c. LABEL**` (bold, starts with one or more digits,
  optional single trailing letter, optional `.` + digits sub-number,
  literal `.` before the label, arbitrary label text, closing `**`, nothing
  else on the line).
- `audit.py::_split_sections` splits on this pattern in addition to the
  existing ones, so each checklist item inside a larger `##` section
  becomes its own entry in the returned section-key dict — nested inside
  (i.e. subordinate to, not replacing) the enclosing H2's own boundary
  behavior. A checklist item's body key is stable and independent of
  content changes elsewhere in the same enclosing H2 section.
- Existing behavior for files/sections with no bold-marker items is
  byte-for-byte unchanged (this is an additive boundary pattern, not a
  replacement) — verified by the existing `test_audit.py` suite passing
  unmodified.
- `sync.py::_replace_section_in_file` and `_append_section_to_file` (or
  their shared boundary-detection helper) locate and patch bold-marker
  section keys correctly: given a project file with a customized bold-marker
  item body, replacing that item's canonical-diffed section key updates
  only that item's body and leaves every other checklist item — including
  other bold-marker items in the same enclosing H2 — untouched.
- `_load_overrides`'s parsing is unchanged (it already accepts arbitrary
  `file:section_key` pairs); this story only ensures a bold-marker key is
  now a valid, matchable `section_key` that audit/sync agree on.
- `.pairmode-overrides`'s format-comment block (the one shipped in
  `bootstrap.py`'s scaffold and mirrored in existing project files) gains
  one additional example line showing a checklist-item-granularity override,
  e.g. `.claude/agents/reviewer.md:**3. build gate**`.
- New tests in `tests/pairmode/test_audit.py` cover: a bold-marker item
  audits as INCONSISTENT independently of sibling items when only that
  item's body differs from canonical; sibling items in the same enclosing
  H2 do NOT audit as INCONSISTENT when unchanged.
- New tests in `tests/pairmode/test_sync.py` and/or `test_sync_agents.py`
  cover: syncing a file with one overridden bold-marker item (declared in
  `.pairmode-overrides`) preserves that item's custom body while still
  updating a different, non-overridden sibling item's body to canonical in
  the same sync run.
- No change to `CANONICAL_FILES`, `SCAFFOLD_FILES`, `EXISTENCE_CHECK_FILES`,
  or any template `.j2` file — this story changes only boundary-detection
  and replace/append logic, not the shipped checklist content.

## Test plan

`PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_audit.py tests/pairmode/test_sync.py tests/pairmode/test_sync_agents.py -x -q`

Full suite gate before checkpoint: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`
