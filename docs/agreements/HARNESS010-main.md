# Agreements — HARNESS010-main · Token surgery

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS009-main` (write-path determinism; record-checkpoint-step; JSON verdict).
**Phase key:** `HARNESS010-main` · **Rails:** HARNESS, WORKER
**Builds on:** `harness` (post-HARNESS009).
**Status:** ✅ SETTLED — all 4 DPs AGREED (2026-07-04).

## Why this phase exists

A cold-eyes review (2026-07-04) identified ~1,800 tokens per build cycle that are either
dead weight or redundant across the always-loaded policy files. The dominant problem: `CLAUDE.md`
carries the full 10-item reviewer checklist (~1,100 tokens) and multi-paragraph hook exception
footnotes (~600 tokens) into every session — build sessions never use either. Additionally,
`CLAUDE.build.md` contains two prose paragraphs describing checkpoint sequencing and spec mode
that duplicate what the resolver already enforces via emitted actions.

This phase is editorial. No logic changes. All cuts are in `.md` source files and their
corresponding `.j2` templates.

## Context

- **`CLAUDE.md`** is loaded unconditionally into every session (reviewer and build). It
  currently contains: session-mode routing prose, the full 10-item reviewer checklist with
  hook exception footnotes, loop-breaker instructions, and review output format.
- **`reviewer/procedure.md`** (the leaf worker's procedure skill) also carries the reviewer
  checklist — either as a mirror or a near-duplicate. After this phase, it owns the canonical
  copy.
- **Hook exception footnotes** in `CLAUDE.md` checklist items 1–3 explain the dispatch
  logic of `pre_tool_use.py`, `post_tool_use.py`, and `session_start.py` in multi-paragraph
  form (~600 tokens). Their purpose is to prevent a reviewer from incorrectly flagging thin
  delegation as CRITICAL. An inline comment in each hook script achieves the same gate.
- **"Session modes" section** in `CLAUDE.md` lists patterns like "Build Phase N" / "Fix
  story N.X" as build-mode triggers. This is an Era 001/002 vestige — build mode is now an
  explicit `CLAUDE.build.md` session, not a natural-language trigger detected from input.
- **`CLAUDE.build.md` Checkpoint and Spec mode paragraphs** describe what to do when the
  resolver emits `checkpoint-*` or `spawn-spec-writer` actions. After HARNESS009's wiring
  update, the checkpoint paragraph will include the `record-checkpoint-step` call. The
  spec-mode paragraph is pure duplication of what the resolver already emits. Both can be
  reduced.
- **Builder and reviewer procedures** each end with a "Non-negotiables" section (~5 items)
  that restates rules already stated in the body of the same file.
- **Template files** are the canonical sources for all bootstrapped docs:
  `skills/pairmode/templates/CLAUDE.md.j2`, `CLAUDE.build.md.j2`,
  `skills/pairmode/templates/agents/builder.md.j2`,
  `skills/pairmode/templates/agents/reviewer.md.j2` (or the procedure skill equivalents).
  Any change to the project files must also be made to the corresponding template.

## Decision points

### DP1 — Canonical checklist location *(settled)*

**Question:** After deduplication, where does the reviewer checklist live — `CLAUDE.md` or
the reviewer procedure? What does the other file contain?

**Decision:** ✅ AGREED (2026-07-04).

1. **The reviewer procedure (`reviewer/procedure.md`) owns the canonical checklist.** It is
   the skill loaded by the reviewer leaf worker. Keeping the checklist there means it is only
   in context when a reviewer session is active — not in every build session.
2. **`CLAUDE.md` retains a one-line reference:** `"Apply the checklist in the reviewer
   procedure skill. See \`skills/pairmode/skills/reviewer/procedure.md\`."` This is sufficient
   for human reviewers to locate the policy; the full 10-item list is not needed inline.
3. **The hook exception footnotes move out of `CLAUDE.md` entirely.** Each hook script
   (`pre_tool_use.py`, `post_tool_use.py`, `session_start.py`) gains a one-line inline
   comment explaining it is a thin dispatcher (`# thin dispatcher — see context_budget.py /
   scope_guard.py / session_reset.py`). The reviewer procedure retains a brief note that
   named modules are documented thin-delegation exceptions, without the full call-by-call prose.
4. **The "Session modes" section in `CLAUDE.md` is removed.** Replaced with one sentence:
   "Build sessions are governed by `CLAUDE.build.md`; all other input applies the reviewer role."

---

### DP2 — `CLAUDE.build.md` cuts *(settled)*

**Question:** Which paragraphs in `CLAUDE.build.md` can be removed after HARNESS009?

**Decision:** ✅ AGREED (2026-07-04).

1. **The "Spec mode" paragraph is removed.** It describes what to do when the resolver emits
   `spawn-spec-writer` — but the resolver emits this action; the orchestrator only needs to
   know "spawn the leaf worker for `a.action`." The paragraph adds no information the action
   object doesn't already provide.
2. **The "Checkpoint" paragraph is retained but reduced.** After HARNESS009 it will already
   include `record-checkpoint-step`. In HARNESS010 it is trimmed to the minimum: the
   `record-checkpoint-step` call and the `checkpoint-tag` git command. The explanatory prose
   ("The resolver emits checkpoint-security, checkpoint-intent...") is removed — the
   orchestrator learns this from the action object, not from prose.
3. **`CLAUDE.build.md.j2`** is updated identically.

---

### DP3 — Procedure Non-negotiables *(settled)*

**Question:** Should the "Non-negotiables" sections at the end of builder and reviewer
procedures be removed, condensed, or kept?

**Decision:** ✅ AGREED (2026-07-04).

1. **Removed from both procedures.** Every item in the Non-negotiables section is already
   stated in the body of the same file (return format, commit format, no autonomous push).
   Restating them as a separate section adds ~5 items × 2 procedures of redundant prose with
   no enforcement benefit.
2. A single sentence is added to the return-format section of each procedure:
   "Deviating from this format invalidates the result." This covers the contract without the
   separate section.
3. **Template files updated** (`builder.md.j2` and `reviewer.md.j2` / procedure equivalents).

---

### DP4 — Scope fence and regression verification *(settled)*

**Question:** How do we verify the reviewer still works correctly after checklist moves and cuts?

**Decision:** ✅ AGREED (2026-07-04).

**In:**
- `CLAUDE.md`: remove Session modes section, remove inline checklist (replace with reference),
  remove hook exception footnote prose (replace with one-line pointer), add "Build sessions →
  CLAUDE.build.md" routing sentence.
- `CLAUDE.build.md`: remove Spec mode paragraph, trim Checkpoint paragraph to just the
  `record-checkpoint-step` call + checkpoint-tag command.
- Builder procedure: remove Non-negotiables section, add one-sentence contract note.
- Reviewer procedure: ensure it holds the full canonical checklist (migrate from CLAUDE.md if
  not already present); remove Non-negotiables section, add one-sentence contract note.
- All corresponding `.j2` template files updated in the same commit.
- Each hook script (`pre_tool_use.py`, `post_tool_use.py`, `session_start.py`) gains the
  inline thin-dispatcher comment.

**Regression check:** the reviewer procedure after this change must pass a manual checklist
walk — verify all 10 items are present and complete in the procedure file before marking the
story done. A documentation story: no test file required, but the checklist completeness
check is the acceptance gate.

**Out:**
- Any logic changes to hook scripts (hooks get a comment only, no logic change).
- Any changes to `context_budget.py`, `scope_guard.py`, `session_reset.py`.
- Any changes to the resolver or state machine.

---

## Resulting story outline

| Story ID | Title | Rail | Acceptance gist |
|----------|-------|------|-----------------|
| HARNESS-004 | `CLAUDE.md` + `CLAUDE.build.md` token surgery | HARNESS | Session modes removed; checklist replaced by reference; hook footnotes → one-liner + inline comments; Spec mode paragraph cut; Checkpoint paragraph trimmed; `.j2` templates updated; suite green. |
| WORKER-015 | Builder + reviewer procedure Non-negotiables removal | WORKER | Non-negotiables sections removed from both procedures; one-sentence contract note added; reviewer procedure verified to hold full canonical checklist; `.j2` templates updated; suite green. |

**Build order:** HARNESS-004 → WORKER-015 (WORKER-015 verifies the reviewer procedure has
the full checklist before removing Non-negotiables, so HARNESS-004 must land first to
establish what moved).

**Schema delivery:** no persistent schema objects introduced. Documentation-only changes.

**Exception (no management UI required):** no new database tables.
