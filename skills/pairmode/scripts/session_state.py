"""session_state.py — session-scoped context accounting inside ``.companion/state.json``.

INFRA-285 (CER-097). Before this module, the context-budget counter
(``context_current_tokens``), its recorded-at stamp, the session-reset stamp,
the step-growth ring buffer and the derived ``expected_step_tokens`` all lived
as **flat, project-global** keys in ``.companion/state.json``. Every Claude Code
session with the plugin's hooks installed wrote them — including a purely
investigative side session the operator opened to read one file. A side session
starting mid-build reset the build loop's counter to its own fresh-window
baseline, and the two sessions' PostToolUse writers interleaved deltas taken
out of two unrelated context windows into a single ring buffer, corrupting the
gate's forward estimate rather than merely its display.

This module makes that state **session-keyed**:

    state["context_sessions"][<session_id>] = {
        # any subset of SESSION_SCOPED_KEYS
        "context_current_tokens": 140000,
        "context_current_tokens_recorded_at": "...",
        "context_session_reset_at": "...",
        "context_step_growth_samples": [...],
        "expected_step_tokens": 12000,
        # plus this record's own two fields:
        "spawn_output_prefix": "/tmp/claude-1000/-slug/<session-id>/" | None,
        "last_seen_at": "<iso8601 utc>",
    }

Why the flat keys survive as a derived mirror
---------------------------------------------
The obvious reflex — "just key everything and delete the flat keys" — breaks two
live consumers that have **no session id to resolve against**:

1. ``skills/observability/api/src/routes/context.ts`` (lines 132-140, 239-240)
   reads the flat ``context_current_tokens`` /
   ``context_current_tokens_recorded_at`` pair to render the context panel. It
   is a TypeScript service reading the JSON file directly; teaching the SPA/API
   to render per-session context is OBS-rail work (era doc § Phase G scope),
   not this story's, and doing it here would widen a Python change into a
   cross-language one.
2. Any CLI reader invoked outside a session — e.g. ``set-context-tokens`` and
   the ad-hoc ``jq``/inspection path an operator uses — has no ``session_id``
   at all.

So :func:`apply_session_view` writes each session-scoped value **twice**: into
the session's keyed entry (the authority) and into the flat top-level key (a
last-writer-wins mirror, display-only). Both writes happen in the same
read-modify-write so the mirror can never diverge through a partial write. This
is the same keyed-record + derived-mirror pattern INFRA-281/282/283 established
for ``current_stories``, ``attempt_counter`` and ``checkpoint_steps``.

**The mirror is display-only.** Once a ``context_sessions`` record exists, no
*gating* decision may be made from the flat keys — ``context_budget.decide``
resolves through :func:`session_view` when it has a session id, and fails safe
(CONTEXT CHECK REQUIRED) rather than reading the mirror when it has a session id
that is not registered while other sessions are live.

Every public function here is **total**: malformed input (a non-dict state, a
``context_sessions`` that is a list or ``None``, an unparseable timestamp)
returns the safe value and never raises. These functions run on the hook path.

Stdlib-only, and it must stay that way: ``hooks/session_start.py`` and
``hooks/post_tool_use.py`` import it through their bare ``sys.path`` injection,
with no package context and no third-party packages available.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

#: Key under which the session-keyed context record lives in state.json.
CONTEXT_SESSIONS_KEY = "context_sessions"

#: The state.json keys whose values are session-scoped rather than
#: project-scoped. Everything else in state.json (thresholds, the acknowledgment
#: pair, ``pairmode_version``, ``current_stories``) is genuinely project-wide and
#: is deliberately NOT in this set.
SESSION_SCOPED_KEYS = frozenset(
    {
        "context_current_tokens",
        "context_current_tokens_recorded_at",
        "context_session_reset_at",
        "context_step_growth_samples",
        "expected_step_tokens",
    }
)

#: How long a ``context_sessions`` entry is treated as belonging to a possibly-
#: still-running process.
#:
#: Deliberately much longer than ``context_budget._CONTEXT_TOKEN_STALE_MINUTES``
#: (60), and the two must never be conflated — they answer different questions.
#: The token TTL asks "is this *number* still trustworthy?"; this TTL asks
#: "might that other *process* still be running?". An unattended build loop can
#: sit idle far longer than its counter stays fresh (a long builder spawn, an
#: operator away from the keyboard), and treating such a loop as dead is exactly
#: the clobber this module exists to prevent: its counter would be reset from
#: another session's window, and its still-pending effort.db rows would be swept
#: by another session's reconciliation. 180 minutes errs toward "assume alive",
#: which fails safe in both directions.
SESSION_LIVE_TTL_MINUTES = 180


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: object) -> "datetime | None":
    """Parse an ISO-8601 timestamp, returning ``None`` for anything unparseable."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _sessions(state: object) -> dict:
    """Return the ``context_sessions`` mapping, or ``{}`` for any malformed shape."""
    if not isinstance(state, dict):
        return {}
    sessions = state.get(CONTEXT_SESSIONS_KEY)
    if not isinstance(sessions, dict):
        return {}
    return sessions


def _is_live(
    entry: object,
    now: "datetime | None" = None,
    ttl_minutes: int = SESSION_LIVE_TTL_MINUTES,
) -> bool:
    """Return ``True`` when *entry*'s ``last_seen_at`` is within *ttl_minutes*.

    An entry with a missing or unparseable ``last_seen_at`` is **not** live —
    it cannot be dated, so it cannot be defended. Shared by
    :func:`prune_stale_sessions` and :func:`live_session_ids` so the two can
    never disagree about what "live" means.
    """
    if not isinstance(entry, dict):
        return False
    seen = _parse_iso(entry.get("last_seen_at"))
    if seen is None:
        return False
    try:
        ttl = int(ttl_minutes)
    except (TypeError, ValueError):
        ttl = SESSION_LIVE_TTL_MINUTES
    reference = now if now is not None else _now()
    return seen >= reference - timedelta(minutes=ttl)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def session_view(state: dict, session_id: "str | None") -> dict:
    """Return a **new** dict: *state* overlaid with *session_id*'s own values.

    For each key in :data:`SESSION_SCOPED_KEYS` present in
    ``state["context_sessions"][session_id]``, the keyed value replaces the flat
    one; every key absent from that entry keeps its flat value (so a session
    that has not yet recorded a value inherits the mirror, which is what makes
    the first read after this story ships behave exactly as before).

    *state* is never mutated — the result is a shallow copy. Returns a plain
    copy of *state* when *session_id* is falsy, when there is no
    ``context_sessions`` record, or when that record is malformed. Never raises.
    """
    if not isinstance(state, dict):
        return {}
    view = dict(state)
    if not session_id:
        return view
    entry = _sessions(state).get(session_id)
    if not isinstance(entry, dict):
        return view
    for key in SESSION_SCOPED_KEYS:
        if key in entry:
            view[key] = entry[key]
    return view


def apply_session_view(
    state: dict, session_id: "str | None", view: dict
) -> None:
    """Write *view*'s session-scoped values back, keyed **and** mirrored.

    Mutates *state* in place:

    - every key of :data:`SESSION_SCOPED_KEYS` present in *view* is written into
      ``state["context_sessions"][session_id]``;
    - ``last_seen_at`` on that entry is stamped with the current UTC time;
    - the same values are **also** written to the flat top-level keys — the
      derived, display-only mirror (see the module docstring).

    Other sessions' entries are never touched. With a falsy *session_id* only
    the flat keys are written and no ``context_sessions`` entry is created, so
    legacy/no-session callers keep working byte-for-byte as before. Never
    raises.
    """
    if not isinstance(state, dict) or not isinstance(view, dict):
        return
    values = {key: view[key] for key in SESSION_SCOPED_KEYS if key in view}

    if session_id:
        sessions = state.get(CONTEXT_SESSIONS_KEY)
        if not isinstance(sessions, dict):
            sessions = {}
            state[CONTEXT_SESSIONS_KEY] = sessions
        entry = sessions.get(session_id)
        if not isinstance(entry, dict):
            entry = {}
            sessions[session_id] = entry
        entry.update(values)
        entry.setdefault("spawn_output_prefix", None)
        entry["last_seen_at"] = _now().isoformat()

    # Derived mirror — last writer wins, display-only, never gating.
    state.update(values)


def prune_stale_sessions(
    state: dict,
    ttl_minutes: int = SESSION_LIVE_TTL_MINUTES,
    keep: "str | None" = None,
) -> int:
    """Drop ``context_sessions`` entries older than *ttl_minutes*; return the count.

    An entry whose ``last_seen_at`` is missing or unparseable is also dropped —
    it can never age out otherwise, and an undateable entry would pin the record
    open forever. The entry named by *keep* (the session doing the pruning) is
    always retained, even when its own stamp is stale or absent: it is by
    definition alive.

    Bounded growth is the point — without this, every ``/clear`` in a long-lived
    project appends one more permanent entry. Called exactly once per
    SessionStart and nowhere else. Never raises.
    """
    if not isinstance(state, dict):
        return 0
    sessions = state.get(CONTEXT_SESSIONS_KEY)
    if not isinstance(sessions, dict):
        return 0
    now = _now()
    removed = 0
    for sid in list(sessions.keys()):
        if keep is not None and sid == keep:
            continue
        if not _is_live(sessions.get(sid), now, ttl_minutes):
            sessions.pop(sid, None)
            removed += 1
    if not sessions:
        state.pop(CONTEXT_SESSIONS_KEY, None)
    return removed


def live_session_ids(
    state: dict,
    exclude: "str | None" = None,
    ttl_minutes: int = SESSION_LIVE_TTL_MINUTES,
) -> "tuple[str, ...]":
    """Return the ids of every live ``context_sessions`` entry other than *exclude*.

    "Live" is :func:`_is_live` — ``last_seen_at`` within *ttl_minutes*. Order is
    the record's own iteration order. Returns ``()`` for any malformed state.
    Never raises.
    """
    now = _now()
    result: "list[str]" = []
    for sid, entry in _sessions(state).items():
        if exclude is not None and sid == exclude:
            continue
        if _is_live(entry, now, ttl_minutes):
            result.append(sid)
    return tuple(result)


def other_live_session_prefixes(
    state: dict,
    session_id: "str | None" = None,
    ttl_minutes: int = SESSION_LIVE_TTL_MINUTES,
) -> "tuple[str, ...]":
    """Return the deduplicated spawn-output prefixes of every *other* live session.

    Used by ``hooks/session_start.py`` as
    ``reconcile_pending_attempts(exclude_output_prefixes=...)`` so a starting
    session's orphan-row sweep can never reconcile — or bump the attempt counter
    for — rows belonging to a build loop that is still running.

    Entries with no recorded ``spawn_output_prefix`` (a session that has not yet
    spawned anything) contribute nothing: there are no rows of theirs to
    exclude. With no other live session this returns ``()``, and the sweep
    behaves exactly as it did before this story — which matters, because a
    single-session project must not lose orphan-row reconciliation. Never
    raises.
    """
    prefixes: "list[str]" = []
    for sid in live_session_ids(state, exclude=session_id, ttl_minutes=ttl_minutes):
        entry = _sessions(state).get(sid)
        if not isinstance(entry, dict):
            continue
        prefix = entry.get("spawn_output_prefix")
        if isinstance(prefix, str) and prefix and prefix not in prefixes:
            prefixes.append(prefix)
    return tuple(prefixes)
