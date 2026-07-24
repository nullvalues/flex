#!/usr/bin/env python3
"""UserPromptSubmit hook — thin dispatcher to user_turn_seq.py.

Fires on every user prompt submission. Domain logic (the idempotent
read-modify-write of ``context_budget_user_turn_seq`` in state.json,
including the INFRA-248 duplicate-invocation fingerprint guard) lives
entirely in ``skills/pairmode/scripts/user_turn_seq.py``. This hook does
stdin parsing, one delegated call, and exit — nothing else.

``context_budget_user_turn_seq`` is the sole signal that a genuine human
turn has occurred, consumed by ``context_budget.should_block()``
(INFRA-193) to distinguish "the block fired" from "the user actually
replied" when deciding whether to suppress a repeat context-budget prompt.

Never emits a decision. Never blocks. Write-only, matching the
``post_tool_use.py`` Task/Agent branch contract.
"""
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))

from user_turn_seq import record_user_turn  # noqa: E402


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if not isinstance(data, dict):
        sys.exit(0)

    project_dir = Path(data.get("cwd") or ".")
    record_user_turn(project_dir, data)

    sys.exit(0)


if __name__ == "__main__":
    main()
