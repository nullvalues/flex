"""
next_story.py — Find the next unbuilt story from a phase file.

Reads the ## Stories table from the given phase file (using
`_parse_stories_table` from `story_resolver`) and iterates stories in table
order. For each story, determines completion from the project directory's git
log using a two-step rule (`_has_story_commit`):

  1. **Scope-restricted (CER-116).** When a commit subject's
     conventional-commit scope — the text inside the first `(...)` of a
     leading `type(scope):` prefix — names at least one uppercase story-ID
     token, only those tokens count as build evidence from that commit. This
     stops a commit that merely *mentions* a sibling story ("RELEASE-067+
     held for operator ruling") from marking it built and having the resolver
     silently skip past it.
  2. **Whole-subject fallback.** Otherwise the story ID is matched as a whole
     token (word-boundary, case-insensitive) anywhere in the commit subject —
     not only when prefixed with the literal `story-`. This recognizes the
     `story-<ID>` conventional-commit convention, parenthetical merge
     suffixes (`... (RELEASE-014)`), and bare mentions (`RELEASE-014 status
     update`) alike, while word boundaries keep a longer ID sharing a numeric
     prefix (e.g. `INFRA-1001`) from matching a lookup for `INFRA-100`.

Commits whose message starts with `spec(` are excluded from matching before
either step (RELEASE-041) — spec-authoring commits legitimately reference
multiple story IDs in prose without building any of them. A commit match is
authoritative over the table's status column.

Returns the first story that:
  - has no matching git commit, AND
  - whose table status is not `deferred` or `skipped`, AND
  - (when a `claimed` set is supplied) is not in that set — a story whose
    build is already in flight in another worktree (CER-095.1). Skipped
    claimed IDs are reported in the returned dict's `claimed_skipped` key.

When a story's table status is `complete` but no matching git commit exists,
the story is still returned as the next unbuilt one with `git_verified=true`
to signal that git overrode the table's status.

CLI:
    uv run next_story.py <phase-file> [--json] [--project-dir DIR]

Exit codes:
  0 — found
  1 — all stories complete
  2 — error (e.g. missing phase file)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Ensure sibling imports work whether invoked as CLI or imported as module.
sys.path.insert(0, str(Path(__file__).parent))

import click

from story_resolver import _parse_stories_table, resolve_story  # noqa: E402
from table_utils import split_table_row  # noqa: E402


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# Statuses that mark a story as definitively not next-up.
# `complete` is intentionally NOT here — git overrides table `complete` when
# no matching commit exists.
_SKIP_STATUSES = {"deferred", "skipped"}


def _parse_stories_table_statuses(text: str) -> dict[str, str]:
    """Parse the ## Stories table and return {story_id: status} mapping.

    Mirrors the row-iteration logic in `story_resolver._parse_stories_table`
    but additionally captures the third column (status). Story IDs are
    stripped of Markdown link syntax. Returns lowercase statuses.
    """
    stories_section_re = re.compile(r'^##\s+Stories\s*$', re.MULTILINE)
    m = stories_section_re.search(text)
    if not m:
        return {}

    section_text = text[m.end():]
    statuses: dict[str, str] = {}
    in_table = False
    header_seen = False
    separator_seen = False

    for line in section_text.splitlines():
        stripped = line.strip()

        if stripped.startswith('##'):
            break

        if not stripped.startswith('|'):
            if in_table and stripped:
                break
            continue

        in_table = True
        # split rationale: `table_utils.split_table_row`
        parts = [p.strip() for p in split_table_row(stripped)]
        if len(parts) < 2:
            continue

        if not header_seen:
            header_seen = True
            continue

        if not separator_seen:
            separator_seen = True
            continue

        first_col = parts[1].strip()
        if not first_col:
            continue

        story_id = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', first_col)

        # Status is the third pipe-delimited column (parts[3] after the
        # leading empty string at parts[0]). May be missing in malformed
        # tables.
        status = ""
        if len(parts) > 3:
            status = parts[3].strip().lower()

        statuses[story_id] = status

    return statuses


def _git_log_oneline(project_dir: Path) -> str:
    """Return `git log --oneline` output for the project, or '' on error."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline"],
            capture_output=True,
            cwd=str(project_dir),
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


# Conventional-commit prefix: `type(scope):` at the start of a subject.
# Group 1 is the scope text between the first parentheses.
_SCOPE_RE = re.compile(r'^[A-Za-z]+\(([^)]*)\)\s*:')

# A story-ID token, deliberately uppercase-only — see `_has_story_commit`'s
# docstring. Greedily consumes chained `-SEGMENT` prefixes (each starting
# with an uppercase letter) ahead of the final `-NNN` so that a legacy
# compound scope like `B034-API-005` (old phase-rail-number ID scheme,
# pre-D1-re-key) is captured as ONE token, not left to leak its tail segment
# as a false match for the bare current-scheme ID `API-005` (INFRA-297 follow-up:
# see docstring below). Segments are letter-led by construction — a `-NNN`
# suffix never starts a continuation — so this cannot merge two independent
# bare IDs written back-to-back (`API-005-UI-006` still splits into
# `API-005` + `UI-006`, since `005` isn't letter-led).
_SCOPE_STORY_ID_RE = re.compile(r'\b[A-Z][A-Z0-9_]*(?:-[A-Z][A-Z0-9_]*)*-\d{2,}\b')

# A bare uppercase phase-tag segment (`B034`, `B055`, ...) immediately
# preceding a hyphen at the point a fallback match begins. Used only to
# reject a fallback match embedded inside a legacy compound scope like
# `B034-API-005` (see `_has_story_commit`'s fallback branch) — it must stay
# uppercase-only so it never rejects a legitimate lowercase prefix like the
# `story-` in `story-INFRA-100`.
_LEGACY_COMPOUND_PREFIX_RE = re.compile(r'[A-Z][A-Z0-9_]*-$')


def _has_story_commit(story_id: str, git_log: str) -> bool:
    """Return True if `git_log` carries build evidence for `story_id`.

    **Scope rule (CER-116).** If a commit subject has a conventional-commit
    prefix (`type(scope):`) whose scope contains at least one uppercase
    story-ID token (`\\b[A-Z][A-Z0-9_]*-\\d{2,}\\b`), then *only* those scope
    tokens count as build evidence from that commit: `story_id` matches only
    if it equals one of them (compared case-insensitively). Otherwise the
    whole-subject search below runs as the fallback.

    This exists because a whole-subject search cannot tell "this commit built
    X" from "this commit mentions X". Commit `e83ce900`
    (`story(RELEASE-066): ...; RELEASE-067+ held for operator ruling`) marked
    RELEASE-067 as built while it was still draft and unbuilt, and
    `find_next_story` silently skipped past it — the worst failure shape a
    build loop can have. The rule replaces the interim operator discipline
    "never name sibling story IDs in non-`spec(` commit subjects", which was
    unenforceable and had already been violated.

    **Fallback — whole-subject search.** With no story ID in the scope, the
    story ID is matched anywhere in the commit *message* (word-boundary
    match, case-insensitive). The three legitimate shapes this preserves:
    the `story-` conventional-commit convention
    (`feat(story-INFRA-100): done`), a parenthetical merge suffix
    (`merge(fold-prep): ... (RELEASE-014)`), and a bare mention
    (`chore(orchestrator): RELEASE-014 status update`). The `\\b` boundaries
    prevent a longer ID that shares a numeric prefix (e.g. `INFRA-1001`)
    from satisfying a lookup for `INFRA-100`. The search runs on the message
    (the subject after the abbreviated SHA), never on the raw
    `git log --oneline` line, so a story ID can never be matched out of the
    SHA field.

    **Why the scope detector is uppercase-only, deliberately.** Lowercase
    scopes such as `phase-112`, `era-004`, `fold-prep` and `story-infra-100`
    do not activate the restriction and fall through to the fallback. Rails
    are uppercase by construction (`story_new.py`'s
    `_RAIL_RE = re.compile(r"[A-Z][A-Z0-9_]*")`), so a lowercase token is not
    reliably a story ID. This is the conservative direction: a missed
    restriction re-offers a story that was already built (loud, recoverable),
    whereas a wrong restriction skips a story silently — the failure CER-116
    is about.

    **`spec(` skip (RELEASE-041), unchanged and evaluated first.** Commits
    whose message starts with `spec(` are skipped entirely before the scope
    rule is considered: this repo's spec-authoring convention prefixes commits
    that create or edit specs, and such a commit legitimately lists several
    story IDs in prose (e.g. "add RELEASE-020/021/022 specs") without building
    any of them — counting that as build evidence produced a false positive.
    """
    if not git_log:
        return False
    pattern = re.compile(r'\b' + re.escape(story_id) + r'\b', re.IGNORECASE)
    wanted = story_id.upper()
    for line in git_log.splitlines():
        message = line.split(" ", 1)[1] if " " in line else ""
        if message.lstrip().startswith("spec("):
            continue

        scope_match = _SCOPE_RE.match(message.lstrip())
        if scope_match:
            scope_ids = _SCOPE_STORY_ID_RE.findall(scope_match.group(1))
            if scope_ids:
                # Scope names its own story/stories — that is this commit's
                # build evidence, and nothing else in the subject counts.
                if wanted in {sid.upper() for sid in scope_ids}:
                    return True
                continue

        # Whole-subject fallback: word-boundary, case-insensitive search —
        # but reject a match embedded inside a legacy compound scope like
        # `B034-API-005` (old phase-rail-number ID scheme, pre-D1-re-key).
        # `\b` alone can't tell that apart from a standalone mention: hyphen
        # is a non-word character on both sides, so the boundary is
        # satisfied identically whether `API-005` is standalone or is the
        # tail of `B034-API-005`. Only reject
        # when the immediately preceding segment is a BARE uppercase run
        # (a phase-tag shape) — a lowercase prefix like the `story-` in
        # `story-INFRA-100` must still match, so the guard is deliberately
        # uppercase-only, mirroring the scope detector's own restriction.
        for candidate in pattern.finditer(message):
            if _LEGACY_COMPOUND_PREFIX_RE.search(message[: candidate.start()]):
                continue
            return True
    return False


def find_next_story(
    phase_file: Path,
    project_dir: Path,
    *,
    claimed: set[str] | None = None,
) -> dict | None:
    """Return the next unbuilt story or None if all are complete.

    Result dict keys: `story_id`, `story_file` (str path or 'UNRESOLVED'),
    `git_verified` (bool), `claimed_skipped` (list[str]).

    `claimed` is an opt-in filter (CER-095.1): when supplied and non-empty,
    a story whose ID is in `claimed` is skipped (its build is already in
    flight in another worktree) and appended to the returned
    `claimed_skipped` list. Called with no `claimed` argument, behaviour is
    byte-for-byte identical to before this filter existed — callers such as
    `flex_build.resolve_current_phase`'s no-index fallback, which only asks
    "does this phase file still have an unbuilt story?", intentionally do not
    pass it.
    """
    text = phase_file.read_text(encoding="utf-8")

    # Use _parse_stories_table directly (per spec) for IDs in order.
    story_ids = _parse_stories_table(text)
    # Parse statuses separately (the helper only returns IDs).
    statuses = _parse_stories_table_statuses(text)

    git_log = _git_log_oneline(project_dir)

    skipped: list[str] = []

    for story_id in story_ids:
        status = statuses.get(story_id, "")

        # If a matching commit exists, this story is definitively done.
        if _has_story_commit(story_id, git_log):
            continue

        # Deferred/skipped stories are deliberately excluded from "next up"
        # regardless of git state.
        if status in _SKIP_STATUSES:
            continue

        # A claimed story is already being built in another worktree
        # (CER-095.1). This check runs after the commit and skip-status
        # checks so a claim never overrides either of them (A5).
        if claimed and story_id in claimed:
            skipped.append(story_id)
            continue

        # If the table says complete but no commit exists, git overrides the
        # table — this story is the next unbuilt one and git_verified is true.
        git_verified = status == "complete"

        # Resolve the story file path.
        story_file: str
        try:
            resolve_story(story_id, project_dir)
            story_file = str(
                project_dir
                / "docs"
                / "stories"
                / story_id.split("-", 1)[0]
                / f"{story_id}.md"
            )
        except (FileNotFoundError, ValueError):
            story_file = "UNRESOLVED"

        return {
            "story_id": story_id,
            "story_file": story_file,
            "git_verified": git_verified,
            "claimed_skipped": skipped,
        }

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.argument("phase_file", type=click.Path())
@click.option("--json", "as_json", is_flag=True, help="Emit JSON output.")
@click.option(
    "--project-dir",
    default=None,
    type=click.Path(),
    help="Project root (defaults to phase_file's grandparent's parent).",
)
def next_story_cli(phase_file: str, as_json: bool, project_dir: str | None) -> None:
    """Find the next unbuilt story from a phase file."""
    phase_path = Path(phase_file)
    if not phase_path.exists() or not phase_path.is_file():
        click.echo(f"error: phase file not found: {phase_file}", err=True)
        sys.exit(2)

    if project_dir is None:
        # Default: <project_root>/docs/phases/phase-N.md → project_root
        resolved_project_dir = phase_path.resolve().parent.parent.parent
    else:
        resolved_project_dir = Path(project_dir).resolve()

    try:
        result = find_next_story(phase_path, resolved_project_dir)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    if result is None:
        if as_json:
            click.echo(json.dumps({"status": "all stories complete"}))
        else:
            click.echo("all stories complete")
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(result))
    else:
        click.echo(f"{result['story_id']} {result['story_file']}")
    sys.exit(0)


if __name__ == "__main__":
    next_story_cli()
