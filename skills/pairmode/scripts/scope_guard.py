"""
scope_guard.py — Story file-scope enforcement for the pre_tool_use hook.

check_path(file_path, project_dir) -> (allowed: bool, reason: str)

Fails open: when state, permissions file, or any read fails, returns (True, reason).
Protected paths (PROTECTED_GLOBS) are blocked even with no active story.
"""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

PROTECTED_GLOBS = [
    "hooks/**",
    ".claude-plugin/**",
    "skills/seed/**",
    "skills/companion/**",
    "lessons/**",
    ".claude/settings.json",
    ".claude/settings.local.json",
]


def _is_protected(path_str: str) -> bool:
    return any(fnmatch.fnmatch(path_str, g) for g in PROTECTED_GLOBS)


def check_path(
    file_path: str | Path,
    project_dir: str | Path,
) -> tuple[bool, str]:
    project = Path(project_dir).resolve()

    story_id = _read_current_story(project)
    if not story_id:
        relative_path = _normalise(file_path, project)
        if relative_path is not None and _is_protected(relative_path):
            return (
                False,
                f"{relative_path} is a protected path — requires an active story with this file in primary_files",
            )
        return True, "no active story — allowing"

    allowed_paths = _read_allowed_paths(project, story_id)
    if allowed_paths is None:
        return True, f"no permissions file for {story_id} — allowing"
    if not allowed_paths:
        return True, f"empty allowed_paths for {story_id} — allowing"

    normalised = _normalise(file_path, project)
    if normalised is None:
        return False, "path escapes project root"

    if normalised in allowed_paths:
        return True, "allowed"
    return False, f"not in story scope for {story_id}: {normalised}"


def _read_current_story(project: Path) -> str | None:
    try:
        state = json.loads((project / ".companion" / "state.json").read_text())
        # current_story is stored as {"id": "RAIL-NNN", "set_at": "..."} by story_context.py
        val = state.get("current_story", {}).get("id")
        return str(val).strip() if val else None
    except Exception:
        return None


def _read_allowed_paths(project: Path, story_id: str) -> list[str] | None:
    perm_path = project / "docs" / "phases" / "permissions" / f"{story_id}.json"
    if not perm_path.exists():
        return None
    try:
        data = json.loads(perm_path.read_text())
        paths = data.get("allowed_paths")
        return [_norm_str(p) for p in paths] if isinstance(paths, list) else []
    except Exception:
        return None  # malformed — fail open


def _normalise(file_path: str | Path, project: Path) -> str | None:
    p = Path(file_path)
    if p.is_absolute():
        try:
            return _norm_str(p.resolve().relative_to(project))
        except ValueError:
            return None
    return _norm_str(p)


def _norm_str(p: str | Path) -> str:
    s = Path(p).as_posix()
    return s.lstrip("./") if s.startswith("./") else s
