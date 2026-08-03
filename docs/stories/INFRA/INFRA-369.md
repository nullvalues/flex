---
id: INFRA-369
rail: INFRA
title: Decouple a migrate test from the literal checkout directory name flex-harness (CER-146)
status: draft
phase: "119"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - tests/pairmode/test_pairmode_migrate.py
touches: []
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

CER-146 (LOW): `tests/pairmode/test_pairmode_migrate.py::test_to030_relocates_stale_flex_harness_hook_command`
fails whenever the pairmode test suite is physically run from inside a checkout literally named
`flex-harness` (e.g. `/mnt/work/flex-harness`) — a pre-existing defect (reproduces back at
cp-115), not introduced by any Phase 116 story. The test asserts the migrated hook command does
not contain the substring `"flex-harness"`, but the migration code (or the fixture project's
derived path) picks up the literal directory name of wherever `pairmode_migrate.py`'s own module
lives — which legitimately contains `flex-harness` when the suite runs from that checkout. This is
a test-environment coupling bug, not a real migration defect. Fix direction: parameterize the
test's fixture project path/name so the assertion is independent of the literal directory the
suite happens to run from, or assert on a synthetic marker instead of the substring
`"flex-harness"`. File: `tests/pairmode/test_pairmode_migrate.py`. Surfaced during Phase 116's
checkpoint-tag promotion when the full suite was run post-merge inside `/mnt/work/flex-harness`.

Picked up now as part of era 004's Phase 119 goal of draining the CER backlog to zero unresolved
operational findings.

## Requires

- No prior story in this phase. `tests/pairmode/test_pairmode_migrate.py` and
  `skills/pairmode/scripts/pairmode_migrate.py` exist at HEAD and the migrate suite is otherwise
  green when run from a checkout whose directory name is not `flex-harness`.

## Ensures

1. `test_to030_relocates_stale_flex_harness_hook_command` no longer asserts on the ambient literal
   `"flex-harness"`. Its pass/fail outcome is determined only by fixture state the test itself
   creates — a synthetic stale marker it writes into the fixture project's hook command — not by
   the name of the directory the suite is running from.
   **Forbidden proxy:** skipping, xfailing, or early-returning the test when the checkout is named
   `flex-harness`. The test must still exercise the relocation and still fail if relocation breaks.
2. The test passes when the migrate module's own resolved location sits under a path segment
   literally named `flex-harness`, and passes when it does not. A test exercising the
   harness-named ambient case exists (e.g. by running the migration against a fixture project
   rooted under a tmp directory containing a `flex-harness` segment) and asserts relocation
   succeeded.
3. The test still fails if the relocation behaviour in `pairmode_migrate.py` regresses — verified by
   temporarily reverting/neutering the relocation branch locally and observing a red test, then
   restoring. State the observed failure in the build notes.
4. `skills/pairmode/scripts/pairmode_migrate.py` is unchanged by this story (this is a
   test-environment coupling bug, not a migration defect).
5. `uv run pytest tests/pairmode/ -q` is green.

## Instructions

1. Read `test_to030_relocates_stale_flex_harness_hook_command` in
   `tests/pairmode/test_pairmode_migrate.py` and identify exactly where the ambient checkout name
   leaks in: either the fixture's pre-migration hook command is derived from the running module's
   path, or the post-migration assertion is a bare `"flex-harness" not in command` substring check.
2. Fix by making the fixture self-describing: seed the fixture project's stale hook command with a
   synthetic stale path the test constructs itself (a unique marker token, not `flex-harness`), and
   assert post-migration that the marker token is gone and that the command equals/contains the
   expected relocated target. Do not weaken the assertion to "contains something plausible".
3. Add the harness-named ambient case (Ensures 2) as a second test or a parametrization, rather
   than only fixing the existing one — the whole point is that the outcome must be invariant to the
   ambient directory name.
4. Do not touch `pairmode_migrate.py`. If the investigation shows the migration code genuinely does
   emit the running module's directory name into the migrated command in a way that is wrong for
   real users, stop and file a CER rather than widening this story.

Ideology note: the fix keeps a single source of truth for the test's expectation (the fixture the
test writes) rather than an implicit dependency on the environment — the same "explicit over
inferred" reasoning as the project's core convictions, and it preserves the constraint that a test
must never silently pass when the behaviour it guards has regressed.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_pairmode_migrate.py -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```

Acceptance: both green (run the full suite without `-x` so no later failure is masked), including
the new harness-named ambient-path test.

## Out of scope

- Auditing the rest of `tests/pairmode/` for other ambient-path couplings. Any further instance
  found while working here is a CER, not an inline fix in this story.
- Any change to `pairmode_migrate.py`'s relocation logic or to the `to030` migration's behaviour.
  (Spec-preflight reports `pairmode_migrate.py` as a declared-scope gap; that is intentional — the
  file is named only as read context and as the subject of Ensures 4's "unchanged" assertion, so it
  is deliberately absent from `primary_files`/`touches`.)
- Making the whole suite runnable from arbitrary checkout names as a general guarantee — this story
  fixes the one test named in CER-146.
