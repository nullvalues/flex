"""flex_build.py — single click CLI that aggregates the 8 inline Python
blocks that used to be embedded as ``uv run python -c "..."`` heredocs in
``skills/pairmode/templates/CLAUDE.build.md.j2``.

Each subcommand wraps one helper call from the pairmode scripts package
(``model_selector``, ``permission_scope``, ``effort_db``, ``context_health``).
The CLI exists solely so the orchestrator template can shell out to a single
script rather than embed multi-line Python boilerplate.

Commands: select-builder-model, select-reviewer-model,
select-security-auditor-model, select-intent-reviewer-model,
write-permissions, clear-permissions, permissions-create,
check-guardrail, context-health, check-stubs, current-phase,
transition-era, write-attempt-count, read-attempt-count,
clear-attempt-count, story-cost-estimate.

Story: INFRA-131.
"""

from __future__ import annotations

import datetime as _dt
import fnmatch
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Make sibling modules importable when invoked as a script.
sys.path.insert(0, str(Path(__file__).parent))

# When this file is executed directly (``__name__ == "__main__"``), alias
# this already-loaded module object under its own filename ("flex_build")
# in sys.modules *before* any sibling module runs ``from flex_build import
# ...``. Without this, next_action.py's bare import would re-execute this
# file as a second, distinct module object, and a module-level exception
# class (``AmbiguousActivePhaseError``, CER-077 — INFRA-265) raised via
# that copy would not match an ``except AmbiguousActivePhaseError`` clause
# written against this one — surfacing as an uncaught traceback instead of
# the loud CLI error A10 requires.
if __name__ == "__main__" and "flex_build" not in sys.modules:
    sys.modules["flex_build"] = sys.modules[__name__]

# next_story is imported lazily inside cmd_current_phase to avoid circular
# import issues when the module is loaded in test environments.


import click

from schema_validator import _parse_frontmatter  # noqa: E402
from model_selector import (  # noqa: E402
    select_builder_model,
    select_intent_reviewer_model,
    select_reviewer_model,
    select_security_auditor_model,
)
from permission_scope import (  # noqa: E402
    clear_story_permissions,
    write_story_permissions,
)
from effort_db import check_guardrail, resolve_effort_db_path  # noqa: E402
from context_health import check_context_health  # noqa: E402
from context_model import (  # noqa: E402
    CONTEXT_CURRENT_TOKENS_SOURCE_KEY,
    TRACK_STORY_SPEND,
    track_label,
)
from next_action import _CHECKPOINT_SEQUENCE  # noqa: E402
from state_utils import _atomic_write_json, state_lock  # noqa: E402
from story_context import (  # noqa: E402
    set_current_story,
    clear_current_story,
    get_current_stories,
    read_state,
    CURRENT_STORIES_KEY,
)
from scope_guard import (  # noqa: E402
    entry_is_fresh,
    PROTECTED_GLOBS,
    STATE_STORY_MAX_AGE_HOURS,
    _is_protected,
    _resolve_main_project_root,
    standing_paths_for,
)
from table_utils import split_table_row  # noqa: E402


def _stamp_active_story(project_path: Path, story_id: str) -> None:
    """Stamp *story_id* as ``current_story`` in the main checkout's
    ``.companion/state.json``, creating the directory if needed.

    Best-effort: any failure is swallowed by the caller (create-story-worktree
    surfaces it as a warning) — a stamping failure must never prevent the
    worktree itself from being created.
    """
    story_path = _story_path(story_id, project_path)
    fm = _read_story_frontmatter(story_path)
    companion_dir = project_path / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    set_current_story(companion_dir, story_id, title=fm.get("title"))


def _clear_active_story(project_path: Path, story_id: str) -> None:
    """Clear *story_id*'s entry from ``current_stories`` in the main
    checkout's ``.companion/state.json`` — and only that entry.

    INFRA-281 (CER-095.2): an unconditional clear here used to wipe the
    single global ``current_story`` slot on every merge/discard, which
    silently disabled scope enforcement for a *different* builder that is
    still running in its own worktree the moment the first story landed.
    Passing ``story_id`` through to ``clear_current_story`` makes the clear
    story-scoped, so a still-building sibling's entry (and therefore its
    scope enforcement) survives.

    Silent no-op when ``.companion/`` does not exist — merge/discard must
    never fail because the story was never stamped in the first place (e.g.
    a story ID with no matching spec file, as several worktree-lifecycle
    tests use).
    """
    companion_dir = project_path / ".companion"
    if not companion_dir.is_dir():
        return
    try:
        clear_current_story(companion_dir, story_id)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

_STORY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d{3}$")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _story_path(story_id: str, project_dir: Path) -> Path:
    """Return ``docs/stories/<RAIL>/<STORY_ID>.md`` for ``story_id``.

    Rail is the substring before the first ``-`` in ``story_id``.

    Raises ``ValueError`` when the resolved path escapes the stories root
    (e.g. a story_id containing path-traversal sequences).
    """
    rail = story_id.split("-", 1)[0]
    resolved = (project_dir / "docs" / "stories" / rail / f"{story_id}.md").resolve()
    stories_root = (project_dir / "docs" / "stories").resolve()
    try:
        resolved.relative_to(stories_root)
    except ValueError:
        raise ValueError(f"story ID escapes stories root: {story_id}")
    return resolved


def story_path_checked(story_id: str, project_dir: Path) -> Path:
    """Resolve *story_id* to its spec path, validating shape first (CER-064).

    ``spec-preflight`` has two entry points (this module's ``spec-preflight``
    subcommand and the standalone ``spec_preflight.py`` script) and they must
    not disagree about what counts as a valid story ID. This is the single
    validated resolver both use: it rejects a *story_id* that ``_STORY_ID_RE``
    does not match, then delegates to ``_story_path`` for containment
    resolution, letting that function's own escape-guard ``ValueError``
    propagate unchanged.
    """
    if not _STORY_ID_RE.match(story_id):
        raise ValueError(f"invalid story ID: {story_id!r}")
    return _story_path(story_id, project_dir)


def _read_story_frontmatter(story_path: Path) -> dict:
    """Read and parse YAML frontmatter from a story spec file.

    Always includes ``flex_factor`` as a float (default 1.0 when the key is
    absent or non-numeric). INFRA-160.
    """
    text = story_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text) or {}
    # Ensure flex_factor is always a float, defaulting to 1.0.
    try:
        flex_factor = float(fm.get("flex_factor", 1.0) or 1.0)
    except (TypeError, ValueError):
        flex_factor = 1.0
    fm["flex_factor"] = flex_factor
    return fm


def _read_guardrail_multiplier(project_dir: Path) -> float:
    """Read ``effort_guardrail_multiplier`` from ``.companion/state.json``.

    Defaults to ``3.0`` when state.json is absent, malformed, or missing the
    field.
    """
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return 3.0
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return float(data.get("effort_guardrail_multiplier", 3.0))
    except (json.JSONDecodeError, ValueError, TypeError, OSError):
        return 3.0


# ---------------------------------------------------------------------------
# Story-worktree helpers (INFRA-224)
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path, timeout: int = 120):
    """Run ``git <args>`` with ``cwd`` and return the completed process.

    Output is captured (text mode). Callers inspect ``returncode`` /
    ``stdout`` / ``stderr`` themselves. No exception is raised on non-zero
    exit — the story-worktree commands surface git's own error text.
    """
    import subprocess  # noqa: PLC0415

    return subprocess.run(  # noqa: S603
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _worktree_paths(story_id: str, project_dir: Path) -> tuple[Path, Path, str]:
    """Return ``(worktree_rel, worktree_abs, branch)`` for ``story_id``.

    Convention (INFRA-224): worktree at ``.pairmode-worktrees/<story-id>/``
    (relative to the project dir), branch ``pairmode/<story-id>``.
    """
    wt_rel = Path(".pairmode-worktrees") / story_id
    wt_abs = (project_dir / wt_rel).resolve()
    branch = f"pairmode/{story_id}"
    return wt_rel, wt_abs, branch


def _read_worktree_provision(project_path: Path) -> list[str]:
    """Read the optional ``worktree_provision`` list from
    ``<project_dir>/.companion/pairmode_context.json`` (CER-075, INFRA-302).

    Returns a list of project-relative paths to symlink into a fresh story
    worktree from the main checkout. Total: never raises, never exits.

    Read from ``pairmode_context.json`` rather than ``.companion/state.json``:
    ``state.json`` is runtime state under single-writer ownership
    (``docs/ideology.md:124-132`` — "Sidebar owns all state writes"; its
    writers take ``state_lock``), rewritten every build/merge cycle, while
    ``worktree_provision`` is durable, hand-authored operator intent that is
    never machine-written — mixing an operator-edited key into a
    lock-protected, machine-rewritten file invites a lost update and mixes
    intent with ephemera. ``pairmode_context.json`` is already the
    project-level operator config file (written once by bootstrap, read-only
    thereafter) and already holds the sibling build-environment keys
    ``build_command``/``test_command``/``test_dir``.

    Declared shape: a list of paths relative to the project (main checkout)
    root, e.g. ``["node_modules", ".env.local", "apps/web/node_modules"]``.
    Absolute paths and paths containing a ``..`` segment are rejected (by
    ``_provision_story_worktree``), not normalised.
    """
    context_path = project_path / ".companion" / "pairmode_context.json"
    if not context_path.exists():
        return []
    try:
        data = json.loads(context_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, dict) or "worktree_provision" not in data:
        return []

    raw = data["worktree_provision"]
    if not isinstance(raw, list):
        click.echo(
            f"warning: worktree_provision in {context_path} is not a list; ignoring",
            err=True,
        )
        return []

    entries: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            entries.append(item)
        else:
            click.echo(
                f"warning: worktree_provision entry {item!r} in {context_path} "
                "is not a non-empty string; skipping",
                err=True,
            )
    return entries


def _provision_story_worktree(
    project_path: Path, wt_abs: Path, entries: list[str]
) -> list[str]:
    """Symlink ``entries`` (project-relative paths) from ``project_path`` into
    ``wt_abs`` (CER-075, INFRA-302).

    Returns a list of human-readable warning lines (empty on full success).
    Never raises, never exits — a misconfigured or partially-satisfiable
    ``worktree_provision`` list must never cost an operator a worktree; each
    skip is loud (one warning line naming the entry and the reason) but
    non-fatal (docs/ideology.md:102-110 — "Never silently pass
    contradictions": the contradiction lives in the config, not in the
    worktree, so refusing to hand back a valid worktree would punish the
    wrong thing).

    Conditions are checked in cheap-to-expensive order; only when none of
    them holds is the link created.
    """
    project_root = project_path.resolve()
    warnings: list[str] = []

    for entry in entries:
        # 1. Must be a non-empty string (the reader already filters this, but
        # the provisioner is a public contract in its own right and must not
        # assume its only caller is well-behaved).
        if not isinstance(entry, str) or not entry.strip():
            warnings.append(f"worktree_provision entry {entry!r}: not a path string")
            continue

        entry_path = Path(entry)

        # 2. Absolute paths and any ".." segment are rejected outright, not
        # normalised — a provisioner that "helpfully" resolves a traversal is
        # a provisioner that hides one.
        if entry_path.is_absolute() or ".." in entry_path.parts:
            warnings.append(
                f"worktree_provision entry {entry!r}: must be a project-relative "
                "path without .."
            )
            continue

        src = project_path / entry_path

        # 3. Source must exist in the main checkout.
        if not src.exists():
            warnings.append(
                f"worktree_provision entry {entry!r}: not present in the main checkout"
            )
            continue

        # 4. Containment is checked on the *resolved* target, not the literal
        # string, so a symlink in the main checkout that points outside the
        # project is rejected too. This matters because the permission
        # artifact (docs/phases/permissions/<id>.json) — the Layer 1
        # allow-list scope_guard.py enforces — is written in terms of
        # project-relative paths; a link that silently escapes the checkout
        # would let a scope-allowed write land outside every path the guard
        # believes it is enforcing. Config here is operator-authored, so this
        # is a footgun guard, not a trust boundary.
        try:
            src_resolved = src.resolve()
        except OSError:
            warnings.append(f"worktree_provision entry {entry!r}: resolves outside the main checkout")
            continue
        if src_resolved != project_root and project_root not in src_resolved.parents:
            warnings.append(
                f"worktree_provision entry {entry!r}: resolves outside the main checkout"
            )
            continue

        dst = wt_abs / entry_path

        # 5. Already present in the worktree — including a broken symlink,
        # which os.path.exists() would report False for, so lexists is used.
        if os.path.lexists(dst):
            warnings.append(
                f"worktree_provision entry {entry!r}: already present in the worktree"
            )
            continue

        # 6. Parent directory must already exist in the worktree; the
        # provisioner never invents directory structure — a provisioner that
        # does is a provisioner that can quietly reshape a worktree.
        dst_parent = dst.parent
        if not dst_parent.exists():
            warnings.append(
                f"worktree_provision entry {entry!r}: parent directory missing in the worktree"
            )
            continue
        try:
            dst_parent_resolved = dst_parent.resolve()
        except OSError:
            warnings.append(
                f"worktree_provision entry {entry!r}: parent directory missing in the worktree"
            )
            continue
        wt_abs_resolved = wt_abs.resolve()
        if dst_parent_resolved != wt_abs_resolved and wt_abs_resolved not in dst_parent_resolved.parents:
            warnings.append(
                f"worktree_provision entry {entry!r}: parent directory missing in the worktree"
            )
            continue

        # 7. Refuse to shadow content git already tracks in the worktree —
        # this is the other half of this story (§ Ensures B3): shadowing a
        # tracked path with a symlink makes the worktree permanently dirty
        # and merge-story-worktree's rebase (flex_build.py:3618) refuse, the
        # same failure mode the tsconfig.tsbuildinfo half of this story
        # removes.
        tracked_check = _run_git(
            ["ls-files", "--error-unmatch", "--", entry],
            wt_abs,
        )
        if tracked_check.returncode == 0:
            warnings.append(
                f"worktree_provision entry {entry!r}: tracked by git; refusing to "
                "shadow tracked content"
            )
            continue

        # 8. Create the link. Target is absolute so it survives regardless of
        # the worktree's depth relative to the main checkout.
        try:
            os.symlink(src_resolved, dst)
        except OSError as exc:
            warnings.append(f"worktree_provision entry {entry!r}: {exc}")
            continue

    return warnings


def _teardown_story_worktree(project_path: Path, story_id: str) -> list[str]:
    """Remove a story's worktree and branch; return residue descriptions.

    Returns [] on full success. Never raises, never exits, never writes
    companion state — the caller decides what a residue means, because it
    means opposite things on the merge path (the story landed; clear the
    stamps anyway) and the discard path (nothing landed; leave them).

    Runs ``worktree remove --force`` first and, only when that succeeds,
    ``branch -D``: git refuses to delete a branch still checked out in a
    worktree, so attempting the delete after a failed removal would only
    produce a second, guaranteed, misleading error (CER-098(a), Ensures A2).
    """
    wt_rel, _wt_abs, branch = _worktree_paths(story_id, project_path)
    residue: list[str] = []

    remove = _run_git(["worktree", "remove", "--force", str(wt_rel)], project_path)
    if remove.returncode != 0:
        detail = (remove.stderr or remove.stdout or "").strip() or (
            f"failed to remove worktree {wt_rel}"
        )
        residue.append(f"worktree {wt_rel} still exists: {detail}")
        residue.append(f"branch {branch} still exists (removal skipped: worktree removal failed)")
        return residue

    delete = _run_git(["branch", "-D", branch], project_path)
    if delete.returncode != 0:
        detail = (delete.stderr or delete.stdout or "").strip() or (
            f"failed to delete branch {branch}"
        )
        residue.append(f"branch {branch} still exists: {detail}")

    return residue


def _residue_lines(story_id: str, residue: list[str]) -> list[str]:
    """Render *residue* (from ``_teardown_story_worktree``) plus repair
    commands for whichever artifacts remain (CER-098(a), Ensures A4).

    Both ``merge-story-worktree`` and ``discard-story-worktree`` call this so
    the operator sees identical text from either path.
    """
    if not residue:
        return []
    wt_rel = Path(".pairmode-worktrees") / story_id
    branch = f"pairmode/{story_id}"
    lines = list(residue)
    lines.append(f"repair: git worktree remove --force {wt_rel}")
    lines.append(f"repair: git branch -D {branch}")
    return lines


def _recovery_block(story_id: str, project_path: Path, *, reason: str) -> list[str]:
    """Return the ``recovery: ``-prefixed lines for a failed land (CER-098(b)).

    *reason* is ``"rebase"`` or ``"merge"`` and only changes the first line's
    wording — both failure modes leave the exact same state behind (nothing
    torn down, nothing cleared) and share the same re-run recovery.
    """
    branch = f"pairmode/{story_id}"
    wt_rel = Path(".pairmode-worktrees") / story_id
    if reason == "rebase":
        first = (
            f"recovery: rebase of {branch} failed — resolve the conflict in "
            f"{wt_rel}/ (or re-run to retry against a new tip); nothing was "
            "torn down or cleared"
        )
    else:
        first = (
            f"recovery: fast-forward merge of {branch} failed (a lost race — "
            "another merge-story-worktree landed first); nothing was torn "
            "down or cleared"
        )
    return [
        first,
        f"recovery: {branch} still holds the story's commits; they were not discarded",
        f"recovery: {wt_rel}/ still exists and still holds the in-flight claim",
        "recovery: the attempt counter, current_stories entry and permission "
        "artifact are deliberately untouched",
        "recovery: re-run to retry — this is the supported recovery, no "
        "manual repair step is required:",
        f"recovery:   flex_build.py merge-story-worktree --story-id {story_id} "
        f"--project-dir {project_path}",
    ]


MERGE_LOCK_TIMEOUT_SECONDS: float = 120.0
# Matches _run_git's own subprocess timeout (flex_build.py:177) — a waiter
# must not give up before the holder's longest single git call (rebase,
# merge, worktree remove) can finish; a shorter bound would time the waiter
# out while the holder is still doing legitimate work.


@contextmanager
def _merge_lock(project_path: Path):
    """Advisory, bounded, fail-open lock serializing merge/discard critical
    sections against ``.companion/merge.lock`` (CER-098(c)).

    This narrows — it does not close — the window in which two
    ``merge-story-worktree`` (or a merge and a discard) calls contend on the
    repository's own ``index.lock``. It does not make concurrent merges safe
    against an external ``git`` process or a second orchestrator; that is out
    of scope for the whole phase (``docs/phases/phase-109.md`` § Scope
    statement). "Make it reliable" changes — an unbounded wait, a retry loop,
    a lock daemon — are regressions for the same reason
    ``state_utils.state_lock``'s own docstring gives
    (``state_utils.py:180-194``): they trade a rare loud failure (a
    precisely-reported, re-runnable exit 1) for a common stall. Non-
    acquisition is not fatal: callers proceed exactly as they do today and
    emit a warning (CER-098(c), Ensures C4).
    """
    companion_dir = project_path / ".companion"
    try:
        companion_dir.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass
    with state_lock(
        companion_dir / "merge", timeout_seconds=MERGE_LOCK_TIMEOUT_SECONDS
    ) as acquired:
        yield acquired


def claimed_story_ids(project_dir: Path) -> set[str]:
    """Return the set of story IDs currently claimed by an in-flight worktree.

    A story is "claimed" (CER-095.1) for exactly the window between
    ``create-story-worktree`` and whichever of ``merge-story-worktree`` /
    ``discard-story-worktree`` ends its build cycle — both of those commands
    remove ``.pairmode-worktrees/<ID>/`` and delete the ``pairmode/<ID>``
    branch, which is what releases the claim. This function reads that single
    piece of state; it introduces no second record of what is in flight.

    A leftover ``pairmode/<ID>`` branch with no matching worktree directory is
    deliberately **not** treated as a claim: ``create-story-worktree`` already
    refuses to run (with its own clear error) against an existing branch, so
    duplicating that check here would make the resolver silently hide a story
    for a condition the claim-taking command already reports loudly.

    Returns an empty set when ``.pairmode-worktrees/`` does not exist or is
    unreadable. Performs no filesystem writes.
    """
    wt_root = project_dir / ".pairmode-worktrees"
    if not wt_root.exists():
        return set()
    try:
        entries = list(wt_root.iterdir())
    except OSError:
        return set()
    claimed: set[str] = set()
    for entry in entries:
        try:
            is_dir = entry.is_dir()
        except OSError:
            continue
        if is_dir and _STORY_ID_RE.match(entry.name):
            claimed.add(entry.name)
    return claimed


def _validate_story_id_or_exit(story_id: str) -> None:
    """Exit non-zero with a clear message if ``story_id`` is malformed.

    Guards the worktree/branch path construction against traversal or
    injection (the story ID becomes both a directory name and a branch name).
    """
    if not _STORY_ID_RE.match(story_id):
        click.echo(
            f"error: malformed story ID '{story_id}' "
            "(expected RAIL-NNN, e.g. INFRA-224)",
            err=True,
        )
        sys.exit(1)


def _current_branch(project_dir: Path) -> str:
    """Return the abbreviated branch name of the main worktree's HEAD."""
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], project_dir)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
def flex_build() -> None:
    """flex pairmode build orchestrator helpers (INFRA-131)."""


@flex_build.command("select-builder-model")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-131).")
@click.option(
    "--protected-file",
    "protected_files",
    multiple=True,
    default=(),
    help="Protected file path; may be supplied zero or more times.",
)
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_select_builder_model(
    story_id: str,
    protected_files: tuple[str, ...],
    project_dir: str,
) -> None:
    """Select the builder model for *story_id*; print ``model|reason``."""
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)
    fm = _read_story_frontmatter(story_path)
    story_class = fm.get("story_class") or "code"
    primary_files = fm.get("primary_files") or []
    model, reason = select_builder_model(
        story_class, list(primary_files), list(protected_files)
    )
    click.echo(f"{model}|{reason}")


@flex_build.command("write-permissions")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-131).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_write_permissions(story_id: str, project_dir: str) -> None:
    """Write story-scoped allow rules to ``.claude/settings.local.json``."""
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)
    write_story_permissions(story_path, project_path)


@flex_build.command("check-guardrail")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-131).")
@click.option("--tokens", required=True, type=int, help="Latest attempt token count.")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_guardrail(story_id: str, tokens: int, project_dir: str) -> None:
    """Run the effort guardrail; print the warning to stderr when fired."""
    project_path = Path(project_dir).resolve()
    rail = story_id.split("-", 1)[0]
    multiplier = _read_guardrail_multiplier(project_path)
    db_path = resolve_effort_db_path(project_path)
    result = check_guardrail(
        db_path,
        story_id=story_id,
        rail=rail,
        latest_tokens=tokens,
        multiplier=multiplier,
    )
    if result.get("fired"):
        click.echo(result["message"], err=True)


@flex_build.command("select-reviewer-model")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-131).")
@click.option("--attempt", required=True, type=int, help="Attempt number (1 = first).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_select_reviewer_model(
    story_id: str, attempt: int, project_dir: str
) -> None:
    """Select the reviewer model; print ``model`` then ``reason``."""
    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)
    fm = _read_story_frontmatter(story_path)
    story_class = fm.get("story_class") or "code"
    phase_id = fm.get("phase")
    phase_id_str = str(phase_id) if phase_id is not None else None
    model, reason = select_reviewer_model(
        story_class=story_class,
        attempt_number=attempt,
        phase_id=phase_id_str,
        project_dir=project_path,
    )
    click.echo(model)
    click.echo(reason)


@flex_build.command("clear-permissions")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_clear_permissions(project_dir: str) -> None:
    """Clear story-scoped allow rules from ``.claude/settings.local.json``."""
    project_path = Path(project_dir).resolve()
    clear_story_permissions(project_path)


class PermissionsCreateError(Exception):
    """Raised by ``generate_permissions_artifact`` on any recoverable failure."""


def generate_permissions_artifact(
    story_id: str, project_path: Path, *, spec_project_path: "Path | None" = None
) -> str:
    """Generate ``docs/phases/permissions/<story_id>.json`` from story frontmatter.

    Shared by the ``permissions-create`` CLI command and
    ``create-story-worktree`` (INFRA-238 Ensures 1) so the Layer 1 artifact is
    generated automatically on every worktree creation, not only when an
    operator runs the command by hand. Returns a human-readable status
    message; raises ``PermissionsCreateError`` on any failure instead of
    calling ``sys.exit`` directly, so callers other than the CLI command can
    decide how to handle it.

    *spec_project_path* (INFRA-320 § B3) lets a caller read the story spec
    from a different root than the artifact is written to — the shape
    ``widen_story_scope`` needs: the story file it just edited lives wherever
    the caller's own project root is (typically a builder's per-story
    worktree, since that copy is what gets committed), but the artifact
    itself must always land under the MAIN checkout root, because that is
    the only place ``scope_guard.check_path`` ever reads it from, regardless
    of the calling tool's cwd. Defaults to *project_path* — every existing
    caller (``permissions-create``, ``create-story-worktree``) reads and
    writes the same root, unchanged.
    """
    if not _STORY_ID_RE.match(story_id):
        raise PermissionsCreateError(f"invalid story_id format: {story_id!r}")

    spec_root = spec_project_path if spec_project_path is not None else project_path

    rail = story_id.split("-")[0]
    story_spec_rel = f"docs/stories/{rail}/{story_id}.md"
    story_path = spec_root / story_spec_rel

    stories_root = spec_root / "docs" / "stories"
    try:
        story_path.resolve().relative_to(stories_root.resolve())
    except ValueError:
        raise PermissionsCreateError("story spec path escapes project root") from None

    if not story_path.exists():
        raise PermissionsCreateError(f"story spec not found: {story_path}")

    try:
        fm = _read_story_frontmatter(story_path)
    except Exception as exc:  # noqa: BLE001
        # INFRA-296 B3: name the story file — the parser may now refuse a
        # malformed value (schema_validator.FrontmatterError), and the raw
        # parser message alone does not say which spec it came from.
        raise PermissionsCreateError(
            f"failed to parse frontmatter in {story_spec_rel}: {exc}"
        ) from exc

    primary_files: list[str] = fm.get("primary_files") or []
    touches: list[str] = fm.get("touches") or []

    # INFRA-296 B1 (CER-115): refuse a non-list before the concatenation
    # below. A frontmatter form the parser reads as a scalar (historically
    # `primary_files: [a, b]`) used to reach `primary_files + touches` as a
    # str and raise a bare TypeError, which is not a PermissionsCreateError
    # and so escaped every caller's handler.
    for _field, _value in (("primary_files", primary_files), ("touches", touches)):
        if not isinstance(_value, list):
            raise PermissionsCreateError(
                f"frontmatter field '{_field}' must be a list, got "
                f"{type(_value).__name__} in {story_spec_rel}"
            )

    seen: set[str] = set()
    allowed: list[str] = []
    for p in primary_files + touches:
        if p not in seen:
            seen.add(p)
            allowed.append(p)
    # INFRA-320 § A5: the story spec is no longer appended into
    # `allowed_paths` here — it is one of the per-story derived standing
    # paths (`scope_guard.standing_paths_for`) and is delivered through the
    # separate `standing_paths` key below instead, so `allowed_paths`
    # continues to mean exactly what this story declared.

    phase_raw = fm.get("phase")
    story_phase = (
        phase_raw.strip() if isinstance(phase_raw, str) and phase_raw.strip() else None
    )
    standing = list(standing_paths_for(story_id, story_phase))

    out_dir = project_path / "docs" / "phases" / "permissions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{story_id}.json"

    try:
        out_path.resolve().relative_to(out_dir.resolve())
    except ValueError:
        raise PermissionsCreateError("output path escapes permissions dir") from None

    computed = {
        "story_id": story_id,
        "story_spec": story_spec_rel,
        "allowed_paths": allowed,
        "standing_paths": standing,
    }
    if story_phase:
        computed["story_phase"] = story_phase

    existing_comparable: dict | None = None
    if out_path.exists():
        try:
            existing_payload = json.loads(out_path.read_text(encoding="utf-8"))
            if isinstance(existing_payload, dict):
                existing_comparable = {
                    k: v for k, v in existing_payload.items() if k != "generated_at"
                }
        except (json.JSONDecodeError, OSError):
            existing_comparable = None

    # INFRA-320 § A6: the unchanged short-circuit compares the full computed
    # payload (minus `generated_at`) rather than `allowed_paths` alone —
    # otherwise a `standing_paths`/`story_phase` change with an unchanged
    # `allowed_paths` would leave a stale artifact on disk.
    if existing_comparable == computed:
        return f"permissions: docs/phases/permissions/{story_id}.json unchanged ({len(allowed)} paths)"

    payload = dict(computed)
    payload["generated_at"] = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return f"permissions: wrote docs/phases/permissions/{story_id}.json ({len(allowed)} paths)"


def clear_permissions_artifact(story_id: str, project_path: Path) -> None:
    """Remove ``docs/phases/permissions/<story_id>.json`` if present.

    Called by ``merge-story-worktree``/``discard-story-worktree`` (INFRA-238
    Ensures 1) to clear the Layer 1 artifact stamped by
    ``create-story-worktree``, mirroring the ``current_story`` clear. Silent
    no-op when the file does not exist — merge/discard must never fail because
    a permissions file was never generated (e.g. a story with an empty
    ``primary_files``/``touches``, or a manually-discarded worktree).
    """
    out_path = project_path / "docs" / "phases" / "permissions" / f"{story_id}.json"
    try:
        out_path.unlink(missing_ok=True)
    except OSError:
        pass


@flex_build.command("permissions-create")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_permissions_create(story_id: str, project_dir: str) -> None:
    """Generate docs/phases/permissions/<STORY_ID>.json from story spec frontmatter."""
    project_path = Path(project_dir).resolve()
    try:
        message = generate_permissions_artifact(story_id, project_path)
    except PermissionsCreateError as exc:
        click.echo(f"permissions-create: {exc}", err=True)
        sys.exit(1)
    click.echo(message)


# ---------------------------------------------------------------------------
# permissions-widen — audited mid-build scope widening (INFRA-320 § B)
# ---------------------------------------------------------------------------


class PermissionsWidenError(Exception):
    """Raised by ``widen_story_scope`` on any refusal (INFRA-320 § B2)."""


_FRONTMATTER_BLOCK_RE = re.compile(r"\A(---\n)(.*?)(\n---\n)", re.DOTALL)
_FM_TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")


def _split_frontmatter_blocks(fm_text: str) -> list[tuple[str, str]]:
    """Split a frontmatter body into ``(key, raw_block_text)`` pairs, in
    order. ``raw_block_text`` is the key's own ``key: value`` line plus any
    indented continuation lines (e.g. a block-style list), with no trailing
    newline. Preserves every other line verbatim — this is a textual split,
    never a YAML round-trip.
    """
    blocks: list[tuple[str, list[str]]] = []
    for line in fm_text.splitlines():
        m = _FM_TOP_KEY_RE.match(line)
        if m:
            blocks.append((m.group(1), [line]))
        elif blocks:
            blocks[-1][1].append(line)
    return [(k, "\n".join(v)) for k, v in blocks]


def _append_touches_entry(fm_text: str, path: str) -> str:
    """Textually append *path* to a story frontmatter's ``touches:``
    block-style YAML list (INFRA-320 § B3.1), preserving existing entries
    and their order. Creates the ``touches:`` key immediately after
    ``primary_files:`` when absent (or at the end of the frontmatter body
    when ``primary_files:`` is also absent). Never round-trips through a
    YAML dumper — reformatting unrelated frontmatter or losing comments is
    exactly what a textual edit against the ``touches:`` block avoids.
    """
    blocks = _split_frontmatter_blocks(fm_text)
    new_item = f"  - {path}"
    keys = [k for k, _ in blocks]

    if "touches" in keys:
        idx = keys.index("touches")
        key, block = blocks[idx]
        header, _sep, remainder = block.partition("\n")
        header_value = header.split(":", 1)[1].strip() if ":" in header else ""
        if not remainder and header_value in ("", "[]"):
            # `touches:` alone, or an empty flow list — becomes a
            # single-item block-style list (INFRA-296 made flow style a
            # parse refusal, so this is the only flow-style shape we ever
            # see here).
            blocks[idx] = (key, f"touches:\n{new_item}")
        else:
            blocks[idx] = (key, f"{block}\n{new_item}")
    else:
        new_block = ("touches", f"touches:\n{new_item}")
        if "primary_files" in keys:
            blocks.insert(keys.index("primary_files") + 1, new_block)
        else:
            blocks.append(new_block)

    return "\n".join(block for _, block in blocks) + "\n"


def _widen_frontmatter_touches(full_text: str, path: str) -> str:
    """Apply `_append_touches_entry` to *full_text*'s frontmatter block only
    — the body (everything after the closing ``---``) is passed through
    untouched.
    """
    m = _FRONTMATTER_BLOCK_RE.match(full_text)
    if m is None:
        raise PermissionsWidenError("story file has no parseable frontmatter block")
    new_fm_body = _append_touches_entry(m.group(2), path)
    if new_fm_body.endswith("\n"):
        new_fm_body = new_fm_body[:-1]
    return full_text[: m.start(2)] + new_fm_body + full_text[m.end(2) :]


_SCOPE_WIDENINGS_SECTION_RE = re.compile(
    r"^## Scope widenings\s*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
_REQUIRES_SECTION_RE = re.compile(
    r"^## Requires\s*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)


def _append_scope_widening_row(
    full_text: str, path: str, reason: str, widened_at: str
) -> str:
    """Append a ``| path | reason | widened_at |`` row to the story body's
    ``## Scope widenings`` table (INFRA-320 § B3.2), creating the section
    (with its header row) immediately after ``## Requires`` when absent —
    or at the end of the body when ``## Requires`` is also absent.
    """
    row = f"| {path} | {reason} | {widened_at} |\n"

    existing = _SCOPE_WIDENINGS_SECTION_RE.search(full_text)
    if existing is not None:
        insert_at = existing.end()
        prefix = "" if full_text[:insert_at].endswith("\n") else "\n"
        return full_text[:insert_at] + prefix + row + full_text[insert_at:]

    new_section = (
        "\n## Scope widenings\n\n| path | reason | widened_at |\n"
        "| --- | --- | --- |\n" + row + "\n"
    )
    requires_match = _REQUIRES_SECTION_RE.search(full_text)
    if requires_match is not None:
        insert_at = requires_match.end()
        return full_text[:insert_at] + new_section + full_text[insert_at:]

    sep = "" if full_text.endswith("\n") else "\n"
    return full_text + sep + new_section


def widen_story_scope(
    story_id: str,
    path: str,
    reason: str,
    project_path: Path,
    *,
    dry_run: bool = False,
) -> str:
    """Perform an audited scope widening (INFRA-320 § B): declares *path* in
    the story's ``touches:``, records a ``## Scope widenings`` row with
    *reason*, and regenerates the permissions artifact — never an implicit
    grant. Modelled on `generate_permissions_artifact` (§ B1): raises
    `PermissionsWidenError` on any refusal instead of calling ``sys.exit``,
    so a future non-CLI caller can use it directly.

    Refuses (writing nothing) when: *story_id* is malformed or has no spec
    file; *reason* is empty/whitespace-only; *path* resolves outside the
    project root (same resolve-then-``relative_to`` containment semantics
    `permission_scope._safe_path` already uses — never a string
    ``startswith``); or *path* is matched by `scope_guard.PROTECTED_GLOBS` —
    a protected path is never widenable by this command under any flag
    (§ B2).

    Idempotent (§ B4): a *path* already present in ``primary_files`` or
    ``touches`` is a no-op success. A *path* already standing (§ A) is also
    a no-op success (§ B6) — widening it would re-introduce exactly the
    per-story copy-pasting § A removes.

    ``dry_run=True`` (§ B5) computes and describes every write without
    changing a byte of any file.

    The three writes (touches append, Scope widenings row, artifact
    regeneration) are computed fully in memory before anything reaches
    disk, and the story file's two edits land in a single ``write_text``
    call — so a failure anywhere in the computation leaves every file
    byte-identical to before the call (atomic in intent, § B3).
    """
    if not _STORY_ID_RE.match(story_id):
        raise PermissionsWidenError(f"invalid story_id format: {story_id!r}")

    story_path = _story_path(story_id, project_path)
    if not story_path.exists():
        raise PermissionsWidenError(f"story spec not found: {story_path}")

    if not reason or not reason.strip():
        raise PermissionsWidenError("--reason must not be empty")

    try:
        resolved = (project_path.resolve() / path).resolve()
        rel = resolved.relative_to(project_path.resolve())
    except (ValueError, OSError):
        raise PermissionsWidenError(
            f"--path resolves outside the project root: {path!r}"
        ) from None
    norm_path = rel.as_posix()

    if _is_protected(norm_path):
        matched = next(
            (g for g in PROTECTED_GLOBS if fnmatch.fnmatch(norm_path, g)), "?"
        )
        raise PermissionsWidenError(
            f"{norm_path} matches protected glob {matched!r} — protected paths "
            "are never widenable by permissions-widen (see builder/procedure.md "
            "§ Before writing anything, BUILDER BLOCKED)"
        )

    fm = _read_story_frontmatter(story_path)
    primary_files = fm.get("primary_files")
    touches = fm.get("touches")
    primary_files = primary_files if isinstance(primary_files, list) else []
    touches = touches if isinstance(touches, list) else []

    if norm_path in primary_files or norm_path in touches:
        return (
            f"permissions-widen: {norm_path} already declared for {story_id} "
            "— no-op"
        )

    phase_raw = fm.get("phase")
    story_phase = (
        phase_raw.strip() if isinstance(phase_raw, str) and phase_raw.strip() else None
    )
    if norm_path in standing_paths_for(story_id, story_phase):
        return (
            f"permissions-widen: {norm_path} is a standing shared surface — "
            "no touches: entry needed"
        )

    widened_at = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if dry_run:
        return (
            f"permissions-widen: DRY RUN — would append {norm_path!r} to "
            f"{story_id}'s touches:, add a Scope widenings row "
            f"(reason={reason!r}, widened_at={widened_at}), and regenerate "
            f"docs/phases/permissions/{story_id}.json"
        )

    text = story_path.read_text(encoding="utf-8")
    new_text = _widen_frontmatter_touches(text, norm_path)
    new_text = _append_scope_widening_row(new_text, norm_path, reason, widened_at)
    story_path.write_text(new_text, encoding="utf-8")

    # The story-file edit above lands wherever the caller says (typically the
    # builder's own per-story worktree — that copy is what gets committed and
    # merged). The permissions artifact, like every other scope_guard read,
    # only ever lives under the MAIN checkout root regardless of the caller's
    # cwd (`scope_guard._resolve_main_project_root`, INFRA-238) — a builder
    # invoking this from inside its worktree must still land the widened
    # artifact where `check_path` actually reads it, or the widening would
    # edit the story spec without ever un-blocking the write it names. Read
    # the just-widened frontmatter from *project_path* (the caller's own
    # root) but write the artifact under the resolved main root.
    generate_permissions_artifact(
        story_id,
        _resolve_main_project_root(project_path),
        spec_project_path=project_path,
    )

    return (
        f"permissions-widen: {norm_path} added to {story_id}'s touches: "
        f"(reason: {reason})"
    )


@flex_build.command("permissions-widen")
@click.argument("story_id")
@click.option(
    "--path",
    "widen_path",
    required=True,
    help="Repo-relative path to declare into the story's scope.",
)
@click.option(
    "--reason",
    required=True,
    help="Why this path is needed — required and must not be empty.",
)
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Echo the writes that would be made without changing any file.",
)
def cmd_permissions_widen(
    story_id: str, widen_path: str, reason: str, project_dir: str, dry_run: bool
) -> None:
    """Audited mid-build scope widening (INFRA-320 § B) — not an auto-widen.

    Declares --path in the story's touches:, records a reason and timestamp
    in a ## Scope widenings body row, and regenerates the permissions
    artifact, so the frontmatter stays the single source of truth and the
    artifact stays derived.
    """
    if not reason or not reason.strip():
        raise click.UsageError("--reason must not be empty")

    project_path = Path(project_dir).resolve()
    try:
        message = widen_story_scope(
            story_id, widen_path, reason, project_path, dry_run=dry_run
        )
    except PermissionsWidenError as exc:
        click.echo(f"permissions-widen: {exc}", err=True)
        sys.exit(1)
    click.echo(message)


def collectable_permission_artifacts(
    project_path: Path,
) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Classify ``docs/phases/permissions/*.json`` into collectable vs retained.

    INFRA-290: ``merge-story-worktree``/``discard-story-worktree`` clear each
    story's artifact inline (INFRA-238), but every artifact stamped before
    that story — or cleaned up by hand — is stranded sediment. This helper is
    the pure classification behind ``permissions-gc``; the command is a thin
    printer over it.

    Retention is a **whitelist of reasons to keep**, not a blacklist of
    reasons to delete — anything that cannot be positively classified is
    retained. A GC that deletes on uncertainty deletes a live permission
    artifact and hands the next builder a fail-closed scope guard with no
    explanation. An artifact is retained when any of:

    - a ``.pairmode-worktrees/<story_id>/`` directory exists (the INFRA-280
      in-flight claim, via ``claimed_story_ids`` — the existing derivation);
    - ``state.json``'s ``current_stories`` holds the story's key, or the flat
      ``current_story`` mirror names it (read from the same loaded state);
    - the file name does not parse as a story ID;
    - the file itself is unreadable.

    Everything else is collectable. Pure read — never writes anything, never
    reads ``effort.db``, and returns ``([], [])`` when the permissions
    directory does not exist.
    """
    perm_dir = project_path / "docs" / "phases" / "permissions"
    collectable: list[Path] = []
    retained: list[tuple[Path, str]] = []
    if not perm_dir.is_dir():
        return collectable, retained

    claimed = claimed_story_ids(project_path)
    companion_dir = project_path / ".companion"
    # get_current_stories reads the keyed record (falling back to the flat
    # mirror on a pre-INFRA-281 state file); the mirror is additionally read
    # from the same state load so a divergent mirror still retains.
    keyed_ids = set(get_current_stories(companion_dir).keys())
    mirror = read_state(companion_dir).get("current_story")
    mirror_id = mirror.get("id") if isinstance(mirror, dict) else None

    try:
        entries = sorted(perm_dir.iterdir())
    except OSError:
        return collectable, retained

    for entry in entries:
        if not entry.is_file() or entry.suffix != ".json":
            continue
        story_id = entry.stem
        if not _STORY_ID_RE.match(story_id):
            retained.append((entry, "file name does not parse as a story ID"))
            continue
        try:
            entry.read_bytes()
        except OSError:
            retained.append((entry, "artifact unreadable"))
            continue
        if story_id in claimed:
            retained.append(
                (entry, f".pairmode-worktrees/{story_id}/ exists (in-flight claim)")
            )
            continue
        if story_id in keyed_ids:
            retained.append((entry, "current_stories entry in state.json"))
            continue
        if mirror_id == story_id:
            retained.append((entry, "current_story mirror in state.json"))
            continue
        collectable.append(entry)
    return collectable, retained


@flex_build.command("permissions-gc")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Actually delete collectable artifacts. Without this flag, only reports.",
)
def cmd_permissions_gc(project_dir: str, apply: bool) -> None:
    """Report (default) or delete (--apply) stranded permission artifacts.

    INFRA-290: sweeps ``docs/phases/permissions/*.json`` files whose story is
    no longer in flight. Mirrors ``clear-stale-stories``' report-then-``--apply``
    shape. Never reads or writes effort.db, story files, or state.json; exits
    0 on every path including a missing permissions directory.
    """
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    collectable, retained = collectable_permission_artifacts(project_path)
    for path in collectable:
        rel = path.relative_to(project_path)
        if apply:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                click.echo(f"[warn] could not delete {rel}", err=True)
                continue
            click.echo(f"[apply] deleted {rel}")
        else:
            click.echo(f"[would] delete {rel}")
    for path, reason in retained:
        click.echo(f"retained {path.relative_to(project_path)} — {reason}")
    click.echo(
        f"permissions-gc: {len(collectable)} collectable, {len(retained)} retained"
    )


@flex_build.command("select-security-auditor-model")
@click.option("--phase-class", required=True, help="Phase class (e.g. production).")
def cmd_select_security_auditor_model(phase_class: str) -> None:
    """Select the security-auditor model; print ``model``."""
    model, _reason = select_security_auditor_model(phase_class)
    click.echo(model)


@flex_build.command("select-intent-reviewer-model")
@click.option("--phase-class", required=True, help="Phase class (e.g. production).")
def cmd_select_intent_reviewer_model(phase_class: str) -> None:
    """Select the intent-reviewer model; print ``model``."""
    model, _reason = select_intent_reviewer_model(phase_class)
    click.echo(model)


@flex_build.command("context-health")
@click.option("--phase", required=True, help="Phase ID to evaluate.")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_context_health(phase: str, project_dir: str) -> None:
    """Run the context-health check; print the JSON result.

    INFRA-321: the printed JSON is the two-tracked-sub-object shape from
    context_health.check_context_health's § B3 restructure — ``orchestrator``
    (the only track a pause/`/clear` verdict may be computed from) and
    ``story_spend`` (informational, retry-churn signal, never gates).
    """
    project_path = Path(project_dir).resolve()
    db_path = resolve_effort_db_path(project_path)
    result = check_context_health(
        db_path=db_path, current_phase=phase, project_dir=project_path
    )
    click.echo(json.dumps(result))


def _depth_guard(project_dir: Path) -> None:
    """Reject paths that are too shallow (fewer than 3 components)."""
    if len(project_dir.resolve().parts) < 3:
        click.echo(
            f"error: --project-dir '{project_dir}' is too shallow (depth guard).",
            err=True,
        )
        sys.exit(1)


def _is_aggregate_range(phase_ref: str) -> bool:
    """Return True when *phase_ref* looks like a legacy aggregate range (e.g. ``1–7`` or ``1-7``).

    An aggregate range has both sides of the separator as integers.  Named
    suffix phases like ``RD077-main`` are NOT ranges and must not be skipped.
    """
    for sep in ("–", "-"):
        if sep in phase_ref:
            left, _, right = phase_ref.partition(sep)
            try:
                int(left)
                int(right)
                return True
            except ValueError:
                pass
    return False


def _parse_index_phases(index_text: str) -> list[tuple[str, str]]:
    """Parse ``docs/phases/index.md`` and return ``[(phase_ref, status)]``.

    ``phase_ref`` is the raw first-column value (e.g. ``52``, ``RD077-main``).
    ``status`` is the third column, lowercased.

    Rows with multi-phase entries like ``1–7`` or ``1-7`` (where both sides of
    the separator are integers) are skipped because they describe legacy
    aggregated phases that have no individual phase file.  Named suffix phases
    like ``RD077-main`` are retained.
    """
    rows: list[tuple[str, str]] = []
    in_table = False
    header_seen = False
    separator_seen = False

    for line in index_text.splitlines():
        stripped = line.strip()

        if not stripped.startswith("|"):
            if in_table and stripped:
                # End of this table — reset and keep scanning for more tables.
                in_table = False
                header_seen = False
                separator_seen = False
            continue

        in_table = True
        # split rationale: `table_utils.split_table_row`
        parts = [p.strip() for p in split_table_row(stripped)]
        if len(parts) < 4:
            continue

        if not header_seen:
            header_seen = True
            continue

        if not separator_seen:
            separator_seen = True
            continue

        phase_ref = parts[1].strip()
        # Skip aggregate range rows (e.g. "1–7", "1-7") but keep suffix-keyed
        # phases like "RD077-main".
        if _is_aggregate_range(phase_ref):
            continue

        # Status is the third data column (index 3 after leading empty at 0).
        status = parts[3].strip().lower() if len(parts) > 3 else ""
        rows.append((phase_ref, status))

    return rows


class AmbiguousActivePhaseError(RuntimeError):
    """Raised when ``docs/phases/index.md`` has more than one row whose status
    is ``active`` (or ``active``-prefixed, e.g. ``active (paused)``) with an
    existing phase file (CER-077).

    Two rows simultaneously claiming ``active`` is a corrupt index, not a
    steady state — unlike multiple ``planned`` rows (the normal queue of
    future work), there is no non-arbitrary way to pick between two rows both
    asserting they are the one currently being worked. The live incident this
    guards against: on 2026-07-23 the ``fold-prep`` index had both phase-97
    and phase-98 flagged ``active``; phase-98's ``checkpoint-tag`` resolved to
    phase-97 — the still-in-progress fold — and marked it complete as a side
    effect of tagging 98 (caught and reverted by hand, commit ``c6c2c6a``).
    """


def _active_phase_candidates(project_dir: Path) -> list[tuple[str, str]]:
    """Return ``(phase_ref, status)`` for every index row that is a viable
    "currently active" candidate: not inactive per
    ``index_integrity.is_phase_inactive`` (plus the ``complete``-prefix guard
    for annotated terminal statuses like ``complete (partial)``), **and**
    whose ``docs/phases/phase-<ref>.md`` file exists.

    Returns rows in index order (build order). Returns ``[]`` when
    ``docs/phases/index.md`` does not exist.

    This is the single row walk over ``docs/phases/index.md``; both
    ``resolve_current_phase`` (below) and ``record-checkpoint-step``'s
    key-resolution precedence (CER-077) reuse it rather than re-parsing the
    index a second time. ``status`` is returned already ``.strip().lower()``'d
    (as ``_parse_index_phases`` produces it).
    """
    from index_integrity import is_phase_inactive  # noqa: PLC0415

    index_path = project_dir / "docs" / "phases" / "index.md"
    if not index_path.exists():
        return []

    index_text = index_path.read_text(encoding="utf-8")
    phase_rows = _parse_index_phases(index_text)

    candidates: list[tuple[str, str]] = []
    for phase_ref, status in phase_rows:
        normalised = status.strip().lower()
        if is_phase_inactive(normalised) or normalised.startswith("complete"):
            continue
        candidate = project_dir / "docs" / "phases" / f"phase-{phase_ref}.md"
        if candidate.exists():
            candidates.append((phase_ref, normalised))
        # Non-inactive row with no file yet — fileless-phase guard: keep
        # scanning for a later row that does have a file rather than
        # returning here.

    return candidates


def resolve_current_phase(project_dir: Path) -> Path | None:
    """Return the active phase file Path, or None when all phases are complete.

    Reads ``docs/phases/index.md`` when present (authoritative); falls back to
    scanning ``docs/phases/phase-*.md`` files for one with an unbuilt story.
    Pure read — no state writes.

    Extracted from ``cmd_current_phase`` as a module-level helper so that
    ``next_action.infer_position`` can compose it as a library call (RESOLVER-002).

    Index walk semantics (Era 3 fold — RELEASE-008): rows are walked in index
    order (build order) and the FIRST row whose status is active per
    ``index_integrity.is_phase_inactive`` AND whose phase file exists is
    returned.  Inactive statuses (``complete``, ``complete (partial)``,
    ``deferred``, ``backlog``) are skipped; an active-but-fileless row is
    skipped rather than terminating the walk, so a planned future row without
    a file never masks a later active phase that has one.

    Raises ``AmbiguousActivePhaseError`` (CER-077) when more than one
    candidate row's status is ``active`` or ``active``-prefixed — two rows
    both claiming to be the phase currently being worked is a corrupt index,
    not a fact this function may pick between. Deliberately does **not**
    raise when multiple candidate rows are ``planned`` (or any other
    non-``active`` status): a queue of planned future phases (e.g. 105, 106,
    107, 108 all queued behind an active/first-planned 104) is the normal,
    correct steady state of every index in the fleet, and raising there would
    break ``current-phase``/``next-action`` on every project with more than
    one queued phase. The multi-``planned`` ambiguity that CER-077 also
    surfaced is instead caught where it actually causes harm — at the
    irreversible ``checkpoint-tag`` mark-complete write — by
    ``record-checkpoint-step``'s explicit precedence chain, not by
    crippling this read-model.
    """
    # Import lazily to avoid issues in environments where next_story isn't on
    # sys.path at module load time.
    from next_story import find_next_story  # noqa: E402  # type: ignore[import]

    index_path = project_dir / "docs" / "phases" / "index.md"

    if index_path.exists():
        candidates = _active_phase_candidates(project_dir)

        active_candidates = [
            ref
            for ref, status in candidates
            if status == "active" or status.startswith("active")
        ]
        if len(active_candidates) > 1:
            raise AmbiguousActivePhaseError(
                "CER-077: docs/phases/index.md has more than one row flagged "
                "'active' with an existing phase file: "
                f"{', '.join(active_candidates)}. Refusing to guess which "
                "phase is active — fix the index so only one row is active."
            )

        if candidates:
            phase_ref = candidates[0][0]
            return project_dir / "docs" / "phases" / f"phase-{phase_ref}.md"

        # Index exists but no active phase with an existing file was found —
        # authoritative signal that no active phase remains.
        return None

    # No index file — fallback: scan phase files directly for one with an
    # unbuilt story.
    phases_dir = project_dir / "docs" / "phases"
    if not phases_dir.exists():
        return None

    # Collect all phase-N.md files and sort descending by N.
    phase_files = sorted(
        phases_dir.glob("phase-*.md"),
        key=lambda p: int(re.search(r"phase-(\d+)\.md", p.name).group(1))  # type: ignore[union-attr]
        if re.search(r"phase-(\d+)\.md", p.name)
        else 0,
        reverse=True,
    )

    for phase_file in phase_files:
        try:
            result = find_next_story(phase_file, project_dir)
        except Exception:  # noqa: BLE001
            continue
        if result is not None:
            return phase_file

    return None


def _resolve_current_phase_or_exit(project_path: Path) -> Path | None:
    """Call ``resolve_current_phase``, converting ``AmbiguousActivePhaseError``
    (CER-077) into a loud CLI error — stderr message + ``sys.exit(2)`` —
    instead of letting it reach click's default traceback handler (A10).
    """
    try:
        return resolve_current_phase(project_path)
    except AmbiguousActivePhaseError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)


@flex_build.command("current-phase")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_current_phase(project_dir: str) -> None:
    """Print the active phase file path; exit 1 if all stories are complete."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)

    result = _resolve_current_phase_or_exit(project_path)
    if result is not None:
        click.echo(str(result.relative_to(project_path)))
        sys.exit(0)

    click.echo("No active phase found — all stories complete.", err=True)
    sys.exit(1)


def _next_phase_after(after_phase: str, project_dir: Path) -> "str | None":
    """Return the ``phase_ref`` of the index row immediately following
    *after_phase*, or ``None`` when the index is missing, the phase is not
    found, or the matched row is the last one.

    Extracted from ``cmd_next_phase`` (INFRA-236) so ``checkpoint-report``
    can reuse the same lookup without shelling out to a second CLI
    invocation. Pure read — no state writes.
    """
    index_path = project_dir / "docs" / "phases" / "index.md"
    if not index_path.exists():
        return None

    index_text = index_path.read_text(encoding="utf-8")
    phase_rows = _parse_index_phases(index_text)

    for i, (phase_ref, _status) in enumerate(phase_rows):
        if phase_ref == after_phase:
            if i + 1 < len(phase_rows):
                return phase_rows[i + 1][0]
            return None

    return None


@flex_build.command("next-phase")
@click.option(
    "--after",
    "after_phase",
    required=True,
    type=str,
    help="Current phase key (e.g. 59 or RD077-main).",
)
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_next_phase(after_phase: str, project_dir: str) -> None:
    """Print the phase key immediately following *after_phase* in the index.

    Reads ``docs/phases/index.md``, finds the row whose ``phase_ref`` equals
    ``--after``, and prints the ``phase_ref`` of the next row.  Exits 1
    (with empty stdout) when the index is missing, the phase is not found, or
    the matched row is the last in the index.

    The command is read-only and makes no writes.
    """
    project_path = Path(project_dir).resolve()

    next_ref = _next_phase_after(after_phase, project_path)
    if next_ref is None:
        sys.exit(1)
    click.echo(next_ref)
    sys.exit(0)


def _mark_phase_complete_in_index(phase_key: str, project_dir: Path) -> bool:
    """Set the status cell of *phase_key*'s row in docs/phases/index.md to
    'complete'.

    Idempotent no-op (returns ``False``) when the index file is absent, the
    phase row is not found, or the row is already ``complete``. Returns
    ``True`` when a write happened.

    Extracted from ``cmd_mark_phase_complete`` so that both the standalone
    ``mark-phase-complete`` CLI command and the ``checkpoint-tag`` step of
    ``record-checkpoint-step`` share one implementation (INFRA-239) — the
    write side no longer requires a second, separate CLI call for the
    checkpoint-tag path.
    """
    import tempfile  # noqa: PLC0415

    index_path = project_dir / "docs" / "phases" / "index.md"
    if not index_path.exists():
        return False

    text = index_path.read_text(encoding="utf-8")
    rows = _parse_index_phases(text)
    found = any(ref == phase_key for ref, _ in rows)
    if not found:
        return False

    # Check for idempotency: if already complete, no write.
    for ref, status in rows:
        if ref == phase_key and status == "complete":
            return False

    # Rewrite the matching row in-place, line by line.
    new_lines: list[str] = []
    replaced = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if not replaced and stripped.startswith("|"):
            # inner cells: drop the leading/trailing empty strings produced by
            # splitting "| a | b | c |" on unescaped "|".
            # split rationale: `table_utils.split_table_row` — the split is
            # non-destructive, so the rejoin below writes the row back with
            # its `\|` cells intact.
            cells = [p.strip() for p in split_table_row(stripped)[1:-1]]
            # cells[0]=phase, cells[1]=title, cells[2]=status, cells[3:]=rest
            if len(cells) >= 3:
                if cells[0] == phase_key and cells[2] != "complete":
                    cells[2] = "complete"
                    new_row = "| " + " | ".join(cells) + " |\n"
                    new_lines.append(new_row)
                    replaced = True
                    continue
        new_lines.append(line)

    if not replaced:
        return False

    new_text = "".join(new_lines)

    # Atomic write: NamedTemporaryFile in same directory + os.replace.
    dir_ = index_path.parent
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=dir_,
        delete=False,
        suffix=".tmp",
    ) as tf:
        tf.write(new_text)
        tmp_path_str = tf.name

    os.replace(tmp_path_str, index_path)
    return True


def _is_era_ledger_heading(stripped: str) -> bool:
    """True for the era doc's machine-maintained ledger heading.

    Matches ``## Phases`` exactly and the qualified variant
    ``## Phases (...)``; never a deeper heading. Deliberately duplicated from
    its twin ``phase_new._update_era_phases_table`` / ``phase_new.
    _is_era_ledger_heading`` rather than imported — importing ``phase_new``
    into ``flex_build`` would add a whole module dependency for two tokens
    (INFRA-267). Keep the two in sync.
    """
    return stripped == "## Phases" or stripped.startswith("## Phases ")


def _mark_phase_complete_in_era_ledger(phase_key: str, project_dir: Path) -> bool:
    """Set the status cell of *phase_key*'s row in the **active** era doc's
    ``## Phases`` ledger to 'complete'.

    The era doc is the era's phase ledger: ``phase_new.py`` appends a
    ``| <phase> | <title> | planned |`` row at scaffold time and this helper
    advances it, keeping the ledger in parity with ``docs/phases/index.md``
    (which ``check-index`` check 2c enforces). Before INFRA-267 nothing ever
    advanced it, so every checkpointed phase read ``planned`` forever
    (CER-082).

    Idempotent no-op (returns ``False``, writes nothing, raises nothing) when
    ``docs/eras/`` is absent, no era doc has ``status: active``, the active era
    doc has no ledger heading or table, no ledger row's first cell equals
    *phase_key*, or that row already reads ``complete``. Legacy eras with no
    ledger row must never crash a checkpoint. Returns ``True`` when a write
    happened.

    Mirrors ``_mark_phase_complete_in_index``'s atomic-write contract
    (``NamedTemporaryFile`` in the target's own directory + ``os.replace``) and
    flips any non-``complete`` status, ``deferred`` included, so both writes
    stay symmetric.
    """
    import tempfile  # noqa: PLC0415

    eras_dir = project_dir / "docs" / "eras"
    if not eras_dir.is_dir():
        return False

    # Collect active era docs. More than one: highest ID wins (last in sorted
    # order), matching phase_new._detect_active_era — but silently; other
    # tooling reads this CLI's stdout.
    active: list[Path] = []
    for era_path in sorted(eras_dir.glob("*.md")):
        try:
            text = era_path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        if fm is None:
            continue
        if fm.get("status") == "active":
            active.append(era_path)

    if not active:
        return False

    target = active[-1]
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return False

    new_lines: list[str] = []
    in_ledger_section = False
    in_ledger_table = False
    replaced = False

    for line in text.splitlines(keepends=True):
        stripped = line.strip()

        if not replaced and not in_ledger_section and _is_era_ledger_heading(stripped):
            in_ledger_section = True
            new_lines.append(line)
            continue

        if in_ledger_section and not replaced:
            if stripped.startswith("|"):
                in_ledger_table = True
                # inner cells: drop the leading/trailing empty strings produced
                # by splitting "| a | b | c |" on unescaped "|". Header and
                # |---| rows never match phase_key, so they are skipped
                # naturally.
                # split rationale: `table_utils.split_table_row` — the split is
                # non-destructive, so the rejoin below writes the row back with
                # its `\|` cells intact.
                cells = [p.strip() for p in split_table_row(stripped)[1:-1]]
                if len(cells) >= 3 and cells[0] == phase_key:
                    if cells[2] == "complete":
                        return False
                    cells[2] = "complete"
                    new_lines.append("| " + " | ".join(cells) + " |\n")
                    replaced = True
                    continue
            elif in_ledger_table and stripped:
                # Left the first table in the ledger section without a match.
                in_ledger_section = False

        new_lines.append(line)

    if not replaced:
        return False

    new_text = "".join(new_lines)

    dir_ = target.parent
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=dir_,
            delete=False,
            suffix=".tmp",
        ) as tf:
            tf.write(new_text)
            tmp_path_str = tf.name
        os.replace(tmp_path_str, target)
    except OSError:
        return False

    return True


@flex_build.command("mark-phase-complete")
@click.option(
    "--phase",
    "phase_key",
    required=True,
    type=str,
    help="Phase key to mark complete (e.g. 59 or PM037-main).",
)
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_mark_phase_complete(phase_key: str, project_dir: str) -> None:
    """Set the status cell of a phase row in docs/phases/index.md to 'complete'."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    index_path = project_path / "docs" / "phases" / "index.md"
    if not index_path.exists():
        click.echo(
            f"mark-phase-complete: index not found: {index_path}", err=True
        )
        raise SystemExit(1)

    text = index_path.read_text(encoding="utf-8")
    rows = _parse_index_phases(text)
    found = any(ref == phase_key for ref, _ in rows)
    if not found:
        click.echo(
            f"mark-phase-complete: phase '{phase_key}' not in index", err=True
        )
        raise SystemExit(1)

    _mark_phase_complete_in_index(phase_key, project_path)
    # Same key, same invocation: the active era doc's ledger row tracks the
    # index row (INFRA-267/CER-082). A no-op there never affects this command's
    # exit status.
    _mark_phase_complete_in_era_ledger(phase_key, project_path)


_DELEGATION_RE = re.compile(
    r"see phase doc|see docs/phases/|see phase-",
    re.IGNORECASE,
)
_ACCEPTANCE_RE = re.compile(
    r"^##\s+(?:ensures|acceptance criterion|acceptance criteria)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@flex_build.command("check-stubs")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_stubs(project_dir: str) -> None:
    """Audit all story files for stubs (delegation or missing acceptance surface)."""
    project_path = Path(project_dir).resolve()
    stories_dir = project_path / "docs" / "stories"

    click.echo(f"Scanning docs/stories/ in {project_path}...")
    click.echo("")

    if not stories_dir.exists():
        click.echo("Summary: 0 stubs / 0 total stories")
        sys.exit(0)

    story_files = sorted(stories_dir.rglob("*.md"))

    rows: list[tuple[str, str, str, str]] = []
    for story_file in story_files:
        story_id = story_file.stem
        text = story_file.read_text(encoding="utf-8")

        m = _DELEGATION_RE.search(text)
        if m:
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            matched_line = text[line_start : line_end if line_end != -1 else len(text)].strip()
            if len(matched_line) > 70:
                matched_line = matched_line[:70] + "..."
            rows.append(("STUB", story_id, "delegation", f'"{matched_line}"'))
        elif not _ACCEPTANCE_RE.search(text):
            rows.append(("STUB", story_id, "no-acceptance", "(no ## Ensures or ## Acceptance criterion)"))
        else:
            rows.append(("OK", story_id, "self-contained", ""))

    for status, story_id, reason, detail in rows:
        if status == "STUB":
            click.echo(f"STUB  {story_id:<12}  {reason:<14}  {detail}")
        else:
            click.echo(f"OK    {story_id:<12}  self-contained")

    stub_rows = [(s, sid, r, d) for s, sid, r, d in rows if s == "STUB"]
    stub_count = len(stub_rows)
    total = len(rows)
    delegation_count = sum(1 for _, _, r, _ in stub_rows if r == "delegation")
    no_acceptance_count = sum(1 for _, _, r, _ in stub_rows if r == "no-acceptance")
    pct = int(stub_count / total * 100) if total > 0 else 0

    click.echo("")
    click.echo(f"Summary: {stub_count} stubs / {total} total stories ({pct}%)")
    click.echo(f"  delegation:    {delegation_count}")
    click.echo(f"  no-acceptance: {no_acceptance_count}")

    sys.exit(1 if stub_count > 0 else 0)


# ---------------------------------------------------------------------------
# Per-story attempt counter (BUILD-022; story-keyed storage: INFRA-282, CER-095.3)
# ---------------------------------------------------------------------------

# Top-level key under which the story-ID -> attempt-count map is stored in
# .companion/attempt_counter.json (INFRA-282, CER-095.3).
_ATTEMPT_COUNTER_STORIES_KEY = "stories"


def _attempt_counter_path(project_dir: Path) -> Path:
    return project_dir / ".companion" / "attempt_counter.json"


def _read_attempt_counters(project_dir: Path) -> dict[str, int]:
    """Return the full story-ID -> attempt-count mapping.

    Pure read — never writes, on any path, including when it normalises a
    legacy-shape file in memory (INFRA-282, CER-095.3, assertion 2/3).

    Returns ``{}`` when the file is absent, unreadable, or malformed JSON.
    Normalises both on-disk shapes:

    - keyed (current): ``{"stories": {"<story_id>": <count>, ...}}`` — each
      value is coerced with ``int()``; a key whose value will not coerce is
      dropped.
    - legacy (pre-INFRA-282): ``{"story_id": "<id>", "attempt_count": <n>}``
      — the single entry is returned as a one-item mapping, or dropped if
      the count will not coerce. Legacy files are read as-is here and
      upgraded to the keyed shape only on the next write
      (``write_attempt_count``) — there is no migration step.
    """
    path = _attempt_counter_path(project_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    stories = data.get(_ATTEMPT_COUNTER_STORIES_KEY)
    if isinstance(stories, dict):
        counters: dict[str, int] = {}
        for story_id, count in stories.items():
            try:
                counters[story_id] = int(count)
            except (TypeError, ValueError):
                continue
        return counters
    legacy_story_id = data.get("story_id")
    if isinstance(legacy_story_id, str):
        try:
            return {legacy_story_id: int(data.get("attempt_count", 0))}
        except (TypeError, ValueError):
            return {}
    return {}


@flex_build.command("write-attempt-count")
@click.option("--story-id", required=True, help="Story ID (e.g. BUILD-022).")
@click.option("--count", required=True, type=int, help="Attempt count (>=1).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_write_attempt_count(story_id: str, count: int, project_dir: str) -> None:
    """Persist the per-story attempt counter to .companion/attempt_counter.json."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    write_attempt_count(story_id, count, project_path)


def write_attempt_count(story_id: str, count: int, project_dir: Path) -> None:
    """Persist *story_id*'s attempt count into the story-keyed counter file.

    Read-modify-write over the full keyed map (``_read_attempt_counters``),
    so a write for one story never removes or alters another in-flight
    story's entry (INFRA-282, CER-095.3) — the pre-story whole-file rewrite
    silently clobbered a sibling builder's escalation state under parallel
    story builds (CER-095 item 3). A legacy flat-shape file is upgraded to
    the keyed shape as a side effect of this write, with its existing entry
    preserved as one of the keys.

    Extracted as a module-level helper (mirrors ``read_attempt_count``) so
    other modules — ``subagent_transcript.record_attempt_from_transcript``
    and ``cmd_merge_story_worktree`` — can compose it as a library call
    instead of shelling out to the CLI (INFRA-237).

    Persists via ``state_utils._atomic_write_json`` (temp-file + os.replace),
    not a direct in-place write, so a reader never observes a
    truncated/partial file.
    """
    path = _attempt_counter_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    counters = _read_attempt_counters(project_dir)
    counters[story_id] = count
    _atomic_write_json(path, {_ATTEMPT_COUNTER_STORIES_KEY: counters})


def bump_attempt_count(story_id: str, project_dir: Path) -> int:
    """Increment and persist the attempt counter for *story_id*; return the new count.

    Reads the current count via ``read_attempt_count`` and writes
    ``count + 1`` under *story_id*'s own key. Bumps are per-key: each story
    has its own entry in the counter file, so another story's entry is
    neither read nor overwritten by this call — a story with no existing
    entry starts at 1, not at whatever count a different story happens to
    hold (INFRA-282, CER-095.3; this replaces the pre-story "a mismatched
    story_id resets the counter to 1" whole-file semantics).

    Called on builder/reviewer FAIL (INFRA-237). The persisted counter is
    ``next_action.infer_position``'s sole durable signal that a story
    attempt failed before any commit exists — independent of
    ``effort_tracking`` (core build-loop control state, not observability).
    """
    new_count = read_attempt_count(story_id, project_dir) + 1
    write_attempt_count(story_id, new_count, project_dir)
    return new_count


def read_attempt_count(story_id: str, project_dir: Path) -> int:
    """Return the persisted attempt count for *story_id* (0 if absent).

    Pure read — no state writes, including no upgrade write for a
    legacy-shape file (that upgrade only happens on the next
    ``write_attempt_count``/``bump_attempt_count`` call). Reads are per-key:
    a count stored for a different story never satisfies a read for
    *story_id*, and a count stored for *story_id* is returned even when
    other stories also have entries in the same file (INFRA-282, CER-095.3).
    Also reads the legacy flat shape (``{"story_id": ..., "attempt_count":
    ...}``) transparently via ``_read_attempt_counters``.

    Extracted from ``cmd_read_attempt_count`` as a module-level helper so that
    ``next_action.infer_position`` can compose it as a library call (RESOLVER-002).
    """
    return _read_attempt_counters(project_dir).get(story_id, 0)


@flex_build.command("read-attempt-count")
@click.option("--story-id", required=True, help="Story ID (e.g. BUILD-022).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_read_attempt_count(story_id: str, project_dir: str) -> None:
    """Print the persisted attempt count for *story_id* (0 if absent/mismatched)."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    click.echo(str(read_attempt_count(story_id, project_path)))


@flex_build.command("clear-attempt-count")
@click.option(
    "--story-id",
    default=None,
    help=(
        "Story ID to clear (e.g. BUILD-022). When omitted, the whole "
        "counter file is removed (unchanged legacy behaviour, retained for "
        "operator recovery)."
    ),
)
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_clear_attempt_count(story_id: str | None, project_dir: str) -> None:
    """Delete .companion/attempt_counter.json, or just one story's entry."""
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    clear_attempt_count(project_path, story_id)


def clear_attempt_count(project_dir: Path, story_id: str | None = None) -> None:
    """Clear the attempt counter, scoped to *story_id* when given.

    ``story_id is None``: delete ``.companion/attempt_counter.json`` if
    present (today's behaviour, preserved for operator recovery via the
    ``clear-attempt-count`` CLI with no ``--story-id``).

    ``story_id`` given: remove only that story's entry from the keyed map,
    leaving every other story's entry — and the file itself — intact
    (deleting the file only when the removed entry was the last one). This
    scoped form exists because an unconditional clear on merge would wipe a
    sibling builder's still-live escalation state the moment any other
    story lands (INFRA-282, CER-095.3 — the same class of cross-story
    clobber INFRA-281 fixed for the ``current_story`` stamp). Missing file
    or missing key is a silent no-op either way.

    Extracted as a module-level helper (mirrors ``read_attempt_count``) so
    ``cmd_merge_story_worktree`` can clear the counter on a successful merge
    without shelling out to the CLI (INFRA-237).
    """
    path = _attempt_counter_path(project_dir)
    if story_id is None:
        if path.exists():
            path.unlink()
        return
    counters = _read_attempt_counters(project_dir)
    if story_id not in counters:
        return
    counters.pop(story_id, None)
    if not counters:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path, {_ATTEMPT_COUNTER_STORIES_KEY: counters})


# ---------------------------------------------------------------------------
# Stale current_stories reporting and clearing (INFRA-271, CER-080)
# ---------------------------------------------------------------------------


@flex_build.command("clear-stale-stories")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--max-age-hours",
    default=None,
    type=float,
    help=(
        "Override scope_guard.STATE_STORY_MAX_AGE_HOURS for this run. "
        "Defaults to the module constant so the CLI and the guard can "
        "never disagree about what 'stale' means."
    ),
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Actually clear stale entries. Without this flag, only reports.",
)
def cmd_clear_stale_stories(project_dir: str, max_age_hours: float | None, apply: bool) -> None:
    """Report (default) or clear (--apply) stale current_stories/current_story
    stamps in .companion/state.json (INFRA-271, CER-080).

    A `current_stories` entry older than the cutoff is far more likely to be
    an uncleaned/idle checkout than an in-flight build (the observed case:
    INFRA-209, stamped 2026-07-20, never cleared, blocked every Edit/Write
    from every worktree of the repo indefinitely). This command sweeps a
    project's state.json for exactly that shape ahead of a fleet campaign,
    rather than discovering each stale stamp as a mid-build denial.

    Never raises and never exits non-zero (C6) — this is run across
    eight-plus fleet projects in a loop during the Phase 106 campaign; one
    malformed state.json must not abort the sweep.
    """
    try:
        _clear_stale_stories_body(Path(project_dir), max_age_hours, apply)
    except Exception:
        # C6: no input may produce a non-zero exit or an uncaught traceback.
        pass


def _clear_stale_stories_body(
    project_path: Path, max_age_hours: "float | None", apply: bool
) -> None:
    """Body of ``clear-stale-stories``, isolated so the CLI wrapper's
    blanket ``except Exception`` (C6) never hides a bug in this from tests
    that call the body function directly."""
    cutoff = max_age_hours if max_age_hours is not None else STATE_STORY_MAX_AGE_HOURS
    companion_dir = project_path / ".companion"

    try:
        state = read_state(companion_dir)
    except Exception:
        state = {}
    if not isinstance(state, dict):
        state = {}

    keyed = state.get(CURRENT_STORIES_KEY)
    keyed = keyed if isinstance(keyed, dict) else {}

    stale_keyed_ids: list[str] = []
    for story_id, entry in keyed.items():
        if not entry_is_fresh(entry, max_age_hours=cutoff):
            stale_keyed_ids.append(story_id)
            set_at = entry.get("set_at") if isinstance(entry, dict) else None
            age = _format_age_hours(set_at)
            click.echo(f"STALE {story_id} set_at={set_at if set_at else '<none>'} age={age}h")

    legacy_stale_id: "str | None" = None
    if not keyed:
        legacy = state.get("current_story")
        if isinstance(legacy, dict):
            legacy_id = legacy.get("id")
            legacy_id = str(legacy_id).strip() if legacy_id else None
            if legacy_id and not entry_is_fresh(legacy, max_age_hours=cutoff):
                legacy_stale_id = legacy_id
                set_at = legacy.get("set_at")
                age = _format_age_hours(set_at)
                click.echo(
                    f"STALE {legacy_id} set_at={set_at if set_at else '<none>'} age={age}h"
                )

    if not apply:
        return

    # C3: prefer the scoped clear for every keyed entry — a concurrently-
    # building fresh story must keep its own scope enforcement.
    for story_id in stale_keyed_ids:
        clear_current_story(companion_dir, story_id)
        click.echo(f"CLEARED {story_id}")

    # C4: the legacy-only shape has no keyed entry to scope to, so the
    # unscoped clear-the-slate call is correct here precisely because there
    # is nothing else in the slate to protect.
    if legacy_stale_id is not None:
        clear_current_story(companion_dir, None)
        click.echo(f"CLEARED {legacy_stale_id}")


def _format_age_hours(set_at: "str | None") -> str:
    """Render *set_at*'s age in hours for the report line, tolerating a
    missing/unparseable stamp (C6)."""
    if not isinstance(set_at, str) or not set_at:
        return "?"
    try:
        parsed = datetime.fromisoformat(set_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age = (now - parsed).total_seconds() / 3600.0
        return f"{age:.1f}"
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# Story cost estimate (INFRA-135)
# ---------------------------------------------------------------------------


_COST_MIN_SAMPLE = 3


def _query_story_cost_samples(
    db_path: Path, rail: str, story_class: str
) -> tuple[list[int], str]:
    """Return ``(tokens_total_values, tier)`` using a waterfall query strategy.

    Tier 1 — specific (rail, story_class): if ≥ ``_COST_MIN_SAMPLE`` PASS rows.
    Tier 2 — all rails, same story_class: if Tier 1 insufficient.
    Tier 3 — all PASS rows (global): if Tier 2 insufficient.
    Tier 4 — ``"insufficient"`` if global < ``_COST_MIN_SAMPLE``.

    Returns a ``(rows, tier)`` tuple where ``tier`` is one of
    ``"rail"``, ``"all-rails"``, ``"global"``, or ``"insufficient"``.
    (INFRA-171)
    """
    import sqlite3

    if not db_path.exists():
        return [], "insufficient"

    def _q(conn: sqlite3.Connection, where: str, *params: object) -> list[int]:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT tokens_total
              FROM attempts
             WHERE {where}
               AND outcome = 'PASS'
               AND tokens_total IS NOT NULL
               AND tokens_total > 0
            """,
            params,
        )
        return [int(row[0]) for row in cur.fetchall()]

    conn = sqlite3.connect(str(db_path))
    try:
        # Tier 1: specific rail + story_class.
        rows = _q(conn, "rail = ? AND story_class = ?", rail, story_class)
        if len(rows) >= _COST_MIN_SAMPLE:
            return rows, "rail"

        # Tier 2: all rails, same story_class.
        rows = _q(conn, "story_class = ?", story_class)
        if len(rows) >= _COST_MIN_SAMPLE:
            return rows, "all-rails"

        # Tier 3: global — all PASS rows.
        rows = _q(conn, "1=1")
        if len(rows) >= _COST_MIN_SAMPLE:
            return rows, "global"

        return rows, "insufficient"
    finally:
        conn.close()


@flex_build.command("story-cost-estimate")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-135).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_story_cost_estimate(story_id: str, project_dir: str) -> None:
    """Print a one-line median PASS-token estimate for (rail, story_class).

    INFRA-321 § D2: a STORY-SPEND informational surface — captioned via
    ``track_label`` so it reads as retrospective cost, not headroom. It
    carries no threshold and no pause/`/clear` language; it is not a gate.
    """
    import statistics

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    story_path = _story_path(story_id, project_path)
    fm = _read_story_frontmatter(story_path) if story_path.exists() else {}
    rail = (fm.get("rail") or story_id.split("-", 1)[0]).strip()
    story_class = (fm.get("story_class") or "code").strip()

    db_path = resolve_effort_db_path(project_path)
    samples, tier = _query_story_cost_samples(db_path, rail, story_class)
    n = len(samples)
    label = track_label(TRACK_STORY_SPEND)

    if tier == "insufficient":
        click.echo(
            f"estimate ({label}): insufficient data ({n} PASS attempts on {rail}/{story_class})"
        )
        return

    median = int(statistics.median(samples))

    if tier == "rail":
        click.echo(
            f"estimate ({label}): {median} tokens (median of {n} PASS attempts on {rail}/{story_class})"
        )
    elif tier == "all-rails":
        click.echo(
            f"estimate ({label}): {median} tokens (median of {n} PASS attempts, all rails, story_class={story_class})"
        )
    else:  # global
        click.echo(
            f"estimate ({label}): {median} tokens (median of {n} PASS attempts, global)"
        )


@flex_build.command("set-context-tokens")
@click.option("--tokens", required=True, type=int, help="Token count from /context (must be > 0).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_set_context_tokens(tokens: int, project_dir: str) -> None:
    """Record the current ``/context`` token count into ``.companion/state.json``.

    Writes ``state["context_current_tokens"] = N`` and
    ``state["context_current_tokens_recorded_at"] = <ISO-8601>``.

    This is a manual override / debugging escape hatch. Under normal operation,
    ``post_tool_use.py`` writes ``context_current_tokens`` automatically after
    each Task/Agent completion by reading the JSONL transcript (INFRA-182).
    ``pre_tool_use.py`` reads this value to enforce the context budget gate.
    """
    if tokens <= 0:
        click.echo(
            f"set-context-tokens: --tokens must be > 0 (got {tokens})", err=True
        )
        sys.exit(1)

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    companion = project_path / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state_path = companion / "state.json"

    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except (json.JSONDecodeError, OSError):
            state = {}
    else:
        state = {}

    now_iso = datetime.now(timezone.utc).isoformat()

    # Scalar write — the sole gate token source for INFRA-182.
    state["context_current_tokens"] = tokens
    state["context_current_tokens_recorded_at"] = now_iso
    # INFRA-321 § C6/C7: this is one of the two live writers of the
    # provenance field — a manual operator override, not a measurement.
    state[CONTEXT_CURRENT_TOKENS_SOURCE_KEY] = "manual"

    _atomic_write_json(state_path, state)
    click.echo(f"context: recorded {tokens:,} tokens")


@flex_build.command("bump-context-tokens")
@click.option("--cost", required=True, type=int, help="Token cost to add (must be > 0).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_bump_context_tokens(cost: int, project_dir: str) -> None:
    """Add --cost to context_current_tokens in state.json (per-story accumulation).

    When ``context_current_tokens`` is absent or invalid, treats the base as 0
    and writes ``cost`` as the new value.  Resets ``context_current_tokens_recorded_at``
    on every successful write so the TTL clock restarts after each bump.

    Silent no-op (exit 0) when ``.companion/state.json`` is absent — consistent
    with ``set-context-tokens`` fail-open behaviour for non-pairmode projects.

    INFRA-245 decision (dormant-command review): this command has zero live
    callers in this project's own build loop — removed from ``CLAUDE.build.md``
    at BUILD-029/BUILD-030 (Phase 70-71) because its historical caller fed it
    subagent ``<usage>`` cost, which is a DP7 violation (``docs/architecture.md``
    § effort.db ≠ context-control invariant: subagent tokens never entered the
    orchestrator's own window, so summing them into ``context_current_tokens``
    inflates it with figures that were never really there). Kept rather than
    removed per INFRA-179's prior decision (older sibling-project
    ``CLAUDE.build.md`` files may still reference it; removal was explicitly
    deferred, not forgotten). If you are about to wire a new caller: feed this
    command ONLY a measured live-window delta (e.g. from
    ``context_budget.compute_context_tokens``), never a subagent cost/effort.db
    figure — doing so reintroduces the exact conflation this invariant exists
    to prevent.

    INFRA-321 § C7 (two-track vocabulary): ``--cost`` MUST be a measured
    ``TRACK_ORCHESTRATOR`` delta, never a ``TRACK_STORY_SPEND`` figure. This
    command stays dormant by design — § C1's ``user_turn_seq.record_user_turn``
    measured refresh (real JSONL reads, not an estimate) is the reason no
    caller is needed; this command's arithmetic and exit codes are unchanged.
    """
    if cost <= 0:
        click.echo(
            f"bump-context-tokens: --cost must be > 0 (got {cost})", err=True
        )
        sys.exit(1)

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    state_path = project_path / ".companion" / "state.json"

    if not state_path.exists():
        return  # non-pairmode project, fail-open

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (json.JSONDecodeError, OSError):
        state = {}

    existing = state.get("context_current_tokens")
    try:
        base = int(existing) if existing and int(existing) > 0 else 0
    except (TypeError, ValueError):
        base = 0

    state["context_current_tokens"] = base + cost
    state["context_current_tokens_recorded_at"] = datetime.now(timezone.utc).isoformat()
    # INFRA-321 § C6/C7: manual writer — see the docstring's cost-source rule
    # (a measured orchestrator-window delta, never a story-spend figure).
    state[CONTEXT_CURRENT_TOKENS_SOURCE_KEY] = "manual"
    _atomic_write_json(state_path, state)
    click.echo(f"context: bumped by {cost:,} → total {state['context_current_tokens']:,} tokens")


# ---------------------------------------------------------------------------
# check-story-scope rule 3 — body-named paths (INFRA-320 § C1)
# ---------------------------------------------------------------------------

_BODY_SECTIONS_FOR_SCOPE_RE = re.compile(
    r"^##\s+(?:Ensures|Instructions)\s*\n(.*?)(?=^##|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_INLINE_CODE_FOR_SCOPE_RE = re.compile(r"`([^`]+)`")
_CODE_FENCE_FOR_SCOPE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_PATH_TOKEN_FOR_SCOPE_RE = re.compile(
    r"[A-Za-z0-9_.\-/]+\.(?:py|md|json|j2|ts|tsx|js|jsx|toml|yaml|yml)"
)


def check_story_scope_body_named_paths(story_path: Path, project_path: Path) -> list[str]:
    """Pure warning function behind check-story-scope's rule 3 (INFRA-320
    § C1): extract repo-relative path tokens named inside inline code or
    fenced code in the story's ``## Ensures``/``## Instructions`` sections,
    keep only those that exist in the working tree (a spec may legitimately
    name a file it is about to create — warning on those would be noise),
    and return one message per token absent from the declared scope
    (``primary_files ∪ touches ∪ standing_paths_for(...)``, reusing
    `scope_guard.standing_paths_for` — § C2 — so a path added to
    `STANDING_SURFACES` stops producing spec-time warnings in the same
    commit that stops producing deny decisions).

    Pure and total: any read/parse failure returns ``[]`` rather than
    raising. Both `cmd_check_story_scope` (rule 3) and
    `spec_preflight.run_preflight` (§ C4) call this directly — never a CLI
    shell-out from inside another Python process.
    """
    try:
        text = story_path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        fm = _read_story_frontmatter(story_path)
    except Exception:  # noqa: BLE001
        return []

    story_id = str(fm.get("id") or story_path.stem)
    primary_files = fm.get("primary_files")
    touches = fm.get("touches")
    primary_files = primary_files if isinstance(primary_files, list) else []
    touches = touches if isinstance(touches, list) else []

    def _norm(s: object) -> str:
        return str(s).replace("\\", "/").lstrip("./")

    phase_raw = fm.get("phase")
    story_phase = (
        phase_raw.strip() if isinstance(phase_raw, str) and phase_raw.strip() else None
    )

    declared: set[str] = {_norm(p) for p in list(primary_files) + list(touches)}
    declared |= {_norm(p) for p in standing_paths_for(story_id, story_phase)}

    body = "\n".join(_BODY_SECTIONS_FOR_SCOPE_RE.findall(text))
    if not body.strip():
        return []

    tokens: list[str] = []
    for m in _INLINE_CODE_FOR_SCOPE_RE.finditer(body):
        tokens.extend(
            t for t in _PATH_TOKEN_FOR_SCOPE_RE.findall(m.group(1)) if "/" in t
        )
    for fence_m in _CODE_FENCE_FOR_SCOPE_RE.finditer(body):
        tokens.extend(
            t for t in _PATH_TOKEN_FOR_SCOPE_RE.findall(fence_m.group(1)) if "/" in t
        )

    warnings: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        norm = _norm(tok)
        if norm in seen:
            continue
        seen.add(norm)
        if norm in declared:
            continue
        if not (project_path / norm).exists():
            continue
        warnings.append(
            f"{norm} is named in Ensures/Instructions but is not in declared "
            "scope (primary_files/touches/standing)"
        )
    return warnings


@flex_build.command("check-story-scope")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_story_scope(story_id: str, project_dir: str) -> None:
    """Check declared primary_files/touches for common co-dependency scope misses.

    Applies two heuristics:

    1. Test co-location — a skills/pairmode/scripts/*.py file should have its
       sibling test declared.
    2. Template/live-rendered pair — a *.j2 template should have its rendered
       live counterpart declared.

    Always exits 0.  Prints nothing when no warnings are found.
    """
    # Validate story_id format.
    if not _STORY_ID_RE.match(story_id):
        click.echo(
            f"check-story-scope: invalid story_id format: {story_id!r}", err=True
        )
        sys.exit(1)

    project_path = Path(project_dir).resolve()
    story_path = _story_path(story_id, project_path)

    if not story_path.exists():
        click.echo(
            f"check-story-scope: story spec not found: {story_path}", err=True
        )
        sys.exit(1)

    try:
        fm = _read_story_frontmatter(story_path)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"check-story-scope: failed to parse frontmatter: {exc}", err=True)
        sys.exit(1)

    primary_files: list[str] = fm.get("primary_files") or []
    touches: list[str] = fm.get("touches") or []

    def _norm(s: str) -> str:
        return s.replace("\\", "/").lstrip("./")

    # Build the declared scope set (normalised).
    scope_set: set[str] = set()
    for p in primary_files + touches:
        scope_set.add(_norm(p))

    # Rule 1 — Test co-location.
    for p in primary_files + touches:
        np = _norm(p)
        # Match skills/pairmode/scripts/<name>.py where <name> is not test_* / __init__
        parts = np.split("/")
        if (
            len(parts) == 4
            and parts[0] == "skills"
            and parts[1] == "pairmode"
            and parts[2] == "scripts"
            and parts[3].endswith(".py")
        ):
            basename = parts[3]
            if basename.startswith("test_") or basename == "__init__.py":
                continue
            stem = basename[:-3]  # strip .py
            expected_test = f"tests/pairmode/test_{stem}.py"
            # Check that the test file exists on disk.
            if (project_path / expected_test).exists():
                if _norm(expected_test) not in scope_set:
                    click.echo(
                        f"SCOPE WARNING: {story_id}: scripts/{basename} declared but "
                        f"tests/pairmode/test_{stem}.py not in primary_files/touches"
                    )

    # Rule 2 — Template / live-rendered pair.
    for p in primary_files + touches:
        np = _norm(p)
        # Match skills/pairmode/templates/**/*.j2
        if not (np.startswith("skills/pairmode/templates/") and np.endswith(".j2")):
            continue
        bare = Path(np).name[:-3]  # strip .j2
        # Candidate locations in order:
        # 1. bare at project root
        # 2. skills/pairmode/<bare>
        candidates = [bare, f"skills/pairmode/{bare}"]
        for candidate in candidates:
            if (project_path / candidate).exists():
                if _norm(candidate) not in scope_set:
                    click.echo(
                        f"SCOPE WARNING: {story_id}: {np} declared but "
                        f"{candidate} not in primary_files/touches"
                    )
                # Only emit for the first matching candidate.
                break

    # Rule 3 — body-named paths (INFRA-320 § C1): a repo path token named in
    # the story's own Ensures/Instructions, that exists on disk, but is
    # absent from the declared scope (primary_files ∪ touches ∪ standing).
    for msg in check_story_scope_body_named_paths(story_path, project_path):
        click.echo(f"SCOPE WARNING: {story_id}: {msg}")

    # Rule: architecture.md prompt for code stories with no docs/ touches.
    story_class = fm.get("story_class") or "code"
    if story_class == "code":
        all_files = list(primary_files) + list(touches)
        has_docs_path = any(
            str(p).startswith("docs/") for p in all_files
        )
        if not has_docs_path:
            click.echo(
                "Scope hint: if this story affects documented architecture, "
                "add docs/architecture.md to touches."
            )

    # Scope budget warning.
    total_declared = len(list(primary_files)) + len(list(touches))
    if total_declared > 8:
        click.echo(
            f"Scope budget: story declares {total_declared} files — "
            f"consider splitting if stories are independently reviewable."
        )

    sys.exit(0)


@flex_build.command("spec-preflight")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-190).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_spec_preflight(story_id: str, project_dir: str) -> None:
    """Scan a story's body sections for unverifiable routes and constants.

    Exit 0 means the scan ran (clean or with warnings), including the
    well-formed-but-missing story file case. Exit 2 means the *story_id*
    itself is malformed or resolves outside the stories tree — a scan that
    cannot locate its subject must not report as clean.
    """
    import spec_preflight as _sp  # noqa: PLC0415

    project_path = Path(project_dir).resolve()
    try:
        story_path = story_path_checked(story_id, project_path)
    except ValueError as exc:
        click.echo(f"spec-preflight: {exc}", err=True)
        sys.exit(2)

    if not story_path.exists():
        click.echo(f"spec-preflight: story file not found: {story_path}", err=True)
        sys.exit(0)

    for w in _sp.run_preflight(story_path, project_path):
        click.echo(w)


# ---------------------------------------------------------------------------
# Pre-flight gate CLIs (BUILD-034)
# ---------------------------------------------------------------------------

_STUB_DELEGATION_RE = re.compile(
    r"see phase doc|see docs/phases/|see phase-",
    re.IGNORECASE,
)
_STUB_ACCEPTANCE_RE = re.compile(
    r"^##\s+(?:ensures|acceptance criterion|acceptance criteria)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Fence opener/closer: up to 3 leading spaces, then a run of >= 3 backticks
# or >= 3 tildes (CER-076 code-region mask).
_FENCE_MARKER_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
# Inline code span: a run of backticks closed by an equal-length run on the
# same line (pragmatic, not CommonMark-exact).
_INLINE_CODE_RE = re.compile(r"(`+)([^\n]*?)\1")


def _mask_code_regions(text: str) -> str:
    """Return *text* with code regions blanked to spaces, length preserved.

    Every character inside a fenced code block (including the fence marker
    lines themselves) or an inline code span is replaced by a space;
    newlines are preserved verbatim. Because the result has exactly the
    same length as the input, regex match offsets against the masked text
    index the original text directly (CER-076: the stub gate searches the
    masked body but reports the original line).

    Handles: triple-backtick fences with or without an info string; tilde
    (``~~~``) fences; fence openers indented up to three spaces; an
    unterminated fence (masked to end of text); and inline spans delimited
    by equal-length backtick runs on one line. This is a pragmatic two-pass
    scanner, not a CommonMark implementation. Pure — no I/O, no state.

    The gate must never crash on a malformed story: if the mask ever fails
    to preserve length, the original text is returned unchanged (search
    falls back to the unmasked body).
    """

    def _blank(line: str) -> str:
        # Replace every non-newline character with a space; keep the line
        # ending (\n or \r\n) verbatim.
        stripped = line.rstrip("\r\n")
        return " " * len(stripped) + line[len(stripped):]

    # Pass 1 — fenced code blocks.
    masked_lines: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in text.splitlines(keepends=True):
        m = _FENCE_MARKER_RE.match(line)
        if not in_fence:
            if m:
                marker = m.group(1)
                in_fence = True
                fence_char = marker[0]
                fence_len = len(marker)
                masked_lines.append(_blank(line))
            else:
                masked_lines.append(line)
        else:
            # Inside a fence: everything is blanked, including the closer.
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                in_fence = False
            masked_lines.append(_blank(line))
    masked = "".join(masked_lines)

    # Pass 2 — inline code spans (applied to the fence-masked text only;
    # fence content is already spaces, so no backticks remain there).
    masked = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), masked)

    if len(masked) != len(text):
        # Length-preservation guard: never crash, never mis-offset — search
        # the unmasked body instead.
        return text
    return masked

_SCHEMA_MGMT_KEYWORDS = re.compile(
    r"\b(?:management|ui|crud|admin|route|page|command|dashboard)\b",
    re.IGNORECASE,
)
_SCHEMA_EXCEPTION_RE = re.compile(
    r"append-only|junction table|cron-output cache",
    re.IGNORECASE,
)

_AUTH_CLASSIFICATION_RE = re.compile(
    r"^\*\*Classification:\*\*",
    re.MULTILINE,
)


def _story_body(text: str) -> str:
    """Return the body of a story file (after the closing --- of frontmatter)."""
    lines = text.splitlines(keepends=True)
    # Find the second '---' line
    dashes_found = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            dashes_found += 1
            if dashes_found == 2:
                return "".join(lines[i + 1:])
    return text


def _find_phase_file(phase_id: str, project_dir: Path) -> Path | None:
    """Return the path to the phase file for *phase_id*, or None if not found."""
    candidate = project_dir / "docs" / "phases" / f"phase-{phase_id}.md"
    if candidate.exists():
        return candidate
    return None


def _parse_phase_stories_with_status(phase_text: str) -> list[tuple[str, str, str]]:
    """Parse the ## Stories table; return [(story_id, title, status)]."""
    stories_section_re = re.compile(r"^##\s+Stories\s*$", re.MULTILINE)
    m = stories_section_re.search(phase_text)
    if not m:
        return []

    section = phase_text[m.end():]
    rows: list[tuple[str, str, str]] = []
    header_seen = False
    separator_seen = False
    in_table = False

    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        if not stripped.startswith("|"):
            if in_table and stripped:
                break
            continue
        in_table = True
        # split rationale: `table_utils.split_table_row`
        parts = [p.strip() for p in split_table_row(stripped)]
        if len(parts) < 4:
            continue
        if not header_seen:
            header_seen = True
            continue
        if not separator_seen:
            separator_seen = True
            continue
        story_id_cell = parts[1].strip()
        title_cell = parts[2].strip() if len(parts) > 2 else ""
        status_cell = parts[3].strip().lower() if len(parts) > 3 else ""
        # Strip Markdown link syntax
        story_id_cell = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", story_id_cell)
        if story_id_cell:
            rows.append((story_id_cell, title_cell, status_cell))
    return rows


def check_stub_gate(story_id: str, project_dir: Path) -> dict:
    """Return a structured gate result for the stub check.

    Returns a dict with keys:
      - ``ok`` (bool): True when the story passes, False when blocked.
      - ``missing`` (bool): True when the story file does not exist.
      - ``reasons`` (list[str]): Human-readable block reasons (empty on pass).

    Pure read — no state writes.

    Extracted from ``cmd_check_stub`` as a module-level helper so that
    ``next_action.infer_position`` can compose it as a library call (RESOLVER-002).
    """
    story_path = _story_path(story_id, project_dir)

    if not story_path.exists():
        return {"ok": False, "missing": True, "reasons": [f"story file not found: {story_path}"]}

    text = story_path.read_text(encoding="utf-8")
    body = _story_body(text)

    reasons: list[str] = []

    # Check for delegation language in the body. The search runs over a
    # length-preserving mask of the body with fenced code blocks and inline
    # code spans blanked (CER-076: quoted text is data, not delegation), so
    # the match offsets below index the ORIGINAL body directly and the
    # reported line shows real text.
    m = _STUB_DELEGATION_RE.search(_mask_code_regions(body))
    if m:
        line_start = body.rfind("\n", 0, m.start()) + 1
        line_end = body.find("\n", m.end())
        matched_line = body[line_start: line_end if line_end != -1 else len(body)].strip()
        if len(matched_line) > 80:
            matched_line = matched_line[:80] + "..."
        reasons.append(f'Delegation language found: "{matched_line}"')

    # Check for acceptance surface.
    if not _STUB_ACCEPTANCE_RE.search(text):
        reasons.append(
            "No acceptance surface found (missing ## Ensures, ## Acceptance criterion, "
            "or ## Acceptance criteria)."
        )

    return {"ok": len(reasons) == 0, "missing": False, "reasons": reasons}


@flex_build.command("check-stub")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_stub(story_id: str, project_dir: str) -> None:
    """Check a single story file for stub indicators (delegation language or missing acceptance surface).

    Exits 0 silently on a clean story.
    Exits 1 with a structured block when the story is a stub.
    Exits 2 with a clear error message when the story file cannot be found.
    """
    project_path = Path(project_dir).resolve()
    result = check_stub_gate(story_id, project_path)

    if result["missing"]:
        click.echo(
            f"check-stub: story file not found: {_story_path(story_id, project_path)}", err=True
        )
        sys.exit(2)

    if not result["ok"]:
        click.echo(f"PRE-STORY BLOCK — Story [{story_id}] is a stub.")
        for reason in result["reasons"]:
            click.echo(reason)
        click.echo("Action required: fill in the story spec before building.")
        click.echo('When resolved, say: "Continue building"')
        sys.exit(1)

    # Silent pass.
    sys.exit(0)


def check_schema_gate_result(story_id: str, project_dir: Path) -> dict:
    """Return a structured gate result for the schema-introduces check.

    Returns a dict with keys:
      - ``ok`` (bool): True when the story passes, False when blocked.
      - ``missing`` (bool): True when the story file does not exist.
      - ``blocked_reason`` (str): Human-readable reason when blocked (empty on pass).

    Pure read — no state writes.

    Extracted from ``cmd_check_schema_gate`` as a module-level helper so that
    ``next_action.infer_position`` can compose it as a library call (RESOLVER-002).
    """
    story_path = _story_path(story_id, project_dir)

    if not story_path.exists():
        return {"ok": False, "missing": True, "blocked_reason": f"story file not found: {story_path}"}

    text = story_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text) or {}

    schema_introduces_raw = fm.get("schema_introduces")
    # _parse_frontmatter returns strings; coerce "true"/"false" as booleans.
    if isinstance(schema_introduces_raw, bool):
        schema_introduces = schema_introduces_raw
    elif isinstance(schema_introduces_raw, str):
        schema_introduces = schema_introduces_raw.lower() == "true"
    else:
        schema_introduces = False

    if not schema_introduces:
        return {"ok": True, "missing": False, "blocked_reason": ""}

    # schema_introduces is True — look for management surface or exception phrase.
    body = _story_body(text)

    # Check for exception phrase in story body.
    if _SCHEMA_EXCEPTION_RE.search(body):
        return {"ok": True, "missing": False, "blocked_reason": ""}

    # Load phase manifest to check remaining unbuilt stories.
    phase_id = fm.get("phase")
    if phase_id is not None:
        phase_id_str = str(phase_id).strip()
        phase_file = _find_phase_file(phase_id_str, project_dir)
        if phase_file is not None:
            phase_text = phase_file.read_text(encoding="utf-8")
            phase_stories = _parse_phase_stories_with_status(phase_text)
            for sid, title, status in phase_stories:
                if status == "complete":
                    continue
                if _SCHEMA_MGMT_KEYWORDS.search(title):
                    return {"ok": True, "missing": False, "blocked_reason": ""}
                # Also check the story file's title if we can read it.
                candidate_path = _story_path(sid, project_dir)
                if candidate_path.exists():
                    candidate_fm = _parse_frontmatter(
                        candidate_path.read_text(encoding="utf-8")
                    ) or {}
                    candidate_title = candidate_fm.get("title") or ""
                    if _SCHEMA_MGMT_KEYWORDS.search(candidate_title):
                        return {"ok": True, "missing": False, "blocked_reason": ""}

    return {
        "ok": False,
        "missing": False,
        "blocked_reason": (
            f"Story [{story_id}] introduces a schema object with no management surface."
        ),
    }


@flex_build.command("check-schema-gate")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_schema_gate(story_id: str, project_dir: str) -> None:
    """Check whether a schema-introducing story has a management surface in the phase.

    Exits 0 silently when schema_introduces is absent/false, or when a management
    surface story or documented exception is present.
    Exits 1 with a structured block when schema_introduces is true and neither
    condition is satisfied.
    Exits 2 with a clear error message when the story file cannot be found.
    """
    project_path = Path(project_dir).resolve()
    result = check_schema_gate_result(story_id, project_path)

    if result["missing"]:
        click.echo(
            f"check-schema-gate: story file not found: {_story_path(story_id, project_path)}", err=True
        )
        sys.exit(2)

    if not result["ok"]:
        click.echo(
            f"PRE-STORY BLOCK — Story [{story_id}] introduces a schema object with no management surface."
        )
        click.echo("Options:")
        click.echo("1. Add a management UI story to the phase spec before building.")
        click.echo(
            "2. Note an explicit exception in the story spec (append-only, junction table,"
        )
        click.echo("   or cron-output cache) if one of those categories applies.")
        sys.exit(1)

    sys.exit(0)


def check_auth_gate_result(story_id: str, project_dir: Path) -> dict:
    """Return a structured gate result for the auth-gated check.

    Returns a dict with keys:
      - ``ok`` (bool): True when the story passes, False when blocked.
      - ``missing`` (bool): True when the story file does not exist.
      - ``blocked_reason`` (str): Human-readable reason when blocked (empty on pass).

    Pure read — no state writes.

    Extracted from ``cmd_check_auth_gate`` as a module-level helper so that
    ``next_action.infer_position`` can compose it as a library call (RESOLVER-002).
    """
    story_path = _story_path(story_id, project_dir)

    if not story_path.exists():
        return {"ok": False, "missing": True, "blocked_reason": f"story file not found: {story_path}"}

    text = story_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text) or {}

    auth_gated_raw = fm.get("auth_gated")
    # _parse_frontmatter returns strings; coerce "true"/"false" as booleans.
    if isinstance(auth_gated_raw, bool):
        auth_gated = auth_gated_raw
    elif isinstance(auth_gated_raw, str):
        auth_gated = auth_gated_raw.lower() == "true"
    else:
        auth_gated = False

    if not auth_gated:
        return {"ok": True, "missing": False, "blocked_reason": ""}

    # auth_gated is True — check docs/architecture.md for **Classification:** line.
    arch_path = project_dir / "docs" / "architecture.md"
    if arch_path.exists():
        arch_text = arch_path.read_text(encoding="utf-8")
        if _AUTH_CLASSIFICATION_RE.search(arch_text):
            return {"ok": True, "missing": False, "blocked_reason": ""}

    return {
        "ok": False,
        "missing": False,
        "blocked_reason": (
            f"Story [{story_id}] is auth-gated but no classification is recorded in "
            "docs/architecture.md."
        ),
    }


@flex_build.command("check-auth-gate")
@click.argument("story_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_auth_gate(story_id: str, project_dir: str) -> None:
    """Check whether an auth-gated story has a recorded auth model classification.

    Exits 0 silently when auth_gated is absent/false, or when docs/architecture.md
    contains a **Classification:** line.
    Exits 1 with a structured block when auth_gated is true and no classification
    is recorded.
    Exits 2 with a clear error message when the story file cannot be found.
    """
    project_path = Path(project_dir).resolve()
    result = check_auth_gate_result(story_id, project_path)

    if result["missing"]:
        click.echo(
            f"check-auth-gate: story file not found: {_story_path(story_id, project_path)}", err=True
        )
        sys.exit(2)

    if not result["ok"]:
        click.echo(
            f"AUTH GATE — Story [{story_id}] is auth-gated but no classification is recorded."
        )
        click.echo(
            "Load ~/.claude/policies/auth-coexistence.md and classify the auth model"
        )
        click.echo(
            "(RBAC / ABAC / both), then record it in docs/architecture.md before building."
        )
        sys.exit(1)

    sys.exit(0)


@flex_build.command("transition-era")
@click.option("--name", default=None, help="New era name (required in --yes mode).")
@click.option("--intent", default="", help="Strategic intent for the new era.")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip interactive prompts; --name must be provided.",
)
def cmd_transition_era(
    name: str | None,
    intent: str,
    project_dir: str,
    yes: bool,
) -> None:
    """Formally close the current active era and open the next one."""
    from era_transition import era_transition_cli  # noqa: PLC0415

    sys.exit(
        era_transition_cli(
            project_dir=project_dir,
            name=name,
            intent=intent,
            yes=yes,
        )
    )


@flex_build.command("next-action")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the canonical JSON action object instead of a human-readable line.",
)
@click.option(
    "--warning",
    "warnings",
    multiple=True,
    help="Advisory signal to surface in meta.warnings[] (e.g. guardrail-fired). May be repeated.",
)
def cmd_next_action(project_dir: str, as_json: bool, warnings: tuple) -> None:
    """Resolve the next build-loop action from durable state.

    Pure-read: no file is written.  Advisory only — not wired into the live
    CLAUDE.build.md loop (DP7).

    Prints a human-readable summary by default; use --json to emit the
    canonical action object that round-trips through validate_action.
    """
    from next_action import infer_position, resolve_next_action  # noqa: PLC0415

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)

    warnings_list = list(warnings) if warnings else None
    try:
        position = infer_position(project_path)
    except AmbiguousActivePhaseError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)
    action = resolve_next_action(position, warnings=warnings_list)

    if as_json:
        click.echo(json.dumps(action))
    else:
        # Human-readable summary line.
        action_val = action["action"]
        scalar = action.get("scalar") or ""
        reason = action.get("reason") or ""
        model = action.get("model")
        parts = [f"action: {action_val}"]
        if scalar:
            parts.append(f"scalar: {scalar}")
        if reason:
            parts.append(f"reason: {reason}")
        if model:
            parts.append(f"model: {model}")
        click.echo("  ".join(parts))


# ---------------------------------------------------------------------------
# OBS-001 helpers — resolver state model
# ---------------------------------------------------------------------------

def _query_effort_by_role(db_path: Path) -> dict:
    """Per-agent-role effort rollup from effort.db (OBS-001).

    Returns a dict keyed by agent_role with count and median_tokens.
    Returns {} when the db is absent or unreadable.
    """
    import sqlite3 as _sqlite3
    import statistics as _stats

    if not db_path.exists():
        return {}

    try:
        conn = _sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT agent_role, tokens_total
                FROM attempts
                WHERE tokens_total IS NOT NULL AND tokens_total > 0
                ORDER BY agent_role
                """
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return {}

    by_role: dict[str, list[int]] = {}
    for role, tokens in rows:
        by_role.setdefault(role, []).append(int(tokens))

    return {
        role: {
            "count": len(vals),
            "median_tokens": int(_stats.median(vals)) if vals else None,
        }
        for role, vals in by_role.items()
    }


def _query_effort_by_story_ids(db_path: Path, story_ids: list[str]) -> dict:
    """Effort rollup restricted to attempts whose ``story_id`` is in *story_ids*
    (INFRA-256).

    Counts are row counts (spawns), not ``attempt_number`` values — see
    ``docs/architecture.md`` § Effort tracking for why row-count is the honest
    measure here (sibling story INFRA-257 addresses ``attempt_number``
    correctness separately).

    Returns a dict with two keys:
      - ``by_role``: same shape as ``_query_effort_by_role`` — ``{role: {"count":
        int, "median_tokens": int | None}}`` — restricted to the given story IDs.
      - ``by_story``: ``{story_id: {role: {"count": int, "median_tokens": int |
        None}}}``.

    Returns ``{"by_role": {}, "by_story": {}}`` (never raises) when the db is
    absent, unreadable, or *story_ids* is empty — matching
    ``_query_effort_by_role``'s never-raise contract. Story IDs are bound as
    SQL parameters; never interpolated into the query text.
    """
    import sqlite3 as _sqlite3
    import statistics as _stats

    empty_result = {"by_role": {}, "by_story": {}}

    if not story_ids or not db_path.exists():
        return empty_result

    placeholders = ", ".join("?" for _ in story_ids)
    try:
        conn = _sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT story_id, agent_role, tokens_total
                FROM attempts
                WHERE tokens_total IS NOT NULL AND tokens_total > 0
                  AND story_id IN ({placeholders})
                ORDER BY story_id, agent_role
                """,
                list(story_ids),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return empty_result

    by_role: dict[str, list[int]] = {}
    by_story_role: dict[str, dict[str, list[int]]] = {}
    for story_id, role, tokens in rows:
        tokens_int = int(tokens)
        by_role.setdefault(role, []).append(tokens_int)
        by_story_role.setdefault(story_id, {}).setdefault(role, []).append(tokens_int)

    def _summarize(vals: list[int]) -> dict:
        return {
            "count": len(vals),
            "median_tokens": int(_stats.median(vals)) if vals else None,
        }

    return {
        "by_role": {role: _summarize(vals) for role, vals in by_role.items()},
        "by_story": {
            story_id: {role: _summarize(vals) for role, vals in role_map.items()}
            for story_id, role_map in by_story_role.items()
        },
    }


def _query_pending_by_story_ids(db_path: Path, story_ids: list[str]) -> "dict[str, int]":
    """Count pending (unreconciled) attempt rows per story (INFRA-287, CER-101).

    Returns ``{story_id: pending_row_count}`` for rows whose ``tokens_total
    IS NULL OR outcome IS NULL`` — the same pendingness definition
    ``effort_db.pending_reconcilable`` sweeps on — restricted to
    *story_ids*. Deliberately **not** built on ``effort_db.pending_reconcilable``:
    that query applies an age cutoff and row limits that are right for a
    bounded hook-path sweep and wrong for a report that must count *every*
    pending row in the phase.

    Returns ``{}`` (never raises) when the db is absent, unreadable, or
    *story_ids* is empty — the same contract as ``_query_effort_by_story_ids``
    above. Story IDs are bound as SQL parameters; never interpolated.
    """
    import sqlite3 as _sqlite3

    if not story_ids or not db_path.exists():
        return {}

    placeholders = ", ".join("?" for _ in story_ids)
    try:
        conn = _sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT story_id, COUNT(*)
                FROM attempts
                WHERE (tokens_total IS NULL OR outcome IS NULL)
                  AND story_id IN ({placeholders})
                GROUP BY story_id
                """,
                list(story_ids),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return {}

    return {str(story_id): int(count) for story_id, count in rows}


def _format_role_rollup_lines(by_role: dict) -> list[str]:
    """Render ``{role: {"count": int, "median_tokens": int | None}}`` as the
    printed ``<role>: <n> attempt(s)[, median <n> tokens]`` lines shared by the
    phase-scoped and lifetime checkpoint-report sections (INFRA-256).
    """
    lines: list[str] = []
    for role in sorted(by_role):
        stats = by_role[role]
        median = stats.get("median_tokens")
        count = stats.get("count", 0)
        if median is not None:
            lines.append(f"  {role}: {count} attempt(s), median {median:,} tokens")
        else:
            lines.append(f"  {role}: {count} attempt(s)")
    return lines


def _build_resolver_index(project_dir: Path) -> list:
    """Build the resolver-owned phase index from docs/phases/index.md (OBS-001).

    Deferred and backlog phases are reported as inactive (CER-056 rule:
    deferred/backlog phases must not be treated as active work).
    """
    index_path = project_dir / "docs" / "phases" / "index.md"
    if not index_path.exists():
        return []

    try:
        index_text = index_path.read_text(encoding="utf-8")
    except OSError:
        return []

    phase_rows = _parse_index_phases(index_text)

    result = []
    for phase_ref, status in phase_rows:
        active = status not in ("complete", "deferred", "backlog")
        result.append({
            "phase_ref": phase_ref,
            "status": status,
            "active": active,
        })
    return result


@flex_build.command("resolver-state")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_resolver_state(project_dir: str) -> None:
    """Emit the pure-read resolver state model as JSON (OBS-001).

    Output contains:
      action     — the current next-action dict
      position   — the infer_position Position dict
      effort_by_role — per-agent-role effort rollup from effort.db
      index      — phase index (deferred/backlog reported as inactive, CER-056)

    Pure-read: no file is written.
    """
    from next_action import infer_position, resolve_next_action  # noqa: PLC0415

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)

    try:
        position = infer_position(project_path)
    except AmbiguousActivePhaseError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)
    action = resolve_next_action(position)

    # Serialize position: convert Path objects to strings for JSON.
    serialized_position: dict = {}
    for k, v in position.items():
        if isinstance(v, Path):
            serialized_position[k] = str(v)
        else:
            serialized_position[k] = v

    db_path = project_path / ".companion" / "effort.db"
    effort_by_role = _query_effort_by_role(db_path)
    index = _build_resolver_index(project_path)

    doc = {
        "schema_version": 1,
        "action": action,
        "position": serialized_position,
        "effort_by_role": effort_by_role,
        "index": index,
    }
    click.echo(json.dumps(doc))


# ---------------------------------------------------------------------------
# record-checkpoint-step (RESOLVER-012, phase-keyed per INFRA-283/CER-095.4)
# ---------------------------------------------------------------------------

# Top-level state.json key holding the phase-keyed checkpoint-step record —
# one completed-step list per in-flight phase, so two phases checkpointing
# under one orchestrator cannot clobber each other's progress (CER-095.4).
_CHECKPOINT_STEPS_KEY = "checkpoint_steps"


def _read_checkpoint_steps(state: dict) -> "dict[str, list[str]]":
    """Return the phase-key -> completed-step-list view of *state*.

    Pure: takes the already-loaded state dict, performs no file I/O and no
    writes on any path — including when it derives the keyed view from a
    legacy flat file (INFRA-283 assertion 2).

    Two shapes are normalised:

    - keyed: ``state["checkpoint_steps"]`` is a dict — kept as-is, but only
      string keys whose value is a list survive, and each list is filtered
      to its ``str`` members.
    - legacy: the keyed key is absent or not a dict — derived from the flat
      ``state["checkpoint_step"]`` / ``state["checkpoint_phase"]`` pair,
      under the stamp when it is a non-empty string, else under the empty
      key ``""``. Returns ``{}`` when the flat list is absent, empty, or not
      a list.
    """
    steps_raw = state.get(_CHECKPOINT_STEPS_KEY)
    if isinstance(steps_raw, dict):
        result: dict[str, list[str]] = {}
        for key, value in steps_raw.items():
            if not isinstance(key, str) or not isinstance(value, list):
                continue
            result[key] = [item for item in value if isinstance(item, str)]
        return result

    # Legacy flat shape.
    flat = state.get("checkpoint_step")
    if not isinstance(flat, list) or not flat:
        return {}
    stamp = state.get("checkpoint_phase")
    key = stamp if isinstance(stamp, str) and stamp != "" else ""
    return {key: [item for item in flat if isinstance(item, str)]}


def _record_checkpoint_step(
    step_id: str, project_dir: Path, phase_key: "str | None" = None
) -> int:
    """Atomically append *step_id* to the phase-keyed checkpoint-step record.

    Returns 0 on success or when step_id is already present for the
    resolved phase key (idempotent, per-key — INFRA-283 assertion 5).
    Returns 1 when step_id is not in _CHECKPOINT_SEQUENCE.
    Returns 2 when the phase key cannot be resolved unambiguously — see the
    precedence chain below (CER-077). No write to either ``state.json`` or
    ``docs/phases/index.md`` occurs on a 2-exit path; every validation and
    ambiguity check happens before the atomic state write and before
    ``_mark_phase_complete_in_index``.

    Storage shape (INFRA-283, CER-095.4). Completed steps are stored in
    ``state.json["checkpoint_steps"]``, a ``dict[phase_key, list[step_id]]``
    — one entry per in-flight phase, so two phases checkpointing
    concurrently under one orchestrator cannot silently record one
    another's progress or wipe one another's list. ``state["checkpoint_step"]``
    and ``state["checkpoint_phase"]`` survive as a **derived mirror**, written
    on every call but never read to decide what to append — they exist only
    for readers outside this fix's scope
    (``skills/observability/api/src/readers/resolverState.ts``,
    ``skills/observability/ui/src/api/client.ts``). A legacy-shape
    ``state.json`` (no keyed record yet) is read correctly via
    ``_read_checkpoint_steps`` and upgraded to the keyed shape on the next
    successful write — there is no migration command and no bootstrap
    change.

    Completing the terminal step (``checkpoint-tag``) also marks the
    resolved phase's row ``complete`` in ``docs/phases/index.md``, via
    ``_mark_phase_complete_in_index`` (INFRA-239). This happens in the same
    CLI call as the ``checkpoint_step`` reset — the orchestrator no longer
    needs to remember to invoke ``mark-phase-complete`` separately. Without
    this, the phase's index row stays non-``complete``, so the next
    ``next-action`` resolution re-selects the same phase as active; combined
    with the ``checkpoint_step`` reset below, that re-emits
    ``checkpoint-security`` for a phase that was just tagged (INFRA-239
    regression). The terminal step now clears only its own key from the
    keyed record (``steps.pop(effective_key, None)``) — a sibling phase's
    mid-sequence progress is untouched (INFRA-283 assertion 7).

    Phase-key resolution precedence (CER-077 — INFRA-265). An explicit
    ``--phase-key`` carries operator intent; the ``state.json`` stamp was
    recorded by a prior call in this same checkpoint sequence while that
    phase was provably active; re-derivation via ``resolve_current_phase`` is
    a guess and is only trusted when the index yields exactly one candidate.
    Disagreeing sources are an error, not a choice — picking either one when
    two disagree is the CER-077 failure mode wearing a different hat:

      1. ``phase_key`` when given (validated against the index first);
      2. otherwise ``state.json["checkpoint_phase"]`` when non-empty;
      3. otherwise the sole candidate from ``_active_phase_candidates`` — for
         the terminal step, more than one candidate is a loud error (no
         guessing which phase is being closed); for a non-terminal step it is
         only a warning (nothing irreversible happens yet, and the terminal
         step will demand the key anyway), and the stamp is left ``""`` (the
         documented INFRA-260 backward-compatible value).

    Note (INFRA-283 instruction 16 — accepted limitation): the read-write
    window between the state read above and the atomic ``os.replace`` below
    is not serialised. Two calls that interleave inside that window can
    still lose one update; atomic replacement guarantees no reader ever sees
    a truncated or corrupt file, it does not guarantee no lost update.
    File-level serialisation of ``.companion/`` writers is INFRA-285's
    advisory state lock (CER-097) — deliberately deferred rather than
    pre-empted here, to avoid a second, competing locking scheme.
    """
    import tempfile  # noqa: PLC0415

    if step_id not in _CHECKPOINT_SEQUENCE:
        click.echo(
            f"record-checkpoint-step: unknown step_id {step_id!r}. "
            f"Valid values: {', '.join(_CHECKPOINT_SEQUENCE)}",
            err=True,
        )
        return 1

    state_path = project_dir / ".companion" / "state.json"

    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except (json.JSONDecodeError, OSError):
            state = {}
    else:
        state = {}

    is_terminal = step_id == _CHECKPOINT_SEQUENCE[-1]

    # --- A2: an explicit --phase-key must name a real index row before any
    # write happens. ---
    index_path = project_dir / "docs" / "phases" / "index.md"
    if phase_key is not None and index_path.exists():
        index_text = index_path.read_text(encoding="utf-8")
        rows = _parse_index_phases(index_text)
        if not any(ref == phase_key for ref, _status in rows):
            click.echo(
                f"record-checkpoint-step: --phase-key {phase_key!r} does not "
                "match any row in docs/phases/index.md (CER-077). No write "
                "performed — re-check the phase key.",
                err=True,
            )
            return 2

    # --- A4: an explicit --phase-key that disagrees with the recorded stamp
    # is an error, not a choice between two sources. ---
    #
    # INFRA-283 (CER-095.4): once state.json has been upgraded to the keyed
    # shape (state["checkpoint_steps"] is a dict), the flat stamp can no
    # longer be trusted as "the phase currently mid-sequence" — with two
    # phases genuinely in flight, the stamp only ever names whichever one
    # wrote most recently (it is a single-slot mirror of a now-multi-slot
    # record), so a mismatch is no longer evidence of an operator mistake.
    # Applying A4 there would resurrect exactly the CER-095.4 bug this story
    # closes: "the A4 disagreement guard starts rejecting the other phase's
    # perfectly correct calls" (see docs/architecture.md's checkpoint-state
    # paragraph). A2's index-row validation still catches a genuinely
    # unknown --phase-key regardless of shape. On a legacy-shaped state (no
    # keyed record yet — at most one phase has ever been stamped), the stamp
    # is still a reliable single-phase-in-flight signal, so A4 keeps
    # protecting against the operator-typo case it was built for — this
    # mirrors the CER-083 stale-stamp rule on the resolver side, which is
    # likewise scoped to the legacy read path only (see next_action.py).
    keyed_present = isinstance(state.get(_CHECKPOINT_STEPS_KEY), dict)
    stamp = state.get("checkpoint_phase")
    stamp_is_set = isinstance(stamp, str) and stamp != ""
    if (
        not keyed_present
        and phase_key is not None
        and stamp_is_set
        and stamp != phase_key
    ):
        click.echo(
            f"record-checkpoint-step: --phase-key {phase_key!r} disagrees "
            f"with state.json['checkpoint_phase'] {stamp!r} (CER-077). "
            "Refusing to guess which is correct — no write performed.",
            err=True,
        )
        return 2

    # --- A3: resolve the effective key by precedence. ---
    if phase_key is not None:
        effective_key = phase_key
    elif stamp_is_set:
        effective_key = stamp
    else:
        try:
            candidates = _active_phase_candidates(project_dir)
        except AmbiguousActivePhaseError as exc:
            click.echo(str(exc), err=True)
            return 2

        if len(candidates) == 1:
            effective_key = candidates[0][0]
        elif len(candidates) == 0:
            effective_key = ""
        else:
            keys = ", ".join(ref for ref, _status in candidates)
            message = (
                "record-checkpoint-step: ambiguous active phase — "
                f"candidate rows {keys} (CER-077). Re-run with "
                "--phase-key <key>."
            )
            if is_terminal:
                click.echo(message, err=True)
                return 2
            # Non-terminal step: nothing irreversible happens here, and the
            # terminal step will demand the key anyway (A8) — degrade to a
            # warning and stamp the documented INFRA-260 fallback value.
            click.echo(f"warning: {message}", err=True)
            effective_key = ""

    # --- Idempotency is now checked here, after the key is resolved, not
    # before A2/A4/A3 (INFRA-283). Idempotency is per-key: whether step_id is
    # "already recorded" can only be decided once we know *which* phase's
    # list to check, so the check cannot run before effective_key exists. A
    # future reader who sees this below the precedence chain instead of at
    # the top should read it as a deliberate reorder, not an accidental
    # behaviour change — the pre-story code checked the flat list before any
    # key was known, which is exactly the bug this story fixes (a second
    # phase's identical step_id short-circuited as "done" against the first
    # phase's list).
    if isinstance(state.get(_CHECKPOINT_STEPS_KEY), dict):
        # Keyed record already exists: this project has already been
        # through at least one phase-keyed write, so each phase's list
        # lives at its own key and this call reads its own.
        steps = _read_checkpoint_steps(state)
        current = list(steps.get(effective_key, []))
    else:
        # Legacy state: before the first phase-keyed write there was only
        # ever one shared list, regardless of which key (if any) the stamp
        # named — including the A8 case where the stamp was deliberately
        # left "" while a step was recorded. Whichever phase THIS call
        # resolves to (via the A3 precedence chain above) inherits that
        # single list whole; this is what keeps a legacy sequence's single
        # phase behaviourally identical to today (assertion 9) even when an
        # explicit --phase-key only shows up on a later call in the
        # sequence than the one that started accumulating the list.
        flat = state.get("checkpoint_step")
        current = (
            [s for s in flat if isinstance(s, str)] if isinstance(flat, list) else []
        )
        steps = {}
    if step_id in current:
        return 0  # idempotent — no write, per-key

    current.append(step_id)
    steps[effective_key] = current

    if is_terminal:
        if effective_key:
            # A False return means "already complete" (idempotent, benign) —
            # not an error; A2 already validated the row exists when an
            # explicit --phase-key was given.
            _mark_phase_complete_in_index(effective_key, project_dir)
            # Identical key — never a second lookup (the CER-077 failure mode
            # INFRA-265 removed). Flips the active era doc's ledger row so the
            # era ledger tracks the index (INFRA-267/CER-082).
            _mark_phase_complete_in_era_ledger(effective_key, project_dir)
        # Clear only this call's own key — a sibling phase's mid-sequence
        # progress must survive a terminal call for a different phase
        # (INFRA-283 assertion 7; the pre-story code cleared the single
        # shared list unconditionally here).
        steps.pop(effective_key, None)
        current = []
        # Reset the phase stamp alongside the checkpoint_step reset, in the
        # same atomic write — a stamp naming a phase that was just tagged
        # must not be mistaken for a still-active phase's stamp.
        effective_key = ""

    # Store the keyed record — omit the key entirely once it is empty, so an
    # untouched project's state.json stays free of a stray empty dict.
    if steps:
        state[_CHECKPOINT_STEPS_KEY] = steps
    else:
        state.pop(_CHECKPOINT_STEPS_KEY, None)

    # Mirror block (INFRA-283, assertions 11-12): checkpoint_step /
    # checkpoint_phase are written here purely as a *derived* view of the
    # keyed record above — never the authority, never read to decide what to
    # append (see the read at "steps = _read_checkpoint_steps(state)"). They
    # exist only for readers outside this fix's scope
    # (skills/observability/api/src/readers/resolverState.ts,
    # skills/observability/ui/src/api/client.ts), which still expect one
    # flat list + one stamp. A bare "mirror, don't read" comment invites a
    # future simplification back into the single-slot bug this story fixes,
    # so the reason is spelled out here deliberately.
    if not is_terminal:
        # Non-terminal: mirror this call's own key, unambiguous.
        state["checkpoint_step"] = current
        state["checkpoint_phase"] = effective_key
    elif not steps:
        # Terminal and no keyed entries remain: today's exact post-tag value.
        state["checkpoint_step"] = []
        state["checkpoint_phase"] = ""
    elif len(steps) == 1:
        # Terminal, exactly one sibling phase remains in flight: the mirror
        # can name it without ambiguity.
        only_key, only_list = next(iter(steps.items()))
        state["checkpoint_step"] = list(only_list)
        state["checkpoint_phase"] = only_key
    else:
        # Terminal, two or more phases remain: a single flat slot cannot
        # name more than one live checkpoint without lying to a reader that
        # doesn't know about the keyed record, so it falls back to the safe
        # "no active checkpoint" value rather than guessing which one.
        state["checkpoint_step"] = []
        state["checkpoint_phase"] = ""

    # Atomic write: temp file in same dir, then rename.
    dir_ = state_path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=dir_,
        delete=False,
        suffix=".tmp",
    ) as tf:
        tf.write(json.dumps(state, indent=2))
        tmp_path_str = tf.name

    os.replace(tmp_path_str, state_path)
    return 0


@flex_build.command("checkpoint-report")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_checkpoint_report(project_dir: str) -> None:
    """Print a phase-scoped + lifetime effort cost rollup, and the next-phase
    pointer, at checkpoint time.

    Mirrors 0.2's checkpoint step 8 intent (per-role cost rollup + a closing
    "next phase" prompt) without reintroducing 0.2's prose bulk (INFRA-236,
    folding operator decision A5).

    Phase scoping (INFRA-256): the printed rollup is restricted to the
    stories listed in the active phase's ``## Stories`` table (parsed via
    ``_parse_phase_stories_with_status``, the same phase-membership list the
    checkpoint gates reason over) — never ``attempts.phase`` (nullable,
    unreliable — see ``docs/architecture.md`` § Effort tracking) and never a
    timestamp window. A lifetime rollup (unchanged ``_query_effort_by_role``,
    the same rollup ``resolver-state`` emits under ``effort_by_role``) is
    still printed afterward, under its own heading, as the historical
    baseline. Counts are row counts (spawns), not ``attempt_number`` values
    (INFRA-257 addresses ``attempt_number`` correctness separately).

    Intended call site: ``CLAUDE.build.md``'s Checkpoint section, once after
    all three checkpoint gate workers (checkpoint-security, checkpoint-intent,
    checkpoint-docs) have completed and before ``checkpoint-tag``.

    Pending-row visibility (INFRA-287, CER-101): a story whose rows exist
    but are still awaiting async reconciliation is reported as "no
    reconciled attempts (N pending)", never the bare "no attempts recorded"
    — the bare string misled a cp-109 operator into reading deferred
    reconciliation as data loss. This command deliberately does **not** run
    the reconciliation sweep first (the reconcile-first option in
    CER-101's filed fix was declined): the sweep already runs on every
    PostToolUse and SessionStart, so there is nothing left for a report to
    fix, and a reporting command that mutates the database it reports on is
    a boundary this project does not cross for convenience.

    Pure-read: writes nothing. Never raises — an absent/empty effort.db or
    index produces a minimal report, not an error.
    """
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)

    db_path = project_path / ".companion" / "effort.db"

    # Resolve the active phase and its story membership *before* the rollup,
    # so the same phase_key derivation feeds both the phase-scoped heading
    # and the existing next-phase pointer (INFRA-256 instruction 3).
    active_phase_file = _resolve_current_phase_or_exit(project_path)
    phase_key: str | None = None
    story_ids: list[str] = []
    scoping_unavailable_reason: str | None = None

    if active_phase_file is None:
        scoping_unavailable_reason = "no active phase resolved"
    else:
        phase_key = active_phase_file.stem
        if phase_key.startswith("phase-"):
            phase_key = phase_key[len("phase-") :]
        try:
            phase_text = active_phase_file.read_text(encoding="utf-8")
        except OSError:
            phase_text = ""
        phase_stories = _parse_phase_stories_with_status(phase_text)
        story_ids = [sid for sid, _title, _status in phase_stories]
        if not phase_stories:
            scoping_unavailable_reason = (
                f"phase {phase_key} has no parseable ## Stories table "
                "(or the table yields zero story IDs)"
            )

    if scoping_unavailable_reason is not None:
        click.echo("=== checkpoint cost rollup — phase scoping unavailable ===")
        click.echo(f"  reason: {scoping_unavailable_reason}")
    else:
        click.echo(f"=== checkpoint cost rollup — phase {phase_key} ===")
        scoped = _query_effort_by_story_ids(db_path, story_ids)
        by_role = scoped.get("by_role", {})
        by_story = scoped.get("by_story", {})
        pending_by_story = _query_pending_by_story_ids(db_path, story_ids)

        if not by_role:
            click.echo(f"  no attempts recorded for phase {phase_key}")
            total_pending = sum(pending_by_story.values())
            if total_pending:
                click.echo(
                    f"  {total_pending} attempt row(s) recorded but not yet "
                    "reconciled — effort is pending, not absent"
                )
        else:
            for line in _format_role_rollup_lines(by_role):
                click.echo(line)

        click.echo("  -- per-story --")
        for sid in story_ids:
            story_roles = by_story.get(sid)
            if not story_roles:
                pending_count = pending_by_story.get(sid, 0)
                if pending_count:
                    click.echo(
                        f"  {sid}: no reconciled attempts ({pending_count} pending)"
                    )
                else:
                    click.echo(f"  {sid}: no attempts recorded")
                continue
            role_parts = []
            for role in sorted(story_roles):
                stats = story_roles[role]
                count = stats.get("count", 0)
                median = stats.get("median_tokens")
                if median is not None:
                    role_parts.append(f"{role}: {count} attempt(s), median {median:,} tokens")
                else:
                    role_parts.append(f"{role}: {count} attempt(s)")
            click.echo(f"  {sid}: " + "; ".join(role_parts))

    click.echo("=== lifetime cost rollup (all phases) ===")
    effort_by_role = _query_effort_by_role(db_path)
    if not effort_by_role:
        click.echo("  no effort.db attempts recorded yet")
    else:
        for line in _format_role_rollup_lines(effort_by_role):
            click.echo(line)

    if active_phase_file is None:
        click.echo("next phase: unknown (no active phase resolved)")
        return

    next_ref = _next_phase_after(phase_key, project_path)
    if next_ref:
        click.echo(f"next phase: {next_ref}")
    else:
        click.echo("next phase: none (end of index)")


@flex_build.command("record-checkpoint-step")
@click.argument("step_id")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--phase-key",
    "phase_key",
    default=None,
    type=str,
    help=(
        "Explicit phase key this checkpoint step belongs to (CER-077). "
        "Takes precedence over the state.json checkpoint_phase stamp and "
        "over any re-derivation from docs/phases/index.md; disagreement "
        "with the stamp is an error, not a choice. Optional — every "
        "existing fleet call site keeps working without it."
    ),
)
def cmd_record_checkpoint_step(
    step_id: str, project_dir: str, phase_key: "str | None"
) -> None:
    """Atomically append *step_id* to state.json["checkpoint_step"].

    Validates step_id against the known checkpoint sequence before writing.
    Idempotent: if step_id is already present, exits 0 with no write.
    """
    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)
    rc = _record_checkpoint_step(step_id, project_path, phase_key=phase_key)
    sys.exit(rc)


@flex_build.command("check-index")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root directory.",
)
def cmd_check_index(project_dir: str) -> None:
    """Run the graph-invariant integrity checker on the project index.

    Checks four invariants:
      1. Status drift — story with a feat(story-<ID>) commit but status not complete/deferred.
      2. Cross-link consistency — phase files exist; story phase frontmatter valid; era tables match.
      3. Orphan stories — story files not referenced in any phase doc.
      4. Deferred without section — deferred story with no ## Deferred stories section naming it.

    Exits 0 (silent) when the graph is clean.
    Exits 1 and prints each violation's IDs/paths + reason when violations exist.
    Pure-read: writes nothing.

    RESOLVER-010.
    """
    from index_integrity import check_index  # noqa: PLC0415

    project_path = Path(project_dir).resolve()
    _depth_guard(project_path)

    violations = check_index(project_path)

    if not violations:
        sys.exit(0)

    for v in violations:
        ids_str = ", ".join(v.ids)
        click.echo(f"{v.kind}  [{ids_str}]  {v.path}  —  {v.reason}")

    sys.exit(1)


@flex_build.command(
    "record-attempt",
    context_settings={"ignore_unknown_options": True},
    add_help_option=False,
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def cmd_record_attempt(args: tuple[str, ...]) -> None:
    """Transparent passthrough to record_attempt.py's CLI.

    This alias exists so the orchestrator template can call
    ``flex_build.py record-attempt ...`` without knowing the path to
    ``record_attempt.py`` directly. It declares no options of its own:
    ``ignore_unknown_options`` + a ``click.UNPROCESSED`` variadic argument
    collect every token verbatim (including ``--help``, which is forwarded
    to the delegate rather than answered locally), and the alias exits with
    the delegate's own exit code.

    RELEASE-009 (origin). INFRA-263 (CER-071, CER-073): the declaration was
    previously empty, so Click rejected every real flag before the body ever
    ran. WARNING: do not add any ``@click.option`` to this command — that
    would re-introduce the exact defect this story closed. The alias must
    stay a pure passthrough; ``record_attempt.py`` alone owns its option set.
    """
    import subprocess  # noqa: PLC0415

    _scripts_dir = Path(__file__).parent
    record_script = _scripts_dir / "record_attempt.py"
    result = subprocess.run(
        [sys.executable, str(record_script), *args],
        check=False,
    )
    sys.exit(result.returncode)


@flex_build.command("create-story-worktree")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-224).")
@click.option(
    "--project-dir",
    default=".",
    help="Project directory (main worktree). Defaults to CWD.",
)
def cmd_create_story_worktree(story_id: str, project_dir: str) -> None:
    """Create a disposable git worktree for a story's build/review cycle.

    Creates ``.pairmode-worktrees/<story-id>/`` on a new branch
    ``pairmode/<story-id>`` from the current branch's HEAD and prints the
    absolute worktree path to stdout. Fails loudly (exit 1) if a worktree or
    branch for that story ID already exists — never silently reuses one.
    (INFRA-224, Ensures 1 & 2.)

    Also stamps ``current_story`` into the main checkout's
    ``.companion/state.json`` and (re)generates the story's Layer 1
    permission artifact (``docs/phases/permissions/<story_id>.json``) before
    returning the worktree path — both must be in place before the builder
    spawns so ``scope_guard.py`` can resolve the active story and its
    allowed paths regardless of the spawn's cwd (INFRA-238, Ensures 1).
    """
    _validate_story_id_or_exit(story_id)
    project_path = Path(project_dir).resolve()
    wt_rel, wt_abs, branch = _worktree_paths(story_id, project_path)

    if wt_abs.exists():
        click.echo(f"error: worktree already exists: {wt_abs}", err=True)
        sys.exit(1)

    branch_check = _run_git(
        ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        project_path,
    )
    if branch_check.returncode == 0:
        click.echo(f"error: branch already exists: {branch}", err=True)
        sys.exit(1)

    result = _run_git(
        ["worktree", "add", "-b", branch, str(wt_rel), "HEAD"],
        project_path,
    )
    if result.returncode != 0:
        click.echo(
            (result.stderr or result.stdout).strip()
            or "error: git worktree add failed",
            err=True,
        )
        sys.exit(1)

    # INFRA-238: stamp the active story into the main checkout's state.json —
    # the worktree has no .companion/ of its own; scope_guard.py always
    # resolves state from the main checkout regardless of cwd — and
    # (re)generate the Layer 1 permission artifact from the just-checked-out
    # story spec. Best-effort: a failure here must not leave the worktree
    # half-created, but it also must not silently mask the story-scope gap,
    # so it is surfaced on stderr rather than swallowed.
    try:
        _stamp_active_story(project_path, story_id)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"warning: failed to stamp current_story for {story_id}: {exc}", err=True)

    # INFRA-296 (CER-115): a permissions failure is fatal here, and the
    # asymmetry with the stamp failure above is the point. The permissions
    # artifact *is* the Layer 1 allow-list `scope_guard.py` reads, so a
    # worktree without one is a worktree in which every scoped write goes
    # unenforced — handing that to a builder is worse than handing back an
    # error. A missing `current_story` stamp only degrades scope *resolution*,
    # which INFRA-281's story-keyed `current_stories` tolerates, so that one
    # stays a warning. Do not unify the two handlers.
    # The teardown makes the command all-or-nothing: `.pairmode-worktrees/<ID>/`
    # is itself the in-flight claim (INFRA-280), so a half-created worktree
    # pins the story as claimed and forces a manual `discard-story-worktree`
    # before any retry.
    try:
        generate_permissions_artifact(story_id, project_path)
    except PermissionsCreateError as exc:
        click.echo(f"error: failed to generate permissions for {story_id}: {exc}", err=True)
        residue = _teardown_story_worktree(project_path, story_id)
        for line in _residue_lines(story_id, residue):
            click.echo(line, err=True)
        sys.exit(1)

    # CER-075 (INFRA-302): provisioning runs last, after the permissions
    # gate — a worktree about to be torn down for a missing permission
    # artifact must not be provisioned first, and provisioning must not run
    # before the story's Layer 1 allow-list exists.
    try:
        for line in _provision_story_worktree(
            project_path, wt_abs, _read_worktree_provision(project_path)
        ):
            click.echo(line, err=True)
    except Exception as exc:  # noqa: BLE001
        # CER-075: provisioning is a convenience layered on a worktree that is
        # already valid. Nothing here may strand or fail it.
        click.echo(f"warning: worktree provisioning failed: {exc}", err=True)

    click.echo(str(wt_abs))


@flex_build.command("merge-story-worktree")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-224).")
@click.option(
    "--project-dir",
    default=".",
    help="Project directory (main worktree). Defaults to CWD.",
)
def cmd_merge_story_worktree(story_id: str, project_dir: str) -> None:
    """Land a story's worktree branch onto the main worktree's branch (PASS).

    Rebases ``pairmode/<story-id>`` onto the current tip of the main
    worktree's branch, fast-forward-merges it in, then removes the worktree
    and deletes the branch. On any rebase conflict the rebase is aborted and
    the command exits non-zero with git's error output — no partial state
    change, no automatic conflict resolution. (INFRA-224, Ensures 3.)

    CER-098(c): the whole critical section — from the main-branch check
    through the final echo — runs inside the bounded advisory merge lock, so
    a concurrent ``merge-story-worktree``/``discard-story-worktree`` call is
    less likely to contend with this one on git's own ``index.lock``. Lock
    non-acquisition is fail-open (a warning, never fatal) — see `_merge_lock`.
    """
    _validate_story_id_or_exit(story_id)
    project_path = Path(project_dir).resolve()
    wt_rel, wt_abs, branch = _worktree_paths(story_id, project_path)

    if not wt_abs.exists():
        click.echo(f"error: no worktree for story: {wt_abs}", err=True)
        sys.exit(1)

    with _merge_lock(project_path) as locked:
        if not locked:
            click.echo(
                "warning: merge lock not acquired — proceeding without "
                "serialization (advisory, fail-open; CER-098(c))",
                err=True,
            )

        main_branch = _current_branch(project_path)
        if not main_branch or main_branch == "HEAD":
            click.echo(
                "error: main worktree is not on a named branch (detached HEAD)",
                err=True,
            )
            sys.exit(1)

        # Rebase the story branch onto the main branch. Run via `git -C <worktree>`
        # because the branch is checked out in the linked worktree; the invocation
        # itself is issued from the main worktree (cwd = project_dir), never by
        # cd-ing into the directory that is about to be torn down.
        rebase = _run_git(["-C", str(wt_abs), "rebase", main_branch], project_path)
        if rebase.returncode != 0:
            _run_git(["-C", str(wt_abs), "rebase", "--abort"], project_path)
            click.echo(
                (rebase.stdout + rebase.stderr).strip()
                or f"error: rebase of {branch} onto {main_branch} failed",
                err=True,
            )
            # CER-098(b): a lost race here means the story branch may now be
            # rebased onto a stale tip while the worktree, the branch and the
            # loop's stamps (attempt counter, current_stories, permission
            # artifact) are all still exactly as they were. Nothing is torn
            # down and nothing is cleared: the story's commits exist only on
            # `pairmode/<story_id>`, so releasing the claim or clearing the
            # scope stamps here would orphan them and free the resolver to
            # hand the same story to a second dispatch while this one's work
            # sits unmerged on a branch nobody is watching. Re-running the
            # command is the supported recovery — it re-rebases onto whatever
            # the new tip is and lands normally.
            for line in _recovery_block(story_id, project_path, reason="rebase"):
                click.echo(line, err=True)
            sys.exit(1)

        merge = _run_git(["merge", "--ff-only", branch], project_path)
        if merge.returncode != 0:
            click.echo(
                (merge.stderr or merge.stdout).strip()
                or f"error: fast-forward merge of {branch} failed",
                err=True,
            )
            # CER-098(b): same rationale as the rebase-failure branch above —
            # this is the lost-race case proper (another merge-story-worktree
            # landed between our rebase and our --ff-only merge). Nothing is
            # torn down, nothing is cleared; re-running rebases onto the new
            # tip and lands.
            for line in _recovery_block(story_id, project_path, reason="merge"):
                click.echo(line, err=True)
            sys.exit(1)

        # CER-098(a): the merge already landed — the story *is* done — so the
        # loop stamps below must not survive a cleanup hiccup (a failed
        # `git worktree remove`/`branch -D` must not carry a stale FAIL count
        # or scope stamp into the next story, re-creating the INFRA-237 bug
        # from a cleanup failure rather than a build failure). Residue is
        # still an operator-facing error, so it is captured and reported
        # after the clears run, not instead of them.
        residue = _teardown_story_worktree(project_path, story_id)

        # INFRA-237: a successful land is the durable "story is done" signal —
        # clear the per-story attempt counter so the next story starts at
        # attempt_count == 0 rather than carrying over a stale FAIL count.
        # INFRA-282 (CER-095.3): scoped to this story's own ID — an
        # unconditional clear wipes a still-building sibling's live escalation
        # state, the same class of cross-story clobber INFRA-281 fixed for the
        # active-story stamp below.
        clear_attempt_count(project_path, story_id)
        # INFRA-238: clear both artifacts create-story-worktree stamped — the
        # active-story marker and the Layer 1 permission artifact — so the next
        # story starts with a clean slate rather than inheriting this story's
        # scope. INFRA-281 (CER-095.2): the active-story clear is scoped to this
        # story's own ID — an unconditional clear would disable scope
        # enforcement for a different builder that is still running in its own
        # worktree.
        _clear_active_story(project_path, story_id)
        clear_permissions_artifact(story_id, project_path)
        click.echo(f"merged {branch} into {main_branch}")

        if residue:
            for line in _residue_lines(story_id, residue):
                click.echo(line, err=True)
            sys.exit(1)


@flex_build.command("discard-story-worktree")
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-224).")
@click.option(
    "--project-dir",
    default=".",
    help="Project directory (main worktree). Defaults to CWD.",
)
def cmd_discard_story_worktree(story_id: str, project_dir: str) -> None:
    """Throw away a story's worktree and branch (reviewer FAIL).

    Removes the worktree — including any uncommitted or untracked content the
    builder created inside it — and deletes the ``pairmode/<story-id>``
    branch. Runs no command against the main worktree's working directory:
    a FAIL in a story's worktree cannot touch the main worktree's files,
    tracked or untracked, regardless of the reviewer's revert logic.
    (INFRA-224, Ensures 4.)

    CER-098(c): the critical section — teardown through the final echo —
    runs inside the bounded advisory merge lock (shared with
    ``merge-story-worktree``), for the same fail-open reasoning; see
    `_merge_lock`.
    """
    _validate_story_id_or_exit(story_id)
    project_path = Path(project_dir).resolve()
    _wt_rel, _wt_abs, branch = _worktree_paths(story_id, project_path)

    with _merge_lock(project_path) as locked:
        if not locked:
            click.echo(
                "warning: merge lock not acquired — proceeding without "
                "serialization (advisory, fail-open; CER-098(c))",
                err=True,
            )

        # CER-098(a): on a discard nothing has landed, so — unlike the merge
        # path — residue keeps the loop stamps in place and exits *before*
        # clearing them, preserving the discard path's existing behaviour
        # exactly: the asymmetry with the merge path is deliberate, not an
        # oversight to "unify".
        residue = _teardown_story_worktree(project_path, story_id)
        if residue:
            for line in _residue_lines(story_id, residue):
                click.echo(line, err=True)
            sys.exit(1)

        # INFRA-238: clear both artifacts create-story-worktree stamped — the
        # active-story marker and the Layer 1 permission artifact — so a
        # discarded attempt does not leave stale scope state behind for whatever
        # runs next (a retry re-stamps via create-story-worktree; a different
        # story must not inherit this one's scope). INFRA-281 (CER-095.2): the
        # active-story clear is scoped to this story's own ID — an unconditional
        # clear would disable scope enforcement for a different builder that is
        # still running in its own worktree.
        _clear_active_story(project_path, story_id)
        clear_permissions_artifact(story_id, project_path)

        click.echo(f"discarded {branch}")


if __name__ == "__main__":
    flex_build()
