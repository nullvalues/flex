#!/usr/bin/env python3
"""
PreToolUse hook — dispatches to context_budget (Task/Agent) and scope_guard (Edit/Write).

Thin dispatcher. Domain logic lives in the named modules:
  - Task/Agent → skills/pairmode/scripts/context_budget.py  (CER-027, CER-049)
    Two delegated module calls:
      (a) read_current_tokens(project_dir, session_id) — JSONL-only live count;
          when successful the hook writes context_current_tokens +
          context_current_tokens_recorded_at to state.json.
      (b) decide(project_dir, session_id) — JSONL-first, state.json-fallback
          block decision; the hook writes context_budget_acknowledged_at
          to state.json when result["block"] is True.
    Both state writes are merged into a single write_text() call.
  - Edit/Write → skills/pairmode/scripts/scope_guard.py (Phase 55)
    Read-only; no state writes.

CER-049: Current Claude Code harnesses name the agent-spawn tool `Agent`
(was `Task` in earlier harnesses). The matcher in hooks.json and the
tool-name check here accept both names so the context-budget gate fires
under either harness.
"""
import json, sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name")

    if tool_name in ("Task", "Agent"):
        try:
            import context_budget
            from datetime import datetime, timezone

            project_dir = Path(data.get("cwd") or ".")
            session_id = data.get("session_id", "")

            # JSONL-only read — for state.json display update.
            live_tokens = context_budget.read_current_tokens(
                project_dir=project_dir,
                session_id=session_id,
            )

            # Block decision (JSONL-first, state.json fallback internally).
            result = context_budget.decide(
                project_dir=project_dir,
                session_id=session_id,
            )
        except Exception:
            sys.exit(0)

        # Merge state.json writes (live count + optional acknowledged_at).
        needs_write = live_tokens is not None or (result and result.get("block"))
        if needs_write:
            try:
                state_path = project_dir / ".companion" / "state.json"
                if state_path.exists():
                    state = json.loads(state_path.read_text())
                    if live_tokens is not None:
                        state["context_current_tokens"] = live_tokens
                        state["context_current_tokens_recorded_at"] = (
                            datetime.now(timezone.utc).isoformat()
                        )
                    if result and result.get("block"):
                        state["context_budget_acknowledged_at"] = result["acknowledged_at"]
                    state_path.write_text(json.dumps(state, indent=2))
            except Exception:
                pass

        if result and result.get("block"):
            print(json.dumps({"decision": "block", "reason": result["reason"]}))
        sys.exit(0)

    elif tool_name in ("Edit", "Write"):
        try:
            import scope_guard
            file_path = data.get("tool_input", {}).get("file_path", "")
            allowed, reason = scope_guard.check_path(
                file_path=file_path,
                project_dir=Path(data.get("cwd") or "."),
            )
        except Exception:
            sys.exit(0)
        if not allowed:
            print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
