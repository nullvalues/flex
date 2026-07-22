---
id: RELEASE-042
rail: RELEASE
title: Pre-fold doc sweep — era status, post-flip staleness, reviewer input-scope contradiction (retry, scoped to drop forbidden brief.md section)
status: draft
phase: "97"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - docs/eras/003-flex-orchestrator-as-harness.md
  - docs/phases/index.md
  - docs/architecture.md
  - CLAUDE.build.md
  - skills/pairmode/skills/reviewer/procedure.md
touches:
  - docs/architecture.md
---

## Context

Phase 97 resumes HARNESS016-main's deferred tail and folds `fold-prep` into
`main` as pairmode `v0.3.0`. Before that fold, the project's canonical docs must
tell the truth about the post-flip world: Era 003's flip (`HARNESS006-main`)
already reduced the orchestrator to a thin dispatch loop and converted every unit
of work to leaf workers, but documentation written before the flip can still
describe the old "orchestrator runs the loop" model as current. Folding stale
docs into `main` would ship a false description of the harness to every downstream
consumer that syncs to `0.3.0`.

This story is the pre-fold documentation sweep. It corrects three specific
doc-truth defects surfaced during the HARNESS016 close-out:

1. **Era status** — the Era 003 doc / phase index state of the era (active vs.
   closed, phases-complete claims) is internally inconsistent or overstated
   relative to "era active — not yet closed; formal close pending field
   validation."
2. **Post-flip staleness** — one or more canonical docs still describe the
   pre-flip orchestrator-runs-the-loop procedure as the current mechanism, rather
   than the thin dispatch loop + `next-action` resolver + leaf-worker model that
   the flip established.
3. **Reviewer input-scope contradiction** — the reviewer procedure skill
   (`skills/pairmode/skills/reviewer/procedure.md`) contradicts itself about what
   inputs the reviewer is allowed to read.

It is a **retry** of the deferred HARNESS016-main doc-sweep story
(originally RELEASE-022). The prior scoping included an edit to `docs/brief.md`;
`brief.md` is operator-intent and is out of bounds for a build story. This retry
is deliberately **scoped to drop that forbidden `brief.md` section** — the brief
is not touched here.

## Requires

- Phase 97 is the active phase; `HARNESS006-main` (the flip) is complete, so the
  thin-harness model is the current, correct description of the build loop.
- The fold to `main` (RELEASE-059) has **not** yet happened — this sweep runs
  before the fold so `main` receives corrected docs.
- **Human-review gap (see status: revised):** this stub carries no `primary_files`
  frontmatter and an empty `touches` list. The sweep's edit targets must be pinned
  to concrete files before a builder is dispatched, because story-scoped write
  permissions are seeded from `primary_files`. Likely targets, to be confirmed by
  a human and recorded in frontmatter:
  - `docs/eras/003-flex-orchestrator-as-harness.md` and/or
    `docs/phases/index.md` — era-status defect (target 1)
  - `docs/architecture.md` and/or `CLAUDE.build.md` — post-flip staleness
    (target 2); if `docs/architecture.md` is edited it must be added to `touches`
  - `skills/pairmode/skills/reviewer/procedure.md` — reviewer input-scope
    contradiction (target 3)

## Ensures
<!-- Binary assertions the reviewer checks independently. One per line. -->

- The Era 003 doc (`docs/eras/003-flex-orchestrator-as-harness.md`) states a single
  consistent era status: `active`, all planned phases complete, formal close
  pending field validation — with no sentence claiming or implying the era is
  closed or that field validation is done.
- No canonical doc under `docs/` or the repo-root build docs describes the
  orchestrator as *executing* the build-loop procedure in-context as the current
  mechanism; every current-tense description of the loop reflects the post-flip
  model (thin dispatch loop + `next-action` resolver + disposable leaf workers).
  Historical/past-tense narration of the pre-flip state is left intact.
- The reviewer procedure skill (`skills/pairmode/skills/reviewer/procedure.md`)
  contains exactly one, non-contradictory statement of the reviewer's permitted
  input scope; no two passages in that file assert conflicting input rules.
- `docs/brief.md` is unmodified by this story (`git diff --name-only` for the
  story commit does not list `docs/brief.md`).
- If `docs/architecture.md` is edited, it appears in this story's `touches`
  frontmatter; if it is not edited, `touches` need not list it.
- The pairmode test suite is green: `uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

1. This is a documentation-correctness story. Do not change runtime behavior or
   code logic; edits are confined to prose in the doc/skill files.
2. **Target 1 — era status.** Read
   `docs/eras/003-flex-orchestrator-as-harness.md` and `docs/phases/index.md`.
   Reconcile any statement about the era being closed / fully validated against
   the authoritative status: era `active`, all 8 planned phases complete, formal
   close pending field validation. Fix only the contradicting sentences; preserve
   the completed-phase summary.
3. **Target 2 — post-flip staleness.** Search the canonical docs
   (`docs/architecture.md`, `CLAUDE.build.md`, and any doc that narrates the build
   loop) for present-tense descriptions of the pre-flip model where the
   orchestrator itself runs the loop procedure from `CLAUDE.build.md` in its own
   context. Rewrite those to the post-flip model (harness = thin dispatch loop;
   `next-action` resolver owns sequencing/counters/routing; each unit of work is a
   leaf worker in disposable context). Do not rewrite passages that are explicitly
   historical/past-tense. If you edit `docs/architecture.md`, add it to the story's
   `touches` frontmatter.
4. **Target 3 — reviewer input-scope contradiction.** Read
   `skills/pairmode/skills/reviewer/procedure.md` end to end and locate the two (or
   more) passages that state conflicting rules about what the reviewer may read.
   Resolve to a single consistent statement of reviewer input scope. Do not change
   the review checklist or output-format sections beyond the input-scope wording.
5. **Do NOT touch `docs/brief.md`.** The brief is operator-intent and forbidden to
   this story; that is the explicit scope reduction from the original RELEASE-022
   attempt. If a brief.md change seems needed, stop and surface it — do not edit.
6. Keep each edit minimal and localized. This story corrects existing prose; it
   does not restructure the docs.

## Tests

- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` — suite green
  (documentation edits must not break any test).
- Manual verification (documentation story):
  - `git diff --name-only` for the story commit does **not** include
    `docs/brief.md`.
  - Re-read each edited file and confirm the three target defects are resolved and
    no new contradiction was introduced.

## Out of scope

- **`docs/brief.md`** — explicitly excluded (the forbidden section dropped from the
  original attempt). No edit to operator-intent.
- Any code-logic or runtime-behavior change — this is a prose-correctness sweep only.
- The fleet-migration syncs, the DP8 pre-fold gate, the fold merge, and worktree
  retirement — those are separate Phase 97 stories (RELEASE-043–061).
- Restructuring or rewriting docs beyond the three named defects; unrelated
  staleness found elsewhere should be filed to the backlog, not fixed here.
