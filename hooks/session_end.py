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


# INFRA-238: standardized on the hardcoded pipe location post_tool_use.py
# already used. The `pipe_path` state.json key was deleted by
# pairmode_migrate.py's `to-030` step; reading it here was dead code.
PIPE_PATH = os.path.join(tempfile.gettempdir(), "companion.pipe")


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
    print("📌 Remember to close the Flex companion terminal.", file=sys.stderr)
    print("📌 Remember to close the Flex companion terminal.")

    sys.exit(0)


if __name__ == "__main__":
    main()
