---
id: INFRA-315
rail: INFRA
title: Pre-build intent review — resolver emits spawn-intent-reviewer before the first build of a fresh phase, behind Build-standards opt-in
status: draft
phase: "116"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/next_action.py
touches:
  - skills/pairmode/templates/CLAUDE.build.md.j2
  - skills/pairmode/skills/intent-reviewer/procedure.md
  - tests/pairmode/test_next_action.py
  - docs/architecture.md
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Cora item A#2 (AG-6): run the intent reviewer on a phase spec **before the
first builder spawn**, not only at checkpoint — spec-level drift caught
pre-build costs one edit; caught at checkpoint it costs every token already
spent. The 2026-07-29 cold-eyes pass is itself the live demonstration: it
caught plan-level holes (F4's unsatisfiable Ensures, F5's era gap) before any
builder ran.

The machinery mostly exists: `next_action.py` already defines
`SPAWN_INTENT_REVIEWER` (`next_action.py:173`) and dispatches it in the
checkpoint sequence. This story adds one resolver behaviour: when the active
phase's Stories table is entirely `planned`/`draft` (no story has a build
attempt or commit yet — a *fresh* phase) and the project's Build standards
opt in (`intent_review: pre-build`), `next-action` resolves to
`spawn-intent-reviewer` (scalar: the phase) once, before the first
`spawn-builder`.

**Correct signal: on a fresh opted-in phase, the resolver's first non-spec
action is `spawn-intent-reviewer`, and after that review is recorded it never
re-fires for the same phase. Forbidden proxy: an instruction line in
CLAUDE.build.md telling the orchestrator to "consider an intent review" —
the behaviour must be resolver-emitted, not prose-suggested.**

## Requires

1. `next_action.py` action grammar: `_REQUIRED_KEYS` (`:241`),
   `SPAWN_INTENT_REVIEWER` (`:173`), the row-decision table (`:1056+`), and
   the model-null rule (`:315` — model must be null for non-builder spawns).
   The new emission must conform to the existing schema; no schema-version
   bump unless a new key is genuinely required (justify in evidence if so).
2. Build standards live as a one-line key=value block in
   `CLAUDE.build.md` (template: `CLAUDE.build.md.j2:50`, INFRA-240 pattern:
   per-project facts the skills read). `intent_review` joins that block;
   absent → today's behaviour, byte-identical resolver output.
3. "Already reviewed" needs durable evidence, not memory: the resolver is
   stateless per invocation. Use the same evidence style the resolver
   already trusts (state.json key or recorded step), consistent with
   INFRA-299's recording-integrity rules; pick one and document it.
4. Fresh-phase detection must not misread cross-references: INFRA-297
   (phase 113) scoped commit build-evidence to the commit's own story —
   reuse its helpers for "no story in this phase has build evidence".
5. Baseline 4116/211.

## Ensures

1. **Opt-in emission.** Fixture: opted-in project, phase all-`draft`/`planned`,
   no attempts → `next-action` returns `spawn-intent-reviewer` with the
   phase as scalar, `model: null`, and a reason naming pre-build intent
   review. Without the opt-in key (or any other value than `pre-build`),
   output is byte-identical to today's for the same fixture.
2. **Fires once.** After the review outcome is recorded (Requires 3's
   evidence), the same fixture resolves to `spawn-builder`. The evidence
   key is phase-scoped: a later fresh phase re-fires.
3. **Never mid-phase.** A phase with ≥ 1 story `complete`/`in-progress` or
   any recorded attempt never triggers the pre-build emission, opted-in or
   not — this gate is for fresh specs only.
4. **Verdict routing is advisory-block, not silent.** The intent-reviewer's
   FAIL/flag verdict routes to `await-user` (spec drift is an operator
   decision, not an auto-fix); PASS routes to `spawn-builder`. Mirrors the
   existing checkpoint-time verdict handling — reuse it, don't fork it.
5. **Procedure + docs updated.** `intent-reviewer/procedure.md` gains a
   short pre-build mode note (what to compare when no diff exists yet:
   phase Goal vs story specs vs era intent); `docs/architecture.md`
   documents the opt-in key; `CLAUDE.build.md.j2`'s Build standards line
   carries the new key with a default of unset/off.
6. **Suite green** without `-x`; baseline + added tests. Existing resolver
   tests pass unmodified except any that enumerate the Build-standards keys.

## Instructions

1. Read the resolver's decision-table docstring (`:1056+`) and add the new
   row *above* the spawn-builder rows, guarded by opt-in + freshness +
   no-evidence; update the docstring table in the same commit.
2. Reuse INFRA-297's evidence helpers (Requires 4) and the checkpoint-time
   intent-reviewer verdict path (Ensures 4).
3. Tests: three fixtures (opted-in fresh, opted-out fresh, opted-in
   mid-phase) plus the once-only round-trip.

**Do not:** make pre-build review default-on (opt-in is the agreement);
add prose-only enforcement (the forbidden proxy); spawn it per-story (it is
per-phase).

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_next_action.py -q 2>&1 | tail -10
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q 2>&1 | tail -5
```

Acceptance: green; baseline held. Reviewer negative checks: (a) opted-out
fixture output byte-identical to pre-story behaviour; (b) the once-only
evidence survives a resolver re-invocation (stateless re-run test); (c) no
new prose instruction in CLAUDE.build.md.j2 stands in for the resolver row.

## Out of scope

- Changing what the intent reviewer *checks* (procedure note only).
- Checkpoint-time intent review (exists; untouched).
- Downstream rollout of the opt-in (post-tag campaign).
