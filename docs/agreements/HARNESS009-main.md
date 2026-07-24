# Agreements — HARNESS009-main · Write-path determinism

**Parent era:** [Era 003 — Orchestrator as harness](../eras/003-flex-orchestrator-as-harness.md)
**Parent phase:** `HARNESS008-main` (housekeeper complete; index_integrity.py + CER-056 fix).
**Phase key:** `HARNESS009-main` · **Rails:** RESOLVER, WORKER
**Builds on:** `harness` (post-HARNESS008).
**Status:** ✅ SETTLED — all 4 DPs AGREED (2026-07-04).

> An *agreements doc* records the decisions for a phase before any story is specced.

## Why this phase exists

Era 003 moved all transition *reads* into deterministic code. Two write-path gaps survived
the era: the orchestrator LLM writes `checkpoint_step` into `state.json` by prose compliance,
and gate worker verdicts are parsed from free-form text with a `partition(":")` split. Both
gaps are violations of the "resolver owns all durable state" invariant — they make resolver
correctness depend on LLM prose adherence rather than code enforcement.

If the orchestrator writes a wrong checkpoint step ID, the resolver re-emits the same
checkpoint action forever. If a gate worker returns a non-standard delimiter, the resolver
silently reads the gate as clean. These are silent-failure modes in the load-bearing control path.

Two lower-priority findings (the `needs_spec` magic constant and a commit-format check CLI)
are captured in the CER backlog as Do Later — they are not blocking and do not affect resolver
correctness.

## Context

- **`checkpoint_step` writer:** `next_action.py:748–758` reads `state.json["checkpoint_step"]`
  to sequence the four checkpoint sub-actions. No `flex_build.py` CLI writes this key — the
  orchestrator LLM is expected to append the correct step ID string after each checkpoint
  worker exits. There is no validation at write time.
- **Known step IDs:** `checkpoint-security`, `checkpoint-intent`, `checkpoint-docs`,
  `checkpoint-tag` — these are `_CHECKPOINT_SEQUENCE` in `next_action.py:168–173`.
- **Gate verdict parser:** `next_action.py` (`parse_worker_verdict_text`) splits on `": "`
  to extract `gate: verdict` pairs. A gate worker returning `schema:block:reason` (no space)
  or `schema — block` (wrong separator) is silently skipped, causing that gate to appear clean.
- **Gate verdict grammar (current):** workers emit lines like `schema: block — reason text` or
  `schema: clean`. Three gates: `schema`, `auth`, `stub`.
- **`CLAUDE.build.md`** currently handles checkpoint sequencing in two sentences of prose
  ("Execute each leaf worker as dispatched. checkpoint-tag: run `git tag ...`"). This prose
  does not include a `record-checkpoint-step` call because no such CLI exists.
- **`CLAUDE.build.md.j2`** is the canonical template source; any CLAUDE.build.md change must
  also update the template.

## Decision points

### DP1 — `record-checkpoint-step` contract *(settled)*

**Question:** What exactly does `flex_build.py record-checkpoint-step <step-id>` do, and what
are its invariants?

**Decision:** ✅ AGREED (2026-07-04).

1. **Atomically appends** the step ID to `state.json["checkpoint_step"]` (read → append →
   write, no partial writes). Creates the key as `[]` if absent.
2. **Validates** the step ID against `_CHECKPOINT_SEQUENCE` before writing. Unknown step ID
   → exits non-zero with a clear error; does not mutate state.
3. **Idempotent:** if the step ID is already in the list, exits 0 with no write.
4. **No other state is written.** This command only touches `checkpoint_step`.
5. **`CLAUDE.build.md`** (and `.j2`) is updated to call
   `flex_build.py record-checkpoint-step <step-id>` immediately after each checkpoint leaf
   worker returns, before re-running `next-action`. This closes the write-path gap.

---

### DP2 — Gate verdict JSON schema *(settled)*

**Question:** What is the structured output schema gate workers must emit, and does the
resolver need backward compatibility with the old text format?

**Decision:** ✅ AGREED (2026-07-04).

1. **Gate workers emit a single JSON object** on stdout (all other output goes to stderr):
   ```json
   {
     "schema":  "clean | block:<reason>",
     "auth":    "clean | block:<reason>",
     "stub":    "clean | block:<reason>"
   }
   ```
   All three keys are always present. `clean` means no block. `block:<reason>` means blocked,
   with a short human-readable reason after the colon.
2. **`parse_worker_verdict_text` is replaced by `parse_worker_verdict_json`** in
   `next_action.py`. The new parser calls `json.loads()` on the worker's stdout; a
   `json.JSONDecodeError` or missing key is treated as a gate failure with
   `reason="malformed-verdict"` (fail-closed, not fail-open).
3. **No backward compatibility with the old text format.** The gate worker procedure
   (`skills/pairmode/skills/gate-worker/procedure.md` or equivalent) is updated in the
   same phase. Both sides change together; there is no migration window to support.
4. **The resolver's routing is unaffected.** The action emitted for a blocked gate remains
   `await-user`; only the parsing mechanism changes.

---

### DP3 — Orchestrator wiring *(settled)*

**Question:** How does `CLAUDE.build.md` change to call `record-checkpoint-step`? Does the
orchestrator need to parse the step ID from the action object, or is it passed explicitly?

**Decision:** ✅ AGREED (2026-07-04).

1. The resolver action object already contains the action string
   (e.g. `"action": "checkpoint-security"`). The orchestrator extracts this and passes it
   directly: `flex_build.py record-checkpoint-step checkpoint-security`.
2. **`CLAUDE.build.md` checkpoint section** becomes:
   ```
   ## Checkpoint
   After each checkpoint leaf worker returns, call:
     flex_build.py record-checkpoint-step <action>
   Then re-run next-action. checkpoint-tag: git tag cp-<phase-key> && git push origin harness --tags.
   ```
3. **`CLAUDE.build.md.j2`** is updated identically. This is a HARNESS-primary-file change.

---

### DP4 — Scope fence *(settled)*

**Question:** What is explicitly in/out of HARNESS009?

**Decision:** ✅ AGREED (2026-07-04).

**In:**
- `flex_build.py record-checkpoint-step` CLI (RESOLVER-012 primary)
- `parse_worker_verdict_json` replacing `parse_worker_verdict_text` in `next_action.py` (RESOLVER-013 primary)
- Gate worker procedure updated to emit JSON (WORKER rail, RESOLVER-013 touches)
- `CLAUDE.build.md` + `.j2` wiring update (RESOLVER-012 touches)
- Tests for both CLI and parser

**Out (CER backlog — Do Later):**
- `needs_spec` magic constant (5 lines) — rename to named constant with comment; trivial,
  not a correctness risk.
- `flex_build.py check-commit-format --story-id X` — commit message format enforcement;
  lower priority since commit format failures surface as "unexpected FAIL" on next cycle
  rather than silent corruption.

---

## Resulting story outline

| Story ID | Title | Rail | Acceptance gist |
|----------|-------|------|-----------------|
| RESOLVER-012 | `record-checkpoint-step` CLI + orchestrator wiring | RESOLVER | `flex_build.py record-checkpoint-step <step>` writes atomically, validates, idempotent; CLAUDE.build.md + .j2 updated; tests; suite green. |
| RESOLVER-013 | Gate verdict JSON schema + parser hardening | RESOLVER | `parse_worker_verdict_json` replaces text parser; fail-closed on malformed JSON; gate worker procedure emits JSON; tests; suite green. |

**Build order:** RESOLVER-012 → RESOLVER-013.

**Schema delivery:** no new persistent schema objects. `state.json["checkpoint_step"]` key
already exists; this phase adds CLI write authority over it.
