#!/usr/bin/env python3
"""
PreToolUse hook — dispatches to context_budget (Task/Agent) and scope_guard (Edit/Write).

Thin dispatcher. Domain logic lives in the named modules:
  - Task/Agent → skills/pairmode/scripts/context_budget.py  (CER-027, CER-049, INFRA-182)
    One delegated module call:
      decide(project_dir) — reads context_current_tokens from state.json
      (written by post_tool_use.py after each completed spawn, or by the
      SessionStart baseline on /clear); the hook writes
      context_budget_acknowledged_at to state.json when result["block"] is True.
    No story_id lookup; no live-count write (PostToolUse handles that).
  - Edit/Write → skills/pairmode/scripts/scope_guard.py (Phase 55)
    Read-only; no state writes.

CER-049: Current Claude Code harnesses name the agent-spawn tool `Agent`
(was `Task` in earlier harnesses). The matcher in hooks.json and the
tool-name check here accept both names so the context-budget gate fires
under either harness.

INFRA-182: simplified Task/Agent branch — removed story_id lookup and the
live_tokens state write (now PostToolUse's job). decide() now takes only
project_dir.
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

            project_dir = Path(data.get("cwd") or ".")
            result = context_budget.decide(project_dir=project_dir)
        except Exception:
            sys.exit(0)

        if result and result.get("block"):
            try:
                state_path = project_dir / ".companion" / "state.json"
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
