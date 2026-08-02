---
id: INFRA-342
rail: INFRA
title: Reconcile CLAUDE.build.md and its .j2 template; add an automated dispatch-parity drift check
status: draft
phase: "117"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - CLAUDE.build.md
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - tests/pairmode/test_claude_build_parity.py
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->
## Context

HIGH finding F5 of `docs/build-loop-cold-eyes-review-20260801.md`, corroborated independently by
both reviewers: `CLAUDE.build.md` (live) and `skills/pairmode/templates/CLAUDE.build.md.j2` (the
template rendered for downstream/fresh-bootstrapped projects) have drifted in both directions
because Phase 116/117 stories each edited only one of the two files.

**Re-verified against both files fresh, after INFRA-339/340/341/344 all landed (this story is
scheduled last in the phase Ordering section precisely so it captures the final shape, not a
mid-phase snapshot).** Most of F5's originally-listed divergence has already been closed
incidentally: INFRA-341 and INFRA-344 both added their `ACTION_SUBAGENT_TYPE` entries
(`spawn-gate-worker: gate-worker`, `spawn-spec-writer: spec-writer`) to **both** files, and
INFRA-339 removed the `pause-context` action from `next_action.py` entirely — neither file
mentions `pause-context` any more, so that half of F5 is now moot rather than unresolved. Three
concrete divergences remain, verified by direct diff of the two files as they stand on disk today:

1. **`checkpoint-docs: docs-reviewer` is still missing from the template's `ACTION_SUBAGENT_TYPE`
   dict** (`skills/pairmode/templates/CLAUDE.build.md.j2` line 15). It is present in live
   `CLAUDE.build.md` (line 15, added by INFRA-325). The template's own prose one paragraph above
   *names* `checkpoint-docs` as one of the three read-mostly checkpoint workers, but the dispatch
   map entry that lets the loop actually resolve `ACTION_SUBAGENT_TYPE["checkpoint-docs"]` without
   a `KeyError` is absent — a project freshly bootstrapped from this template today cannot dispatch
   `checkpoint-docs`, exactly the class of bug F5 originally described, just narrowed from three
   entries to one.
2. **Live `CLAUDE.build.md`'s Build standards line has no `intent_review=` key at all**, and the
   paragraph lacks the explanatory prose the template carries (the pre-build `spawn-intent-reviewer`
   case and the `record-intent-review --phase-key <a.scalar> --verdict <PASS|FAIL|ALIGNED>` command
   to run afterward). `intent_review=` (INFRA-315) is still a live, functioning opt-in read by
   `next_action.py`'s `_intent_review_opt_in` (`skills/pairmode/scripts/next_action.py:928-931`) —
   it was never removed, unlike `pause-context` — so this is a live capability gap, not stale prose:
   if flex's own `CLAUDE.build.md` ever sets `intent_review=pre-build`, there is no instruction
   anywhere in the live file explaining what to do with the resulting `spawn-intent-reviewer`
   phase-key case.
3. **The template's catch-all `else` branch lacks the INFRA-328 comment** describing how
   `spawn-loop-breaker`'s `a.reason` carries the double-fail story's recorded `fail_cause` and how
   to build the `LOOP-BREAKER:` prompt from it. Live's `else` branch carries this comment; the
   template's does not. `next_action.py`'s INFRA-328 behavior (`a.reason` carrying `fail_cause`) is
   general resolver behavior, not flex-specific, so the guidance belongs in the template too.

Everything else that differs between the two files — the literal `/mnt/work/flex-harness/...`
paths, "flex-harness" as the named project, the hardcoded `main` branch in the `git push` command,
and checkpoint-tag's step 3 "promote" clause (`git -C /mnt/work/flex-harness merge --ff-only
cp-<phase-key>`) — is **intentional, documented flex-specific customization**
(`docs/architecture.md` § Release channel — flex-harness), not drift. It must not be touched or
"genericized" by this story; it is the correct rendering of the template's `{{ pairmode_scripts_dir
}}`/`{{ project_name }}`/`{{ default_branch }}` variables for this specific project, not a
divergence to reconcile.

`pairmode_drift_report.py` nominally compares the two files (`_analyse_file`, section-keyed on `##`
headings) but two structural gaps stopped it from catching this drift: (a) nothing invokes it
automatically anywhere in this repo — it is a manual cross-project CLI (`--projects <dir>...`),
never wired into a test, a checkpoint gate, or CI, so its output is never read unless a human
remembers to run it; and (b) even when run by hand against flex itself
(`uv run python skills/pairmode/scripts/pairmode_drift_report.py --projects .`), its comparison
granularity is a whole `##`-delimited section — `## Build loop` and `## Checkpoint` each contain
several hundred words including the entire `ACTION_SUBAGENT_TYPE` dict, the whole dispatch loop,
and the Build standards line as one block. Because flex's own file *always* differs from a naive
template render within those same two sections (the intentional path/name substitutions above),
the tool reports those sections as `DRIFT` unconditionally — the signal a single missing dispatch
key would add is invisible inside noise that is already always present. Fixing (a) or (b) generally
for `pairmode_drift_report.py`/`audit.py` (multi-project section-diffing tool) is out of scope here;
this story closes the gap with a narrower, purpose-built check instead (see Instructions/Tests) —
extracting the specific structural invariants (dispatch-map key sets, Build-standards key sets) that
must match between the two files regardless of literal path substitutions, and asserting on those
directly rather than diffing whole rendered sections.

## Requires

1. INFRA-339 merged (`b7ed8d8e`) — removed the unreachable `pause-context` Row-8 check; both files
   must be free of `pause-context` references (verified above — already true).
2. INFRA-340 merged (`06e412c1`) — checkpoint-security/checkpoint-intent model-selector wiring;
   touches `next_action.py`, not `CLAUDE.build.md`/`.j2` directly, but is a same-region prerequisite
   per the phase Ordering section.
3. INFRA-341 merged (`d6c1a6ec`) — added the explicit `spawn-gate-worker` branch and
   `ACTION_SUBAGENT_TYPE` entry to both files.
4. INFRA-344 merged (`1d423760`) — added the explicit `spawn-spec-writer` branch and
   `ACTION_SUBAGENT_TYPE` entry to both files.
5. `skills/pairmode/scripts/next_action.py` on disk today still implements `_intent_review_opt_in`
   (`:928-931`) and the `intent_review_opt_in`/`spawn-intent-reviewer` pre-build row (`:1659-1674`)
   — the feature this story restores documentation for in `CLAUDE.build.md` is live, not retired.

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line.
     Each must be verifiable without interpretation: file exists, command output
     contains X, function Y returns Z. -->
<!-- State the correct signal AND the forbidden proxy (INFRA-314): e.g. "the
     write is absent after refusal; forbidden proxy: a warning line while the
     write happens anyway." -->

1. `skills/pairmode/templates/CLAUDE.build.md.j2`'s `ACTION_SUBAGENT_TYPE` dict literal contains
   the key-value pair `checkpoint-docs: docs-reviewer` (grep:
   `grep -o "checkpoint-docs: docs-reviewer" skills/pairmode/templates/CLAUDE.build.md.j2` returns
   a match). Forbidden proxy: adding the key name in prose text only (e.g. a comment mentioning
   "checkpoint-docs") without it appearing inside the `ACTION_SUBAGENT_TYPE = { ... }` dict literal
   itself — the dict is what `next_action.py`'s dispatch resolves against, prose is not read by
   code.
2. The set of keys inside `ACTION_SUBAGENT_TYPE = { ... }` in `CLAUDE.build.md` is identical to the
   set of keys inside `ACTION_SUBAGENT_TYPE = { ... }` in
   `skills/pairmode/templates/CLAUDE.build.md.j2` (order may differ; membership must not).
3. `CLAUDE.build.md`'s Build standards line contains an `intent_review=` key (grep:
   `grep -o "intent_review=" CLAUDE.build.md` returns a match) with value `(unset)` (flex has not
   opted in — matches the template's `{{ intent_review | default('(unset)', true) }}` default
   rendering for a project with no `intent_review` context key set).
4. `CLAUDE.build.md` contains the substring
   `record-intent-review --phase-key <a.scalar> --verdict <PASS|FAIL|ALIGNED>` (the pre-build
   verdict-recording command, using live's literal `/mnt/work/flex-harness/skills/pairmode/scripts`
   path form, not a Jinja placeholder) and prose stating a non-`PASS`/`ALIGNED` verdict pauses for
   the operator instead of proceeding.
5. `skills/pairmode/templates/CLAUDE.build.md.j2`'s catch-all `else` branch line (the generic
   `spawn leaf-worker-for(a.action) ...` line with no preceding `elif`) carries a comment describing
   that `spawn-loop-breaker`'s `a.reason` carries the double-fail story's recorded `fail_cause`, and
   that a `LOOP-BREAKER:` prompt is built from it before spawning — the same substantive content as
   live `CLAUDE.build.md`'s existing INFRA-328 comment on that line (verbatim wording may differ;
   the fail_cause/LOOP-BREAKER-prompt-construction fact must be present in both).
6. Neither `CLAUDE.build.md` nor `skills/pairmode/templates/CLAUDE.build.md.j2` contains the string
   `pause-context` anywhere (`grep -c pause-context CLAUDE.build.md
   skills/pairmode/templates/CLAUDE.build.md.j2` reports `0` for both) — guards against
   reintroducing a reference to the action INFRA-339 removed from `next_action.py`'s `ACTIONS`.
7. The intentional flex-specific customizations are unchanged by this story: `git diff` against the
   pre-story `CLAUDE.build.md` shows no change to the `/mnt/work/flex-harness/...` literal paths,
   the "flex-harness" project name, the `git push origin main --tags` line, or the checkpoint-tag
   "promote" clause (`git -C /mnt/work/flex-harness merge --ff-only cp-<phase-key>`) outside the
   Build standards line edited by Ensures 3/4.
8. `tests/pairmode/test_claude_build_parity.py` exists and contains at least two categories of
   test: (a) unit tests of the extraction helper(s) against inline fixture strings — proving the
   extraction correctly flags a fixture pair with a deliberately-dropped
   `ACTION_SUBAGENT_TYPE`/Build-standards key as a mismatch (a red case), not just a green case; and
   (b) an integration test that reads the real `CLAUDE.build.md` and
   `skills/pairmode/templates/CLAUDE.build.md.j2` off disk and asserts their `ACTION_SUBAGENT_TYPE`
   key sets are equal and their Build-standards key sets are equal. Forbidden proxy: a test that
   only exercises the green (already-matching) case — a parity check with no red-path unit test
   cannot be trusted to actually fire on a future single-file edit; it might be vacuously true (e.g.
   a regex that matches nothing in either file and reports "equal empty sets").
9. `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` exits 0 (suite green,
   including the new `test_claude_build_parity.py`).
10. `skills/pairmode/scripts/pairmode_drift_report.py` and `skills/pairmode/scripts/audit.py` are
    unmodified by this story (`git diff --stat` shows no changes to either path) — this story closes
    the drift-detection gap with the new dedicated test (Ensures 8), not by extending the
    multi-project section-diffing tool (see Context § why extending it was rejected; also
    Out of scope).

## Instructions

1. In `skills/pairmode/templates/CLAUDE.build.md.j2`, add `checkpoint-docs: docs-reviewer` to the
   `ACTION_SUBAGENT_TYPE` dict literal on the `## Build loop` line, in the same dict-literal
   position live's line uses (immediately after `checkpoint-intent: intent-reviewer,`). Optionally
   extend the trailing comment to attribute the entry to INFRA-325, mirroring live's comment — not
   independently verified by the reviewer, but keep the two comments substantively aligned rather
   than contradictory.
2. In `CLAUDE.build.md`'s Build standards line, insert `intent_review=`(unset)`` immediately after
   `domain_isolation_rule=`...`` and before `covered_contracts=`...``, matching the template's key
   ordering. Immediately after the Build standards line's `covered_contracts=` clause (or wherever
   reads most naturally without disturbing the existing INFRA-317 `covered_contracts` sentence), add
   a clause carrying the same substance as the template's: when `intent_review` is `pre-build`
   (INFRA-315), a `spawn-intent-reviewer` action whose `scalar` is a phase key (not a story ID) is
   the pre-build case — spawn `intent-reviewer` with `model=null`, then run
   `/mnt/work/flex-harness/skills/pairmode/scripts/flex_build.py record-intent-review --phase-key
   <a.scalar> --verdict <PASS|FAIL|ALIGNED> --project-dir .` before re-running `next-action`; this
   fires once per phase; a non-`PASS`/`ALIGNED` verdict pauses for the operator instead of
   proceeding. Use live's literal path form throughout (no `{{ }}` placeholders — this is the
   rendered file, not the template).
3. In `skills/pairmode/templates/CLAUDE.build.md.j2`'s `else` branch (the final, un-`elif`'d
   `spawn leaf-worker-for(a.action) with subagent_type=ACTION_SUBAGENT_TYPE[a.action], scalar=a.scalar,
   model=a.model` line), append the INFRA-328 comment live's equivalent line carries — copy live's
   wording (`# INFRA-328: for spawn-loop-breaker, a.reason carries the double-fail story's most
   recent recorded fail_cause (or "" if none found); build the LOOP-BREAKER: [error] | FILE:
   [file:line] | TRIED: [what failed] prompt (CLAUDE.md § Loop-breaker mode) from it before
   spawning, extracting a FILE: value from a.reason when it names one`) verbatim; it references
   `next_action.py`/`CLAUDE.md` behavior that is not flex-specific, so it applies unchanged to any
   downstream project scaffolded from this template.
4. Re-diff the two files after steps 1-3 (e.g. the `diff` invocation used in this story's
   investigation, normalizing `{{ pairmode_scripts_dir }}`/`{{ project_name }}` template variables
   against their live literal values first) and confirm no other *structural* divergence remains —
   i.e. every dispatch branch, every `ACTION_SUBAGENT_TYPE` key, and every Build-standards key
   present in one file is present in the other. Do not chase cosmetic prose differences that carry
   no behavioral content (e.g. slightly different clause ordering in a comment) — only structural
   gaps (missing dict keys, missing Build-standards keys, missing behavioral prose describing a live
   feature) are in scope.
5. Write `tests/pairmode/test_claude_build_parity.py`. Implement a small parsing helper (in the test
   file itself, or a tiny importable module under `skills/pairmode/scripts/` if you judge it
   reusable — your call, but keep it minimal) that: (a) extracts the `ACTION_SUBAGENT_TYPE = { ... }`
   dict literal's key set from a text blob via regex (match `\{[^}]*\}` after
   `ACTION_SUBAGENT_TYPE = `, then split on `,` and take the token before each `:`); and (b)
   extracts the Build-standards line's key set via regex (match `(\w+)=` occurrences on the
   `**Build standards**` line, or the whole file if the line-anchoring proves fragile). Write:
   - Unit tests against inline fixture strings for both helpers, including a red-path case per
     helper (a fixture pair with one key deliberately dropped from one side) that must fail the
     parity assertion — proving the helper is discriminating, not vacuous.
   - One integration test that reads `CLAUDE.build.md` and
     `skills/pairmode/templates/CLAUDE.build.md.j2` (repo-root-relative paths, resolved the same way
     other tests in `tests/pairmode/` resolve the repo root — check an existing test file's
     `Path(__file__).resolve().parents[...]` pattern and reuse it) off disk and asserts the two
     `ACTION_SUBAGENT_TYPE` key sets are equal, and the two Build-standards key sets are equal.
     Assert with a diff-friendly failure message (e.g. `assert live_keys == template_keys, f"..."`
     showing the symmetric difference) so a future CI failure names the missing key directly rather
     than just "sets differ."
6. Do not attempt to make the integration test render the `.j2` template through Jinja2 with a
   flex-specific context and byte-diff the whole file against live — that reintroduces exactly the
   noise problem described in Context (the intentional path/name substitutions would always show as
   difference). Parse both files as plain text for the two specific structural invariants named
   above; do not compare anything else between them in this test.
7. Run the full suite once without `-x` first (per the standing "pytest -x masks failures" lesson)
   to confirm no pre-existing unrelated failure is hidden, then the `-x` command in Tests below for
   the acceptance run.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_claude_build_parity.py -q 2>&1 | tail -20
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -10
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q 2>&1 | tail -10
```

Acceptance: `test_claude_build_parity.py`'s red-path unit tests fail as designed when run in
isolation against a mutated fixture (verify by hand during development, not part of the committed
suite — the committed suite only asserts the real files are in parity and that the helper correctly
distinguishes a deliberately-broken fixture pair as *not* in parity); the full suite is green both
without and with `-x`.

## Out of scope

- Extending `pairmode_drift_report.py`/`audit.py`'s general multi-project section-diffing machinery
  to catch this class of drift automatically for every template file — that tool's per-project,
  whole-section comparison model is a larger redesign (context-aware rendering per consuming
  project, or sub-section-granular diffing) than this story's scope; the dedicated test added here
  closes the specific `CLAUDE.build.md`/`.j2` gap without redesigning the general tool.
- Wiring `pairmode_drift_report.py` into an automated gate (CI, checkpoint, pre-commit) for other
  template/project-file pairs beyond `CLAUDE.build.md`/`.j2` — only the new dedicated test in scope
  here is wired into `tests/pairmode/`, which is already part of every story's standard test run.
- Any change to `next_action.py`'s `intent_review`/`pause-context`/dispatch behavior itself — this
  story only reconciles the two *documentation* files against the behavior `next_action.py` already
  implements; it does not add, remove, or alter any action, model-selector wiring, or resolver row.
- Regenerating or re-scaffolding any downstream/fleet project's `CLAUDE.build.md` from the corrected
  template — that is each fleet project's own sync/audit responsibility, out of this story's
  single-repo scope.

**spec-preflight note:** `skills/pairmode/scripts/pairmode_drift_report.py` and
`skills/pairmode/scripts/audit.py` are named in Ensures 10/Context/Out of scope but are
deliberately absent from `primary_files`/`touches` — Ensures 10 requires them to stay
**unmodified**, and the surrounding Context/Out-of-scope prose explains why extending them was
rejected in favor of the new dedicated test. Naming them without declaring them in scope is
intentional here, not an oversight.
