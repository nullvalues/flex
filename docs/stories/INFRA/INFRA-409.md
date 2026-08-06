---
id: INFRA-409
rail: INFRA
title: Bootstrap/scaffold doc and quoting quality fixes (CER-166/167/187)
status: draft
phase: "139"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/story_new.py
  - skills/pairmode/scripts/bootstrap.py
touches:
  - tests/pairmode/test_story_new.py
  - tests/pairmode/test_bootstrap.py
  - skills/pairmode/skills/security-auditor/procedure.md
  - tests/pairmode/test_security_auditor_worker.py
  - skills/pairmode/SKILL.md
narrative_roles: []
---

<!-- If this story changes any documented architecture, add docs/architecture.md to the touches: list above. -->

## Context

Three unrelated LOW-severity findings share one shape: a fact is true in the code
but not reflected where a reader looks it up. CER-166 — `post_tool_use.py` writes
`context_current_tokens_source` (INFRA-374), but the security-auditor's check-1
authorized-write enumeration never gained the key, so each future audit
re-derives in-scope-ness instead of checking a current list. CER-167 —
`story_new.py`'s `_story_frontmatter` interpolates `--primary-file` values into
YAML unquoted (`lines.append(f"  - {pf}")`), the defect class CER-163 already
closed for `bootstrap.py`'s `--operator-note`; a path containing `: `, a leading
quote, or a newline emits malformed frontmatter. CER-187 — INFRA-392 widened
`--force-agents` to also unconditionally overwrite `docs/exemplars/EXEMPLAR-000.md`,
but neither the flag's help text nor `SKILL.md`'s description was updated, so an
operator refreshing agent shells can clobber a locally-edited exemplar with no
warning from the docs describing the flag. All three are documentation/serialisation
fixes at named lines; none changes behaviour beyond CER-167's quoting.

## Requires

None — the three fixes are independent of each other and of any other Phase 139
story.

## Ensures

1. `_story_frontmatter`'s emitted `primary_files:` and `touches:` entries survive a
   `yaml.safe_load` round-trip byte-identically for values containing `: `, a
   leading `"`, a leading `#`, and an embedded newline. Forbidden proxy: rejecting,
   stripping, or sanitising such a value so the round-tripped string differs from
   the operator's input — the fix is serialisation, not validation.
2. `bootstrap.py`'s `--force-agents` help text and `SKILL.md`'s `--force-agents`
   bullet each name `docs/exemplars/EXEMPLAR-000.md` as also overwritten.
3. `skills/pairmode/skills/security-auditor/procedure.md`'s `hooks/post_tool_use.py`
   authorized-state.json-writes list names `context_current_tokens_source`.

## Instructions

1. **CER-167** — in `story_new.py`, add a small YAML-scalar helper and route every
   operator-derived sequence entry through it (both the `primary_files:` loop at
   ~line 113 and the `touches:` loop at ~line 132 — the derived test paths carry the
   operator's stem forward, so they need the same treatment). Emit the value bare
   when it is a plain safe scalar, quoted otherwise; the acceptance property is the
   round-trip in Ensures 1, not any particular quoting style. Do not change the
   CER-092 title-quoting branch.
2. **CER-187** — extend the `--force-agents` help string (`bootstrap.py` ~line 1407)
   and `SKILL.md`'s matching bullet (~line 140) to state that the flag also
   overwrites `docs/exemplars/EXEMPLAR-000.md`.
3. **CER-166** — in `security-auditor/procedure.md`, add `context_current_tokens_source`
   to the `hooks/post_tool_use.py` entry's "Authorized state.json writes" list,
   citing INFRA-374.
   **Known conflict and resolution (found by INFRA-409 attempt 1, CER-208):**
   `tests/pairmode/test_security_auditor_worker.py::test_procedure_does_not_reference_context_current_tokens`
   asserts the bare substring `context_current_tokens` never appears anywhere in
   the procedure file — a DP1.3 bounded-input guard whose actual intent (per its
   own docstring) is that the security-auditor must never be told to *read*
   `context_current_tokens` as accumulated orchestrator state. `context_current_tokens_source`
   is a distinct key (a static write-enumeration entry for Check 1, not a read
   instruction) that happens to contain the guarded substring. Resolution: narrow
   the guard assertion in `test_security_auditor_worker.py` to flag the bare key
   `context_current_tokens` (e.g. via a regex asserting it is not present unless
   immediately followed by `_source`, or an equivalent word-boundary-aware check)
   rather than the raw substring, and add a case to that same test asserting the
   bare key is still disallowed. This is now in this story's scope — add
   `tests/pairmode/test_security_auditor_worker.py` to `touches:`.
4. Tests: extend `tests/pairmode/test_story_new.py` with the Ensures-1 round-trip
   cases, and `tests/pairmode/test_bootstrap.py` with an assertion that the
   `--force-agents` help output mentions `EXEMPLAR-000.md`. The two Markdown-only
   edits (step 2's `SKILL.md` half and step 3) need no test.
5. Scope note (spec-preflight): `security-auditor/procedure.md` and `SKILL.md` are
   edited by this story and are declared in `touches:` above rather than
   `primary_files:` — they are documentation surfaces, not the story's code subject.
   Two further preflight `scope:` findings are intentional and left as-is:
   `docs/exemplars/EXEMPLAR-000.md` and `hooks/post_tool_use.py` are named only as
   the *subjects described by* the edited help text and enumeration; neither file is
   modified by this story.

## Tests

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_story_new.py tests/pairmode/test_bootstrap.py -q
```
Acceptance: green, including the new quoting round-trip and help-text cases.

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -q
```
Acceptance: no new failures relative to the pre-story baseline.

## Out of scope

- `SKILL.md`'s chronically stale "Outputs" list (missing narratives, spec-writer,
  docs-reviewer, gate-worker, shadow-reviewer, `.pairmode-overrides`) — CER-187
  names it as pre-existing drift; this story fixes only the `--force-agents`
  description.
- Auditing any other hook's authorized-write enumeration in
  `security-auditor/procedure.md` for completeness — only the one missing
  `post_tool_use.py` key is added here.
- Prompting or refusing before `--force-agents` overwrites a locally-edited
  `EXEMPLAR-000.md` — this story documents the existing behaviour, it does not
  change it.
