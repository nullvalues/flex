---
id: INFRA-314
rail: INFRA
title: Deferral/disposition gates at both boundaries — checkpoint-tag refusal, era-transition check, phase_new --parent-phase/--proposed, forbidden-proxy stub
status: draft
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/flex_build.py
  - skills/pairmode/scripts/era_transition.py
  - skills/pairmode/scripts/phase_new.py
touches:
  - skills/pairmode/scripts/index_integrity.py
  - tests/pairmode/test_index_integrity.py
  - docs/phases/index.md
  - skills/pairmode/templates/docs/phases/phase.md.j2
  - skills/pairmode/scripts/story_new.py
  - tests/pairmode/test_story_new.py
  - tests/pairmode/test_flex_build.py
  - tests/pairmode/test_era_transition.py
  - tests/pairmode/test_phase_new.py
  - docs/architecture.md
  - docs/cer/backlog.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Cora item A#6 plus the reconciliation's T5 (AG-6): "the deferral protocol is
what makes phase docs trustworthy forensic records instead of optimistic
fiction" — and cora's own caveat was that disposition verification "is NOT
currently enforced by the 0.3.0 tooling and is a real gap." The cold-eyes
review is the incident report at both boundaries: 13 deferred-without-section
violations in `phase-97.md` (story→phase), and era 003 left active with
`planned` phases while era 004 opened (phase→era — the exact failure T5 shows
a story-level gate alone would have missed).

Four pieces:

1. **Story→phase gate:** `record-checkpoint-step checkpoint-tag` refuses when
   the phase manifest holds `planned`/`draft`/`in-progress` stories that are
   neither `complete` nor named in a `## Deferred stories` section.
2. **Phase→era gate:** the era-transition path refuses to close an era whose
   ledger holds phases not `complete`/`deferred` — and, because two eras can
   be active simultaneously (live incident), it must take the target era
   **by ID**, not "the active era."
3. **`phase_new.py --parent-phase N`** — stamps the fork provenance line
   (`**Parent phase:**`) the phase-continuity policy requires.
4. **A#3 polish (folded per the agreements' unambiguous-dispositions
   discretion):** `phase_new.py --proposed <name>` emits
   `phase-proposed-<name>-YYYYMMDD-NNN.md` (the convention
   `docs/phases/index.md:143-148` documents but no tool implements), and the
   story template gains a forbidden-proxy stub — one comment line under
   Ensures prompting "state the correct signal AND the forbidden proxy".

Detection partially exists: `index_integrity` check 4 flags
deferred-without-section after the fact. This story adds *refusal at act
time*; the checks must agree (one definition of "formally deferred").

## Requires

1. `record-checkpoint-step` phase-keyed step machinery
   (`flex_build.py:~2916-3290`; terminal step `checkpoint-tag` at `:2990`,
   which also marks the phase complete via the shared INFRA-239
   implementation, `:1109-1112`). INFRA-313 lands its CER gate at the same
   seam first — compose, don't collide: both gates run, each with its own
   named refusal message.
2. `era_transition.py`: `_find_active_eras` returns a list (`:29`);
   `era_transition_cli` (`:108`) closes "the current active era" and creates
   the next. The refusal check and by-ID targeting go here;
   `_close_era_frontmatter` (`:64`) is the write to guard.
3. `index_integrity.py` check 4 (`:340-375`, deferred-without-section) and
   `is_phase_inactive` (`:72-78`) — reuse their definitions of "deferred"
   and "inactive"; do not fork a variant predicate.
4. `phase_new.py` is a click CLI (`:259+`). The proposed-file naming
   convention is documented at `docs/phases/index.md:143-148`.
5. INFRA-310 builds after this story and its era-003 closure must *pass*
   these gates — phases 106/107/108 will be `deferred` with notes by then.
   The gates must therefore accept `deferred`-with-section as clean, or
   INFRA-310 deadlocks. A test pins this exact composition.
6. Baseline 4116/211.

## Ensures

1. **checkpoint-tag refuses on undispositioned stories.** Against a fixture
   phase with one `planned` story and no `## Deferred stories` entry,
   `record-checkpoint-step checkpoint-tag` exits nonzero, does not record
   the step, does not mark the phase complete, and names the story ID and
   the two legal resolutions (complete it, or defer it formally). With the
   story either `complete` or named in `## Deferred stories` (status
   `deferred`), the step records. **Correct signal: the step/state write is
   absent after refusal; forbidden proxy: a warning line while the tag step
   records anyway.**
2. **Era close refuses on undispositioned phases and takes an ID.** The
   era-transition path gains a required era-ID argument (or equivalent
   explicit selector); given an era whose ledger holds a phase not
   `complete`/`deferred`, it exits nonzero naming the phases and writes
   nothing (`_close_era_frontmatter` not reached; era file byte-identical).
   Given a clean ledger, it closes exactly the named era even when two eras
   are active. **Forbidden proxy: closing `active[-1]` implicitly.**
3. **One deferral predicate.** The story→phase gate and `index_integrity`
   check 4 share one definition of "formally deferred" (same function or
   same imported predicate); a story formally deferred per the gate never
   trips check 4, proven by a round-trip test.
4. **`--parent-phase`.** `phase_new.py --parent-phase 115` emits a phase doc
   whose body opens with `**Parent phase:** Phase 115 — <title>` under the
   H1, per the phase-continuity policy. Omitted → no line (unchanged
   output, byte-level, for existing invocations).
5. **`--proposed`.** `phase_new.py --proposed <name>` writes
   `docs/phases/phase-proposed-<slug>-YYYYMMDD-NNN.md` (NNN monotonically
   next for that date), carries no sequential phase number, and does **not**
   touch `docs/phases/index.md`'s numbered table. The proposed-phases
   section convention text in `index.md` is updated only if its wording
   contradicts the implementation.
6. **Forbidden-proxy stub.** The story scaffold `story_new.py` emits
   (body block at `story_new.py:87-89`) gains one HTML comment under
   `## Ensures`: acceptance criteria must state the correct signal AND the
   forbidden proxy. Newly created stories carry it; no existing story file
   is rewritten.
7. **Composition with INFRA-310 pinned.** A test builds the phase-107-shaped
   fixture (phase `deferred` in index + era ledger, stories `backlog`,
   `## Superseded` note) and asserts both gates pass — the exact state
   INFRA-310 must leave behind (Requires 5).
8. **Docs + CER.** `docs/architecture.md` phase-authoring/checkpoint section
   documents both gates in ≤ 25 added lines. Any CER row the agreements
   filed for A#6 is annotated `RESOLVED Phase 116 — INFRA-314`; if none
   exists, evidence states so.
9. **Suite green** without `-x`; baseline + added tests.

## Instructions

1. Build after INFRA-313; read its gate seam first so the two refusals
   compose in one step handler with distinct messages.
2. Implement the story→phase gate against `index_integrity`'s predicates
   (Requires 3) — hoist, don't copy.
3. Refactor `era_transition` to explicit-ID targeting; keep the existing
   close-then-scaffold flow for the normal single-era case (the new
   argument may default to the sole active era when exactly one exists;
   with two or more, it must be required — that is the incident case).
4. Add the two `phase_new` flags with golden-file tests.
5. Template stub last (Ensures 6); do not reflow the template otherwise.

**Do not:** rewrite historical phase docs (phase-97's cleanup is
INFRA-310's); auto-defer anything (the gate refuses, a human dispositions);
break `era_transition`'s existing single-active-era invocation shape used by
RELEASE-072-era tests.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_flex_build.py tests/pairmode/test_era_transition.py tests/pairmode/test_phase_new.py tests/pairmode/test_index_integrity.py -q 2>&1 | tail -15
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative checks: (a) refusal
paths assert *absence of writes*, not just exit codes; (b) the two-active-era
fixture exists and the implicit `active[-1]` path is gone; (c) the
INFRA-310-composition test (Ensures 7) exists — its absence is a HIGH
finding, since it is what keeps the era's own terminal story buildable.

## Out of scope

- Dispositioning any real phase (106/107/108/97 belong to INFRA-310).
- A resume-time tooling path ("Picks up deferred stories from Phase N" is
  authored prose; only fork-time gets a flag).
- Downstream propagation (post-tag sync campaign).
