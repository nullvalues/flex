#!/usr/bin/env python3
# thin dispatcher — Write/Edit/MultiEdit → sidebar pipe relay; Task/Agent → context_budget.py
"""
PostToolUse hook — Pair Partner + Validator roles.

Fires after every file write/edit. Thin relay only.
Sends file change event to sidebar for UML delta + spec check.

Also fires after Task/Agent tool calls. Two delegated calls (never blocks —
each wrapped independently, exits silently on any failure):
  1. context_budget.read_current_tokens() (INFRA-182) — reads the JSONL
     transcript and writes context_current_tokens +
     context_current_tokens_recorded_at to state.json.
  2. subagent_transcript.record_attempt_from_transcript() (INFRA-236) —
     reads the same live transcript for the just-completed spawn's own
     usage, plus tool_input/tool_response/state.json for role/story/model/
     outcome, and writes one effort.db attempt row. This is a DIFFERENT
     metric than (1) — a subagent's own resource cost never entered the
     orchestrator's own context window (DP7); the two calls must never be
     merged or have their outputs cross-written.

Protected-file classification is intentionally NOT done here.
The hook must stay a thin relay (millisecond exit, no file reads beyond
the grandfathered state.json read).  The sidebar process is responsible
for loading deny-rationale.json and calling display_override_prompt()
when a changed file matches a protected-file rule.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))


PIPE_PATH = os.path.join(tempfile.gettempdir(), "companion.pipe")
STATE_PATH = ".companion/state.json"

WATCHED_TOOLS = {"Write", "Edit", "MultiEdit"}


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    if tool_name in ("Task", "Agent"):
        # Two delegated calls (INFRA-236), each independently wrapped so a
        # failure in one never blocks the other. Never blocks — exits
        # silently on any failure.
        project_dir = Path(data.get("cwd") or ".")
        session_id = data.get("session_id", "")

        # 1. context_current_tokens writer (INFRA-182) — read JSONL, write
        #    fresh count to state.json.
        try:
            import context_budget
            from state_utils import _atomic_write_json
            live_tokens = context_budget.read_current_tokens(
                project_dir=project_dir,
                session_id=session_id,
            )
            if live_tokens is not None:
                from datetime import datetime, timezone
                state_path = project_dir / ".companion" / "state.json"
                if state_path.exists():
                    state = json.loads(state_path.read_text())
                    state["context_current_tokens"] = live_tokens
                    state["context_current_tokens_recorded_at"] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    _atomic_write_json(state_path, state)
        except Exception:
            pass

        # 2. effort.db attempt-row writer (INFRA-236) — separate metric,
        #    separate store. See module docstring above.
        try:
            import subagent_transcript
            subagent_transcript.record_attempt_from_transcript(
                project_dir=project_dir,
                session_id=session_id,
                tool_input=data.get("tool_input", {}),
                tool_response=data.get("tool_response"),
                tool_use_id=data.get("tool_use_id"),
            )
        except Exception:
            pass

        sys.exit(0)

    if tool_name not in WATCHED_TOOLS:
        sys.exit(0)

    if not os.path.exists(PIPE_PATH):
        sys.exit(0)

    # get file path from tool input
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""

    cwd = data.get("cwd") or os.getcwd()

    loaded_modules = []
    try:
        state = json.loads(open(STATE_PATH).read())
        loaded_modules = state.get("last_loaded_modules", [])
    except Exception:
        pass

    try:
        fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
        msg: dict = {
            "event": "post_tool_use",
            "type": "file_changed",
            "path": file_path,
            "tool": tool_name,
            "file_path": file_path,
            "loaded_modules": loaded_modules,
            "session_id": data.get("session_id"),
            "cwd": cwd,
        }
        event = json.dumps(msg) + "\n"
        os.write(fd, event.encode())
        os.close(fd)
    except (OSError, BlockingIOError):
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
