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
    (``command.rsplit("/", 1)[-1]``), ``source``, ``path`` (the file
    the entry was read from, as a string), and ``predicate`` (``str | None``
    — the entry-level ``"if"`` value, e.g. ``Bash(git commit:*)``; see
    :func:`duplicate_hook_groups` and CER-110).

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
                        predicate = entry.get("if")
                        if not isinstance(predicate, str):
                            predicate = None
                        view.append(
                            {
                                "event": event,
                                "matcher": matcher,
                                "command": command,
                                "basename": command.rsplit("/", 1)[-1],
                                "source": source["source"],
                                "path": source["path"],
                                "predicate": predicate,
                            }
                        )
    except Exception:
        pass
    return view


#: Basenames of flex's own hook scripts (INFRA-319/CER-127). Used to scope
#: the machine-absolute-path finding to flex's hooks — flex does not police
#: an unrelated project hook (e.g. a local pytest-runner PostToolUse entry).
_FLEX_HOOK_BASENAMES = frozenset(
    {
        "pre_tool_use.py",
        "post_tool_use.py",
        "user_prompt_submit.py",
        "session_start.py",
        "session_end.py",
        "subagent_stop.py",
        "stop.py",
    }
)


def machine_absolute_hook_entries(
    view: "list[dict] | Any", project_dir: "Path | str"
) -> "list[dict]":
    """Return one dict per offending entry in *view* (CER-127, C1-C2).

    An entry is offending when it is a flex hook command (basename in
    ``_FLEX_HOOK_BASENAMES``) registered from the **committed**
    ``.claude/settings.json`` (``source == "settings"``) and either:

    - contains ``flex-harness`` — the pre-rename
      ``/mnt/work/flex-harness/hooks/*`` shape (``reason ==
      "stale-flex-harness"``), flagged even if it would otherwise pass; or
    - contains an absolute path token that does not resolve under
      *project_dir* (``reason == "machine-absolute"``).

    A ``settings.local`` entry is never flagged (a machine-bound value is
    correct there) and neither is a ``plugin`` entry using
    ``${CLAUDE_PLUGIN_ROOT}`` (the portable shape), a relative or
    ``$CLAUDE_PROJECT_DIR``-rooted command, or a non-flex basename.

    Each returned dict has keys ``event``, ``basename``, ``command``,
    ``source``, ``path``, and ``reason``. *project_dir* is a required
    parameter, never inferred from ``os.getcwd()``. Total — malformed input
    (including an unresolvable *project_dir*) returns ``[]``, never raises.
    """
    findings: "list[dict]" = []
    try:
        if not isinstance(view, list):
            return []
        project_path = Path(project_dir).resolve()
    except Exception:
        return []

    try:
        for entry in view:
            if not isinstance(entry, dict):
                continue
            if entry.get("source") != HOOK_SOURCE_SETTINGS:
                continue
            basename = entry.get("basename")
            command = entry.get("command")
            if not isinstance(basename, str) or basename not in _FLEX_HOOK_BASENAMES:
                continue
            if not isinstance(command, str):
                continue

            reason = None
            if "flex-harness" in command:
                reason = "stale-flex-harness"
            else:
                for token in command.split():
                    if not token.startswith("/"):
                        continue
                    try:
                        Path(token).resolve().relative_to(project_path)
                    except (OSError, ValueError):
                        reason = "machine-absolute"
                    break

            if reason is None:
                continue

            findings.append(
                {
                    "event": entry.get("event"),
                    "basename": basename,
                    "command": command,
                    "source": entry.get("source"),
                    "path": entry.get("path"),
                    "reason": reason,
                }
            )
    except Exception:
        return []
    return findings


def duplicate_hook_groups(view: "list[dict] | Any") -> "list[dict]":
    """Group a merged view's entries and report every duplicated
    ``(event, basename)`` pair (B6, refined CER-110).

    Bucketing is still by ``(event, basename)`` exactly as before — NOT by a
    resolved command path. A plugin's hooks.json holds an unexpanded
    ``${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py`` while the settings
    entry holds an absolute path; resolving paths would make the two *stop*
    matching, which is the precise cross-source blindness this module
    exists to remove (B5).

    Once bucketed, a bucket containing at least one ``settings`` or
    ``settings.local`` member (``actionable``) is emitted **unrefined** when
    it has >= 2 members — matcher and path are never applied across sources,
    because matcher strings legitimately differ *and overlap* across sources
    (``Task|Agent`` settings-side vs ``Task|Agent|SendMessage`` plugin-side
    for ``post_tool_use.py``) and a settings absolute path can never equal a
    plugin's ``${CLAUDE_PLUGIN_ROOT}`` command path. Applying either
    discriminator across sources would silently restore the cross-source
    blindness this module exists to remove.

    An all-plugin bucket (no settings-level member) is refined instead,
    because two *different* plugins can legitimately ship the same
    basename (R1), and one plugin can legitimately register the same
    basename several times under distinct triggers (R2):

    - **R1 (multi-plugin split):** partition the bucket by member ``path``,
      so two plugins shipping the same basename land in different
      partitions.
    - **R2 (distinct-trigger drop):** within each partition, drop a member
      whose ``(matcher, predicate)`` pair is unique among that partition;
      only members sharing an identical ``(matcher, predicate)`` with at
      least one other member survive. A partition is emitted only if two or
      more members survive.

    (Ideology note: narrowing a detector is the risky direction, so the
    narrowing here is scoped so that no settings-touching group can ever be
    dropped — a settings-level member always forces the unrefined,
    unconditionally-actionable path. The dropped plugin-side partitions are
    not suppressed either: callers still see and print them as
    ``PLUGIN-INTERNAL:`` — reported, just not gating.)

    Returns one dict per surviving group, with keys ``event``, ``basename``,
    ``commands`` (full command strings in view order — the pre-INFRA-288
    contract, unchanged), ``sources`` (parallel list of source labels),
    ``matchers`` (parallel list, new), ``predicates`` (parallel list, new),
    ``paths`` (parallel list, new), and ``actionable`` (bool, new — ``True``
    iff at least one member's ``source`` is ``settings`` or
    ``settings.local``). Total — malformed input yields ``[]``.
    """
    buckets: "dict[tuple, dict]" = {}
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
            matcher = entry.get("matcher")
            if not isinstance(matcher, str):
                matcher = None
            predicate = entry.get("predicate")
            if not isinstance(predicate, str):
                predicate = None
            path = entry.get("path")
            if not isinstance(path, str):
                path = None
            bucket = buckets.setdefault(
                (event, basename),
                {
                    "event": event,
                    "basename": basename,
                    "commands": [],
                    "sources": [],
                    "matchers": [],
                    "predicates": [],
                    "paths": [],
                },
            )
            bucket["commands"].append(command)
            bucket["sources"].append(source if isinstance(source, str) else None)
            bucket["matchers"].append(matcher)
            bucket["predicates"].append(predicate)
            bucket["paths"].append(path)
    except Exception:
        return []

    groups: "list[dict]" = []
    try:
        for bucket in buckets.values():
            actionable = any(
                s in (HOOK_SOURCE_SETTINGS, HOOK_SOURCE_SETTINGS_LOCAL)
                for s in bucket["sources"]
            )
            n = len(bucket["commands"])
            if actionable:
                if n > 1:
                    group = dict(bucket)
                    group["actionable"] = True
                    groups.append(group)
                continue

            # All-plugin bucket: refine per R1 (split by path) then R2
            # (drop members whose (matcher, predicate) is unique within
            # their partition).
            indices_by_path: "dict[Any, list[int]]" = {}
            for i, path in enumerate(bucket["paths"]):
                indices_by_path.setdefault(path, []).append(i)

            for indices in indices_by_path.values():
                key_counts: "dict[tuple, int]" = {}
                for i in indices:
                    key = (bucket["matchers"][i], bucket["predicates"][i])
                    key_counts[key] = key_counts.get(key, 0) + 1
                surviving = [
                    i
                    for i in indices
                    if key_counts[(bucket["matchers"][i], bucket["predicates"][i])]
                    > 1
                ]
                if len(surviving) > 1:
                    groups.append(
                        {
                            "event": bucket["event"],
                            "basename": bucket["basename"],
                            "commands": [bucket["commands"][i] for i in surviving],
                            "sources": [bucket["sources"][i] for i in surviving],
                            "matchers": [bucket["matchers"][i] for i in surviving],
                            "predicates": [
                                bucket["predicates"][i] for i in surviving
                            ],
                            "paths": [bucket["paths"][i] for i in surviving],
                            "actionable": False,
                        }
                    )
    except Exception:
        return []
    return groups
