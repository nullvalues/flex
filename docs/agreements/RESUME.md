# Resume point — Era 003 active, ready to build HARNESS001-ante1

**Written:** 2026-06-26 (step 6 / `era_transition` is done). Update or delete
once `HARNESS001-ante1` is created and its first story is in flight.

## One-line status

Era 002 is closed (`complete`, `closed_at: 2026-06-26`); **Era 003
(orchestrator-as-harness) is `active`**. The transition (close-out steps 1–6) is
complete and committed. Build gate green (2232 passed). The live era doc is
`docs/eras/003-flex-orchestrator-as-harness.md`; the proposal file was deleted.

## The next action (needs the user's go)

Build the era-wide preflight phase `HARNESS001-ante1` (RELEASE rail):

1. `phase_new.py --phase-id HARNESS001 --suffix ante1`
2. `story_new.py` for **RELEASE-001 … RELEASE-006** — story outline is finalized
   in `docs/agreements/HARNESS001-ante1.md` § "Resulting story outline".
   - RELEASE-001 = operator git work (worktree + `v0.2.0` tag); lands on `main`.
   - RELEASE-002 = the only harness-only story (version bump → `0.3.0-dev`);
     lands on `harness`.
   - RELEASE-003/004/005/006 = additive read-only tools + docs; land on `main`.
3. Spec each story before building (spec-before-build policy), then build.

## Read these first (in order)

1. `docs/eras/003-flex-orchestrator-as-harness.md` — the live era doc (settled
   architecture, rails, phase table; Phase G = HARNESS007-main absorbs the
   deferred Era 002 Phase 64 + D1/D2/D3 = CER-053/054/055).
2. `docs/agreements/HARNESS001-ante1.md` — settled DP1–DP8 + finalized
   RELEASE-001…006 story outline. This is the input to `phase_new.py`.
3. `docs/agreements/era-002-closeout.md` — historical close-out record.

## Working-tree / housekeeping notes

- `flex_eph/` (observability screenshot) is untracked — leave it.
- **Watch for the stray `flex_build.py` edit reappearing** (first-table `break`
  parser + first-non-complete `current-phase`). Settled decision is option (a) —
  revert, do not reintroduce. It came back once after the close-out and was
  reverted again on 2026-06-26; if it keeps returning, something is regenerating
  it. The committed HEAD version is the known-good state.
- Recurring guardrail (also in auto-memory): never estimate orchestrator context
  headroom from effort.db cost totals — see CER-053 / HARNESS001-ante1 DP7.
- The status-drift + stale-era-table mess from the close-out is the forcing
  function for the **HARNESS008 housekeeper**.
