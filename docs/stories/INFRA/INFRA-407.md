---
id: INFRA-407
rail: INFRA
title: Overrides/audit key-shape quality fixes (CER-182/184/185/202)
status: complete
phase: "137"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/audit.py
  - skills/pairmode/scripts/lesson_review.py
  - skills/pairmode/scripts/pairmode_drift_report.py
touches:
  - tests/pairmode/test_audit.py
  - tests/pairmode/test_lesson_review.py
  - tests/pairmode/test_drift_report.py
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Phases 123/128/129 changed the `.pairmode-overrides` section-key shape and
de-duplicated its parser, but left four residual gaps behind the change. The
diagnostic audit.py prints when it finds a stale-shape key still suggests a
corrected form that is itself invalid under the new shape (CER-182), so a user
who follows the advice stays broken. lesson_review.py persists rejected-pattern
keys in the pre-change shape, so those records are stranded — written under one
key shape and looked up under another (CER-184). audit.py and
pairmode_drift_report.py disagree on case handling for mixed-case override keys,
so the same file can be clean in one tool and a finding in the other (CER-185).
And audit.py's remediation advice for an overrides-shape finding is the generic
string, which describes an action that cannot resolve that finding (CER-202).
All four are quality fixes on an already-shipped mechanism; none change the key
shape itself.

## Requires

Phases 123, 128 and 129 complete (the current key shape and the de-duplicated
parser are in place). No other preconditions.

## Ensures

- audit.py's stale-shape diagnostic names a corrected key that the same
  codebase's own override-key parser accepts; forbidden proxy: the message text
  merely changing while the suggested key still fails to parse.
- lesson_review.py reads back a rejected-pattern record that was persisted under
  the pre-CER-181 key shape, and re-persists it under the current shape;
  forbidden proxy: new records working while pre-existing ones stay unreachable.
- audit.py and pairmode_drift_report.py return the same clean/finding verdict
  for the same mixed-case override key, via one shared normalization helper
  rather than two independently-maintained rules; forbidden proxy: the two rules
  being edited to match today while remaining separate.
- The remediation text audit.py emits for an overrides-shape finding is specific
  to that finding and describes an action that resolves it — not the generic
  remediation string used for other findings.
- `tests/pairmode/test_audit.py`, `tests/pairmode/test_lesson_review.py` and
  `tests/pairmode/test_drift_report.py` each contain at least one new test
  covering the fix in their subject module, and the pairmode suite is green.

## Instructions

1. Locate the override-key normalization used by audit.py and the one used by
   pairmode_drift_report.py. Pick audit.py's behaviour as canonical (it is the
   one sync.py already agrees with), lift it into a single shared helper, and
   have pairmode_drift_report.py call that helper instead of its own rule.
   Do not change sync.py.
2. Fix the stale-shape diagnostic in audit.py so the corrected key it suggests
   is produced by the current key-shape constructor/parser rather than by an
   inline string built to the old shape. Assert in a test that the suggested
   key round-trips through the parser.
3. In lesson_review.py, when a rejected-pattern lookup misses under the current
   key shape, fall back to the pre-CER-181 shape; on a hit, rewrite the record
   under the current shape so the fallback is not needed again. Keep the
   fallback read-only in the miss case (no key is invented for patterns that
   were never persisted).
4. Give the overrides-shape finding its own remediation string in audit.py,
   replacing the generic one for that finding only; leave every other finding's
   remediation unchanged.
5. Add the tests named in `## Ensures` alongside the existing cases in each
   file.

Note (ideology check, Step 4a): step 3's fallback rewrite is a state write from
a skill script, which the "Sidebar owns all state writes" constraint permits
(skill scripts are named writers); no hook is involved, so the hook-relay
constraint is untouched.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: suite green, including the new audit / lesson_review / drift_report
cases.

## Out of scope

- Changing the `.pairmode-overrides` section-key shape itself, or re-running any
  migration over existing override files — this story only fixes tools that
  handle the already-decided shape.
- sync.py's own normalization, which already agrees with audit.py and is not a
  primary file here.
- The remaining fleet-gate CERs scheduled for phases 135/136 and the
  shadow-reviewer scope_guard work in phase 138.
