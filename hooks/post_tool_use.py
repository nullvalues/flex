#!/usr/bin/env python3
"""
PostToolUse hook — Pair Partner + Validator roles.

Fires after every file write/edit. Thin relay only.
Sends file change event to sidebar for UML delta + spec check.

Also fires after Task/Agent tool calls (INFRA-182): reads the JSONL
transcript via context_budget.read_current_tokens() and writes
context_current_tokens + context_current_tokens_recorded_at to state.json.
This branch never blocks — exits silently on any failure.

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

WATCHED_TOOLS = {"Write", "Edit", "MultiEdit"}


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    if tool_name in ("Task", "Agent"):
        # Read JSONL, write fresh count to state.json. Never blocks.
        try:
            import context_budget
            project_dir = Path(data.get("cwd") or ".")
            session_id = data.get("session_id", "")
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
                    state_path.write_text(json.dumps(state, indent=2))
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
