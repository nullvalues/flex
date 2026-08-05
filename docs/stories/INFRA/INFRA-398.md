---
id: INFRA-398
rail: INFRA
title: Fix .pairmode-overrides template/migration gap from audit.py key-format change (CER-180)
status: complete
phase: "128"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/.pairmode-overrides.j2
  - skills/pairmode/scripts/audit.py
touches:
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_overrides_boilerplate.py
  - tests/pairmode/test_sync.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

INFRA-391 (CER-170, already on main) changed `audit.py`'s `_split_sections` to strip a
leading `#+\s*` header marker before normalising, so `.pairmode-overrides` section keys
now match SKILL.md's documented no-`##` shape. Two things did not follow. First,
`skills/pairmode/templates/.pairmode-overrides.j2:9-13` — the operator-facing template
every scaffolded project receives — still documents the old `##`-included key format
("the full header line — `##` markers included") with examples like
`CLAUDE.md:## review checklist`, so new projects are instructed to write keys that can
never match. Second, no migration or dual-shape acceptance shipped, so every existing
fleet `.pairmode-overrides` written to the old instructions silently stopped matching:
audit.py's five `(dest_rel, key) in overrides` suppression checks (around audit.py:651,
672, 707, 723, 827) and sync.py's four destructive-write guards (sync.py:645, 702, 773,
826) all fall through to "not overridden" without a word to the operator.
`_check_overrides_health` (audit.py:566-582) reports parse errors only, so a whole file
of stale keys reads as healthy. That is a silent failure of destructive-write
protection — the exact shape `docs/ideology.md` § Never silently pass contradictions
forbids.

## Requires

- INFRA-391's `_split_sections` header-marker strip is present on main (it is).


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| tests/pairmode/test_overrides_boilerplate.py | pre-existing test asserted the pre-CER-170 stale ##-included key format the template docs are being fixed to stop documenting | 2026-08-05T22:25:09Z |

| tests/pairmode/test_sync.py | pre-existing test computed its injected AuditItem.section key without the ## strip audit.py's real _split_sections already applies since CER-170; the dual-shape override-load strip added in this story exposes the latent mismatch, so the test's key derivation needs to match real audit output | 2026-08-05T22:32:15Z |
## Ensures

1. `skills/pairmode/templates/.pairmode-overrides.j2` documents the current key format
   (header text only — no leading `#`/`##` markers — lowercased, whitespace-collapsed)
   and carries a worked example whose key is exactly what `_split_sections`/`_normalise`
   produce for the header line shown beside it.
2. A test in `tests/pairmode/test_audit.py` renders/reads the template, extracts its
   worked example's header line and key, and asserts the key equals what audit.py's own
   normalisation produces for that header — i.e. the documented example is verified by
   execution, not by eye. Forbidden proxy: a test that hardcodes the expected key string
   independently of audit.py's normalisation function, which would keep passing if the
   two drifted apart again.
3. A `.pairmode-overrides` file containing a legacy `##`-prefixed key (e.g.
   `CLAUDE.md:## review checklist`) still suppresses the same finding that the stripped
   form (`CLAUDE.md:review checklist`) suppresses — one dual-shape acceptance test per
   shape, both asserting suppression.
4. `_check_overrides_health` emits a distinct, non-fatal stale-shape diagnostic naming
   the offending file, the offending key, and its corrected form, for a
   `.pairmode-overrides` whose entry key still begins with `#` after normalisation-
   adjacent inspection; it emits no such diagnostic for a file whose keys are all in
   the current shape. Forbidden proxy: accepting the legacy key silently, with no
   diagnostic — acceptance without a migration signal is how this recurs.
5. Existing `TestAuditOverridesSuppress` cases still pass unchanged.

## Instructions

1. **Template.** Rewrite the format prose and examples at
   `skills/pairmode/templates/.pairmode-overrides.j2:9-13` to the current shape. Keep the
   `<dest-relative-path>:<section-key>` structure; change only the key description and
   the examples. Add a one-line note that keys written with leading `##` are accepted for
   now but reported as stale by `pairmode audit`.
2. **Dual-shape acceptance.** Apply the same `^#+\s*` strip audit.py already uses to
   override keys at the point the override set is loaded
   (`_load_overrides_with_diagnostics`), not at each membership check — one strip at load
   time makes all five audit.py checks and sync.py's four guards correct without
   duplicating logic or touching sync.py. If sync.py turns out to build its override set
   through a separate loader rather than this one, stop and report that as a scope
   finding rather than editing sync.py or copying the strip into it.
3. **Stale-shape diagnostic.** Have the loader record which raw keys required stripping,
   and have `_check_overrides_health` surface those as a warning-level (non-fatal)
   finding alongside its existing parse-error reporting. Both (a) and (b) from CER-180
   are built deliberately: acceptance alone would satisfy ideology's "never silently pass
   contradictions" only by making the contradiction permanent, and a diagnostic alone
   would leave fleet projects unprotected until each one is hand-edited.
4. **Tests.** Extend `tests/pairmode/test_audit.py` following `TestAuditOverridesSuppress`'s
   existing fixture conventions: legacy-key suppression, current-key suppression, health
   output with and without a stale entry, and the template round-trip check from Ensures 2.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_audit.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green, including the new dual-shape, health-diagnostic, and
template-round-trip cases.

## Out of scope

- `lesson_review.py`'s `.pairmode-drift-rejected` keys — same root cause, smaller blast
  radius (MEDIUM); file a separate CER if it needs fixing.
- Deduplicating the `^#+\s*` strip logic shared by audit.py and sync.py's
  `_normalise_section_boundary` — refactor-shaped MEDIUM, not urgent.
- The latent key collision between `## Foo` and `### Foo` in one file — MEDIUM, no live
  collision found.
- sync.py's stale `_header_from_key` docstring and dead code — LOW.
- Removing the dual-shape acceptance window — it is deliberately kept for one release;
  retiring it is a later story.
