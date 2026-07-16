"""
cold_read_guard.py — Cold-read enforcement for the pre_tool_use hook (INFRA-196).

check_path(file_path, agent_type, project_dir) -> (allowed: bool, reason: str)

Blocks the orchestrator (top-level session, no agent_type in the PreToolUse
payload) from directly Read-ing story specs (docs/stories/**) or agent role
files (.claude/agents/**). These must be handed to the builder/reviewer
subagent as a story ID and read cold by that subagent instead — see
CLAUDE.build.md's spawn contract.

Subagent reads (agent_type present and non-empty) are always allowed,
unconditionally, without inspecting file_path.

Fails open: on any unexpected exception, returns (True, reason).
"""
from __future__ import annotations

from pathlib import Path

_PROTECTED_PREFIXES = ("docs/stories/", ".claude/agents/")


def check_path(
    file_path: str | Path,
    agent_type: str | None,
    project_dir: str | Path,
) -> tuple[bool, str]:
    try:
        if agent_type:
            return True, "subagent read — allowing"

        project = Path(project_dir).resolve()
        normalised = _normalise(file_path, project)
        if normalised is None:
            return False, "path escapes project root"

        for prefix in _PROTECTED_PREFIXES:
            if normalised == prefix.rstrip("/") or normalised.startswith(prefix):
                return False, (
                    f"orchestrator must not Read {prefix}** directly — pass the "
                    "story ID to the builder/reviewer subagent and let it read cold"
                )

        return True, "not a protected orchestrator-read path"
    except Exception as exc:  # fail open
        return True, f"cold_read_guard error — allowing: {exc}"


def _normalise(file_path: str | Path, project: Path) -> str | None:
    p = Path(file_path)
    try:
        if p.is_absolute():
            resolved = p.resolve()
        else:
            resolved = (project / p).resolve()
        rel = resolved.relative_to(project)
    except ValueError:
        return None
    s = rel.as_posix()
    return s.lstrip("./") if s.startswith("./") else s
