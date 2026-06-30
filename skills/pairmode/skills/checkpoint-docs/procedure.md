---
name: flex:checkpoint-docs-procedure
description: Docs-review procedure for the Era 003 checkpoint-docs worker (WORKER-011). Canonical source for the bounded inputs, documentation currency checklist, and REVIEW-RESULT return format used by the checkpoint-docs action.
version: "0.1.0"
---

# Checkpoint Docs-Review — Procedure

This document is the **plugin-versioned procedure skill** for the checkpoint-docs
worker (WORKER-011, HARNESS004-main). It is the single source of the documentation
currency review procedure. The thin agent shell delegates to this skill; no review
logic lives in the shell.

The checkpoint-docs worker runs at each checkpoint, after `checkpoint-security` and
`checkpoint-intent` are complete. Its job is a cold-eyes check of documentation
currency: verifying that era/phase/story docs, `docs/architecture.md`, the CER
backlog, and `CHANGELOG.md` are consistent with what was built. It does not write
code, does not commit, and produces a `REVIEW-RESULT` with verdict `PASS` or `FAIL`.

---

## Shell instruction

If you are a thin agent shell loading this procedure, your complete instruction is:

> Load `skills/pairmode/skills/checkpoint-docs/procedure.md`. Run the docs-review
> for phase `{scalar}`. Return the result as JSON matching the `REVIEW-RESULT`
> schema with verdict `"PASS"` when all documentation is current, or `"FAIL"` when
> a blocking documentation gap is found.

Where `{scalar}` is the phase ID passed to you by the orchestrator (e.g.
`HARNESS004-main`).

---

## Role

You are the docs-reviewer for the current checkpoint. You run once per phase,
after `checkpoint-security` and `checkpoint-intent` are complete. You verify that
documentation is consistent with what was built and that the CER backlog has no
unaddressed Do Now items. You never write code. You never commit. You are cold-eyes:
you assess documentation currency only.

---

## Input contract (DP1.3 — input-bound property)

You read **only**:

1. The phase doc: `docs/phases/phase-<ID>.md` (the agreements input — the spec
   of what was planned, and the `## Stories` table of actual story statuses).
2. The era doc: `docs/eras/<NNN>-<name>.md` (the current era document, identified
   from `docs/phases/index.md`).
3. `docs/phases/index.md` (phase and era index — identifies the current era and
   active phase).
4. `docs/architecture.md` (the architecture reference — must mention the current
   era and phase).
5. `docs/cer/backlog.md` (CER backlog — Do Now section must be empty or all RESOLVED).
6. Story files referenced by the phase doc: `docs/stories/<RAIL>/<RAIL>-NNN.md`
   (existence check and status field only).
7. `CHANGELOG.md` (if the file exists at the project root — checked for a phase entry).

You **must not** request or rely on accumulated orchestrator state, prior-attempt
transcripts, the effort database, session state contents, attempt counters,
or any context outside these categories. If information beyond these inputs is
needed, report the finding and continue — do not fetch additional context.

---

## Starting a docs review

You are given a phase ID (e.g. `HARNESS004-main`). Before taking any other action:

1. Read `docs/phases/index.md` to identify the current era and the phase doc path.
2. Read the phase doc in full — note the `## Stories` table and each story ID and
   its status column.
3. Read each story file referenced in the `## Stories` table (frontmatter only).
4. Read `docs/architecture.md` in full.
5. Read `docs/cer/backlog.md` in full.
6. Read `CHANGELOG.md` if it exists at the project root.

---

## Documentation currency checklist

Run every item. Record each failure as a finding string.

1. **Story table ↔ disk status match.** For each story in the phase doc `## Stories`
   table, read the story file's frontmatter `status` field. The phase-doc table status
   and the story file status must agree. Report any mismatch (e.g. "Story RAIL-NNN
   shows `complete` in phase doc but `planned` on disk").

2. **Story files exist.** Every story ID listed in the phase doc `## Stories` table
   must have a corresponding file at `docs/stories/<RAIL>/<RAIL>-NNN.md`. Report any
   missing file (e.g. "Story RAIL-NNN referenced in phase doc but file not found").

3. **CER Do Now is clear.** In `docs/cer/backlog.md`, the `## Do Now` section (or
   equivalent top-priority section) must be empty or every item must be marked
   `RESOLVED`. Report any unresolved Do Now item (e.g. "CER Do Now contains
   unresolved item: [item text]").

4. **`docs/architecture.md` mentions the current era.** The file must contain a
   reference to the current era name or ID (as identified from `docs/phases/index.md`).
   Report if absent (e.g. "docs/architecture.md does not reference current era
   `003-flex-orchestrator-as-harness`").

5. **`docs/architecture.md` mentions the current phase.** The file must contain a
   reference to the current phase ID (e.g. `HARNESS004-main`). Report if absent
   (e.g. "docs/architecture.md does not reference current phase `HARNESS004-main`").

6. **`CHANGELOG.md` has a phase entry (if present).** If `CHANGELOG.md` exists at
   the project root, it must contain an entry for the current phase ID or its
   human-readable title. Report if absent (e.g. "CHANGELOG.md exists but has no
   entry for phase `HARNESS004-main`"). Skip this check entirely if `CHANGELOG.md`
   does not exist.

---

## Decision

- **PASS** — All checklist items passed. Documentation is current.
- **FAIL** — One or more checklist items failed. List each failure as a finding.

The docs-reviewer does not block the checkpoint on advisory findings — only on
concrete documentation gaps (a missing story file, an unresolved Do Now item, a
status mismatch, or a missing architecture reference).

---

## Return format

Return a JSON object conforming to the `REVIEW-RESULT` schema (WORKER-004 grammar).

On pass:

```json
{
  "type": "REVIEW-RESULT",
  "verdict": "PASS",
  "findings": [],
  "reason": "One sentence summarising the documentation currency assessment."
}
```

On failure:

```json
{
  "type": "REVIEW-RESULT",
  "verdict": "FAIL",
  "findings": [
    "Story RAIL-NNN shows complete in phase doc but planned on disk",
    "CER Do Now contains unresolved item: CER-042 context-staleness edge case"
  ],
  "reason": "One sentence summarising why the checkpoint cannot proceed."
}
```

Fields:
- `type` — always `"REVIEW-RESULT"`
- `verdict` — `"PASS"` when all documentation is current; `"FAIL"` on any blocking gap
- `findings` — list of finding strings (empty when PASS)
- `reason` — one sentence summarising the assessment

Return only the JSON object. No preamble, no commentary, no usage block.

---

## Non-negotiables

- Never read beyond the declared input categories (DP1.3).
- Never write, edit, or fix documentation — report findings only.
- Never commit, revert, or block the checkpoint beyond reporting FAIL.
- Preserve the `REVIEW-RESULT` JSON format the checkpoint-docs action relies on.
- Return value must be valid `REVIEW-RESULT` JSON (parseable by `worker_result.py`).
