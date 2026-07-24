# Agreements — HARNESS008-main · Housekeeper consolidation

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS007-main` (observability refactor complete; SPA reads resolver state model;
D1/D2/D3 defects closed; Phase 64 hardening done; fleet on the thin harness).
**Phase key:** `HARNESS008-main` · **Rail:** RESOLVER
**Builds on:** `main` (post-fold).
**Status:** ✅ SETTLED — all 5 DPs AGREED; story outline finalized (2026-06-29).

> An *agreements doc* records the decisions for a phase before any story is specced.

## Why this phase exists

The Era 002 close-out surfaced a textbook case for a missing system: nothing currently catches
"a built story still marked `planned`." Eight built stories were found in that state during the
close-out (INFRA-106/107/108/109/110/111, INFRA-148, BUILD-029 — all with `feat(story-X)` commits,
none marked `complete`). Similarly, the era table was stale (phases 61/62/66/70 shown `planned`
but complete), and a deferred Phase 64 was being returned as `current-phase` (CER-056).

HARNESS008 folds scattered index-integrity logic into the resolver's read-model as a first-class
graph-invariant checker: a pure-read `index_integrity.py` module exposed via an additive
`flex_build.py check-index` CLI. The checker detects the four classes of drift found in practice.
The CER-056 deferred-as-inactive rule is implemented once and shared between the checker and
`infer_position`.

## Context (established facts)

- **CER-056 (Do Later):** `next-action`'s index read treats `deferred`/`backlog` phases as active.
  `infer_position` reads `current-phase` from the index and may return a deferred phase as active.
  The fix is: treat only `complete` phases as inactive in the "find the first non-complete phase"
  scan (the current behavior) AND treat `deferred`/`backlog` as inactive too.
- **`next_story.py`** has commit-authority helpers (`_git_log_oneline`, `_has_story_commit`) that
  can detect whether a story has a `feat(story-ID)` commit. `index_integrity.py` reuses these.
- **Existing index parsers** in `next_story.py` / `next_action.py` parse the phase index and
  story frontmatter. `index_integrity.py` reuses them (no duplicated parse logic).
- **Status drift:** a `feat(story-ID)` commit in `git log` but story `status != complete/deferred`
  is the canonical signal. Eight stories had this drift in Era 002.
- **Cross-link consistency:** every index phase row should have a phase file; every story's
  `phase` frontmatter should name an existing phase doc; every era's phase table should match
  index truth.
- **Orphan story files:** a file at `docs/stories/<RAIL>/<ID>.md` not referenced in any phase
  doc's Stories table.
- **Deferred without section:** a story marked `deferred` whose phase doc lacks a
  `## Deferred stories` section naming it (required by the phase-continuity policy).
- **The OBS-001 `resolver-state --json` command** (HARNESS007) applies the deferred-as-inactive
  rule to its index section. HARNESS008 moves that rule into `index_integrity.py` so both
  `check-index` and `infer_position` share the same implementation.
- **This phase may merge into `HARNESS001-main`** per the era doc ("May merge into HARNESS001-main
  if it stays small"). It did not — the forcing function arrived late (Era 002 close-out), and
  HARNESS001 was complete before the scope was fully understood.

## Decision points

### DP1 — The four graph invariants *(settled)*

**Question:** What exactly does `index_integrity.py` check?

**Decision:** ✅ AGREED (2026-06-29).

1. **Status drift** — a story file with a `feat(story-<ID>)` commit in `git log` but
   `status` frontmatter is not `complete` or `deferred`. (Exact match: the commit subject line
   contains `feat(story-<ID>)` where `<ID>` matches the story's `id` frontmatter.)
2. **Cross-link consistency** — four sub-checks:
   (a) Every phase row in `docs/phases/index.md` has a corresponding `docs/phases/phase-<key>.md`.
   (b) Every story's `phase` frontmatter names an existing `docs/phases/phase-<key>.md`.
   (c) Every era's phase table (in `docs/eras/*.md`) matches the index truth for phase status.
   (d) Deferred/backlog phases are treated as inactive in all "current-phase" derivations (CER-056).
3. **Orphan story files** — a `docs/stories/<RAIL>/<ID>.md` not referenced in any phase doc's
   `| ID |` table row.
4. **Deferred without section** — a story with `status: deferred` whose phase doc file does not
   contain a `## Deferred stories` section that names that story's ID.

---

### DP2 — Pure-read; no auto-repair *(settled)*

**Question:** Does `index_integrity.py` auto-fix drifted status, or only report?

**Decision:** ✅ AGREED (2026-06-29).

1. **Reporter only, no auto-repair.** `index_integrity.py` emits a structured violations list;
   it does not mutate any story file, phase doc, or index. The operator (or a future dedicated
   repair tool) acts on the report.
2. **`flex_build.py check-index` exits non-zero on any violation, zero on a clean graph.**
   The non-zero exit makes it composable in CI or a pre-checkpoint gate (even though it is
   advisory now — no checkpoint wiring in this phase).
3. **Pure-read invariant:** `grep` in the isolation suite asserts no `write_text` / `json.dump`
   in `index_integrity.py`.

---

### DP3 — CER-056 shared deferred-as-inactive rule *(settled)*

**Question:** How is CER-056 fixed exactly, and where does the rule live?

**Decision:** ✅ AGREED (2026-06-29).

1. **`index_integrity.py` owns the canonical deferred-as-inactive helper** — a small function
   `is_phase_inactive(status: str) -> bool` that returns True for `complete`, `deferred`,
   `backlog`. This is the single source.
2. **`next_action.py`'s `infer_position`** imports and calls this helper (making `index_integrity`
   a dependency of `next_action`). This resolves CER-056: `infer_position` no longer treats
   `deferred` phases as active.
3. **`OBS-001`'s `resolver-state --json`** index section also uses this helper (it already
   applied the rule; RESOLVER-011 ensures it reads from `index_integrity.py`'s implementation
   rather than a local copy).
4. **The resolver stays pure-read.** `infer_position` imports a helper; no writes are added.
   The resolver's routing is unaffected (the checker is advisory).

---

### DP4 — Isolation testing approach *(settled)*

**Question:** How are the graph-invariant checks tested?

**Decision:** ✅ AGREED (2026-06-29).

1. **Synthetic project trees** via `resolver_fixtures` (`make_resolver_project`) — one fixture
   per violation class triggers exactly that violation; a clean fixture → exit 0, empty violations.
2. **Synthetic git logs** — mock `_git_log_oneline` (or use `resolver_fixtures` to write a
   synthetic `.git/COMMIT_EDITMSG` journal) so the status-drift check works without a real git
   history.
3. **CER-056 fixture:** a synthetic project with a `deferred` phase file → `infer_position`
   treats it as inactive; `check-index` cross-link sub-check (d) passes.
4. **The deferred-as-inactive shared rule** is tested by asserting that both `check-index` and
   `infer_position` agree on the same synthetic deferred-phase fixture.
5. **No network, no live git-history dependence** in any test.

---

### DP5 — Scope fence *(settled)*

**Question:** What is explicitly in/out of HARNESS008?

**Decision:** ✅ AGREED (2026-06-29).

**In:** `index_integrity.py` module with the four invariants; `flex_build.py check-index` CLI
(additive); CER-056 deferred-as-inactive shared helper; `infer_position` updated to use helper;
RESOLVER-010 (module + CLI) and RESOLVER-011 (resolver integration + isolation suite). Advisory
CLI only — no hard checkpoint gating in this phase.

**Out:** Auto-repair of drifted status. Hard-gating the checkpoint on `check-index` (future).
Observability integration of `check-index` results in the SPA (HARNESS007 scope is closed).
Any change to `effort.db` or the effort tracking system. Any new action in `ACTIONS`.

---

## Resulting story outline (RESOLVER rail — finalized)

| Story ID | Title | Rail | Acceptance gist |
|----------|-------|------|-----------------|
| RESOLVER-010 | `check-index` graph-invariant checker (`index_integrity.py` + CLI) | RESOLVER | Four invariants; pure-read; `flex_build.py check-index` exits non-zero on violations; deferred-as-inactive helper; per-violation-class fixtures; freeze green; suite green. |
| RESOLVER-011 | Resolver read-model integration + housekeeper isolation suite | RESOLVER | `infer_position` uses shared deferred-as-inactive helper (CER-056); resolver pure-read; both CLI + resolver agree on deferred fixture; RESOLVER-004 matrix unchanged; consolidated isolation suite; suite green. |

**Build order:** RESOLVER-010 → RESOLVER-011.

**Schema delivery:** HARNESS008 introduces no new persistent schema objects.

---

## Status

✅ SETTLED — DP1–DP5 all ✅ AGREED; story outline finalized.
