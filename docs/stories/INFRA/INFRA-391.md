---
id: INFRA-391
rail: INFRA
title: Fix audit.py override-key format mismatch between _normalise() and _load_overrides() (CER-170)
status: complete
phase: "123"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/audit.py
touches:
  - tests/pairmode/test_audit.py
  - skills/pairmode/scripts/sync.py
  - tests/pairmode/test_sync.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

`.pairmode-overrides` lets a project declare intentional divergence from a canonical
section so `audit` doesn't keep flagging it MISSING/INCONSISTENT. SKILL.md documents
the entry format as the lowercased, `##`-stripped header text (`## Review checklist` →
`review checklist`), and `_load_overrides_with_diagnostics` stores entries exactly that
way. But `_split_sections` builds its own section keys via `key = _normalise(header)`,
and `_normalise()` only lowercases/collapses whitespace — it never strips the leading
`##` — so those keys look like `'## review checklist'`. Every `(dest_rel, key) in
overrides` membership check therefore compares a `'## foo'`-shaped key against a
`'foo'`-shaped override entry and can never match (CER-170): the suppression mechanism
silently never fires for any project using it in the documented format. Found while
investigating an unrelated issue in the `cora` project; confirmed as a bug native to
this repo's own `audit.py`.

## Requires

- CER-170 filed in `docs/cer/backlog.md` (done as part of this story's spec-writing).


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| skills/pairmode/scripts/sync.py | CER-170 header-key strip in _split_sections ripples into sync.py's own header/RETIRED_SECTIONS key comparisons, which independently assumed the pre-fix ##-prefixed key shape; must be corrected in the same story or sync.py silently mis-locates/mis-appends sections and the RETIRED_SECTIONS registry stops matching | 2026-08-05T02:50:00Z |

| tests/pairmode/test_sync.py | sync.py's own tests hardcode the pre-fix ##-prefixed section-key format in RETIRED_SECTIONS/override assertions; must update alongside the sync.py fix to stay meaningful post CER-170 | 2026-08-05T02:51:57Z |
## Ensures

1. `_split_sections`'s section-key construction strips a leading `#+\s*` marker from
   the header text before normalising, so a canonical/project section key for a
   markdown header `## Foo Bar` is `'foo bar'`, not `'## foo bar'`.
2. `_normalise()` itself is unchanged in behaviour for non-header text — it still only
   lowercases and collapses whitespace; body-text comparisons (`canonical_body`/
   `project_body` at the two `_normalise(canonical_sections[key])` /
   `_normalise(project_sections[key])` call sites) are byte-identical to before this
   fix, since the `#+\s*` strip is applied only where a section key is derived from a
   header, not wherever `_normalise()` is called generally. Forbidden proxy: fixing
   the mismatch by changing `_normalise()` itself would also silently alter body-text
   normalisation for every other caller — that is not this fix.
3. Separator keys (`---`) and bold-marker keys (e.g. `'**3. build gate**'`) are
   unaffected — they have no leading `#`, so the strip is a no-op for them; existing
   `_is_separator_key`/bold-marker handling continues to work unchanged.
4. A `.pairmode-overrides` entry written in the SKILL.md-documented `file_path:
   section_key` form (no `##` prefix, e.g. `CLAUDE.md: review checklist`) now actually
   suppresses both a MISSING finding (canonical section absent from the project file)
   and an INCONSISTENT finding (canonical section present but content differs) for
   that section — verified by a new regression test that writes the override in the
   real documented format (not by re-deriving the expected key via `_normalise("##
   ...")` the way the pre-existing `TestAuditOverridesSuppress` tests do) and asserts
   the corresponding finding is absent from `audit_project`'s result.
5. A section NOT named in `.pairmode-overrides` still surfaces as MISSING/INCONSISTENT
   as before — the fix narrows the key-matching bug only; it does not broaden
   suppression to unlisted sections.
6. `uv run pytest tests/pairmode/test_audit.py -q` passes, including the four
   pre-existing `TestAuditOverridesSuppress` tests (`test_inconsistent_finding_
   suppressed_when_in_overrides`, `test_missing_finding_suppressed_when_in_overrides`,
   `test_section_not_in_overrides_still_surfaces`, `test_no_overrides_file_no_
   behavioral_change`) and the new regression test(s) from Ensures 4.

## Instructions

1. In `skills/pairmode/scripts/audit.py`, in `_split_sections` (around line 381),
   change `key = _normalise(header)` to strip a leading `#+\s*` from `header` before
   calling `_normalise` on the result — e.g. `key = _normalise(re.sub(r"^#+\s*", "",
   header))`. Do not modify `_normalise()` itself (Ensures 2).
2. Confirm (by inspection, no code change needed) that the two `_normalise(canonical_
   sections[key])` / `_normalise(project_sections[key])` calls used for body-content
   comparison are unaffected — they normalise section *bodies*, not headers, so they
   never see a leading `##` in the first place; this instruction is a check, not a
   change.
3. In `tests/pairmode/test_audit.py`'s `TestAuditOverridesSuppress`, either fix
   `_get_first_canonical_section_key` to strip the `##` before calling `_normalise`
   (so it matches the real documented format and the real post-fix internal key), or
   add a new test class/method alongside it that writes the override using the plain
   SKILL.md-documented key (no `##`) and asserts suppression — pick whichever keeps
   the existing four tests meaningful rather than just passing. At minimum, add one
   new test that: (a) removes or alters a canonical section in a fixture project file
   to produce a MISSING or INCONSISTENT finding, (b) writes `.pairmode-overrides` with
   that section's key in the exact `##`-free lowercased form SKILL.md documents (not
   derived from `_normalise("## " + header)`), (c) asserts the finding is absent from
   `audit_project`'s result, and (d) asserts a sibling section not named in the
   override still surfaces. This must be a test that would have failed before this
   fix and passes after.
4. Run the full `tests/pairmode/test_audit.py` suite and confirm green (Ensures 6).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_audit.py -q
```
Acceptance: green, including all pre-existing `TestAuditOverridesSuppress` tests and
the new documented-format regression test(s) from Instructions step 3.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q --tb=no
```
Acceptance: full suite green (no regression introduced elsewhere by the `_split_
sections` key-format change — any other test that keys off a section-key string, e.g.
`_check_overrides_health` tests or drift-report tests, must still pass with the
`##`-free key shape).

## Out of scope

- Changing the `.pairmode-overrides` file format itself, or SKILL.md's documented
  entry style — this story makes the code match the documented format, not the
  reverse.
- Fixing the `cora` project's own issue that surfaced this bug — that investigation is
  out of scope for this repo's story.
- Any other CER-170-adjacent cleanup not required to close the specific key-mismatch
  bug (e.g. broader refactoring of `_split_sections`/`_normalise`).
