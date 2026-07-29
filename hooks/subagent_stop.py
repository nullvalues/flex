#!/usr/bin/env python3
# thin dispatcher — SubagentStop -> subagent_transcript.reconcile_one
"""SubagentStop hook — deterministic single-row effort.db reconcile.

INFRA-298 (CER-114): `SubagentStop` is the one event the harness fires when
a spawned agent actually finishes — for both synchronous and async/
background spawns (see this story's `## Evidence` section for the live
measurement this hook's existence depends on). This hook is a thin relay:
read stdin, make exactly one delegated call into
`skills/pairmode/scripts/subagent_transcript.reconcile_one`, exit. No
decision logic, no outcome parsing, no direct `effort.db` access, no
block/decision emission, and no `state.json` write live here — all of that
lives in the delegated module (see the security-auditor procedure's
thin-delegation exception list, and `docs/architecture.md` § Hook
architecture).

`SubagentStop` has no `additionalContext` contract to satisfy, so this hook
emits nothing on stdout on every path, and always exits `0` — a hook
failure must never fail a spawn. Best-effort, same style
`hooks/session_start.py`'s reconcile block uses: any exception anywhere in
`main()` is swallowed silently.
"""
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))


def main() -> None:
    try:
        if sys.stdin.isatty():
            return
        raw = sys.stdin.read()
        if not raw:
            return
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return

        project_dir = Path(payload.get("cwd") or ".")
        agent_id = payload.get("agent_id")

        import subagent_transcript
        subagent_transcript.reconcile_one(
            project_dir=project_dir,
            agent_id=agent_id,
            payload=payload,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
