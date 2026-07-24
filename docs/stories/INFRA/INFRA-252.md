---
id: INFRA-252
rail: INFRA
title: Authorize user_prompt_submit.py as fourth thin-delegation exception in security-auditor procedure
status: complete
phase: "99"
story_class: docs
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/skills/security-auditor/procedure.md
touches: []
---

## Context

The phase-99 checkpoint security audit FAILed with one HIGH finding:
INFRA-248 converted `hooks/user_prompt_submit.py` into a thin dispatcher that
delegates to `skills/pairmode/scripts/user_turn_seq.py` (sys.path insert +
`from user_turn_seq import record_user_turn`), byte-for-byte matching the idiom
of the three already-authorized dispatcher hooks (`pre_tool_use.py`,
`post_tool_use.py`, `session_start.py`). `docs/architecture.md` documents it as
an intentional fourth exception ("Documented exception —
hooks/user_prompt_submit.py (INFRA-192, INFRA-248)"), and the reviewer
procedure's thin-delegation rule already names it. But the security-auditor
procedure skill (`skills/pairmode/skills/security-auditor/procedure.md`) was
not updated: its check-1 exception list still names only the three original
hooks, and its authorized state.json writes list omits the two keys this hook
writes. The audit is input-bound to that procedure text, so the letter of the
checklist reports a layer violation that is in fact an authorization-doc gap.

The auditor's own recommendation: update the procedure skill's exception list,
not the code.

## Ensures

1. `skills/pairmode/skills/security-auditor/procedure.md` check-1
   thin-delegation exception list includes `hooks/user_prompt_submit.py`,
   delegating to `user_turn_seq.py`, with the same style/rationale as the
   existing three entries.
2. The procedure's authorized state.json writes list includes
   `context_budget_user_turn_seq` and `context_budget_user_turn_seq_fingerprint`
   as written by `hooks/user_prompt_submit.py` via
   `user_turn_seq.record_user_turn()`.
3. Check-6 (hooks may not import from skills/ beyond check-1 exceptions)
   remains consistent — no other wording still implies exactly three
   exception hooks.
4. No code files are modified; the diff is confined to the procedure skill.
5. A re-run of the phase-level security audit reports 0 CRITICAL / 0 HIGH for
   the phase-99 diff.

## Deliberate exceptions

Docs-only story: no new tables, no UI, no logic — no test file expected
(documentation/template-only per project review rules).
