---
id: INFRA-439
rail: INFRA
title: guard and stop-condition updates for handshake artifacts
status: stub
id_provisional: true # INFRA numbering assigned at sequencing — upstream counter moves
phase: "proposed:shadow-handshake"
narrative_roles: [SHADOW-REVIEWER, ORCHESTRATOR]
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/scope_guard.py
  - skills/pairmode/skills/shadow-reviewer/procedure.md
touches:
  - tests/pairmode/test_scope_guard.py
  - .gitignore
---

## Context

Today the shadow-reviewer's stop condition is a blind fixed-cycle poll (20
cycles, `skills/pairmode/skills/shadow-reviewer/procedure.md` § Stop
condition): in production this window closes in roughly 60-80 seconds, while
real builder attempts run 10-19+ minutes, so the shadow gives up before it
ever observes meaningful builder activity — `shadow_review=concurrent` is
currently a no-op on any non-trivial build. INFRA-437 and INFRA-438 replace
the polled-diff protocol with an event-driven handshake (builder writes a
`.pairmode-review-request` quiescence marker; shadow acks `OPEN` in
`.pairmode-review.lck`, runs its full-diff pass, appends findings, writes
`CLOSED`; builder waits for `CLOSED` and addresses findings). This story is
the guard/glue layer: `scope_guard` must admit both new gitignored artifacts,
each confined to exactly one writer role (mirroring the CER-174/175
shadow-confinement pattern), and the shadow procedure's stop-condition
section must be rewritten around the new handshake — with the critical
requirement that the old 20-cycle poll ceiling stays retired from the wait
it used to bound (builder activity) and is repurposed only to bound the new,
much shorter OPEN→CLOSED exchange. Collapsing the two waits back into one
flat timeout would silently reintroduce the exact bug this phase exists to
fix.

## Requires

- INFRA-437 (shadow procedure v2: OPEN/CLOSED entries, full-diff pass,
  `.pairmode-review.lck` writer) landed, so the lck's write pattern and
  content contract (`OPEN`/`CLOSED`) exist for this story's guard rule and
  stop-condition prose to reference.
- INFRA-438 (builder quiescence signal, bounded wait, dispositions) landed,
  so `.pairmode-review-request`'s write pattern and the builder's own
  wait-for-`CLOSED` behavior exist for this story's guard rule to reference.

## Ensures

`scope_guard` admits the builder-owned `.pairmode-review-request` marker and
the shadow-owned `.pairmode-review.lck` (both gitignored, never committed,
each writable by exactly one role, unwritable by the other), and the shadow
procedure's stop condition becomes CLOSED-then-story-commit. The retained
poll ceiling from the old fixed-cycle mechanism is repurposed narrowly: it
bounds only the OPEN→CLOSED handshake exchange once builder quiescence (the
`.pairmode-review-request` marker) is observed — never the outer wait for
that marker to appear. The outer wait-for-quiescence loop is not bounded by
the old ~60-80s/20-cycle budget; it runs for as long as the builder is
actually working, bounded only by a generous absolute ceiling set far longer
than any real build (or left effectively unbounded), so a build running
10-19+ minutes is still observed by the shadow rather than abandoned before
quiescence is ever reached.

## Instructions

1. In `scope_guard.py`, extend the existing `agent_type == "shadow-reviewer"`
   confinement branch (§ CER-174/175, `_SHADOW_REVIEWER_ONLY_PATH`) so the
   shadow role's permitted write set is exactly `.pairmode-suggestions.md`
   (or its INFRA-437 successor path, if renamed) and `.pairmode-review.lck` —
   no other path, same default-deny-otherwise pattern already in place.
2. Add a parallel, symmetric guard rule for the builder role admitting
   exactly `.pairmode-review-request` as a builder-writable, gitignored,
   worktree-root-only path — using the same cwd-only worktree-root
   derivation the shadow branch already uses (INFRA-408), not a fallback to
   `file_path` content or `state.json`. The shadow role must be denied
   writing `.pairmode-review-request`, and the builder role must be denied
   writing `.pairmode-review.lck` — verify both denials explicitly (see
   `## Tests`).
3. Add `.pairmode-review-request` and `.pairmode-review.lck` to `.gitignore`,
   next to the existing `.pairmode-suggestions.md` entry, if INFRA-437/438
   have not already added them (idempotent — do not duplicate an existing
   entry).
4. Rewrite `skills/pairmode/skills/shadow-reviewer/procedure.md`'s
   `## Stop condition` section around two distinct, separately-bounded
   waits — do not merge them into one timeout:
   - **Outer wait (for builder quiescence):** the shadow waits for
     `.pairmode-review-request` to appear. This wait is bounded only by a
     generous absolute ceiling chosen to exceed any real build's duration
     (e.g. an order of magnitude above the ~19-minute longest observed
     attempt, not the old 20-cycle/~60-80s budget), or left effectively
     unbounded and terminated only by the worktree teardown that already
     bounds every build. State explicitly in the doc that this ceiling is
     not the same ceiling as the one below.
   - **Inner wait (the OPEN→CLOSED handshake):** once quiescence is
     observed, the shadow writes `OPEN`, runs its full-diff pass, appends
     findings, and writes `CLOSED` — this exchange is expected to be fast.
     The retained fixed poll-cycle ceiling from the old mechanism applies
     *only* here, as a backstop against a shadow that dies mid-exchange
     (writes `OPEN` and never reaches `CLOSED`), not as a bound on the outer
     wait.
   - Stop condition overall: `CLOSED`-then-story-commit, i.e. the shadow's
     run ends after it writes `CLOSED` (or, in the mid-review-death case,
     after the inner ceiling backstop fires).
5. Do not touch INFRA-437's or INFRA-438's own file scope beyond the guard
   and stop-condition edits above — if a conflict surfaces (e.g. the exact
   lck content contract), match what INFRA-437 actually shipped rather than
   redefining it here.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_scope_guard.py -q
```

Add cases to `tests/pairmode/test_scope_guard.py` asserting, for a worktree
cwd resolving to an active story:
- `agent_type="shadow-reviewer"` writing `.pairmode-review.lck` → allowed.
- `agent_type="shadow-reviewer"` writing `.pairmode-review-request` → denied.
- `agent_type="builder"` (or unset/default) writing `.pairmode-review-request`
  → allowed.
- `agent_type="builder"` writing `.pairmode-review.lck` → denied.

Acceptance: suite green, including all four new cases.

For the stop-condition doc rewrite (§ Instructions step 4), verify by
inspection (not test-suite-enforced, since this is prose in a procedure
skill) that `## Stop condition` in
`skills/pairmode/skills/shadow-reviewer/procedure.md` names two distinct
ceilings — one for the outer quiescence wait, one for the inner OPEN→CLOSED
exchange — and does not describe a single flat timeout covering both.

## Out of scope

- Writing the shadow's `OPEN`/`CLOSED`/full-diff-pass logic itself, and
  renaming/relocating the suggestions file — INFRA-437.
- The builder's own quiescence-marker write, its bounded wait for `OPEN`,
  and per-finding disposition logging — INFRA-438.
- Any change to `docs/phases/phase-proposed-shadow-handshake-20260807-003.md`
  itself.

## Spec-writer notes

- `docs/narratives/SHADOW-REVIEWER/SHADOW-REVIEWER-000-ideology.md` (cited in
  this story's `narrative_roles:`) does not exist yet — bounded input 6 for
  the SHADOW-REVIEWER role could not be read. `ORCHESTRATOR`'s narrative was
  read and is unaffected by this gap. Flagging for operator resolution
  (`status: "revised"`) rather than silently proceeding as if the input were
  absent-and-optional.
