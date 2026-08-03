---
id: INFRA-354
rail: INFRA
title: Backfill flex's own docs/narratives/ from the new template source (real dogfood backfill)
status: draft
phase: "118"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/narratives
touches:
  - docs/stories/INFRA/INFRA-354.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

INFRA-351 moves the nine harness-role narratives' content into template source; INFRA-352 adds the
`sync-narratives` add-missing-file path; INFRA-353 adds OPERATOR's seed-then-extend mechanism. This
story is the real-world dogfood step, directly mirroring INFRA-332's own backfill discipline
(Phase 116: "ran the equivalent bootstrap-parity path against both /mnt/work/flex and
/mnt/work/flex-harness... verified by reading the generated files, not by exit code"). flex's own
`docs/narratives/<ROLE>/*.md` were hand-authored directly in this era, *before* the template
existed — this story reconciles flex's own tree to be the genuine first materialized/synced copy
of the template, not a one-off that happens to look similar to it.

## Requires

- INFRA-351, INFRA-352, INFRA-353 must all land first.

## Ensures

1. flex's own `docs/narratives/<ROLE>/<ROLE>-000-ideology.md` for all nine harness-role narratives
   is regenerated via the real `sync-narratives` (or `bootstrap`) mechanism from INFRA-351/352 —
   not hand-copied — and the regenerated content is read directly and compared against this era's
   originally-authored versions to confirm no substantive content was lost or altered in the
   template-extraction step (INFRA-351's Instructions left this as an explicit authorial judgment
   call to record — this story is where that record gets verified against the actual rendered
   output).
2. `docs/narratives/OPERATOR/OPERATOR-000-ideology.md` is regenerated from the new generic seed
   template (INFRA-353) — this **replaces** flex's era-specific hand-authored OPERATOR content at
   `-000`; that era-specific content (the concrete findings about the escalation ladder, dead
   features, etc.) is preserved by moving it into a new
   `docs/narratives/OPERATOR/OPERATOR-010-flex.md` extension file, so nothing this era wrote about
   flex's actual operator experience is lost — it just moves to where a project-specific extension
   belongs.
3. Real backfill evidence, read directly (not inferred from exit code): before/after file listing
   of `docs/narratives/` and a diff summary showing what changed in each of the ten regenerated
   `-000` files, written into this story's own `## Evidence` section.
4. `git status --short docs/narratives/` after the backfill shows exactly what's expected (content
   changes to existing `-000` files, one new `OPERATOR-010-flex.md`) — no unexpected additions or
   deletions.

## Instructions

1. Run the actual `sync-narratives`/bootstrap-parity path (per INFRA-352's landed mechanism)
   against `/mnt/work/flex` itself, the same way INFRA-332 did for `.claude/agents/`.
2. Read every regenerated file directly and diff it against the pre-backfill version (available in
   git history) — confirm the extraction in INFRA-351 preserved the substantive content (Always
   true / Never / Open gaps items), not just structural shape.
3. For OPERATOR specifically: extract this era's flex-specific findings (the escalation-ladder
   evidence, the dead-feature findings, the "no standing signal" gap) from the original
   `OPERATOR-000` into the new `OPERATOR-010-flex.md`, then let `OPERATOR-000` be overwritten by
   the generic seed.
4. Write the before/after Evidence section directly into this story file once merged — matching
   INFRA-332's own Evidence-section convention.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: green; no test regression from the content changes (these are markdown-only,
no code-path changes of their own).

## Out of scope

- Any new narrative content beyond what already exists in this era's authored drafts and the
  seed/extend split — this is a reconciliation story, not an authoring story.

## Evidence

**Mechanism used (not hand-copied).** All nine harness-role `-000` files were deleted, then
regenerated via the real `sync-narratives` command (INFRA-352):

```
$ uv run python skills/pairmode/scripts/pairmode_sync.py sync-narratives --project-dir . --yes
  added: BUILDER-000-ideology.md
  added: REVIEWER-000-ideology.md
  added: LOOP-BREAKER-000-ideology.md
  added: SECURITY-AUDITOR-000-ideology.md
  added: INTENT-REVIEWER-000-ideology.md
  added: DOCS-REVIEWER-000-ideology.md
  added: GATE-WORKER-000-ideology.md
  added: SPEC-WRITER-000-ideology.md
  added: ORCHESTRATOR-000-ideology.md
RESTART REQUIRED ...
```

`OPERATOR-000-ideology.md` is deliberately kept out of `bootstrap.NARRATIVE_FILES`
(`bootstrap.OPERATOR_SEED_FILE`, INFRA-353) and therefore out of `sync-narratives`'
enumeration — INFRA-352's own Out of scope explicitly left OPERATOR's sync path to be
decided in INFRA-353, and INFRA-353 only wired OPERATOR's seed into `bootstrap.py`'s
fresh-install path (§ 4c), not into any already-bootstrapped-project sync command. For a
project already bootstrapped before `OPERATOR_SEED_FILE` existed (flex's own case), the
`sync-narratives`/`sync-agents` add-missing-file mechanism has no CLI entry point for this
one file. Rather than build a new production code path (out of scope for this
reconciliation-only story), `OPERATOR-000-ideology.md` was regenerated by calling
`pairmode_sync._collect_missing_files()` directly with `[bootstrap.OPERATOR_SEED_FILE]` —
the exact same render/write primitive `sync-narratives` itself calls for the other nine
(same `_render_full_template`, same `StrictUndefined`/`keep_trailing_newline` jinja
environment) — after first deleting the old file so it register as missing. This is the
"bootstrap-parity path" per this story's Instructions (using the underlying mechanism,
not a hand-copy), applied to the one narrative file INFRA-352/353 deliberately did not
wire into a CLI command.

**Before/after file listing.**

Before (all ten `-000` files present, hand-authored pre-template):
```
docs/narratives/BUILDER/BUILDER-000-ideology.md
docs/narratives/DOCS-REVIEWER/DOCS-REVIEWER-000-ideology.md
docs/narratives/GATE-WORKER/GATE-WORKER-000-ideology.md
docs/narratives/INTENT-REVIEWER/INTENT-REVIEWER-000-ideology.md
docs/narratives/LOOP-BREAKER/LOOP-BREAKER-000-ideology.md
docs/narratives/OPERATOR/OPERATOR-000-ideology.md
docs/narratives/ORCHESTRATOR/ORCHESTRATOR-000-ideology.md
docs/narratives/README.md
docs/narratives/REVIEWER/REVIEWER-000-ideology.md
docs/narratives/SECURITY-AUDITOR/SECURITY-AUDITOR-000-ideology.md
docs/narratives/SPEC-WRITER/SPEC-WRITER-000-ideology.md
```

After (ten `-000`/seed files regenerated, one new extension file):
```
docs/narratives/BUILDER/BUILDER-000-ideology.md
docs/narratives/DOCS-REVIEWER/DOCS-REVIEWER-000-ideology.md
docs/narratives/GATE-WORKER/GATE-WORKER-000-ideology.md
docs/narratives/INTENT-REVIEWER/INTENT-REVIEWER-000-ideology.md
docs/narratives/LOOP-BREAKER/LOOP-BREAKER-000-ideology.md
docs/narratives/OPERATOR/OPERATOR-000-ideology.md
docs/narratives/OPERATOR/OPERATOR-010-flex.md
docs/narratives/ORCHESTRATOR/ORCHESTRATOR-000-ideology.md
docs/narratives/README.md
docs/narratives/REVIEWER/REVIEWER-000-ideology.md
docs/narratives/SECURITY-AUDITOR/SECURITY-AUDITOR-000-ideology.md
docs/narratives/SPEC-WRITER/SPEC-WRITER-000-ideology.md
```

**Diff summary per file, read directly (not inferred from exit code).**

Nine harness-role narratives — `git diff --stat HEAD -- docs/narratives/<ROLE>/<ROLE>-000-ideology.md`
for BUILDER, REVIEWER, LOOP-BREAKER, SECURITY-AUDITOR, INTENT-REVIEWER, DOCS-REVIEWER,
GATE-WORKER, SPEC-WRITER, ORCHESTRATOR each report **no diff at all** — every regenerated
file is byte-for-byte identical to the pre-backfill (hand-authored) version. This confirms
INFRA-351's Instructions item 1 authorial call (relocate content verbatim into `.j2`
templates, no genericization, since "none of the nine harness-role narratives contain the
literal string 'flex'") held completely: extraction lost or altered nothing substantive —
each file's Always true / Never / Open gaps content is unchanged. `diff <(cat
docs/narratives/<ROLE>/<ROLE>-000-ideology.md) skills/pairmode/templates/narratives/<ROLE>/<ROLE>-000-ideology.md.j2`
was also confirmed identical for all nine before deletion (i.e. this was already true prior
to running the mechanism — the mechanism's job here was to prove the pipeline actually
reproduces that content live, not to change it).

`OPERATOR-000-ideology.md` — `git diff --stat HEAD` reports `30 insertions(+), 38
deletions(-)`. The new content is the generic seed from
`skills/pairmode/templates/narratives/OPERATOR/OPERATOR-000-ideology.md.j2` (`era: "seed"`
instead of `era: "004"`; "this era's own..." references and concrete findings — the
escalation-ladder failure rate, the two dead Phase-116 features, the CER-corruption
bug — removed from the seed's Narrative/Always true/Never/Open gaps sections; a new "Never
given standing visibility..." bullet and a pointer to the `OPERATOR-010`-and-onward
extension convention added). Nothing was lost: every flex-specific finding stripped from
`OPERATOR-000` (the escalation-ladder evidence, the dead-feature findings, the "no standing
signal" gap, the "channel gets used for real decisions" evidence, the phase-redirect
example) was moved verbatim (paraphrased only where needed to stand alone as its own
Narrative/Always true/Never/Open gaps sections) into the new
`docs/narratives/OPERATOR/OPERATOR-010-flex.md`.

**`git status --short docs/narratives/` after the backfill — exactly as expected, no
unexpected additions or deletions:**
```
 M docs/narratives/OPERATOR/OPERATOR-000-ideology.md
?? docs/narratives/OPERATOR/OPERATOR-010-flex.md
```
(The nine harness-role files show no status line at all, since their regenerated content
is byte-identical to what was already committed — this is the expected, honestly-reported
outcome given INFRA-351 already moved that content verbatim; it is not a sign the
mechanism was skipped, since the nine files were genuinely deleted and regenerated from
the templates, per the `sync-narratives --yes` transcript above, and their absence from
`git status` is exactly what byte-identical regeneration produces.)

**Suite.** `uv run pytest tests/pairmode/ -q` → `4830 passed, 211 skipped` — full suite
green, no regression from the content-only changes.

**Covered-contracts gate:** `CLAUDE.build.md`'s `covered_contracts` pairs (`## Pairmode
build loop::skills/pairmode/scripts/cer.py`, `## Module structure::skills/pairmode/scripts/next_action.py`)
have no intersection with this story's `primary_files`/`touches` (`docs/narratives`,
this story file) — gate does not apply.
