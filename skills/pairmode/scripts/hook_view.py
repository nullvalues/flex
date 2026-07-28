"""hook_view.py — merged, provenance-tagged view of every hook registration
a project actually runs under (INFRA-288, CER-104).

Duplicate-hook detection was structurally blind before this module existed:
`fleet_discovery._check_duplicate_hooks` and
`pairmode_sync._audit_duplicate_hooks` each grouped registrations *within one
`.claude/settings.json`*, so a hook registered once in settings.json and once
in an installed plugin's `hooks/hooks.json` (the CER-104 shape — every effort
row written twice) was reported as **0 duplicates**. This module builds the
union view — `settings.json` + `settings.local.json` + every discoverable
plugin `hooks/hooks.json` — with each entry carrying its source, so both
detectors (and `bootstrap`'s registrar skip) see the whole picture.

This is deliberately a *third* module that both `fleet_discovery.py` (fleet
scanning) and `pairmode_sync.py` (per-project sync) may import: those two must
not depend on each other, and the shared grouping logic living here is what
lets both stay independent.

**Plugin layout caveat (load-bearing):** Claude Code's on-disk plugin layout
under `~/.claude/plugins/` is **not a stable public contract**. Discovery
therefore globs tolerantly (bounded depth), degrades to today's settings-only
view when the layout is unrecognised or absent — never raises inside a fleet
scan or a bootstrap run — and offers the ``FLEX_PLUGIN_HOOKS`` environment
variable (``os.pathsep``-separated absolute paths to plugin ``hooks.json``
files) as the escape hatch when the glob misses a real install.

Stdlib-only: this module is imported by CLI/fleet/bootstrap code and must not
grow a click or third-party dependency. It is never imported on the hook path
— hooks stay thin relays (C4).

Every public function is total: malformed input returns the safe empty value,
never raises.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

#: Source labels carried by every merged-view entry (B2).
HOOK_SOURCE_SETTINGS = "settings"
HOOK_SOURCE_SETTINGS_LOCAL = "settings.local"
HOOK_SOURCE_PLUGIN = "plugin"

#: Environment escape hatch for plugin discovery (see module docstring):
#: ``os.pathsep``-separated absolute paths to plugin ``hooks.json`` files.
FLEX_PLUGIN_HOOKS_ENV = "FLEX_PLUGIN_HOOKS"

#: Maximum path depth (components under ``<home>/.claude/plugins/``) the
#: plugin glob will look for a ``hooks/hooks.json`` file at. Observed live
#: layout: ``marketplaces/<marketplace>/plugins/<plugin>/hooks/hooks.json``
#: (6 components); the bound keeps an adversarially deep or looped tree from
#: turning discovery into a filesystem walk.
_PLUGIN_GLOB_MAX_DEPTH = 6


def _resolve_home(home: "Path | str | None") -> "Path | None":
    """Resolve the home directory to scan; ``None`` means the real home."""
    try:
        if home is not None:
            return Path(home)
        return Path.home()
    except Exception:
        return None


def plugin_hook_files(home: "Path | str | None" = None) -> "list[Path]":
    """Return the plugin ``hooks/hooks.json`` files visible to *home* (B4).

    A bounded glob (depth <= ``_PLUGIN_GLOB_MAX_DEPTH`` components) under
    ``<home>/.claude/plugins/``, plus every path listed in the
    ``FLEX_PLUGIN_HOOKS`` environment variable (``os.pathsep``-separated
    absolute paths). Returns ``[]`` — never raises, never scans outside
    *home* — when the directory is absent or the layout is unrecognised
    (see the module docstring: the plugin layout is not a stable contract,
    so tolerance here, not accuracy, is the load-bearing property).
    """
    files: "list[Path]" = []
    seen: "set[str]" = set()

    try:
        home_path = _resolve_home(home)
        if home_path is not None:
            plugins_root = home_path / ".claude" / "plugins"
            if plugins_root.is_dir():
                resolved_root = plugins_root.resolve()
                # Depth-bounded glob: "hooks/hooks.json" itself is 2
                # components, so allow 0..(max-2) wildcard directories
                # above it.
                for extra in range(0, _PLUGIN_GLOB_MAX_DEPTH - 1):
                    pattern = "/".join(["*"] * extra + ["hooks", "hooks.json"])
                    try:
                        matches = sorted(plugins_root.glob(pattern))
                    except Exception:
                        continue
                    for match in matches:
                        try:
                            if not match.is_file():
                                continue
                            # Never follow a symlink out of home's plugin
                            # tree: a path whose resolution escapes the
                            # plugins root is skipped, not followed.
                            match.resolve().relative_to(resolved_root)
                        except (OSError, ValueError):
                            continue
                        key = str(match)
                        if key not in seen:
                            seen.add(key)
                            files.append(match)
    except Exception:
        pass

    try:
        env_value = os.environ.get(FLEX_PLUGIN_HOOKS_ENV, "")
        for token in env_value.split(os.pathsep):
            token = token.strip()
            if not token:
                continue
            candidate = Path(token)
            if not candidate.is_absolute():
                continue
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                files.append(candidate)
    except Exception:
        pass

    return files


def hook_sources(
    project_dir: "Path | str", *, home: "Path | str | None" = None
) -> "list[dict]":
    """Return the ordered ``{"source", "path"}`` list the merged view is
    built from (B3): ``settings``, then ``settings.local``, then one entry
    per discovered plugin ``hooks.json``. Total — never raises.
    """
    sources: "list[dict]" = []
    try:
        project_path = Path(project_dir)
        claude_dir = project_path / ".claude"
        sources.append(
            {
                "source": HOOK_SOURCE_SETTINGS,
                "path": str(claude_dir / "settings.json"),
            }
        )
        sources.append(
            {
                "source": HOOK_SOURCE_SETTINGS_LOCAL,
                "path": str(claude_dir / "settings.local.json"),
            }
        )
        for plugin_file in plugin_hook_files(home):
            sources.append(
                {"source": HOOK_SOURCE_PLUGIN, "path": str(plugin_file)}
            )
    except Exception:
        pass
    return sources


def _load_hooks_dict(path: "Path | str") -> dict:
    """Read *path* and return its top-level ``hooks`` dict, or ``{}``.

    A missing, unparseable, or malformed-shape file is treated as absent —
    a hand-edited settings file must never crash a fleet scan (same
    discipline as the pre-INFRA-288 detectors it replaces).
    """
    try:
        file_path = Path(path)
        if not file_path.is_file():
            return {}
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    hooks_top = data.get("hooks")
    if not isinstance(hooks_top, dict):
        return {}
    return hooks_top


def merged_hook_view(
    project_dir: "Path | str", *, home: "Path | str | None" = None
) -> "list[dict]":
    """Flatten every hook registration visible to *project_dir* into one
    provenance-tagged list (B3).

    One dict per registered hook *entry*, in source order (``settings``,
    then ``settings.local``, then plugins), each with keys ``event``,
    ``matcher`` (``str | None``), ``command``, ``basename``
    (``command.rsplit("/", 1)[-1]``), ``source``, and ``path`` (the file
    the entry was read from, as a string).

    Pure read: no environment variable is expanded and no path is resolved
    — a plugin entry's ``${CLAUDE_PLUGIN_ROOT}`` command is recorded
    verbatim (see :func:`duplicate_hook_groups` for why). A missing,
    unparseable, or malformed-shape file contributes nothing and is not an
    error. Total — never raises.
    """
    view: "list[dict]" = []
    try:
        for source in hook_sources(project_dir, home=home):
            hooks_top = _load_hooks_dict(source["path"])
            # Same traversal shape (and isinstance guard at every level) as
            # the pre-INFRA-288 detectors: hooks -> event -> block list ->
            # block "hooks" -> entry "command".
            for event, block_list in hooks_top.items():
                if not isinstance(block_list, list):
                    continue
                for block in block_list:
                    if not isinstance(block, dict):
                        continue
                    matcher = block.get("matcher")
                    if not isinstance(matcher, str):
                        matcher = None
                    inner_hooks = block.get("hooks")
                    if not isinstance(inner_hooks, list):
                        continue
                    for entry in inner_hooks:
                        if not isinstance(entry, dict):
                            continue
                        command = entry.get("command")
                        if not isinstance(command, str):
                            continue
                        view.append(
                            {
                                "event": event,
                                "matcher": matcher,
                                "command": command,
                                "basename": command.rsplit("/", 1)[-1],
                                "source": source["source"],
                                "path": source["path"],
                            }
                        )
    except Exception:
        pass
    return view


def duplicate_hook_groups(view: "list[dict] | Any") -> "list[dict]":
    """Group a merged view's entries and report every duplicated
    ``(event, basename)`` pair (B6).

    Returns one dict per pair holding more than one entry, with keys
    ``event``, ``basename``, ``commands`` (full command strings in view
    order — the pre-INFRA-288 contract, unchanged) and ``sources`` (the
    parallel list of source labels, new).

    Grouping is deliberately by ``basename`` — NOT by a resolved command
    path. A plugin's hooks.json holds an unexpanded
    ``${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py`` while the settings
    entry holds an absolute path; resolving paths would make the two *stop*
    matching, which is the precise cross-source blindness this module
    exists to remove (B5). Total — malformed input yields ``[]``.
    """
    groups: "dict[tuple, dict]" = {}
    try:
        if not isinstance(view, list):
            return []
        for entry in view:
            if not isinstance(entry, dict):
                continue
            event = entry.get("event")
            basename = entry.get("basename")
            command = entry.get("command")
            source = entry.get("source")
            if not isinstance(event, str) or not isinstance(basename, str):
                continue
            if not isinstance(command, str):
                continue
            group = groups.setdefault(
                (event, basename),
                {
                    "event": event,
                    "basename": basename,
                    "commands": [],
                    "sources": [],
                },
            )
            group["commands"].append(command)
            group["sources"].append(source if isinstance(source, str) else None)
    except Exception:
        return []
    return [g for g in groups.values() if len(g["commands"]) > 1]
