"""story_context.py — Read/write current story context in .companion/state.json.

Provides helpers for:
- Detecting whether a project has pairmode active
  (by checking for .claude/settings.deny-rationale.json)
- Reading and writing the current_story field in .companion/state.json

CLI usage:
  uv run python skills/pairmode/scripts/story_context.py --set RAIL-NNN
  uv run python skills/pairmode/scripts/story_context.py --get
  uv run python skills/pairmode/scripts/story_context.py --clear
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running directly with: uv run python skills/pairmode/scripts/story_context.py
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import click

from state_utils import _atomic_write_json

# Key under which the story-keyed record of active stories lives in
# state.json (INFRA-281 / CER-095.2). One story is no longer allowed to
# answer "which story is active" for every builder — with two worktrees in
# flight there can legitimately be two active stories at once, so state.json
# tracks all of them, keyed by story ID.
CURRENT_STORIES_KEY = "current_stories"


def is_pairmode_active(project_dir: Path) -> bool:
    """Return True if the project has pairmode active.

    Pairmode is considered active when
    .claude/settings.deny-rationale.json exists in the project root.
    """
    return (project_dir / ".claude" / "settings.deny-rationale.json").exists()


def read_state(companion_dir: Path) -> dict:
    """Read .companion/state.json, returning an empty dict if missing or malformed."""
    state_path = companion_dir / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def write_state(companion_dir: Path, state: dict) -> None:
    """Write state dict to .companion/state.json (pretty-printed, atomic)."""
    state_path = companion_dir / "state.json"
    _atomic_write_json(state_path, state)


def set_current_story(
    companion_dir: Path,
    story_id: str,
    title: str | None = None,
) -> dict:
    """Write current_story into .companion/state.json.

    Creates state.json if it does not exist.  Existing keys are preserved.
    Returns the updated state dict.

    INFRA-281 (CER-095.2): the same entry is written to both
    ``state["current_stories"][story_id]`` (the keyed record — the authority
    once more than one story can be in flight) and ``state["current_story"]``
    (a derived mirror, kept only for readers outside this story's scope:
    ``hooks/session_start.py``, ``global_session_check``,
    ``skills/observability/api/src/routes/context.ts``, and
    ``subagent_transcript._story_accepts_late_bump``). Both writes happen in
    the same ``write_state`` call so the mirror can never diverge from the
    keyed record through a partial write — it is derived, never
    independently written.

    Args:
        companion_dir: Path to the .companion directory.
        story_id: Story identifier, e.g. "2.3".
        title: Optional human-readable story title.

    Returns:
        The updated state dict (also written to disk).
    """
    state = read_state(companion_dir)
    entry: dict = {
        "id": story_id,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }
    if title is not None:
        entry["title"] = title
    state.setdefault(CURRENT_STORIES_KEY, {})[story_id] = entry
    state["current_story"] = entry
    write_state(companion_dir, state)
    return state


def clear_current_story(companion_dir: Path, story_id: str | None = None) -> dict:
    """Remove a story from ``current_stories`` (and, when unscoped, the
    ``current_story`` mirror) in state.json.

    INFRA-281 (CER-095.2): with two builders in flight, an unconditional
    clear silently switches off scope enforcement for whichever *other*
    story is still building. So this function supports two modes:

    - ``story_id`` given — removes only ``current_stories[story_id]``; every
      other entry survives untouched. If the removed entry was the one
      mirrored in ``current_story``, the mirror is re-pointed to the
      remaining entry with the latest ``set_at`` (ties broken by story ID,
      ascending, for a deterministic result independent of dict ordering),
      or removed entirely when no entries remain. If the removed entry was
      not the mirrored one, ``current_story`` is left unchanged.
    - ``story_id=None`` (the legacy/operator path, e.g. the CLI's
      ``--clear``) — clears ``current_stories`` entirely and removes
      ``current_story``, i.e. today's "clear the slate" behaviour. An
      operator asking to clear the slate means the slate.

    ``context_current_tokens`` and ``context_current_tokens_recorded_at`` are
    intentionally retained in both modes so accumulated token counts survive
    story transitions within a session.  Cross-session staleness is handled
    by the TTL check in ``context_budget.read_context_tokens_from_state``.

    Returns the updated state dict.
    """
    state = read_state(companion_dir)
    if story_id is None:
        state.pop(CURRENT_STORIES_KEY, None)
        state.pop("current_story", None)
        write_state(companion_dir, state)
        return state

    current_stories = state.get(CURRENT_STORIES_KEY, {})
    removed = current_stories.pop(story_id, None)
    if CURRENT_STORIES_KEY in state and not current_stories:
        state.pop(CURRENT_STORIES_KEY, None)
    elif current_stories:
        state[CURRENT_STORIES_KEY] = current_stories

    mirror = state.get("current_story")
    was_mirrored = removed is not None and mirror is not None and mirror.get("id") == story_id
    if was_mirrored:
        if current_stories:
            # Deterministic re-point: latest set_at wins; ties broken by
            # ascending story ID so the result never depends on dict order.
            latest_set_at = max(
                entry.get("set_at", "") for entry in current_stories.values()
            )
            next_id = min(
                sid
                for sid, entry in current_stories.items()
                if entry.get("set_at", "") == latest_set_at
            )
            state["current_story"] = current_stories[next_id]
        else:
            state.pop("current_story", None)

    write_state(companion_dir, state)
    return state


def get_current_story(companion_dir: Path) -> dict | None:
    """Return the current_story dict from state.json, or None if not set."""
    state = read_state(companion_dir)
    return state.get("current_story")


def get_current_stories(companion_dir: Path) -> dict[str, dict]:
    """Return the story-keyed ``current_stories`` dict from state.json.

    INFRA-281 (CER-095.2). Read-only — performs no writes, even when the
    state file predates this key.

    For a state file that already has ``current_stories``, that dict is
    returned as-is. For a pre-INFRA-281 state file that has the flat
    ``current_story`` but no ``current_stories`` key, a single-entry dict
    derived from the flat key is returned, so a project mid-migration is
    never seen as having zero active stories. For a state file with neither
    key, ``{}`` is returned.
    """
    state = read_state(companion_dir)
    keyed = state.get(CURRENT_STORIES_KEY)
    if isinstance(keyed, dict):
        return keyed
    legacy = state.get("current_story")
    if isinstance(legacy, dict) and legacy.get("id"):
        return {legacy["id"]: legacy}
    return {}


def match_file_to_module(file_path: str, modules: list[dict]) -> str | None:
    """Return the module name whose paths contain the given file path as a prefix.

    Iterates over each module entry in *modules* (list of dicts with ``name``
    and ``paths`` keys).  A module matches when any of its ``paths`` entries is
    a prefix of *file_path* (simple string prefix matching, no filesystem ops).

    Args:
        file_path: Absolute or relative path of the file that was changed.
        modules: List of module dicts, each with ``name`` (str) and ``paths``
                 (list[str]) keys, as found in ``.companion/modules.json``.

    Returns:
        The module name if a match is found, otherwise ``None``.
    """
    for module in modules:
        for path in module.get("paths", []):
            if file_path.startswith(path):
                return module.get("name")
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _resolve_story_file(story_id: str, project_dir: Path) -> Path:
    """Resolve a story ID like 'INFRA-074' to its file path.

    Returns the Path to docs/stories/<RAIL>/<RAIL>-NNN.md relative to
    project_dir.  Raises FileNotFoundError if the file does not exist or
    if the resolved path escapes the stories root (traversal guard).
    """
    parts = story_id.split("-")
    if len(parts) < 2:
        raise ValueError(f"Invalid story ID format: {story_id!r} (expected RAIL-NNN)")
    rail = parts[0].upper()
    stories_root = (project_dir / "docs" / "stories").resolve()
    story_path = (project_dir / "docs" / "stories" / rail / f"{story_id}.md").resolve()
    try:
        story_path.relative_to(stories_root)
    except ValueError:
        raise FileNotFoundError(f"Story file not found: {story_path}")
    if not story_path.exists():
        raise FileNotFoundError(f"Story file not found: {story_path}")
    return story_path


def _read_story_frontmatter(story_path: Path) -> dict:
    """Read YAML frontmatter from a story file using the canonical parser."""
    from schema_validator import _parse_frontmatter  # noqa: PLC0415

    text = story_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    return fm or {}


@click.command()
@click.option("--set", "story_id", default=None, help="Story ID to set as current (e.g. INFRA-001).")
@click.option("--get", "do_get", is_flag=True, default=False, help="Print current story ID.")
@click.option("--clear", "do_clear", is_flag=True, default=False, help="Remove current story from state.json.")
@click.option(
    "--project-dir",
    "project_dir",
    default=".",
    show_default=True,
    help="Project root directory (used to locate .companion/ and docs/).",
)
def cli(story_id: str | None, do_get: bool, do_clear: bool, project_dir: str) -> None:
    """Manage the current story in .companion/state.json.

    Exactly one of --set, --get, or --clear must be provided.
    """
    # Validate mutual exclusivity — exactly one option must be provided
    provided = sum([story_id is not None, do_get, do_clear])
    if provided == 0:
        raise click.UsageError("One of --set, --get, or --clear must be provided.")
    if provided > 1:
        raise click.UsageError("Only one of --set, --get, or --clear may be provided at a time.")

    proj = Path(project_dir).resolve()
    if len(proj.parts) < 3:
        raise click.ClickException(
            f"--project-dir {project_dir!r} resolves to a suspiciously shallow path: {proj}"
        )
    companion_dir = proj / ".companion"

    if story_id is not None:
        # --set: resolve story file and extract frontmatter
        try:
            story_path = _resolve_story_file(story_id, proj)
        except (FileNotFoundError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc

        fm = _read_story_frontmatter(story_path)
        title = fm.get("title")
        set_current_story(companion_dir, story_id, title=title)
        click.echo(f"Story set: {story_id}")

    elif do_get:
        # --get: print current story ID or "No story set."
        story = get_current_story(companion_dir)
        if story and story.get("id"):
            click.echo(story["id"])
        else:
            click.echo("No story set.")

    elif do_clear:
        # --clear: remove current_story from state.json
        clear_current_story(companion_dir)
        click.echo("Story cleared.")


if __name__ == "__main__":
    cli()
