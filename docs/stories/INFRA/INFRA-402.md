---
id: INFRA-402
rail: INFRA
title: Add excluded-siblings mechanism to the fleet-name reconciliation gate (CER-195)
status: draft
phase: "132"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/fleet_map.py
  - skills/pairmode/scripts/scrub_fleet_names.py
  - .pairmode-fleet.local.json.example
touches:
  - tests/pairmode/test_scrub_fleet_names.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

The `--verify` reconciliation added by INFRA-400/401 treats every on-disk sibling
directory under the fleet root that is absent from `.pairmode-fleet.local.json` as
an unmapped failure. Some sibling directories are legitimately not private
third-party fleet clients and must never be added to the anonymized map (this
project's own documented history, and the operator's own already-published work).
With no way to say "deliberately out of scope," `--verify` can never exit clean:
the same known-noisy list prints on every run and a genuine new leak becomes
indistinguishable from expected noise, which is exactly the trust the gate exists
to provide. This story adds a local-config-only exclusion list, following the same
CER-172/188/194 contract that real names live only in the gitignored local config
and never in committed source.

**Scope decision — exclusion vs. the text-scrub pass.** Exclusion is defined
against the *sibling-directory reconciliation* only, and this deliberately (not
incidentally) leaves excluded names untouched by the text scrub as well: the
`apply()`/`verify()` substitution pattern is built from `real_names_to_labels`,
i.e. from mapped entries only, so a name with no label has nothing to be replaced
*with* and can never be rewritten or reported as a hit. That is the correct
outcome here — the excluded siblings are precisely the ones whose names appear in
committed text on purpose, and silently rewriting them would corrupt legitimate
documentation. The consequence of the alternative reading (letting an exclusion
also suppress a scrub that a label *does* exist for) is a real leak, so the two
lists must stay mutually exclusive: a name that is both mapped and excluded is a
configuration contradiction, not a precedence question, and must fail loudly
rather than resolve to one side.

## Requires

- INFRA-400/401 complete: `fleet_map.py` exists with `repo_entries` /
  `unmapped_sibling_repos` / `FLEET_ROOT_CONFIG_KEY`, and `scrub_fleet_names.py`
  has `_reconcile_fleet_root` wired into `verify()`.

## Ensures

- A sibling directory whose basename is listed in the exclusion list is absent
  from `unmapped_sibling_repos`' return value and does not cause `verify()` to
  return non-zero; forbidden proxy: `verify()` still printing the directory in
  its reconciliation list while returning 0.
- A sibling directory that is neither mapped nor excluded is still returned by
  `unmapped_sibling_repos` and still makes `verify()` return non-zero.
- An excluded name occurring in a tracked file's text is neither rewritten by
  `apply()` nor reported as a hit by `verify()`.
- A name present both as a mapped entry and in the exclusion list makes
  `verify()` return non-zero with a message naming the mapped label (never the
  real name).
- `repo_entries` excludes the exclusion key as well as `_fleet_root`, so no
  reserved key is ever interpreted as a `{label: real_path}` repo entry.
- `verify()`'s success line keeps its existing `verify OK: zero remaining
  real-name hits` prefix and additionally reports the mapped/excluded/unmapped
  counts.
- `.pairmode-fleet.local.json.example` contains the exclusion key with synthetic
  placeholder names only, and no file changed by this story contains any real
  sibling-repo name.

## Instructions

1. In `fleet_map.py`, add `EXCLUDED_REPOS_CONFIG_KEY = "_excluded"` — a reserved
   key inside the existing `.pairmode-fleet.local.json`, holding a list of
   directory basenames. Chosen over a second sibling file because `_fleet_root`
   already establishes the reserved-key shape in this file, the loader and its
   gitignore/`.example` plumbing already exist, and a second file would need its
   own load/missing/malformed handling for one array.
2. Generalise `repo_entries` to filter *all* reserved keys (a module-level
   `RESERVED_CONFIG_KEYS` frozenset — introduced by this story, hence the expected
   spec-preflight constant warning), not just `_fleet_root`. This is load-bearing:
   `fleet_discovery.py` also calls `repo_entries`, and a list value reaching
   `real_names_to_labels` would raise.
3. Add `excluded_repo_names(fleet_map) -> set[str]` returning the basenames of the
   exclusion entries (normalise via `Path(entry).name` so a full path also works),
   tolerating a missing key or a non-list value by returning an empty set — the
   loader's never-raises contract.
4. Subtract that set from `unmapped_sibling_repos`' result (compare on `d.name`).
5. In `scrub_fleet_names.py`'s `verify()`, add the mapped/excluded conflict check
   (Ensures 4) and extend the success line with the three counts. Keep the
   substitution pattern derived solely from mapped entries — do not add excluded
   names to it in any form.
6. Update `.pairmode-fleet.local.json.example` with an `"_excluded"` array of
   synthetic names (e.g. `"excluded-legacy-tool"`), plus a sibling
   `.example`-appropriate hint that entries are directory basenames deliberately
   out of anonymization scope.
7. Tests go in `tests/pairmode/test_scrub_fleet_names.py` using tmp_path fixtures
   with synthetic names only, covering each `## Ensures` case.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_scrub_fleet_names.py tests/pairmode/test_fleet_discovery.py -q
```
Acceptance: green, including the new exclusion cases, with `test_fleet_discovery.py`
confirming the widened `repo_entries` filter did not regress its callers.

## Out of scope

- Populating the exclusion list with this project's real directory names — a
  manual, local operator action performed directly against the gitignored config,
  never by a builder.
- `fleet_discovery.py`'s write-time anonymization: an excluded sibling still
  renders as `<unmapped-repo-n>` in snapshot output. That is leak-safe by
  construction and is a separate decision from the reconciliation gate.
- CER-189/190/191 (three LOW findings) and CER-192 (git-history remediation).
