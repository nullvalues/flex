---
id: INFRA-403
rail: INFRA
title: Fix invalid-JSON fleet-config example causing silent fail-open verify (CER-196)
status: draft
phase: "133"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_map.py
  - skills/pairmode/scripts/scrub_fleet_names.py
  - .pairmode-fleet.local.json.example
touches:
  - tests/pairmode/test_scrub_fleet_names.py
  - skills/pairmode/scripts/fleet_discovery.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

`.pairmode-fleet.local.json.example` is the template an operator copies to create
their local fleet-name map, but it opens with `//` comment lines, which JSON does
not permit — so the copied file fails to parse. `fleet_map.load_local_fleet_map`
swallows the resulting `JSONDecodeError` and returns an empty map, and
`scrub_fleet_names.verify()` then reads that empty map as "no fleet names are
configured" and passes. The leak-prevention gate is therefore unusable and
reports green while unusable — exactly the "silently pass contradictions"
failure this project's ideology names as worse than no gate at all. This story
makes the shipped template valid JSON and makes the loader fail loudly instead
of degrading to empty on a parse error.

## Requires

None — the fix is contained to the template, its loader, and the one caller that
misreads the loader's degraded return.


## Scope widenings

| path | reason | widened_at |
| --- | --- | --- |
| skills/pairmode/scripts/fleet_discovery.py | fleet_map.load_local_fleet_map now raises FleetMapConfigError on malformed JSON (CER-196); fleet_discovery.py's own wrapper must catch it locally to preserve its documented never-raises contract, which is out of this story's scope to change and has its own existing tests asserting it | 2026-08-06T03:24:37Z |

## Ensures

The committed `.pairmode-fleet.local.json.example` parses with `json.loads`, a
malformed local fleet-config file makes `load_local_fleet_map` fail loudly
rather than return an empty map, and `scrub_fleet_names.verify()` reports that
failure as a gate failure (non-zero exit) rather than passing.

Forbidden proxy: a warning line emitted about the parse error while an empty map
is still returned and `verify()` still exits 0.

## Instructions

1. Rewrite `.pairmode-fleet.local.json.example` as valid JSON. Carry the
   explanatory text that the `//` lines held in a JSON-legal field (e.g. a
   top-level `"_comment"` string or array) so the operator guidance survives the
   format change; do not simply delete it.
2. In `fleet_map.py`'s `load_local_fleet_map`, stop swallowing `JSONDecodeError`
   (and any other malformed-content error) into an empty-map return. Raise a
   clear error naming the offending path and the parse problem. A genuinely
   absent config file must keep its existing "no config" behaviour — absent and
   malformed are different answers and must not collapse into one.
3. Update `scrub_fleet_names.verify()` so the raised error surfaces as a gate
   failure with a non-zero exit and a message identifying the unparseable file,
   not as a pass. Check every other `load_local_fleet_map` caller in
   `fleet_map.py`/`scrub_fleet_names.py` and make each one propagate the failure
   rather than reinstating the empty-map fallback locally.
4. Add tests to `tests/pairmode/test_scrub_fleet_names.py` covering: the
   committed template parses as JSON; a malformed config file causes
   `load_local_fleet_map` to raise; `verify()` on a malformed config exits
   non-zero; and a control case where a valid config still verifies as before.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: suite green, including the new template-parses and
malformed-config-fails-loudly cases.

## Out of scope

- Adding comment-stripping / JSON5 tolerance to the loader so `//` lines parse —
  the template is being made valid JSON, not the parser made lenient.
- Changing the fleet-name map's schema, key format, or the scrub/reconciliation
  logic itself (CER-194/CER-195 territory) — this story fixes only the
  template's validity and the parse-failure path.
- Migrating any operator's already-copied `.pairmode-fleet.local.json`; the
  loud failure is the migration signal.
