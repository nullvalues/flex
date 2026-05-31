#!/usr/bin/env python3
"""
PreToolUse hook — context budget enforcement (CER-027).

Thin delegate. All decision logic lives in
skills/pairmode/scripts/context_budget.py. This script:
  1. Parses stdin
  2. Skips if tool_name != "Task"
  3. Delegates to context_budget.decide(cwd, transcript_path)
  4. Writes acknowledged_at to state.json (one write; hook owns this)
  5. Emits the module's return value as a Claude Code hook response
No logic beyond delegation. See CLAUDE.md HOOK PERFORMANCE check #1
for the documented exception.
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
    if data.get("tool_name") != "Task":
        sys.exit(0)

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


if __name__ == "__main__":
    main()
