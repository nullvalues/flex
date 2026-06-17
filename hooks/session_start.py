#!/usr/bin/env python3
"""SessionStart hook — injects pairmode context into Claude's session.

Thin-delegation exception: when Claude Code passes a stdin payload containing
``source`` (one of ``"startup"``, ``"resume"``, ``"clear"``, ``"compact"``),
this hook delegates the dead-reckoning counter reset decision to
``skills/pairmode/scripts/session_reset.decide_reset()`` (CER-047 / Phase 68
INFRA-175 / INFRA-180). All decision logic and timestamp generation live in
that module; the hook owns one state write (all keys returned by
``decide_reset()``: ``context_current_tokens``,
``context_current_tokens_recorded_at``, and ``context_session_reset_at``)
when ``decide_reset()`` returns a dict with ``should_reset=True``.
"""
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))


def _pipe_active(pipe_path: str) -> bool:
    return bool(pipe_path) and Path(pipe_path).exists()


def _read_source_from_stdin() -> str | None:
    """Read the ``source`` field from the SessionStart stdin payload.

    Returns ``None`` on any parse failure (backwards compatible with direct
    invocation and older harnesses that pass no stdin).
    """
    try:
        if sys.stdin.isatty():
            return None
        raw = sys.stdin.read()
        if not raw:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        source = data.get("source")
        if isinstance(source, str):
            return source
        return None
    except Exception:
        return None


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
    source = _read_source_from_stdin()
    reset_notice: str | None = None
    try:
        import session_reset
        reset_result = session_reset.decide_reset(source, state)
        if isinstance(reset_result, dict) and reset_result.get("should_reset"):
            baseline = reset_result["context_current_tokens"]
            # Write all keys returned by decide_reset to state.json.
            state["context_current_tokens"] = baseline
            state["context_current_tokens_recorded_at"] = reset_result[
                "context_current_tokens_recorded_at"
            ]
            state["context_session_reset_at"] = reset_result["context_session_reset_at"]
            state_path.write_text(
                json.dumps(state, indent=2), encoding="utf-8"
            )
            reset_notice = (
                f"Context counter reset to {baseline} "
                f"(session source: {source})."
            )
    except Exception:
        # Reset path is best-effort; never break the status block.
        pass

    lines: list[str] = [f"Pairmode v{pairmode_version} is active in this repo."]
    if reset_notice:
        lines.append(reset_notice)

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
    pipe_path = state.get("pipe_path", "")
    if _pipe_active(pipe_path):
        lines.append(f"Companion sidebar: active (pipe: {pipe_path})")
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
