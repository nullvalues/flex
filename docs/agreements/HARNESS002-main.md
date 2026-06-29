# Agreements — HARNESS002-main · Gate verdict extraction

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS001-main` (resolver foundation complete, tagged `cp-HARNESS001-main`) —
left behind the advisory-only `flex_build.py next-action` resolver: the action grammar
(`make_action`/`validate_action`/`ACTIONS`), the pure-read `infer_position` read-model, and the
`resolve_next_action` 9-state DP2 machine, all isolation-tested. Still **not** wired into the live
`CLAUDE.build.md` (DP7); the additive contract + CLI-surface freeze test guard the fleet.
**Phase key:** `HARNESS002-main` · **Rail:** WORKER (with a RESOLVER touch — DP1)
**Builds on:** `harness` branch, in `/mnt/work/flex-harness` (DP1). Breaking/refactor code does
**not** land on `main`.
**Status:** ✅ SETTLED — all 8 DPs AGREED; story outline finalized (2026-06-28).

> An *agreements doc* records the decisions for a phase before any story is specced. We walk each
> decision point (DP) top to bottom; once a DP is settled its **Decision** line moves from ⬜ OPEN
> to ✅ AGREED and becomes binding on the story specs. This doc is the input to
> `phase_new.py --phase-id HARNESS002 --suffix main`.

## Why this phase exists

The era inverts the gates' relationship to the LLM. **Today an exit code *is* the verdict:** each
`check-*` gate exits `1` and the loop hard-blocks to `await-user`, rendering no judgment (the
`next_action.py` Row-4 handoff is a *dumb* stop — `await-user:gate-blocked:<which>`). HARNESS002
inserts a **cold, disposable gate worker** between the deterministic signals and the resolver's
routing: the `check-*` CLIs stay *signal providers* (cheap deterministic facts), the **worker**
reads those signals plus the actual story context and renders the verdict, and the resolver
*routes* on the verdict but never computes it. This **raises** the LLM's role at the gates — the
concrete instance of the era's *"it does not codify judgment."*

This is the era's **first leaf-worker conversion** (no worker scaffold exists yet) and it
establishes the **designated safe-clear seam**: the gate-worker spawn is where the working tree is
at HEAD, no mutation is in flight, and the `pre_tool_use`/`post_tool_use` budget hooks fire before
any Edit/Write.

Like HARNESS001, everything here is **advisory-until-flip**: built and isolation-tested but **not**
wired into the live `CLAUDE.build.md` until HARNESS006. The additive contract (DP4 of ante1) + the
CLI-surface freeze test (RELEASE-003) keep the fleet green throughout.

## Context (established facts — from the gate-surface survey, 2026-06-28)

Source: `flex_build.py` (gate CLIs), `next_action.py` (resolver), `CLAUDE.build.md` (live prose),
`tests/pairmode/test_cli_surface_freeze.py` (freeze).

| Gate | CLI (`flex_build.py`) | Detection | Resolving a block needs | Today |
|------|-----------------------|-----------|-------------------------|-------|
| **stub** | `check-stub` (1225–1258) | syntactic (delegation regex + acceptance headers) | edit the story — **mechanical** | exit 1 → hard block |
| **schema** | `check-schema-gate` (1333–1371) | frontmatter `schema_introduces` + body exception phrases + phase-manifest scan | **judgment** — is the exception legit? does a mgmt story exist? | exit 1 → hard block |
| **auth** | `check-auth-gate` (1424–1462) | frontmatter `auth_gated` + classification-line presence | **judgment** — is the auth model correctly classified? | exit 1 → hard block |
| **scope** | `check-story-scope` (990–1089) | heuristic (primary_files/touches vs disk) | advisory | never blocks (warning) |
| **context** | `/context` + `story-cost-estimate` | token estimate | advisory | never blocks (info) |

- **Resolver gate handling today:** `next_action.py` collects each gate to `{ok, blocked_reason}`
  (≈295–322) and Row 4 (≈473–493) emits `await-user` with `reason="gate-blocked:<which>"` in strict
  precedence `stub → schema → auth`; first block wins. No verdict is computed (DP4 of HARNESS001).
- **Worker/agent pattern today:** agents are prose at `.claude/agents/<role>.md`, rendered from
  `skills/pairmode/templates/agents/<role>.md.j2` via `sync-agents`. None render gate verdicts.
  **No leaf-worker (agent-shell + plugin procedure skill) scaffold exists** — HARNESS002 is first.
- **Freeze test:** `test_cli_surface_freeze.py` pins the 0.2.x command+flag set; **additions are
  allowed, removals/renames forbidden.** A new gate command is permissible; changing a `check-*`
  signature is not.

## Carry-forward obligations (inherited — addressed at DP7)

### CF-1 ← CER-060 (intent review, HARNESS001-main) — DP5 composition gap in the retry path

**What:** `resolve_next_action` Row 5 (attempt-1 FAIL → spawn attempt 2, `retry-upgrade`)
**hardcodes** `model="opus"` (`skills/pairmode/scripts/next_action.py`, the Row 5 branch) instead
of delegating to `select_builder_model(..., attempt_number=2)`.

**Why it matters:** Behaviour is correct *today* — it matches the `model_selector` table (any
`code` story at attempt ≥ 2 → opus/`retry-upgrade`). But the retry tier is now encoded in **two
places**, and the DP5 composition guard (`tests/pairmode/test_next_action_compose.py`) only
asserts import-*presence*, not call-site *coverage*. If a future phase rebalances the selector
table, the state machine will silently diverge. Root cause: `infer_position` computes
`builder_model` at `select_builder_model(..., attempt_number=max(attempt_count, 1))`, i.e. one
attempt **behind** the retry spawn, so the Position cannot supply the attempt-2 model.

**Required resolution (pick one — settled at DP7):**
1. **Preferred — fix the read-model:** on inferred FAIL, have `infer_position` compute the
   Position's `builder_model` at the *next* attempt number (`attempt_count + 1`), so Row 5 emits
   `position.builder_model` and the selector remains the single source of the retry tier (true DP5
   composition). Verify no other row regresses (Row 2 first-attempt model must stay attempt-1).
2. **Minimum — pin it with a test:** add an assertion that Row 5's emitted model equals
   `select_builder_model(<code story>, attempt_number=2)[0]`, so a future selector-table change
   fails loudly here. (Leaves the two-places encoding but removes the silent-divergence risk.)

**Status:** ⬜ OPEN — to settle at DP7. Tracked as **CER-060** (Do Later) in `docs/cer/backlog.md`.

> Note: CF-1 is small and self-contained. If HARNESS002's scope makes it awkward to bundle, it may
> be promoted to its own one-story fix phase instead — decide at DP7, do not pull it into a build
> without a spec.

---

## Decision points

### DP1 — What "gate verdict extraction" is, and the rail *(settled)*

**Question:** What does this phase concretely build, and what owns the verdict?

**Decision:** ✅ AGREED (2026-06-28).

1. **Reframe (binding correction to the seed).** The seed's earlier Scope wording — "moving gate
   judgment into the resolver/CLI surface" — is **rejected**: it contradicts the era invariant
   *"it does not codify judgment."* The corrected statement: HARNESS002 inserts a **cold,
   disposable gate worker** between the deterministic gate signals and the resolver's routing. The
   `check-*` CLIs stay **signal providers**; the **worker** renders the verdict; the **resolver**
   routes on it but never computes it. This *raises* the LLM's role versus today's exit-code-as-verdict.
2. **Single gate worker** (not per-gate workers). One spawn at the seam receives all signals and
   returns one verdict — fewer spawns, and a story that trips both auth and schema gets one
   coherent judgment, not two.
3. **The worker is a leaf in disposable context.** It loads only (a) the three `check-*` signal
   outputs, (b) the one story file under evaluation, and (c) the relevant diff/frontmatter — and
   then returns a scalar and dies. It **never inherits accumulated orchestrator/loop state.** So
   context cannot accumulate *across* seams (each spawn is cold) and is bounded *within* a spawn
   (one story's signals, not phase history). This "reads only its signal inputs + the single story"
   property is **binding** and a DP8 test target — it is the guardrail against the worker's own
   context becoming a liability.
4. **Rail = WORKER (with a RESOLVER touch).** The gate worker (agent shell + plugin procedure
   skill) is the WORKER deliverable; the new resolver action + verdict routing in `next_action.py`
   is the RESOLVER touch (DP4). Primary-domain ownership is WORKER — this corrects the seed's
   provisional "RESOLVER".
5. **Advisory-until-flip.** Built and isolation-tested; **not** wired into the live
   `CLAUDE.build.md` until the flip (HARNESS006). The freeze test stays green.
6. **Establishes the safe-clear seam.** The gate-worker spawn is the designated safe-clear point
   (working tree at HEAD, no mutation in flight, budget hooks fire before any Edit/Write); detailed
   at DP4.

---

### DP2 — The signal/verdict boundary *(era open thread #2)*

**Question:** Precisely which gate facts stay deterministic, resolver/CLI-owned **signals** vs.
which become **worker judgment**? Every gate must land on one side.

**Recommendation (to walk):**
- **stub → pure signal, no worker judgment.** It is syntactic; there is nothing to judge. A stub
  block routes straight to `await-user` (story needs editing) without consulting the worker.
- **schema → worker judgment.** Detection (is `schema_introduces` set? is an exception phrase
  present? does a mgmt story exist?) is the signal; *whether the exception is legitimate / the
  mgmt-surface obligation is genuinely met* is the worker's verdict.
- **auth → worker judgment.** Detection (is `auth_gated` set? is a classification line present?) is
  the signal; *whether the auth model is correctly classified for this story* is the verdict.
- **scope → advisory `meta.warning`, not a verdict** (unchanged from HARNESS001 DP2). The worker
  may *read* scope facts as context but does not block on them.
- **context → advisory `meta.warning`** (unchanged). Not the worker's concern.

So the worker judges **schema + auth**; **stub** stays mechanical; **scope/context** stay advisory.

**Decision:** ✅ AGREED (2026-06-28).

1. **Boundary table adopted as proposed:** stub → pure signal, no worker (routes straight to
   `await-user`); schema → worker judgment; auth → worker judgment; scope → advisory
   `meta.warning`; context → advisory `meta.warning`.
2. **Spawn-on-trip (not always-spawn).** The worker is consulted **only when a judged gate
   (schema/auth) signal trips.** It can then **downgrade** a block to `clean` (the era's "raise the
   LLM's role" — clearing a spurious/legitimately-excepted block) or **confirm** it with a richer
   `block:<reason>`. It is **not** asked to catch false-negatives (a clean signal that should have
   blocked) — that would cost a worker spawn every cycle and re-derive the gate's detection logic;
   false-negative detection stays a review-stage concern, out of HARNESS002 scope. This keeps the
   safe-clear seam cheap and binds DP4's "emit `spawn-gate-worker` only when a judged gate trips."

---

### DP3 — The gate worker's return grammar *(first instance of era open thread #3)*

**Question:** What scalar does the worker return, and how does the resolver route each value?

**Recommendation (to walk):** the era-doc grammar `clean | block:<reason> | flag:<reason>`:
- `clean` → resolver proceeds (the deterministic signal may have tripped, but the worker judged the
  block spurious / the obligation met) → emit the normal `spawn-builder`.
- `block:<reason>` → `await-user` with `reason="gate-blocked:<which>"` carrying the **worker's**
  reason (richer than today's CLI text).
- `flag:<reason>` → proceed, but attach `meta.warnings[]` (a concern noted, not a stop).

Pin the grammar with a fixture + round-trip test, exactly as DP1 of HARNESS001 pinned the action
grammar. This is the *first* leaf-worker return contract; HARNESS003 generalizes it across all
workers, so it must be designed to extend (shared `<verb>:<reason>` shape).

**Decision:** ✅ AGREED (2026-06-28).

1. **Per-gate verdict map, not a single scalar.** Because one worker (DP1) can face both auth and
   schema tripped at once (DP2), the return is a map over the *tripped* gates, each value using the
   `clean | block:<reason> | flag:<reason>` grammar — e.g.
   `{"auth": "clean", "schema": "block:introduces sessions table, no mgmt UI story in phase"}`.
2. **Resolver aggregation rule:** any `block` → `await-user` with `reason="gate-blocked:<gate(s)>"`
   carrying the worker's reason(s); else any `flag` → proceed + `meta.warnings[]`; else all `clean`
   → proceed (`spawn-builder`).
3. **Keep `flag`.** It covers "resolvable but I'm uneasy — proceed with a recorded concern" and maps
   to the existing `meta.warnings[]` channel; it is the right forward design for the generalized
   HARNESS003 contract. Low cost.
4. **`<reason>` is a freeform human string,** consistent with existing `reason`/`blocked_reason`
   fields, carried verbatim to `await-user` / `meta.warnings`. No structured sub-schema now.
5. Pinned with a fixture + round-trip test (parallel to HARNESS001 DP1). The shared `<verb>:<reason>`
   shape is what HARNESS003 generalizes across all leaf workers.

---

### DP4 — The new resolver action + verdict routing *(the RESOLVER touch)*

**Question:** How does the worker enter the loop and the verdict re-enter the resolver? Does
`next_action.py` gain a new action?

**Recommendation (to walk):**
- Add `spawn-gate-worker` to the open action enum (DP1 of HARNESS001 designed it open-ended).
- **When emitted:** at the cycle-boundary seam, *before* `spawn-builder`, when any judged gate
  (schema/auth) has a tripped signal. If no gate signal trips, no worker spawn — go straight to
  `spawn-builder` (don't pay for a worker when there's nothing to judge). `scalar` = story ID.
- **Verdict re-entry** parallels HARNESS001 DP3: the worker→verdict→route micro-sequence has **no
  durable inter-step seam**, so it stays **orchestrator-held** within the turn; the resolver
  re-engages at the next durable seam. The resolver does **not** persist private "worker ran" state
  (DP7 of HARNESS001 holds — pure-read).
- **Safe-clear seam + hooks:** the `spawn-gate-worker` action is the point where `pre_tool_use` /
  `post_tool_use` budget hooks fire before any mutation; document this as the seam contract.

**Decision:** ✅ AGREED (2026-06-28).

1. **New action `spawn-gate-worker`** added to the open enum; `scalar` = story ID.
2. **Row 4 splits by the DP2 boundary:** **stub** trips → `await-user:gate-blocked:stub` directly
   (mechanical, as today); **schema/auth** trips → `spawn-gate-worker`, and `await-user:gate-blocked`
   fires only *after* the worker returns `block` (DP3 aggregation); no judged gate trips →
   `spawn-builder`.
3. **Verdict re-entry stays orchestrator-held within the turn; the resolver stays pure-read** (no
   durable "worker ran" marker — DP7 of HARNESS001 holds). Safe because **re-running the gate worker
   is idempotent**: inputs are durable and unchanged (story frontmatter, diff at HEAD), so across a
   `/clear` the resolver re-emits `spawn-gate-worker`, the cold worker re-judges identical inputs and
   reaches the same verdict — re-paying one spawn, persisting nothing.
4. **Recorded caveat:** LLM judgment is not *guaranteed* stable across re-judges, but the direction
   is bounded-safe — `clean → block` on re-judge just stops for the user; `block → clean` re-clears a
   block the user would have seen anyway. Acceptable for pre-flight; not a blocker.
5. **Safe-clear seam:** `spawn-gate-worker` *is* the seam where `pre_tool_use`/`post_tool_use` budget
   hooks fire before any mutation — documented as the seam contract; **no change to the hooks**
   themselves (protected).

---

### DP5 — Leaf-worker scaffold: gate-only now, or generic?

**Question:** HARNESS002 is the first worker conversion. Do we build a *generic* leaf-worker
scaffold now, or a gate-worker-specific one that HARNESS003 generalizes?

**Recommendation (to walk):** build the gate worker as a **bespoke agent-shell + plugin procedure
skill**, and *document* the reusable shape (shell loads procedure from a plugin-versioned skill;
disposable context; returns a `<verb>:<reason>` scalar) as a convention — but **do not
pre-generalize** before HARNESS003 has three more workers (builder/reviewer/loop-breaker) to
generalize *from*. Premature abstraction with one instance is the wrong bet. Procedure lives in a
new plugin skill (location to settle: under `skills/pairmode/` per the era's "plugin-versioned
skill" decision), not per-project agent prose — which also dodges the `sync-agents` drift problem.

**Decision:** ✅ AGREED (2026-06-28).

1. **(a) Gate-only, no generic framework.** Build *this* worker concretely; do not abstract a
   reusable multi-worker leaf framework before HARNESS003 has three more workers
   (builder/reviewer/loop-breaker) to generalize *from*.
2. **(b) Plugin-versioned procedure skill + thin agent shell** (NOT the status-quo per-project
   rendered `agents/gate.md`). The gate-judgment procedure lives **once, in a plugin-versioned
   skill**, with a minimal agent shell that loads it ("load the gate procedure, evaluate the signals
   for this story, return the verdict map"). This is the era's worker shape — and it deliberately
   avoids recreating the `sync-agents` drift problem that per-project rendered prose would reintroduce.
   HARNESS002 pioneers the shape for one worker; HARNESS003 generalizes it.
3. **Exact path is a story-level detail** (e.g. a procedure skill under the `pairmode` family vs. a
   standalone `skills/gate-worker/`); the binding decision is only "procedure in a plugin-versioned
   skill, thin shell, not per-project rendered prose."

---

### DP6 — Additive contract & CLI-freeze compliance

**Question:** Does the gate worker need any **new** `flex_build.py` command, or does it reuse the
three existing `check-*` CLIs as signal sources?

**Recommendation (to walk):** **no new gate-check CLI, no `check-*` signature change.** The worker
calls the existing `check-stub` / `check-schema-gate` / `check-auth-gate` as signal providers; the
verdict is the worker's text return, parsed by a small resolver-side helper. If a parse/validation
helper warrants a CLI surface at all, it must be a pure *addition* (freeze test stays green —
removals/renames forbidden). Confirm the freeze fixture is unaffected.

**Decision:** ✅ AGREED (2026-06-28).

1. **No new gate-check CLI; no `check-*` signature change.** The three
   `check-stub`/`check-schema-gate`/`check-auth-gate` commands stay exactly as they are, reused as
   signal providers. Freeze fixture unaffected (additions allowed, removals/renames forbidden).
2. **Verdict parse helper is a module-level function** (text return → DP3 per-gate map), in
   `next_action.py` or a sibling module — **not** a new CLI. If a story finds it genuinely needs a
   CLI surface in the advisory window, it is added as a pure *addition* (freeze stays green).
   Default: no new command.
3. **Worker self-checks.** The gate worker re-runs the `check-*` CLIs itself in its disposable
   context and judges the results — self-contained, matches DP1.3 ("reads only its own signal
   inputs + the single story"), and keeps the spawn `scalar` = story ID only. The checks run twice
   total (resolver's `infer_position` to decide *whether* to spawn; the worker to *judge*); they are
   cheap, deterministic, idempotent reads, so double-execution is harmless.

---

### DP7 — Scope fence (in/out) + CF-1 placement

**Question:** What is explicitly in vs. out of HARNESS002, and where does CF-1 (CER-060) land?

**Recommendation (to walk):**
- **In:** the gate worker (agent shell + procedure skill); the DP3 verdict grammar + fixture; the
  DP4 `spawn-gate-worker` action + verdict routing in `next_action.py`; full isolation tests;
  advisory-only (NOT wired into the live `CLAUDE.build.md`).
- **Out (later phases):** builder/reviewer/loop-breaker conversion + the generalized return
  contract (HARNESS003); checkpoint-step decomposition (HARNESS004); spec-writer (HARNESS005); the
  flip (HARNESS006); observability (Phase G).
- **CF-1 (CER-060):** because HARNESS002 already opens `next_action.py` for the DP4 action,
  CF-1 is **naturally co-located** → bundle the **preferred fix** (read-model computes
  `builder_model` at the next attempt on FAIL) as one story here, rather than promoting it to a
  standalone phase. Confirm at walk time.

**Decision:** ✅ AGREED (2026-06-28).

1. **Scope fence adopted as stated.** **In:** the gate worker (thin shell + plugin procedure skill,
   DP5); the DP3 verdict grammar + fixture; the DP4 `spawn-gate-worker` action + Row-4 split +
   verdict routing in `next_action.py`; the DP6 parse helper; full isolation tests (DP8);
   advisory-only (NOT wired into the live `CLAUDE.build.md`). **Out:** builder/reviewer/loop-breaker
   conversion + generalized return contract (HARNESS003); checkpoint decomposition (HARNESS004);
   spec-writer (HARNESS005); the flip (HARNESS006); observability (Phase G).
2. **CF-1 → option 1 (preferred fix), bundled as one story in HARNESS002.** On inferred FAIL,
   `infer_position` computes the Position's `builder_model` at the *next* attempt
   (`attempt_count + 1`) so Row 5 emits `position.builder_model` and the selector is the single
   source of the retry tier (true DP5 composition). **Acceptance must verify no other row regresses**
   — Row 2 (first attempt) must still resolve the attempt-1 model. Closes CER-060.

---

### DP8 — Isolation testing (incl. how to unit-test an LLM worker)

**Question:** "Fully unit-tested in isolation" — but the worker's verdict is LLM judgment. What is
the deterministic test model?

**Recommendation (to walk):** test the **deterministic scaffold**, not the LLM's judgment quality:
- **Signal collection** — synthetic story fixtures (auth-gated w/ & w/o classification; schema w/ &
  w/o mgmt story / exception; stub; clean) → assert the `{ok, blocked_reason}` signal set the
  worker is handed.
- **Verdict parsing + resolver routing** — feed each grammar value (`clean` / `block:<r>` /
  `flag:<r>`) as an **injected** verdict and assert the routed action (DP3 table). No live model
  call — tests must not hit the API.
- **Grammar round-trip** (DP3 fixture) and the **"reads only its signal inputs + the single story"**
  guard (DP1.3) — assert the worker's input set excludes accumulated loop state.
- The LLM's *judgment quality* is validated by the worker's prompt + manual review, not unit tests;
  state this explicitly so the gap is deliberate, not silent. Backs review-checklist items 6 + 10.

**Decision:** ✅ AGREED (2026-06-28).

1. **Deterministic-scaffold test model** (the worker's verdict is LLM judgment → not unit-asserted;
   no live API call in the suite): **signal collection** (synthetic story fixtures → asserted
   `{ok, blocked_reason}` set + spawn-vs-not per DP2); **verdict parsing + resolver routing**
   (inject each grammar value / per-gate map → assert the routed action per DP3/DP4 aggregation);
   **grammar round-trip** (DP3 fixture); **DP1.3 input-bound guard** (assert the worker's input set
   excludes accumulated loop state — the "context can't become a liability" property as a test);
   **CF-1 regression** (Row 5 = `select_builder_model(...,attempt_number=2)`, Row 2 stays attempt-1).
2. **The LLM-judgment gap is stated explicitly** (deliberate, not silent): judgment quality is
   validated by the worker's prompt + manual review. **Optional, non-gating golden eval fixtures**
   (story+signals → expected verdict) may be seeded for manual validation; they do **not** gate the
   build. Backs review-checklist items 6 + 10.

---

## Resulting story outline (WORKER rail + RESOLVER touch — finalized)

All 8 DPs ✅ AGREED. Stories land on the `harness` branch in `/mnt/work/flex-harness` (DP1),
**advisory-only** — none wires the gate worker into the live `CLAUDE.build.md` (DP7). Built by
flex's own 0.2.x loop. Sequenced so each story's tests pass before the next. The CLI-surface freeze
test (RELEASE-003) must stay green throughout (DP6). Story IDs are provisional — exact numbers are
assigned at `story_new.py` time.

| Story (provisional ID) | Title | Rail | Acceptance gist |
|------------------------|-------|------|-----------------|
| WORKER-001 | Gate verdict grammar + fixture (DP3) | WORKER | Per-gate verdict map; per-value grammar `clean \| block:<reason> \| flag:<reason>`; freeform `<reason>`; JSON fixture + round-trip test. No worker, no CLI wiring yet. |
| RESOLVER-005 | `spawn-gate-worker` action + Row-4 split + verdict routing (DP4, DP6) | RESOLVER | Add `spawn-gate-worker` to the open enum; split Row 4 (stub→`await-user:gate-blocked:stub`; schema/auth→`spawn-gate-worker`; none→`spawn-builder`); module-level parse helper (text→DP3 map); aggregation routing (block→await-user, flag→`meta.warnings[]`, clean→proceed). Pure-read; tested with **injected** verdicts. No `check-*` signature change. |
| WORKER-002 | Gate worker — thin shell + plugin procedure skill (DP1, DP2, DP5, DP6) | WORKER | Thin agent shell + plugin-versioned procedure skill (not per-project rendered prose); worker self-checks via the existing `check-*` CLIs; judges **schema + auth**, returns the verdict map; stub stays mechanical; scope/context advisory; reads only its signal inputs + the single story (DP1.3). |
| RESOLVER-006 | CF-1 / CER-060 — retry-path model composition fix (DP7) | RESOLVER | On inferred FAIL, `infer_position` computes `builder_model` at `attempt_count + 1` so Row 5 emits `position.builder_model` (selector = single source of the retry tier). **Verify Row 2 stays attempt-1.** Closes CER-060. |
| WORKER-003 | Isolation test suite (DP8) | WORKER | Exhaustive deterministic matrix: signal-collection fixtures, injected-verdict routing, grammar round-trip, DP1.3 input-bound guard, CF-1 regression. LLM-judgment gap documented; optional non-gating golden eval fixtures. Backs review-checklist items 6 + 10. |

**Build order:** WORKER-001 (grammar) → RESOLVER-005 (resolver wiring, tested with injected
verdicts) → WORKER-002 (gate worker) → RESOLVER-006 (CF-1) → WORKER-003 (isolation suite).
RESOLVER-005 and WORKER-002 are close-coupled via the grammar but separable (injected verdicts let
the resolver wiring be built and tested before the real worker exists); if either proves thin they
may merge at spec time.

**Schema delivery:** HARNESS002 introduces **no new persistent schema objects** — the gate worker
is stateless (reads existing durable state, persists nothing; DP1.3 / DP4). The schema-delivery
table is N/A for this phase.

---

## Open threads (rolled into DPs above)

- Signal → verdict boundary → **DP2**.
- Whether gate-verdict extraction changes any `flex_build.py` gate-command signature → **DP6**
  (recommendation: no — additive, freeze-green).

## Status

✅ SETTLED — DP1–DP8 all ✅ AGREED; story outline finalized. **Ready for**
`phase_new.py --phase-id HARNESS002 --suffix main` and `story_new.py` on the WORKER rail
(WORKER-001 … WORKER-003) + RESOLVER rail (RESOLVER-005, RESOLVER-006), built on the `harness`
branch in `/mnt/work/flex-harness`. The phase spec is the next step; this agreements doc is its
input. CF-1 (CER-060) is bundled as RESOLVER-006 and closes on its build.
