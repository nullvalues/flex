"""
scope_guard.py — Story file-scope enforcement for the pre_tool_use hook.

check_path(file_path, project_dir) -> (allowed: bool, reason: str)

Fails open for non-protected paths: when state, permissions file, or any read
fails, returns (True, reason). Protected paths (PROTECTED_GLOBS) fail closed —
blocked with no active story, AND blocked mid-story whenever the active
story's permissions artifact is missing, empty, or malformed (INFRA-253):
a protected path is only satisfiable by an explicit entry in the story's
permissions artifact (derived from the story's `primary_files` + `touches`).
"""
from __future__ import annotations

import fnmatch
import json
import re
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

    # INFRA-281 (CER-095.2): resolve_call_story is handed the *raw*
    # project_dir, not `project` — the worktree identity `project` just
    # collapsed away is exactly the signal resolve_call_story needs to tell
    # concurrent builders apart.
    story_id, source = resolve_call_story(project_dir, file_path)
    if not story_id:
        relative_path = _normalise(file_path, project)
        if relative_path is None:
            return False, "path escapes project root"
        ambiguous_note = None
        if source == "ambiguous":
            claimed = sorted(_read_current_stories_keyed(project))
            ambiguous_note = (
                "ambiguous — multiple stories claimed ("
                + ", ".join(claimed)
                + "); resolving to no active story rather than guessing"
            )
        if _is_protected(relative_path):
            if ambiguous_note:
                return (
                    False,
                    f"{relative_path} is a protected path — {ambiguous_note}; "
                    "requires an active story with this file in primary_files "
                    "or touches, authorized via "
                    "docs/phases/permissions/<story_id>.json",
                )
            return (
                False,
                f"{relative_path} is a protected path — requires an active story "
                "with this file in primary_files or touches, authorized via "
                "docs/phases/permissions/<story_id>.json",
            )
        if ambiguous_note:
            return True, ambiguous_note
        return True, "no active story — allowing"

    normalised = _normalise(file_path, project)
    if normalised is None:
        return False, "path escapes project root"

    # INFRA-253: protected-path status is checked against the worktree-stripped
    # candidate (the real repo-relative identity of the path), not the raw
    # (possibly worktree-prefixed) normalised path.
    candidate = _strip_worktree_prefix(normalised, story_id)
    protected = _is_protected(candidate)

    allowed_paths, status = _read_allowed_paths(project, story_id)

    if status == "missing":
        if protected:
            return False, (
                f"{candidate} is a protected path — no permissions artifact for "
                f"{story_id} (docs/phases/permissions/{story_id}.json missing); "
                "authorization requires the path in the story's primary_files "
                "or touches"
            )
        return True, f"no permissions file for {story_id} — allowing"

    if status == "malformed":
        if protected:
            return False, (
                f"{candidate} is a protected path — permissions artifact for "
                f"{story_id} is malformed; authorization requires the path in "
                "the story's primary_files or touches"
            )
        return True, f"malformed permissions file for {story_id} — allowing"

    # status == "ok"
    if not allowed_paths:
        if protected:
            return False, (
                f"{candidate} is a protected path — empty allowed_paths for "
                f"{story_id}; authorization requires the path in the story's "
                "primary_files or touches"
            )
        return True, f"empty allowed_paths for {story_id} — allowing"

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


# Copied from flex_build._STORY_ID_RE (source of truth for the story-ID
# shape) rather than imported: this module sits on the pre_tool_use hook
# path and must stay import-light — flex_build pulls in click, effort_db,
# next_action and more.
_STORY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d{3}$")

# The literal `source` values `resolve_call_story` can return, defined once
# so tests can enumerate them without hardcoding the strings twice.
RESOLVE_CALL_STORY_SOURCES = frozenset(
    {
        "worktree-cwd",
        "worktree-path",
        "state-single",
        "state-legacy",
        "ambiguous",
        "none",
    }
)


def _read_state_dict(project: Path) -> dict:
    try:
        return json.loads((project / ".companion" / "state.json").read_text())
    except Exception:
        return {}


def _read_current_stories_keyed(project: Path) -> dict:
    """Return the ``current_stories`` dict from *project*'s state.json.

    Read-only; never raises. Returns ``{}`` when the key is absent, empty,
    or the state file can't be read — deliberately does **not** fall back to
    the flat ``current_story`` key, so callers that need the legacy fallback
    (``resolve_call_story``'s ``state-legacy`` step) apply it explicitly and
    the two fallback conditions in B5 stay distinguishable.
    """
    state = _read_state_dict(project)
    keyed = state.get("current_stories")
    return keyed if isinstance(keyed, dict) else {}


def _read_legacy_story_id(project: Path) -> str | None:
    state = _read_state_dict(project)
    legacy = state.get("current_story")
    if isinstance(legacy, dict):
        val = legacy.get("id")
        return str(val).strip() if val else None
    return None


def resolve_call_story(
    project_dir: str | Path,
    file_path: str | Path | None = None,
) -> tuple[str | None, str]:
    """Resolve which story a tool call belongs to, per-call, from the call
    itself (INFRA-281 / CER-095.2).

    A single global ``state.json["current_story"]`` slot cannot answer "which
    story is this write for?" once more than one story can be in flight —
    whichever story was stamped last wins for every builder. The answer is
    already carried by the call: a builder's tool calls come from its own
    worktree (``.pairmode-worktrees/<ID>/``), the same claim INFRA-280 taught
    the resolver to read. Only when the call demonstrably comes from the main
    checkout, with no worktree signal in either the cwd or the target path,
    does this fall back to ``state.json`` — and even then it refuses to guess
    when more than one story is claimed there.

    Returns ``(story_id, source)`` where ``source`` is one of
    ``RESOLVE_CALL_STORY_SOURCES``. Resolution order:

    1. ``worktree-cwd`` — *project_dir* is, or is inside,
       ``<main>/.pairmode-worktrees/<ID>/`` with ``<ID>`` matching
       ``_STORY_ID_RE``;
    2. ``worktree-path`` — otherwise, the repo-relative *file_path* begins
       with ``.pairmode-worktrees/<ID>/`` with ``<ID>`` matching
       ``_STORY_ID_RE``;
    3. ``state-single`` — otherwise, ``current_stories`` holds exactly one
       entry;
    4. ``state-legacy`` — otherwise, ``current_stories`` is absent/empty and
       the flat ``current_story`` names a story;
    5. ``ambiguous`` — otherwise, ``current_stories`` holds two or more
       entries: ``story_id`` is ``None`` (never "pick the most recent" —
       false confidence here is worse than no answer);
    6. ``none`` — no signal at all: ``story_id`` is ``None``.

    Performs no writes, never raises (any exception resolves to
    ``(None, "none")``), and does not require the resolved worktree ID to
    appear in ``current_stories`` — the worktree itself is the claim
    (INFRA-280), authoritative over the state file, not subordinate to it.
    """
    try:
        raw = Path(project_dir).resolve()
        main = _resolve_main_project_root(raw)

        # 1. worktree-cwd
        try:
            rel_parts = raw.relative_to(main).parts
        except ValueError:
            rel_parts = ()
        if (
            len(rel_parts) >= 2
            and rel_parts[0] == _WORKTREE_PREFIX.rstrip("/")
            and _STORY_ID_RE.match(rel_parts[1])
        ):
            return rel_parts[1], "worktree-cwd"

        # 2. worktree-path. SECURITY (regression guard for
        # test_scope_guard_blocks_foreign_story_worktree_path_bypass): a
        # story ID lifted straight out of the *target path* must not be fed
        # back into `_strip_worktree_prefix` for that same path — the two
        # would always agree by construction, silently defeating that
        # function's "only strip when the segment equals the caller's real
        # active story" guarantee, and letting any caller impersonate any
        # story merely by spelling a worktree-shaped path. Unlike
        # worktree-cwd (where the cwd's mere existence as the process's real
        # working directory *is* the INFRA-280 claim), a path string proves
        # nothing about who issued the call. So this step additionally
        # requires the named worktree directory to exist on disk — the same
        # standard INFRA-280's claim reader (`flex_build.claimed_story_ids`)
        # applies to a cwd-based claim, applied here to a path-based one.
        if file_path is not None:
            normalised = _normalise(file_path, main)
            if normalised is not None and normalised.startswith(_WORKTREE_PREFIX):
                remainder = normalised[len(_WORKTREE_PREFIX):]
                segment, _sep, rest = remainder.partition("/")
                if (
                    rest
                    and _STORY_ID_RE.match(segment)
                    and (main / _WORKTREE_PREFIX.rstrip("/") / segment).is_dir()
                ):
                    return segment, "worktree-path"

        # 3-6: state.json fallback, main-checkout calls only.
        return _resolve_story_from_state(main)
    except Exception:
        return None, "none"


def _resolve_story_from_state(main: Path) -> tuple[str | None, str]:
    """Steps 3-6 of ``resolve_call_story``'s order: the state.json-only
    fallback rules, given the already-resolved main checkout root.
    """
    keyed = _read_current_stories_keyed(main)
    if len(keyed) == 1:
        return next(iter(keyed)), "state-single"
    if not keyed:
        legacy_id = _read_legacy_story_id(main)
        if legacy_id:
            return legacy_id, "state-legacy"
        return None, "none"
    return None, "ambiguous"


def _read_current_story(project: Path) -> str | None:
    """Thin wrapper over ``resolve_call_story``'s state-only rules.

    Kept for ``hooks/pre_tool_use.py``'s (pre-INFRA-281) import and for any
    other caller that only has *project* — not a raw call cwd or target
    path — to resolve against. ``state-single``/``state-legacy`` return the
    resolved ID; ``ambiguous``/``none`` return ``None`` rather than a guess,
    exactly as ``resolve_call_story`` does when two stories are active.
    Never raises.
    """
    try:
        main = _resolve_main_project_root(Path(project).resolve())
        story_id, _source = _resolve_story_from_state(main)
        return story_id
    except Exception:
        return None


def _read_allowed_paths(project: Path, story_id: str) -> tuple[list[str] | None, str]:
    """Returns (allowed_paths, status) where status is one of:
    "missing" (no permissions artifact for the story), "malformed" (artifact
    exists but is unreadable/invalid), or "ok" (artifact read successfully;
    allowed_paths may still be an empty list).

    INFRA-253: status is reported separately from the list itself so
    check_path() can distinguish these three fail-open triggers and apply
    the fail-closed protected-path override to each independently.
    """
    perm_path = project / "docs" / "phases" / "permissions" / f"{story_id}.json"
    if not perm_path.exists():
        return None, "missing"
    try:
        data = json.loads(perm_path.read_text())
        paths = data.get("allowed_paths")
        return ([_norm_str(p) for p in paths] if isinstance(paths, list) else []), "ok"
    except Exception:
        return None, "malformed"


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
    """Resolve *file_path* to an absolute path and contain it against
    *project*, returning the repo-relative posix string, or ``None`` if the
    resolved path is not *project* or a descendant of it (INFRA-255).

    Both relative and absolute inputs are resolved through the same code
    path: a relative input is joined onto *project* (the main-checkout root
    returned by ``_resolve_main_project_root()``, NOT the raw ``project_dir``
    cwd — resolving against a worktree cwd would turn a no-active-story
    protected-path candidate like ``hooks/x.py`` into
    ``.pairmode-worktrees/<id>/hooks/x.py``, which no longer matches
    ``PROTECTED_GLOBS`` in the branch that does not strip the worktree
    prefix; resolving against the main root instead preserves pre-story
    semantics for the common case of an already repo-relative path from a
    build spawn). ``Path.resolve()`` is non-strict on Python 3.11 (it works
    for paths that do not exist yet, which matters for Write creating a new
    file) and collapses ``..`` segments, so containment is enforced by
    ``relative_to()`` on the resolved, absolute path — never by a
    pre-resolution string check for ``..``, which would be trivially evaded
    (e.g. a disguised prefix) and is not a security boundary on its own.

    ``resolve()`` also follows symlinks, so a repo-internal symlink pointing
    outside the project root is denied here too. That is intentional
    fail-closed behaviour, not a bug — do not "fix" it by skipping symlink
    resolution.
    """
    p = Path(file_path)
    candidate = p if p.is_absolute() else project / p
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(project)
    except ValueError:
        return None
    return _norm_str(relative)


def _norm_str(p: str | Path) -> str:
    s = Path(p).as_posix()
    # NOTE: the previous implementation used str.lstrip("./"), which strips
    # every leading "." and "/" character (a character-class strip), not a
    # single "./" prefix — so "./../../etc/passwd" was laundered into the
    # innocuous-looking "etc/passwd". Use a single-prefix removal instead.
    return s.removeprefix("./")
