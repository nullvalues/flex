# Agreements — HARNESS004-main · Checkpoint as an action sequence

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS003-main` (builder/reviewer/loop-breaker/security-auditor/intent-reviewer
converted to leaf workers; generalized return contract in `worker_result.py`; all five workers in
`skills/pairmode/skills/`; new ACTIONS entries + `SCHEMA_VERSION` bump).
**Phase key:** `HARNESS004-main` · **Rail:** RESOLVER + WORKER
**Builds on:** `harness` branch, in `/mnt/work/flex-harness`.
**Status:** ✅ SETTLED — all 6 DPs AGREED; story outline finalized (2026-06-29).

> An *agreements doc* records the decisions for a phase before any story is specced. We walk each
> decision point (DP) top to bottom; once a DP is settled its **Decision** line moves from ⬜ OPEN
> to ✅ AGREED and becomes binding on the story specs.

## Why this phase exists

Today the checkpoint is a monolithic 8-step prose sequence in `CLAUDE.build.md`. The era's
no-nested-spawning invariant requires that **any multi-spawn sequence be expressed as a sequence of
resolver-emitted actions** rather than a single action that internally spawns multiple workers.
HARNESS004 decomposes the checkpoint into exactly that: a series of resolver-emitted checkpoint
actions (`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`, `checkpoint-tag`), each
a leaf worker, sequenced by a `checkpoint_step` Position field in the resolver.

After HARNESS004, a `/clear` mid-checkpoint is safe: `next-action` re-reads `checkpoint_step`
from durable state and re-emits the next uncompleted checkpoint action — the harness resumes
exactly where it was with no context reconstruction needed.

Advisory-only; NOT wired into the live `CLAUDE.build.md` until HARNESS006.

## Context (established facts)

The current checkpoint sequence in `CLAUDE.build.md` (circa HARNESS002-main):
1. Phase completion check — all stories `complete` or formally `deferred`
2. Documentation review — era/phase/story docs current
3. CER backlog review — no unaddressed Do Now items
4. Security audit — `security-auditor` subagent
5. Intent review — `intent-reviewer` subagent
6. Build gate — `pytest` passes
7. Checkpoint tag — `git tag cp-<phase-key>`
8. Push — `git push origin harness --tags`

Steps 4 and 5 spawn subagents today. Steps 1–3, 6–8 are prose checks in the orchestrator.
The era invariant requires all of these to be resolver-emitted actions, each a leaf, so the
harness holds no checkpoint progress state beyond what `next-action` can reconstruct.

Steps 7 and 8 (tag + push) are operator-verifiable mechanical actions. They may be thin
inline operations rather than full worker spawns (see DP3).

## Decision points

### DP1 — What `checkpoint_step` tracks *(settled)*

**Question:** How does the resolver know which checkpoint step to emit next?

**Decision:** ✅ AGREED (2026-06-29).

1. **A `checkpoint_step` field in `Position`** (read from durable state — e.g. a key in
   `state.json` written by each checkpoint worker on completion) tracks which checkpoint steps
   are complete. It is a set or ordered list of completed step IDs (strings).
2. `infer_position` reads `checkpoint_step` from `state.json["checkpoint_step"]` (a list of
   completed step IDs, empty or absent if no checkpoint is in progress, cleared after a
   successful tag).
3. When the resolver's current story is complete and a checkpoint is warranted
   (all stories in the phase are complete/deferred), `resolve_next_action` emits the next
   uncompleted checkpoint action from the ordered sequence: `checkpoint-security` →
   `checkpoint-intent` → `checkpoint-docs` → `checkpoint-tag`.
4. Each checkpoint worker writes its step ID to `state.json["checkpoint_step"]` on completion.
   The harness reads `next-action` again; the resolver re-derives position and emits the
   next step. This is the lossless resume property.
5. `state.json["checkpoint_step"]` is cleared (set to `[]` or deleted) after `checkpoint-tag`
   succeeds, or when the resolver detects a new phase has begun.

---

### DP2 — The checkpoint worker decomposition *(settled)*

**Question:** Which checkpoint steps become resolver-emitted leaf workers, and which stay prose?

**Decision:** ✅ AGREED (2026-06-29).

1. **Four resolver-emitted checkpoint actions:**
   - `checkpoint-security` — spawns the security-auditor leaf worker (WORKER-008); returns
     `REVIEW-RESULT`. The resolver emits this step first.
   - `checkpoint-intent` — spawns the intent-reviewer leaf worker (WORKER-009); returns
     `REVIEW-RESULT`.
   - `checkpoint-docs` — spawns a new docs-review leaf worker (WORKER-011); returns
     `REVIEW-RESULT`. The docs review step has no existing leaf worker (the security-auditor
     and intent-reviewer leaves handle their specific concerns; a separate docs-review worker
     handles documentation currency).
   - `checkpoint-tag` — a thin mechanical action: the harness runs `git tag cp-<phase-key>`
     and `git push` inline (no worker spawn needed for a deterministic one-liner). The resolver
     emits `checkpoint-tag` as a signal; the harness executes the tag + push directly.
2. **Phase completion check (step 1), CER backlog review (step 3), and build gate (step 6)**
   become **pre-checkpoint resolver guards** rather than leaf workers. `infer_position` checks
   these deterministically (all stories complete/deferred; no Do Now items in the CER backlog
   file; `pytest` exit code). If any guard fails, the resolver emits `await-user` with the
   specific reason rather than entering the checkpoint sequence.
3. **Push (step 8)** is bundled into the `checkpoint-tag` harness execution (tag + push is a
   single thin operation). No separate `checkpoint-push` action.
4. **The resolver emits checkpoint actions only when all pre-checkpoint guards pass.**

---

### DP3 — `checkpoint-tag` as a thin harness action (not a leaf worker) *(settled)*

**Question:** Should `checkpoint-tag` spawn a leaf worker or be executed inline by the harness?

**Decision:** ✅ AGREED (2026-06-29).

1. **Inline harness action.** `checkpoint-tag` is deterministic (`git tag` + `git push`); no LLM
   judgment is involved; no plugin procedure skill is needed. The harness executes it as a
   two-line shell operation when the resolver emits `checkpoint-tag`.
2. **`checkpoint-tag` is still registered in `ACTIONS`** so the resolver's state machine can emit
   it and the freeze/action-grammar tests can pin it. It simply has no associated leaf worker.
3. **`_SPAWN_ACTIONS` exclusion.** `checkpoint-tag` is NOT in `_SPAWN_ACTIONS` (no model, no
   worker spawn). The harness special-cases it as a direct shell action.
4. All other checkpoint actions (`checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`)
   are in `_SPAWN_ACTIONS` (they spawn leaf workers with a model).

---

### DP4 — New resolver actions for checkpoint sequence *(settled)*

**Question:** Which new actions join `ACTIONS` and `_SPAWN_ACTIONS`?

**Decision:** ✅ AGREED (2026-06-29).

1. **New entries in `ACTIONS`:**
   - `checkpoint-security`
   - `checkpoint-intent`
   - `checkpoint-docs`
   - `checkpoint-tag`
2. **`_SPAWN_ACTIONS` additions:** `checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`
   (each spawns a leaf worker with a model). `checkpoint-tag` is NOT in `_SPAWN_ACTIONS`.
3. **`SCHEMA_VERSION` bumped to 3** (from 2, set in HARNESS003) when these actions are added.
4. The existing `checkpoint` action (already in `ACTIONS`) becomes deprecated — it was a
   catch-all placeholder. It is removed from `ACTIONS` in RESOLVER-007 and its handling in
   `resolve_next_action` is replaced by the four checkpoint sub-actions.
   **Note:** removing `checkpoint` is not a CLI-surface change (it is not a `flex_build.py`
   command flag); it IS an action grammar change, captured by the `SCHEMA_VERSION` bump.

---

### DP5 — Durable progress tracking for checkpoint steps *(settled)*

**Question:** Where does `checkpoint_step` progress live, and who writes it?

**Decision:** ✅ AGREED (2026-06-29).

1. **`state.json["checkpoint_step"]`** — a list of step-IDs that have completed in the current
   checkpoint run (e.g. `["checkpoint-security", "checkpoint-intent"]`). Written by each
   checkpoint worker (or by the harness for `checkpoint-tag`) on successful completion.
2. **The resolver reads this field via `infer_position`** — pure-read, no writes in
   `next_action.py`. Writing is the harness's / worker's responsibility.
3. **Cleared on new phase or tag success.** `infer_position` detects "current phase changed"
   (a new story is the active story) and treats `checkpoint_step` as empty.
4. **`state.json` writes are NOT in `next_action.py`** (pure-read invariant). The checkpoint
   workers (leaf) and the harness (for `checkpoint-tag`) own the writes.

---

### DP6 — Scope fence *(settled)*

**Question:** What is explicitly in/out of HARNESS004?

**Decision:** ✅ AGREED (2026-06-29).

**In:** `checkpoint_step` Position field; new checkpoint `ACTIONS` entries + `SCHEMA_VERSION` bump;
`resolve_next_action` checkpoint routing (pre-checkpoint guards + step sequencing); WORKER-011
docs-review leaf worker; RESOLVER-007 (checkpoint step tracker + action vocabulary);
RESOLVER-008 (checkpoint action routing); WORKER-012 (isolation suite). Advisory-only.

**Out:** Spec-writer (HARNESS005); the flip (HARNESS006); Phase 64 / observability (HARNESS007);
housekeeper (HARNESS008); wiring into live `CLAUDE.build.md` (HARNESS006).

---

## Resulting story outline (RESOLVER + WORKER rail — finalized)

| Story ID | Title | Rail | Acceptance gist |
|----------|-------|------|-----------------|
| RESOLVER-007 | Checkpoint step tracker — `checkpoint_step` Position field + action vocabulary | RESOLVER | `infer_position` reads `checkpoint_step` from `state.json`; new checkpoint actions in `ACTIONS` + `_SPAWN_ACTIONS`; old `checkpoint` action removed; `SCHEMA_VERSION` → 3; pure-read. |
| WORKER-011 | Checkpoint docs-review leaf worker | WORKER | Docs-review procedure in `skills/pairmode/skills/checkpoint-docs/procedure.md`; thin shell; returns `REVIEW-RESULT`; isolation tested with injected verdicts. |
| RESOLVER-008 | Checkpoint action routing — pre-checkpoint guards + step sequencing | RESOLVER | `resolve_next_action` pre-checkpoint guards (phase complete? CER clear? build gate?); checkpoint step sequencing; emits the correct next checkpoint action; `checkpoint-tag` handled inline; pure-read. |
| WORKER-012 | HARNESS004 isolation suite | WORKER | Checkpoint step sequence deterministic matrix: pre-guard failures → `await-user`; each step emitted in order; `checkpoint-tag` emitted after all others; `checkpoint_step` cleared on tag; all injected — no live API call. |

**Build order:** RESOLVER-007 → WORKER-011 → RESOLVER-008 → WORKER-012.

**Schema delivery:** HARNESS004 introduces no new persistent schema objects. `state.json` gains
the `checkpoint_step` key — this is an existing ephemeral state file, not a new schema object.

---

## Status

✅ SETTLED — DP1–DP6 all ✅ AGREED; story outline finalized.
