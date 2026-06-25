# Agreements — HARNESS001-ante1 · Versioning & upstream compatibility

**Parent era:** [Era 003 — Orchestrator as harness](../eras/era-proposed-harness-20260624-001.md)
**Phase key:** `HARNESS001-ante1` (era-wide preflight — must complete first)
**Status:** walking (decisions open)

> An *agreements doc* records the decisions for a phase before any story is
> specced. We walk each decision point (DP) top to bottom; once a DP is settled,
> its **Decision** line is updated from ⬜ OPEN to ✅ AGREED and becomes binding on
> the story specs. This doc is the input to `phase_new.py --phase-id HARNESS001
> --suffix ante1`.

## Why this phase exists

Era 003 makes a breaking change to flex's skills and bootstrapped build loop.
This preflight guarantees the fleet keeps running throughout, reconciles the
version numbers, and establishes the dev line — *before* any refactor lands.

## Context (established facts)

- **Consumption model:** the fleet does **not** install flex via versioned
  marketplace pins. Each consumer resolves flex through `FLEX_DIR` (or common
  paths, defaulting to `/mnt/work/flex` — *this working tree*) and executes skill
  scripts from that **single shared checkout** (`global_session_check.py`
  resolution order; `SKILL.md` §544). There is no per-project copy and no version
  pinning at the plugin layer.
- **Consequence:** breaking changes hit the fleet the moment they land in the
  shared tree — and because scripts run from the working tree, even *uncommitted*
  edits here can break fleet builds. The real isolation primitive is **which
  checkout `FLEX_DIR` points at**, not a marketplace version.
- **Two version numbers:** plugin `0.1.0` (`plugin.json`, `marketplace.json`,
  informational/dead) and pairmode methodology `0.2.0` (single-sourced from
  `skills/pairmode/scripts/_version.py`, mirrored in `SKILL.md` frontmatter).
- **Version nag:** bumping `PAIRMODE_VERSION` in the shared tree immediately makes
  every fleet project's SessionStart hook print "behind canon — run sync," with no
  auto-remediation (operator runs `sync-all` manually).
- **Migration tool:** `sync-build` is **diff/replace, not merge** — it rewrites a
  consumer's `CLAUDE.build.md` from the canonical `.j2` template. `sync-all`
  sequences `sync` → `sync-agents` → `sync-build`; dry-run by default.
- **Fleet (uncertain):** `registered_projects` = `["/mnt/work/coherra"]` (drift
  opt-in only). Docs additionally name forqsite, radar, asp, aab, cora, lumin,
  halfhorse. The true set of `FLEX_DIR`-consumers is not enumerable from here.
- **Git state:** `main` is the only live line; `era2`/`era3-methodology`/`pairmode`
  branches are stale. Checkpoints are tagged (`cpNN-…`); **no semver release tags
  exist.**

---

## Decision points

### DP1 — Dev-line isolation mechanism *(crux; others depend on it)*

**Question:** How do we develop the breaking refactor without the shared-checkout
fleet executing half-built code?

**Options:**
- **A — Hard fork (separate repo/clone).** Heaviest; two repos to keep in sync;
  only warranted if divergence is expected to be long and messy.
- **B — `harness` branch via `git worktree` (recommended).** Keep `/mnt/work/flex`
  on `main` so the fleet's `FLEX_DIR` config is untouched and stable. Do harness
  dev in a worktree (e.g. `/mnt/work/flex-harness`) checked out to a `harness`
  branch. Planning docs + genuinely-additive code may fast-track to `main`;
  all breaking code stays on `harness` until the flip. Cutover = merge
  `harness` → `main` + version bump + fleet sync.
- **C — Single shared `main`, additive discipline only.** No branch isolation;
  rely entirely on every commit being additive. No safety net if "additive" slips.

**Recommendation:** **B + additive discipline.** The worktree gives a hard safety
net (the fleet runs `main`, never sees `harness`) while the additive contract
(DP4) keeps the eventual merge clean. Fork (A) is the fallback if divergence on
`harness` becomes unmanageable.

**Decision:** ✅ AGREED — **B + additive discipline.** `git worktree add
/mnt/work/flex-harness harness`; `/mnt/work/flex` stays on `main` (fleet-facing,
stable); the worktree's `CLAUDE.build.md` is regenerated via `sync-build` with
`pairmode_scripts_dir=/mnt/work/flex-harness/skills/pairmode/scripts` so
flex-in-worktree exercises worktree scripts/tests, fully isolated from the fleet.
Breaking code on `harness`; docs + truly-additive code may fast-track to `main`;
flip = merge `harness → main`. Fork (A) is the fallback only if `harness` diverges
unmanageably or DP7 finds an unavoidable shared-writer conflict. The worktree is a
*hard* barrier (fleet physically cannot execute harness code — different path),
unlike C which has no safety net.

---

### DP2 — Stable anchor / rollback point for the fleet

**Question:** What named point can the fleet roll back to if a cutover goes wrong?

**Context:** no semver tags exist today; only checkpoint tags.

**Recommendation:** tag current `main` HEAD as **`v0.2.0`** (first semver tag) as a
cheap, named rollback anchor, independent of the branch strategy. Optionally a
`stable/0.2` branch if we want fleet `FLEX_DIR` to track a branch rather than the
tip of `main`.

**Decision:** ✅ AGREED — **tag `v0.2.0` at HEAD** (flex's first semver tag; named
"what the fleet runs today" rollback anchor, distinct from `cpNN-…` checkpoint
tags). HEAD is `cp78 + 2 docs-only commits`, functionally identical to last
known-good. **Branch topology deferred to DP5** (`stable/0.2` vs `release/0.3`,
and whether `main` flips or the fleet stays on a stable line, is a cutover-topology
decision — a rolling per-project cutover *requires* lagging projects to point at a
stable line, so it must be decided alongside the cutover sequence). The `v0.2.0`
tag is needed under any topology. Executed when the phase is built, not now.

---

### DP3 — Version reconciliation & bump timing

**Question:** Which numbers move, to what, and *when*?

**Sub-decisions:**
- **Pairmode methodology:** `0.2.0` → **`0.3.0`** (the meaningful "sync
  deliberately" signal).
- **Plugin version:** `0.1.0` → align to **`0.3.0`**, or keep independent? Proposed:
  align both to `0.3.0` going forward (same number, retain separate fields/meaning).
- **Timing (critical):** the bump must **not** land on the fleet-facing checkout
  during dev, or every project nags "behind canon" before 0.3.0 is ready and
  syncable. Proposed: `harness` branch carries the bump (as `0.3.0`); `main`
  stays `0.2.0` until cutover.

**Decision:** ✅ AGREED —
- **Pairmode methodology:** `0.2.0` → **`0.3.0`** (stay pre-1.0; minor bump carries
  the breaking change, matching existing cadence; 1.0.0 deferred until the harness
  architecture is the proven baseline).
- **Plugin version:** `plugin.json` + `marketplace.json` aligned to **`0.3.0`**;
  documented rule "plugin version and pairmode version bump together," guarded by a
  small test asserting the two match. *Not* single-sourced into the JSON manifests
  (not worth a build step) — two manually-synced fields + one guard test.
- **Timing:** the bump lives on **`harness` only**. `main` (fleet-facing) stays
  `0.2.x` through dev so the SessionStart "behind canon" nag never fires
  prematurely. `harness` carries **`0.3.0-dev`**, finalized to **`0.3.0`** at the
  flip. The bump reaches the fleet's line only at cutover, where the nag firing is
  *intentional* — the deliberate "run sync now" migration trigger (DP5).

---

### DP4 — Backward-compat contract (the additive invariant, concretized)

**Question:** What exactly must hold true for "additive-until-flip" to be real?

**Proposed contract — through `HARNESS001-main` … `HARNESS005-main`:**
1. **No existing `flex_build.py` subcommand signature changes** (names, flags,
   output contracts that the live `CLAUDE.build.md` parses).
2. **Resolver is strictly read-only / advisory.** The orchestrator remains the
   sole writer of `state.json`, `effort.db`, story status, attempt counters, and
   permission files. `next-action` may *read* them; it writes nothing
   authoritative until the flip.
3. **No change to consumer-facing templates** (`CLAUDE.build.md.j2`,
   `agents/*.md.j2`) until `HARNESS006-main`.
4. **A compat-guard test** asserts (1) — the set of CLI subcommands + their flags
   is frozen for the additive window.

**Decision:** ✅ AGREED — adopt the four-point contract, scoped to the additive
window `HARNESS001-main … HARNESS005-main`:

1. **Existing CLI surface frozen.** No rename / removal / flag-change to existing
   `flex_build.py` subcommands or their output contracts. Additions (notably
   `next-action`) allowed. Consolidation/removal of old CLIs
   (`select-builder-model`, `next_story`, `check-*-gate`, `read-attempt-count`, …)
   happens only at/after the flip.
2. **Resolver is pure-read.** `next-action` reads `state.json`, `effort.db`, the
   index, story status, attempt counters; writes nothing authoritative (ideally
   nothing at all; any cache is disposable and never read back by the
   orchestrator). Orchestrator stays sole writer. (Same guarantee DP7 validates via
   the state-ownership table.)
3. **Fleet-facing surface frozen on `main`.** Consumer-facing templates
   (`CLAUDE.build.md.j2`, `agents/*.md.j2`), global hooks, and agent files do not
   change on `main` until the flip — a mid-era `sync` yields the unchanged 0.2.x
   loop, never half-built harness. These evolve freely on `harness` (never executed
   by the fleet per DP1).
4. **Guard test.** A `tests/pairmode/` test snapshots the 0.2.x CLI command/flag
   surface and asserts it stays a *subset* of the current surface (additions OK,
   removals/renames forbidden) through HARNESS005; rebaselined at the flip.
   Output-contract stability rides on existing per-command unit tests.

---

### DP5 — Cutover & migration procedure (executed at the flip, `HARNESS006`)

**Question:** How does each consumer move from the 0.2.x loop to the thin harness?

**Recommendation:** **per-project rolling**, not all-at-once. Order: flex itself
(dogfood) → one canary fleet project → the rest. Per project: `sync-all --dry-run`
(preview the `CLAUDE.build.md` rewrite) → `--apply` → verify a build round →
confirm `pairmode_version` advanced to 0.3.0.

**Decision:** ✅ AGREED — **Option Y (opt-in, do-nothing-stays-stable), rolling,
sync-driven.** Resolves the DP2 branch-topology deferral.

- **Binding mechanic (verified):** `pairmode_scripts_dir` = `Path(__file__).parent`
  of whichever flex checkout runs the sync. A consumer's loop binds to flex by the
  absolute scripts path *baked into its `CLAUDE.build.md` at sync time*, not by
  `FLEX_DIR` (which only drives the version-nag hook).
- **Topology:** `main` stays the stable 0.2.x line for the whole migration window;
  `harness` is the 0.3.0 line in the DP1 worktree (`/mnt/work/flex-harness`). **No
  `stable/0.2` branch** — `main` *is* stable. "Do nothing = stay on 0.2.x" is
  structural (an un-synced project ignores any 0.3.0 checkout's mere existence).
  Rejected the flip-`main`-immediately alternative: it breaks any project that does
  nothing.
- **Per-project mechanic:** run `sync-all --project-dir P` *from the harness
  worktree's scripts* → bakes the worktree `pairmode_scripts_dir`, the thin-harness
  template, and `pairmode_version 0.3.0`. `--dry-run` → `--apply` → verify a build
  round → confirm version. (FLEX_DIR repoint optional, nag-only.)
- **Rolling sequence (opt-in):** flex itself first (finalize `0.3.0-dev → 0.3.0`,
  verify — the DP6 dogfood) → one canary fleet project → the rest, one at a time.
  Operator-initiated per project; nothing forced (compatible with DP3 — the bump
  reaches a project's line only when that project migrates).
- **Final state:** fold `harness → main` (main = 0.3.0, unified), tag **`v0.3.0`**,
  re-sync each project so `pairmode_scripts_dir` points back at canonical
  `/mnt/work/flex`, remove the transient worktree.
- **Authored here** as the migration runbook; **executed at/after HARNESS006.**

---

### DP6 — How flex dogfoods its own refactor

**Question:** flex builds itself with pairmode while pairmode's loop is being
rewritten. Which loop builds the harness stories?

**Recommendation:** flex builds `HARNESS001`–`005` using its **existing 0.2.x
orchestrator loop** (safe because of the DP4 additive contract), and **flips its
own loop last**, at `HARNESS006-main`. So the old loop builds the new one, then
cuts over.

**Decision:** ✅ AGREED — flex's **live build loop stays the 0.2.x shape through
`HARNESS001-main … 005-main`** in both checkouts. The worktree isolates the *code
being written*, not the loop being run (its `CLAUDE.build.md` is the 0.2.x template
pointed at worktree scripts). The resolver + leaf workers built in 001–005 are
exercised **only by their own tests**, never wired into flex's live loop until the
flip. **`HARNESS006-main` is the flip in both senses:** rewrite template to the
thin-harness shape, wire in `next-action` + workers, and flip flex first (regen
flex's own `CLAUDE.build.md`, verify a full build round) — flex is developer *and*
canary. Explicitly forbids progressively wiring the resolver into the live loop
during 001–005, which would void the additive guarantee.

---

### DP7 — Pressure-test the additive-until-flip assumption

**Question (the one we agreed to test):** can the resolver genuinely run alongside
the orchestrator without state conflict?

**Method:** enumerate every shared-state surface and assign a single writer during
the additive window. Surfaces: `state.json` (context tokens, attempt counters,
active story), `effort.db`, the era/phase/story index, story `status` frontmatter,
permission files. If the orchestrator is sole writer and the resolver only reads,
there is no conflict — and `next-action` stays advisory. Output: a documented
**state-ownership table** that the DP4 contract enforces.

**Risk to watch:** any place the resolver is tempted to *own* the attempt counter
or story status before the flip — that would break additivity and force the fork.

**Semantic separation — effort.db ≠ context-control (load-bearing invariant).**
The two token surfaces measure different things and must never cross-feed:
- **effort.db** = *retrospective cost* from subagent `<usage>` blocks (tokens spent
  in disposable subagent contexts). Inputs: model selection, guardrail, rollups,
  cost display. **Never an input to a context-headroom or clear-seam decision.**
- **context-control** = the orchestrator's *own live window occupancy*
  (`context_current_tokens` + the `expected_step_tokens` window-growth constant).
  This is the *sole* basis for headroom / clear-seam decisions.

Rationale: subagent tokens never entered the orchestrator's window, so summing
effort.db to estimate headroom counts tokens that were never there. The thin
harness widens this gap (per-step window growth ≈ return-block size, decoupled from
story effort), so the resolver must compute headroom *only* from context-control
state and use effort.db *only* for cost/model.

**Codified comingling found (remediation, lands at HARNESS006 / gate rewrite):**
`CLAUDE.build.md:320-326` compares `threshold − N` (remaining window) against the
`story-cost-estimate` effort.db median (`flex_build.py:834`) and advises `/clear` —
exactly the wrong cross-feed. The correct mechanism already exists separately at
`CLAUDE.build.md:696-750` (`context_current_tokens + expected_step_tokens` vs
threshold). The redesign **deletes** the comingled advisory; the resolver/gate
reports window occupancy only, and any effort-cost figure shown is labelled cost
(not headroom) and never compared to remaining window. Recurrence cause: the bad
model is written into the gate prose, so it re-teaches itself every run — the
durable fix is removing the codified comparison, not "remembering." The redesign
should also re-derive `expected_step_tokens` to model thin-harness return-block
growth, not anything effort-derived.

**Decision:** ✅ AGREED — **assumption HOLDS.** Orchestrator/hooks remain sole
writers of every shared surface (state.json `context_*` via frozen hooks; active
story / effort.db / `attempt_counter.json` / story status / permission files /
index via orchestrator; commits+tags via reviewer/orchestrator). The resolver is
pure-read on all of them and **writes nothing**. Conditioned on the load-bearing
property that **`next-action` is a pure function of existing durable state** (no
private persisted state) — the same property as the era invariant, so the test
passes for the reason the architecture works.
- **Escalation trip-wire:** if `HARNESS001-main` shows `next-action` needs
  *authoritative* private state, keep it disposable+isolated+unread-by-orchestrator,
  else escalate DP1 → fork.
- **Semantic separation (effort.db ≠ context-control):** adopted as invariant
  (see above) + remediation of the codified comingling at `CLAUDE.build.md:320-326`,
  landing at HARNESS006.
- **Pre-existing note:** `state.json` written non-atomically
  (`story_context.write_state`, plain `write_text`); loop is sequential so low-risk,
  but the resolver tolerates a transient malformed read; atomic-rename hardening is
  a candidate task.

---

### DP8 — Enumerate the live fleet (blast-radius discovery)

**Question:** Who actually consumes this shared tree, so cutover is safe?

**Context:** `registered_projects` lists only coherra; docs name 7+ others; the
true `FLEX_DIR`-consumer set is unknown.

**Recommendation:** a discovery deliverable — scan candidate project dirs for a
`.companion/state.json` carrying `pairmode_version` (and/or a `FLEX_DIR` pointing
here), and produce the authoritative consumer list. Decide whether the result
should populate `registered_projects` so future drift/cutover tooling knows the
fleet.

**Decision:** ⬜ OPEN — proposed: build the discovery + record the canonical fleet.

---

## Resulting story outline (RELEASE rail — finalize after DPs agreed)

*Provisional; pending the decisions above.*

1. **Dev-line setup** — create `harness` branch + worktree; document the
   `main`=stable / `harness`=dev split (DP1).
2. **Stable anchor** — tag `v0.2.0`; optional `stable/0.2` branch (DP2).
3. **Version reconciliation** — bump mechanics across `_version.py`, `SKILL.md`,
   `plugin.json`, `marketplace.json`; bump on `harness` only (DP3).
4. **Backward-compat contract + guard test** — write the contract into the era's
   methodology docs; add the CLI-signature freeze test (DP4).
5. **State-ownership table** — the additive-window single-writer map (DP4/DP7).
6. **Fleet discovery** — enumerate live consumers; record canonical fleet (DP8).
7. **Cutover & migration runbook** — the per-project rolling procedure, to be
   *executed* at HARNESS006 but *authored* here (DP5/DP6).

## Open questions / to investigate

- ~~Does any consumer's bootstrapped `CLAUDE.build.md` invoke flex scripts by
  absolute path vs. via `FLEX_DIR`?~~ **RESOLVED (DP5):** by absolute
  `pairmode_scripts_dir` baked at sync time (`Path(__file__).parent` of the
  syncing checkout). `FLEX_DIR` only drives the version-nag hook. Migration is
  therefore sync-driven (re-render from the 0.3.0 checkout), not an env swap.
- Should `marketplace.json`/`plugin.json` versions be made *live* (drive install)
  or formally documented as informational? (Out of scope unless it changes
  cutover.)
