"""
scope_guard.py — Story file-scope enforcement for the pre_tool_use hook.

check_path(file_path, project_dir) -> (allowed: bool, reason: str)

Fails open for non-protected paths: when state, permissions file, or any read
fails, returns (True, reason). Protected paths (PROTECTED_GLOBS) fail closed —
blocked with no active story, AND blocked mid-story whenever the active
story's permissions artifact is missing, empty, or malformed (INFRA-253):
a protected path is only satisfiable by an explicit entry in the story's
permissions artifact (derived from the story's `primary_files` + `touches`).
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# INFRA-271 (CER-080): a single-story build never legitimately spans a day —
# a `current_stories` stamp older than this is far more likely to be an
# uncleaned/idle checkout (the observed case: INFRA-209, stamped 2026-07-20
# and never cleared, blocked every Edit/Write from every worktree of the
# repo indefinitely) than an in-flight build. Ageing a stamp out only ever
# *removes* authorization for the state-file fallback — it never grants any
# (see A7/`check_path`'s protected-path handling of `source == "stale"`).
STATE_STORY_MAX_AGE_HOURS: float = 24.0

PROTECTED_GLOBS = [
    "hooks/**",
    ".claude-plugin/**",
    "skills/seed/**",
    "skills/companion/**",
    "lessons/**",
    ".claude/settings.json",
    ".claude/settings.local.json",
]


def _is_protected(path_str: str) -> bool:
    return any(fnmatch.fnmatch(path_str, g) for g in PROTECTED_GLOBS)


# INFRA-320 (CER-128) § A1 — standing shared surfaces: exact repo-relative
# paths every story may write without declaring them in `primary_files` /
# `touches`. A path may join this tuple only if it is (i) a documentation or
# record surface, never code; (ii) not matched by `PROTECTED_GLOBS` (the
# protected check always runs first and its result is final — a standing
# entry can never reach a protected path, see `check_path`); and (iii) one
# that a majority of stories legitimately touch. Adding a code path to this
# tuple is a CRITICAL review finding (reviewer/procedure.md § 9 RAIL SCOPE).
STANDING_SURFACES: tuple[str, ...] = (
    "docs/cer/backlog.md",
    "docs/architecture.md",
    # INFRA-365 (Phase-118 checkpoint-security HIGH): the shadow-reviewer's
    # sole output channel (INFRA-358/359, skills/pairmode/skills/
    # shadow-reviewer/procedure.md § "The suggestions file"). Gitignored
    # and deliberately never declared in any story's primary_files/touches
    # (INFRA-358) — a standing entry is the only way a live shadow-reviewer
    # dispatch (which resolves to the active story via resolve_call_story,
    # same as the builder) can ever write it. Matched exactly at the
    # worktree root; not a prefix/glob, so no other dotfile or nested path
    # is affected.
    ".pairmode-suggestions.md",
)


def standing_paths_for(
    story_id: "str | None",
    story_phase: "str | None" = None,
) -> tuple[str, ...]:
    """Return `STANDING_SURFACES` plus the per-story derived standing paths
    (INFRA-320 § A2): the story's own spec (`docs/stories/<RAIL>/<ID>.md`)
    and, only when *story_phase* is supplied, that one phase doc
    (`docs/phases/phase-<phase>.md`) — no other phase doc is ever standing.

    Total: a malformed *story_id* or an absent/blank *story_phase* degrades
    to the static surfaces alone (plus the spec path when the ID does
    parse) and never raises. Performs no file I/O — `check_path` runs on
    every Edit/Write through the hook and this function must stay cheap and
    pure.
    """
    paths = list(STANDING_SURFACES)
    try:
        if story_id and _STORY_ID_RE.match(story_id):
            rail = story_id.split("-", 1)[0]
            paths.append(f"docs/stories/{rail}/{story_id}.md")
    except Exception:
        pass
    try:
        if isinstance(story_phase, str) and story_phase.strip():
            paths.append(f"docs/phases/phase-{story_phase.strip()}.md")
    except Exception:
        pass
    return tuple(paths)


_SHADOW_REVIEWER_ONLY_PATH = ".pairmode-suggestions.md"


def check_path(
    file_path: str | Path,
    project_dir: str | Path,
    agent_type: "str | None" = None,
) -> tuple[bool, str]:
    # INFRA-238: *project_dir* is the tool call's cwd, which for a story-build
    # spawn is the per-story worktree (<main>/.pairmode-worktrees/<story-id>/),
    # not the main checkout. state.json and the permissions artifacts only
    # ever live in the main checkout — resolve it here so scope enforcement
    # works regardless of the spawn's cwd.
    project = _resolve_main_project_root(Path(project_dir).resolve())

    # CER-174 (HIGH): a shadow-reviewer-attributed write is confined to
    # exactly `.pairmode-suggestions.md`, independent of resolve_call_story's
    # primary_files/touches/STANDING_SURFACES resolution for the active
    # story — the shadow-reviewer never inherits the builder's write scope,
    # even for a path that IS in that scope (e.g. docs/architecture.md, or a
    # story's own primary_files entry). This short-circuit runs before any
    # story resolution and never falls through to the builder-scope logic
    # below, even as a fallback.
    if agent_type == "shadow-reviewer":
        # INFRA-408 (CER-176/177/201): a cwd-only derivation. The prior
        # implementation handed `resolve_call_story` both `project_dir` AND
        # `file_path`, which meant a call whose cwd carried no worktree
        # signal (e.g. cwd at the main checkout) could still resolve an
        # active story from *file_path*'s own worktree-shaped spelling
        # (`resolve_call_story`'s `worktree-path` step) or from whichever
        # story happened to be "current" in state.json (`state-single` /
        # `state-legacy`) — either lets a write land in a different story's
        # worktree, or in a harness allow-list prefix, once
        # `_strip_worktree_prefix` or a bare filename match let it through.
        # Here only the process's own real cwd (INFRA-280's claim) is ever
        # trusted to name a story: the worktree root is derived by walking
        # `project_dir` itself against `.pairmode-worktrees/<ID>/`, with no
        # fallback to file_path content or to state.json. When cwd carries
        # no such signal — including cwd at the main checkout — there is no
        # permitted worktree root at all, and the call is denied outright,
        # regardless of what *file_path* is, before any path comparison.
        raw_cwd = Path(project_dir).resolve()
        try:
            rel_parts = raw_cwd.relative_to(project).parts
        except ValueError:
            rel_parts = ()
        if (
            len(rel_parts) >= 2
            and rel_parts[0] == _WORKTREE_PREFIX.rstrip("/")
            and _STORY_ID_RE.match(rel_parts[1])
        ):
            worktree_root = project / _WORKTREE_PREFIX.rstrip("/") / rel_parts[1]
        else:
            return (
                False,
                "shadow-reviewer write denied — cwd carries no per-story "
                f"worktree signal, so no path can resolve to "
                f"{_SHADOW_REVIEWER_ONLY_PATH}",
            )

        try:
            p = Path(file_path)
            candidate_path = (p if p.is_absolute() else raw_cwd / p).resolve()
        except Exception:
            return (
                False,
                "shadow-reviewer write denied — could not resolve the "
                "write target path",
            )

        permitted = (worktree_root / _SHADOW_REVIEWER_ONLY_PATH).resolve()
        if candidate_path == permitted:
            return True, "allowed (shadow-reviewer suggestions file)"
        return (
            False,
            f"{candidate_path} is outside the shadow-reviewer role's write "
            f"scope — confined to exactly {permitted}",
        )

    # INFRA-281 (CER-095.2): resolve_call_story is handed the *raw*
    # project_dir, not `project` — the worktree identity `project` just
    # collapsed away is exactly the signal resolve_call_story needs to tell
    # concurrent builders apart.
    story_id, source = resolve_call_story(project_dir, file_path)
    if not story_id:
        relative_path = _normalise(file_path, project)
        if relative_path is None:
            return _out_of_root_decision(file_path, project, project_dir)
        ambiguous_note = None
        if source == "ambiguous":
            claimed = sorted(_read_current_stories_keyed(project))
            ambiguous_note = (
                "ambiguous — multiple stories claimed ("
                + ", ".join(claimed)
                + "); resolving to no active story rather than guessing"
            )
        # INFRA-271 (CER-080): a fully-aged-out state.json produces its own
        # note, built once and reused for both the protected-path denial and
        # the fail-open allow — so the two can never describe the state
        # differently (the same shape `ambiguous_note` already uses above).
        stale_note = None
        if source == "stale":
            stale_note = (
                f"stale — the only current_stories/current_story stamp(s) are "
                f"older than STATE_STORY_MAX_AGE_HOURS ({STATE_STORY_MAX_AGE_HOURS}h); "
                "resolving to no active story rather than trusting an idle "
                "checkout's stamp indefinitely; run "
                "`flex_build.py clear-stale-stories` to sweep it"
            )
        note = ambiguous_note or stale_note
        if _is_protected(relative_path):
            if note:
                return (
                    False,
                    f"{relative_path} is a protected path — {note}; "
                    "requires an active story with this file in primary_files "
                    "or touches, authorized via "
                    "docs/phases/permissions/<story_id>.json",
                )
            return (
                False,
                f"{relative_path} is a protected path — requires an active story "
                "with this file in primary_files or touches, authorized via "
                "docs/phases/permissions/<story_id>.json",
            )
        if note:
            return True, note
        return True, "no active story — allowing"

    normalised = _normalise(file_path, project)
    if normalised is None:
        return _out_of_root_decision(file_path, project, project_dir)

    # INFRA-253: protected-path status is checked against the worktree-stripped
    # candidate (the real repo-relative identity of the path), not the raw
    # (possibly worktree-prefixed) normalised path.
    candidate = _strip_worktree_prefix(normalised, story_id)
    protected = _is_protected(candidate)

    allowed_paths, status = _read_allowed_paths(project, story_id)

    if status == "missing":
        if protected:
            return False, (
                f"{candidate} is a protected path — no permissions artifact for "
                f"{story_id} (docs/phases/permissions/{story_id}.json missing); "
                "authorization requires the path in the story's primary_files "
                "or touches"
            )
        return True, f"no permissions file for {story_id} — allowing"

    if status == "malformed":
        if protected:
            return False, (
                f"{candidate} is a protected path — permissions artifact for "
                f"{story_id} is malformed; authorization requires the path in "
                "the story's primary_files or touches"
            )
        return True, f"malformed permissions file for {story_id} — allowing"

    # status == "ok"
    if not allowed_paths:
        if protected:
            return False, (
                f"{candidate} is a protected path — empty allowed_paths for "
                f"{story_id}; authorization requires the path in the story's "
                "primary_files or touches"
            )
        return True, f"empty allowed_paths for {story_id} — allowing"

    if candidate in allowed_paths:
        return True, "allowed"

    # INFRA-320 § A3/A4/A7: the standing-surface union is consulted only
    # here — after the protected check has already run and only when the
    # candidate is NOT protected — so a standing entry can never override
    # PROTECTED_GLOBS (A4). `artifact_standing` is the artifact's own
    # `standing_paths` (present on any artifact generated after this story
    # lands); `live` is always recomputed from the current STANDING_SURFACES
    # so a pre-INFRA-320 artifact (no `standing_paths` key) still grants the
    # standing set — a migration-free upgrade (A7).
    if not protected:
        artifact_standing, artifact_phase = _read_standing_and_phase(project, story_id)
        live = standing_paths_for(story_id, artifact_phase)
        if candidate in set(artifact_standing) | set(live):
            return True, "allowed (standing shared surface)"

    return False, f"not in story scope for {story_id}: {normalised}"


def harness_owned_prefixes(
    project: Path,
    raw_project_dir: "str | Path | None" = None,
    home: "Path | None" = None,
) -> list[Path]:
    """Return the resolved absolute path prefixes that harness-owned writes
    outside the project root are permitted under (INFRA-271, CER-087).

    This is deliberately narrow (B2) — an allow-list of *harness-owned*
    paths, not a relaxation of `_normalise`'s containment (B4). Only two
    kinds of out-of-root path are listed:

    - ``<home>/.claude/projects/<key>/memory`` — the orchestrator's
      auto-memory notes directory. Allow-listed *only* at its ``memory/``
      subdirectory: the sibling ``<session>.jsonl`` transcripts one level up
      are what `subagent_transcript.py` derives the effort ledger from, so
      an agent that could write those could forge its own effort record —
      the transcript directory itself must never appear in this list.
    - ``<tmp>/claude-<uid>/<key>`` — the session scratchpad root.

    plus, once, ``<home>/.claude/plans``. Nothing else under ``~/.claude/``
    is listed: ``settings.json``, ``policies/``, ``plugins/`` and ``skills/``
    are harness *configuration*, not harness scratch state, and must stay
    denied like any other out-of-root path.

    ``key = str(p).replace("/", "-")`` is the same derivation
    `context_budget.py`'s `_derive_transcript_path` already uses for the
    transcript directory. Both ``project`` (the resolved main checkout root)
    and, when different, the resolved *raw_project_dir* (the tool call's
    raw cwd — e.g. a session anchored in a differently-named worktree of
    the same repo) are keyed, because a harness session's memory/scratchpad
    directories are keyed on the cwd the session actually started in, which
    `_resolve_main_project_root` has already collapsed away by the time this
    function is called.

    Every entry is ``.resolve()``-d. Never raises: any failure (no
    ``os.getuid``, an unresolvable home) drops that entry and returns
    whatever else resolved.
    """
    prefixes: list[Path] = []
    try:
        resolved_home = (home if home is not None else Path.home()).resolve()
    except Exception:
        return prefixes

    keys: list[str] = []
    try:
        keys.append(str(project.resolve()).replace("/", "-"))
    except Exception:
        pass
    if raw_project_dir is not None:
        try:
            raw_resolved = Path(raw_project_dir).resolve()
            if project.resolve() != raw_resolved:
                keys.append(str(raw_resolved).replace("/", "-"))
        except Exception:
            pass

    for key in keys:
        try:
            prefixes.append((resolved_home / ".claude" / "projects" / key / "memory").resolve())
        except Exception:
            pass

    try:
        prefixes.append((resolved_home / ".claude" / "plans").resolve())
    except Exception:
        pass

    try:
        tmp_root = Path(tempfile.gettempdir())
        uid = os.getuid()
        for key in keys:
            prefixes.append((tmp_root / f"claude-{uid}" / key).resolve())
    except Exception:
        pass

    return prefixes


def _out_of_root_decision(
    file_path: "str | Path",
    project: Path,
    raw_project_dir: "str | Path | None",
) -> tuple[bool, str]:
    """The sole decision point for a path that `_normalise` has already
    determined resolves outside *project* (INFRA-271, CER-087).

    Resolves *file_path* using the exact same semantics `_normalise` uses
    (`Path(file_path)`, joined onto *project* when relative, then
    `.resolve()`) and compares the *resolved* path against
    `harness_owned_prefixes()` with `Path.is_relative_to` — never a string
    `startswith` check, which is the same class of mistake INFRA-255's
    `_normalise` docstring already warns about for `..`, and which would let
    a symlink under an allow-listed prefix launder a write to anywhere.

    Returns an allow decision naming the matched prefix when the resolved
    path is relative to one of the allow-listed prefixes, and the module's
    single out-of-root deny result otherwise — this function is the ONLY
    site in the module that produces that deny string (B5).

    `_normalise` itself is unchanged (B4): this function is a decision layered
    on top of its containment result, never a hole punched in it.
    """
    resolved: "Path | None" = None
    try:
        p = Path(file_path)
        candidate = p if p.is_absolute() else project / p
        resolved = candidate.resolve()
    except Exception:
        resolved = None

    if resolved is not None:
        for prefix in harness_owned_prefixes(project, raw_project_dir):
            try:
                if resolved.is_relative_to(prefix):
                    return (
                        True,
                        f"harness-owned path outside project root — allowing: {prefix}",
                    )
            except Exception:
                continue

    return False, "path escapes project root"


def _resolve_main_project_root(project: Path) -> Path:
    """Resolve the main checkout root even when *project* is a per-story
    worktree (``<main>/.pairmode-worktrees/<story-id>/``).

    A linked git worktree has no ``.companion/`` of its own; ``state.json``
    and the permission artifacts only ever live in the main checkout. A
    linked worktree's ``.git`` is a *file* (not a directory) containing
    ``gitdir: <main>/.git/worktrees/<name>``; resolve that back up to the
    main checkout root. Falls back to *project* unchanged when it is not a
    linked worktree, or the ``.git`` file can't be parsed — this is a
    best-effort resolution, never a hard failure.
    """
    git_marker = project / ".git"
    if not git_marker.is_file():
        return project
    try:
        text = git_marker.read_text(encoding="utf-8").strip()
    except OSError:
        return project
    if not text.startswith("gitdir:"):
        return project
    raw = text.split(":", 1)[1].strip()
    gitdir = Path(raw)
    if not gitdir.is_absolute():
        gitdir = (project / gitdir).resolve()
    else:
        gitdir = gitdir.resolve()
    # A linked worktree's gitdir is <main>/.git/worktrees/<name>; the main
    # checkout root is three levels up from there.
    if gitdir.parent.name != "worktrees":
        return project
    candidate = gitdir.parent.parent.parent
    return candidate if candidate.is_dir() else project


# Copied from flex_build._STORY_ID_RE (source of truth for the story-ID
# shape) rather than imported: this module sits on the pre_tool_use hook
# path and must stay import-light — flex_build pulls in click, effort_db,
# next_action and more.
_STORY_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d{3}$")

# The literal `source` values `resolve_call_story` can return, defined once
# so tests can enumerate them without hardcoding the strings twice.
RESOLVE_CALL_STORY_SOURCES = frozenset(
    {
        "worktree-cwd",
        "worktree-path",
        "state-single",
        "state-legacy",
        "ambiguous",
        "stale",
        "none",
    }
)


def entry_is_fresh(
    entry: dict,
    now: "datetime | None" = None,
    max_age_hours: "float | None" = None,
) -> bool:
    """Return whether a ``current_stories``/``current_story`` *entry* dict's
    ``set_at`` stamp is fresh enough to still authorise scope enforcement
    (INFRA-271, CER-080).

    Public (no leading underscore): ``flex_build.py``'s ``clear-stale-stories``
    command calls this directly so the CLI and the guard can never disagree
    about what "stale" means.

    Never raises for any input. Returns ``False`` when *entry* is not a dict,
    when ``set_at`` is absent, empty, or not a string, or when
    ``datetime.fromisoformat`` cannot parse it — a stamp that cannot even be
    dated is strictly less trustworthy than one that can, and ageing it out
    only removes authorization (protected paths stay fail-closed regardless;
    see `check_path`'s `source == "stale"` handling), so treating an
    unparseable stamp as stale is safe.

    A naive (no-tzinfo) ``set_at`` is treated as UTC rather than raising —
    ``datetime.now(timezone.utc).isoformat()`` (the only writer,
    `story_context.set_current_story`) always includes an offset, but this
    keeps the predicate defensive against a hand-edited or legacy stamp.

    A *future* ``set_at`` is always fresh: clock skew between the process
    stamping the entry and the process evaluating it must never silently
    switch scope enforcement off, so a forward-dated stamp fails toward
    enforcement rather than toward staleness.
    """
    try:
        if not isinstance(entry, dict):
            return False
        set_at = entry.get("set_at")
        if not isinstance(set_at, str) or not set_at:
            return False
        parsed = datetime.fromisoformat(set_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        now_dt = now if now is not None else datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        if parsed > now_dt:
            # Future stamp — clock skew must not disable enforcement.
            return True
        cutoff = max_age_hours if max_age_hours is not None else STATE_STORY_MAX_AGE_HOURS
        age_hours = (now_dt - parsed).total_seconds() / 3600.0
        return age_hours <= cutoff
    except Exception:
        return False


def _read_state_dict(project: Path) -> dict:
    try:
        return json.loads((project / ".companion" / "state.json").read_text())
    except Exception:
        return {}


def _read_current_stories_keyed(project: Path) -> dict:
    """Return the ``current_stories`` dict from *project*'s state.json.

    Read-only; never raises. Returns ``{}`` when the key is absent, empty,
    or the state file can't be read — deliberately does **not** fall back to
    the flat ``current_story`` key, so callers that need the legacy fallback
    (``resolve_call_story``'s ``state-legacy`` step) apply it explicitly and
    the two fallback conditions in B5 stay distinguishable.
    """
    state = _read_state_dict(project)
    keyed = state.get("current_stories")
    return keyed if isinstance(keyed, dict) else {}


def _read_legacy_story_id(project: Path) -> str | None:
    state = _read_state_dict(project)
    legacy = state.get("current_story")
    if isinstance(legacy, dict):
        val = legacy.get("id")
        return str(val).strip() if val else None
    return None


def _read_legacy_story_entry(project: Path) -> "tuple[str, dict] | None":
    """Return ``(story_id, entry)`` for the flat ``current_story`` mirror, or
    ``None`` when absent/malformed. Kept separate from `_read_legacy_story_id`
    (which only ever returns the ID) because INFRA-271's staleness check
    (A4/A9) needs the entry's `set_at`, not just its ID.
    """
    state = _read_state_dict(project)
    legacy = state.get("current_story")
    if not isinstance(legacy, dict):
        return None
    val = legacy.get("id")
    story_id = str(val).strip() if val else None
    if not story_id:
        return None
    return story_id, legacy


def resolve_call_story(
    project_dir: str | Path,
    file_path: str | Path | None = None,
) -> tuple[str | None, str]:
    """Resolve which story a tool call belongs to, per-call, from the call
    itself (INFRA-281 / CER-095.2).

    A single global ``state.json["current_story"]`` slot cannot answer "which
    story is this write for?" once more than one story can be in flight —
    whichever story was stamped last wins for every builder. The answer is
    already carried by the call: a builder's tool calls come from its own
    worktree (``.pairmode-worktrees/<ID>/``), the same claim INFRA-280 taught
    the resolver to read. Only when the call demonstrably comes from the main
    checkout, with no worktree signal in either the cwd or the target path,
    does this fall back to ``state.json`` — and even then it refuses to guess
    when more than one story is claimed there.

    Returns ``(story_id, source)`` where ``source`` is one of
    ``RESOLVE_CALL_STORY_SOURCES``. Resolution order:

    1. ``worktree-cwd`` — *project_dir* is, or is inside,
       ``<main>/.pairmode-worktrees/<ID>/`` with ``<ID>`` matching
       ``_STORY_ID_RE``;
    2. ``worktree-path`` — otherwise, the repo-relative *file_path* begins
       with ``.pairmode-worktrees/<ID>/`` with ``<ID>`` matching
       ``_STORY_ID_RE``;
    3. ``state-single`` — otherwise, ``current_stories`` holds exactly one
       entry;
    4. ``state-legacy`` — otherwise, ``current_stories`` is absent/empty and
       the flat ``current_story`` names a story;
    5. ``ambiguous`` — otherwise, ``current_stories`` holds two or more
       entries: ``story_id`` is ``None`` (never "pick the most recent" —
       false confidence here is worse than no answer);
    6. ``none`` — no signal at all: ``story_id`` is ``None``.

    Performs no writes, never raises (any exception resolves to
    ``(None, "none")``), and does not require the resolved worktree ID to
    appear in ``current_stories`` — the worktree itself is the claim
    (INFRA-280), authoritative over the state file, not subordinate to it.
    """
    try:
        raw = Path(project_dir).resolve()
        main = _resolve_main_project_root(raw)

        # 1. worktree-cwd
        try:
            rel_parts = raw.relative_to(main).parts
        except ValueError:
            rel_parts = ()
        if (
            len(rel_parts) >= 2
            and rel_parts[0] == _WORKTREE_PREFIX.rstrip("/")
            and _STORY_ID_RE.match(rel_parts[1])
        ):
            return rel_parts[1], "worktree-cwd"

        # 2. worktree-path. SECURITY (regression guard for
        # test_scope_guard_blocks_foreign_story_worktree_path_bypass): a
        # story ID lifted straight out of the *target path* must not be fed
        # back into `_strip_worktree_prefix` for that same path — the two
        # would always agree by construction, silently defeating that
        # function's "only strip when the segment equals the caller's real
        # active story" guarantee, and letting any caller impersonate any
        # story merely by spelling a worktree-shaped path. Unlike
        # worktree-cwd (where the cwd's mere existence as the process's real
        # working directory *is* the INFRA-280 claim), a path string proves
        # nothing about who issued the call. So this step additionally
        # requires the named worktree directory to exist on disk — the same
        # standard INFRA-280's claim reader (`flex_build.claimed_story_ids`)
        # applies to a cwd-based claim, applied here to a path-based one.
        if file_path is not None:
            normalised = _normalise(file_path, main)
            if normalised is not None and normalised.startswith(_WORKTREE_PREFIX):
                remainder = normalised[len(_WORKTREE_PREFIX):]
                segment, _sep, rest = remainder.partition("/")
                if (
                    rest
                    and _STORY_ID_RE.match(segment)
                    and (main / _WORKTREE_PREFIX.rstrip("/") / segment).is_dir()
                ):
                    return segment, "worktree-path"

        # 3-6: state.json fallback, main-checkout calls only.
        return _resolve_story_from_state(main)
    except Exception:
        return None, "none"


def _resolve_story_from_state(main: Path) -> tuple[str | None, str]:
    """Steps 3-6 of ``resolve_call_story``'s order: the state.json-only
    fallback rules, given the already-resolved main checkout root.

    INFRA-271 (CER-080): the state fallback ages out per-entry staleness
    (`entry_is_fresh`) before applying the single/ambiguous/legacy/none
    rules. A worktree claim (steps 1-2 in `resolve_call_story`) never
    consults this — the worktree directory's existence on disk is the claim,
    not `state.json`. Order, given
    ``keyed = _read_current_stories_keyed(main)`` and
    ``fresh = {k: v for k, v in keyed.items() if entry_is_fresh(v)}``:

    - exactly one fresh entry -> ``(that_id, "state-single")``;
    - two or more fresh entries -> ``(None, "ambiguous")`` (unchanged refusal
      to guess; a stale entry is not counted towards ambiguity);
    - no fresh entries but ``keyed`` non-empty -> ``(None, "stale")``;
    - ``keyed`` empty and the flat ``current_story`` names a story: fresh ->
      ``(id, "state-legacy")``, stale -> ``(None, "stale")``;
    - nothing at all -> ``(None, "none")``.
    """
    keyed = _read_current_stories_keyed(main)
    if keyed:
        fresh = {k: v for k, v in keyed.items() if entry_is_fresh(v)}
        if len(fresh) == 1:
            return next(iter(fresh)), "state-single"
        if len(fresh) >= 2:
            return None, "ambiguous"
        return None, "stale"
    legacy = _read_legacy_story_entry(main)
    if legacy is not None:
        legacy_id, entry = legacy
        if entry_is_fresh(entry):
            return legacy_id, "state-legacy"
        return None, "stale"
    return None, "none"


def _read_current_story(project: Path) -> str | None:
    """Thin wrapper over ``resolve_call_story``'s state-only rules.

    Kept for ``hooks/pre_tool_use.py``'s (pre-INFRA-281) import and for any
    other caller that only has *project* — not a raw call cwd or target
    path — to resolve against. ``state-single``/``state-legacy`` return the
    resolved ID; ``ambiguous``/``none`` return ``None`` rather than a guess,
    exactly as ``resolve_call_story`` does when two stories are active.
    Never raises.
    """
    try:
        main = _resolve_main_project_root(Path(project).resolve())
        story_id, _source = _resolve_story_from_state(main)
        return story_id
    except Exception:
        return None


def _read_allowed_paths(project: Path, story_id: str) -> tuple[list[str] | None, str]:
    """Returns (allowed_paths, status) where status is one of:
    "missing" (no permissions artifact for the story), "malformed" (artifact
    exists but is unreadable/invalid), or "ok" (artifact read successfully;
    allowed_paths may still be an empty list).

    INFRA-253: status is reported separately from the list itself so
    check_path() can distinguish these three fail-open triggers and apply
    the fail-closed protected-path override to each independently.
    """
    perm_path = project / "docs" / "phases" / "permissions" / f"{story_id}.json"
    if not perm_path.exists():
        return None, "missing"
    try:
        data = json.loads(perm_path.read_text())
        paths = data.get("allowed_paths")
        return ([_norm_str(p) for p in paths] if isinstance(paths, list) else []), "ok"
    except Exception:
        return None, "malformed"


def _read_standing_and_phase(project: Path, story_id: str) -> "tuple[tuple[str, ...], str | None]":
    """Read ``standing_paths`` / ``story_phase`` from the story's permissions
    artifact (INFRA-320 § A7).

    Never raises: a missing file, invalid JSON, a non-dict payload, or a
    malformed ``standing_paths``/``story_phase`` value all degrade to
    ``((), None)`` — the malformed-key case check_path's caller then falls
    back to purely by computing the live ``standing_paths_for()`` union,
    never an exception.
    """
    perm_path = project / "docs" / "phases" / "permissions" / f"{story_id}.json"
    try:
        data = json.loads(perm_path.read_text())
    except Exception:
        return (), None
    if not isinstance(data, dict):
        return (), None
    raw_standing = data.get("standing_paths")
    standing = (
        tuple(_norm_str(p) for p in raw_standing)
        if isinstance(raw_standing, list) and all(isinstance(p, str) for p in raw_standing)
        else ()
    )
    raw_phase = data.get("story_phase")
    phase = raw_phase.strip() if isinstance(raw_phase, str) and raw_phase.strip() else None
    return standing, phase


_WORKTREE_PREFIX = ".pairmode-worktrees/"


def _strip_worktree_prefix(path: str, active_story_id: str | None) -> str:
    """Strip a leading ``.pairmode-worktrees/<segment>/`` prefix from *path*,
    but ONLY when ``<segment>`` equals *active_story_id*.

    A build spawn's cwd is the per-story worktree
    (``.pairmode-worktrees/<story-id>/``), so a path edited there
    (``.pairmode-worktrees/INFRA-238/skills/foo.py``) never matches an
    ``allowed_paths`` entry generated from ``primary_files: [skills/foo.py]``
    unless this prefix is stripped first. But stripping it unconditionally —
    regardless of which story's worktree the path actually names — lets a
    path belonging to a DIFFERENT, concurrently in-progress story's worktree
    (``.pairmode-worktrees/INFRA-999/skills/foo.py`` while INFRA-238 is
    active) get misidentified as in-scope purely because its trailing
    segments match an allowed_paths entry name after stripping. That defeats
    per-story worktree isolation. So: only strip when the worktree segment
    equals the currently active story's ID; any other segment (or no active
    story) is left untouched and therefore falls through to the normal
    out-of-scope/not-found comparison below, which will not match.
    """
    if not path.startswith(_WORKTREE_PREFIX):
        return path
    remainder = path[len(_WORKTREE_PREFIX):]
    segment, _sep, rest = remainder.partition("/")
    if not active_story_id or not rest or segment != active_story_id:
        return path
    return rest


def _normalise(file_path: str | Path, project: Path) -> str | None:
    """Resolve *file_path* to an absolute path and contain it against
    *project*, returning the repo-relative posix string, or ``None`` if the
    resolved path is not *project* or a descendant of it (INFRA-255).

    Both relative and absolute inputs are resolved through the same code
    path: a relative input is joined onto *project* (the main-checkout root
    returned by ``_resolve_main_project_root()``, NOT the raw ``project_dir``
    cwd — resolving against a worktree cwd would turn a no-active-story
    protected-path candidate like ``hooks/x.py`` into
    ``.pairmode-worktrees/<id>/hooks/x.py``, which no longer matches
    ``PROTECTED_GLOBS`` in the branch that does not strip the worktree
    prefix; resolving against the main root instead preserves pre-story
    semantics for the common case of an already repo-relative path from a
    build spawn). ``Path.resolve()`` is non-strict on Python 3.11 (it works
    for paths that do not exist yet, which matters for Write creating a new
    file) and collapses ``..`` segments, so containment is enforced by
    ``relative_to()`` on the resolved, absolute path — never by a
    pre-resolution string check for ``..``, which would be trivially evaded
    (e.g. a disguised prefix) and is not a security boundary on its own.

    ``resolve()`` also follows symlinks, so a repo-internal symlink pointing
    outside the project root is denied here too. That is intentional
    fail-closed behaviour, not a bug — do not "fix" it by skipping symlink
    resolution.
    """
    p = Path(file_path)
    candidate = p if p.is_absolute() else project / p
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(project)
    except ValueError:
        return None
    return _norm_str(relative)


def _norm_str(p: str | Path) -> str:
    s = Path(p).as_posix()
    # NOTE: the previous implementation used str.lstrip("./"), which strips
    # every leading "." and "/" character (a character-class strip), not a
    # single "./" prefix — so "./../../etc/passwd" was laundered into the
    # innocuous-looking "etc/passwd". Use a single-prefix removal instead.
    return s.removeprefix("./")
