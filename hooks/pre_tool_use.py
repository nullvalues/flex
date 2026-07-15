#!/usr/bin/env python3
"""
PreToolUse hook — dispatches to context_budget (Task/Agent) and scope_guard (Edit/Write).

Thin dispatcher. Domain logic lives in the named modules:
  - Task/Agent → skills/pairmode/scripts/context_budget.py  (CER-027, CER-049, INFRA-182, INFRA-193)
    Additionally scoped to the pairmode build cycle (INFRA-199): the
    context_budget import/call and acknowledgment state write happen only when
    tool_input.subagent_type is one of BUILD_CYCLE_SUBAGENTS. Non-build-cycle
    spawns (general-purpose / Plan / Explore / absent subagent_type) pass
    straight through ungated.
    One delegated module call:
      decide(project_dir) — reads context_current_tokens from state.json
      (written by post_tool_use.py after each completed spawn, or by the
      SessionStart baseline on /clear); the hook writes
      context_budget_acknowledged_at and (INFRA-193)
      context_budget_acknowledged_user_turn_seq to state.json in a single
      read-modify-write when result["block"] is True.
    No story_id lookup; no live-count write (PostToolUse handles that).
  - Edit/Write → skills/pairmode/scripts/scope_guard.py (Phase 55)
    Read-only; no state writes.
  - Read → skills/pairmode/scripts/cold_read_guard.py (INFRA-196)
    Read-only; no state writes. Blocks orchestrator (no agent_type in the
    payload) Reads of docs/stories/** and .claude/agents/** — these must be
    handed to the builder/reviewer subagent as a story ID, not read cold by
    the orchestrator itself.

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

# Build-cycle subagent types the context-budget gate governs (INFRA-199).
# The gate models context growth across the pairmode build loop only; a
# general-purpose / Plan / Explore spawn must never be blocked. Future
# Era-003 WORKER-rail leaf-worker types are enrolled by adding one line here.
BUILD_CYCLE_SUBAGENTS = frozenset({
    "builder",
    "reviewer",
    "loop-breaker",
    "security-auditor",
    "intent-reviewer",
})


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name")

    if tool_name in ("Task", "Agent"):
        subagent_type = data.get("tool_input", {}).get("subagent_type")
        if subagent_type not in BUILD_CYCLE_SUBAGENTS:
            sys.exit(0)
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
                    if "user_turn_seq_at_block" in result:
                        state["context_budget_acknowledged_user_turn_seq"] = result[
                            "user_turn_seq_at_block"
                        ]
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

    elif tool_name == "Read":
        try:
            import cold_read_guard

            allowed, reason = cold_read_guard.check_path(
                file_path=data.get("tool_input", {}).get("file_path", ""),
                agent_type=data.get("agent_type"),
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
