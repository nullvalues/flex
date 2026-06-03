#!/usr/bin/env python3
"""
PreToolUse hook — dispatches to context_budget (Task) and scope_guard (Edit/Write).

Thin dispatcher. Domain logic lives in the named modules:
  - Task  → skills/pairmode/scripts/context_budget.py  (CER-027)
  - Edit/Write → skills/pairmode/scripts/scope_guard.py (Phase 55)
No logic beyond tool-name dispatch, module call, and stdout emit.
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

    if tool_name == "Task":
        try:
            import context_budget
            result = context_budget.decide(
                project_dir=Path(data.get("cwd") or "."),
                transcript_path=data.get("transcript_path") or "",
            )
        except Exception:
            sys.exit(0)
        if result and result.get("block"):
            # Write acknowledged_at to state.json (the one hook-owned write per D11)
            try:
                state_path = Path(data.get("cwd") or ".") / ".companion" / "state.json"
                if state_path.exists():
                    state = json.loads(state_path.read_text())
                    state["context_budget_acknowledged_at"] = result["acknowledged_at"]
                    state_path.write_text(json.dumps(state, indent=2))
            except Exception:
                pass
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
