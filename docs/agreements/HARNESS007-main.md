# Agreements — HARNESS007-main · Observability refactor (Phase G)

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS006-main` (harness reduction complete; thin loop live; fold executed;
`harness` branch merged to `main` at `v0.3.0`; fleet on the new loop).
**Phase key:** `HARNESS007-main` · **Rail:** OBS + INFRA
**Builds on:** `main` (post-fold). After HARNESS006 the `harness` worktree is gone; work
resumes on `main` in the standard working directory.
**Status:** ✅ SETTLED — all 6 DPs AGREED; story outline finalized (2026-06-29).

> An *agreements doc* records the decisions for a phase before any story is specced.

## Why this phase exists

Phase G absorbs two deferred work-streams that were held because hardening the existing
observability surface before the harness refactor would have been rebuilt-away work:

1. **Era 002 Phase 64 (deferred 2026-06-25):** 5 hardening stories for the observability SPA
   and context-budget module — INFRA-164 through INFRA-168. Deferred to Phase G per the Era 002
   close-out (DC1) because HARNESS007's SPA refactor replaces the current surface.

2. **D1/D2/D3 defects (CER-053/054/055)** found during the Era 002 observability review:
   - D1 → CER-053: `expected_step_tokens` mis-sourced from effort.db (uniform 53000 fleet-wide;
     state half fixed in HARNESS-003; display half fixed here in OBS-003).
   - D2 → CER-054: `context_current_tokens` stuck at the SessionStart reset seed (live writer
     not updating); root-cause needed.
   - D3 → CER-055: waypoint outcomes uniformly FAIL across 224/460 attempts (recording or
     render bug); corrupts `pairmode_effort.py models` PASS-rate report.

3. **The resolver state model** — after the flip, the orchestrator holds no loop state, so the
   SPA must read the **resolver state model** (next-action state, per-leaf-worker effort from
   `effort.db`, resolver-owned index) rather than orchestrator-centric signals. The SPA is
   refactored to this new source.

Phase G is expected to be the heaviest phase of Era 003. The ordering: state model API first
(OBS-001), SPA refactor second (OBS-002), then D1/D2/D3 fixes (OBS-003/004/005), then the
Phase 64 hardening stories (INFRA-164–168, re-homed here with their bodies intact).

## Context (established facts)

- **Phase 64 stories:** INFRA-164 (`flex_observability.py` CLI hardening), INFRA-165
  (`context_budget.py` flex_factor NaN), INFRA-166 (Fastify route hardening), INFRA-167
  (TypeScript parser robustness), INFRA-168 (`effortDb.ts` p90 + dedup). All bodies are
  complete and spec'd; only frontmatter (`phase: "64"` / `status: backlog`) needs updating.
  **These stories are re-homed, not rewritten.**
- **Era open thread #4** (era doc § Open design threads): "What the SPA reads once the
  orchestrator no longer holds loop state — likely the resolver's index read-model + `effort.db`,
  surfaced per leaf worker."
- **`flex_build.py resolver-state --json`** does not yet exist. It is OBS-001's deliverable
  (additive; freeze-green).
- **`effort.db` per-role rollup:** effort records are keyed by `agent_role` (builder, reviewer,
  gate, loop-breaker, security, intent, docs, spec). OBS-001 surfaces these per leaf worker.
- **CER-056 (Do Later):** `next-action`'s index read treats deferred/backlog phases as active
  (returned as `current-phase`). The deferred-as-inactive rule must be shared between the
  resolver read-model and `check-index` (HARNESS008). OBS-001 applies the rule to the
  `resolver-state --json` index section.
- **Security posture:** the SPA has loopback-only default (CER-042/043 posture). This is not
  changed in Phase G — loopback is preserved.

## Decision points

### DP1 — Resolver state model API design *(settled)*

**Question:** What does `flex_build.py resolver-state --json` emit?

**Decision:** ✅ AGREED (2026-06-29).

1. **The command emits a JSON document with four top-level keys:**
   - `action` — the current `make_action` dict (action/scalar/model/reason/meta/meta.schema_version).
   - `position` — the full `infer_position` Position dict (active phase, next story, attempt count,
     gate signals, `checkpoint_step`, `needs_spec`, `last_attempt_outcome`, `builder_model`,
     `builder_model_reason`).
   - `effort` — per-leaf-worker effort summary from `effort.db` keyed by `agent_role`
     (count, median_tokens, last_outcome, last_timestamp per role).
   - `index` — the resolver-owned era/phase/story graph with deferred/backlog treated as inactive
     (CER-056 rule applied here).
2. **Pure-read:** `grep` confirms no writes in the `resolver-state` subcommand. Composes the
   existing resolver read-model functions (no duplicated logic).
3. **Additive CLI surface:** `flex_build.py resolver-state` is a new subcommand; the CLI-surface
   freeze test stays green (additions allowed).
4. **`resolverState.ts`** — a TypeScript reader in the observability API (`readers/`) shells the
   CLI and returns a typed model. `system.ts` and `context.ts` switch their primary reads to this
   source in OBS-002.

---

### DP2 — SPA UI refactor scope *(settled)*

**Question:** What changes in the SPA when it reads the resolver state model?

**Decision:** ✅ AGREED (2026-06-29).

1. **Reads from the resolver state model:** the SPA renders next-action state (action/scalar/model),
   Position fields (active phase, next story, gate signals, `checkpoint_step`), per-leaf-worker
   waypoints (keyed by `agent_role`, not by orchestrator step), and the resolver-owned index
   (deferred/backlog shown inactive).
2. **Orchestrator-centric signal reads are removed** from `system.ts` and `context.ts` once the
   SPA no longer references them. No route re-derives loop state.
3. **Loopback-only default preserved** (CER-042/043 posture unchanged). No new cross-origin exposure.
4. The INFRA-166/167 hardening stories are sequenced after OBS-002 (the hardened routes/parsers
   apply to the refactored surface, not the old surface).

---

### DP3 — D1 display fix scope (CER-053 display half) *(settled)*

**Question:** What does OBS-003 fix in the SPA regarding `expected_step_tokens`?

**Decision:** ✅ AGREED (2026-06-29).

1. The **state half** of CER-053 is fixed in HARNESS006 (HARNESS-003). OBS-003 fixes the
   **display half**: the context-budget panel reads the re-sourced value and labels its
   provenance ("thin-harness return-block growth," not effort-median).
2. The `render_alert_prompt` ceiling display fix (flex_factor != 1.0 shows unfactored `[R]`)
   from Phase 64 D2 is folded into OBS-003 since it shares the context panel surface. The NaN
   clamp (the harder bug) stays in INFRA-165.
3. No effort-derived value appears in the context-budget panel after OBS-003. An assertion
   confirms this.

---

### DP4 — D2 root-cause scope (CER-054) *(settled)*

**Question:** What does OBS-004 investigate and fix?

**Decision:** ✅ AGREED (2026-06-29).

1. **Root-cause first:** use a synthetic PostToolUse JSONL payload (shaped like a thin-harness
   leaf spawn) to exercise the `post_tool_use.py` writer. If the writer doesn't update
   `context_current_tokens`, identify the exact failure mode.
2. **Fix or document:** if a writer bug, fix `post_tool_use.py` (thin relay constraint applies —
   any logic change is delegated to `context_budget.py`); if projects were idle since the fix,
   record the diagnosis with an honest staleness indicator in the SPA.
3. **SPA staleness:** regardless of root cause, the SPA must surface `last_updated` age for
   `context_current_tokens` so a stale value is visibly stale, not silently authoritative.
4. **`post_tool_use.py` is a protected file** — any change must be declared in `primary_files`
   and reviewed against the hook thin-relay invariant (CLAUDE.md review checklist item 1).

---

### DP5 — D3 outcome recording scope (CER-055) *(settled)*

**Question:** What does OBS-005 fix?

**Decision:** ✅ AGREED (2026-06-29).

1. Diagnose whether the uniform FAIL is a recording bug (`record_attempt.py` not writing the
   `outcome` column for builder/leaf rows → NULL stored) or a render bug (`effortDb.ts`
   `queryWaypoints` mapping NULL → FAIL).
2. Fix both ends if both are wrong. The binding rule: **NULL outcome ≠ FAIL** (writer default
   + reader map). A real FAIL renders FAIL; NULL/absent renders a neutral state ("n/a"/"pending").
3. The effort.db schema is not changed (no new column). This is a value-correctness fix on the
   existing `outcome` column.
4. The `pairmode_effort.py models` PASS-rate report is re-verified uncorrupted.

---

### DP6 — Phase 64 story re-homing *(settled)*

**Question:** How are INFRA-164–168 incorporated into HARNESS007?

**Decision:** ✅ AGREED (2026-06-29).

1. **Re-home, don't rewrite.** The five story bodies are complete and spec'd against the Phase 64
   decisions (D1–D8 in `phase-64.md`). Only their frontmatter is updated:
   `phase: "64"` → `phase: "HARNESS007-main"`, `status: backlog` → `status: planned`.
2. **Sequencing within Phase G:** INFRA-166 requires INFRA-167 (the context route's flex_factor
   live-read calls `parseStoryFrontmatter` fixed in INFRA-167). The OBS stories (OBS-001–005)
   are sequenced before the INFRA re-homes so the SPA refactor is in place before hardening.
3. **The Phase 64 decisions (D1–D8) remain the binding design decisions** for the INFRA stories.
   Phase G's agreements do not supersede them; they are folded in by reference.

---

## Resulting story outline (OBS + INFRA rail — finalized)

| Story ID | Title | Rail | Acceptance gist |
|----------|-------|------|-----------------|
| OBS-001 | Resolver state-model read API (`resolver-state --json` + TS reader) | OBS | `flex_build.py resolver-state --json` emits next-action + Position + per-role effort + resolver index (deferred inactive); pure-read; freeze green; `resolverState.ts` reader; routes switch primary source. |
| OBS-002 | SPA UI refactor to the resolver state model | OBS | SPA renders from resolver model (per-leaf waypoints, resolver index, next-action state); orchestrator-centric reads removed; loopback default preserved; builds green. |
| OBS-003 | D1 display half — `expected_step_tokens` provenance (CER-053) | OBS | Panel shows re-sourced value + provenance label; `render_alert_prompt` ceiling fix (flex_factor); no effort-derived value in panel; builds green. Closes CER-053 display half. |
| OBS-004 | D2 — `context_current_tokens` live writer root-cause + fix (CER-054) | OBS | Root cause diagnosed; writer fires on thin-harness spawns (or idle recorded); staleness rendered; hook stays thin; suite green. Closes CER-054. |
| OBS-005 | D3 — waypoint outcome recording + render (CER-055) | OBS | NULL outcome ≠ FAIL (writer + reader); real FAIL renders FAIL; PASS-rate report uncorrupted; suite green. Closes CER-055. |
| INFRA-164 | `flex_observability.py` CLI hardening (re-homed from Phase 64) | INFRA | Re-homed; body unchanged; frontmatter updated. |
| INFRA-165 | `context_budget.py` flex_factor correctness — NaN (re-homed from Phase 64) | INFRA | Re-homed; body unchanged; frontmatter updated. |
| INFRA-167 | TypeScript parser robustness (re-homed from Phase 64) | INFRA | Re-homed; body unchanged; frontmatter updated. Sequenced before INFRA-166. |
| INFRA-166 | Fastify API route hardening (re-homed from Phase 64) | INFRA | Re-homed; body unchanged; frontmatter updated. Sequenced after INFRA-167. |
| INFRA-168 | `effortDb.ts` p90 + in-flight dedup (re-homed from Phase 64) | INFRA | Re-homed; body unchanged; frontmatter updated. |

**Build order:** OBS-001 → OBS-002 → OBS-003 → OBS-004 → OBS-005 → INFRA-164 → INFRA-165 →
INFRA-167 → INFRA-166 → INFRA-168. (INFRA-166 after INFRA-167 per Phase 64 dependency note.)

**Schema delivery:** HARNESS007 introduces no new persistent schema objects. `effort.db` gains a
more correct `outcome` column (OBS-005 value-correctness fix on the existing column — no schema change).

---

## Status

✅ SETTLED — DP1–DP6 all ✅ AGREED; story outline finalized.
