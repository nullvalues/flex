# Agreements — HARNESS005-main · Spec-writer as a leaf worker

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS004-main` (checkpoint decomposed into `checkpoint-security`,
`checkpoint-intent`, `checkpoint-docs`, `checkpoint-tag`; `checkpoint_step` Position field;
docs-review leaf worker; checkpoint isolation suite).
**Phase key:** `HARNESS005-main` · **Rail:** WORKER + RESOLVER touch
**Builds on:** `harness` branch, in `/mnt/work/flex-harness`.
**Status:** ✅ SETTLED — all 5 DPs AGREED; story outline finalized (2026-06-29).

> An *agreements doc* records the decisions for a phase before any story is specced. We walk each
> decision point (DP) top to bottom; once a DP is settled its **Decision** line moves from ⬜ OPEN
> to ✅ AGREED and becomes binding on the story specs.

## Why this phase exists

The build loop has one remaining orchestrator-held step that is not yet a resolver-emitted leaf
worker: **spec-writing**. Today the orchestrator detects that a story has a stub spec and spawns
a Plan subagent inline, embedded in `CLAUDE.build.md` prose. This violates the era invariant
("harness holds nothing not reconstructable from `next-action`") — if the orchestrator clears
mid-spec, the spec-writing step is lost.

HARNESS005 converts spec-writing to the same resolver-emitted leaf-worker pattern: the resolver
detects a story with a stub spec (`needs_spec` Position flag), emits `spawn-spec-writer`, and the
harness spawns the spec-writer leaf worker, which runs the Plan procedure in disposable context
and returns `SPEC-RESULT`. The loop becomes fully resolver-driven: every action the harness takes
is emitted by `next-action`.

Advisory-only; NOT wired into the live `CLAUDE.build.md` until HARNESS006.

## Context (established facts)

- **Current spec mode** in `CLAUDE.build.md` (§ Spec mode): triggered by user command
  `"spec next phase [intent]"` or `"spec phase N: [intent]"`. The orchestrator: determines the
  phase number, reads the active era, spawns a Plan subagent, presents a draft, waits for
  `"commit spec"`, then scaffolds the files with `phase_new.py` / `story_new.py`.
- **`needs_spec` detection today:** not formalized — the orchestrator checks whether the next
  story is a stub (has no `## Ensures` section, or has a `## Instructions` section with
  placeholder text). After HARNESS005, this check lives in `infer_position`.
- **`SPEC-RESULT` type** defined in `worker_result.py` (HARNESS003-main WORKER-004):
  `{type: "SPEC-RESULT", story_id: str, status: "done"|"revised"}`.
- **`spawn-spec-writer`** does not yet exist in `ACTIONS`. It is the RESOLVER touch of this phase.
- **The spec-writer procedure** wraps today's Plan-subagent logic: read the active era + the
  relevant story stub + the phase doc → produce an expanded story spec (Ensures, Instructions,
  Tests, Out of scope) → write it to disk. It does NOT replace `phase_new.py` / `story_new.py`
  scaffolding (that remains a one-time operator action, not part of the resolver loop).

## Decision points

### DP1 — What `needs_spec` means and when the resolver emits `spawn-spec-writer` *(settled)*

**Question:** How does the resolver detect a story needs spec-writing, and when does it emit
the action?

**Decision:** ✅ AGREED (2026-06-29).

1. **`needs_spec` in Position:** `infer_position` sets `needs_spec = True` when the next story
   has `status: planned` AND its `## Ensures` section is absent or contains only a placeholder
   stub (heuristic: fewer than 5 non-blank lines in the Ensures block, or the literal text
   "TODO"). This is a pure-read heuristic — no writes in `infer_position`.
2. **Emit `spawn-spec-writer` instead of `spawn-builder` when `needs_spec` is True.** The resolver
   does not emit `spawn-gate-worker` or `spawn-builder` until the spec exists. This is a Row-2
   branch: if `needs_spec`, emit `spawn-spec-writer`; else proceed as today.
3. **After `spawn-spec-writer` returns `SPEC-RESULT` with `status: "done"`**, the harness re-runs
   `next-action`. `infer_position` re-checks the story file; `needs_spec` is now False (the
   spec was expanded by the worker); the resolver emits `spawn-gate-worker` or `spawn-builder`
   as normal.
4. **If `SPEC-RESULT` returns `status: "revised"`**, the harness shows the result to the user and
   emits `await-user` (the spec-writer flagged it needs human review). The orchestrator surfaces
   the result and stops — the user iterates.

---

### DP2 — What the spec-writer leaf worker does *(settled)*

**Question:** Precisely what does the spec-writer worker compute, and what does it write?

**Decision:** ✅ AGREED (2026-06-29).

1. **Procedure source:** `skills/pairmode/skills/spec-writer/procedure.md` — the same
   plugin-versioned skill pattern as all other leaf workers. The procedure wraps the Plan-subagent
   logic from today's spec mode, adapted for a single-story scope (not a full phase spec).
2. **Inputs (bounded — DP1.3 equivalent):** the story stub file (`docs/stories/<RAIL>/<ID>.md`),
   the phase doc (`docs/phases/phase-<key>.md`), the active era doc, and one recent complete
   story as a format exemplar. No accumulated orchestrator context; no prior-attempt transcripts.
3. **Output:** the spec-writer expands the story's `## Ensures`, `## Instructions`, `## Tests`,
   and `### Out of scope` sections in place (writing to the story file). It returns `SPEC-RESULT`
   on stdout. The in-place edit is the spec-writer's only write target.
4. **No `phase_new.py` / `story_new.py` involvement.** Scaffolding (creating the phase doc and
   stub story files) remains an operator step outside the resolver loop. The spec-writer operates
   only on an already-scaffolded stub story.
5. **The spec-writer does NOT write the phase doc or any file outside the single story file.**
   If it touches other files, that is a scope violation. Declared in the story's `primary_files`.

---

### DP3 — New resolver action *(settled)*

**Question:** What changes in `next_action.py`?

**Decision:** ✅ AGREED (2026-06-29).

1. **`spawn-spec-writer` added to `ACTIONS` and `_SPAWN_ACTIONS`.** The spec-writer runs at
   the opus tier (same as loop-breaker); it carries a model parameter.
2. **`SCHEMA_VERSION` bumped to 4** (from 3, set in HARNESS004) when this action is added.
3. **Row-2 branch in `resolve_next_action`:** when `position["needs_spec"]` is True, emit
   `spawn-spec-writer` with `scalar=story_id`. This is a pure-read addition; no other rows change.
4. The resolver stays pure-read (no writes). The spec-writer leaf worker writes the story file.

---

### DP4 — Isolation testing *(settled)*

**Question:** How do we test the spec-writer, whose output is LLM-generated spec text?

**Decision:** ✅ AGREED (2026-06-29).

1. **Same deterministic-scaffold model as HARNESS002/003.** Tests assert:
   - `infer_position` on a stub story → `needs_spec: True`; on a complete story → `needs_spec: False`.
   - `resolve_next_action` on a `needs_spec: True` position → emits `spawn-spec-writer`.
   - `resolve_next_action` after `SPEC-RESULT{status: "done"}` injected → emits `spawn-gate-worker`
     or `spawn-builder` (re-evaluates as normal).
   - The spec-writer shell/procedure loads only its bounded input set (the four declared inputs —
     no accumulated loop state). Negative assertion on source text.
   - `SPEC-RESULT` grammar round-trips via `worker_result.py`.
2. **No live API call.** The LLM spec quality is validated by manual review and the subsequent
   build/review loop.
3. **WORKER-014 consolidates** all spec-writer isolation tests.

---

### DP5 — Scope fence *(settled)*

**Question:** What is explicitly in/out of HARNESS005?

**Decision:** ✅ AGREED (2026-06-29).

**In:** `needs_spec` Position field; `spawn-spec-writer` action + Row-2 branch in resolver;
spec-writer procedure skill + thin shell; `SCHEMA_VERSION` bump to 4; full isolation suite
(WORKER-014). Advisory-only.

**Out:** Phase scaffolding (`phase_new.py` / `story_new.py`) — operator action, not changed.
The flip (HARNESS006). Observability (HARNESS007). Housekeeper (HARNESS008). Multi-story spec
generation (the spec-writer operates on one story at a time). Any change to `story_new.py`'s
stub format.

---

## Resulting story outline (WORKER + RESOLVER touch — finalized)

| Story ID | Title | Rail | Acceptance gist |
|----------|-------|------|-----------------|
| RESOLVER-009 | `spawn-spec-writer` action + `needs_spec` Position flag | RESOLVER | `infer_position` detects stub story → `needs_spec: True`; `resolve_next_action` Row-2 branch → `spawn-spec-writer`; `ACTIONS` + `_SPAWN_ACTIONS` entry; `SCHEMA_VERSION` → 4; pure-read. |
| WORKER-013 | Spec-writer leaf worker | WORKER | Procedure in `skills/pairmode/skills/spec-writer/procedure.md`; thin shell; bounded inputs (stub story + phase doc + era doc + exemplar); writes expanded story spec in place; returns `SPEC-RESULT`; advisory-only. |
| WORKER-014 | HARNESS005 isolation suite | WORKER | `needs_spec` detection; `spawn-spec-writer` routing; `SPEC-RESULT` routing (done → proceed, revised → await-user); shell input-bound guard; grammar round-trip; no live API call. |

**Build order:** RESOLVER-009 → WORKER-013 → WORKER-014.

**Schema delivery:** HARNESS005 introduces no new persistent schema objects. The spec-writer
writes to the existing story file (already scaffolded); no new state.json keys.

---

## Status

✅ SETTLED — DP1–DP5 all ✅ AGREED; story outline finalized.
