---
id: INFRA-410
rail: INFRA
title: Fix silent YAML frontmatter truncation on embedded comment introducer (CER-211)
status: complete
phase: "140"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
touches:
  - tests/pairmode/test_story_new.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

INFRA-409 (CER-166/167/187) added a YAML quoting helper to `story_new.py` so
that operator-supplied `primary_files:`/`touches:` scalars round-trip safely
through YAML instead of being silently reinterpreted. CER-211 found that the
helper's comment-introducer detection only checks for `#` at the start of the
scalar, not a ` #` occurring anywhere inside it — so a value like
`foo bar #baz.py` is written unquoted, and on the next YAML parse everything
from the ` #` onward is dropped as a comment, silently truncating the stored
value. This is the exact silent-data-loss shape CER-167/INFRA-409 exists to
prevent, just on a case that fix missed. This story closes that gap.

## Requires

- INFRA-409 is complete: `skills/pairmode/scripts/story_new.py` contains a
  YAML-quoting decision helper (introduced for CER-166/167/187) that
  `tests/pairmode/test_story_new.py` already exercises.

## Ensures

- A scalar value containing an embedded ` #` (a space followed by `#`)
  anywhere in the string — not only at position 0 — is quoted by the helper
  before being written into story frontmatter, so that loading the written
  file back with `yaml.safe_load` reproduces the original string exactly,
  with nothing truncated at the ` #`.
- Forbidden proxy: the helper merely logging or warning about the embedded
  `#` while still emitting the value unquoted does not satisfy this — the
  written YAML itself must be quoted, verified by round-tripping the written
  file through `yaml.safe_load` and comparing to the original input.
- The existing leading-`#` and other already-covered unsafe-character cases
  (from INFRA-409) continue to round-trip correctly — this fix does not
  regress them.

## Instructions

1. In `skills/pairmode/scripts/story_new.py`, find the YAML quoting/escaping
   decision helper added for CER-167 (INFRA-409) that decides whether a
   scalar needs quoting before being written into frontmatter.
2. Widen its comment-introducer check from "starts with `#`" to "contains
   ` #` (space then `#`) anywhere in the string" — this is the substring
   YAML treats as a comment introducer mid-scalar, per the YAML spec's plain
   scalar rules, not only at the scalar's start.
3. Route any string matching this to the same quoting path already used for
   the other unsafe-character cases the helper handles — no new quoting
   mechanism, just wider detection.
4. Add regression cases to `tests/pairmode/test_story_new.py`: a value with
   an embedded ` #` mid-string, and a value with ` #` immediately followed by
   more content (confirming nothing after the introducer is lost on
   round-trip). Assert via `yaml.safe_load` on the written file, matching the
   existing round-trip test style from INFRA-409.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py -q
```
Acceptance: green, including the new embedded-` #` round-trip cases.

## Out of scope

- YAML 1.1 bare-value type coercion (e.g. unquoted `yes`/`no`/`on`/`off`
  scalars being read back as booleans instead of strings) — a related MEDIUM
  noted in this phase's Goal as "time permitting," but it requires different
  detection logic (type-coercion-safe quoting, not comment-introducer
  detection) than this story's fix. Left for a follow-on story rather than
  folded in here, per this project's proportionality convention.
- Raw control-character passthrough hardening — the other related MEDIUM
  named in the phase Goal; same reasoning, deferred to its own story.
