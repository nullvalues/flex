#!/usr/bin/env python3
# thin dispatcher — Edit/Write → scope_guard.py; Task/Agent → context_budget.py
"""
PreToolUse hook — dispatches to context_budget (Task/Agent) and scope_guard (Edit/Write).

Thin dispatcher. Domain logic lives in the named modules:
  - Task/Agent → skills/pairmode/scripts/context_budget.py  (CER-027, CER-049, INFRA-182, INFRA-193)
    Additionally scoped to the pairmode build cycle (INFRA-199): the
    context_budget import/call and acknowledgment state write happen only when
    tool_input.subagent_type is one of BUILD_CYCLE_SUBAGENTS. Non-build-cycle
    spawns (general-purpose / Plan / Explore / absent subagent_type) pass
    straight through ungated. BUILD_CYCLE_SUBAGENTS covers only discretionary
    or escalation build-cycle spawns; `reviewer` is exempt (INFRA-246) because
    it is the build loop's mandatory, deterministic next step after every
    builder attempt and never reaches decide().
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

RELEASE-020: re-added a read-only story lookup, scoped strictly to
resolving ``flex_factor`` for the ``decide()`` call. Reuses
``scope_guard._read_current_story`` (current-story lookup) and
``flex_build._story_path`` / ``flex_build._read_story_frontmatter``
(frontmatter parsing) rather than duplicating story-lookup logic. This is
distinct from the story_id lookup INFRA-182 removed (which fed a
now-defunct live-count write) — no state.json write results from this
resolution.
"""
import json, sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))

from state_utils import _atomic_write_json  # noqa: E402

# Build-cycle subagent types the context-budget gate governs (INFRA-199).
# The gate models context growth across the pairmode build loop only; a
# general-purpose / Plan / Explore spawn must never be blocked. Future
# Era-003 WORKER-rail leaf-worker types are enrolled by adding one line here.
#
# This set covers discretionary/escalation build-cycle spawns only — spawns
# where the orchestrator has a legitimate alternative action (report tokens,
# /clear, or reconsider whether to spawn at all) and blocking-to-conserve is
# a valid tradeoff. It never gates a spawn that is the mandatory, only-valid
# next step in the build loop. `reviewer` is exempt (INFRA-246): per
# CLAUDE.build.md's `on reviewer PASS` / `on reviewer FAIL` routing, reviewer
# is the deterministic next step after every builder attempt, and there is
# no alternative action the gate would be preserving by blocking it.
BUILD_CYCLE_SUBAGENTS = frozenset({
    "builder",
    "loop-breaker",
    "security-auditor",
    "intent-reviewer",
})


def _resolve_flex_factor(project_dir: Path) -> float:
    """Resolve the current story's ``flex_factor`` for the context-budget gate.

    RELEASE-020: reuses ``scope_guard._read_current_story`` (current-story
    lookup from ``.companion/state.json``) and ``flex_build._story_path`` /
    ``flex_build._read_story_frontmatter`` (story-frontmatter parsing) rather
    than duplicating story-lookup logic. Fails open to ``1.0`` — the
    pre-INFRA-160 default — when there is no active story, the story file is
    missing, no ``flex_factor`` is set, or any error occurs.
    """
    try:
        from scope_guard import _read_current_story
        from flex_build import _read_story_frontmatter, _story_path

        story_id = _read_current_story(project_dir)
        if not story_id:
            return 1.0
        story_path = _story_path(story_id, project_dir)
        if not story_path.exists():
            return 1.0
        fm = _read_story_frontmatter(story_path)
        return float(fm.get("flex_factor", 1.0) or 1.0)
    except Exception:
        return 1.0


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
            flex_factor = _resolve_flex_factor(project_dir)
            result = context_budget.decide(project_dir=project_dir, flex_factor=flex_factor)
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
                    _atomic_write_json(state_path, state)
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
