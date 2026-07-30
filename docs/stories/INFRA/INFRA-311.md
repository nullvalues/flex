---
id: INFRA-311
rail: INFRA
title: Sync canon-shrink propagation; audit flags EXTRA inside canonical files; SCAFFOLD_FILES parity test
status: complete
phase: "113"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/sync.py
  - skills/pairmode/scripts/audit.py
touches:
  - skills/pairmode/scripts/bootstrap.py
  - tests/pairmode/test_sync.py
  - tests/pairmode/test_audit.py
  - docs/architecture.md
  - docs/cer/backlog.md
  - README.md
  - docs/stories/INFRA/INFRA-311.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

This story exists because `sync` is a monotonic mechanism applied to a
non-monotonic canon. The cold-eyes review's single CRITICAL finding (F1,
`docs/closeout-planning-cold-eyes-review_20260729.md`; CER-119) is that the
INFRA-241 thin-agent canon *reduction* never reached the fleet: all six
consuming projects still carry the fat pre-241 reviewer checklist (6×–13× the
current canon, including `git clean -fd` residue) with the thin shell appended
below it — two contradictory grading contracts in one file. The root cause is
structural, not operational:

- `sync.py`'s contract is "Project-specific content (EXTRA items) is always
  preserved" (`sync.py:5`) and `sync_project` "Never modifies EXTRA items"
  (`sync.py:344`). When canon *removes* a section, the removed section is
  reclassified downstream as EXTRA — and is then preserved forever. Sync
  propagates canon growth only; it structurally cannot deliver shrinkage.
- `audit.py` compounds it: sections in project but not in canonical are
  reported as EXTRA (`audit.py:555`, description at `:563`) and rendered
  "EXTRA (project-specific, keep as-is)" (`audit.py:753`) — a `✓` for what is
  actually stale canon (F2; CER-120).

Every future simplification of the methodology will fail to reach the fleet
the same way, silently, unless this is fixed once. It also gates this era
twice over (AG-1, `docs/closeout-agreements-20260729.md`): phase 106 cannot be
dispositioned "complete by hand-migration" while the agent shells prove
hand-migration didn't hold (AG-3 orders that disposition after this story),
and phase 116's canon rewrites are only propagatable once shrinkage works.

**Design choice: an explicit canon-side retirement manifest, not blanket
pruning.** A `--prune-extra` flag that deletes all EXTRA content would violate
the one promise sync must keep — genuinely project-specific extensions (cora's
deliberate extensions region is the live example) are EXTRA *by design* and
must survive. The distinction "once-canonical, since retired" vs "never
canonical" is knowledge only canon has, so canon must declare it: a
`RETIRED_SECTIONS` registry in `sync.py` (section keys canon once shipped and
has since removed, with the retiring story ID). Sync deletes a downstream
EXTRA item **only** when its key is in the registry; audit flags it as a
finding rather than blessing it. Everything not in the registry keeps today's
preservation behaviour, verbatim.

Also folded in (AG-1, third bullet): the one-test
`bootstrap.SCAFFOLD_FILES ⊆ audit-tracked` parity assertion — the analog of
`test_audit.py`'s existing `test_agent_files_subset_of_canonical_files`
(~`:2209`) — so seeded-but-untracked scaffold surfaces can't silently multiply
(F3's cheap half; the full seeded-doc body-tracking is CER-121, deliberately
out of scope here).

## Requires

1. **The EXTRA-preservation contract and its anchors.** `sync.py:5`
   (module docstring promise), `sync.py:344` ("Never modifies EXTRA items"),
   `sync.py:596` (EXTRA recorded as preserved in the report). Re-verify line
   numbers before editing; locate by text.

2. **Audit's classification and rendering paths.** `audit.py:41`
   (`CANONICAL_FILES`), `audit.py:54` (SCAFFOLD_FILES distinction comment),
   `audit.py:505` (`all_files = list(CANONICAL_FILES) + list(SCAFFOLD_FILES)`),
   `audit.py:555-563` (EXTRA classification), `audit.py:753` (report line).

3. **The override mechanism exists and must keep working.** Checklist-item
   level overrides (Phase 87) and `.pairmode-overrides` are the sanctioned way
   a project protects deliberate extensions; nothing here may weaken them. A
   project override naming a retired section key is a legitimate "keep it
   anyway" signal and wins over the registry.

4. **The INFRA-241 reduction is the seed content for the registry.** The
   sections the thin-agent reduction removed from the six agent shells
   (fat reviewer checklist, `git clean -fd` step, and siblings) are
   recoverable from git history of
   `skills/pairmode/templates/agents/*.md.j2` around the INFRA-241 commits.
   The registry ships non-empty: it must list at least the retired
   reviewer-checklist sections, each tagged `INFRA-241`.

5. **Fleet state is the test oracle, not the test target.** This story fixes
   flex's tooling and proves it on fixtures shaped like the observed fleet
   state (thin shell + appended stale fat canon). It does **not** run
   `sync-all` against the fleet — the rollout is a campaign act after 0.3.1
   (see `## Out of scope`).

6. **Baseline.** `main`'s suite is green at 4116 passed / 211 skipped.

## Ensures

1. **`RETIRED_SECTIONS` registry exists, non-empty, and documented.**
   `sync.py` defines a module-level registry mapping retired section keys to
   the story ID that retired them, seeded with the INFRA-241 reductions
   (Requires 4). Each entry carries a comment or field naming the retiring
   story. `grep -c 'RETIRED_SECTIONS' skills/pairmode/scripts/sync.py` ≥ 2
   (definition + consumption).

2. **Sync deletes registry-matched EXTRA items and reports each deletion.**
   `sync_project` on a fixture carrying a retired section as EXTRA removes
   that section under `--apply` and lists it in the report under a distinct
   heading (e.g. `RETIRED (canon-removed, pruned)`), naming the retiring
   story ID. **The correct signal is the section's absence from the
   downstream file after `--apply`; the forbidden proxy is the report line
   alone — a test that only greps the report while the file still contains
   the section must fail.** The test asserts on the written file's content.

3. **Non-registry EXTRA items are byte-preserved.** On the same fixture, an
   EXTRA section *not* in the registry (a genuine project extension) survives
   `--apply` byte-identically, and the report still records it as preserved.
   The `sync.py:5` / `:344` docstrings are updated to state the new contract
   precisely: "EXTRA items are preserved unless canon has explicitly retired
   them (`RETIRED_SECTIONS`); project overrides win over retirement."

4. **Dry-run parity.** Without `--apply`, no file changes
   (`git diff` empty on the fixture) and the report shows the same
   `RETIRED` classification it would apply. **Correct signal: identical
   classification across dry-run and apply; forbidden proxy: a dry-run that
   simply skips the retirement branch.**

5. **Override wins over registry.** A fixture project override naming a
   retired section key keeps the section under `--apply`, and the report
   records it as override-kept, not pruned, not blessed-EXTRA.

6. **Audit: EXTRA inside `CANONICAL_FILES` is a finding.** For files in
   `CANONICAL_FILES` (not `SCAFFOLD_FILES` — their body content is inherently
   project-specific, `audit.py:54` / `:569`), an EXTRA section now reports as
   a finding — severity WARN for unregistered keys ("stale-canon candidate or
   deliberate extension — confirm or override"), severity ERROR for
   registry-matched keys ("canon-retired content still present; run sync").
   The `✓ project-specific` keep-as-is rendering (`audit.py:753`) no longer
   applies to canonical files. Scaffold files keep today's behaviour
   unchanged. **Correct signal: a nonzero finding count on the stale-fleet
   fixture; forbidden proxy: a reworded checkmark line that still exits
   clean.** The test asserts audit's exit/finding status, not report text
   alone.

7. **Override suppresses the WARN, never the ERROR silently.** An
   override-matched EXTRA in a canonical file reports as overridden (no WARN);
   a registry-matched key under override reports override-kept (Ensures 5's
   audit-side mirror) — visible, not silent.

8. **Parity test: every bootstrap scaffold surface is audit-tracked.**
   `tests/pairmode/test_audit.py` gains one test asserting
   `{dest for dest, _ in bootstrap.SCAFFOLD_FILES} ⊆
   {dest for dest, _ in audit.CANONICAL_FILES} ∪
   {dest for dest, _ in audit.SCAFFOLD_FILES}`, styled after
   `test_agent_files_subset_of_canonical_files`. It must pass against the
   current tree or the discrepancy must be fixed in this story (whichever
   file lists are out of parity), with the fix named in the story evidence.

9. **Architecture doc updated.** `docs/architecture.md`'s sync/audit section
   states the retirement contract (registry, override precedence,
   canonical-vs-scaffold EXTRA severities) in ≤ 20 added lines.

10. **CER rows annotated.** `docs/cer/backlog.md` rows CER-119 and CER-120
    each gain `**RESOLVED Phase 113 — INFRA-311: <one sentence>.**` in the
    Finding cell, in place, no row deleted or moved. CER-121 (full seeded-doc
    tracking) is **not** touched — it stays open with its `gate:` condition.

11. **Suite green.** Full run **without `-x`**: no failures beyond the
    4116/211 baseline plus this story's added tests.

## Instructions

1. Recover the INFRA-241 removed sections from template git history first;
   the registry's seed content is evidence-driven, not from memory.
2. Implement the registry and the `sync_project` retirement branch; update
   the two docstring contracts in the same commit as the behaviour change.
3. Implement the audit severity split (Ensures 6-7) against the same section
   keys; share the registry — do not duplicate it in `audit.py`. The sharing
   mechanism is **import from `sync.py`** (the sibling-import pattern already
   exists in `audit.py` — `lesson_utils`, `_version`); do not create a
   new shared module — that file would sit outside this story's declared
   scope.
4. Build the stale-fleet fixture: a canonical file whose downstream copy is
   thin-shell + appended retired fat section + one genuine extension section.
   All of Ensures 2-7 run against it.
5. Add the parity test (Ensures 8) and reconcile any discrepancy it finds.
6. Annotate CER-119/120 (Ensures 10) last.

**Do not:**
- implement blanket `--prune-extra` (deletes legitimate extensions);
- change scaffold-file EXTRA handling (`audit.py:54` contract stands);
- run `sync-all` or modify any downstream repo;
- weaken or bypass `.pairmode-overrides` / checklist-item overrides;
- touch `CER-121`'s row.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_sync.py tests/pairmode/test_audit.py -q 2>&1 | tail -15
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: both green; full run without `-x`; no failures beyond baseline +
added tests. Reviewer negative checks: (a) delete a registry entry in a
scratch copy — the corresponding sync test must fail (the registry is
load-bearing, not decorative); (b) confirm Ensures 2's test reads the written
file, not just the report; (c) confirm the genuine-extension fixture section
survives apply byte-identically.

## Out of scope

- **Fleet rollout.** Running the shrink against the six downstream projects
  is a `sync-all` campaign after 0.3.1 (and is what makes phase-106's
  disposition honest — AG-3 sequences that after this story *lands*, not
  after the campaign).
- **Full seeded-doc body tracking** for `docs/architecture.md` /
  `docs/checkpoints.md` (F3's larger half) — CER-121, gated.
- **Template content changes.** This story moves the *mechanism*; any new
  canon rewrite rides phase 116.

## Evidence

- **README.md scope expansion.** README.md:209 promises non-destructive sync
  ("It offers to apply the delta non-destructively"); this story changes that
  contract, so the sentence was reworded in the same commit to the new
  contract: sync preserves project extensions and prunes only canon-retired
  sections (`RETIRED_SECTIONS`), each behind an explicit per-section
  confirmation. `docs/architecture.md:52` ("apply delta from audit
  non-destructively") was reworded identically.
- **Registry seed (Requires 4).** The 46 retired section keys were recovered
  from git history, not memory: `_split_sections` diff of
  `skills/pairmode/templates/agents/*.md.j2` at `9acb9145^` (pre-INFRA-241
  fat templates: builder 7, reviewer 20, loop-breaker 4, security-auditor 9,
  intent-reviewer 6 = 46 occurrences, 42 unique keys after cross-shell
  dedupe) against the current thin shells. All entries tagged `INFRA-241`.
- **Parity reconciliation (Ensures 8).** `bootstrap.SCAFFOLD_FILES` vs
  audit-tracked surfaces is out of parity for five entries. Reconciled as:
  `docs/ideology.md` / `docs/reconstruction.md` are audit-tracked via the
  dedicated `_check_ideology_staleness` / `_check_reconstruction_staleness`
  checks (counted as tracked, `_DEDICATED_CHECK_FILES`);
  `docs/architecture.md` / `docs/checkpoints.md` are known gaps held open by
  CER-121 (untouched, still gated); `.pairmode-overrides` was a previously
  unfiled gap — filed as CER-132 (Do Later) and excepted via `_KNOWN_GAPS`.
  Two meta-tests keep the exceptions honest: every `_KNOWN_GAPS` tracker must
  exist as a real backlog row, and every excepted path must still be
  untracked (a closed gap fails the test until the exception is removed).
