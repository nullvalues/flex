#!/usr/bin/env python3
# thin dispatcher — clear/startup/compact → session_reset.py
"""SessionStart hook — injects pairmode context into Claude's session.

Thin-delegation exception: when Claude Code passes a stdin payload containing
``source`` (one of ``"startup"``, ``"resume"``, ``"clear"``, ``"compact"``),
this hook delegates the live context-counter reset decision to
``skills/pairmode/scripts/session_reset.decide_reset()`` (CER-047 / Phase 68
INFRA-175 / INFRA-180 / INFRA-245). All decision logic and timestamp
generation live in that module; the hook owns one state write (all keys
returned by ``decide_reset()``: ``context_current_tokens``,
``context_current_tokens_recorded_at``, and ``context_session_reset_at``)
when ``decide_reset()`` returns a dict with ``should_reset=True``.

INFRA-285 (CER-097): that write is now **session-scoped**. The payload's
``session_id`` selects a ``context_sessions`` entry
(``skills/pairmode/scripts/session_state.py``), so a side session starting
mid-build writes its own fresh-window baseline into its own entry instead of
clobbering the build loop's counter. The reset write, the non-reset session
seed, and the stale-entry prune are folded into **one** locked
read-modify-write via ``state_utils``' single-call update helper — the hook
stays a thin relay with a single state write per invocation.
"""
import json
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))

# INFRA-238: standardized on the hardcoded pipe location post_tool_use.py
# already used. The `pipe_path` state.json key was deleted by
# pairmode_migrate.py's `to-030` step; reading it here was dead code.
PIPE_PATH = str(Path(tempfile.gettempdir()) / "companion.pipe")


def _pipe_active() -> bool:
    return Path(PIPE_PATH).exists()


def _read_payload_from_stdin() -> dict:
    """Read the whole SessionStart stdin payload as a dict.

    INFRA-285: widened from the previous ``source``-only reader because the
    hook now also needs ``session_id`` to scope its state write. Same
    never-raises contract — returns ``{}`` on any parse failure, on a tty
    stdin, on empty input, or on a non-dict root (backwards compatible with
    direct invocation and older harnesses that pass no stdin).
    """
    try:
        if sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def main() -> None:
    state_path = Path(".companion/state.json")
    if not state_path.exists():
        return

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    pairmode_version = state.get("pairmode_version")
    if not pairmode_version:
        return  # not a pairmode repo; emit nothing

    # CER-047 / Phase 68 INFRA-175 / INFRA-180: delegate counter-reset decision.
    # INFRA-285: the decision stays pure (session_reset performs no I/O and
    # still receives the FLAT state dict — its pairmode_version and
    # baseline-override lookups are project-scoped, not session-scoped); only
    # *where* the returned keys land changed.
    payload = _read_payload_from_stdin()
    source = payload.get("source")
    if not isinstance(source, str):
        source = None
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        session_id = None

    reset_notice: str | None = None
    staleness_notice: str | None = None
    try:
        import session_lifecycle
        import session_reset
        import session_state
        import state_utils

        reset_result = session_reset.decide_reset(source, state)
        should_reset = bool(
            isinstance(reset_result, dict) and reset_result.get("should_reset")
        )

        def _mutate(current: dict) -> "bool | None":
            # A6: bounded growth — prune once per SessionStart, never elsewhere.
            pruned = session_state.prune_stale_sessions(current, keep=session_id)
            if should_reset:
                session_state.apply_session_view(current, session_id, reset_result)
                return None
            if not session_id:
                # No session to register and no baseline to write. Skip the
                # write entirely unless the prune actually removed something —
                # a non-reset source must leave state.json byte-identical
                # (INFRA-175 acceptance criterion 7), and a formatting-only
                # rewrite would be an unnecessary torn-write opportunity.
                return None if pruned else False
            # B3: a non-reset source (`resume`, or a missing/unknown source)
            # must still REGISTER the session, or the fail-safe in
            # context_budget.decide would fire on a legitimate --resume.
            # Seeding from session_view() writes the flat mirror's current
            # values into the new entry and re-mirrors the identical values
            # back, so no baseline is written and no token value changes.
            session_state.apply_session_view(
                current, session_id, session_state.session_view(current, session_id)
            )
            return None

        # INFRA-323 § F31/F33: read pre-mutation — best-effort, wrapped in its
        # own try so a malformed stamp or view can never affect the reset
        # decision above or this hook's exit status.
        try:
            staleness_notice = session_lifecycle.agent_staleness_notice(
                source=source,
                session_started_at=session_state.session_view(
                    state, session_id
                ).get("context_session_reset_at"),
                written_at=state.get("agent_surfaces_written_at"),
                written_by=state.get("agent_surfaces_written_by"),
            )
        except Exception:
            staleness_notice = None

        updated = state_utils.update_state_json(state_path, _mutate)
        if isinstance(updated, dict):
            state = updated
        if should_reset:
            baseline = reset_result["context_current_tokens"]
            reset_notice = (
                f"Context counter reset to {baseline} "
                f"(session source: {source})."
            )
    except Exception:
        # Reset path is best-effort; never break the status block.
        pass

    # INFRA-258: sweep any effort.db rows left pending by an async spawn
    # whose completion arrived after this session's own PostToolUse sweeps
    # had already run out (or never ran again before /clear). Best-effort,
    # own try/except — must never affect decide_reset() above or this
    # hook's exit status. Imported inside the try using the flat-sys.path
    # style this hook already relies on (line 21 above prepends
    # skills/pairmode/scripts to sys.path) — a package-qualified import
    # would pass tests but break at runtime.
    #
    # INFRA-285 (CER-097, item D5): the sweep is now scoped by EXCLUSION rather
    # than inclusion. Every SessionStart previously reconciled — and, on a FAIL
    # verdict, bumped the attempt counter for — rows belonging to whatever build
    # loop was running in another session. Excluding only *other live sessions'*
    # prefixes stops that while keeping the sweep's whole reason for existing:
    # orphan rows from sessions that have since died are still collected. With
    # no other live session this is `()` and behaviour is exactly as before.
    try:
        from subagent_transcript import reconcile_pending_attempts
        import session_state
        reconcile_pending_attempts(
            project_dir=Path(".").resolve(),
            exclude_output_prefixes=session_state.other_live_session_prefixes(
                state, session_id
            ),
        )
    except Exception:
        pass

    lines: list[str] = [f"Pairmode v{pairmode_version} is active in this repo."]
    if reset_notice:
        lines.append(reset_notice)
    if staleness_notice:
        lines.append(staleness_notice)

    # Current story
    story = state.get("current_story")
    if isinstance(story, dict):
        sid = story.get("id", "")
        title = story.get("title", "")
        status = story.get("status", "")
        lines.append(f"Current story: {sid} — {title} [{status}]")
    else:
        lines.append("No active story. Set one with: story_context.py --set RAIL-NNN")

    # Loaded modules
    modules = state.get("last_loaded_modules", [])
    if modules:
        lines.append(f"Loaded modules: {', '.join(modules)}")

    # Sidebar
    if _pipe_active():
        lines.append(f"Companion sidebar: active (pipe: {PIPE_PATH})")
    else:
        project_dir = Path(".").resolve()
        repo_root = Path(__file__).resolve().parent.parent
        start_sh = repo_root / "skills" / "companion" / "scripts" / "start_sidebar.sh"
        sidebar_log = project_dir / ".companion" / "sidebar.log"
        lines.append("Companion sidebar: not detected")
        lines.append("  To start (macOS / desktop Linux):")
        lines.append(f"    bash {start_sh}")
        if sidebar_log.exists():
            lines.append("  If already running in background, attach with:")
            lines.append(f"    tail -f {sidebar_log}")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }))


if __name__ == "__main__":
    main()
