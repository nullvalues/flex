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

# Reserved key (INFRA-402/CER-195): an optional entry in the same JSON file
# holding a list of sibling-directory basenames deliberately out of
# anonymization scope for the sibling-directory reconciliation `--verify`
# performs (see `excluded_repo_names`). Never treated as a repo entry itself.
EXCLUDED_REPOS_CONFIG_KEY = "_excluded"

# Reserved key (INFRA-403/CER-196): an optional free-text string or list of
# strings carrying operator-facing explanatory text (e.g. what `_excluded`
# means). Introduced so `.pairmode-fleet.local.json.example` can hold its
# guidance prose in a JSON-legal field instead of the `//` comment lines
# that made the shipped template invalid JSON. Never treated as a repo entry
# itself; harmless if an operator forgets to strip it from their copied file.
COMMENT_CONFIG_KEY = "_comment"

# All reserved keys inside `.pairmode-fleet.local.json` that are
# configuration, not a `{label: real_path}` repo entry (INFRA-402). Kept as a
# single frozenset so `repo_entries` filters every reserved key uniformly —
# `fleet_discovery.py` also calls `repo_entries`, and a list value (e.g. the
# `_excluded` array) reaching `real_names_to_labels` would raise.
RESERVED_CONFIG_KEYS = frozenset(
    {FLEET_ROOT_CONFIG_KEY, EXCLUDED_REPOS_CONFIG_KEY, COMMENT_CONFIG_KEY}
)

# Stable, non-identifying placeholder for a discovered repo path with no
# fleet-map entry (Ensures 4, INFRA-400). `{n}` is a 1-based per-snapshot
# counter, not derived from anything about the real path.
UNMAPPED_PLACEHOLDER_TEMPLATE = "<unmapped-repo-{n}>"


class FleetMapConfigError(RuntimeError):
    """Raised by ``load_local_fleet_map`` when
    ``.pairmode-fleet.local.json`` exists but its contents are not valid
    JSON (CER-196, INFRA-403).

    A genuinely absent config file is a different answer than a present-but-
    malformed one — a fresh clone with no local fleet map configured means
    "no fleet names are configured, nothing to scrub/reconcile", while a
    present file that fails to parse means the operator's configuration is
    broken and the leak-prevention gate cannot be trusted to have actually
    checked anything. Collapsing both into an empty-map return let
    ``scrub_fleet_names.verify()`` report a broken config as a clean pass
    (CER-196) — this exception exists so that can never happen again.
    """


def load_local_fleet_map(root: Path) -> dict[str, str]:
    """Read ``<root>/.pairmode-fleet.local.json``.

    A genuinely absent file, or one this process cannot read (permissions,
    the path being a directory, etc.), yields ``{}`` — the "no config"
    behaviour is unchanged. A file that exists and is readable but is not
    valid JSON raises ``FleetMapConfigError`` (CER-196, INFRA-403) instead
    of degrading to ``{}``: a malformed config must never be silently read
    as "no fleet names configured".
    """
    local_path = Path(root) / LOCAL_FLEET_CONFIG_FILENAME
    try:
        with local_path.open() as f:
            text = f.read()
    except (FileNotFoundError, OSError):
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise FleetMapConfigError(
            f"{local_path}: invalid JSON ({e})"
        ) from e


def repo_entries(fleet_map: dict[str, str]) -> dict[str, str]:
    """The ``{label: real_path}`` entries only, excluding every reserved key
    (``_fleet_root``, ``_excluded``, ...) — configuration, not a repo mapping.
    """
    return {k: v for k, v in fleet_map.items() if k not in RESERVED_CONFIG_KEYS}


def excluded_repo_names(fleet_map: dict[str, str]) -> set[str]:
    """Basenames of sibling directories deliberately out of anonymization
    scope for the sibling-directory reconciliation (INFRA-402/CER-195).

    Reads the reserved ``_excluded`` key. Never raises: a missing key or a
    non-list value both yield an empty set (the loader's never-raises
    contract). Each entry is normalised via ``Path(entry).name`` so a full
    path also works, not just a bare basename.
    """
    raw = fleet_map.get(EXCLUDED_REPOS_CONFIG_KEY)
    if not isinstance(raw, list):
        return set()
    return {Path(entry).name for entry in raw if isinstance(entry, str) and Path(entry).name}


def real_names_to_labels(fleet_map: dict[str, str]) -> dict[str, str]:
    """Derive ``{real_name: label}`` from ``{label: real_path}``.

    The real name to match is the leaf/basename of the real absolute path
    (e.g. ``/mnt/work/<name>`` -> ``<name>``). Every reserved key is excluded
    via ``repo_entries`` before this derivation runs.
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
    ``fleet_map`` and not deliberately excluded (Ensures 1/2, INFRA-400;
    exclusion subtraction added by INFRA-402/CER-195) — the map/disk
    reconciliation.

    Excludes ``project_root`` itself: when the fleet root is the parent
    directory of the project running the reconciliation (the default), the
    project's own checkout is one of the fleet root's immediate
    subdirectories but is never a "sibling" the map needs to cover. Also
    excludes any sibling whose basename is listed in the reserved
    ``_excluded`` key (see ``excluded_repo_names``) — those are deliberately
    out of anonymization scope and must never be reported as unmapped.
    """
    mapped_names = set(real_names_to_labels(fleet_map))
    excluded_names = excluded_repo_names(fleet_map)
    fleet_root = resolve_fleet_root(fleet_map, project_root)
    resolved_project_root = Path(project_root).resolve()
    return [
        d
        for d in sibling_repo_dirs(fleet_root)
        if d.name not in mapped_names
        and d.name not in excluded_names
        and d.resolve() != resolved_project_root
    ]
