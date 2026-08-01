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

from state_utils import _atomic_write_json, state_lock

# Key under which the story-keyed record of active stories lives in
# state.json (INFRA-281 / CER-095.2). One story is no longer allowed to
# answer "which story is active" for every builder — with two worktrees in
# flight there can legitimately be two active stories at once, so state.json
# tracks all of them, keyed by story ID.
CURRENT_STORIES_KEY = "current_stories"

# INFRA-336: state.json key recording story IDs whose worktree was just
# discarded (reviewer FAIL, ``discard-story-worktree``) but whose FAIL
# outcome may not yet have been reconciled from ``effort.db``. Value shape
# is ``{story_id: <iso8601 timestamp>}``. Existence here is what widens
# ``subagent_transcript._story_accepts_late_bump``'s rule 2 to recognise a
# story that was building a moment ago (and therefore has a real, not
# stale/replayed, FAIL) even though its ``current_stories`` stamp has
# already been cleared. Entries are consumed (removed) the moment the late
# bump they authorized actually fires, or the moment the same story_id is
# re-stamped by a later ``create-story-worktree`` — see
# :func:`consume_recently_discarded` and its call sites — so this never
# accumulates unboundedly across discards and never re-authorizes a later,
# unrelated FAIL for the same story_id.
RECENTLY_DISCARDED_STORIES_KEY = "recently_discarded_stories"

# INFRA-336 (CER-148): state.json key recording, per story_id, the identity
# ("cycle key") of the most recent attempt cycle whose FAIL has already
# bumped the attempt counter — so a *second* FAIL row for the same
# still-open attempt (e.g. builder self-report, then reviewer, both
# eventually reconciled from effort.db) is recognised as a duplicate of one
# already-counted semantic attempt rather than bumping a second time. See
# ``subagent_transcript._attempt_cycle_key`` for how the cycle key is
# derived, and :func:`cycle_already_bumped` / :func:`mark_cycle_bumped` for
# the read/write pair. Value shape is ``{story_id: <cycle_key str>}``.
FAIL_CYCLE_BUMPED_KEY = "fail_cycle_bumped"


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
    # INFRA-285 (CER-097, item E4): the read-modify-write runs under the
    # advisory state lock. INFRA-281 made ``current_stories`` concurrency-
    # critical — with two worktrees in flight, two `create-story-worktree`
    # stamps racing here would drop one story's scope enforcement entirely.
    with state_lock(companion_dir / "state.json"):
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
    story transitions within a session. Cross-session staleness is handled by
    ``context_budget._is_stale``'s comparison of
    ``context_current_tokens_recorded_at`` against
    ``context_session_reset_at`` — the latter written by ``session_start.py``
    on ``clear``/``startup``. (INFRA-272: this docstring previously named a
    TTL check in ``context_budget.read_context_tokens_from_state``; that TTL
    was removed as dead code — ``decide()`` never called it — the retention
    behaviour above is unchanged.)

    Returns the updated state dict.
    """
    # INFRA-285 (CER-097, item E4): locked read-modify-write — see
    # set_current_story. A racing clear here is how a still-building story
    # silently loses its scope entry.
    with state_lock(companion_dir / "state.json"):
        return _clear_current_story_locked(companion_dir, story_id)


def _clear_current_story_locked(
    companion_dir: Path, story_id: str | None
) -> dict:
    """Body of :func:`clear_current_story`, executed inside the state lock."""
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


def mark_recently_discarded(companion_dir: Path, story_id: str) -> dict:
    """Record *story_id* under ``state["recently_discarded_stories"]``
    (INFRA-336).

    Called by ``discard-story-worktree`` at the same point it clears
    *story_id*'s ``current_stories`` stamp (``_clear_active_story``) — the
    marker exists precisely to survive that clear, so a FAIL for this
    ``story_id`` reconciled from ``effort.db`` *after* the discard (but
    before a retry re-stamps it) still authorizes a late attempt-counter
    bump. See :data:`RECENTLY_DISCARDED_STORIES_KEY` for the bounded-lifetime
    contract and :func:`consume_recently_discarded` for the removal side.

    Locked read-modify-write (mirrors :func:`set_current_story`) — two
    near-simultaneous discards for different stories must not clobber each
    other's marker entry.

    Creates ``state.json`` if it does not exist. Returns the updated state
    dict.
    """
    with state_lock(companion_dir / "state.json"):
        state = read_state(companion_dir)
        marker = state.setdefault(RECENTLY_DISCARDED_STORIES_KEY, {})
        marker[story_id] = datetime.now(timezone.utc).isoformat()
        write_state(companion_dir, state)
        return state


def consume_recently_discarded(companion_dir: Path, story_id: str) -> bool:
    """Remove *story_id* from ``state["recently_discarded_stories"]``
    (INFRA-336).

    Called from two places (whichever fires first bounds the marker's
    lifetime, per :data:`RECENTLY_DISCARDED_STORIES_KEY`'s contract):

    - ``subagent_transcript._story_accepts_late_bump``'s caller, the moment
      a late bump it authorized for this ``story_id`` actually fires;
    - ``flex_build._stamp_active_story`` (``create-story-worktree``), the
      moment this ``story_id`` is re-stamped as current — a retry means the
      discard is old news, and a *second*, unrelated FAIL for the same
      ``story_id`` must not still be treated as "just discarded".

    Returns ``True`` if an entry was present and removed, ``False``
    otherwise (including when ``state.json`` is missing/malformed or the
    key is absent) — a pure no-op in the common case where nothing needs
    consuming. Never raises.
    """
    try:
        with state_lock(companion_dir / "state.json"):
            state = read_state(companion_dir)
            marker = state.get(RECENTLY_DISCARDED_STORIES_KEY)
            if not isinstance(marker, dict) or story_id not in marker:
                return False
            marker.pop(story_id, None)
            if marker:
                state[RECENTLY_DISCARDED_STORIES_KEY] = marker
            else:
                state.pop(RECENTLY_DISCARDED_STORIES_KEY, None)
            write_state(companion_dir, state)
            return True
    except Exception:
        return False


def cycle_already_bumped(companion_dir: Path, story_id: str, cycle_key: str | None) -> bool:
    """Return ``True`` when *cycle_key* has already been recorded as bumped
    for *story_id* (INFRA-336, CER-148).

    ``cycle_key is None`` (no live ``current_stories``/``recently_discarded``
    marker to anchor a cycle on — see
    ``subagent_transcript._attempt_cycle_key``) always returns ``False``:
    the caller must fall back to the pre-CER-148 unconditional-bump
    behaviour rather than guess at deduplication with no anchor. Pure read;
    never raises.
    """
    if not cycle_key:
        return False
    try:
        state = read_state(companion_dir)
        bumped = state.get(FAIL_CYCLE_BUMPED_KEY)
        return isinstance(bumped, dict) and bumped.get(story_id) == cycle_key
    except Exception:
        return False


def mark_cycle_bumped(companion_dir: Path, story_id: str, cycle_key: str | None) -> dict:
    """Record that *cycle_key* has now bumped the attempt counter for
    *story_id* (INFRA-336, CER-148) — a subsequent FAIL row carrying the
    same ``cycle_key`` is then recognised as a duplicate of this same
    semantic attempt by :func:`cycle_already_bumped`.

    ``cycle_key is None`` is a no-op (returns the unmodified state) — there
    is nothing to anchor a dedup record to. Locked read-modify-write,
    mirroring :func:`mark_recently_discarded`.
    """
    if not cycle_key:
        return read_state(companion_dir)
    with state_lock(companion_dir / "state.json"):
        state = read_state(companion_dir)
        state.setdefault(FAIL_CYCLE_BUMPED_KEY, {})[story_id] = cycle_key
        write_state(companion_dir, state)
        return state


def clear_story_bump_markers(companion_dir: Path, story_id: str) -> dict:
    """Remove *story_id*'s entries from both
    ``recently_discarded_stories`` and ``fail_cycle_bumped`` (INFRA-336).

    Called from two places, each of which means "this story's prior FAIL
    history is no longer relevant": ``flex_build._stamp_active_story``
    (``create-story-worktree`` re-stamping the story — a new attempt cycle
    is starting) and ``merge-story-worktree`` (the story landed; nothing
    about a past discard/duplicate-FAIL cycle should linger). Locked
    read-modify-write; missing keys/file is a silent no-op. Never raises.
    """
    try:
        with state_lock(companion_dir / "state.json"):
            state = read_state(companion_dir)
            changed = False
            discarded = state.get(RECENTLY_DISCARDED_STORIES_KEY)
            if isinstance(discarded, dict) and story_id in discarded:
                discarded.pop(story_id, None)
                if discarded:
                    state[RECENTLY_DISCARDED_STORIES_KEY] = discarded
                else:
                    state.pop(RECENTLY_DISCARDED_STORIES_KEY, None)
                changed = True
            bumped = state.get(FAIL_CYCLE_BUMPED_KEY)
            if isinstance(bumped, dict) and story_id in bumped:
                bumped.pop(story_id, None)
                if bumped:
                    state[FAIL_CYCLE_BUMPED_KEY] = bumped
                else:
                    state.pop(FAIL_CYCLE_BUMPED_KEY, None)
                changed = True
            if changed:
                write_state(companion_dir, state)
            return state
    except Exception:
        return {}


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
