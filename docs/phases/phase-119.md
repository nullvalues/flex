---
era: "004"
phase_class: production
---

# project — Phase 119: Spec precision (frozen exemplar) and fundamental-doc trim

← [Phase 118: Narrative of Record: propagation, spec-writer/intent-reviewer integration, and mid-build steering](phase-118.md)

<!-- Phase doc = planning surface only. Story-level detail (acceptance criteria,
     file paths, implementation guidance, test instructions, codebase recon)
     belongs in docs/stories/<RAIL>/<ID>.md — not here. -->

**Status: ACTIVE (operator-commissioned 2026-08-03).** Following Phase 118's checkpoint (cp-118),
the operator explicitly directed the broadest reasonable coverage of the open CER backlog into
this phase, then closing era 004 and sealing the 0.3.1 release. Scope was widened from the
original two stories (INFRA-363/364) to 18, per the `## Goal` section below.

## Goal

Follow up on Phase 118's spec-volume remediation (INFRA-357) with two independent, narrowly
scoped fixes surfaced by a two-round third-party analysis (session 2026-08-03, requested
independently of the Devin/Windsurf cold-eyes reviews already cited in INFRA-357): (1) replace
the spec-writer's "one recent story" exemplar input with a frozen reference exemplar, since a
moving exemplar is structurally self-reinforcing regardless of INFRA-357's brevity instruction;
and (2) trim four specific, already-identified pieces of dead or duplicated content out of this
project's own fundamental docs (`docs/ideology.md`, `docs/architecture.md`,
`skills/pairmode/SKILL.md`).

The phase was subsequently widened to also drain 16 open CER backlog items — CER-42, CER-43,
CER-62, CER-109, CER-117, CER-121, CER-125, CER-131, CER-132, CER-133, CER-135, CER-142, CER-145,
CER-146, CER-160, CER-163 — as part of era 004's stated goal of bringing the CER backlog to zero
unresolved operational findings.

## Stories

| ID | Title | Status |
|----|-------|--------|
| INFRA-363 | Freeze the spec-writer's format exemplar; correct INFRA-357's attempt-count claim | complete |
| INFRA-364 | Trim dead/duplicated content from ideology.md, architecture.md, and pairmode SKILL.md | complete |
| INFRA-367 | Add non-interactive rail-creation flags to story_new.py (CER-117) | complete |
| INFRA-368 | Fix resolverState.ts getFlexBuildPath() resolving one directory too high (CER-142) | complete |
| INFRA-369 | Decouple a migrate test from the literal checkout directory name flex-harness (CER-146) | complete |
| INFRA-370 | Auto-derive model_selector.py's test file into touches: when the module is touched (CER-145) | complete |
| INFRA-371 | Close four residual doc/scoping seams left by INFRA-311 canon-retirement (CER-133) | complete |
| INFRA-372 | Track .pairmode-overrides in CANONICAL_FILES/SCAFFOLD_FILES audit surfaces (CER-132) | complete |
| INFRA-373 | Log SubagentStop-relay worker-contract rejections instead of silently dropping them (CER-131) | complete |
| INFRA-374 | Wire the missing context_current_tokens_source writer in post_tool_use.py (CER-135) | draft |
| INFRA-375 | Audit hardcoded flex-harness absolute paths for release-channel staleness risk (CER-160) | draft |
| INFRA-376 | Close shadow-reviewer Bash-bypass and bootstrap operator-note escaping gaps (CER-163) | draft |
| INFRA-377 | Gate abs_path disclosure in observability API GET responses (CER-43) | draft |
| INFRA-378 | Narrow observability API's CORS origin from wildcard for non-loopback overrides (CER-42) | draft |
| INFRA-379 | Derive test_plugin_manifest.py's expected skill names from skills/*/SKILL.md glob (CER-109) | draft |
| INFRA-380 | Match suffixed phase filenames in story_new.py's phase-manifest lookup (CER-62) | draft |
| INFRA-381 | Add drift/staleness tracking for bootstrap-seeded cold-start triad docs (CER-121) | draft |
| INFRA-382 | Correct stale story statuses in docs/phases/phase-64.md's Stories table (CER-125) | draft |

## Ordering

INFRA-363 and INFRA-364 are independent of each other and of the rest of Phase 118 — neither
touches a file the other touches, and neither depends on Phase 118's Cluster A/B/C work landing
first.

The 16 CER-backlog stories (INFRA-367 through INFRA-382) are, with two exceptions noted below,
small, independent, mechanical fixes touching different files, with no ordering constraint between
them or against INFRA-363/364. Two file-overlap pairs were found while reading the stub Context
sections and should be sequenced (or explicitly coordinated) rather than built fully in parallel:

- **INFRA-367 (CER-117)** and **INFRA-380 (CER-62)** both edit
  `skills/pairmode/scripts/story_new.py` — INFRA-367 adds a `--create-rail`/`--yes` flag to the
  interactive rail-creation prompt, INFRA-380 fixes `_append_to_phase`'s phase-manifest glob
  matching (~lines 127-137). Different functions, but the same file — build serially or merge
  carefully to avoid a spurious conflict.
- **INFRA-372 (CER-132)** and **INFRA-381 (CER-121)** both plausibly edit
  `skills/pairmode/scripts/audit.py`'s tracking surfaces — INFRA-372 adds
  `.pairmode-overrides` existence/parse-health tracking to `CANONICAL_FILES`/`SCAFFOLD_FILES`/
  `_load_overrides`, and INFRA-381 adds a new body-tracking/staleness mechanism for
  `docs/architecture.md`/`docs/checkpoints.md` that is likely to land in the same module (it
  already carries the analogous staleness-check pattern for `docs/ideology.md`/
  `docs/reconstruction.md`). Confirm the actual diff shape at build time; if both land in
  `audit.py`, build serially.

No other overlaps were found between the 16 stories' cited files, or between them and
`docs/ideology.md`, `docs/architecture.md`, or `skills/pairmode/SKILL.md` (INFRA-364's scope) —
INFRA-371 (CER-133) does touch `skills/pairmode/SKILL.md`, but at different line ranges/content
(sync-behavior claims) than INFRA-364's dead/duplicated-content trim; confirm no line-range clash
at build time before running them fully in parallel.

## Schema delivery

For each new persistent schema object (table, collection, migration) introduced in
this phase, record the management surface before the phase is checkpointed.

| Object | Management surface | Exception |
|---|---|---|
| | | |

None of these 18 stories introduce a persistent schema object — n/a.

---

### CP-119 Cold-eyes checklist

- [ ] written-never-read — does anything this phase persists have no reader?
- [ ] required-never-written — does any read path depend on a value no writer produces?
- [ ] duplicate state — is any fact now stored twice with independent writers?
- [ ] half-implementation — is any branch unreachable, or any producer without its consumer?

— developer fills in after phase completion —
