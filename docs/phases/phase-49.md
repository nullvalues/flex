# flex — Phase 49: Observability SPA (sidebar replacement)

← [Phase 48: Open-patterns publication initiative](phase-48.md)

**Status:** anchor only, scaffolded 2026-05-29. **No stories, no scope decisions
yet.** Flesh out in plan mode before any spec lands. Do not pick up before
Phase 47 checkpoints; depends on Phase 47 INFRA-127 state.json fields. Phase
number is provisional — both Phase 48 and this phase may renumber if more
urgent work preempts.

**Parent phase:** Phase 47 (no deferred stories; this is the planned
follow-on to the sidebar-deprecation context recorded in Phase 47 CER-027
sub-track decisions, especially the language at phase-47.md:380-385 and
1030-1033).

## Goal (provisional)

Build a thin TypeScript SPA that replaces the companion sidebar (Python
TUI / `skills/companion/scripts/sidebar.py`) as the observability and tuning
surface for pairmode. The SPA reads `.companion/state.json` and exposes:

- Context-budget telemetry (current tokens, threshold, overrun_pct,
  acknowledged_at) — the fields seeded by Phase 47 INFRA-127.
- Per-phase effort.db summaries (medians, attempt counts, backend mix).
- Story state (current rail, current story, last reviewer outcome).
- Tuning controls for the state.json scalars the operator currently edits
  by hand.

The SPA being thin (read state.json + effort.db; no LLM calls of its own;
no parallel state) is the load-bearing design constraint. The sidebar's
per-response LLM calls do NOT carry over.

## Why this phase exists

The companion sidebar is on a documented deprecation path (phase-47.md
CER-027 sub-track, decision rationale around lines 380-385). Multiple
recent phases have routed observability/tuning state into state.json
specifically so the SPA can consume it without scraping logs or the TUI.
Without an anchored next phase, the deprecation has no landing zone and
the state.json investment loses its forcing function.

## Open questions (resolve in plan mode, not now)

- **Stack.** TypeScript implied. Vite + React 19 likely (matches the
  forqsite stack flex already targets), but a server-rendered SSG option
  (e.g. Astro) might fit better for an operator-local tool. Confirm at
  plan time.
- **Hosting model.** Local-only (file://, served from skill dir)?
  `uv run` script that spawns a dev server? Bundled binary? Each has
  permission and update-cadence trade-offs.
- **Auth / scope.** Operator-only single-user, or multi-project view
  across the seven downstream projects? Single-user is cheaper; multi-
  project would require a pattern for discovering state.json paths.
- **Write model.** Read-only at first, or does the SPA write tuning
  changes back to state.json? If it writes, the Phase 47 D11 read-only
  contract for `decide()` extends to a question: does the SPA's write
  path conflict with the hook's `acknowledged_at` write? Concurrency
  model needs explicit design.
- **Sidebar parity.** Which sidebar features migrate verbatim, which get
  redesigned, and which get dropped? Audit `skills/companion/scripts/sidebar.py`
  feature-by-feature at plan time.
- **Sidebar retirement criteria.** When is the sidebar actually deleted?
  Likely after SPA reaches feature parity + ships to at least one
  downstream project. Define explicit retirement gates.
- **Effort.db read path.** Direct SQLite reads from the browser (via
  e.g. sql.js / wasm), or a small read-only API the SPA talks to?
  Browser-direct is simpler but constrains hosting model.

## Known dependencies

- Phase 47 INFRA-127 must have shipped — its state.json fields
  (`context_budget_threshold`, `context_budget_overrun_pct`,
  `expected_step_tokens`, `context_budget_acknowledged_at`,
  `context_budget_reprompt_margin`) are part of the read surface.
- Phase 47 D11 (write boundary) extends to this phase: if the SPA writes
  to state.json, the write-path concurrency model must be designed
  explicitly. Cross-reference catalog pattern `files-over-databases`
  (Common Pitfalls: "Not locking files during writes").
- effort.db schema must be stable. Phase 46 INFRA-123 added the `backend`
  column; further evolutions before Phase 49 starts get audited at plan
  time for SPA impact.

## Out of scope (firm — do not let scope creep here)

- Cloud-hosted dashboard or multi-tenant deployment.
- LLM-driven anything inside the SPA. The sidebar's per-response LLM
  calls are exactly what we're moving away from.
- Replacing effort.db with a different store.
- Replacing state.json with a different format.
- Cross-project analytics (a separate phase if ever needed).

## Stories

| ID | Rail | Title | Status |
|----|------|-------|--------|
| INFRA-133 | INFRA | Wire context budget hook registration into bootstrap and sync | planned |

SPA stories: none yet. Plan-mode session will produce the SPA story inventory
after INFRA-133 ships. All future SPA stories `planned` until then.

## Resume marker

**Current state (2026-06-01):** INFRA-133 is the active story. Build it first.
After INFRA-133 ships and the operator runs the post-ship bootstrap step on
flex and downstream projects, context budget enforcement will be live.

**After INFRA-133 is complete:**

1. Open plan mode against this doc with intent "design the observability SPA."
2. Walk the Open Questions list above; resolve each before any SPA story spec
   is drafted.
3. Re-recon `skills/companion/scripts/sidebar.py` for current feature
   inventory.
4. Draft SPA stories under the standard rail convention (likely a new `UI`
   rail; `INFRA` for any state.json read-API if needed).

**Unrelated open work (do not lose):** The open-patterns pattern doc review
is in progress at `docs/open-patterns-review.md`. Issue PR1 (PR #3 comment
text) is ACTIVE; issues X1 through C1 are OPEN. Return to that doc after
INFRA-133 is built and the post-ship operator steps are done.

Tag (on ship): `cp49-observability-spa`
