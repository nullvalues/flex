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
    # INFRA-238: *project_dir* is the tool call's cwd, which for a story-build
    # spawn is the per-story worktree (<main>/.pairmode-worktrees/<story-id>/),
    # not the main checkout. state.json and the permissions artifacts only
    # ever live in the main checkout — resolve it here so scope enforcement
    # works regardless of the spawn's cwd.
    project = _resolve_main_project_root(Path(project_dir).resolve())

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

    candidate = _strip_worktree_prefix(normalised, story_id)

    if candidate in allowed_paths:
        return True, "allowed"
    return False, f"not in story scope for {story_id}: {normalised}"


def _resolve_main_project_root(project: Path) -> Path:
    """Resolve the main checkout root even when *project* is a per-story
    worktree (``<main>/.pairmode-worktrees/<story-id>/``).

    A linked git worktree has no ``.companion/`` of its own; ``state.json``
    and the permission artifacts only ever live in the main checkout. A
    linked worktree's ``.git`` is a *file* (not a directory) containing
    ``gitdir: <main>/.git/worktrees/<name>``; resolve that back up to the
    main checkout root. Falls back to *project* unchanged when it is not a
    linked worktree, or the ``.git`` file can't be parsed — this is a
    best-effort resolution, never a hard failure.
    """
    git_marker = project / ".git"
    if not git_marker.is_file():
        return project
    try:
        text = git_marker.read_text(encoding="utf-8").strip()
    except OSError:
        return project
    if not text.startswith("gitdir:"):
        return project
    raw = text.split(":", 1)[1].strip()
    gitdir = Path(raw)
    if not gitdir.is_absolute():
        gitdir = (project / gitdir).resolve()
    else:
        gitdir = gitdir.resolve()
    # A linked worktree's gitdir is <main>/.git/worktrees/<name>; the main
    # checkout root is three levels up from there.
    if gitdir.parent.name != "worktrees":
        return project
    candidate = gitdir.parent.parent.parent
    return candidate if candidate.is_dir() else project


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


_WORKTREE_PREFIX = ".pairmode-worktrees/"


def _strip_worktree_prefix(path: str, active_story_id: str | None) -> str:
    """Strip a leading ``.pairmode-worktrees/<segment>/`` prefix from *path*,
    but ONLY when ``<segment>`` equals *active_story_id*.

    A build spawn's cwd is the per-story worktree
    (``.pairmode-worktrees/<story-id>/``), so a path edited there
    (``.pairmode-worktrees/INFRA-238/skills/foo.py``) never matches an
    ``allowed_paths`` entry generated from ``primary_files: [skills/foo.py]``
    unless this prefix is stripped first. But stripping it unconditionally —
    regardless of which story's worktree the path actually names — lets a
    path belonging to a DIFFERENT, concurrently in-progress story's worktree
    (``.pairmode-worktrees/INFRA-999/skills/foo.py`` while INFRA-238 is
    active) get misidentified as in-scope purely because its trailing
    segments match an allowed_paths entry name after stripping. That defeats
    per-story worktree isolation. So: only strip when the worktree segment
    equals the currently active story's ID; any other segment (or no active
    story) is left untouched and therefore falls through to the normal
    out-of-scope/not-found comparison below, which will not match.
    """
    if not path.startswith(_WORKTREE_PREFIX):
        return path
    remainder = path[len(_WORKTREE_PREFIX):]
    segment, _sep, rest = remainder.partition("/")
    if not active_story_id or not rest or segment != active_story_id:
        return path
    return rest


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
