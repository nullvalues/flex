"""
next_story.py — Find the next unbuilt story from a phase file.

Reads the ## Stories table from the given phase file (using
`_parse_stories_table` from `story_resolver`) and iterates stories in table
order. For each story, determines completion by checking whether a git commit
message mentions the story ID as a whole token (word-boundary match,
case-insensitive) anywhere in the project directory's git log — not only when
prefixed with the literal `story-`. This recognizes the `story-<ID>`
conventional-commit convention, parenthetical merge suffixes
(`... (RELEASE-014)`), and bare mentions (`RELEASE-014 status update`) alike,
while word boundaries keep a longer ID sharing a numeric prefix (e.g.
`INFRA-1001`) from matching a lookup for `INFRA-100`. Commits whose message
starts with `spec(` are excluded from matching (RELEASE-041) — spec-authoring
commits legitimately reference multiple story IDs in prose without building
any of them. A commit match is authoritative over the table's status column.

Returns the first story that:
  - has no matching git commit, AND
  - whose table status is not `deferred` or `skipped`.

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
        parts = [p.strip() for p in stripped.split('|')]
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


def _has_story_commit(story_id: str, git_log: str) -> bool:
    """Return True if `git_log` mentions `story_id` as a whole token
    (word-boundary match, case-insensitive), in a commit that isn't
    spec-authoring only.

    Matches the story ID anywhere in a commit message — whether prefixed
    with the `story-` conventional-commit convention
    (`feat(story-INFRA-100): done`), as a parenthetical merge suffix
    (`merge(fold-prep): ... (RELEASE-014)`), or as a bare mention
    (`chore(orchestrator): RELEASE-014 status update`). The `\\b`
    boundaries prevent a longer ID that shares a numeric prefix (e.g.
    `INFRA-1001`) from satisfying a lookup for `INFRA-100`.

    Commits whose message starts with `spec(` are skipped entirely (RELEASE-041):
    this repo's spec-authoring convention prefixes commits that create or edit
    specs, and such a commit legitimately lists several story IDs in prose
    (e.g. "add RELEASE-020/021/022 specs") without building any of them —
    counting that as build evidence produced a false positive."""
    if not git_log:
        return False
    pattern = re.compile(r'\b' + re.escape(story_id) + r'\b', re.IGNORECASE)
    for line in git_log.splitlines():
        message = line.split(" ", 1)[1] if " " in line else ""
        if message.lstrip().startswith("spec("):
            continue
        if pattern.search(line):
            return True
    return False


def find_next_story(phase_file: Path, project_dir: Path) -> dict | None:
    """Return the next unbuilt story or None if all are complete.

    Result dict keys: `story_id`, `story_file` (str path or 'UNRESOLVED'),
    `git_verified` (bool).
    """
    text = phase_file.read_text(encoding="utf-8")

    # Use _parse_stories_table directly (per spec) for IDs in order.
    story_ids = _parse_stories_table(text)
    # Parse statuses separately (the helper only returns IDs).
    statuses = _parse_stories_table_statuses(text)

    git_log = _git_log_oneline(project_dir)

    for story_id in story_ids:
        status = statuses.get(story_id, "")

        # If a matching commit exists, this story is definitively done.
        if _has_story_commit(story_id, git_log):
            continue

        # Deferred/skipped stories are deliberately excluded from "next up"
        # regardless of git state.
        if status in _SKIP_STATUSES:
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
