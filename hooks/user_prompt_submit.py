#!/usr/bin/env python3
"""UserPromptSubmit hook — records a monotonic user-turn sequence counter.

Thin-delegation exception: fires on every user prompt submission. Increments
``context_budget_user_turn_seq`` in state.json by 1 (starting from 0 when
absent). This is the sole signal that a genuine human turn has occurred,
consumed by ``context_budget.should_block()`` (INFRA-193) to distinguish
"the block fired" from "the user actually replied" when deciding whether to
suppress a repeat context-budget prompt.

Never emits a decision. Never blocks. Write-only, one state.json read-modify-
write, matching the ``post_tool_use.py`` Task/Agent branch contract.
"""
import json
import sys
from pathlib import Path


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    project_dir = Path(data.get("cwd") or ".")
    state_path = project_dir / ".companion" / "state.json"

    try:
        if not state_path.exists():
            sys.exit(0)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            sys.exit(0)
        current = state.get("context_budget_user_turn_seq", 0)
        try:
            current = int(current)
        except (TypeError, ValueError):
            current = 0
        state["context_budget_user_turn_seq"] = current + 1
        state_path.write_text(json.dumps(state, indent=2))
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
