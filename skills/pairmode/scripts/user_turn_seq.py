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
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow the flat import below under every invocation style this module has
# (the hook's own sys.path injection, a direct CLI run, and the package-style
# ``skills.pairmode.scripts.user_turn_seq`` import used by some tests).
sys.path.insert(0, str(Path(__file__).parent))

from state_utils import update_state_json  # noqa: E402

try:
    from skills.pairmode.scripts import context_budget  # type: ignore
    from skills.pairmode.scripts import session_state  # type: ignore
    from skills.pairmode.scripts.context_model import (  # type: ignore
        CONTEXT_CURRENT_TOKENS_SOURCE_KEY,
    )
except ImportError:  # flat import via hook sys.path
    import context_budget  # type: ignore[no-redef]
    import session_state  # type: ignore[no-redef]
    from context_model import (  # type: ignore[no-redef]
        CONTEXT_CURRENT_TOKENS_SOURCE_KEY,
    )


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
      stored.

    Fails open (returns silently, no write) when: ``project_dir`` does not
    contain ``.companion/state.json``; the file is unreadable or malformed;
    its root is not a dict; or any exception occurs. Never raises.

    This function owns the entirety of the read-modify-write for this hook
    (D11 thin-hook contract) — ``hooks/user_prompt_submit.py`` makes exactly
    one call to this function and performs no state.json I/O itself.

    INFRA-285 (CER-097, item E4/E5): the whole read-check-write is one
    ``state_utils.update_state_json`` call, so it happens under the advisory
    state lock and persists via atomic replace. The previous shape — a bare
    bare ``write_text()`` of the entire state dict on every prompt in
    every session — could tear the file, and because every reader in the system
    fails open on ``JSONDecodeError`` the observable symptom was not a lost
    counter but the whole companion state silently reverting to defaults. The
    idempotency check is expressed as the mutate callback's ``return False``
    branch rather than an early return, because the decision to write is part
    of the critical section and cannot be hoisted outside the lock. The
    fingerprint algorithm and ``compute_fingerprint``'s signature are unchanged
    (INFRA-248: the counter is only ever compared ordinally).

    INFRA-321 § C1: this function ALSO refreshes the orchestrator track
    (``context_current_tokens`` / ``context_current_tokens_recorded_at``)
    from the same real, ``isSidechain``-filtered JSONL measurement
    ``hooks/post_tool_use.py`` uses (``context_budget.read_current_tokens``),
    inside the SAME read-modify-write — one state write per invocation,
    unchanged. This closes the between-spawn blind spot: everything that
    enters the orchestrator's window between Task/Agent spawns (poll output,
    merge output, task-completion notifications, spec-writer coordination) was
    previously never observed.

    § C3 (measurement-only, fail-open): a ``None`` measurement (no
    ``session_id``, transcript not on disk, no non-sidechain assistant entry)
    leaves ``context_current_tokens`` and its stamp untouched — never zeroed,
    never estimated. The refresh and the turn-counter increment are two
    independently-wrapped responsibilities (mirroring
    ``hooks/post_tool_use.py``'s "two delegated calls, each independently
    wrapped" posture) — an exception raised by the refresh must not prevent
    the counter increment from being persisted.

    § C4: ``context_budget.record_step_growth`` is deliberately NOT called
    from this path. The ring buffer must stay a per-build-step growth series
    (what ``expected_step_tokens``'s ceiling arithmetic assumes); mixing
    per-user-turn deltas into it would corrupt that median.

    § C6: when the refresh writes a measured value, it also stamps
    ``context_current_tokens_source = "user-prompt-submit"`` — one of two live
    writers of that provenance field (the other being the "manual"
    ``set-context-tokens`` / ``bump-context-tokens`` commands). The third
    named value, ``"post-tool-use"``, has NO live writer today:
    ``hooks/post_tool_use.py`` is a protected path (``hooks/**``) and this
    story does not edit it — see ``docs/cer/backlog.md``'s INFRA-321 follow-up
    row. ``context_budget.decide()`` does not gate on this field either way.
    """
    try:
        project_dir = Path(project_dir)
        state_path = project_dir / ".companion" / "state.json"
        fingerprint = compute_fingerprint(data)
        session_id = data.get("session_id", "") if isinstance(data, dict) else ""

        def _mutate(state: dict) -> "bool | None":
            if state.get("context_budget_user_turn_seq_fingerprint") == fingerprint:
                # Duplicate firing of the same UserPromptSubmit event — skip.
                return False

            # § C1/C3: orchestrator-track refresh — wrapped independently so a
            # failure here can never block the turn-counter increment below.
            try:
                live_tokens = context_budget.read_current_tokens(
                    project_dir=project_dir,
                    session_id=session_id,
                )
                if live_tokens is not None:
                    view = session_state.session_view(state, session_id)
                    view["context_current_tokens"] = live_tokens
                    view["context_current_tokens_recorded_at"] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    session_state.apply_session_view(state, session_id, view)
                    # § C6 provenance stamp — additive, observability only.
                    state[CONTEXT_CURRENT_TOKENS_SOURCE_KEY] = "user-prompt-submit"
                    # § C4: record_step_growth() is deliberately NOT called
                    # here — this is a per-user-turn measurement, not a
                    # per-build-step one; mixing the two series would corrupt
                    # expected_step_tokens's median.
            except Exception:
                pass

            # Turn-counter increment (INFRA-248) — independent of the refresh
            # above; always advances on a genuine (non-duplicate) event.
            current = state.get("context_budget_user_turn_seq", 0)
            try:
                current = int(current)
            except (TypeError, ValueError):
                current = 0
            state["context_budget_user_turn_seq"] = current + 1
            state["context_budget_user_turn_seq_fingerprint"] = fingerprint
            return None

        update_state_json(state_path, _mutate)
    except Exception:
        pass
