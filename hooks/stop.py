#!/usr/bin/env python3
"""
Stop hook — Historian role (incremental capture).

Thin relay only. No API calls. Must exit fast.
Writes event to pipe for sidebar to process.
Sidebar does the actual extraction and conflict checking.
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
STATE_PATH = ".companion/state.json"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # only relay if pipe exists and someone is reading it
    if not os.path.exists(PIPE_PATH):
        sys.exit(0)

    # read mode and loaded modules from state
    mode = "planning"
    loaded_modules = []
    try:
        state = json.loads(open(STATE_PATH).read())
        mode = state.get("mode", "planning")
        loaded_modules = state.get("last_loaded_modules", [])
    except Exception:
        pass

    try:
        fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
        event = (
            json.dumps(
                {
                    "event": "stop",
                    "mode": mode,
                    "loaded_modules": loaded_modules,
                    "transcript_path": data.get("transcript_path"),
                    "session_id": data.get("session_id"),
                    "cwd": data.get("cwd"),
                }
            )
            + "\n"
        )
        os.write(fd, event.encode())
        os.close(fd)
    except (OSError, BlockingIOError):
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
