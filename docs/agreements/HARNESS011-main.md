# Agreements — HARNESS011-main · Era 3 Closeout Remediation

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS010-main` (token surgery).
**Phase key:** `HARNESS011-main` · **Rails:** INFRA, OBS
**Builds on:** `harness` (post-HARNESS010).
**Status:** ✅ SETTLED — all 5 DPs AGREED (2026-07-06).

## Why this phase exists

A backlog sweep prior to Era 3 close-out identified 15 open CER findings that reference
files present on the harness branch. Five additional CER items were found to have already
been resolved by Era 3 work but lacked resolved notes in the backlog. This phase closes
all of them before the fold, keeping the backlog clean.

Story numbering starts at INFRA-192 (main branch holds planned INFRA-186–191 for post-fold
work; harness uses 192+ to avoid merge collision at RELEASE-007).

## Decision points

### DP1 — CER-048 scope: scope_guard integration *(settled)*

**Question:** CER-048 proposes full integration (fail-closed protected-path list in
`scope_guard.py`, then retire the static Edit/Write denies once verified). How far does
this story go?

**Decision:** ✅ AGREED.

1. **INFRA-196 adds the fail-closed protected-path list to `scope_guard.py`.** A
   `PROTECTED_GLOBS` constant (same glob patterns as the static deny entries) is checked
   when no active story is found; if the write target matches a protected glob, the hook
   blocks even in fail-open mode.
2. **Static deny entries in `.claude/settings.json` are NOT retired in this phase.**
   Retirement requires end-to-end validation across the fleet; that belongs in a dedicated
   post-fold story. This phase eliminates the friction case (authorized story blocked by
   static deny) while preserving the belt-and-suspenders posture.
3. Scope fence: no changes to the story-permissions-file lookup logic; only the
   no-active-story fall-through path gains the protected-path check.

---

### DP2 — CER-006: empty primary_files fix approach *(settled)*

**Question:** `schema_validator.py` rejects an empty `primary_files: []` list, but
`story_new.py` writes that value by default on every new story. Fix the validator
(allow empty) or fix the writer (omit the field)?

**Decision:** ✅ AGREED.

Fix both ends: `story_new.py` omits `primary_files` and `touches` when they are empty
(writes the key only when the list is non-empty). `schema_validator.py` treats an absent
or empty `primary_files` as valid for `status: draft` stories; it enforces non-empty only
when `status` is not `draft`. This preserves the gate for built stories while eliminating
the false-positive on freshly scaffolded stubs.

---

### DP3 — CER-050 atomic write scope *(settled)*

**Question:** `state.json` writes are non-atomic across three writers
(`session_start.py`, `pre_tool_use.py`, `flex_build.py` CLI paths). Which get the fix?

**Decision:** ✅ AGREED.

All three writers are updated in INFRA-201. The pattern: write to a `.tmp` sibling in the
same directory, then `os.replace()` (atomic on POSIX). A shared `_atomic_write_json(path,
data)` helper is added to a new `skills/pairmode/scripts/state_utils.py` (or inlined where
the writer is self-contained). The existing `_write_state()` / `write_text()` call sites
are replaced. No change to read paths.

---

### DP4 — CER-058 investigation scope *(settled)*

**Question:** CER-058 is an investigation ("enumerate every writer of
`registered_projects`"). Does the story deliver a fix or just a diagnosis?

**Decision:** ✅ AGREED.

INFRA-198 investigates AND fixes. The investigation is a code read (grep all writers of
`registered_projects`). If a bootstrap path writes it directly, the fix routes it through
`pairmode_sync.register()` or adds a guard. The story is complete only when every write
site is either confirmed intentional (documented) or corrected. The diagnosis is recorded
as inline code comments at each write site, not in a separate doc.

---

### DP5 — Story numbering and fold conflict management *(settled)*

**Question:** Main branch already has planned INFRA-186 through INFRA-191. Using those
numbers on harness creates a merge conflict at RELEASE-007 (the fold).

**Decision:** ✅ AGREED.

New harness stories use INFRA-192+. At the fold, RELEASE-007 must include a step to
reconcile the two INFRA ranges: either renumber the main-branch planned stories (186–191)
to follow harness's highest at fold time, or absorb them if still unbuilt. This is
recorded as a constraint in the fold runbook. No action required in HARNESS011-main itself.

---

## Resulting story outline

| Story ID | Title | Rail | CER(s) |
|----------|-------|------|--------|
| INFRA-192 | Context gate edge cases and session_id safety | INFRA | CER-040, CER-041, CER-051 |
| INFRA-193 | story_new.py rail validation and empty primary_files | INFRA | CER-006, CER-010 |
| INFRA-194 | bootstrap.py ergonomics: --yes flag and effort_tracking transparency | INFRA | CER-002, CER-017 |
| INFRA-195 | PIPE_PATH redirectable via crafted state.json | INFRA | CER-009 |
| OBS-006 | phaseIndex.ts href path containment | OBS | CER-044 |
| INFRA-196 | scope_guard fail-closed protected-path list | INFRA | CER-048 |
| INFRA-197 | Architecture doc stale claims | INFRA | CER-014, CER-035 |
| INFRA-198 | registered_projects writer audit and fix | INFRA | CER-058 |
| INFRA-199 | Signal-1 detection fix and runbook verification step | INFRA | CER-059 |
| INFRA-200 | state.json atomic writes | INFRA | CER-050 |
| INFRA-201 | Backlog hygiene: mark CER-013/015/032/033/052 resolved | INFRA | CER-013, CER-015, CER-032, CER-033, CER-052 |

**Build order:** INFRA-192 → INFRA-193 → INFRA-194 → INFRA-195 → OBS-006 → INFRA-196 → INFRA-197 → INFRA-198 → INFRA-199 → INFRA-200 → INFRA-201

**Schema delivery:** No new database tables or persistent schema objects introduced.
