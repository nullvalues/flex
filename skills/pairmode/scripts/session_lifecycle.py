"""session_lifecycle.py — session-boundary notices for agent-registration writes.

Claude Code reads ``.claude/agents/*.md`` agent definitions, plugin/skill
registration files, and the ``hooks`` blocks in ``.claude/settings*.json`` at
**session start**. Every pairmode tooling path that writes those surfaces
(``bootstrap``, ``sync-agents``, ``sync-all``, ``migrate``, ``to-030``,
``audit-hooks``) does so **mid-session** — the running process never re-reads
what it just wrote, so a builder spawn or agent-registry check in the same
session silently uses the stale, pre-write registry.

This module is the single, pure definition of:

- the notice a completed write prints as its terminal output
  (:func:`render_restart_notice`) — see § A of ``docs/stories/INFRA/INFRA-323.md``;
- the state-dict stamp callers use to record *that* a registration surface
  was written, so a later hook can read it back (:func:`stamp_agent_surfaces`);
- the SessionStart advisory line for the one session boundary that does not
  re-register the surfaces on its own — ``/clear`` and ``/compact``
  (:func:`agent_staleness_notice`).

Stdlib-only. Importable by both a ``click`` CLI and a hook: no I/O, no clock
read beyond parsing arguments already in hand, no ``click`` import.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Sequence

#: Surface keys this module knows how to name and classify, mapped to a
#: one-line human description. Every notice-emitting caller enumerates a
#: subset of these keys (or the concrete changed paths that belong to them).
RESTART_SURFACES: dict[str, str] = {
    "agent_shells": ".claude/agents/*.md — subagent definitions",
    "hook_registration": (
        ".claude/settings.json / settings.local.json — hooks blocks"
    ),
    "plugin_skills": (
        "plugin/skill registration files (.claude-plugin/ or SKILL.md)"
    ),
}

#: SessionStart sources that are a fresh CLI process — the registry is
#: re-read on these, so a staleness warning would be false (§ F29 / R5).
_FRESH_PROCESS_SOURCES = frozenset({"startup", "resume"})

#: SessionStart sources that reuse the running process without reloading the
#: agent registry — the only boundary the advisory needs to fire on.
_STALE_CAPABLE_SOURCES = frozenset({"clear", "compact"})


def classify_surface(path: str) -> "str | None":
    """Return the :data:`RESTART_SURFACES` key *path* belongs to, or ``None``.

    Pure string/path classification — no filesystem access. Accepts either a
    project-relative or absolute path string. Never raises: an unparseable
    input simply classifies as ``None``.
    """
    if not isinstance(path, str) or not path:
        return None
    try:
        parts = PurePosixPath(path.replace("\\", "/")).parts
        name = PurePosixPath(path.replace("\\", "/")).name
    except (TypeError, ValueError):
        return None

    if name == "SKILL.md" or ".claude-plugin" in parts:
        return "plugin_skills"
    if name in {"settings.json", "settings.local.json"} and ".claude" in parts:
        return "hook_registration"
    if (
        name.endswith(".md")
        and ".claude" in parts
        and "agents" in parts
        and name != "SKILL.md"
    ):
        return "agent_shells"
    return None


def render_restart_notice(
    changed: Sequence[str],
    *,
    project_dir: "str | None" = None,
    action: str,
) -> str:
    """Return the § A notice text, or ``""`` for an empty *changed*.

    Pure — no I/O, no path resolution, never calls ``click.echo``. *changed*
    is the list of changed paths or surface-group labels the caller wants
    enumerated verbatim, one per line. *project_dir* is accepted for future
    callers that want to qualify paths but is not required to render a
    correct notice today (unused otherwise).
    """
    if not changed:
        return ""

    lines = [
        "RESTART REQUIRED",
        f"`{action}` just wrote one or more session-start-only surfaces:",
    ]
    for item in changed:
        lines.append(f"  - {item}")
    lines.append(
        "Claude Code loads agent definitions and hook registrations at "
        "session start, so the files just written are not in effect in this "
        "session."
    )
    lines.append(
        "Exit this session and start a new one to pick up the change. "
        "/clear and /compact are NOT sufficient — neither re-registers "
        "agents or hooks."
    )
    return "\n".join(lines)


def stamp_agent_surfaces(
    state: dict,
    *,
    changed: Sequence[str],
    action: str,
    now: "str | None" = None,
) -> None:
    """Mutate *state* in place with the § A6 stamp keys.

    Writes ``agent_surfaces_written_at`` (ISO-8601 UTC) and
    ``agent_surfaces_written_by`` (*action*) when *changed* is non-empty.
    Performs no file I/O — callers own the write. Absent *changed*, mutates
    nothing. Never raises for a non-dict *state* — it is simply a no-op.
    """
    if not changed:
        return
    if not isinstance(state, dict):
        return
    stamp = now if isinstance(now, str) and now else datetime.now(timezone.utc).isoformat()
    state["agent_surfaces_written_at"] = stamp
    state["agent_surfaces_written_by"] = action


def _parse_iso(value: object) -> "datetime | None":
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def agent_staleness_notice(
    *,
    source: "str | None",
    session_started_at: "str | None",
    written_at: "str | None",
    written_by: "str | None",
) -> "str | None":
    """Return a one-line advisory, or ``None``.

    Pure — no I/O, no clock read beyond parsing the given arguments. Fires
    **only** when all of: *source* is ``"clear"`` or ``"compact"``; both
    timestamps parse; and *written_at* is strictly after
    *session_started_at*. Every other case — including ``"startup"`` and
    ``"resume"``, which are fresh CLI processes that re-read the registry on
    their own — returns ``None`` (§ F29 / R5).

    The returned line is a status-block context line, not the § A4 banner —
    it does not contain the ``RESTART REQUIRED`` literal.
    """
    if source not in _STALE_CAPABLE_SOURCES:
        return None

    started = _parse_iso(session_started_at)
    written = _parse_iso(written_at)
    if started is None or written is None:
        return None
    if not written > started:
        return None

    action = written_by if isinstance(written_by, str) and written_by else "a tooling run"
    return (
        f"Agent/hook registration was written by {action!s} at {written_at} — "
        "after this session started. Exit and start a new session to pick it "
        "up; /clear and /compact do not reload the registry."
    )
