---
id: WORKER-002
rail: WORKER
title: Gate worker — thin shell + plugin procedure skill (DP1, DP2, DP5, DP6)
status: complete
phase: "HARNESS002-main"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/templates/agents/gate-worker.md.j2
  - skills/pairmode/gate_worker/SKILL.md
  - tests/pairmode/test_gate_worker.py
touches:
  - skills/pairmode/scripts/gate_verdict.py
---

## Context

The WORKER deliverable of HARNESS002 (agreements `HARNESS002-main.md` DP1 + DP2
+ DP5 + DP6): the era's **first leaf-worker conversion**. A cold, disposable
**single gate worker** is inserted between the deterministic gate signals and
the resolver's routing. The `check-*` CLIs stay signal providers; the worker
renders the **schema + auth** verdict; the resolver (RESOLVER-005) routes on it
but never computes it.

Per DP5 the worker is built as a **thin agent shell + a plugin-versioned
procedure skill**, NOT a per-project rendered `agents/gate.md`. The
gate-judgment procedure lives **once, in a plugin-versioned skill**; the agent
shell is minimal ("load the gate procedure, evaluate the signals for this story,
return the verdict map"). This is the era's worker shape and it deliberately
avoids the `sync-agents` drift problem that per-project rendered prose
reintroduces. HARNESS002 pioneers the shape for one worker; HARNESS003
generalizes it — so build it **gate-only, no generic multi-worker framework**
(DP5.1).

DP2 boundary the worker honours: it judges **schema + auth**; **stub** stays
mechanical (the worker is never consulted for stub); **scope/context** are read
as advisory context only, never blocked on. DP2.2 spawn-on-trip: the worker is
consulted only when a judged gate signal trips, and may **downgrade** a block to
`clean` (clearing a spurious / legitimately-excepted block) or **confirm** it
with a richer `block:<reason>`; it is **not** asked to catch false-negatives.

DP1.3 binding input-bound property: the worker loads only (a) the three
`check-*` signal outputs, (b) the one story file under evaluation, and (c) the
relevant diff/frontmatter — and **never inherits accumulated orchestrator/loop
state**. "Reads only its signal inputs + the single story" is binding and is a
WORKER-003 test target.

DP6.3: the worker **self-checks** — it re-runs the existing
`check-stub`/`check-schema-gate`/`check-auth-gate` CLIs itself in its disposable
context and judges the results (no new CLI, no `check-*` signature change). The
checks run twice total (the resolver's `infer_position` to decide *whether* to
spawn; the worker to *judge*) — cheap, deterministic, idempotent reads, so
double-execution is harmless.

## Requires

- WORKER-001 complete: the verdict grammar and `gate_verdict.py` — the worker's
  return must conform to the per-gate verdict-map contract.
- RESOLVER-005 complete: the `spawn-gate-worker` action exists, so the worker has
  a defined entry/exit in the loop and the verdict has a documented consumer
  (the aggregation helper). The worker is built/tested against that contract,
  even though wiring into the live loop is deferred (HARNESS006).

## Ensures

- A **plugin-versioned procedure skill** for the gate worker exists under the
  `pairmode` family (e.g. `skills/pairmode/gate_worker/SKILL.md`). It is the
  single source of the gate-judgment procedure: given the three `check-*` signal
  outputs + the one story file + the relevant diff/frontmatter, judge
  **schema + auth** and return the WORKER-001 per-gate verdict map. (Exact path
  is a story-level detail per DP5.3; the binding decision is "procedure in a
  plugin-versioned skill, thin shell, not per-project rendered prose.")
- A **thin agent shell** template (e.g.
  `skills/pairmode/templates/agents/gate-worker.md.j2`) that loads the procedure
  skill and carries no domain logic of its own — its body is "load the gate
  procedure, evaluate the signals for this story (`scalar` = story ID), return
  the verdict map." It is markedly thinner than the existing builder/reviewer
  agent templates.
- The procedure instructs the worker to **self-check**: re-run
  `check-stub` / `check-schema-gate` / `check-auth-gate` itself, judge **only**
  schema + auth, treat **stub** as mechanical (not its concern), and read
  scope/context **only** as advisory context (never block on them).
- The procedure encodes the DP2.2 judgment direction: downgrade a spurious /
  legitimately-excepted block to `clean`; confirm a genuine block with a richer
  `block:<reason>`; use `flag:<reason>` for "resolvable but uneasy"; do **not**
  attempt false-negative detection.
- The procedure encodes the DP1.3 input-bound property explicitly: the worker
  reads **only** its signal inputs + the single story under evaluation + the
  relevant diff/frontmatter, and must not request or rely on accumulated
  orchestrator/loop/phase-history state.
- The worker's return conforms to the WORKER-001 grammar
  (`clean | block:<reason> | flag:<reason>` per tripped judged gate); the return
  validates against `gate_verdict.py`.
- `tests/pairmode/test_gate_worker.py` asserts the **scaffold** deterministically
  (no live API call — DP8): the procedure skill and agent shell exist at their
  declared paths; the shell is thin (delegates to the skill, contains no
  gate-detection logic of its own — e.g. no inline `schema_introduces`/
  `auth_gated` parsing); the procedure text names the three `check-*` CLIs, the
  schema+auth-only judgment scope, the stub-is-mechanical exclusion, the DP2.2
  downgrade/confirm direction, the no-false-negative caveat, and the DP1.3
  input-bound constraint; and any example verdict the procedure embeds validates
  against `gate_verdict.py`.
- The worker is **advisory-only**: it is **not** referenced from the live
  `CLAUDE.build.md` (that flip is HARNESS006). `grep` confirms `CLAUDE.build.md`
  is unchanged by this story.
- `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q` passes.

## Instructions

- Keep the shell genuinely thin — if it grows gate logic, that logic belongs in
  the procedure skill. The whole point of DP5.2 is one versioned procedure, not
  rendered-per-project prose. Do **not** wire this template into `sync-agents`'
  rendered set in a way that creates a live `.claude/agents/` artifact for the
  flip; the flip is HARNESS006.
- The procedure is prose-with-structure (the worker is an LLM). Its testable
  surface is the **presence and shape** of the required instructions, not the
  LLM's judgment quality — DP8.2 states the judgment gap is validated by the
  prompt + manual review, not unit tests. Make that gap explicit in the test
  module docstring.
- The worker's verdict must round-trip through `gate_verdict.py`; embed at least
  one concrete example verdict map in the procedure and assert it validates.
- Do **not** add any new `flex_build.py` CLI or change a `check-*` signature
  (DP6) — the worker calls the existing commands as-is.
- Respect rail ownership: the resolver action/routing is RESOLVER-005's; this
  story only *imports/validates against* `gate_verdict.py` (declared in
  `touches`) and does not modify `next_action.py`.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_gate_worker.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```

Acceptance: scaffold-presence + thin-shell + procedure-content assertions green;
embedded example verdict validates; `CLAUDE.build.md` unchanged; full suite
green. No live API call in the suite.

### Out of scope

- The verdict grammar/fixture — WORKER-001.
- The `spawn-gate-worker` action and resolver-side routing/aggregation —
  RESOLVER-005.
- The CF-1/CER-060 retry-path fix — RESOLVER-006.
- The exhaustive isolation/regression matrix (DP8) — WORKER-003.
- Asserting LLM judgment quality (deliberate gap — DP8.2: prompt + manual
  review; optional non-gating golden evals may be seeded in WORKER-003).
- Wiring the worker into the live `CLAUDE.build.md` loop (the flip — HARNESS006).
- A generic multi-worker leaf framework (DP5.1 — gate-only now; HARNESS003
  generalizes).
