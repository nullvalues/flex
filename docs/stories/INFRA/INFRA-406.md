---
id: INFRA-406
rail: INFRA
title: Fleet-gate coverage and leak-closure fixes (CER-190/191/197/206)
status: draft
phase: "136"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/scrub_fleet_names.py
  - skills/pairmode/scripts/fleet_discovery.py
  - skills/pairmode/scripts/fleet_map.py
touches:
  - tests/pairmode/test_scrub_fleet_names.py
  - tests/pairmode/test_fleet_discovery.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The fleet-name reconciliation gate (Phases 125/130/131/132/133) now runs, but four
real gaps remain in what it actually covers. The scrub pattern matches only the
bare, exact-case fleet token, so case variants and domain-suffixed forms pass
through un-anonymized (CER-190). `fleet_discovery`'s sibling scan silently reports
fewer candidates than the entries it considered — a 16-to-15 drop with no record of
which entry vanished or why (CER-191). The `--json` output anonymizes only its
top-level surface, leaving real machine paths inside the nested
`duplicate_hooks`/`machine_absolute_hooks` entries (CER-197). And the
malformed-config error path swallows the failure and falls back to a default root,
discarding a custom `_fleet_root` and silently narrowing anonymization scope
(CER-206). All four are the same failure shape the gate exists to prevent: a check
that reports clean while the thing it checks leaked.

## Requires

Phase 133 complete (`fleet_map.py`'s config parsing and `resolve_fleet_root` in
their post-CER-196 form).

## Ensures

1. **CER-190** — the scrub replaces a fleet name in every case variant (`name`,
   `Name`, `NAME`, mixed) and when carrying a domain suffix (`name.com`,
   `name.io`), and still leaves substring-only occurrences inside unrelated longer
   words untouched. *Forbidden proxy:* matching only the exact-case bare token and
   leaving `Name`/`NAME`/`name.io` in the output.
2. **CER-191** — for a fleet map whose entry count exceeds its resolvable-repo
   count, `fleet_discovery`'s sibling scan accounts for every entry it dropped:
   each non-candidate is either counted separately or named with its reason in
   output. *Forbidden proxy:* a candidate total that shrinks (16 → 15) with no
   record of which entry was dropped.
3. **CER-197** — in `--json` mode, no string at any nesting depth of the emitted
   object contains an un-anonymized fleet name or real machine path, including
   values inside `duplicate_hooks` and `machine_absolute_hooks` list entries.
   *Forbidden proxy:* scrubbing only top-level string fields while nested
   list-of-dict values pass through raw.
4. **CER-206** — when the fleet config is malformed, the run surfaces the failure
   (non-zero exit or an explicit error record) rather than continuing on a default
   root. *Forbidden proxy:* a caught exception that returns the default fleet root
   and proceeds with silently narrowed anonymization scope.

## Instructions

1. **CER-190** — widen the scrub matcher in `scrub_fleet_names.py` to be
   case-insensitive and to match a fleet name followed by a domain suffix. Keep the
   existing word-boundary guard so unrelated longer words are not partially
   rewritten; replacement should preserve the anonymized placeholder shape already
   in use rather than introducing a new one.
2. **CER-191** — in `fleet_discovery.py`'s sibling scan, stop dropping entries
   silently. Reserved config keys (`_fleet_root`, `_excluded`, …) and unresolvable
   paths are legitimate non-candidates, but each must be visible in the output
   (separate count or named reason). This is the ideology's *Never silently pass
   contradictions* constraint applied to the gate's own reporting: a shrinking
   count with no rationale is exactly the false-confidence failure that rule
   protects against.
3. **CER-197** — make the `--json` anonymization recurse over the full emitted
   structure (dicts, lists, nested combinations) instead of scrubbing a fixed set
   of top-level fields, so `duplicate_hooks` and `machine_absolute_hooks` entries
   are covered by construction rather than by enumeration.
4. **CER-206** — on malformed-config parse failure, do not fall back to the default
   root. Propagate the error (or return an explicit error result the caller
   surfaces) so a custom `_fleet_root` is never discarded without the operator
   seeing it.
5. Add tests to `tests/pairmode/test_scrub_fleet_names.py` (fixes 1, 4) and
   `tests/pairmode/test_fleet_discovery.py` (fixes 2, 3) covering each numbered
   `## Ensures` assertion, including at least one test that would fail against the
   corresponding forbidden proxy.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_scrub_fleet_names.py tests/pairmode/test_fleet_discovery.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: both green, including the new cases for all four fixes.

## Out of scope

- The remaining fleet-gate CERs routed to sibling phases — quality fixes
  (CER-189/198/199/203/204/205, Phase 135) and overrides/audit key-shape work
  (CER-182/184/185/202, Phase 137). This story fixes only the four coverage/leak
  defects named above.
- Changing the anonymization placeholder format or the fleet-config schema — this
  story widens what is matched and reported, not what the output looks like.
- Re-scrubbing already-published artifacts; the fix is forward-looking on the gate
  itself.
