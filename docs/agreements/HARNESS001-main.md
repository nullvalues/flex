# Agreements — HARNESS001-main · Resolver foundation (deterministic skeleton)

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS001-ante1` (preflight complete, tagged `cp-HARNESS001-ante1`) —
left behind the dev line (`harness` branch + `/mnt/work/flex-harness` worktree), the
`v0.2.0` rollback anchor, the additive contract (DP4) + CLI-surface freeze test, and the
state-ownership table (DP7).
**Phase key:** `HARNESS001-main` · **Rail:** RESOLVER
**Builds on:** `harness` branch, in `/mnt/work/flex-harness` (DP1). Breaking/refactor code
from here on does **not** land on `main`.
**Status:** ✅ SETTLED — all 8 DPs AGREED; story outline finalized (2026-06-26).

> An *agreements doc* records the decisions for a phase before any story is specced.
> We walk each decision point (DP) top to bottom; once a DP is settled, its **Decision**
> line moves from ⬜ OPEN to ✅ AGREED and becomes binding on the story specs. This doc is
> the input to `phase_new.py --phase-id HARNESS001 --suffix main`.

## Why this phase exists

Era 003 moves the deterministic skeleton of the build loop — sequencing, counters,
model-selection routing — out of the 986-line `CLAUDE.build.md` prose and into a
code-resident `next-action` resolver. **This phase builds that resolver as a CLI and
nothing else.** It runs *alongside* the existing orchestrator (it can answer "what's
next?" but is not yet wired into the live loop), is pure-read on all durable state (DP7),
and is fully unit-tested in isolation. No worker is converted, no template is touched, no
gate judgment is extracted — those are HARNESS002–006.

The load-bearing deliverable is the **interface**: the action grammar `next-action` emits.
Every later phase consumes it, so getting it right here is what the whole era rests on.

## Context (established facts)

- **The era invariant:** *the harness holds nothing that isn't reconstructable from
  `next-action`.* For this phase that means `next-action` must be a **pure function of
  existing durable state** — no private persisted state of its own (DP7 trip-wire: if it
  needs authoritative private state, escalate DP1 → fork).
- **Additive window (binding, from ante1):** the resolver is **pure-read**; the
  orchestrator/hooks remain sole writers of every shared surface (state-ownership table,
  `docs/architecture.md` § Era 003 additive contract). No existing `flex_build.py`
  subcommand signature changes; `next-action` is a pure *addition*. The CLI-surface freeze
  test (RELEASE-003) enforces this.
- **What the loop prose actually contains** (source: `CLAUDE.build.md`, read in full): a
  spec mode, a per-story pre-flight gate stack (context/auth/schema/stub/scope), model
  evaluation (builder/reviewer/auditor/intent), builder spawn + effort recording +
  guardrail, a pre-reviewer methodology commit, reviewer spawn, a result-handling ladder
  (PASS → advance; FAIL→retry→loop-breaker→pause), a between-stories context-budget check,
  and an 8-step checkpoint sequence. Several of these are **judgment-handoff** points where
  the prose routes but a *human or worker* decides (prompted model upgrade, guardrail pause,
  loop-breaker accept, gate-blocked resolution, build-paused, clear-and-resume).
- **Resolver-shaped code that already exists** (additive — must be reused, not duplicated or
  changed):
  - `story_resolver.py` — `resolve_story(id)`, `list_phase_stories(phase)` / parse Stories
    table. (188 lines)
  - `next_story.py` — next unbuilt story for a phase; **git-commit match is authoritative**
    over the table status column. Exit 0 found / 1 all-complete / 2 error. (243 lines)
  - `flex_build.py current-phase` — active phase file; exit 1 = all phases complete.
  - `flex_build.py read-attempt-count` / `write-attempt-count` / `clear-attempt-count` —
    `attempt_counter.json` (orchestrator-owned writer).
  - `select-builder-model` / `select-reviewer-model` / `select-security-auditor-model` /
    `select-intent-reviewer-model` (+ `model_selector.py`) — the model decision table.
  - `next-phase`, `mark-phase-complete` — phase-advance plumbing.
- **Open era threads this phase touches** (era doc § Open design threads): #1 *full state
  set the resolver must emit* — **the crux of this phase**. #3 *leaf-worker return contract*
  is an **input** here (how the resolver infers the last outcome) but is settled in HARNESS003;
  this doc fixes only the provisional inference, not the worker grammar.

---

## Decision points

### DP1 — The action grammar `next-action` emits *(crux; the whole era consumes it)*

**Question:** What exactly does one `next-action` invocation return? This is the interface
the dumb-loop pseudocode (`while (a = next-action()) != done: spawn worker-for(a.action)
with a.scalar, model=a.model`) binds to, and every later phase (workers, checkpoint
decomposition, the flip) consumes it. Getting the shape right is the deliverable.

**Sub-questions:**
- **Output format** — JSON object on stdout? (Consistent with `next_story.py --json`,
  `context-health` JSON.) Proposed: a single JSON object `{action, scalar, model,
  reason, meta}` + a human line; `--json` for machine form.
- **Action vocabulary** — the closed enum of actions. First cut (skeleton only, post-DP3 —
  `spawn-reviewer` dropped, it's intra-cycle/orchestrator-held): `spawn-builder` (= run one
  build cycle for a story at an attempt), `spawn-loop-breaker`, `checkpoint`, `await-user`,
  `done`. (Gate/spec workers and checkpoint-step decomposition arrive in later phases as
  *additional* action values — the enum is designed open-ended.)
- **`scalar`** — the single work payload (story ID for spawns; phase key for checkpoint;
  empty for done). Mirrors the era's "harness holds only the current action scalar."
- **`model`** — the resolved model for spawn actions, from the existing selectors. For a
  `prompted-upgrade` the action is `await-user` (the human decides), not `spawn-builder` —
  so `model` is only populated for auto-resolved spawns.
- **`reason` / `meta`** — human-readable selection reason (carried to `record_attempt.py
  --model-selection-reason`) + structured routing detail (attempt number, gate that
  blocked, FAIL-ladder rung).

**Recommendation:** settle a small, explicit, versioned JSON schema now; treat it as the
era's load-bearing contract and pin it with a schema fixture + round-trip test. Bias toward
*fewer* action values with rich `meta` over a large flat enum.

**Decision:** ✅ AGREED — versioned JSON object `{action, scalar, model, reason, meta}` on
stdout (human line by default; `--json` for machine form, consistent with `next_story.py
--json` / `context-health`). Action enum (post-DP3): `spawn-builder` (= run one build cycle
for a story at an attempt) · `spawn-loop-breaker` · `checkpoint` · `await-user` · `done`.
`scalar` = the single work payload (story ID for spawns, phase key for checkpoint, empty for
done). `model` populated only for auto-resolved spawns (prompted-upgrade ⇒ `await-user`).
`meta` carries attempt number, the FAIL-ladder rung, the blocking gate, and advisory
`warnings[]` (guardrail / context-budget). The enum is open-ended — later phases add values
(gate/spec workers, checkpoint steps). Pinned by a schema fixture + round-trip test.

---

### DP2 — The full resolver state set *(era open thread #1)*

**Question:** Every state the loop prose currently handles must map to exactly one emitted
action — *including* the judgment-handoff states, where the resolver routes but the decision
stays outside it. Below is the state set drawn from `CLAUDE.build.md`, proposed for
ratification. "Decision owner" names who decides at that state (never the resolver).

Evaluated at **cycle-boundary seams only** (DP3): working tree at HEAD, no spawn in flight.

| # | Resolver state (durable-state condition) | Emitted action | Decision owner |
|---|------------------------------------------|----------------|----------------|
| 1 | `current-phase` exit 1 (no active phase / all phases complete) | `done` | — |
| 2 | active phase, `next-story` finds an unbuilt story, attempt counter 0, model auto | `spawn-builder` (attempt 1) | resolver (skeleton) |
| 3 | same as #2 but `select-builder-model` = `prompted-upgrade` | `await-user` (reason `model-upgrade`) | **user** |
| 4 | a pre-flight gate (auth/schema/stub) signals blocked for the next story | `await-user` (reason `gate-blocked:<which>`) | **user** |
| 5 | attempt 1 cycle failed (status `planned`, counter = 1, no commit) | `spawn-builder` (attempt 2, `retry-upgrade`) | resolver (skeleton) |
| 6 | attempt 2 cycle failed (counter = 2, no commit) | `spawn-loop-breaker` | resolver routes; **user** decides the proposal (orchestrator-held handoff) |
| 7 | attempt 3 cycle failed (counter = 3, no commit), or user chose pause, or builder DEVELOPER-ACTION gate | `await-user` (reason `build-paused`) | **user** |
| 8 | story committed (PASS), more unbuilt stories remain in phase | `spawn-builder` (next story, attempt 1) | resolver (skeleton) |
| 9 | last story of phase committed | `checkpoint` | resolver routes; workers/gates decide pass/fail (HARNESS004) |

**Removed vs. the pre-DP3 draft:** the standalone `spawn-reviewer` state — builder→reviewer
is now intra-cycle (orchestrator-held). The loop-breaker *proposal decision* (old rows 6–7)
collapses into the orchestrator-held handoff after `spawn-loop-breaker` returns; the resolver
re-engages at the next durable seam (counter=3 + no commit, or terminal pause).

**Advisory signals (NOT states — `meta` flags on the next action):** guardrail-fired and
context-budget-exceeded. The prose treats both as informational (the *human* pauses, not the
loop), so the resolver surfaces them as `meta.warnings[]` on whatever action it emits, never
as a blocking `await-user`. The context-budget-exceeded flag specifically marks the emitted
seam as a **safe-clear point** for the human.

**Open modelling questions inside DP2:**
- **Spec mode** (`spec next phase`) — **RESOLVED: deferred** to HARNESS005 (spec-writer
  worker). HARNESS001 covers *build* sequencing only; `spec` is not a HARNESS001 action.
- **The pre-flight gate stack** — **RESOLVED:** the resolver **reads the deterministic
  exit-code gates** (`check-auth-gate` / `check-schema-gate` / `check-stub`) as pure facts and
  emits `await-user:gate-blocked:<which>` when one signals blocked. It renders **no judgment** —
  these are mechanical exit-code checks, so reading them is pure and additive, and it makes the
  state set complete (era thread #1) without crossing into HARNESS002 scope (the cold
  "should this proceed?" *judgment* gate-worker, which consumes these CLIs as signals).
- ~~**Guardrail / context-budget**~~ — **RESOLVED** (post-DP3): both are advisory `meta`
  flags on the next action, not states (see table note). The human pauses, not the loop.

**Recommendation:** ratify the 9-state table as the spec contract, confirm the two remaining
modelling questions (spec-mode deferral; gate-as-signal), and make the table the backbone of
the test suite (DP8). The non-negotiable property: **every judgment-handoff state emits
`await-user` and stops — the resolver never computes the decision.**

**Decision:** ✅ AGREED — the 9-state table is the spec contract, evaluated at cycle-boundary
seams. Both modelling questions resolved above (spec-mode deferred to HARNESS005; gates read
as deterministic signals → `await-user:gate-blocked`). Guardrail / context-budget are advisory
`meta.warnings[]`, not states. The binding property: every judgment-handoff state emits
`await-user` and stops — the resolver never computes the decision.

---

### DP3 — How `next-action` infers position (the pure-function input model)

**Question:** `next-action` must reconstruct "where are we" entirely from durable state, with
no private persisted state (DP7). Which files does it read, and how does it infer the harder
states — specifically the FAIL-ladder rung and "builder done, awaiting review"?

**Proposed input model (all read-only):**
- **Phase position** ← `current-phase` (active phase file) + `next_story.py` (next unbuilt
  story; git-commit-authoritative over table status).
- **Attempt rung** ← `attempt_counter.json` via `read-attempt-count`. Counter `0` = fresh;
  `1`/`2`/`3` = retry ladder rung.
- **Model** ← the existing `select-*-model` selectors, composed (not reimplemented).
- **Gate signals** ← the existing `check-auth-gate` / `check-schema-gate` / `check-stub`
  exit codes, read as facts.

**The subtle inference — outcome of the last attempt.** In the additive window the
orchestrator still parses `REVIEW-RESULT`; the resolver does **not** see worker returns. It
must infer outcome from durable state:
- **PASS** ⇒ a `story-<ID>` commit exists (`next_story` already treats the commit as
  authoritative) ⇒ story is done, advance.
- **FAIL** ⇒ no commit + status still `planned` + attempt counter advanced ⇒ route to the
  retry ladder by counter value.
- **"builder returned, reviewer not yet run"** — *this transient is not durably recorded
  today.* Within a single live orchestrator turn the orchestrator holds it in context; across
  a `/clear` it is reconstructed by re-running the builder (idempotent-ish) or by the
  orchestrator's own sequencing. **Open question:** does the resolver need to distinguish
  "spawn-builder" from "spawn-reviewer" at all in HARNESS001, or does it emit at the
  *story* granularity (`work-story`) and leave builder-then-reviewer sequencing to the
  orchestrator until HARNESS003 makes them separate leaf workers?

**Recommendation (provisional — the heart of the walk):** for HARNESS001, have `next-action`
resolve to **story-level granularity** (which story to work, at which attempt, with which
model, or `await-user`/`checkpoint`/`done`), and **not** attempt to emit the intra-story
builder/reviewer split — because that split has no durable seam today (no committed state
between builder-return and reviewer-spawn) and inventing one would require the resolver to
*write* state, breaking DP7. The builder→reviewer→result micro-sequence stays orchestrator-
held until HARNESS003 converts them to leaf workers with a durable return contract. This
keeps the resolver a clean pure function and defers the intra-story state to the phase that
actually needs it.

**Risk to flag:** if the walk decides HARNESS001 *must* emit `spawn-builder`/`spawn-reviewer`
separately, that forces a durable "builder-done" marker — re-open DP7's trip-wire.

**Decision:** ✅ AGREED — **story/cycle-level granularity.** `next-action` resolves at the
granularity of one build *cycle* (a builder→reviewer attempt), not the intra-cycle
builder-vs-reviewer split. Three settled consequences:

1. **Consulted only at safe seams.** The resolver is called at cycle boundaries — working
   tree at HEAD, no spawn in flight — where durable state is unambiguous (a `story-<ID>`
   commit ⇒ PASS; attempt counter advanced + no commit ⇒ FAIL). It is *never* consulted
   mid-cycle, so the "currently running vs. finished" transient never reaches it. This is
   the era's safe-clear seam, now made the resolver's contract.
2. **The retry ladder IS resolver-owned** (per the era's "the retry ladder" → code): routing
   across cycles — attempt 1 → attempt 2 (`retry-upgrade`) → loop-breaker → pause — is driven
   by `attempt_counter.json` + commit-presence, both durable. Only the *within-cycle*
   micro-sequence is orchestrator-held.
3. **Micro-sequences without a durable inter-step seam stay orchestrator-held** until
   HARNESS003 gives them a durable return contract: (a) builder→reviewer within one attempt,
   and (b) loop-breaker→present-to-user→await within the attempt-2 handoff. `spawn-reviewer`
   is therefore **not** a HARNESS001 resolver action.

This keeps `next-action` a clean pure function and requires no private resolver state (DP7
holds for the reason the architecture works).

---

### DP4 — The judgment boundary: what the resolver must never decide

**Question:** Make explicit the line between skeleton (in the resolver) and judgment (out).

**Proposed — the resolver ONLY routes; it never computes any of these verdicts:**
- whether to upgrade the model on a high-scope story (user, prompted-upgrade);
- whether a gate's *judgment* passes — the resolver reads the gate's deterministic signal but
  renders no verdict (verdict extraction is HARNESS002);
- whether to accept a loop-breaker proposal (user);
- whether a guardrail/context warning warrants a pause (user);
- whether a diff is in scope, auth/schema preconditions are genuinely met (worker, later);
- the checkpoint sub-verdicts — security/intent/doc (workers, HARNESS004).

**Recommendation:** adopt as the binding boundary; it is the concrete instance of the era's
"it does not codify judgment." Every item above resolves to an `await-user` (or, later, a
worker-spawn) action — never to a resolver-computed branch.

**Decision:** ✅ AGREED — adopted as the binding judgment boundary. The resolver routes;
it never computes any verdict in the list above. Each resolves to `await-user` now (or a
worker-spawn in a later phase), never to a resolver-computed branch.

---

### DP5 — Reuse vs. reimplement (module boundary)

**Question:** Does `next-action` compose the existing modules, or reimplement their logic?

**Context:** the additive contract forbids changing existing subcommand signatures. The
existing modules (`current-phase`, `next_story`, `read-attempt-count`, `select-*-model`,
`story_resolver`) already encode most of the position logic.

**Recommendation:** `next-action` is a **thin read-model that composes the existing modules
as a library** (import their functions, do not shell out), adding only the state-transition
logic that today lives as prose. It introduces a new module (e.g.
`skills/pairmode/scripts/next_action.py`) + a `flex_build.py next-action` subcommand, with a
**corresponding test file** (`tests/pairmode/test_next_action.py`, per review-checklist item
6). It changes none of the modules it composes. Where a needed function is buried in a CLI
command body rather than importable, **extract it to a module-level function** (pure
refactor, signature-preserving) rather than duplicating.

**Decision:** ✅ AGREED — `next_action.py` is a thin read-model composing the existing modules
as a library (import, no shelling out), adding only the transition logic that today lives as
prose. New `flex_build.py next-action` subcommand + `tests/pairmode/test_next_action.py`. No
composed module's signature changes; buried logic is extracted to a module-level function
(signature-preserving), never duplicated.

---

### DP6 — Model-selection routing placement

**Question:** The era pseudocode carries `model=a.model`. Where does model selection happen,
and how does it interact with the `prompted-upgrade` fork (which needs a human)?

**Recommendation:** `next-action` calls the existing selectors and **embeds the resolved
model + reason in the action** for the *auto* cases (`auto-baseline`, `auto-downgrade`,
`retry-upgrade`). For `prompted-upgrade` it emits `await-user` (reason `model-upgrade`, with
the suggested model in `meta`) and stops — the human's reply re-enters the loop, after which
`next-action` (or an override flag) yields the spawn with the chosen model. The selectors are
unchanged; the resolver only *routes* their output.

**Decision:** ✅ AGREED — resolver embeds resolved model + reason in `spawn-builder` for the
auto cases (`auto-baseline`/`auto-downgrade`/`retry-upgrade`); emits `await-user:model-upgrade`
(suggested model in `meta`) for `prompted-upgrade`. Selectors unchanged; the resolver only
routes their output.

---

### DP7 — Scope fence for HARNESS001-main (+ the housekeeper merge question)

**Question:** What is explicitly in vs. out of this phase, and does HARNESS008 (housekeeper /
graph-integrity) merge in here?

**Proposed scope fence:**
- **In:** `next-action` CLI + module; the DP1 action grammar; the DP2 build-sequencing state
  set; pure-read position inference (DP3); composition of existing selectors/gates; full unit
  tests in isolation; advisory-only (NOT wired into the live `CLAUDE.build.md`).
- **Out (later phases):** gate *verdict* extraction (HARNESS002); leaf-worker conversion +
  durable return contract (HARNESS003); checkpoint-step decomposition (HARNESS004); spec-writer
  action (HARNESS005); template/flip (HARNESS006); observability read-model (Phase G).
- **Housekeeper (HARNESS008):** the era doc says it "may merge into HARNESS001-main if it
  stays small." **Recommendation: keep it OUT** — graph-integrity checking (deferred-story
  sweep, orphan/status-drift, era→phase→story cross-link validation) is a distinct read-model
  concern and folding it in now bloats the foundation phase. Capture as its own phase unless
  the walk finds it trivially co-located with the position-inference read-model.

**Decision:** ✅ AGREED — scope fence adopted as proposed. **In:** the `next-action` CLI +
module, the DP1 grammar, the DP2 state set, pure-read position inference, composition of
existing selectors/gates, full isolation tests, advisory-only (NOT wired into the live
`CLAUDE.build.md`). **Out:** everything HARNESS002+. **Housekeeper (HARNESS008) stays OUT** —
kept a distinct phase to keep the foundation lean.

---

### DP8 — Isolation testing strategy (the acceptance backbone)

**Question:** "Fully unit-tested in isolation" — what is the test model?

**Recommendation:** a fixture harness that constructs a synthetic durable-state tree (phase
docs + Stories tables, story files with frontmatter, a fake git log for commit-authority,
`state.json`, `attempt_counter.json`) and asserts `next-action` emits the exact action for
each of the DP2 states. One test per state row (≥13), plus the DP1 schema round-trip test and
the DP5 "composes, does not duplicate" guard (e.g. assert no signature drift in the reused
selectors). Targets review-checklist items 6 (test coverage) and 10 (build gate).

**Decision:** ✅ AGREED — synthetic durable-state fixture tree (phase docs + Stories tables,
story frontmatter, a fake git log for commit-authority, `state.json`, `attempt_counter.json`);
one assertion per DP2 state (9) + the DP1 schema round-trip + the DP5 "composes, no signature
drift" guard. Backs review-checklist items 6 and 10.

---

## Resulting story outline (RESOLVER rail — finalized)

All DPs ✅ AGREED. Stories land on the `harness` branch in `/mnt/work/flex-harness` (DP1),
advisory-only — none wires `next-action` into the live `CLAUDE.build.md` (DP7). Built by
flex's own 0.2.x loop (era DP6). Sequenced so each story's tests pass before the next.

| Story | Title | Lands on | Acceptance gist |
|-------|-------|----------|-----------------|
| RESOLVER-001 | Action grammar + schema fixture (DP1) | `harness` | Versioned JSON schema for `next-action` output `{action, scalar, model, reason, meta}`; action enum `spawn-builder · spawn-loop-breaker · checkpoint · await-user · done`; schema fixture + round-trip test. No CLI wiring yet. |
| RESOLVER-002 | Position-inference read-model (DP3, DP5) | `harness` | `next_action.py` composes `current-phase` / `next_story` / `read-attempt-count` / `select-*-model` / gate exit-codes as a library; signature-preserving extractions where logic is buried in CLI bodies; pure-read, no private state. Unit-tested against synthetic durable state. |
| RESOLVER-003 | State machine + `next-action` subcommand (DP2, DP4, DP6) | `harness` | The 9-state transition table → emitted actions; `flex_build.py next-action` subcommand; judgment-handoff states emit `await-user`; guardrail/context-budget surfaced as `meta.warnings[]`; model embedded for auto cases, `await-user:model-upgrade` for prompted-upgrade. |
| RESOLVER-004 | Isolation test suite (DP8) | `harness` | Synthetic durable-state fixture tree; one assertion per DP2 state (9) + DP1 schema round-trip + DP5 "composes, no signature drift" guard. Backs review-checklist items 6 + 10. |

**Note:** RESOLVER-002 and -003 are close-coupled; if the read-model proves thin they may
merge at spec time. The CLI-surface freeze test (RELEASE-003) must continue to pass —
`next-action` is a pure *addition*.

## Open questions / backlog ties

- **CER-058** (`meander` in `registered_projects`) — unrelated to resolver foundation; leave
  in backlog.
- **CER-059** / **CER-054** — HARNESS006 / Phase G; not pulled forward here.
- `state.json` non-atomic write (ante1 DP7 pre-existing note) — the resolver tolerates a
  transient malformed read; atomic-write hardening remains a backlog candidate, not in scope.

## Status

✅ SETTLED — DP1–DP8 all ✅ AGREED; story outline finalized. **Ready for**
`phase_new.py --phase-id HARNESS001 --suffix main` and `story_new.py` on the RESOLVER rail
(RESOLVER-001 … RESOLVER-004), built on the `harness` branch in `/mnt/work/flex-harness`.
The phase spec is the next step; this agreements doc is its input.
