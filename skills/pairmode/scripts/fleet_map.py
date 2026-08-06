"""fleet_map.py — shared local fleet-map loading/parsing helpers (INFRA-400).

Factored out of ``scrub_fleet_names.py`` so ``fleet_discovery.py``'s
write-time anonymization loads and interprets the exact same
``.pairmode-fleet.local.json`` mapping as ``scrub_fleet_names.py``, through
one shared implementation, rather than each module re-implementing its own
parser. A divergence between two independent parsers is worse here than in
most modules: it would mean the two callers disagree about what "real name"
or "label" means, silently reopening the exact leak this project's history
(CER-172, CER-188) keeps rediscovering.

No real repo name is ever a source-code literal in this file. Every real
name this module ever sees comes from the local, gitignored
``.pairmode-fleet.local.json`` file at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path

# The local, gitignored fleet map filename (CER-172, INFRA-393).
LOCAL_FLEET_CONFIG_FILENAME = ".pairmode-fleet.local.json"

# Reserved key (INFRA-400): an optional entry in the same JSON file naming
# the fleet root directory reconciliation reads from, distinct from the
# `{label: real_path}` repo entries. Never treated as a repo entry itself.
FLEET_ROOT_CONFIG_KEY = "_fleet_root"

# Stable, non-identifying placeholder for a discovered repo path with no
# fleet-map entry (Ensures 4, INFRA-400). `{n}` is a 1-based per-snapshot
# counter, not derived from anything about the real path.
UNMAPPED_PLACEHOLDER_TEMPLATE = "<unmapped-repo-{n}>"


def load_local_fleet_map(root: Path) -> dict[str, str]:
    """Read ``<root>/.pairmode-fleet.local.json``. Never raises: a missing
    file, an unreadable file, or invalid JSON all yield ``{}``.
    """
    local_path = Path(root) / LOCAL_FLEET_CONFIG_FILENAME
    try:
        with local_path.open() as f:
            return json.load(f)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def repo_entries(fleet_map: dict[str, str]) -> dict[str, str]:
    """The ``{label: real_path}`` entries only, excluding the reserved
    ``_fleet_root`` key (which is configuration, not a repo mapping).
    """
    return {k: v for k, v in fleet_map.items() if k != FLEET_ROOT_CONFIG_KEY}


def real_names_to_labels(fleet_map: dict[str, str]) -> dict[str, str]:
    """Derive ``{real_name: label}`` from ``{label: real_path}``.

    The real name to match is the leaf/basename of the real absolute path
    (e.g. ``/mnt/work/<name>`` -> ``<name>``). The reserved ``_fleet_root``
    key is excluded via ``repo_entries`` before this derivation runs.
    """
    names: dict[str, str] = {}
    for label, real_path in repo_entries(fleet_map).items():
        name = Path(real_path).name
        if not name:
            continue
        names[name] = label
    return names


def label_for_path(fleet_map: dict[str, str], path: str | Path) -> str | None:
    """The mapped label for ``path``'s basename, or ``None`` if unmapped."""
    return real_names_to_labels(fleet_map).get(Path(path).name)


def resolve_fleet_root(fleet_map: dict[str, str], project_root: Path) -> Path:
    """The fleet root reconciliation reads sibling repos from.

    Reads the optional ``_fleet_root`` key from ``fleet_map`` (relative
    values resolve against ``project_root``); defaults to
    ``project_root``'s parent directory when the key is absent, matching
    the pre-INFRA-400 assumption that fleet siblings live next to this
    project on disk.
    """
    raw = fleet_map.get(FLEET_ROOT_CONFIG_KEY)
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = Path(project_root) / p
        return p
    return Path(project_root).parent


def sibling_repo_dirs(fleet_root: Path) -> list[Path]:
    """Immediate subdirectories of ``fleet_root`` that look like git repos
    (contain a ``.git`` entry). Returns ``[]`` when ``fleet_root`` doesn't
    exist or isn't a directory — never raises.

    An unreadable candidate (e.g. a directory chmod'd to deny access, or one
    that disappears mid-scan) is skipped rather than aborting the whole scan
    (INFRA-401): both the top-level ``iterdir()`` and the per-candidate
    ``is_dir()``/``.git`` probe are guarded, since either can raise
    ``PermissionError`` (a subclass of ``OSError``) on a candidate this
    process cannot stat or list.
    """
    fleet_root = Path(fleet_root)
    if not fleet_root.exists() or not fleet_root.is_dir():
        return []
    try:
        candidates = list(fleet_root.iterdir())
    except OSError:
        return []
    repos: list[Path] = []
    for p in candidates:
        try:
            if p.is_dir() and (p / ".git").exists():
                repos.append(p)
        except OSError:
            continue
    return sorted(repos, key=lambda p: p.name)


def unmapped_sibling_repos(fleet_map: dict[str, str], project_root: Path) -> list[Path]:
    """On-disk sibling repos under the fleet root with no entry in
    ``fleet_map`` (Ensures 1/2, INFRA-400) — the map/disk reconciliation.

    Excludes ``project_root`` itself: when the fleet root is the parent
    directory of the project running the reconciliation (the default), the
    project's own checkout is one of the fleet root's immediate
    subdirectories but is never a "sibling" the map needs to cover.
    """
    mapped_names = set(real_names_to_labels(fleet_map))
    fleet_root = resolve_fleet_root(fleet_map, project_root)
    resolved_project_root = Path(project_root).resolve()
    return [
        d
        for d in sibling_repo_dirs(fleet_root)
        if d.name not in mapped_names and d.resolve() != resolved_project_root
    ]
