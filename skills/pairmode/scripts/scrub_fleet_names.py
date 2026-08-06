"""scrub_fleet_names.py — scrub real fleet-repo names from committed docs (CER-172).

Lessons-scoped mode (CER-173): the general ``apply()``/``verify()`` loop
above deliberately excludes ``lessons/lessons.json``/``lessons/LESSONS.md``
(both a declared ``protected_path``), because rewriting an existing lesson
entry's field content would otherwise violate the append-only integrity
rule those files are held to. ``apply_lessons()``/``verify_lessons()`` are a
narrow, explicitly-scoped exception to that exclusion: a real-name-only text
substitution within a fixed set of existing entries' free-text fields
(``source_project``, ``trigger``, ``problem``, ``learning``,
``methodology_change.description``, ``value_framing``), never touching
``id``, ``date``, ``status``, ``enforced_by``, ``applies_to``,
``methodology_change.affects``, ``validation_phase``, or entry count/order.
This path is never invoked by the general ``apply()``/``verify()`` loop —
it is only reachable via ``--lessons``/``--verify --lessons`` or by calling
``apply_lessons()``/``verify_lessons()`` directly.

This project is public; ~150 already-committed files (phase docs, story
specs, docs/architecture.md, the CER backlog, etc.) mention real sibling-repo
names in prose. This script mechanically replaces every occurrence of a real
repo name with its stable anonymized label (``Repo-A``, ``Repo-B``, ...),
sourced entirely at runtime from the local, gitignored
``.pairmode-fleet.local.json`` mapping (INFRA-393). No real repo name is a
source-code literal anywhere in this file.

Usage:
    uv run python skills/pairmode/scripts/scrub_fleet_names.py           # apply
    uv run python skills/pairmode/scripts/scrub_fleet_names.py --verify  # verify only
    uv run python skills/pairmode/scripts/scrub_fleet_names.py install-hook [REPO_ROOT]
        # writes a git pre-commit hook (INFRA-400) that blocks a commit on a
        # failing --verify; REPO_ROOT defaults to this checkout's own root.

Exclusions (INFRA-394 review finding — a prior attempt corrupted these):
a real name is skipped when it appears as part of an email address
(``user@<name>...``) or as the host of a URL under ``<name>.<tld>`` used as
someone's own public domain — both reduce to "the match is immediately
followed by a domain suffix like ``.com``", which is not how a fleet repo
name is ever used in prose. This check is generic (keyed off the matched
text, not any hardcoded real name), so it applies uniformly to every mapped
name, not just the one that happened to collide in review.

This script also never rewrites a file under this project's own
``protected_paths`` (read at runtime from ``CLAUDE.build.md``'s Build
standards line, same convention the builder procedure itself uses) — the
builder is not authorized to modify those files, whether by hand or via a
mechanical script it runs. ``lessons/LESSONS.md`` is additionally excluded
as the auto-generated rendering of the protected ``lessons/lessons.json``
(regenerating it from a since-reverted json would just undo an isolated
edit anyway).
"""

from __future__ import annotations

import json
import re
import stat
import subprocess
import sys
from pathlib import Path

# Path resolution — no hardcoded absolute paths; everything relative to __file__.
_SCRIPTS_DIR = Path(__file__).resolve().parent          # skills/pairmode/scripts
_PAIRMODE_DIR = _SCRIPTS_DIR.parent                      # skills/pairmode
_SKILLS_DIR = _PAIRMODE_DIR.parent                        # skills
_FLEX_ROOT = _SKILLS_DIR.parent                            # flex root

# fleet_map.py is a sibling module in this same scripts/ directory (INFRA-400)
# holding the loader/parser both this script and fleet_discovery.py share.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import fleet_map as _fleet_map_lib  # noqa: E402

_LOCAL_FLEET_CONFIG_FILENAME = _fleet_map_lib.LOCAL_FLEET_CONFIG_FILENAME

_NO_LOCAL_CONFIG_MESSAGE = (
    "no local fleet config found, skipping verification"
)

# A real name immediately followed by one of these suffixes is almost
# certainly a domain (email address or URL host) rather than a fleet-repo
# mention in prose — e.g. "david@<name>.com" or "https://x.<name>.com/...".
# Fleet repo names in prose are never immediately followed by a TLD suffix.
_DOMAIN_SUFFIX_RE = re.compile(
    r"\.(com|org|net|io|dev|app|co|help|ai|xyz)\b", re.IGNORECASE
)

# Path segments identifying vendored/third-party content (e.g. npm/pnpm
# dependency trees checked into the repo). These are not "committed docs"
# that ever mention a real fleet-repo name in prose; a match inside them is
# necessarily an accidental short-token collision (e.g. a file extension or
# code identifier that happens to equal a short repo basename) rather than
# a genuine repo mention, and must never be rewritten — doing so corrupts
# third-party source that this project doesn't own.
_VENDORED_PATH_SEGMENTS = ("node_modules",)


def _is_vendored(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return any(seg in _VENDORED_PATH_SEGMENTS for seg in parts)


_BUILD_MD_FILENAME = "CLAUDE.build.md"
_PROTECTED_PATHS_RE = re.compile(r"protected_paths\s*=\s*`([^`]*)`")

# lessons/LESSONS.md is auto-generated from the protected lessons/lessons.json
# (see lesson.py / lesson_review.py / pairmode_migrate.py's regenerate step);
# scrubbing it directly would drift from its source of truth and is excluded
# alongside the protected_paths entries themselves.
_GENERATED_FROM_PROTECTED = ("lessons/LESSONS.md",)


def _read_protected_paths(root: Path) -> tuple[str, ...]:
    """Read this project's protected_paths list from CLAUDE.build.md's Build
    standards line, mirroring the convention the builder procedure itself
    uses for covered_contracts. Returns () when CLAUDE.build.md or the
    protected_paths key is absent (never raises).
    """
    build_md = root / _BUILD_MD_FILENAME
    try:
        text = build_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ()
    match = _PROTECTED_PATHS_RE.search(text)
    if not match:
        return ()
    raw = match.group(1).strip()
    if not raw or raw == "(none)":
        return ()
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def _is_protected(rel_path: str, protected_paths: tuple[str, ...]) -> bool:
    if rel_path in _GENERATED_FROM_PROTECTED:
        return True
    for entry in protected_paths:
        if entry.endswith("/"):
            if rel_path == entry.rstrip("/") or rel_path.startswith(entry):
                return True
        elif rel_path == entry:
            return True
    return False


def _load_local_fleet_map(root: Path = _FLEX_ROOT) -> dict[str, str]:
    """Read the local, gitignored fleet map (CER-172).

    Delegates to ``fleet_map.py`` (INFRA-400) — the same loader
    ``fleet_discovery.py`` uses — so both callers agree on file shape.

    Never raises on a genuinely absent config file (returns ``{}``, "no
    config"). Raises ``fleet_map.FleetMapConfigError`` when the file exists
    but is not valid JSON (CER-196, INFRA-403) — every caller in this module
    (``apply``, ``verify``, ``apply_lessons``, ``verify_lessons``) lets that
    propagate rather than catching it and reinstating an empty-map
    fallback; only ``main()`` catches it, to turn it into a non-zero exit
    with a message identifying the unparseable file.
    """
    return _fleet_map_lib.load_local_fleet_map(root)


def _real_names_to_labels(fleet_map: dict[str, str]) -> dict[str, str]:
    """Derive {real_name: label} from {label: real_path}.

    The real name to match is the leaf/basename of the real absolute path
    (e.g. "/mnt/work/<name>" -> "<name>"). Sourced only from the runtime
    mapping — never re-derived or hardcoded. Excludes the reserved
    ``_fleet_root`` config key (INFRA-400) via ``fleet_map.py``.
    """
    return _fleet_map_lib.real_names_to_labels(fleet_map)


def _reconcile_fleet_root(fleet_map: dict[str, str], root: Path) -> list[Path]:
    """On-disk sibling repos under the fleet root absent from ``fleet_map``
    (Ensures 1/2, INFRA-400) — the map/disk reconciliation ``--verify``
    performs. A thin, testable wrapper around ``fleet_map.py`` kept here so
    it's colocated with the rest of ``verify()``'s logic.
    """
    return _fleet_map_lib.unmapped_sibling_repos(fleet_map, root)


def _validate_one_to_one(names_to_labels: dict[str, str]) -> None:
    """Verify no two distinct real names collapse to the same label, and no
    single real name maps to two different labels, before any file is written.
    Runs on the base {real_name: label} map (one entry per fleet repo), not
    the case-variant-expanded map — expanding case variants of the *same*
    real name to the *same* label is expected and is not a collision.
    """
    labels_seen: dict[str, str] = {}
    for name, label in names_to_labels.items():
        if label in labels_seen and labels_seen[label] != name:
            # Never interpolate the colliding real names into this message
            # (INFRA-400 leak-free reporting) — the label alone is enough to
            # locate the offending entry in the local, gitignored map.
            raise ValueError(
                f"fleet map is not one-to-one: label {label!r} is claimed by "
                "more than one distinct real-name entry in the local fleet map"
            )
        labels_seen[label] = name


def _expand_case_variants(names_to_labels: dict[str, str]) -> dict[str, str]:
    """Expand each real name to its as-written, Capitalized, and UPPERCASE
    forms, all mapped to the same label as the original.

    Prose naturally capitalizes a proper noun at the start of a sentence
    (e.g. "<Name>'s CLAUDE.build.md...") or in an all-caps acronym-style
    mention (e.g. "<NAME>"); a real name's mapping entry in
    ``.pairmode-fleet.local.json`` is always lowercase (it is a directory
    basename), so without this expansion those case variants would survive
    the scrub as leftover real-name literals. This is a purely mechanical
    transform of the runtime-loaded name — it never inspects or re-derives
    from the docs being scrubbed.
    """
    expanded: dict[str, str] = {}
    for name, label in names_to_labels.items():
        for variant in (name, name.capitalize(), name.upper()):
            expanded[variant] = label
    return expanded


def _build_pattern(names_to_labels: dict[str, str]) -> re.Pattern | None:
    """Build a single alternation regex, longest name first, so a longer
    real name (e.g. one that is a strict prefix of another mapped name) is
    never partially matched by a shorter alternative.
    """
    if not names_to_labels:
        return None
    ordered_names = sorted(names_to_labels, key=len, reverse=True)
    escaped = [re.escape(n) for n in ordered_names]
    # Word-boundary on both sides so a real name embedded inside an unrelated
    # longer token is not matched (e.g. a name that happens to be a substring
    # of some other word).
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern)


def _is_domain_context(text: str, match: re.Match) -> bool:
    """True if the match is immediately followed by a domain-suffix pattern
    (".com", ".org", ...), indicating an email address or URL host rather
    than a fleet-repo mention in prose. See module docstring.
    """
    tail = text[match.end():match.end() + 8]
    return bool(_DOMAIN_SUFFIX_RE.match(tail))


def _tracked_files(root: Path) -> list[str]:
    """Enumerate git-tracked files repo-wide via `git ls-files` (not a
    docs/-only glob — a real name in a non-docs tracked file must not be
    missed).
    """
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _substitute(text: str, pattern: re.Pattern, names_to_labels: dict[str, str]) -> tuple[str, int]:
    """Apply pattern substitution to text, skipping domain-context matches.

    Returns (new_text, count_replaced).
    """
    count = 0

    def _repl(match: re.Match) -> str:
        nonlocal count
        if _is_domain_context(text, match):
            return match.group(0)
        count += 1
        return names_to_labels[match.group(0)]

    new_text = pattern.sub(_repl, text)
    return new_text, count


def apply(root: Path = _FLEX_ROOT) -> int:
    """Apply the scrub across all git-tracked files. Returns number of files changed."""
    fleet_map = _load_local_fleet_map(root)
    if not fleet_map:
        print(f"{_NO_LOCAL_CONFIG_MESSAGE} (apply: nothing to do)")
        return 0

    names_to_labels = _real_names_to_labels(fleet_map)
    _validate_one_to_one(names_to_labels)
    expanded = _expand_case_variants(names_to_labels)
    pattern = _build_pattern(expanded)
    if pattern is None:
        print(f"{_NO_LOCAL_CONFIG_MESSAGE} (apply: nothing to do)")
        return 0

    changed_files = 0
    this_script = Path(__file__).resolve()
    protected_paths = _read_protected_paths(root)

    for rel_path in _tracked_files(root):
        if rel_path == _LOCAL_FLEET_CONFIG_FILENAME:
            # The local config itself is the source of truth for real names
            # and is gitignored; it must never be rewritten (and should
            # never be tracked in the first place).
            continue
        if _is_vendored(rel_path):
            continue
        if _is_protected(rel_path, protected_paths):
            # The builder is not authorized to modify protected_paths (or
            # lessons/LESSONS.md, generated from the protected lessons.json)
            # by hand or via a mechanical script it runs.
            continue
        abs_path = root / rel_path
        if abs_path.resolve() == this_script:
            # Never rewrite this file's own source (it must never contain a
            # real name literal in the first place).
            continue
        try:
            original = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # binary or unreadable file — skip

        new_text, count = _substitute(original, pattern, expanded)
        if count > 0 and new_text != original:
            abs_path.write_text(new_text, encoding="utf-8")
            changed_files += 1
            print(f"scrubbed {rel_path} ({count} replacement(s))")

    print(f"apply complete: {changed_files} file(s) changed")
    return changed_files


def verify(root: Path = _FLEX_ROOT) -> int:
    """Re-scan the tracked tree for any remaining real-name hit, and
    reconcile the local fleet map against the real on-disk sibling-repo set
    (Ensures 1, INFRA-400).

    Returns 0 (and prints the skip message) when no local config is present,
    per the same graceful-degrade contract INFRA-393 established — the
    reconciliation step is skipped in that case too (a clean clone has no
    fleet root to reconcile against), but is never skipped silently once a
    local map file exists. Returns 0 when clean, non-zero otherwise: either
    an unmapped on-disk sibling repo (reconciliation) or a remaining
    real-name hit in a tracked file fails the run. Hit and reconciliation
    reporting never embeds the matched real-name literal (leak-free
    reporting, Ensures 5) — only the mapped label, `file:line`, or (for
    reconciliation only, which is inherently about a name absent from the
    map and therefore has no label yet) the unmapped directory path itself.
    """
    fleet_map = _load_local_fleet_map(root)
    if not fleet_map:
        print(_NO_LOCAL_CONFIG_MESSAGE)
        return 0

    reconciliation_failed = False

    # Mapped/excluded conflict check (Ensures 4, INFRA-402/CER-195): a name
    # that is both mapped and excluded is a configuration contradiction, not
    # a precedence question, and must fail loudly rather than resolve to one
    # side. Report the mapped label only — never the real name (leak-free
    # reporting, same contract as the rest of this function).
    names_to_labels_for_conflict = _real_names_to_labels(fleet_map)
    excluded_names = _fleet_map_lib.excluded_repo_names(fleet_map)
    conflicting = sorted(
        set(names_to_labels_for_conflict) & excluded_names
    )
    if conflicting:
        reconciliation_failed = True
        for real_name in conflicting:
            label = names_to_labels_for_conflict[real_name]
            print(
                f"verify FAILED: label {label!r} is both mapped and listed "
                "in the exclusion list — a name cannot be both",
                file=sys.stderr,
            )

    unmapped = _reconcile_fleet_root(fleet_map, root)
    if unmapped:
        reconciliation_failed = True
        print(
            f"verify FAILED: reconciliation found {len(unmapped)} unmapped "
            "on-disk sibling repo(s) under the fleet root (present on disk, "
            "absent from .pairmode-fleet.local.json):",
            file=sys.stderr,
        )
        for d in unmapped:
            print(f"  {d}", file=sys.stderr)

    names_to_labels = _real_names_to_labels(fleet_map)
    expanded = _expand_case_variants(names_to_labels)
    pattern = _build_pattern(expanded)
    if pattern is None:
        if reconciliation_failed:
            return 1
        print(_NO_LOCAL_CONFIG_MESSAGE)
        return 0

    this_script = Path(__file__).resolve()
    hits: list[str] = []
    protected_paths = _read_protected_paths(root)

    for rel_path in _tracked_files(root):
        if rel_path == _LOCAL_FLEET_CONFIG_FILENAME:
            continue
        if _is_vendored(rel_path):
            continue
        if _is_protected(rel_path, protected_paths):
            continue
        abs_path = root / rel_path
        if abs_path.resolve() == this_script:
            continue
        try:
            lines = abs_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for lineno, line in enumerate(lines, start=1):
            for match in pattern.finditer(line):
                if _is_domain_context(line, match):
                    continue
                label = expanded[match.group(0)]
                hits.append(f"{label} — {rel_path}:{lineno}")

    if hits:
        print(f"verify FAILED: {len(hits)} remaining real-name hit(s):")
        for hit in hits:
            print(f"  {hit}")
        return 1

    if reconciliation_failed:
        return 1

    print(
        "verify OK: zero remaining real-name hits "
        f"(mapped={len(names_to_labels)}, excluded={len(excluded_names)}, "
        f"unmapped={len(unmapped)})"
    )
    return 0


# ---------------------------------------------------------------------------
# Lessons-scoped mode (CER-173)
# ---------------------------------------------------------------------------

_LESSONS_JSON_REL = "lessons/lessons.json"
_LESSONS_MD_REL = "lessons/LESSONS.md"

# The only fields eligible for a real-name substitution, per lesson entry.
# `methodology_change.description` and `value_framing` are nested/optional
# and handled separately from this flat list.
_LESSON_TEXT_FIELDS = ("source_project", "trigger", "problem", "learning")


def _substitute_lesson_entry(
    entry: dict, pattern: re.Pattern, names_to_labels: dict[str, str]
) -> int:
    """Substitute real-name matches in one lesson entry's free-text fields,
    in place. Returns the number of replacements made across this entry.
    """
    total = 0

    for field in _LESSON_TEXT_FIELDS:
        if field in entry and isinstance(entry[field], str):
            new_text, count = _substitute(entry[field], pattern, names_to_labels)
            if count:
                entry[field] = new_text
                total += count

    methodology_change = entry.get("methodology_change")
    if isinstance(methodology_change, dict) and isinstance(
        methodology_change.get("description"), str
    ):
        new_text, count = _substitute(
            methodology_change["description"], pattern, names_to_labels
        )
        if count:
            methodology_change["description"] = new_text
            total += count

    if isinstance(entry.get("value_framing"), str):
        new_text, count = _substitute(entry["value_framing"], pattern, names_to_labels)
        if count:
            entry["value_framing"] = new_text
            total += count

    return total


def apply_lessons(root: Path = _FLEX_ROOT) -> int:
    """Apply the scrub to lessons/lessons.json's existing entries' free-text
    fields only (CER-173), then regenerate lessons/LESSONS.md from the
    result. Never invoked by the general apply() loop. Returns the total
    number of replacements made across all entries.

    Raises ValueError if entry count or ordered id list would change — this
    path must never add, remove, or reorder entries.
    """
    fleet_map = _load_local_fleet_map(root)
    if not fleet_map:
        print(f"{_NO_LOCAL_CONFIG_MESSAGE} (apply --lessons: nothing to do)")
        return 0

    names_to_labels = _real_names_to_labels(fleet_map)
    _validate_one_to_one(names_to_labels)
    expanded = _expand_case_variants(names_to_labels)
    pattern = _build_pattern(expanded)
    if pattern is None:
        print(f"{_NO_LOCAL_CONFIG_MESSAGE} (apply --lessons: nothing to do)")
        return 0

    lessons_path = root / _LESSONS_JSON_REL
    lessons_md_path = root / _LESSONS_MD_REL

    with lessons_path.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("lessons", [])
    original_ids = [entry.get("id") for entry in entries]
    original_count = len(entries)

    total_replacements = 0
    for entry in entries:
        total_replacements += _substitute_lesson_entry(entry, pattern, expanded)

    new_ids = [entry.get("id") for entry in entries]
    if len(entries) != original_count or new_ids != original_ids:
        raise ValueError(
            "lessons-scoped apply would change entry count or id order — "
            f"before: {original_count} entries {original_ids}, "
            f"after: {len(entries)} entries {new_ids}"
        )

    if total_replacements == 0:
        print("apply --lessons complete: 0 replacement(s), no write performed")
        return 0

    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    import lesson_utils  # sibling module in this same scripts/ directory

    with lessons_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    lessons_md_path.write_text(
        lesson_utils.generate_lessons_md(data), encoding="utf-8"
    )

    print(
        f"apply --lessons complete: {total_replacements} replacement(s) "
        f"across {original_count} entries"
    )
    return total_replacements


def verify_lessons(root: Path = _FLEX_ROOT) -> int:
    """Re-read lessons/lessons.json and lessons/LESSONS.md and report any
    remaining real-name hit in either file, using the same domain-context-
    aware matching as verify(). Never scans the rest of the tracked tree.
    """
    fleet_map = _load_local_fleet_map(root)
    if not fleet_map:
        print(_NO_LOCAL_CONFIG_MESSAGE)
        return 0

    names_to_labels = _real_names_to_labels(fleet_map)
    expanded = _expand_case_variants(names_to_labels)
    pattern = _build_pattern(expanded)
    if pattern is None:
        print(_NO_LOCAL_CONFIG_MESSAGE)
        return 0

    hits: list[str] = []

    lessons_path = root / _LESSONS_JSON_REL
    if lessons_path.exists():
        with lessons_path.open(encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("lessons", []):
            entry_id = entry.get("id", "?")
            texts: list[tuple[str, str]] = []
            for field in _LESSON_TEXT_FIELDS:
                if isinstance(entry.get(field), str):
                    texts.append((field, entry[field]))
            methodology_change = entry.get("methodology_change")
            if isinstance(methodology_change, dict) and isinstance(
                methodology_change.get("description"), str
            ):
                texts.append(
                    ("methodology_change.description", methodology_change["description"])
                )
            if isinstance(entry.get("value_framing"), str):
                texts.append(("value_framing", entry["value_framing"]))

            for field_name, text in texts:
                for match in pattern.finditer(text):
                    if _is_domain_context(text, match):
                        continue
                    label = expanded[match.group(0)]
                    hits.append(
                        f"{label} — {_LESSONS_JSON_REL}: entry {entry_id} "
                        f"field {field_name!r}"
                    )

    lessons_md_path = root / _LESSONS_MD_REL
    if lessons_md_path.exists():
        lines = lessons_md_path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            for match in pattern.finditer(line):
                if _is_domain_context(line, match):
                    continue
                label = expanded[match.group(0)]
                hits.append(f"{label} — {_LESSONS_MD_REL}:{lineno}")

    if hits:
        print(f"verify --lessons FAILED: {len(hits)} remaining real-name hit(s):")
        for hit in hits:
            print(f"  {hit}")
        return 1

    print("verify --lessons OK: zero remaining real-name hits")
    return 0


# ---------------------------------------------------------------------------
# Mechanical gate: git pre-commit hook (Ensures 6, Instructions 5, INFRA-400)
# ---------------------------------------------------------------------------
#
# Rationale for choosing a *git* pre-commit hook over a flex Claude-Code hook:
# this project's own hooks (hooks/*.py) are constrained to thin relays with
# no blocking logic (docs/ideology.md § Accepted constraints, "Hooks are thin
# relays only") — they emit to the companion pipe and exit, never run
# blocking checks. A git pre-commit hook is a different layer entirely (git's
# own commit lifecycle, not the Claude-Code hook/pipe/sidebar pipeline that
# constraint protects), so routing the "must block a commit on a failing
# --verify" requirement through git satisfies it without touching, bending,
# or carving an exception into the thin-relay rule. The hook body itself
# stays a few lines of versioned logic in this tracked script (via
# `install-hook`); only the generated `.git/hooks/pre-commit` artifact is
# local and untracked (git never tracks `.git/hooks/*`).

_PRE_COMMIT_HOOK_TEMPLATE = """#!/bin/sh
# Installed by `scrub_fleet_names.py install-hook` (INFRA-400).
# Blocks a commit whenever `scrub_fleet_names.py --verify` fails, so a real
# fleet-repo name (or an unmapped on-disk sibling repo) can never land in a
# tracked file, or drift silently uncovered, without the commit failing.
exec uv run python "{script_path}" --verify --root "{repo_root}"
"""


#: The five statuses `install_hook` can report (INFRA-401). Each is a
#: distinct, visible outcome — no branch below is a silent no-op.
HOOK_STATUS_INSTALLED = "installed"
HOOK_STATUS_ALREADY_INSTALLED = "already-installed"
HOOK_STATUS_NOT_A_GIT_REPO = "not-a-git-repo"
HOOK_STATUS_WORKTREE = "worktree"
HOOK_STATUS_FOREIGN_HOOK = "foreign-hook"


def install_hook(repo_root: Path) -> tuple[str, Path | None]:
    """Write an executable `.git/hooks/pre-commit` into `repo_root` that
    invokes this script's `--verify` (bound to `repo_root` explicitly, via
    `--root`, so the hook works correctly even when `repo_root` is not this
    script's own checkout) and aborts the commit on nonzero exit.

    Returns `(status, path_or_none)` rather than assuming success
    (INFRA-401) — five distinct, visible outcomes:

    - `HOOK_STATUS_NOT_A_GIT_REPO`: `repo_root/.git` does not exist. Nothing
      is created; `path` is `None`.
    - `HOOK_STATUS_WORKTREE`: `repo_root/.git` exists but is a file (a
      worktree or submodule pointer, not a directory) — the real hooks
      directory belongs to the main checkout the pointer references, so
      nothing is written here; `path` is `None`.
    - `HOOK_STATUS_ALREADY_INSTALLED`: `repo_root/.git/hooks/pre-commit`
      already exists and is byte-identical to the template this call would
      render — no write performed (idempotent re-run).
    - `HOOK_STATUS_FOREIGN_HOOK`: `repo_root/.git/hooks/pre-commit` already
      exists with different content — a pre-existing hook this call did not
      install. Left untouched; never overwritten.
    - `HOOK_STATUS_INSTALLED`: the hook did not exist (or did not match) and
      was written.

    Invoked automatically by `bootstrap.py` as part of its normal run
    (INFRA-401) — bootstrap is this project's only "apply pairmode's
    machinery to a checkout" touchpoint and runs once per checkout, which is
    the lifecycle this function's contract assumes. Also invokable directly
    via the `install-hook` CLI subcommand to re-apply the gate to a checkout
    outside a bootstrap run.
    """
    repo_root = Path(repo_root)
    git_path = repo_root / ".git"
    if not git_path.exists():
        return HOOK_STATUS_NOT_A_GIT_REPO, None
    if git_path.is_file():
        return HOOK_STATUS_WORKTREE, None

    hooks_dir = git_path / "hooks"
    hook_path = hooks_dir / "pre-commit"
    script_path = Path(__file__).resolve()
    rendered = _PRE_COMMIT_HOOK_TEMPLATE.format(
        script_path=script_path, repo_root=repo_root
    )

    if hook_path.exists():
        try:
            existing = hook_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            existing = None
        if existing == rendered:
            return HOOK_STATUS_ALREADY_INSTALLED, hook_path
        return HOOK_STATUS_FOREIGN_HOOK, hook_path

    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(rendered, encoding="utf-8")
    mode = hook_path.stat().st_mode
    hook_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return HOOK_STATUS_INSTALLED, hook_path


def _parse_root(args: list[str]) -> Path:
    """Read an optional `--root PATH` from args, defaulting to `_FLEX_ROOT`
    — used by the installed pre-commit hook (which always passes `--root`
    explicitly) and available to any other caller that needs to point
    `--verify`/apply at a repo other than this script's own checkout.
    """
    if "--root" in args:
        idx = args.index("--root")
        if idx + 1 < len(args):
            return Path(args[idx + 1])
    return _FLEX_ROOT


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    if args and args[0] == "install-hook":
        rest = args[1:]
        repo_root = Path(rest[0]) if rest else _FLEX_ROOT
        status, hook_path = install_hook(repo_root)
        _INSTALL_HOOK_CLI_MESSAGES = {
            HOOK_STATUS_INSTALLED: f"pre-commit hook installed at {hook_path}",
            HOOK_STATUS_ALREADY_INSTALLED: (
                f"pre-commit hook already installed at {hook_path}"
            ),
            HOOK_STATUS_NOT_A_GIT_REPO: (
                f"{repo_root} is not a git repository — pre-commit hook not installed"
            ),
            HOOK_STATUS_WORKTREE: (
                f"{repo_root}'s .git is a worktree pointer — pre-commit hook belongs "
                "to the main checkout, not installed here"
            ),
            HOOK_STATUS_FOREIGN_HOOK: (
                f"a pre-existing pre-commit hook is present at {hook_path} — left "
                "untouched, not overwritten"
            ),
        }
        print(_INSTALL_HOOK_CLI_MESSAGES[status])
        # An explicit `install-hook` request that could not be fulfilled is a
        # failure (Instructions 3, INFRA-401): only the two "the gate is
        # actually in place" outcomes exit 0.
        return 0 if status in (HOOK_STATUS_INSTALLED, HOOK_STATUS_ALREADY_INSTALLED) else 1

    root = _parse_root(args)
    try:
        if "--lessons" in args:
            if "--verify" in args:
                return verify_lessons(root)
            apply_lessons(root)
            return 0
        if "--verify" in args:
            return verify(root)
        apply(root)
        return 0
    except _fleet_map_lib.FleetMapConfigError as e:
        # CER-196/INFRA-403: a malformed local fleet-config file must fail
        # the gate loudly, not be swallowed into an empty-map "nothing
        # configured" pass. Every caller above (apply/verify/apply_lessons/
        # verify_lessons) let this propagate rather than catching it
        # locally — this is the one place it's converted into a process
        # exit code.
        print(f"scrub_fleet_names: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
