# Agreements — HARNESS006-main · Harness reduction — the flip

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS005-main` (spec-writer leaf worker; `spawn-spec-writer` + `needs_spec`
Position flag; full resolver action vocabulary complete). HARNESS001–005 have built all leaf
workers and resolver extensions in advisory mode.
**Phase key:** `HARNESS006-main` · **Rail:** HARNESS + RELEASE
**Builds on:** `harness` branch, in `/mnt/work/flex-harness`.
**Status:** ✅ SETTLED — all 7 DPs AGREED; story outline finalized (2026-06-29).

> An *agreements doc* records the decisions for a phase before any story is specced. We walk each
> decision point (DP) top to bottom; once a DP is settled its **Decision** line moves from ⬜ OPEN
> to ✅ AGREED and becomes binding on the story specs.

## Why this phase exists

HARNESS001–005 built every resolver extension and leaf worker in advisory mode alongside the
existing `CLAUDE.build.md` prose loop. HARNESS006 is **the flip**: it reduces `CLAUDE.build.md`
and its `.j2` template to the thin dispatch loop, retires the old per-project agent templates,
dogfoods flex on the new loop, and folds the `harness` branch to `main`. After the flip, the era's
load-bearing invariant holds in production: **the harness holds nothing not reconstructable from
`next-action`.**

This phase is also the designated removal point for the effort.db ≠ context-control comingling
(CER-053 state half: `expected_step_tokens` sourced from effort.db). That comingling is removed
here because the thin-harness return-block growth model (the correct source) is now fully defined.

The irreversible git fold (merge `harness` → `main`, tag `v0.3.0`, re-sync fleet, remove worktree)
is an **operator action** per `docs/harness-cutover-runbook.md`. The buildable deliverables in
this phase are: (1) the reduced template, (2) the dogfood flip, (3) the comingling removal, and
(4) the fold preparation (version finalize, Signal-1 diagnosis, runbook gate, RELEASE-002 reconcile).

## Context (established facts)

- **Thin dispatch loop target** (era doc §): ~20 lines in `CLAUDE.build.md`:
  ```
  while (a = next-action()) != done:
      spawn leaf-worker-for(a.action) with a.scalar, model=a.model
      record-result(result)
  ```
- **`CLAUDE.build.md.j2` template** at `skills/pairmode/templates/CLAUDE.build.md.j2` — the source
  bootstrapped into each project by `sync-build`. Reducing the template reduces all downstream
  projects at their next `sync-build --apply`.
- **Per-project agent files** (`.claude/agents/`): `builder.md`, `reviewer.md`, `loop-breaker.md`,
  `security-auditor.md`, `intent-reviewer.md` — rendered from `.md.j2` templates via `sync-agents`.
  Replaced by the plugin-versioned procedure skills in HARNESS003.
- **CER-059 (Do Later, HARNESS006):** `fleet_discovery` shows 0 Signal-1 hits across the fleet
  — diagnose before the pre-fold gate; add a Signal-1 verification step to the runbook;
  HARNESS006 needs an explicit AC to reconcile RELEASE-002 `deferred → complete` on main at the fold.
- **RELEASE-002** (`docs/stories/RELEASE/RELEASE-002.md`) — pairmode version bump to `0.3.0-dev`
  on the `harness` branch. Marked `deferred` on `main` pending the fold. Its reconciliation
  (`deferred → complete` on main) is the post-fold operator step; the AC is carried in RELEASE-007.
- **Cutover runbook:** `docs/harness-cutover-runbook.md` (RELEASE-006). The fold follows
  the runbook's § Final fold sequence.

## Decision points

### DP1 — The thin dispatch loop content *(settled)*

**Question:** What exactly goes in the reduced `CLAUDE.build.md` / `.j2`?

**Decision:** ✅ AGREED (2026-06-29).

1. **The reduced template** contains:
   - Session modes section (build mode / all other input) — unchanged header.
   - The thin dispatch loop (~20 lines):
     ```
     ## Build loop
     while (a = flex_build.py next-action --json --project-dir .) != done:
         spawn leaf-worker-for(a["action"]) with scalar=a["scalar"], model=a["model"]
         record result via flex_build.py record-attempt ...
     ```
   - A `## Checkpoint` stanza describing the checkpoint sub-sequence actions (thin reference to
     the resolver emitting checkpoint actions — no prose procedure).
   - A `## Spec mode` stanza with one line: `spawn spec-writer leaf worker for story_id`.
   - All the current multi-page prose procedure is **removed**.
2. **The `.j2` template is reduced first (HARNESS-001).** The live `CLAUDE.build.md` for flex
   is updated in the dogfood flip (HARNESS-002) via `sync-build --apply`.
3. **Total length target: ≤40 lines** (excluding comments). A line-count test in the isolation
   suite gates this.

---

### DP2 — Per-project agent template retirement *(settled)*

**Question:** When are the old `.claude/agents/*.md` rendered files and `.md.j2` source templates
removed?

**Decision:** ✅ AGREED (2026-06-29).

1. **Per-project rendered files** (`.claude/agents/builder.md`, `reviewer.md`, `loop-breaker.md`,
   `security-auditor.md`, `intent-reviewer.md`) are **removed during the dogfood flip (HARNESS-002)**
   as part of `sync-build --apply`. The new worker shells (from HARNESS003's procedure skills)
   replace them as the rendered output.
2. **The `.md.j2` source templates** in `skills/pairmode/templates/agents/` are also removed in
   HARNESS-002. `sync-agents` is updated to render the new `-worker` shells instead.
3. **`reconstruction-agent.md`** is NOT removed (out of scope; not part of the build loop).
4. **Fleet migration:** after the fold, each downstream consumer runs `sync-build --apply` to get
   the reduced loop and the new worker shells. This is Phase 2 of the runbook (operator-driven).

---

### DP3 — CER-053 effort.db ≠ context-control comingling removal *(settled)*

**Question:** Where and how is `expected_step_tokens` re-sourced off effort.db?

**Decision:** ✅ AGREED (2026-06-29).

1. **Three sites must change:** `bootstrap.py:_load_seed_expected_step_tokens()`, `sync.py:594`,
   `context_budget.py:526`. All currently read effort.db / `by_role.builder.median` or default
   to the literal `53000` (effort-median fallback). After the fix, all three read a
   **thin-harness return-block growth constant** defined once (e.g. in a small `context_model.py`
   or next to `next_action.py`).
2. **The thin-harness growth constant** models the harness's per-step context growth: the
   dispatch loop's return block + `<usage>` tokens per action, not a builder's per-story cost.
   It is a deliberate, documented constant — not derived from effort.db.
3. **HARNESS-003 delivers this fix** (state side); a companion SPA display fix is OBS-003 (Phase G).
4. **The per-project re-estimation hook** (effort.db median after ≥5 attempts replaces the seed)
   is removed from the window-growth path (it reintroduces the comingling). It may be preserved
   for a separate per-story context advisory, clearly separated from window growth.

---

### DP4 — Fold sequencing: three stories *(settled)*

**Question:** How are the four HARNESS006 stories ordered?

**Decision:** ✅ AGREED (2026-06-29).

1. **HARNESS-001 first:** template reduction (`CLAUDE.build.md.j2`). The live `CLAUDE.build.md`
   is NOT touched here — only the template source changes.
2. **HARNESS-002 second:** dogfood flip — apply the thin loop to flex's own `CLAUDE.build.md`
   via `sync-build --apply`; retire old agent templates; render new worker shells; run one
   end-to-end story arc on the new loop to confirm it works.
3. **HARNESS-003 third:** CER-053 state fix — re-source `expected_step_tokens` off effort.db.
   Sequenced after the dogfood flip so the thin-harness return-block growth shape is confirmed
   in the live loop before the constant is set.
4. **RELEASE-007 fourth:** fold preparation — `_version.py` → `0.3.0`, CER-059(a) Signal-1
   diagnosis, CER-059(b) runbook Signal-1 verification step, CER-059(c) RELEASE-002 reconcile AC.
   This is the last buildable step before the operator runs the irreversible fold.
5. **The git fold itself** (merge → tag → re-sync → worktree removal) is an operator action per
   the runbook, not a story deliverable.

---

### DP5 — Operator fold gate: what must be true before merging *(settled)*

**Question:** What conditions must hold before the operator runs the fold?

**Decision:** ✅ AGREED (2026-06-29).

1. HARNESS001–006 all checkpointed and tagged.
2. HARNESS006's dogfood pass recorded (HARNESS-002 end-to-end arc completed).
3. `_version.py` == `0.3.0` (RELEASE-007).
4. CER-059(a) diagnosed: Signal-1 detection works on a synthetic scripts-bound tree.
5. CER-059(b): runbook contains the Signal-1 verification step.
6. CER-059(c): RELEASE-002 reconciliation AC present in RELEASE-007's story.
7. Full test suite green: `PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q`.
8. The operator follows the runbook § Final fold sequence: merge `harness` → `main`, tag
   `v0.3.0`, `pairmode_status --sync-all --apply` on each consumer, remove the worktree.

---

### DP6 — CER-059 Signal-1 diagnosis scope *(settled)*

**Question:** What exactly does Signal-1 diagnosis require?

**Decision:** ✅ AGREED (2026-06-29).

1. **CER-059(a):** `fleet_discovery._check_signal1` is tested with a synthetic scripts-bound
   project tree. If the current detection logic yields a false-negative (shows 0 hits when a
   real Signal-1 project exists), fix the detection (`relative_to` path resolution).
2. **CER-059(b):** `docs/harness-cutover-runbook.md` § Pre-fold discovery gate gains an explicit
   step: "After syncing each project, re-run discovery and confirm `binding: scripts` appears."
3. **CER-059(c):** RELEASE-007's story carries an explicit AC: `RELEASE-002.md` status
   transitions `deferred → complete` on `main` after the fold merge. A test asserts this AC
   text is present; the status-flip check is xfail/skip pre-fold (becomes a real check
   post-fold on `main`).

---

### DP7 — Scope fence *(settled)*

**Question:** What is explicitly in/out of HARNESS006?

**Decision:** ✅ AGREED (2026-06-29).

**In:** `CLAUDE.build.md.j2` template reduction (HARNESS-001); flex dogfood flip via
`sync-build --apply` + agent template retirement (HARNESS-002); CER-053 `expected_step_tokens`
re-source (HARNESS-003); fold preparation: version finalize + Signal-1 + RELEASE-002 AC
(RELEASE-007). Advisory isolation tests for each. The buildable flip confirmation (one
end-to-end story arc on the new loop).

**Out:** The irreversible git fold itself (operator action). Fleet-wide consumer migration
(Phase 2–3 of the runbook; operator). Observability refactor (HARNESS007). Housekeeper
(HARNESS008). Any new feature — this phase is pure reduction.

---

## Resulting story outline (HARNESS + RELEASE rail — finalized)

| Story ID | Title | Rail | Acceptance gist |
|----------|-------|------|-----------------|
| HARNESS-001 | Thin dispatch loop + `CLAUDE.build.md.j2` template reduction | HARNESS | `.j2` reduced to ≤40 lines; all prose procedure removed; thin loop + checkpoint stanza + spec stanza; line-count test; live `CLAUDE.build.md` not touched. |
| HARNESS-002 | Dogfood flip — apply thin loop + retire agent templates | HARNESS | `sync-build --apply` updates flex's own `CLAUDE.build.md`; old agent `.md.j2` templates removed; new `-worker` shells rendered; end-to-end story arc on the new loop recorded. |
| HARNESS-003 | Re-source `expected_step_tokens` off effort.db (CER-053 state half) | HARNESS | Three sites re-sourced to thin-harness growth constant; effort.db not read for window growth; invariant test; context budget still functions; test suite green. |
| RELEASE-007 | Fold preparation — version finalize, Signal-1 diagnosis, runbook gate, RELEASE-002 reconcile (CER-059) | RELEASE | `_version.py` → `0.3.0`; Signal-1 detection tested + fixed; runbook Signal-1 step added; RELEASE-002 reconcile AC present (xfail pre-fold); suite green. |

**Build order:** HARNESS-001 → HARNESS-002 → HARNESS-003 → RELEASE-007.

**Schema delivery:** HARNESS006 introduces no new persistent schema objects.

---

## Status

✅ SETTLED — DP1–DP7 all ✅ AGREED; story outline finalized.
