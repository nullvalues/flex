# flex — Revised Decision Memo: Era 4 closeout (0.4.1) and Era 5 definition (0.5.1)

**From:** design review of `flex:songline` brief against `nullvalues/flex@main`, revised per operator rulings of 2026-08-05
**For:** David Jacobsen — remaining rulings requested in 9
**Supersedes:** flex-0.4-decision-memo.md (v1). Version semantics changed; see 0.

**Already ruled by operator (not re-argued):**
- All of D1–D9 in scope; OpenProse is a hard dependency; songline naming stands.
- **Versioning:** Era 4 closes with a wiring-cleanup release at **0.4.1**. This memo's real work defines **Era 5**, landing at **0.5.1**. (Prior memo's "0.4.x" scope is now Era 5 scope.)
- **Hard fork after 0.4.1.** The fork must be free of fleet mentions — the private proving repos and the upgrade/jockeying history of the proving cycle do not travel.
- **Platform:** shift the harness to **TypeScript** as part of the monolith-drag cleanup (Era 5), so the platform language matches what we mostly build — no reaching across repos or into the skill install cache to run tests. A Python version returns later as a **port of the tidy TS kernel**, not a parallel effort. (Prior memo's DQ-1 B is amended: the shrink still happens, but the kernel that survives it is written in TS, not left in Python.)
- **Sidebar + pipes: retired.** (Prior DQ-3, ruling 5 — ruled as recommended.) Post-fork we carry across even less companion-sidebar legacy than v1 proposed: no deprecation shim, no one-minor alias window for the companion skill.
- **Cross-family pairing** is a build-loop invariant (new — 5).

---

## 0. Version and era semantics (correction)

| Era | Version | Content |
|-----|---------|---------|
| Era 4 (open) | **0.4.1** | Close the missing wiring: shadow-reviewer dispatch, dead gate-worker retirement, measurement columns, stale-hook + sync repair across the proving projects. Last release under the old vocabulary. |
| — | hard fork | Fork hygiene: fleet expunged (2). Clean lineage forward. |
| Era 5 | **0.5.1** | songline: event bus, TS kernel, prose contracts, observability, song/corrections, cross-family router. |

---

## 1. Narrative of Record — mislabeled, not missing

Ruling-question from review: the brief never says "Narrative of Record." Findings: it was **renamed, in two directions**. The repo artifact (ten role narratives, spec-writer sixth input via INFRA-355, intent-reviewer input via INFRA-356) appears in brief 3.1 as "parts and steering" — the *prospective* half. The *retrospective* half ("of record") was split into reflections/corrections (2.5–2.6, D3).

**Disposition:** restore **Narrative of Record** as the canonical name for the part-steering layer in Era 5 docs. The song sits above the Narratives of Record; reflections/corrections sit below as the memory layer. D4 composes all three; nothing is greenfield.

---

## 2. Fork hygiene — expunging the fleet

The 16 bound proving projects (0.1.0–0.3.0) served their purpose: they proved the wiring. After 0.4.1 they stay behind on the old line.

**Before the fork (0.4.1):** final stale-hook remediation and sync-all across the proving projects, under the old vocabulary. This is where the sync-process attention (7) starts — 0.4.1 repairs sync enough to run one last clean pass.

**In the fork:** 
- No `fleet_*` code paths — `fleet_discovery.py` and fleet framing do not travel; generic **project sync** (one target, current version) replaces fleet sync (many targets, version spread).
- `docs/fleet-snapshot.md` and proving-cycle era notes referencing private repos: dropped.
- Private remotes, upgrade/jockeying history: scrubbed (fresh history at fork point, not a filtered rewrite).
- Grep gate at fork: zero matches for `fleet`, proving-repo names, or private remote URLs in the forked tree.

Consequence for v1 memo: baseline row 9 ("fleet machinery is the migration vehicle") is void. Era 5 migration tooling targets *one project at a time* from 0.4.1 → 0.5.1; there is no fleet to migrate.

---

## 3. DQ-1 revised — TypeScript kernel, Python as later port

Ruled in direction; mechanics below are the recommendation.

The v1 diagnosis stands: monolith drag, tests-as-concrete, and spec bloat are the cost, and porting them intact would carry all three across. The ruling resolves the tension differently than v1's option B: **the shrink and the language shift are the same act.** Decomposing `flex_build.py` (210 KB) and `next_action.py` (103 KB) rewrites every surviving line anyway — write those lines in TS.

1. **Prose deletes first.** Maintains-shaped subsystems (4) become OpenProse contracts; their Python is deleted, never ported. ~300 KB never becomes TS.
2. **The kernel is rewritten in TS under the module budget** (~25 KB/module, ruling 8): next-action resolver, worktree lifecycle, effort recording, scope_guard, model router. One toolchain with the observability stack (already Fastify 5 + React 19).
3. **Tests are culled, not ported.** Freeze tests (CLI-surface, test-identity, build parity) die at the fork. Surviving semantics are re-earned as TS tests that **report onto the event bus** — test runs become event types, so the observability SPA reflects testing natively. This is the observability-overlap jump: the test lane and the build lane are the same interface.
4. **Python returns as a port** of the tidy kernel once it settles (0.6-planning trigger), for Python-native host repos — platform language matching build language cuts both ways.
5. **Hooks:** single-file, zero-resolution fast-start stands; runtime is now a ruling (ruling 1) — node/Bun single-file follows the platform, stdlib Python remains the no-new-runtime option.

---

## 4. DQ-2 — OpenProse attachment (unchanged except fleet row)

Two-wave recommendation stands. Revised fate table:

| Subsystem | Python today | Fate |
|-----------|--------------|------|
| audit | audit.py, 46 KB | prose contract, wave 1 |
| sync | pairmode_sync.py, 70 KB | prose contract, wave 1 — redesigned per 7 first |
| drift report | pairmode_drift_report.py, 26 KB | prose contract, wave 2 |
| docs currency | checkpoint prose + scripts | prose contract, wave 2 |
| index integrity | index_integrity.py, 17 KB | prose contract, wave 2 |
| ~~fleet discovery/sync~~ | fleet_discovery.py, 29 KB | **deleted at fork** (2) — does not travel, is not contracted |
| scaffold rendering | bootstrap.py, 84 KB | partial — template maintenance to contracts; interactive bootstrap stays code (rewritten TS, Era 5) |

D9 invariant unchanged: narrative enters contracts only as bounded low-cardinality parameters; song text is never fingerprinted into a node. Reactor pin-and-vendor still ruling 3.

---

## 5. Cross-family pairing — new build-loop invariant

Ruled: any pair of agents working together in the build loop should be from **different model families, if possible**. Escalation examples as ruled: a sonnet builder is reviewed by opus and shadowed by opus; the intent reviewer is escalated **one family level above the builder** where a higher family exists — an opus build is intent-reviewed by fable.

This lands as router policy (amends D7), not per-agent config:

- **Pair rule:** builder ⊥ reviewer, builder ⊥ shadow — different families when the roster allows.
- **Intent escalation rule:** intent reviewer = one level above builder's family; at the top of the ladder, see ruling 10.
- Enforced in the model router with an audit event on every waiver (roster didn't allow it) — waivers are visible in the observability lane, so correlated-checker governance is measurable, answering the brief's "your cross-checkers are correlated" objection with data instead of policy prose.
- Existing model_selector escalation (per-class, per-attempt, loop-breaker) generalizes into this router; the loop-breaker tier above opus is the same ladder.

Open sub-rulings: 10 (top-of-ladder behavior) and 11 (hard requirement vs prefer-with-waiver).

---

## 6. DQ-3/DQ-5 — event bus and observability (ruled retired; scope grows one lane)

`.flex/events.jsonl` replacement architecture stands as v1 4: hooks append lines, observability API tails + serves SSE, state.json single-writer becomes a derived view. Shadow suggestions and whispers are event types on the bus. Post-fork simplification: pipe fallback code, multi-project pipe contamination handling, and the companion skill are deleted outright — no deprecation window.

Observability lanes for 0.5.1 (SPA read-only; write controls still ruling 9):

1. **Live session view** — spawns, verdicts, attempt counters, context gauge vs 143k ceiling, worktree state.
2. **Shadow lane** — suggestions beside builder timeline, adopted/ignored derived from worktree diff. (Dispatch wiring itself ships earlier, in 0.4.1.)
3. **Whisper lane** — recollections with source correction; silence rendered as quiet. Rail/file-overlap matching only; no embeddings.
4. **Test lane (new)** — TS test runs as bus events: suite, story, verdict linkage. Testing reflected natively in the interface, per 3.3.
5. **Pairing lane (new, small)** — router decisions and waivers, per 5.

---

## 7. Sync — needs attention (new DQ)

Current sync (`pairmode_sync.py`, 70 KB) was built for fleet-shaped drift: many projects, wide version spread, template-diff reconciliation. Known weaknesses the proving cycle surfaced: stale hooks survive sync (phase-121 problem), version detection trusts `pairmode_version` markers that drift, and sync conflates three jobs (template refresh, version migration, drift report).

**0.4.1 (repair):** fix stale-hook remediation and marker trust enough to run the final proving-cycle sync-all cleanly.

**Era 5 (redesign):** split the three jobs. Template refresh becomes a prose contract (wave 1, 4). **Version migration becomes a first-class, versioned migration chain** — one command, one project, 0.4.1 → 0.5.1, idempotent, with a receipt event on the bus. Drift report stays a contract (wave 2). Recommendation: migrations as ordered single-file steps in-repo (like schema migrations), so bringing a repo to current is `flex sync` reading the chain — no reaching into the skill install cache.

---

## 8. DQ-4 — spec.json, seed, song (unchanged)

As v1 5: song.md authoritative for intent (append-only, drowned-waypoint style); corrections store authoritative for memory with effort.db backfill; spec.json downgrades to a generated one-way compat view for one minor then freezes; seed recast to mine song drafts + candidate corrections; ideology.md fold-in still ruling 7. Corrections storage still ruling 6.

---

## 9. Proposed sequence

**0.4.1 — Era 4 closeout (all small/medium; weeks not months):**

| Phase | Title | Covers |
|-------|-------|--------|
| W1 | Shadow-reviewer dispatch wiring: spawn action, model-selector entry (INFRA-358/359), write capability (CER-164); folds planned phase 122 | brief 2.8/3.1 gap |
| W2 | Measurement + dead code: cause-class column, silent-deviation marking; retire gate-worker | D1, D2, phase-117 finding |
| W3 | Sync repair + final proving-cycle sync-all; stale-hook remediation (folds planned phase 121) | 7 repair |
| W4 | Fork prep: fleet expunge, history scrub, grep gate, 0.4.1 tag → **hard fork** | 2 |

**Era 5 → 0.5.1:**

| Phase | Title | Covers | Size |
|-------|-------|--------|------|
| E1 | Event bus: pipes deleted, hooks → events.jsonl, sidebar removed, state.json single-writer, fast-start hooks | 6, ruling 1 | medium |
| E2 | TS kernel: flex_build/next_action decomposed into TS modules under budget; freeze tests culled; test runs onto the bus | 3 | large |
| E3 | Prose wave 1: audit + template-refresh contracts; matching Python deleted | 4 | large |
| E4 | Observability SPA: live view, shadow lane, test lane (SSE) | 6 | large |
| E5 | Corrections + reflections: durable store, effort.db backfill, CER vocabulary absorbed | D3 | medium |
| E6 | The song: song.md, Narrative of Record naming restored, ideology fold-in, spec.json compat view, seed recast; four-axis verdicts at story + checkpoint | D4, D5, 1 | large |
| E7 | Prose wave 2 + whispers: drift/docs/index contracts; whisper retrieval + lane; reviewer-context instrument | D9, D8 | large |
| E8 | Cross-family router + closeout: pair rule, intent escalation, waiver events, pairing lane; latitude dials + rationale; migration chain (`flex sync`); 0.5.1 tag | D6, D7, 5, 7 | large |

D-coverage: D1✓ D2✓ (W2) · D3✓ (E5) · D4✓ D5✓ (E6) · D6✓ D7✓ (E8) · D8✓ (E7) · D9✓ (E3+E7).

---

## 10. Rulings — closed 2026-08-05

1. **Hook runtime**: node single-file. Python port possible later; bar to install node is low even off-language.
2. **Prose pace**: two waves, via a maintenance registry (`kind: script` | `kind: contract`, uniform verdict/receipt shape) — the straddle is one mixed dispatch table for one phase gap.
3. **Reactor**: pin + vendor in-repo; upgrades are deliberate, tested events.
4. **Corrections storage**: sqlite canonical + append-only markdown digest.
5. **spec.json**: immediate freeze — generated once at migration as a snapshot, never regenerated.
6. **Vocabulary**: keep era/phase/rail. Elevated to invariant: **the ledger is portable** — an outside agent given only eras/phases/rails/stories, in order, can re-derive the software (checked by a "rewrite test"). Boundary rule generalizing D9: narrative crosses into the ledger only as resolved text or bounded enums, never live references — verdicts quote intent-aspect text inline; reseeds carry cause-class enum + plain-text summary.
7. **ideology.md**: fold into song as its fourth-axis section, append-migrated.
8. **Module budget**: 16 KB / ~400-line lint gate; escape hatch to 24 KB with reviewer-accepted rationale comment.
9. **SPA**: read-only permanently, not provisionally — the agent interface is the write path (decision points surface as app prompts; whispers/corrections route there). OSPA is metric reporting for turning dials elsewhere.
10. **Roster + pairing matrix**: the router's roster is operator-owned — register any model suite (any provider, LLM or SLM), declare preferred pairings per matrix slot (builder → reviewer/shadow/intent). Family-ladder rules ship as the prompted default hierarchy, not doctrine. Top of ladder steps *down* one family (opus reviews fable). Optional local-SLM second reviewer: advisory input to the primary (shadow-style, take-it-or-leave-it), primary verdict binds, divergence emitted as a bus metric — never blocking.
11. **Strictness**: prefer-different-family with logged waiver; nothing halts. Explicit `pin` on a matrix slot expresses deliberate single-model posture and suppresses waiver noise.
12. **Fork**: fresh history at fork point — new repo from the expunged 0.4.1 tree; grep gate passes on one tree; blame stops at the fork.
13. **Python**: not supported until post-0.5.
14. **Sequence W1–W4 / E1–E8**: approved as proposed.

### As originally posed

Carried from v1 (still open): 
1. **Hook runtime**: node/Bun single-file (follows platform) vs stdlib-Python single-file (no runtime assumption). Rec now **node single-file** given the TS ruling.
2. **DQ-2 pace**: big bang / **two waves (rec)** / pilot-only.
3. **Reactor dependency**: **pin + vendor (rec)** vs track upstream.
4. **Corrections storage**: **sqlite canonical + markdown digest (rec)** / markdown only / sqlite only.
5. **spec.json compat window**: **one minor (rec)** / immediate freeze / indefinite.
6. **era/phase/rail vocabulary**: **keep (rec)** / rename into songline terms.
7. **ideology.md**: **fold into song (rec)** / keep as peer.
8. **Module size budget**: ~25 KB per kernel module (rec) — confirm or set.
9. **SPA write controls**: **out of 0.5.1 (rec)** / include.

New: 
10. **Top of the family ladder**: when the builder is already top-family (e.g. fable), intent review falls to — a peer family at the same level (rec), the same family with a fresh context, or an operator gate.
11. **Pair-rule strictness**: **prefer-different-family with logged waiver (rec)** vs hard requirement (blocks build when roster is thin).
12. **Fork mechanics**: **fresh history at fork point (rec)** vs filtered rewrite of existing history.
13. **Python port trigger**: revisit at 0.6 planning once TS kernel settles (rec) — confirm.
14. **Sequence W1–W4 / E1–E8**: approve or reorder.


---

## 11. Addendum — landing-spot rule (operator, 2026-08-05)

15. **Landing-spot rule**: no feature ships without a narrative and a landing
spot. Every new agent role, config flag, event type, or persistent surface
must land with a same-phase narrative entry and a discovery surface —
default-on, a bootstrap prompt, or a documented landing spot (the UI analogy:
no schema change without a CRUD/config surface). Enforced twice: the
intent-reviewer procedure FAILs violating phases (INFRA-434) and a mechanical
dark-feature scan runs at every checkpoint (INFRA-435). Named precedent: the
shadow-reviewer shipped built, narrative-less, and default-off. 0.4.1 must
pass the scan itself before tagging (proposed phase fork-prep precondition), and the 0.5.0
cutover additionally requires the KERNEL-006 side-by-side proof with a tested
pin-back path, since the TS shift is hard to reverse.
