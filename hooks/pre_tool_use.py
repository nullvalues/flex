#!/usr/bin/env python3
"""
PreToolUse hook — dispatches to context_budget (Task/Agent) and scope_guard (Edit/Write).

Thin dispatcher. Domain logic lives in the named modules:
  - Task/Agent → skills/pairmode/scripts/context_budget.py  (CER-027, CER-049, INFRA-180)
    One delegated module call:
      decide(project_dir, story_id) — per-story dict lookup block decision;
      the hook writes context_budget_acknowledged_at to state.json when
      result["block"] is True.
    No live-count write; set-context-tokens is the sole writer of
    context_story_tokens.
  - Edit/Write → skills/pairmode/scripts/scope_guard.py (Phase 55)
    Read-only; no state writes.

CER-049: Current Claude Code harnesses name the agent-spawn tool `Agent`
(was `Task` in earlier harnesses). The matcher in hooks.json and the
tool-name check here accept both names so the context-budget gate fires
under either harness.

INFRA-180: removed Phase 72 JSONL additions (read_current_tokens call and
live_tokens path). The Task/Agent branch now makes a single decide() call,
passing story_id for the per-story dict lookup. The state.json write
reduces to context_budget_acknowledged_at only (on block).
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
            story_id = (
                json.loads((project_dir / ".companion" / "state.json").read_text())
                .get("current_story", {})
                .get("id", "")
                if (project_dir / ".companion" / "state.json").exists()
                else ""
            )

            result = context_budget.decide(
                project_dir=project_dir,
                story_id=story_id,
            )
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
