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

**Decision:** ⬜ OPEN — proposed: B + additive discipline.

---

### DP2 — Stable anchor / rollback point for the fleet

**Question:** What named point can the fleet roll back to if a cutover goes wrong?

**Context:** no semver tags exist today; only checkpoint tags.

**Recommendation:** tag current `main` HEAD as **`v0.2.0`** (first semver tag) as a
cheap, named rollback anchor, independent of the branch strategy. Optionally a
`stable/0.2` branch if we want fleet `FLEX_DIR` to track a branch rather than the
tip of `main`.

**Decision:** ⬜ OPEN — proposed: tag `v0.2.0` at current HEAD; `stable/0.2`
branch only if we decide the fleet should track a branch.

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

**Decision:** ⬜ OPEN — proposed: pairmode → 0.3.0, plugin → 0.3.0, bump lives on
`harness` only until flip.

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

**Decision:** ⬜ OPEN — proposed: adopt the four-point contract + guard test.

---

### DP5 — Cutover & migration procedure (executed at the flip, `HARNESS006`)

**Question:** How does each consumer move from the 0.2.x loop to the thin harness?

**Recommendation:** **per-project rolling**, not all-at-once. Order: flex itself
(dogfood) → one canary fleet project → the rest. Per project: `sync-all --dry-run`
(preview the `CLAUDE.build.md` rewrite) → `--apply` → verify a build round →
confirm `pairmode_version` advanced to 0.3.0.

**Decision:** ⬜ OPEN — proposed: per-project rolling, flex-first then canary then
fleet. (Documented in the phase, executed at HARNESS006.)

---

### DP6 — How flex dogfoods its own refactor

**Question:** flex builds itself with pairmode while pairmode's loop is being
rewritten. Which loop builds the harness stories?

**Recommendation:** flex builds `HARNESS001`–`005` using its **existing 0.2.x
orchestrator loop** (safe because of the DP4 additive contract), and **flips its
own loop last**, at `HARNESS006-main`. So the old loop builds the new one, then
cuts over.

**Decision:** ⬜ OPEN — proposed: build on old loop; flex flips itself at
HARNESS006.

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

**Decision:** ⬜ OPEN — proposed: produce the state-ownership table; resolver
read-only on every surface until flip. If any surface can't be cleanly
single-writer, escalate DP1 to fork (A).

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

- Does any consumer's bootstrapped `CLAUDE.build.md` invoke flex scripts by
  absolute path vs. via `FLEX_DIR`? (Affects whether a worktree path swap is even
  needed at cutover.)
- Should `marketplace.json`/`plugin.json` versions be made *live* (drive install)
  or formally documented as informational? (Out of scope unless it changes
  cutover.)
