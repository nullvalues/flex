#!/usr/bin/env python3
"""
SessionEnd hook — Historian role (deep extraction + reconcile).

Runs async so it doesn't block session exit.
Signals sidebar to do final extraction pass.
The sidebar's session_end handler writes session-end fields to state.json.
"""
import json
import os
import sys
import tempfile
from datetime import datetime
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


PIPE_PATH = "/tmp/companion.pipe"  # legacy fallback
try:
    import json as _json
    _state = _json.loads(open(".companion/state.json").read())
    if _state.get("pipe_path"):
        _validated = _resolve_pipe_path(_state["pipe_path"])
        if _validated is not None:
            PIPE_PATH = _validated
except Exception:
    pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cwd = data.get("cwd", os.getcwd())
    session_id = data.get("session_id", "")

    # signal sidebar to do final extraction + reconcile
    if os.path.exists(PIPE_PATH):
        try:
            fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
            event = (
                json.dumps(
                    {
                        "event": "session_end",
                        "transcript_path": data.get("transcript_path"),
                        "session_id": session_id,
                        "cwd": cwd,
                        "last_session_end": datetime.now().isoformat(),
                        "last_session_closed": True,
                        "mode": "planning",
                    }
                )
                + "\n"
            )
            os.write(fd, event.encode())
            os.close(fd)
        except (OSError, BlockingIOError):
            pass

    # Remind user in Claude session to close companion terminal
    print("📌 Remember to close the Anchor companion terminal.", file=sys.stderr)
    print("📌 Remember to close the Anchor companion terminal.")

    sys.exit(0)


if __name__ == "__main__":
    main()
