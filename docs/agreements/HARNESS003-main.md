# Agreements — HARNESS003-main · Builder/reviewer/loop-breaker/security-auditor/intent-reviewer as leaf workers

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS002-main` (gate verdict extraction complete, tagged `cp-HARNESS002-main`) —
left behind the gate worker scaffold (thin agent shell + plugin procedure skill), the generalized
`clean|block:<reason>|flag:<reason>` return grammar, the `spawn-gate-worker` resolver action with
Row-4 split, and the full isolation suite. Advisory-only; still not wired into the live `CLAUDE.build.md`.
**Phase key:** `HARNESS003-main` · **Rail:** WORKER
**Builds on:** `harness` branch, in `/mnt/work/flex-harness` (DP1 of HARNESS001-ante1). Breaking/refactor
code does **not** land on `main`.
**Status:** ✅ SETTLED — all 7 DPs AGREED; story outline finalized (2026-06-29).

> An *agreements doc* records the decisions for a phase before any story is specced. We walk each
> decision point (DP) top to bottom; once a DP is settled its **Decision** line moves from ⬜ OPEN
> to ✅ AGREED and becomes binding on the story specs.

## Why this phase exists

HARNESS002 established the leaf-worker shape for exactly one worker — the gate worker. The remaining
five workers (builder, reviewer, loop-breaker, security-auditor, intent-reviewer) still live as
per-project rendered `.claude/agents/*.md` files: prose that `sync-agents` stamps into each project on
every sync. This is the `sync-agents` drift problem the era's worker shape was designed to eliminate.

HARNESS003 converts all five remaining workers to the same pattern: thin agent shell + plugin procedure
skill (not per-project rendered prose). It also generalizes the return grammar beyond the gate-verdict
per-gate map — each worker type needs a typed return contract so the resolver can route deterministically
on every worker's output without inspecting prose.

Like HARNESS002, everything here is **advisory-until-flip**: built and isolation-tested but **not**
wired into the live `CLAUDE.build.md` until HARNESS006. The additive contract and CLI-surface freeze
test keep the fleet green throughout.

## Context (established facts)

- **Existing workers (`.claude/agents/`):** `builder.md`, `reviewer.md`, `loop-breaker.md`,
  `security-auditor.md`, `intent-reviewer.md`, `reconstruction-agent.md`. These are rendered from
  `skills/pairmode/templates/agents/*.md.j2` via `sync-agents`. The `reconstruction-agent` is out of
  scope for this phase (it is not part of the build loop).
- **Existing ACTIONS in `next_action.py`:**
  `spawn-builder`, `spawn-loop-breaker`, `spawn-gate-worker`, `checkpoint`, `await-user`, `done`.
  `spawn-builder` and `spawn-loop-breaker` already exist in the grammar (HARNESS001-main RESOLVER-001);
  they are not yet wired to the leaf-worker pattern — they were defined in anticipation.
- **`_SPAWN_ACTIONS`** carries `spawn-builder` and `spawn-loop-breaker` (model may be non-null for these).
  `spawn-gate-worker` is deliberately excluded (gate worker tier is not a builder-model decision).
- **Gate verdict grammar** (`gate_verdict.py`): the per-gate `clean|block:<reason>|flag:<reason>` shape
  is gate-specific. The generalized return contract across all workers is the DP3 deliverable.
- **Procedure location precedent (HARNESS002 DP5):** gate-worker procedure lives in a plugin-versioned
  skill under `skills/pairmode/`. The same location pattern applies here.
- **No resolver changes needed for `spawn-builder` / `spawn-loop-breaker`**: the action names already
  exist. What changes is that the orchestrator stops reading the rendered per-project prose and starts
  spawning the plugin-versioned leaf shell instead.
- **`spawn-reviewer`, `spawn-security-auditor`, `spawn-intent-reviewer`**: these actions do NOT yet
  exist in `ACTIONS`. They are HARNESS003 additions (DP4 below).

## Decision points

### DP1 — Which workers convert now, and the exclusion of `reconstruction-agent` *(settled)*

**Question:** Which of the six agents get converted in HARNESS003?

**Decision:** ✅ AGREED (2026-06-29).

1. **Convert all five build-loop workers:** builder, reviewer, loop-breaker, security-auditor,
   intent-reviewer. These are the workers the harness spawns during the build loop and checkpoint
   sequence; converting them all in one phase ensures every worker the flip depends on exists before
   HARNESS006.
2. **Exclude `reconstruction-agent`.** It is not part of the build loop (it runs as an ad-hoc
   investigation tool, not spawned by the resolver). Out of scope for Era 003.
3. **Advisory-only.** The new procedure skills are built and tested but the per-project rendered
   `.claude/agents/*.md` files are NOT removed until HARNESS006's dogfood flip. Both exist during the
   transition window; the harness still reads the rendered files until the flip.

---

### DP2 — The builder/reviewer micro-sequence *(settled)*

**Question:** Today the orchestrator runs builder → spawn reviewer → handle result as a single
orchestrator-held sequence (no intermediate durable state). Does this change?

**Decision:** ✅ AGREED (2026-06-29).

1. **The builder/reviewer micro-sequence stays orchestrator-held.** The resolver emits `spawn-builder`;
   the orchestrator spawns the builder leaf, waits for `BUILD-RESULT`, then independently decides
   whether to spawn the reviewer. This is a within-turn micro-sequence, not two separate resolver
   decisions. It is re-derivable (the builder's result is in `effort.db` / `attempt` state); no new
   intermediate durable state is introduced.
2. **No new `spawn-reviewer` action in the resolver state machine.** `spawn-reviewer` is added to
   `ACTIONS` (and `_SPAWN_ACTIONS`) so the action grammar is complete, but the resolver does not
   emit it as an independent top-level routing step — it is orchestrator-dispatched within the
   `spawn-builder` turn. This keeps the resolver state machine minimal.
3. **The loop-breaker is emitted directly by the resolver** (already in `_SPAWN_ACTIONS`). Row 6 of
   `resolve_next_action` emits `spawn-loop-breaker`; the loop-breaker result feeds back to the
   orchestrator within the same turn.

---

### DP3 — Generalized worker return contract *(settled)*

**Question:** Each worker currently returns prose. What is the typed return contract that makes
routing deterministic?

**Decision:** ✅ AGREED (2026-06-29).

1. **`worker_result.py`** — a new shared module (alongside `gate_verdict.py`) defines the generalized
   return grammar. Each worker type has a named result type:
   - `BUILD-RESULT` — builder outcome: `{type: "BUILD-RESULT", outcome: "PASS"|"FAIL", story_id: str, reason: str}`
   - `REVIEW-RESULT` — reviewer/security-auditor/intent-reviewer outcome: `{type: "REVIEW-RESULT", verdict: "PASS"|"FAIL", findings: [str], reason: str}`
   - `ADVICE` — loop-breaker output: `{type: "ADVICE", approach: str, rationale: str}`
   - `SPEC-RESULT` — spec-writer (HARNESS005): `{type: "SPEC-RESULT", story_id: str, status: "done"|"revised"}`
   The gate verdict per-gate map (`gate_verdict.py`) is a parallel contract, not folded into this module.
2. **Each worker's thin shell** outputs the result as JSON on stdout (matching the declared type). The
   orchestrator parses it with the `worker_result.py` parser; routing is deterministic.
3. **A JSON fixture** (`worker_result_grammar.json`) pins the schema for each type with valid and
   invalid examples. A round-trip test asserts parse → serialize → parse is stable.
4. **The gate verdict grammar remains in `gate_verdict.py`** (not merged into `worker_result.py`) —
   the gate verdict is structurally different (per-gate map) and already has its own test coverage.

---

### DP4 — New resolver actions *(settled)*

**Question:** Which new actions join `ACTIONS`, and which are `_SPAWN_ACTIONS`?

**Decision:** ✅ AGREED (2026-06-29).

1. **New actions added to `ACTIONS`:**
   - `spawn-reviewer` — orchestrator-dispatched within the `spawn-builder` turn (DP2), but the name
     is registered so action grammar is complete and the freeze test can pin it.
   - `spawn-security-auditor` — emitted by the resolver for the checkpoint security step (HARNESS004);
     added here so the action vocabulary is stable before HARNESS004.
   - `spawn-intent-reviewer` — same rationale.
2. **`_SPAWN_ACTIONS` additions:** `spawn-reviewer`, `spawn-security-auditor`, `spawn-intent-reviewer`
   carry builder-model selection (the tier may differ per checkpoint context), so they join
   `_SPAWN_ACTIONS`.
3. **`SCHEMA_VERSION` bumped to 2** when these actions are added (the schema version signals action
   grammar changes to consumers). Managed in WORKER-004's `next_action.py` touch.
4. **No change to existing routing logic.** Adding to `ACTIONS` is additive; no existing row in
   `resolve_next_action` changes. The freeze test must stay green (additions allowed).

---

### DP5 — Procedure skill location *(settled)*

**Question:** Where do the new procedure skills live?

**Decision:** ✅ AGREED (2026-06-29).

1. **Location:** `skills/pairmode/skills/<worker>/procedure.md` (e.g.
   `skills/pairmode/skills/builder/procedure.md`, `skills/pairmode/skills/reviewer/procedure.md`).
   This mirrors the gate worker location established in HARNESS002.
2. **Thin agent shell:** each worker's shell is a minimal agent instruction that loads its procedure
   from the plugin skill (`read skills/pairmode/skills/<worker>/procedure.md; follow it for this task;
   return the result as JSON matching the worker_result grammar`). No business logic in the shell.
3. **Template source:** the procedure content is extracted from the current `CLAUDE.md`
   (review checklist), `CLAUDE.build.md` (builder/loop-breaker steps), and the existing agent
   `.md.j2` templates. The `.j2` templates are NOT removed this phase (HARNESS006 does that).

---

### DP6 — Isolation testing approach *(settled)*

**Question:** How do we test workers whose output is LLM judgment?

**Decision:** ✅ AGREED (2026-06-29).

1. **Same model as HARNESS002 DP8:** test the deterministic scaffold, not judgment quality.
   - **Return contract:** parse each `BUILD-RESULT`/`REVIEW-RESULT`/`ADVICE` grammar value (injected)
     and assert the orchestrator's routing decision is deterministic.
   - **Shell structure:** assert each worker shell loads only its bounded input set (the procedure
     skill + the task context — no accumulated loop state).
   - **Grammar round-trip:** the `worker_result_grammar.json` fixture round-trips.
   - **No live API calls** in any test. The LLM judgment gap is documented explicitly.
2. **WORKER-010 consolidates** all five worker conversion tests into one isolation suite (parallel
   to WORKER-003 for the gate worker).

---

### DP7 — Scope fence *(settled)*

**Question:** What is explicitly in/out of HARNESS003?

**Decision:** ✅ AGREED (2026-06-29).

**In:** `worker_result.py` + fixture; five worker procedure skills + thin shells; new ACTIONS entries
(`spawn-reviewer`, `spawn-security-auditor`, `spawn-intent-reviewer`); `SCHEMA_VERSION` bump; full
isolation suite (WORKER-010). Advisory-only; no per-project agent file removal.

**Out:** Checkpoint decomposition into resolver-emitted actions (HARNESS004); spec-writer
conversion (HARNESS005); the flip (HARNESS006); per-project `.claude/agents/*.md` file removal
(HARNESS006 dogfood flip); `reconstruction-agent` conversion (out of era scope).

---

## Resulting story outline (WORKER rail — finalized)

All 7 DPs ✅ AGREED. Stories land on the `harness` branch (DP1 of HARNESS001-ante1),
**advisory-only** — none wires the new workers into the live `CLAUDE.build.md` (HARNESS006).
Sequenced so each story's tests pass before the next.

| Story ID | Title | Rail | Acceptance gist |
|----------|-------|------|-----------------|
| WORKER-004 | Generalized worker return contract (`worker_result.py` + grammar fixture) | WORKER | `worker_result.py` module; four result types with JSON schema; fixture + round-trip test; new ACTIONS entries + `SCHEMA_VERSION` bump. |
| WORKER-005 | Builder leaf worker — thin shell + plugin procedure skill | WORKER | Procedure extracted from `CLAUDE.build.md` prose into `skills/pairmode/skills/builder/procedure.md`; thin shell; returns `BUILD-RESULT`; injected-result routing tests; no live API call. |
| WORKER-006 | Reviewer leaf worker | WORKER | Review checklist extracted into `skills/pairmode/skills/reviewer/procedure.md`; thin shell; returns `REVIEW-RESULT`; injected-result routing tests. |
| WORKER-007 | Loop-breaker leaf worker | WORKER | Loop-breaker procedure in `skills/pairmode/skills/loop-breaker/procedure.md`; thin shell; returns `ADVICE`; isolation tested. |
| WORKER-008 | Security-auditor leaf worker | WORKER | Security checklist in `skills/pairmode/skills/security-auditor/procedure.md`; thin shell; returns `REVIEW-RESULT`; isolation tested. |
| WORKER-009 | Intent-reviewer leaf worker | WORKER | Intent-reviewer procedure in `skills/pairmode/skills/intent-reviewer/procedure.md`; thin shell; returns `REVIEW-RESULT`; isolation tested. |
| WORKER-010 | HARNESS003 isolation suite | WORKER | Full deterministic matrix: return-contract round-trip; shell input-bound guard for all five workers; injected-result routing for all result types; no live API call; LLM-judgment gap documented. |

**Build order:** WORKER-004 (contract) → WORKER-005 → WORKER-006 → WORKER-007 → WORKER-008 →
WORKER-009 (all conversions) → WORKER-010 (consolidated isolation suite).

**Schema delivery:** HARNESS003 introduces **no new persistent schema objects** — all workers are
stateless (read existing durable state, persist nothing). The schema-delivery table is N/A.

---

## Status

✅ SETTLED — DP1–DP7 all ✅ AGREED; story outline finalized. Ready for
`phase_new.py --phase-id HARNESS003 --suffix main` and `story_new.py` on the WORKER rail
(WORKER-004 … WORKER-010), built on the `harness` branch in `/mnt/work/flex-harness`.
