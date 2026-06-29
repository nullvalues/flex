# Agreements — HARNESS002-main · Gate verdict extraction (seed)

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS001-main` (resolver foundation complete, tagged `cp-HARNESS001-main`) —
left behind the advisory-only `flex_build.py next-action` resolver: the action grammar
(`make_action`/`validate_action`/`ACTIONS`), the pure-read `infer_position` read-model, and the
`resolve_next_action` 9-state DP2 machine, all isolation-tested. Still **not** wired into the live
`CLAUDE.build.md` (DP7); the additive contract + CLI-surface freeze test guard the fleet.
**Phase key:** `HARNESS002-main` · **Rail:** RESOLVER (provisional)
**Builds on:** `harness` branch, in `/mnt/work/flex-harness` (DP1). Breaking/refactor code does
**not** land on `main`.
**Status:** 🌱 SEED — NOT yet walked. No DPs settled, no stories specced. This file only carries
forward binding items inherited from HARNESS001-main so they cannot be lost when the phase is
walked. Per the era doc, walk this doc point-by-point (and resolve the items below) BEFORE running
`phase_new.py --phase-id HARNESS002 --suffix main`.

> An *agreements doc* records the decisions for a phase before any story is specced. A SEED doc is
> a pre-walk placeholder: it holds inherited obligations and open threads, not decisions. Settle
> them during the walk; only then do they become binding on the story specs.

## Scope (from the HARNESS001-main Goal, out-of-scope list)

HARNESS002 is **gate verdict extraction**: moving gate *judgment* (auth/schema/stub and the
broader pre-flight/review verdicts) out of inline LLM judgment and into the resolver/CLI surface.
HARNESS001-main deliberately read gates as **deterministic signals only** (blocked/ok) and routed
every verdict to `await-user` (DP2/DP4); HARNESS002 is where the verdict logic itself is extracted.

## Carry-forward obligations (inherited — must be addressed when walked)

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

**Required resolution (pick one during the walk):**
1. **Preferred — fix the read-model:** on inferred FAIL, have `infer_position` compute the
   Position's `builder_model` at the *next* attempt number (`attempt_count + 1`), so Row 5 emits
   `position.builder_model` and the selector remains the single source of the retry tier (true DP5
   composition). Verify no other row regresses (Row 2 first-attempt model must stay attempt-1).
2. **Minimum — pin it with a test:** add an assertion that Row 5's emitted model equals
   `select_builder_model(<code story>, attempt_number=2)[0]`, so a future selector-table change
   fails loudly here. (Leaves the two-places encoding but removes the silent-divergence risk.)

**Status:** ⬜ OPEN — to settle in the HARNESS002 walk. Tracked as **CER-060** (Do Later) in
`docs/cer/backlog.md`.

> Note: CF-1 is small and self-contained. If HARNESS002's scope makes it awkward to bundle, it may
> be promoted to its own one-story fix phase instead — decide at walk time, do not pull it into a
> build without a spec.

## Open threads (to populate when walked)

- Signal → verdict boundary: which verdicts move into the resolver vs. stay owner=user (DP4).
- Whether gate-verdict extraction changes any `flex_build.py` gate-command signature (must stay
  additive / freeze-test-green, per the Era 003 additive contract).
