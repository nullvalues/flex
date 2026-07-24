"""user_turn_seq.py — Idempotent UserPromptSubmit turn-counter increment.

INFRA-248 (following INFRA-247's dedupe of the plugin-manifest/settings.json
`UserPromptSubmit` registration): before INFRA-247, every user prompt fired
`hooks/user_prompt_submit.py` twice per turn — once via `hooks/hooks.json`
and once via `.claude/settings.json`'s duplicate registration. Each
invocation performed an unconditional read-modify-write increment of
`context_budget_user_turn_seq` in `.companion/state.json`, so a duplicated
registration doubled the counter's advance rate relative to genuine human
turns.

Audit finding (INFRA-248, see `docs/stories/INFRA/INFRA-248.md` Build notes
for the full write-up): the double-increment is confirmed at the code-path
level, but it has **no functional effect** on
`context_budget.should_block()`'s (`skills/pairmode/scripts/context_budget.py`)
gate decision, because that function only ever compares
`user_turn_seq` and `acknowledged_user_turn_seq` *ordinally*
(`user_turn_seq <= acknowledged_user_turn_seq` / `user_turn_seq >
acknowledged_user_turn_seq`) — never by magnitude or delta. Both values are
written from the same doubled counter (the hook increments
`context_budget_user_turn_seq`; `hooks/pre_tool_use.py` copies its current
value into `context_budget_acknowledged_user_turn_seq` at block time), so
the doubling is a uniform scale factor applied to both sides of every
comparison and the ordinal relationship — and therefore every past and
future gate decision — is unaffected. This module exists so a future
duplicate registration (of this hook, or any equivalent re-fire of the same
`UserPromptSubmit` event) degrades to inert noise instead of a genuine
double-count, even though the current corruption was proven harmless.

Design boundary (D11, mirrors ``context_budget.py`` / ``session_reset.py``):
this module owns the full read-modify-write, including the idempotency
check — unlike the pure-decision modules, the thin-hook contract for
`user_prompt_submit.py` requires it to do zero I/O and zero decision logic
itself; ``hooks/user_prompt_submit.py`` is limited to stdin parsing +
one delegated call to ``record_user_turn()`` + ``sys.exit(0)``.

Idempotency mechanism: a sha256 fingerprint of the identifying fields of the
UserPromptSubmit payload (``session_id`` + ``prompt``) is stored in
`state.json["context_budget_user_turn_seq_fingerprint"]` on every increment.
A subsequent invocation whose fingerprint matches the stored value is
treated as a duplicate firing of the *same* event (e.g. two hook
registrations for one prompt) and the increment — and the fingerprint
write — are both skipped. A different prompt (different fingerprint)
always increments, even within the same session. Fails open on any error:
missing/malformed state.json, non-dict payload, or write failure all leave
state.json untouched rather than raising.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def compute_fingerprint(data: dict | None) -> str:
    """Return a deterministic sha256 hex digest identifying one UserPromptSubmit event.

    Built from ``session_id`` + ``prompt`` when either is present (the two
    fields that uniquely identify a single prompt-submission event across
    duplicate hook registrations firing for the same event). Falls back to a
    sorted-key JSON dump of the whole payload when neither field is present,
    so a malformed/minimal payload still produces a stable fingerprint rather
    than crashing. Never raises.
    """
    if not isinstance(data, dict):
        data = {}
    session_id = data.get("session_id")
    prompt = data.get("prompt")
    try:
        if session_id is not None or prompt is not None:
            payload = json.dumps(
                {"session_id": session_id, "prompt": prompt}, sort_keys=True
            )
        else:
            payload = json.dumps(data, sort_keys=True, default=str)
    except Exception:
        payload = repr(data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record_user_turn(project_dir: "str | Path", data: dict | None) -> None:
    """Idempotently record one UserPromptSubmit turn in ``.companion/state.json``.

    Reads state.json, computes ``compute_fingerprint(data)``, and compares it
    against the stored ``context_budget_user_turn_seq_fingerprint``:

    - If they match, this invocation is a duplicate firing of the
      immediately-preceding event (e.g. a second hook registration for the
      same prompt) — the increment is skipped and state.json is left
      untouched.
    - Otherwise, ``context_budget_user_turn_seq`` is incremented by 1
      (treated as 0 when absent or non-numeric) and the new fingerprint is
      stored, in a single ``write_text()`` call.

    Fails open (returns silently, no write) when: ``project_dir`` does not
    contain ``.companion/state.json``; the file is unreadable or malformed;
    its root is not a dict; or any exception occurs. Never raises.

    This function owns the entirety of the read-modify-write for this hook
    (D11 thin-hook contract) — ``hooks/user_prompt_submit.py`` makes exactly
    one call to this function and performs no state.json I/O itself.
    """
    try:
        project_dir = Path(project_dir)
        state_path = project_dir / ".companion" / "state.json"
        if not state_path.exists():
            return
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            return

        fingerprint = compute_fingerprint(data)
        previous_fingerprint = state.get("context_budget_user_turn_seq_fingerprint")
        if previous_fingerprint == fingerprint:
            # Duplicate firing of the same UserPromptSubmit event — skip.
            return

        current = state.get("context_budget_user_turn_seq", 0)
        try:
            current = int(current)
        except (TypeError, ValueError):
            current = 0
        state["context_budget_user_turn_seq"] = current + 1
        state["context_budget_user_turn_seq_fingerprint"] = fingerprint
        state_path.write_text(json.dumps(state, indent=2))
    except Exception:
        pass
