---
id: INFRA-404
rail: INFRA
title: Recognize OBSOLETE as a CER resolution marker (CER-207)
status: complete
phase: "134"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/cer.py
  - docs/architecture.md
touches:
  - tests/pairmode/test_cer.py
  - skills/pairmode/scripts/flex_build.py
narrative_roles: []
---

## Context

`cer.py`'s resolution-marker grammar recognizes only `RESOLVED` and `SUPERSEDED`
as closing a backlog row. This project's own CER backlog closes rows with an
`OBSOLETE` annotation instead — used 19+ times — and the shared grammar does not
recognize it. The consequence is that already-handled rows report as permanently
open to every consumer of the grammar (groom, the gate, next-action), so the
backlog's open count never drops and the signal degrades into noise. This story
extends the grammar to accept `OBSOLETE` alongside the two existing markers, adds
a regression test, and updates the published grammar documentation so the three
markers are recorded as one set rather than re-derived per consumer.

## Requires

None — the change is contained to `cer.py`'s resolution-marker recognition and
the architecture doc that publishes the grammar.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| skills/pairmode/scripts/flex_build.py | reviewer FAIL-cause: _cer_do_now_gate_message (flex_build.py:3923) independently hardcodes RESOLVED/SUPERSEDED literal, never updated for OBSOLETE; must derive from cer.RESOLUTION_MARKERS to make architecture.md's single-implementation claim true | 2026-08-06T16:38:53Z |

## Ensures

A backlog row annotated `OBSOLETE` is reported as resolved by `cer.py`'s
resolution-marker check exactly as `RESOLVED` and `SUPERSEDED` rows are, with
matching case/formatting tolerance; forbidden proxy: `OBSOLETE` handled at one
call site (or by a caller-side special case) while the shared grammar still
reports the row open to the other consumers.

## Instructions

1. In `skills/pairmode/scripts/cer.py`, add `OBSOLETE` to the resolution-marker
   set used by `is_resolution_marked`, in the same place the existing two markers
   are declared — not as a branch in any caller. If the markers are currently
   inline literals, lift them to a single module-level constant so the three
   markers have exactly one definition.
2. Match the existing matching semantics exactly (same case handling, same
   anchoring/whitespace tolerance). Do not tighten or loosen how `RESOLVED` and
   `SUPERSEDED` currently match.
3. Add regression tests to `tests/pairmode/test_cer.py`: an `OBSOLETE` row is
   marked resolved, the two pre-existing markers still are, and a row with no
   marker is still reported open.
4. Update the resolution-marker grammar in `docs/architecture.md` to list all
   three markers and note that `OBSOLETE` was added by CER-207 because the
   backlog convention already used it.

Note: spec-preflight warns that `OBSOLETE` has no definition in the source tree.
That is expected and intentional — this story is what introduces it.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_cer.py -q
```
Acceptance: green, including the new `OBSOLETE` cases.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: no new failures.

## Out of scope

- Rewriting existing `OBSOLETE` backlog rows to say `RESOLVED` — the grammar
  adapts to the convention, not the other way round.
- Adding any further marker vocabulary (e.g. `WONTFIX`, `DUPLICATE`); only the
  one marker this project demonstrably already uses is added here.
- Changing what groom/gate/next-action do with a resolved row — this story only
  changes which rows are recognized as resolved.

## Evidence

Covered-contracts gate (INFRA-317): `cer.py` intersects the
`## Pairmode build loop::skills/pairmode/scripts/cer.py` pair. Both halves
read before editing:

- `docs/architecture.md` § Pairmode build loop (pre-edit text): "The guard
  classifies every other Do Now row as resolved or unresolved via
  `cer.is_resolution_marked` (INFRA-322/CER-130): a row is resolved when the
  keyword `RESOLVED` or `SUPERSEDED` ... `cer.is_resolution_marked` is the
  single implementation of this grammar; no consumer re-derives its own
  test." — this is the exact claim attempt 1 left false: it asserts no
  consumer re-derives the marker list, but `flex_build.py`'s
  `_cer_do_now_gate_message` (checkpoint-tag refusal message) hardcoded the
  literal `"RESOLVED/SUPERSEDED"` independently of `cer.py`, and `cer.py
  gate`'s own CLI refusal message (`cli`, ~line 739) hardcoded the same
  literal a second time.
- `skills/pairmode/scripts/cer.py` (pre-edit): `_RESOLUTION_MARKER_RE` inlined
  `(?:RESOLVED|SUPERSEDED)` directly in the compiled pattern with no shared
  constant, and both the checkpoint-tag message (`flex_build.py`) and the
  `cer.py gate` CLI message independently wrote out `"RESOLVED/SUPERSEDED"`
  as prose.

Resolution: lifted the keyword tuple to `cer.RESOLUTION_MARKERS = ("RESOLVED",
"SUPERSEDED", "OBSOLETE")`, built `_RESOLUTION_MARKER_RE` from it, and updated
**both** call sites that named the marker set in a user-facing message —
`cer.py`'s own `gate` CLI message and `flex_build.py`'s
`_cer_do_now_gate_message` — to format `cer.RESOLUTION_MARKERS` instead of a
hardcoded literal, so `docs/architecture.md`'s "single implementation ... no
consumer re-derives its own copy of the marker list" claim is true across both
call sites, not just the regex. `docs/architecture.md` updated to name both
call sites explicitly and to record the CER-207 fix to the prior drift.
