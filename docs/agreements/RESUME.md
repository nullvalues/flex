# Resume point — Era 002 → 003 transition

**Written:** 2026-06-26 (before a context clear). Delete or update once step 6 below is done.

## One-line status

Era 002 is closed-out clean (build gate green, 2232 passed). **The only remaining
action is step 6 — `era_transition` — which is gated on the user's explicit go.**
Everything up to that point is committed and pushed to `origin/main`.

## Read these first (in order)

1. `docs/eras/era-proposed-harness-20260624-001.md` — the proposed **Era 003
   (orchestrator-as-harness)**. Settled architecture: thin harness loop over a
   code-resident `next-action` resolver; leaf workers = agent shell + plugin
   procedure skill in disposable context; invariant "harness holds nothing not
   reconstructable from `next-action`". Rails: RESOLVER, HARNESS, WORKER, OBS,
   RELEASE. Phases `HARNESS001-ante1` (versioning/compat preflight) →
   `HARNESS008-main` (housekeeper), plus Phase G = observability refactor.
2. `docs/agreements/HARNESS001-ante1.md` — **settled** agreements (DP1–DP8) for the
   first phase: harness branch via `git worktree`; tag `v0.2.0`; pairmode+plugin →
   `0.3.0` (`0.3.0-dev` on harness until flip); 4-point additive contract;
   Option Y rolling sync-driven cutover; flex dogfoods on the old loop and flips
   itself at `HARNESS006`; resolver is pure-read (state-ownership table);
   effort.db ≠ context-control invariant. Finalized RELEASE-001…006 story outline.
3. `docs/agreements/era-002-closeout.md` — **DC1–DC3 settled, steps 1–5 executed.**
   Phase 64 deferred to Era 003 Phase G; D1/D2/D3 → CER-053/054/055; deferred-
   recognition gap → CER-056.

## The next action (step 6 — needs the user's go)

Per the close-out plan, execute `era_transition`:

1. `era_transition.py --yes --name "flex — Orchestrator as harness" --intent "<one-liner>"`
   → closes Era 002 (`status: complete` + `closed_at`), creates a fresh
   `003-flex-orchestrator-as-harness.md` **stub** (`status: active`).
   (`_next_era_id` ignores the `era-proposed-*` file → computes 003. Confirmed.)
2. Replace the stub body with the proposal's full content, keeping
   `id: "003"` / `status: active`.
3. **Fold Phase 64 + D1/D2/D3 (CER-053/054/055) into Phase G's scope** in the 003
   doc; note Phase 64's deferred stories resume there.
4. Delete `era-proposed-harness-20260624-001.md` (superseded by the live 003 doc).
5. Commit + push.

Note: live filename will be `003-flex-orchestrator-as-harness.md` (002 naming
style), not the `003-harness.md` some docs loosely reference — keep references
consistent on the way through.

## After step 6

Era 003 is active → build `HARNESS001-ante1`:
`phase_new.py --phase-id HARNESS001 --suffix ante1`, then `story_new.py` for
RELEASE-001…006 (see HARNESS001-ante1.md story outline). RELEASE-001 is operator
git work (worktree + `v0.2.0` tag); RELEASE-002 is the only harness-only story.

## Working-tree / housekeeping notes

- `flex_eph/` (the observability screenshot) is untracked — leave it.
- Stray uncommitted `flex_build.py` / `flex_observability.py` edits were reverted
  per user decision (option a) — do not reintroduce.
- The status-drift + stale-era-table + un-annotated-CER-Do-Now mess found during
  close-out is the concrete forcing function for the **HARNESS008 housekeeper**.
- Recurring guardrail (also in auto-memory): never estimate orchestrator context
  headroom from effort.db cost totals — see CER-053 / HARNESS001-ante1 DP7.

## Last commits

- `cba8ee4` fix(era-002): green the build gate for close-out
- `64c43fa` chore(era-002): execute close-out steps 1-5 (docs/bookkeeping only)
- (earlier) era-003 proposal, HARNESS001-ante1 agreements, era-002 close-out plan
