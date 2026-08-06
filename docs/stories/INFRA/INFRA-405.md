---
id: INFRA-405
rail: INFRA
title: Fleet-gate trivial quality fixes (CER-189/198/199/203/204/205)
status: draft
phase: "135"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_map.py
  - skills/pairmode/scripts/scrub_fleet_names.py
  - .pairmode-fleet.local.json.example
touches:
  - tests/pairmode/test_scrub_fleet_names.py
  - tests/pairmode/test_fleet_map.py
  - docs/architecture.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

The fleet-name reconciliation gate shipped across the CER-172 remediation chain
(Phases 125, 130, 131, 132, 133) works, but six small quality gaps were found in
its supporting code and template. Each is independently scoped and confined to
one of the three files above: a template whose placeholder values read as if they
were real fleet names (CER-189), a fleet-map load path that fails open when the
parsed JSON is not a dict (CER-198), unescaped shell interpolation in the
emitted pre-commit hook template (CER-199), a `--root` fallback that silently
resolves to the wrong tree instead of erroring (CER-203), an unmapped-name count
that is structurally always zero (CER-204), and a conflict check that compares
case-exactly against a scrub that expands case variants (CER-205). Three of these
(CER-198, CER-203, CER-204) are fail-open or dead-signal shapes, which the
project's "never silently pass contradictions" constraint treats as worse than a
loud failure — that is why they are grouped as one story rather than deferred.

## Requires

None. Phases 130-133 are complete; the gate, its config example, and
`scrub_fleet_names.py`'s scrub/verify paths all exist in their post-CER-196
form.

## Ensures

1. **CER-189** — Every placeholder value in `.pairmode-fleet.local.json.example`
   is self-evidently a label, not a plausible fleet name (e.g. of the form
   `<repo-a>` / `EXAMPLE_...`), and the file still parses as valid JSON.
   Forbidden proxy: a comment saying the values are examples while the values
   themselves still look like real repository names.
2. **CER-198** — Loading a fleet-map file whose top-level JSON value is not an
   object (e.g. `[]`, `"x"`, `3`, `null`) raises/reports an error and the caller
   does not proceed to a "clean" verdict. Forbidden proxy: a warning printed
   while the gate still exits 0.
3. **CER-199** — Every value interpolated into the generated pre-commit hook
   text is shell-quoted (via `shlex.quote`), and a test asserts a value
   containing `$(...)`, a space, and a single quote survives into the hook body
   as an inert literal rather than as shell syntax.
4. **CER-203** — When `--root` is not supplied and the fallback cannot be
   determined to be the intended project root, the tool exits non-zero with a
   message naming the failure, instead of proceeding against a different tree.
   Forbidden proxy: defaulting to the process cwd and continuing.
5. **CER-204** — The unmapped-name count reported by the gate can be non-zero:
   a test constructs input containing a name that is not present in the fleet
   map and asserts the reported unmapped count is > 0 and names it.
6. **CER-205** — The conflict check matches names using the same case handling
   the scrub applies, so a name differing only in case from a mapped entry is
   detected as a conflict; a test asserts this for at least one case-variant
   pair.
7. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q` is green.

## Instructions

1. Work each CER above as a separate, minimal edit. Do not refactor the gate's
   structure; each fix should be local to the code path it names.
2. For CER-198 and CER-203, prefer an explicit error path over a repaired
   default — the project's "never silently pass contradictions" constraint makes
   a loud failure the correct resolution of a fail-open. (Ideology-alignment
   adjustment made at spec time to preserve that constraint's rationale, not
   just its letter.)
3. For CER-199, use `shlex.quote` rather than hand-rolled escaping.
4. For CER-204, first determine *why* the count is structurally zero (the
   counter is incremented in an unreachable branch, or computed from an
   already-filtered collection) and fix the cause, not the reported number.
5. For CER-205, make the conflict check reuse the scrub's own normalization
   helper rather than duplicating a `.lower()` — one normalizer, two callers.
6. Add tests to `tests/pairmode/test_scrub_fleet_names.py` and create
   `tests/pairmode/test_fleet_map.py` covering each numbered assertion in
   `## Ensures` that names a test. Include the `.example` JSON-parse check as a
   test so CER-189's regression is guarded, not just eyeballed.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_fleet_map.py tests/pairmode/test_scrub_fleet_names.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green. Run the full suite without `-x` so any pre-existing
failure does not mask a new one.

## Out of scope

- The remaining fleet-gate CERs batched into Phase 136 (CER-190/191/197/206) —
  coverage and leak-closure work, deliberately kept in a sibling phase.
- Any change to the fleet-map *schema* or to which names are considered
  in-fleet; this story fixes handling of the existing shape only.
- Wiring the gate into any additional hook or CI surface — the gate's
  invocation points are unchanged.

## Evidence

- CER-204's fix (moving `scrub_fleet_names.py verify()`'s mapped/excluded/
  unmapped reconciliation print from success-only to unconditional) changes
  observable output behavior that `docs/architecture.md` § Fleet discovery
  described ("`scrub_fleet_names.py verify()`'s success line reports
  mapped/excluded/unmapped counts"). Updated that section (and added
  `docs/architecture.md` to this story's `touches:`) to describe the new
  unconditional-print behavior instead, so the doc stays current with the
  code (a prior attempt at this story was reverted for exactly this
  documentation-currency gap).
