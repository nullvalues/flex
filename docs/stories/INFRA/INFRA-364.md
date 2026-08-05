---
id: INFRA-364
rail: INFRA
title: Trim dead/duplicated content from ideology.md, architecture.md, and pairmode SKILL.md
status: complete
phase: "119"
story_class: doc
auth_gated: false
schema_introduces: false
primary_files:
  - docs/ideology.md
  - docs/architecture.md
  - skills/pairmode/SKILL.md
touches: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

A two-round third-party analysis (session 2026-08-03) of this project's fundamental/framing docs
— the ones read once and expected to shape many stories, as distinct from individual story specs
— found that unlike `CLAUDE.build.md` (already leaned out via the 0.3.0 thin-dispatch migration
and holding at ~50 lines for 12+ days) `docs/ideology.md`, `docs/architecture.md`, and
`skills/pairmode/SKILL.md` have never had an equivalent trim pass. Most of what the analysis read
in these docs is genuinely load-bearing — specific rules tied to specific documented regressions,
"Rejected direction" records kept so a settled argument isn't re-litigated, and similar material
is explicitly **not** in scope here (see Out of scope). This story is narrowly limited to four
specific pieces of content the analysis identified as dead, superseded, or duplicated, each with a
concrete before/after location:

1. **`docs/ideology.md`** still carries unstripped template scaffolding — `<!-- -->` guidance/
   example comments meant to guide populating the doc once, left in after population (5 HTML
   comment blocks currently, at approximately lines 22, 54, 85, 157, 263). A sibling repo's
   ideology.md (Repo-G, out of this repo's scope to edit, cited here only as evidence) has already
   stripped the same class of scaffolding and reads tighter as a result.
2. **`docs/architecture.md` § "(a) Four-point additive contract (DP4)"** (currently lines
   2726–~2790, under § Era 003 additive contract): scoped explicitly to a migration window
   (`HARNESS001-main … HARNESS005-main`) that has closed. Only one invariant from this section
   still applies today, and it is restated in the surviving "pure-read" / resolver-contract
   material elsewhere in the doc.
3. **`docs/architecture.md` § "Codified comingling — FLAGGED FOR REMOVAL AT HARNESS006 (RESOLVED,
   INFRA-321)"** (currently lines 2911–2945): self-labeled resolved and historical. Its account of
   the original finding and its three-consumer aftermath duplicates material already covered in
   full under § "The two-track model" earlier in the doc. One paragraph in this section —
   "Rejected direction (recorded, not silently declined)" — is not duplicate narration; it records
   three specific rejected approaches (deriving headroom from effort.db totals, heuristic
   poll/merge size estimation, a single unified context number) precisely so they are not
   re-proposed, and must survive the trim.
4. **`skills/pairmode/SKILL.md`** has a specific, mechanical (not narrative) duplication bug,
   present in this file since before the anchor→flex fork (confirmed in anchor's copy too): the
   `review` command's `cer` subsection (around lines 622–648) contains a ~191-word block about
   `apply_template_change`/Jinja2 lesson-comment markers that near-verbatim duplicates content
   already given under the `review` command earlier in the same file (around lines 373–377). This
   is a copy-paste/merge artifact, not intentional cross-referencing.

## Requires

None — independent of INFRA-363, of Phase 118, and of each of the three files' own history;
can build any time, in any order relative to those.

## Ensures

1. `docs/ideology.md`'s five `<!-- -->` scaffolding blocks are removed. The prose/content that
   surrounds each block (the actual conviction/constraint/fingerprint text) is untouched — only
   the guidance-comment scaffolding goes.
2. `docs/architecture.md` § "(a) Four-point additive contract (DP4)" is cut to the one invariant
   that still applies today (identify it precisely during Instructions — do not guess which one
   without re-reading the section against current code), with a one-line note that the rest of the
   section described a now-closed migration window and has been removed rather than silently
   deleted with no trace (mirroring this project's own pattern of leaving a short "this used to
   say X, here's why it's gone" marker rather than an unexplained gap — see the surviving
   `CLAUDE.build.md` line count note already in the "Codified comingling" section as the model to
   follow).
3. `docs/architecture.md` § "Codified comingling — FLAGGED FOR REMOVAL AT HARNESS006 (RESOLVED,
   INFRA-321)" is cut to: (a) a one-to-two sentence pointer to § "The two-track model" for the
   current, live account of the three consumers, and (b) the "Rejected direction (recorded, not
   silently declined)" paragraph in full, unedited. The RESOLVED backstory narration is removed.
4. `skills/pairmode/SKILL.md`'s duplicate `apply_template_change`/Jinja2 block under the `cer`
   subsection is removed, replaced with a short cross-reference to where the content already lives
   (the earlier `review` command section) rather than silently vanishing with no pointer.
5. No other content in any of the three files changes. This story is a subtraction/pointer-fix
   story; it does not rewrite, reorganize, or add new material beyond the short markers described
   above.

**Forbidden proxy:** a "general cleanup pass" over these files that goes beyond the four items
above is not this story — the analysis found most of these docs' length is load-bearing (specific
rules tied to specific documented regressions, or "Rejected direction" records), and a broader
trim risks cutting exactly the material this project's own do-not-cut pattern exists to protect.
If a broader trim is wanted later, it needs its own story with its own content audit, not an
expansion of this one mid-build.

## Instructions

1. Re-read each of the four sections named in Context, in the current file (not from this story's
   Context summary — line numbers may have shifted since the analysis ran), before editing, to
   confirm the cut boundaries are still accurate.
2. For the DP4 section: verify against current code (not assumption) which single invariant, if
   any, still governs behavior today, and confirm it really is restated elsewhere before removing
   the rest — do not cut a genuinely still-load-bearing rule because it superficially resembles
   closed-migration language.
3. For the Codified-comingling section: preserve the "Rejected direction" paragraph verbatim,
   character-for-character — this is the one piece of this section's content flagged explicitly as
   load-bearing by the source analysis, and cutting it defeats the reason the paragraph exists.
4. For SKILL.md: after removing the duplicate block, verify the earlier `review` section it points
   to still reads correctly as the sole home for that content (no other duplicate reference left
   dangling).
5. Do not touch `skills/pairmode/gate_worker/SKILL.md` or any sibling repo's copy of these files
   (flex-harness, anchor) — those were not part of the content audit this story is based on, and
   flex-harness's copy syncs from flex's via the existing promotion mechanism rather than needing
   a parallel manual edit here.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green. (Doc-only change to three markdown files; no code path depends on their
content, so there is no meaningful automated test beyond confirming the edited files still parse
as valid markdown and nothing else in the test suite references the removed sections by line
number or exact text.)

## Out of scope

- Any content in these three files other than the four items named in Context/Ensures — in
  particular, the module-structure and pairmode-build-loop sections of `architecture.md` (both
  flagged by the source analysis as "trim ~8-12%, low confidence, needs a dedicated full read to
  size accurately") and the `Flags:`/`Inputs expected:` restatement pattern and double
  CLI-invocation-example pattern also found in `SKILL.md` (~11% and a smaller remainder of that
  file's ~18% estimated total) are real findings but are not bounded enough yet to build against
  without their own dedicated audit — do not fold them into this story's scope.
- Any change to `CLAUDE.build.md` in this or any sibling repo (already leaned out and holding; the
  source analysis found only ~5-10% further headroom there, and flagged Repo-G's and anchor's
  CLAUDE.build.md as needing a re-sync to the already-proven thin-dispatch template rather than a
  fresh trim — that is separate repo-level work, not in scope for a flex-only story).
- Any change to `skills/pairmode/SKILL.md` in flex-harness or anchor (separate repos; flex-harness
  syncs via the existing release-promotion mechanism, anchor is a frozen ancestor never meant to
  sync forward).
