"""fleet_discovery.py — READ-ONLY fleet discovery for flex checkouts.

Scans candidate project directories for two binding signals:

  Signal 1 (scripts binding): the project's CLAUDE.build.md contains a
  pairmode_scripts_dir that resolves under THIS flex checkout's
  skills/pairmode/scripts directory.

  Signal 2 (version binding): the project's .companion/state.json has a
  pairmode_version key.

Usage:
    uv run python fleet_discovery.py [OPTIONS]

Options:
    --candidate-dir PATH   Add a candidate directory to scan (repeatable)
    --candidates-file PATH Read candidate dirs from a file (one per line)
    --snapshot PATH        Write snapshot to this file (default: the invoking flex
                           checkout's docs/fleet-snapshot.md; refused when the
                           scripts checkout is not the invoking repo)
    --no-snapshot          Skip writing the snapshot file
    --json                 Output JSON instead of human-readable text
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

# Shared merged-hook-view helpers (INFRA-288). hook_view.py is the third,
# stdlib-only module both this fleet scanner and pairmode_sync.py import so
# that neither has to depend on the other. Bare import via the scripts dir,
# same style as pairmode_sync.py's sibling imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hook_view  # noqa: E402

# Shared fleet-map loader (INFRA-400): the same module scrub_fleet_names.py
# uses, so both callers agree on what "real name" and "label" mean.
import fleet_map as fleet_map_lib  # noqa: E402

# ---------------------------------------------------------------------------
# Path resolution — no hardcoded absolute paths; everything relative to __file__
# ---------------------------------------------------------------------------

# This file: skills/pairmode/scripts/fleet_discovery.py
_SCRIPTS_DIR = Path(__file__).resolve().parent          # skills/pairmode/scripts
_PAIRMODE_DIR = _SCRIPTS_DIR.parent                     # skills/pairmode
_SKILLS_DIR = _PAIRMODE_DIR.parent                      # skills
_FLEX_ROOT = _SKILLS_DIR.parent                         # flex root

# The canonical scripts path for THIS checkout
_THIS_SCRIPTS_DIR = _SCRIPTS_DIR

# Local fleet-map config (CER-172): this repo is public, so real sibling-repo
# names must never be committed as source string literals. Extra fleet
# candidates beyond registered_projects instead come from a local, gitignored
# JSON file at the flex root — see _load_local_fleet_map() below and
# .pairmode-fleet.local.json.example for the template a fresh operator copies
# and fills with their own real fleet paths.
_LOCAL_FLEET_CONFIG_FILENAME = ".pairmode-fleet.local.json"

# Pattern to find pairmode_scripts_dir in CLAUDE.build.md
_SCRIPTS_DIR_PATTERN = re.compile(
    r'pairmode_scripts_dir\s*[=:]\s*["\']?([^"\'#\n]+?)["\']?\s*$',
    re.MULTILINE,
)

# CER-059(a) Signal-1 absence reason codes. Named module constants so callers
# (CLI, JSON, snapshot) can branch on a stable string rather than a bare bool.
SIGNAL1_ABSENT_NO_BUILD_MD = "no-build-md"
SIGNAL1_ABSENT_NO_DECLARATION = "no-declaration"
SIGNAL1_ABSENT_INLINE_ONLY = "inline-only"
SIGNAL1_ABSENT_FOREIGN_CHECKOUT = "foreign-checkout"

# Checked longest-first in signal1_absence_reason so the more specific scripts
# path is reported when both this checkout's scripts dir and its flex root
# text appear in a project's CLAUDE.build.md.
_INLINE_BINDING_SENTINELS = tuple(
    sorted((str(_THIS_SCRIPTS_DIR), str(_FLEX_ROOT)), key=len, reverse=True)
)


# ---------------------------------------------------------------------------
# Discovery logic
# ---------------------------------------------------------------------------

def _read_registered_projects() -> list[Path]:
    """Read registered_projects from this checkout's .companion/state.json."""
    state_path = _FLEX_ROOT / ".companion" / "state.json"
    if not state_path.exists():
        return []
    try:
        with state_path.open() as f:
            state = json.load(f)
        projects = state.get("registered_projects", [])
        return [Path(p) for p in projects if p]
    except (json.JSONDecodeError, OSError):
        return []


def _load_local_fleet_map() -> dict[str, str]:
    """Read the local, gitignored fleet map (CER-172).

    Reads ``<flex-root>/.pairmode-fleet.local.json``, a mapping of stable
    anonymized label (e.g. ``"repo-a"``) to real absolute path (e.g.
    ``"repo-a": "/mnt/work/<real-name>"``). Never raises: on a missing file,
    an unreadable file, or invalid JSON, returns ``{}`` — same never-raise
    contract as ``_read_registered_projects()``. This file is per-operator
    and gitignored; only ``.pairmode-fleet.local.json.example`` (fake
    placeholder entries) is committed.

    Delegates to ``fleet_map.py`` (INFRA-400) — the same loader
    ``scrub_fleet_names.py`` uses — bound to this module's own ``_FLEX_ROOT``
    global (read at call time, not import time, so tests that monkeypatch
    ``_FLEX_ROOT`` still take effect).
    """
    return fleet_map_lib.load_local_fleet_map(_FLEX_ROOT)


def _default_candidates() -> list[Path]:
    """Build the default candidate list: registered_projects + local fleet map."""
    candidates: list[Path] = []

    # From registered_projects
    candidates.extend(_read_registered_projects())

    # From the local, gitignored fleet map (CER-172) — real absolute paths,
    # never committed source string literals. Excludes the reserved
    # `_fleet_root` config key (INFRA-400) — it's configuration, not a repo
    # candidate.
    for real_path in fleet_map_lib.repo_entries(_load_local_fleet_map()).values():
        candidates.append(Path(real_path))

    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for c in candidates:
        resolved = c.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(c)
    return unique


def _read_build_md(project_dir: Path) -> Optional[str]:
    """Read project_dir/CLAUDE.build.md, or None if missing/unreadable.

    Shared by ``_check_signal1`` and ``signal1_absence_reason`` so a single
    project scan reads the file at most once per caller. Read-only; never
    raises (an ``OSError`` degrades to ``None``, same as a missing file).
    """
    build_md = project_dir / "CLAUDE.build.md"
    if not build_md.exists():
        return None
    try:
        return build_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _check_signal1(project_dir: Path) -> tuple[bool, Optional[str]]:
    """Signal 1: CLAUDE.build.md contains a pairmode_scripts_dir under THIS checkout.

    Returns (matched, scripts_dir_value_or_none).

    Zero-hit diagnosis (CER-059a): pre-migration projects (0.2.x) embed their scripts
    path only in inline shell commands (e.g. ``uv run python /path/scripts/flex_build.py``),
    NOT as an explicit ``pairmode_scripts_dir = <path>`` key-value line.  The regex
    ``_SCRIPTS_DIR_PATTERN`` matches only the key-value form, which is written by
    ``pairmode_sync.py sync-all --apply`` when a project migrates to the 0.3.0 thin loop.
    Consequently, zero Signal-1 hits across the 0.2.x fleet is the **correct result** —
    no false-negative.  After each project is synced to 0.3.0, its new ``CLAUDE.build.md``
    will carry the ``pairmode_scripts_dir`` declaration and Signal-1 will fire.

    See ``signal1_absence_reason`` below for the full diagnosis of *why* Signal 1 is
    absent in a given project — this docstring only covers the zero-hit-fleet case.
    """
    text = _read_build_md(project_dir)
    if text is None:
        return False, None

    for match in _SCRIPTS_DIR_PATTERN.finditer(text):
        raw = match.group(1).strip()
        # Resolve relative to project_dir if not absolute
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = project_dir / candidate
        try:
            resolved = candidate.resolve()
        except OSError:
            continue

        # Check if the resolved path is the same as or under _THIS_SCRIPTS_DIR
        try:
            resolved.relative_to(_THIS_SCRIPTS_DIR)
            return True, raw
        except ValueError:
            pass

        # Also accept the flex root itself
        try:
            resolved.relative_to(_FLEX_ROOT)
            return True, raw
        except ValueError:
            pass

    return False, None


def signal1_absence_reason(project_dir: Path) -> tuple[Optional[str], Optional[str]]:
    """Classify *why* Signal 1 is absent for project_dir, for the pre-fold gate.

    Returns (reason_code, detail_or_none). Pure, read-only, never raises — any
    OSError or decode failure yields (SIGNAL1_ABSENT_NO_BUILD_MD, None), same as
    a genuinely missing CLAUDE.build.md.

    Each reason code carries a different consequence for the fold (DP8):

    - ``SIGNAL1_ABSENT_NO_BUILD_MD``: no CLAUDE.build.md at all — this is not a
      pairmode project. No blast radius; nothing to migrate.
    - ``SIGNAL1_ABSENT_NO_DECLARATION``: a CLAUDE.build.md exists but declares no
      ``pairmode_scripts_dir`` and does not embed this checkout's path inline.
      This is the expected 0.2.x shape (CER-059a) — the project will bind after
      a ``sync-all --apply`` migrates it to the 0.3.0 thin loop. Not a bug.
    - ``SIGNAL1_ABSENT_INLINE_ONLY``: no key-value declaration, but the file's
      text contains this checkout's scripts dir or flex root inline (e.g. a
      0.2.x build loop that shells out to this checkout's scripts directly).
      The project is bound to THIS checkout today and **breaks at the fold**
      even though it fired neither signal — invisible under the old absent/
      present boolean, which is exactly the gap CER-059(a) flags.
    - ``SIGNAL1_ABSENT_FOREIGN_CHECKOUT``: a ``pairmode_scripts_dir`` declaration
      exists but resolves under neither this checkout's scripts dir nor its
      flex root. The project is bound to a *different* flex checkout — a
      genuine mis-binding to investigate, not assume is ours.

    Checked in that order: foreign-checkout outranks inline-only, because an
    explicit ``pairmode_scripts_dir`` declaration is stronger evidence of
    intent than a path merely appearing inside a shell command line. When both
    inline sentinels (this checkout's scripts dir and its flex root) appear in
    the text, the longer (more specific) one is reported.
    """
    text = _read_build_md(project_dir)
    if text is None:
        return SIGNAL1_ABSENT_NO_BUILD_MD, None

    declared_values: list[str] = []
    foreign_value: Optional[str] = None
    for match in _SCRIPTS_DIR_PATTERN.finditer(text):
        raw = match.group(1).strip()
        declared_values.append(raw)
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = project_dir / candidate
        try:
            resolved = candidate.resolve()
        except OSError:
            continue

        matched_here = False
        for anchor in (_THIS_SCRIPTS_DIR, _FLEX_ROOT):
            try:
                resolved.relative_to(anchor)
                matched_here = True
                break
            except ValueError:
                pass

        if matched_here:
            # A resolved match here means Signal 1 matched — no absence to explain.
            return None, None
        if foreign_value is None:
            foreign_value = raw

    if declared_values:
        # At least one pairmode_scripts_dir declaration exists, but none resolved
        # under this checkout (loop above would have returned early otherwise).
        return SIGNAL1_ABSENT_FOREIGN_CHECKOUT, foreign_value

    # No key-value declaration. Check for an inline appearance of this
    # checkout's identity, longest sentinel first (more specific match wins).
    sentinels = tuple(
        sorted((str(_THIS_SCRIPTS_DIR), str(_FLEX_ROOT)), key=len, reverse=True)
    )
    for sentinel in sentinels:
        if sentinel and sentinel in text:
            return SIGNAL1_ABSENT_INLINE_ONLY, sentinel

    return SIGNAL1_ABSENT_NO_DECLARATION, None


def _check_signal2(project_dir: Path) -> tuple[bool, Optional[str]]:
    """Signal 2: .companion/state.json has pairmode_version.

    Returns (matched, version_value_or_none).
    """
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return False, None

    try:
        with state_path.open() as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False, None

    version = state.get("pairmode_version")
    if version is not None:
        return True, str(version)
    return False, None


def _check_duplicate_hooks(project_dir: Path) -> list[dict]:
    """DP8 fleet-level signal for CER-081: doubled hook registrations left by
    a project whose bootstrap.py registrars ran before INFRA-269's dedupe fix.

    Since INFRA-288 (CER-104) the input is the **merged hook view** —
    ``.claude/settings.json`` + ``.claude/settings.local.json`` + every
    discoverable plugin ``hooks/hooks.json`` (see ``hook_view.py``) — not
    settings.json alone. The settings-only read was structurally blind to
    the CER-104 shape: a project receiving ``post_tool_use.py`` from both
    its settings and an installed flex plugin doubled every effort row while
    this check reported 0 duplicates.

    Returns one dict per duplicated (event, command-basename) pair, with the
    unchanged keys "event", "basename", and "commands" (full command strings
    in view order) plus the parallel "sources" list of source labels, and —
    since CER-110 — the parallel "matchers"/"predicates"/"paths" lists and
    the "actionable" bool. An "actionable" group has at least one
    settings/settings.local member; an all-plugin group is refined by
    matcher/predicate/path first (two unrelated plugins sharing a basename,
    or one plugin registering distinct triggers under it, are not
    duplicates) and is always "actionable": False. Returns [] on
    missing/unparseable files or no duplicates. Read-only — never writes to
    project_dir (same discipline as _check_signal1/_check_signal2; the
    merged view is a pure read).
    """
    return hook_view.duplicate_hook_groups(hook_view.merged_hook_view(project_dir))


def _check_machine_absolute_hooks(project_dir: Path) -> list[dict]:
    """Fleet-level twin of pairmode_sync's audit finding (INFRA-319/CER-127):
    a committed .claude/settings.json holding a machine-bound absolute hook
    command (or the pre-rename ``/mnt/work/flex-harness/hooks/*`` shape) is a
    live per-machine breakage for the next clone.

    Reaches the classifier through ``hook_view`` — fleet_discovery.py and
    pairmode_sync.py must not depend on each other. Returns one dict per
    offending entry (``event``, ``basename``, ``command``, ``source``,
    ``path``, ``reason``). Read-only. Returns [] on missing/unparseable
    files or no findings.
    """
    return hook_view.machine_absolute_hook_entries(
        hook_view.merged_hook_view(project_dir), project_dir
    )


def discover(candidate_dirs: list[Path]) -> list[dict]:
    """Scan candidate_dirs and return discovery results.

    Returns a list of dicts for projects that matched at least one signal, plus
    the two CER-059(a) at-risk cases (B5) below. Each dict has:
        path: str
        signal1: bool
        signal1_value: str | None
        signal2: bool
        signal2_value: str | None
        binding: "scripts" | "version" | "both" | "inline" | "foreign"
        signal1_absent_reason: str | None
        signal1_absent_detail: str | None
        duplicate_hooks: list[dict]
        machine_absolute_hooks: list[dict]  # INFRA-319/CER-127

    CER-059(a): a project with neither signal fired is normally skipped — but
    when its Signal-1 absence reason is SIGNAL1_ABSENT_INLINE_ONLY or
    SIGNAL1_ABSENT_FOREIGN_CHECKOUT, it is included with binding "inline" or
    "foreign" respectively, because the pre-fold gate needs to see it to size
    blast radius accurately (a 0.2.x project inline-bound to this checkout
    breaks at the fold whether or not it also carries a pairmode_version).
    """
    results = []
    for d in candidate_dirs:
        if not d.exists() or not d.is_dir():
            continue

        s1, s1_val = _check_signal1(d)
        s2, s2_val = _check_signal2(d)

        reason: Optional[str] = None
        detail: Optional[str] = None
        if not s1:
            reason, detail = signal1_absence_reason(d)

        if not s1 and not s2:
            if reason == SIGNAL1_ABSENT_INLINE_ONLY:
                binding = "inline"
            elif reason == SIGNAL1_ABSENT_FOREIGN_CHECKOUT:
                binding = "foreign"
            else:
                continue
        elif s1 and s2:
            binding = "both"
        elif s1:
            binding = "scripts"
        else:
            binding = "version"

        results.append({
            "path": str(d.resolve()),
            "signal1": s1,
            "signal1_value": s1_val,
            "signal2": s2,
            "signal2_value": s2_val,
            "binding": binding,
            "signal1_absent_reason": reason,
            "signal1_absent_detail": detail,
            "duplicate_hooks": _check_duplicate_hooks(d),
            "machine_absolute_hooks": _check_machine_absolute_hooks(d),
        })

    return results


# ---------------------------------------------------------------------------
# Snapshot destination policy (INFRA-295)
# ---------------------------------------------------------------------------

def _invoking_repo_is_scripts_checkout(
    invoking_dir: Path = None, flex_root: Path = None
) -> bool:
    """Is the scripts checkout also the repo this invocation came from?

    Protects the rule that the scripts checkout (``_FLEX_ROOT``) is a
    permanent read-only release channel once a project has folded onto a
    consumed 0.3.0 checkout (e.g. ``/mnt/work/flex-harness``): a script
    invoked from a *different* repo must never default-write into the
    checkout it was loaded from. Returns True iff the resolved
    ``invoking_dir`` is ``flex_root`` itself or is nested under it. Pure —
    performs no I/O beyond path resolution.
    """
    if invoking_dir is None:
        invoking_dir = Path.cwd()
    if flex_root is None:
        flex_root = _FLEX_ROOT
    resolved_invoking = invoking_dir.resolve()
    resolved_root = flex_root.resolve()
    return resolved_invoking == resolved_root or resolved_invoking.is_relative_to(resolved_root)


def _default_snapshot_destination(
    invoking_dir: Path = None, flex_root: Path = None
) -> Optional[Path]:
    """Resolve the default (no ``--snapshot``) snapshot destination.

    Returns ``flex_root / "docs" / "fleet-snapshot.md"`` when the invoking
    repo is the scripts checkout (see
    ``_invoking_repo_is_scripts_checkout``), and ``None`` when it is not —
    signalling that the caller must refuse to write a default destination
    rather than silently write into either the scripts checkout or an
    arbitrary consumer repo. Performs no writes itself.
    """
    if invoking_dir is None:
        invoking_dir = Path.cwd()
    if flex_root is None:
        flex_root = _FLEX_ROOT
    if _invoking_repo_is_scripts_checkout(invoking_dir, flex_root):
        return flex_root / "docs" / "fleet-snapshot.md"
    return None


# ---------------------------------------------------------------------------
# Write-time anonymization (Ensures 3/4, INFRA-400)
# ---------------------------------------------------------------------------
#
# CER-188 finding: this module used to write real absolute repo paths
# straight into the tracked docs/fleet-snapshot.md on every default run — a
# live re-leak channel that a later scrub_fleet_names.py pass only cleaned
# up after the fact (a forbidden proxy per this story's Ensures 3). The fix
# maps every repo path through the fleet map *before* any snapshot line is
# composed, so a raw real path is never even briefly present in the string
# this function builds, let alone the file it writes.

def _anonymize_results_for_snapshot(
    results: list[dict], fleet_map: dict[str, str]
) -> list[dict]:
    """Return a copy of ``results`` with every ``"path"`` mapped through
    ``fleet_map`` to its label, or a stable non-identifying placeholder
    (``<unmapped-repo-N>``) when the path has no map entry (Ensures 4). Each
    unmapped gap is reported once on stderr. The same real path always maps
    to the same placeholder within one call, so the composed document stays
    internally consistent.
    """
    placeholders: dict[str, str] = {}

    def _resolve(real_path: str) -> str:
        label = fleet_map_lib.label_for_path(fleet_map, real_path)
        if label is not None:
            return label
        if real_path not in placeholders:
            placeholder = fleet_map_lib.UNMAPPED_PLACEHOLDER_TEMPLATE.format(
                n=len(placeholders) + 1
            )
            placeholders[real_path] = placeholder
            print(
                "fleet_discovery: no fleet-map label for a discovered repo "
                f"path — writing {placeholder} to the snapshot instead of "
                "the real path",
                file=sys.stderr,
            )
        return placeholders[real_path]

    return [{**r, "path": _resolve(r["path"])} for r in results]


# ---------------------------------------------------------------------------
# Snapshot writer
# ---------------------------------------------------------------------------

def _write_snapshot(results: list[dict], snapshot_path: Path) -> None:
    """Write a dated snapshot of the discovered fleet to snapshot_path.

    The caller owns destination policy (see
    ``_default_snapshot_destination`` and ``_invoking_repo_is_scripts_checkout``
    for the default-target refusal rule); this function writes wherever it
    is told, with no refusal branch of its own — one rule, one guard site.

    Every repo path is mapped through the local fleet map to its label (or a
    placeholder, Ensures 4) before any snapshot line is composed (INFRA-400)
    — write-time anonymization, not a post-hoc scrub.
    """
    fleet_map = _load_local_fleet_map()
    results = _anonymize_results_for_snapshot(results, fleet_map)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Fleet Snapshot",
        "",
        f"**Generated:** {now_utc}",
        f"**Flex checkout:** `{_FLEX_ROOT}`",
        "",
        "## Pre-fold gate notice (DP8)",
        "",
        "The **authoritative pre-fold run of this tool is a hard gate immediately before",
        "the fold** (DP8). Under Option Y, the fold makes `/mnt/work/flex` the 0.3.0",
        "checkout; any un-migrated bound project breaks at the fold. The fleet may change",
        "across the era, so the pre-fold run is what licenses the fold.",
        "",
        "`registered_projects` stays drift-opt-in (distinct purpose; optionally seeded",
        "from the discovered fleet, never forced).",
        "",
        "## Discovered fleet",
        "",
    ]

    if not results:
        lines.append("_No bound projects discovered._")
    else:
        lines.append(f"Found **{len(results)}** bound project(s):\n")
        for r in results:
            lines.append(f"### `{r['path']}`")
            lines.append("")
            lines.append(f"- **Binding:** {r['binding']}")
            if r["signal1"]:
                lines.append(f"- **Signal 1 (scripts path):** present — `{r['signal1_value']}`")
            else:
                suffix = ""
                reason = r.get("signal1_absent_reason")
                detail = r.get("signal1_absent_detail")
                if reason:
                    suffix = f" — {reason}"
                    if detail:
                        suffix += f" — `{detail}`"
                lines.append(f"- **Signal 1 (scripts path):** absent{suffix}")
            if r["signal2"]:
                lines.append(f"- **Signal 2 (pairmode_version):** present — `{r['signal2_value']}`")
            else:
                lines.append("- **Signal 2 (pairmode_version):** absent")
            lines.append("")

    lines.append("## Duplicate hook registrations (CER-081)")
    lines.append("")

    lines.append("### Actionable")
    lines.append("")
    actionable_results = [
        r
        for r in results
        if any(dh.get("actionable") for dh in r.get("duplicate_hooks") or [])
    ]
    if not actionable_results:
        lines.append("_No actionable duplicate hook registrations found._")
    else:
        for r in actionable_results:
            events = ", ".join(
                dh["event"] for dh in r["duplicate_hooks"] if dh.get("actionable")
            )
            lines.append(f"- `{r['path']}` — duplicated events: {events}")
    lines.append("")

    lines.append("### Plugin-internal (non-actionable, CER-110)")
    lines.append("")
    plugin_internal_results = [
        r
        for r in results
        if any(
            not dh.get("actionable") for dh in r.get("duplicate_hooks") or []
        )
    ]
    if not plugin_internal_results:
        lines.append("_No plugin-internal duplicate hook registrations found._")
    else:
        for r in plugin_internal_results:
            events = ", ".join(
                dh["event"]
                for dh in r["duplicate_hooks"]
                if not dh.get("actionable")
            )
            lines.append(f"- `{r['path']}` — duplicated events: {events}")
    lines.append("")

    lines.append("## Machine-absolute hook paths (CER-127 / INFRA-319)")
    lines.append("")
    machine_absolute_results = [
        r for r in results if r.get("machine_absolute_hooks")
    ]
    if not machine_absolute_results:
        lines.append("_No machine-absolute hook paths found._")
    else:
        for r in machine_absolute_results:
            reasons = ", ".join(
                f"{f['event']}/{f['basename']} ({f['reason']})"
                for f in r["machine_absolute_hooks"]
            )
            lines.append(f"- `{r['path']}` — {reasons} — remedy: `to-030 --apply`")
    lines.append("")

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--candidate-dir",
    "extra_dirs",
    multiple=True,
    type=click.Path(exists=False),
    help="Add a candidate directory to scan (repeatable).",
)
@click.option(
    "--candidates-file",
    "candidates_file",
    type=click.Path(exists=True),
    default=None,
    help="Read candidate dirs from a file (one per line).",
)
@click.option(
    "--snapshot",
    "snapshot_path",
    type=click.Path(),
    default=None,
    help=(
        "Write snapshot to this file. Default: the invoking flex checkout's "
        "docs/fleet-snapshot.md; refused when the scripts checkout is not "
        "the invoking repo."
    ),
)
@click.option(
    "--no-snapshot",
    "no_snapshot",
    is_flag=True,
    default=False,
    help="Skip writing the snapshot file.",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    default=False,
    help="Output JSON instead of human-readable text.",
)
def cli(
    extra_dirs: tuple,
    candidates_file: Optional[str],
    snapshot_path: Optional[str],
    no_snapshot: bool,
    output_json: bool,
) -> None:
    """Scan candidate project directories for flex binding signals (read-only)."""

    # Build candidate list
    candidates = _default_candidates()

    # Add --candidate-dir entries
    for d in extra_dirs:
        candidates.append(Path(d))

    # Add from --candidates-file
    if candidates_file:
        with open(candidates_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    candidates.append(Path(line))

    # Deduplicate again after additions
    seen: set[Path] = set()
    unique_candidates: list[Path] = []
    for c in candidates:
        resolved = c.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(c)

    results = discover(unique_candidates)

    if output_json:
        click.echo(json.dumps({"flex_root": str(_FLEX_ROOT), "fleet": results}, indent=2))
    else:
        click.echo(f"Flex checkout: {_FLEX_ROOT}")
        click.echo(f"Candidates scanned: {len(unique_candidates)}")
        click.echo(f"Bound projects found: {len(results)}")
        if results:
            click.echo("")
            for r in results:
                click.echo(f"  {r['path']}")
                click.echo(f"    binding: {r['binding']}")
                if r["signal1"]:
                    click.echo(f"    signal1 (scripts path): {r['signal1_value']}")
                else:
                    reason = r.get("signal1_absent_reason")
                    detail = r.get("signal1_absent_detail")
                    if reason:
                        line = f"    signal1 (scripts path): absent — {reason}"
                        if detail:
                            line += f" ({detail})"
                        click.echo(line)
                if r["signal2"]:
                    click.echo(f"    signal2 (pairmode_version): {r['signal2_value']}")
                actionable_hooks = [
                    dh for dh in r["duplicate_hooks"] if dh.get("actionable")
                ]
                non_actionable_hooks = [
                    dh for dh in r["duplicate_hooks"] if not dh.get("actionable")
                ]
                if actionable_hooks:
                    events = ", ".join(dh["event"] for dh in actionable_hooks)
                    click.echo(f"    DUPLICATE HOOKS: {r['path']} — events: {events}")
                if non_actionable_hooks:
                    events = ", ".join(dh["event"] for dh in non_actionable_hooks)
                    click.echo(
                        f"    plugin-internal duplicate hooks: {r['path']} "
                        f"— events: {events}"
                    )
                machine_absolute = r.get("machine_absolute_hooks") or []
                if machine_absolute:
                    reasons = ", ".join(
                        f"{f['event']}/{f['basename']} ({f['reason']})"
                        for f in machine_absolute
                    )
                    click.echo(
                        f"    MACHINE-ABSOLUTE HOOKS: {r['path']} — {reasons} "
                        "— remedy: to-030 --apply"
                    )

        projects_with_actionable_duplicates = sum(
            1
            for r in results
            if any(dh.get("actionable") for dh in r["duplicate_hooks"])
        )
        projects_with_plugin_internal_duplicates = sum(
            1
            for r in results
            if any(not dh.get("actionable") for dh in r["duplicate_hooks"])
        )
        click.echo(
            "Projects with actionable duplicate hooks: "
            f"{projects_with_actionable_duplicates}"
        )
        click.echo(
            "Projects with plugin-internal duplicate hooks (non-actionable): "
            f"{projects_with_plugin_internal_duplicates}"
        )
        projects_with_machine_absolute_hooks = sum(
            1 for r in results if r.get("machine_absolute_hooks")
        )
        click.echo(
            "Projects with machine-absolute hook paths (CER-127): "
            f"{projects_with_machine_absolute_hooks}"
        )

    if not no_snapshot:
        if snapshot_path:
            dest = Path(snapshot_path)
        else:
            dest = _default_snapshot_destination()
        if dest is None:
            declined = _FLEX_ROOT / "docs" / "fleet-snapshot.md"
            click.echo(
                "Refusing to write default snapshot destination "
                f"({declined}): this invocation is outside the flex checkout "
                "the scripts dir belongs to, and the scripts checkout is a "
                "read-only release channel. Pass --snapshot PATH to write "
                "elsewhere, or --no-snapshot to skip the snapshot.",
                err=True,
            )
        else:
            _write_snapshot(results, dest)
            if not output_json:
                click.echo(f"\nSnapshot written to: {dest}")


if __name__ == "__main__":
    cli()
