---
id: "003"
name: flex — Orchestrator as harness
status: active
---

## Strategic intent

Era 003 reduces the orchestrator from a procedure that *runs* the build loop
to a harness that *dispatches* it. Today the entire loop — gates, model
selection, the retry ladder, the eight-step checkpoint — lives as prose in
`CLAUDE.build.md`, loaded wholesale into the orchestrator's own context every
build session. The orchestrator spends its context holding the procedure it is
executing.

The era inverts that. The deterministic skeleton of the loop (sequencing,
counters, routing) moves into a code-resident state machine — a `next-action`
resolver. Each unit of *work* moves into a leaf worker: a thin agent shell that
loads its procedure from a plugin-versioned skill in a disposable subagent
context. The orchestrator becomes a dumb loop:

```
while (a = next-action()) != done:
    spawn leaf-worker-for(a.action) with a.scalar, model=a.model
    record-result(result)        # CLI → index / effort.db
```

At any instant the harness holds only the current action scalar and the last
result block. Everything else is reconstructable from `next-action`.

**The load-bearing invariant — non-negotiable for the whole era:**

> The harness holds nothing that isn't reconstructable from `next-action`.

This makes the orchestrator *stateless across clears*. All durable state already
lives in files the resolver reads (the era/phase/story graph, attempt counters,
`effort.db`, `state.json`), so a `/clear` at a safe seam loses nothing — the
harness re-reads `next-action` and resumes exactly where it was. Lossless resume,
as opposed to the harness's built-in compaction, which summarizes and is lossy.

**The point of all this is unattended runtime.** A thin, stateless harness
grows context slowly enough to build many stories before needing a clear, and
when it does need one, the inter-story gate spawn is a guaranteed safe seam
(working tree at HEAD, no attempt in flight). The goal is to build whole phases —
or several phases — without human intervention.

### Two things this era is *not*

1. **It does not codify judgment.** Only the skeleton (sequencing, counters,
   routing) goes into the resolver. Per-story *verdicts* — is this diff in scope,
   are auth/schema preconditions genuinely met — stay LLM judgment, rendered in a
   disposable worker and returned to the resolver as a scalar. The gate CLIs
   become *signal providers, not deciders*: they gather the cheap deterministic
   facts; the worker's judgment is the verdict; the resolver routes on the verdict
   but never computes it. This *raises* the LLM's role at the gates relative to
   today, where an exit code is treated as the verdict.

2. **It does not solve self-clear or re-entry.** The harness cannot `/clear`
   itself mid-turn; it reaches a safe seam and stops. What restarts it (human,
   API, scheduler) is external and out of scope, unchanged from today. This era is
   responsible only for making the seam *safe* and resume *lossless*.

## Architectural decisions (settled)

These were agreed during design and frame every phase below:

- **Spawning + sequencing → code.** The `next-action` resolver is a state machine
  over the era/phase/story graph. It is the load-bearing core: it absorbs the
  control flow currently expressed as English prose in `CLAUDE.build.md`.
- **The harness → a ~20-line dispatch loop** in `CLAUDE.build.md` (and its `.j2`
  template).
- **Each unit of work → a leaf worker = thin agent shell + procedure skill**, run
  in disposable context. Procedure moves out of per-project agent prose into
  plugin-versioned skills, which also eliminates the `sync-agents` drift problem.
- **No nested spawning.** Subagents do not spawn subagents. Any procedure that
  *itself* spawns (the build loop; the multi-spawn checkpoint) is expressed as a
  *sequence of resolver-emitted actions*, so every worker the harness spawns is a
  leaf that does work and returns.
- **Gates = pre-flight worker** (decided), not folded into the builder. A cold,
  isolated "should this proceed?" judgment, and its spawn is the designated
  safe-clear seam where the `pre_tool_use`/`post_tool_use` budget hooks fire
  before any mutation.

## Rails

| Rail | Primary domain |
|------|----------------|
| RESOLVER | `next-action` state machine; index read-model; housekeeper / graph-integrity checks |
| HARNESS | thin dispatch loop; `CLAUDE.build.md` + `CLAUDE.build.md.j2` reduction; the stateless-across-clears invariant |
| WORKER | leaf-worker conversions — agent shell + plugin procedure skill — for gate, builder, reviewer, security-auditor, intent-reviewer, loop-breaker, spec-writer |
| OBS | observability SPA/API refactor to read the new resolver state model instead of orchestrator-centric signals |
| RELEASE | version increment, upstream-consumer compatibility, plugin packaging; keeping flex usable downstream throughout the refactor |
| CORE | _(fill in primary domain)_ |
| TEST | _(fill in primary domain)_ |

## Phases (proposed — `HARNESS` predicate, suffix scheme)

Phases follow the documented suffix convention (`docs/architecture.md` §
phase-naming; `phase_new.py --phase-id HARNESS00N --suffix <main|anteN|postN>`):

- `-ante[N]` — preflight prerequisite; sorts before `-main`; **must complete first**.
- `-main` — the primary phase.
- `-post[N]` — follow-on remediation (e.g. cold-eyes fixes); sorts after `-main`;
  must complete before the next phase. Reserved as needed, not pre-listed.

Alphabetical disk order mirrors build order (`ante < main < post`). Checkpoint
tags follow the file key: `cp-HARNESS001-main`, `cp-HARNESS001-post1`, etc. The
sequence number within `HARNESS00N` is assigned at `phase_new.py` time; the table
below is the proposed order.

Each phase gets its own **agreements doc** that we walk point by point before any
story is specced. Detail here is deliberately light; the open question(s) named
per phase are what the agreements doc must resolve.

| Phase key | Title | Rail | Intent |
|-----------|-------|------|--------|
| `HARNESS001-ante1` | Versioning & upstream compatibility | RELEASE | **Era-wide preflight — must complete first.** Bump the version, establish the dev line, and guarantee downstream consumers keep running throughout the refactor (see § Versioning & compatibility). Agreements doc settled: `docs/agreements/HARNESS001-ante1.md`. |
| `HARNESS001-main` | Resolver foundation — deterministic skeleton | RESOLVER | Build `next-action` as a CLI covering sequencing, counters, model-selection routing only. Runs *alongside* the existing orchestrator (it asks "what's next?" without yet giving up control). Fully unit-tested in isolation. |
| `HARNESS002-main` | Pre-flight gate worker | WORKER | Extract gate judgment into its own leaf worker, fed by existing gate CLIs as signals, returning a verdict scalar. Establishes the safe-clear seam. |
| `HARNESS003-main` | Builder / reviewer / loop-breaker as leaf workers | WORKER | Convert from per-project agent prose to agent-shell + plugin procedure skills. Validate disposable-context isolation and lossless return contract. |
| `HARNESS004-main` | Checkpoint as an action sequence | RESOLVER + WORKER | Decompose the 8-step checkpoint into resolver-emitted actions (`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`, `checkpoint-tag`), each a leaf worker, so nothing nests. |
| `HARNESS005-main` | Spec-writer as a leaf worker | WORKER | Spec mode → resolver-driven action + spec skill (wrapping today's Plan-subagent step). |
| `HARNESS006-main` | Harness reduction — the flip | HARNESS | Shrink `CLAUDE.build.md` and its `.j2` to the thin dispatch loop. Safe only once HARNESS001–005 exist. Enforces the invariant: harness holds nothing not reconstructable from `next-action`. The cutover (DP5/DP6) and the effort.db≠context-control comingling removal (DP7) land here. |
| `HARNESS007-main` (**Phase G**) | Observability refactor | OBS | Rework the SPA/API to read the resolver state model (next-action state, leaf-worker effort, resolver-owned index) instead of the old orchestrator-centric signals. **Absorbs the deferred Era 002 Phase 64 + defects D1/D2/D3 — see § Phase G scope below.** Expected to be heavy. |
| `HARNESS008-main` | Housekeeper consolidation | RESOLVER | Fold scattered index-integrity logic (deferred-story sweep, orphan/status-drift detection, era→phase→story cross-link validation) into the resolver's read-model as a first-class graph-invariant checker. May merge into `HARNESS001-main` if it stays small. Forcing function: the status-drift + stale-era-table mess found during the Era 002 close-out. |

### Phase G scope (HARNESS007-main) — folded-in Era 002 work

Per the Era 002 close-out (DC1/DC3, `docs/agreements/era-002-closeout.md`), the
observability work deferred from Era 002 resumes here as part of Phase G. This
phase's agreements doc must scope all of the following alongside the resolver-state
SPA refactor:

- **Phase 64 (Observability SPA hardening)** — 5 deferred stories, resumed here:
  - INFRA-164 `flex_observability.py` CLI hardening
  - INFRA-165 `context_budget.py` flex_factor correctness — NaN (low-severity per
    DC1 severity check; capture preserved)
  - INFRA-166 Fastify API route hardening — null project_dir
  - INFRA-167 TypeScript parser robustness — phaseIndex blank
  - INFRA-168 `effortDb.ts` p90 off-by-one + in-flight promise dedupe
- **D1 → CER-053** — `expected_step_tokens` mis-sourced and uniform (seeded from
  the effort-baseline builder median, stamped fleet-wide; the exact
  effort.db ≠ context-control comingling, ≡ DP7). The redesign must re-derive
  `expected_step_tokens` to model thin-harness return-block growth, not anything
  effort-derived.
- **D2 → CER-054** — `context_current_tokens` stuck at the reset seed; live token
  writer not updating these projects. Root-cause needed. (Supersedes CER-045.)
- **D3 → CER-055** — waypoint outcomes uniformly FAIL; either outcome recording
  (`record_attempt.py` → effort.db `outcome`) or the SPA render is wrong; also
  corrupts the `pairmode_effort.py models` PASS-rate report.

The Phase G observability refactor reads the new resolver state model, so hardening
the *old* orchestrator-centric surface in Era 002 would have been wasted effort —
this fold is why Phase 64 was deferred rather than built.

### Open design threads to resolve in the agreements docs

1. **Full state set the resolver must emit (Phase A/D).** Every action and
   transition the prose currently handles, *including the judgment-handoff ones*
   where the resolver routes but a human or worker decides: guardrail pause,
   loop-breaker → user handoff, build-paused. Each becomes an explicit state with
   an explicit action — but the *decision* at that state stays outside the
   resolver.
2. **Signal/verdict boundary (Phase B).** Precisely which gate facts are pure,
   deterministic, resolver-owned signals vs. which stay judgment rendered by the
   gate worker.
3. **Leaf-worker return contract (Phase C).** The exact scalar grammar each worker
   returns (e.g. `clean | block:<reason> | flag:<reason>`,
   `BUILD-RESULT`, `REVIEW-RESULT`) so the resolver can route deterministically.
4. **Observability state model (Phase G).** What the SPA reads once the
   orchestrator no longer holds loop state — likely the resolver's index
   read-model + `effort.db`, surfaced per leaf worker.

## Versioning & compatibility

This era restructures the skills and the bootstrapped build loop — a **breaking
change** for downstream consumers. flex is consumed via a single shared checkout
(consumers resolve flex through `FLEX_DIR` and run skill scripts directly from it);
consumers run skill scripts from the installed plugin while `CLAUDE.build.md` and
the agent files are bootstrapped *into* each project. So a skill refactor on `main`
breaks consumers two ways at once: the plugin CLIs they call shift under them, and
their per-project bootstrapped loop no longer matches. flex also dogfoods its own
pairmode to build itself, so the refactor must not break flex's own build process
mid-flight.

Two version numbers exist today and must be reconciled in `HARNESS001-ante1`:

- **Plugin version** — `0.1.0` in `.claude-plugin/plugin.json` and
  `marketplace.json`.
- **Pairmode methodology version** — `0.2.0`, single-sourced from
  `skills/pairmode/scripts/_version.py` and mirrored in `skills/pairmode/SKILL.md`
  frontmatter; `pairmode_status.py` compares it against each project's recorded
  `pairmode_version` to advise `sync`.

The methodology bump (→ `0.3.0`) is the signal that tells every consumer "the
build loop changed; sync deliberately." The plugin version bumps alongside it.

**Compatibility strategy (ratified in `HARNESS001-ante1`, DP1–DP8):**

1. **Pin a stable line for consumers.** Tag the current state as `v0.2.0` (DP2),
   the named rollback anchor; `main` stays the stable 0.2.x line through the whole
   migration window (DP5, Option Y).
2. **Additive-until-flip.** Per the design, the resolver runs *alongside* the
   existing orchestrator through `HARNESS001`–`005`; the four-point additive
   contract (DP4) keeps every existing CLI subcommand signature backward-compatible
   during that window so neither consumers nor flex's own dogfooding break. The
   breaking change lands only at the flip (`HARNESS006-main`), behind the `0.3.0`
   bump.
3. **Deliberate migration path.** `0.3.0` consumers adopt the new loop via
   `sync-build` / `sync-all`, which rewrites their bootstrapped `CLAUDE.build.md`
   to the thin-harness template — per-project, rolling, opt-in (DP5 Option Y).

**Dev-line isolation (DP1, settled):** `harness` branch in a `git worktree`
(`/mnt/work/flex-harness`); `/mnt/work/flex` stays on `main` (fleet-facing,
stable). Breaking code lives on `harness` until the flip; docs and genuinely
additive code may fast-track to `main`. The full agreements — including the
state-ownership table (DP7) and the effort.db ≠ context-control invariant — are
settled in `docs/agreements/HARNESS001-ante1.md`.

## Transition from Era 002

Era 002 was closed via `era_transition.py` on 2026-06-26 (`status: complete`,
`closed_at: 2026-06-26`), and Era 003 activated. Per the phase-continuity policy,
002's only genuinely-open phase — **Phase 64 (Observability SPA hardening)** — was
formally deferred (its 5 stories → `backlog`/`deferred`, with a `## Deferred
stories` note pointing here). Because Era 003's **OBS** rail reworks observability,
Phase 64 plus the close-out defects **D1/D2/D3 (CER-053/054/055)** fold into
**Phase G (HARNESS007-main)** rather than being built under 002 — see § Phase G
scope above. The close-out record is `docs/agreements/era-002-closeout.md`.

## Era summary

*(era active — not yet closed. The summary below is a provisional record of the
planned-phase work; the final era summary will be written at formal close, once
field validation is complete.)*

All 8 planned phases complete as of 2026-07-03:

- **HARNESS001-ante1** — version pinned (`v0.2.0` tag), `harness` worktree established, dev-line isolated from `main`.
- **HARNESS001-main** — `next-action` resolver built as a pure CLI state machine; sequencing, counters, model-selection routing in code; fully unit-tested in isolation alongside the old orchestrator.
- **HARNESS002-main** — gate verdict extraction: gate-worker leaf worker established, safe-clear seam at inter-story gate spawn.
- **HARNESS003-main** — builder, reviewer, loop-breaker, security-auditor, intent-reviewer converted to agent-shell + plugin procedure skills; disposable-context isolation validated.
- **HARNESS004-main** — checkpoint decomposed into four resolver-emitted actions (`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`, `checkpoint-tag`); no nested spawning.
- **HARNESS005-main** — spec-writer converted to a leaf worker; `spawn-spec-writer` action added to the resolver.
- **HARNESS006-main** — the flip: `CLAUDE.build.md` reduced to the ~20-line dispatch loop; stateless-across-clears invariant enforced; harness holds nothing not reconstructable from `next-action`.
- **HARNESS007-main** (Phase G) — observability SPA/API reworked to read the resolver state model; Phase 64 deferred stories (INFRA-164–168) built; D1/D2/D3 defects (CER-053/054/055) closed.
- **HARNESS008-main** — housekeeper: `index_integrity.py` pure-read graph-invariant checker (status drift, cross-link consistency, orphan stories, deferred-without-section); `check-index` CLI; CER-056 deferred-as-inactive rule shared between the checker and `infer_position`.

The load-bearing invariant held throughout: the harness holds nothing not reconstructable from `next-action`. The era has not yet been run against real project builds at scale; formal close pending field validation.
