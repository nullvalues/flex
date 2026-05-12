#!/usr/bin/env python3
"""
PermissionRequest hook — matcher: ExitPlanMode
Relays plan content to companion sidebar for impact analysis.
Does NOT auto-approve — lets Claude Code show the normal plan approval UI.
"""
import json
import os
import sys
import tempfile
from pathlib import Path


def _resolve_pipe_path(raw_path: str) -> str | None:
    """Validate that a configured pipe path resolves under the system tempdir.

    Returns the resolved path string when valid; returns None when the path
    is malformed or escapes the tempdir, signalling callers to keep the
    legacy fallback. (CER-009)
    """
    try:
        candidate = Path(raw_path).resolve()
        if candidate.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            return str(candidate)
    except Exception:
        return None
    return None


PIPE_PATH = os.path.join(tempfile.gettempdir(), "companion.pipe")  # legacy fallback
try:
    import json as _json
    _state = _json.loads(open(".companion/state.json").read())
    if _state.get("pipe_path"):
        _validated = _resolve_pipe_path(_state["pipe_path"])
        if _validated:
            PIPE_PATH = _validated
except Exception:
    pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    # grab plan content from tool_input + loaded modules from state
    tool_input = data.get("tool_input", {}) or {}
    plan = (tool_input.get("plan", "") or "")[:20000]

    loaded_modules = []
    try:
        with open(".companion/state.json") as f:
            loaded_modules = json.load(f).get("last_loaded_modules", [])
    except Exception:  # nosec B110
        pass

    # signal companion: do the deep extraction pass now + flip mode to implementation
    if os.path.exists(PIPE_PATH):
        try:
            fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
            event = (
                json.dumps(
                    {
                        "event": "exit_plan_mode",
                        "transcript_path": data.get("transcript_path"),
                        "session_id": data.get("session_id"),
                        "cwd": data.get("cwd"),
                        "plan": plan,
                        "loaded_modules": loaded_modules,
                    }
                )
                + "\n"
            )
            os.write(fd, event.encode())
            mode_event = json.dumps({"event": "mode_change", "mode": "implementation"}) + "\n"
            os.write(fd, mode_event.encode())
            os.close(fd)
        except (OSError, BlockingIOError):
            pass

    # Don't output a decision — let Claude Code show the normal plan approval UI


if __name__ == "__main__":
    main()
