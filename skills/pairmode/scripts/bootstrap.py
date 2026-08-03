"""
bootstrap.py — Pairmode scaffold generator.

Writes pairmode scaffold files from Jinja2 templates into a target project
directory.  Existing files are not overwritten without explicit user
confirmation.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(_Path(__file__).parent))

import click
import jinja2

from skills.pairmode.scripts import spec_reader as _spec_reader
from skills.pairmode.scripts import checklist_deriver as _checklist_deriver
from skills.pairmode.scripts import denylist_deriver as _denylist_deriver
from skills.pairmode.scripts._version import PAIRMODE_VERSION  # noqa: E402
from skills.pairmode.scripts.context_model import THIN_HARNESS_STEP_TOKENS
import ideology_parser as _ideology_parser
import hook_view  # INFRA-288: merged hook view (stdlib-only, cheap) — see _register_context_budget_hooks
import session_lifecycle  # INFRA-323: RESTART REQUIRED notice + agent-surface stamp
from schema_validator import _parse_frontmatter
from state_utils import _atomic_write_json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAIRMODE_DEFAULT_RAILS = {
    "generic": ["CORE", "INFRA", "TEST"],
    "web": ["API", "UI", "DB", "AUTH", "INFRA", "TEST"],
    "cli": ["CORE", "INFRA", "TEST"],
    "pairmode": ["BOOTSTRAP", "AUDIT", "RECONSTRUCT", "LESSON", "BUILD", "TEMPLATE", "AGENT", "INFRA"],
}

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"

# Mapping: destination path (relative to project_dir) → template name
# None as the template value means the file is written from a hard-coded
# skeleton string (phase-prompts.md and checkpoints.md are plain skeletons
# that the templates directory already provides as .j2 files).
SCAFFOLD_FILES: list[tuple[str, str]] = [
    ("CLAUDE.md", "CLAUDE.md.j2"),
    ("CLAUDE.build.md", "CLAUDE.build.md.j2"),
    (".pairmode-overrides", ".pairmode-overrides.j2"),
    ("docs/brief.md", "docs/brief.md.j2"),
    ("docs/ideology.md", "docs/ideology.md.j2"),
    ("docs/reconstruction.md", "docs/reconstruction.md.j2"),
    ("docs/architecture.md", "docs/architecture.md.j2"),
    ("docs/checkpoints.md", "docs/checkpoints.md.j2"),
    ("docs/cer/backlog.md", "docs/cer/backlog.md.j2"),
]

# Agent files — skipped if they already exist, unless --force-agents is passed.
# These are treated as project-owned after first bootstrap.
# Note: builder.md.j2, reviewer.md.j2, loop-breaker.md.j2, security-auditor.md.j2,
# and intent-reviewer.md.j2 were retired in HARNESS-002 (dogfood flip) and
# re-registered in INFRA-241 (see below) — HARNESS-002's shared-procedure design
# is preserved (each shell's body is only the "Shell instruction" already
# documented in its corresponding procedure.md; no role logic is duplicated
# into the agent file), but a real, matchable `subagent_type` string is
# required for the context-budget PreToolUse gate (INFRA-199) to ever fire —
# without a registered custom agent type, spawns for these five roles have no
# `subagent_type` to resolve to and the gate falls through as a no-op for
# every real build-cycle spawn.
#
# gate-worker.md.j2 is included (RELEASE-010): the resolver emits spawn-gate-worker for
# stories with schema_introduces/auth_gated true; without this shell the orchestrator has
# no dispatch path for that action.  The shell references skills/pairmode/gate_worker/SKILL.md
# (relative to project root) which is present in any project bootstrapped from this harness.
#
# builder.md.j2, reviewer.md.j2, loop-breaker.md.j2, security-auditor.md.j2, and
# intent-reviewer.md.j2 (INFRA-241): thin shells whose body loads the matching
# skills/pairmode/skills/<role>/procedure.md and defers all judgment/implementation
# logic to it. Deployed to every newly-bootstrapped and re-synced project so the
# fleet-wide context-budget gate (INFRA-199) has a real subagent_type to match on.
#
# docs-reviewer.md.j2 (INFRA-325): an eighth thin shell, mirroring the same pattern
# over skills/pairmode/skills/checkpoint-docs/procedure.md (WORKER-011). Before this
# story the role was fully specced (procedure skill + architecture.md/README.md
# references) but never scaffolded — this list must stay mirrored with
# CANONICAL_FILES in audit.py.
#
# spec-writer.md.j2 (INFRA-331, CER-137/AG-13): a ninth thin shell, over
# skills/pairmode/skills/spec-writer/procedure.md (WORKER-013). Before this
# story next_action.py's Row-2 already emitted spawn-spec-writer (model=opus,
# reason="needs-spec") for any stub story and the procedure skill was fully
# specced, but no template existed to scaffold the role — this list must
# stay mirrored with CANONICAL_FILES in audit.py.
AGENT_FILES: list[tuple[str, str]] = [
    (".claude/agents/reconstruction-agent.md", "agents/reconstruction-agent.md.j2"),
    (".claude/agents/gate-worker.md", "agents/gate-worker.md.j2"),
    (".claude/agents/builder.md", "agents/builder.md.j2"),
    (".claude/agents/reviewer.md", "agents/reviewer.md.j2"),
    (".claude/agents/loop-breaker.md", "agents/loop-breaker.md.j2"),
    (".claude/agents/security-auditor.md", "agents/security-auditor.md.j2"),
    (".claude/agents/intent-reviewer.md", "agents/intent-reviewer.md.j2"),
    (".claude/agents/docs-reviewer.md", "agents/docs-reviewer.md.j2"),
    (".claude/agents/spec-writer.md", "agents/spec-writer.md.j2"),
    # shadow-reviewer.md (INFRA-358): tenth thin shell, added alongside the
    # role's procedure skill and template — the dispatch action, model
    # selector, and escalation wiring (checklist items 3-5) are INFRA-359's
    # job; this scaffold-only entry covers items 1-2.
    (".claude/agents/shadow-reviewer.md", "agents/shadow-reviewer.md.j2"),
]

# INFRA-351: the nine harness-role narratives (the build-loop roles themselves —
# BUILDER, REVIEWER, LOOP-BREAKER, SECURITY-AUDITOR, INTENT-REVIEWER,
# DOCS-REVIEWER, GATE-WORKER, SPEC-WRITER, ORCHESTRATOR) describe the harness,
# not any one project, and so are harness-owned, templated, and scaffolded like
# every other file in this module rather than hand-authored per project — the
# same "harness-owned, templated, never hand-diverged" contract AGENT_FILES
# already establishes for `.claude/agents/*.md`. OPERATOR's narrative is
# handled separately (a seed-then-extend mechanism, INFRA-353) and is
# deliberately not in this list. A `sync-narratives` command for
# already-bootstrapped projects is out of scope here (INFRA-352), as is
# backfilling flex's own `docs/narratives/` from these templates (INFRA-354).
NARRATIVE_FILES: list[tuple[str, str]] = [
    ("docs/narratives/BUILDER/BUILDER-000-ideology.md", "narratives/BUILDER/BUILDER-000-ideology.md.j2"),
    ("docs/narratives/REVIEWER/REVIEWER-000-ideology.md", "narratives/REVIEWER/REVIEWER-000-ideology.md.j2"),
    ("docs/narratives/LOOP-BREAKER/LOOP-BREAKER-000-ideology.md", "narratives/LOOP-BREAKER/LOOP-BREAKER-000-ideology.md.j2"),
    ("docs/narratives/SECURITY-AUDITOR/SECURITY-AUDITOR-000-ideology.md", "narratives/SECURITY-AUDITOR/SECURITY-AUDITOR-000-ideology.md.j2"),
    ("docs/narratives/INTENT-REVIEWER/INTENT-REVIEWER-000-ideology.md", "narratives/INTENT-REVIEWER/INTENT-REVIEWER-000-ideology.md.j2"),
    ("docs/narratives/DOCS-REVIEWER/DOCS-REVIEWER-000-ideology.md", "narratives/DOCS-REVIEWER/DOCS-REVIEWER-000-ideology.md.j2"),
    ("docs/narratives/GATE-WORKER/GATE-WORKER-000-ideology.md", "narratives/GATE-WORKER/GATE-WORKER-000-ideology.md.j2"),
    ("docs/narratives/SPEC-WRITER/SPEC-WRITER-000-ideology.md", "narratives/SPEC-WRITER/SPEC-WRITER-000-ideology.md.j2"),
    ("docs/narratives/ORCHESTRATOR/ORCHESTRATOR-000-ideology.md", "narratives/ORCHESTRATOR/ORCHESTRATOR-000-ideology.md.j2"),
]

# INFRA-353: OPERATOR's seed narrative is scaffolded through the same
# _render_template/_write_file pipeline as NARRATIVE_FILES (so it appears at
# fresh bootstrap "like the other nine" from the operator's point of view),
# but is deliberately kept out of that shared list (docs/architecture.md §
# Harness-role narratives: NARRATIVE_FILES) — unlike the nine harness-role
# narratives, OPERATOR's seed is generic ("a" typical operator, not "the"
# harness's own role) and is meant to be extended per-project via a separate,
# numbered `OPERATOR-010`-and-onward extension file. The seed itself is never
# hand-edited; only the extension file (written below, from the operator's
# free-text prompt answer) diverges per project.
OPERATOR_SEED_FILE: tuple[str, str] = (
    "docs/narratives/OPERATOR/OPERATOR-000-ideology.md",
    "narratives/OPERATOR/OPERATOR-000-ideology.md.j2",
)

# INFRA-355: the ten known narrative role names — the nine harness roles
# (derived from NARRATIVE_FILES's destination paths, "docs/narratives/<ROLE>/...")
# plus OPERATOR (handled separately via OPERATOR_SEED_FILE, but still a valid
# role name a story's `narrative_roles:` frontmatter may cite). This is the
# single source of truth for the role-name vocabulary; do not hand-duplicate
# this list elsewhere (schema_validator.py's narrative_roles validation
# imports this constant, deferred to call time to avoid the circular import
# this module already has with schema_validator.py — see
# schema_validator._valid_narrative_roles's docstring).
NARRATIVE_ROLES: frozenset[str] = frozenset(
    {dest.split("/")[2] for dest, _ in NARRATIVE_FILES} | {"OPERATOR"}
)

# Default deny list written into .claude/settings.json.
# Kept minimal — scope_guard.py (Phase 55) enforces per-story file scope at
# the hook level. Only the permissions files directory is hard-denied here to
# prevent builders from self-modifying their own scope declarations.
DEFAULT_DENY: list[str] = [
    "Edit(docs/phases/permissions/**)",
]

# Entries removed from DEFAULT_DENY in Phase 55. Kept here so sync.py can
# prune them from existing projects' settings.json on next sync.
_SUPERSEDED_DENY_ENTRIES: list[str] = [
    "Edit(CLAUDE.md)",
    "Write(CLAUDE.md)",
    "Edit(CLAUDE.build.md)",
    "Write(CLAUDE.build.md)",
    "Edit(.claude/agents/**)",
    "Write(.claude/agents/**)",
    "Edit(docs/architecture.md)",
    "Write(docs/architecture.md)",
    "Edit(docs/phases/**)",
    "Write(docs/phases/**)",
    "Edit(docs/brief.md)",
    "Write(docs/brief.md)",
    "Edit(docs/ideology.md)",
    "Write(docs/ideology.md)",
    "Edit(docs/reconstruction.md)",
    "Write(docs/reconstruction.md)",
    "Edit(docs/RECONSTRUCTION.md)",
    "Write(docs/RECONSTRUCTION.md)",
]

# Standard build-tool allow rules written into .claude/settings.local.json
PAIRMODE_ALLOW: list[str] = [
    "Bash(uv run *)",
    "Bash(git *)",
    "Bash(python3 *)",
    "Bash(grep *)",
]

# Universal checklist items always included in templates
UNIVERSAL_CHECKLIST_ITEMS: list[dict] = [
    {
        "name": "PROTECTED FILES",
        "description": "Were any protected files modified without a stated reason?",
        "severity": "HIGH",
    },
    {
        "name": "STORY SCOPE",
        "description": "Did the builder touch files outside the stated story scope?",
        "severity": "MEDIUM",
    },
    {
        "name": "BUILD GATE",
        "description": "Does the build command pass without errors?",
        "severity": "CRITICAL",
    },
    {
        "name": "IDEOLOGY ALIGNMENT",
        "description": "Does this implementation express the project ideology? Check docs/ideology.md.",
        "severity": "HIGH",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_build_command(project_dir: pathlib.Path) -> str | None:
    """Return a build command inferred from files present in project_dir."""
    if (project_dir / "pnpm-lock.yaml").exists() or (project_dir / "pnpm-workspace.yaml").exists():
        return "pnpm build && pnpm typecheck"
    if (project_dir / "pyproject.toml").exists() or (project_dir / "uv.lock").exists():
        return "uv run pytest"
    return None


def _validate_test_command(test_command: str, stack: str) -> list[str]:
    """Return a list of warning strings; empty list means no concerns."""
    warnings: list[str] = []
    if ("pytest" in test_command or "uv run" in test_command) and "python" not in stack.lower():
        warnings.append(
            f"test_command looks like a Python toolchain ({test_command!r}) but stack does not"
            f" mention Python ({stack!r}) — likely a bootstrap default that should be overridden."
        )
    return warnings


def _render_template(template_name: str, context: dict) -> str:
    loader = jinja2.FileSystemLoader(str(TEMPLATES_DIR))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_name)
    return template.render(**context)


def _write_file(
    dest: pathlib.Path,
    content: str,
    dry_run: bool,
    yes: bool = False,
) -> bool:
    """
    Write *content* to *dest*.

    Returns True if the file was (or would be, in dry-run mode) written.
    If the file already exists and this is not a dry-run, prompts the user
    for confirmation before overwriting (unless *yes* is True).
    """
    if dry_run:
        click.echo(f"  [dry-run] would write: {dest}")
        return True

    if dest.exists() and not yes:
        overwrite = click.confirm(
            f"  {dest} already exists. Overwrite?", default=False
        )
        if not overwrite:
            click.echo(f"  skipped: {dest}")
            return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    click.echo(f"  wrote: {dest}")
    return True


def _glob_prefix(entry: str) -> tuple[str, str] | None:
    """If *entry* is a glob pattern like ``Tool(prefix/**)`` return ``(Tool, prefix/)``.

    Returns None for non-glob entries (no ``**`` suffix).
    """
    if not entry.endswith("/**)") and not entry.endswith("/**"):
        return None
    paren = entry.index("(")
    tool = entry[:paren]
    inner = entry[paren + 1 : -1]  # strip ( and )
    if inner.endswith("/**"):
        prefix = inner[: -len("/**")] + "/"
        return tool, prefix
    return None


def _is_subsumed(entry: str, globs: list[tuple[str, str]]) -> bool:
    """Return True if *entry* is already covered by one of *globs*.

    *globs* is a list of ``(tool, prefix/)`` pairs produced by ``_glob_prefix``.
    An entry ``Tool(path)`` is subsumed when there exists a glob with the same
    tool whose prefix is a proper prefix of ``path``.
    """
    paren = entry.find("(")
    if paren == -1:
        return False
    tool = entry[:paren]
    inner = entry[paren + 1 : -1]
    for g_tool, g_prefix in globs:
        if g_tool == tool and inner.startswith(g_prefix):
            return True
    return False


def _merge_deny_list(settings_path: pathlib.Path, new_entries: list[str]) -> None:
    """
    Merge *new_entries* into the permissions.deny array in settings_path.

    Creates the file if it does not exist.  Existing entries are preserved;
    duplicates are not added.  Existing entries that are subsumed by a new
    glob pattern (e.g. ``Edit(hooks/stop.py)`` subsumed by ``Edit(hooks/**)``)
    are removed to avoid redundancy.
    """
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    permissions = data.setdefault("permissions", {})
    deny: list[str] = permissions.get("deny", [])

    # Collect glob prefixes from the incoming new_entries so we can prune
    # existing specific entries that are now subsumed.
    incoming_globs: list[tuple[str, str]] = []
    for entry in new_entries:
        gp = _glob_prefix(entry)
        if gp:
            incoming_globs.append(gp)

    # Drop existing entries that are subsumed by an incoming glob.
    deny = [e for e in deny if not _is_subsumed(e, incoming_globs)]

    for entry in new_entries:
        if entry not in deny:
            deny.append(entry)

    permissions["deny"] = deny
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def _prune_superseded_deny_entries(
    settings_path: pathlib.Path,
    entries_to_remove: list[str],
) -> None:
    """Remove deny entries that are no longer in DEFAULT_DENY from settings_path.

    Idempotent: entries already absent are silently skipped.
    Preserves any custom deny entries not in entries_to_remove.
    """
    if not settings_path.exists():
        return
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    permissions = data.get("permissions", {})
    deny: list[str] = permissions.get("deny", [])

    to_remove = set(entries_to_remove)
    new_deny = [e for e in deny if e not in to_remove]

    if new_deny == deny:
        return  # nothing to prune

    permissions["deny"] = new_deny
    data["permissions"] = permissions
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


# Canonical combined PreToolUse matcher for downstream (non-plugin) bootstrap
# registration. Mirrors the three dispatch families pre_tool_use.py routes on
# (Task|Agent → context_budget.py, Edit|Write → scope_guard.py, Read →
# cold_read_guard.py) — see CER-065 / INFRA-205 for the hooks.json counterpart
# and INFRA-206 for this downstream-registrar widening.
PRETOOLUSE_MATCHER = "Task|Agent|Edit|Write|Read"


def _find_block_by_command_basename(
    block_list: list[dict], basename: str
) -> tuple[dict, dict] | None:
    """Find the (block, inner-hook-entry) pair whose command's final path
    segment equals *basename* (e.g. "pre_tool_use.py").

    Matches the full final path segment (``command.rsplit("/", 1)[-1]``) rather
    than a bare ``endswith`` so a different file sharing a suffix (e.g.
    ``my_pre_tool_use.py``) cannot false-positive. Used to locate a stale hook
    entry whose basename matches but whose full path points at a different
    plugin_root (a 0.2.0 -> 0.3.0 migration), so it can be migrated in place
    instead of duplicated. Returns None if no entry matches.
    """
    for block in block_list:
        for entry in block.get("hooks", []):
            command = entry.get("command")
            if isinstance(command, str) and command.rsplit("/", 1)[-1] == basename:
                return block, entry
    return None


def _find_all_entries_by_command_basename(
    block_list: list[dict], basename: str
) -> list[tuple[dict, dict]]:
    """Find every (block, inner-hook-entry) pair whose command's final path
    segment equals *basename* (e.g. "pre_tool_use.py"), in document order.

    Same full-segment match discipline as _find_block_by_command_basename
    (``command.rsplit("/", 1)[-1] == basename``, not ``endswith``), but returns
    every match rather than just the first. Used by _prune_stale_hook_entries
    to locate all stale same-basename entries across sibling blocks (CER-081)
    — the state _find_block_by_command_basename's "first match" semantics
    cannot see once a correct entry already exists alongside a stale one.
    Returns [] when no entry matches.
    """
    matches: list[tuple[dict, dict]] = []
    for block in block_list:
        for entry in block.get("hooks", []):
            command = entry.get("command")
            if isinstance(command, str) and command.rsplit("/", 1)[-1] == basename:
                matches.append((block, entry))
    return matches


def _prune_stale_hook_entries(
    block_list: list[dict], basename: str, keep_command: str
) -> int:
    """Remove every inner hook entry in *block_list* whose command basename
    equals *basename* and whose command is not *keep_command* (CER-081).

    Removes any block left with an empty ``hooks`` list afterward. Mutates
    *block_list* in place (both call sites hold it via
    ``hooks_top.setdefault(...)``) and returns the number of entries removed.
    Never removes an entry whose basename differs from *basename*, and skips
    non-dict blocks or non-list ``hooks`` values rather than raising — a
    hand-edited settings file must not crash the registrar.
    """
    removed = 0
    for block in block_list:
        if not isinstance(block, dict):
            continue
        inner_hooks = block.get("hooks")
        if not isinstance(inner_hooks, list):
            continue
        kept: list[dict] = []
        for entry in inner_hooks:
            command = entry.get("command") if isinstance(entry, dict) else None
            if (
                isinstance(command, str)
                and command.rsplit("/", 1)[-1] == basename
                and command != keep_command
            ):
                removed += 1
                continue
            kept.append(entry)
        block["hooks"] = kept

    block_list[:] = [
        block
        for block in block_list
        if not (isinstance(block, dict) and isinstance(block.get("hooks"), list) and not block["hooks"])
    ]

    return removed


def _hook_settings_path(project_dir: pathlib.Path) -> pathlib.Path:
    """Single construction site for where a portable hook command is written
    (INFRA-319 / CER-127): the project's machine-local settings file, never
    the committed ``.claude/settings.json``. Both registrars and ``to-030``'s
    repair block (pairmode_migrate.py) call this — there is exactly one
    definition of the target file across the codebase.

    ``${CLAUDE_PLUGIN_ROOT}`` is not usable here: it is expanded by Claude
    Code only for commands declared in a *plugin's own* hooks.json, not for a
    project's settings file, so the command itself is still built as an
    absolute path resolved from plugin_root — only the destination file
    moves.
    """
    return project_dir / ".claude" / "settings.local.json"


def _ensure_gitignore_ignores_settings_local(project_dir: pathlib.Path) -> None:
    """A4 (INFRA-319): ensure ``.claude/settings.local.json`` is ignored by
    *this project's own* ``.gitignore`` — not by any developer's global
    ignore, which a fresh clone by another user will not have. Idempotent: a
    second run appends nothing. Creates ``.gitignore`` with just this entry
    when absent. A malformed or unreadable ``.gitignore`` is a silent skip,
    never an exception — this helper must stay total.
    """
    entry = ".claude/settings.local.json"
    gitignore_path = project_dir / ".gitignore"
    try:
        if gitignore_path.exists():
            text = gitignore_path.read_text(encoding="utf-8")
            if entry in text.splitlines():
                return
            if text and not text.endswith("\n"):
                text += "\n"
            text += entry + "\n"
            gitignore_path.write_text(text, encoding="utf-8")
        else:
            gitignore_path.parent.mkdir(parents=True, exist_ok=True)
            gitignore_path.write_text(entry + "\n", encoding="utf-8")
    except OSError:
        return


def _plugin_registered_hook_pairs(project_dir: pathlib.Path) -> set:
    """(event, basename) pairs already provided by an installed plugin's
    hooks.json, per the merged hook view (INFRA-288/CER-104). Shared by both
    registrars (INFRA-319 A1) so PreToolUse gets the same skip
    _register_context_budget_hooks already applied to the other four events.

    Best-effort: degrades to ``set()`` on any failure. Failing closed here
    (registering nothing) would leave a project with no gate hook at all,
    which is strictly worse than a duplicated one — see callers' docstrings.
    """
    try:
        return {
            (entry.get("event"), entry.get("basename"))
            for entry in hook_view.merged_hook_view(project_dir)
            if entry.get("source") == hook_view.HOOK_SOURCE_PLUGIN
        }
    except Exception:
        return set()


def _evict_stale_committed_hook_entries(
    committed_settings_path: pathlib.Path, event: str, basename: str
) -> int:
    """A7 (INFRA-319): remove any entry for (event, basename) left in the
    project's *committed* ``.claude/settings.json``, now that the correct
    entry is guaranteed to live in ``.claude/settings.local.json``.

    Callers must invoke this only **after** the correct entry has already
    been written to settings.local.json — the ordering is load-bearing: at
    no point does the project have zero registrations for this pair. Reuses
    ``_prune_stale_hook_entries``'s empty-block cleanup with a keep_command
    that can never match a real command, so every same-basename entry is
    evicted unconditionally. A missing, unparseable, or malformed-shape
    committed settings file is a no-op — never raises. Rewrites the file
    only when something was actually removed, so an unaffected project's
    committed settings.json stays byte-identical.
    """
    if not committed_settings_path.exists():
        return 0
    try:
        data = json.loads(committed_settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    hooks_top = data.get("hooks")
    if not isinstance(hooks_top, dict):
        return 0
    event_list = hooks_top.get(event)
    if not isinstance(event_list, list):
        return 0
    removed = _prune_stale_hook_entries(event_list, basename, "")
    if removed:
        committed_settings_path.write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
    return removed


def _register_pretooluse_hook(settings_path: pathlib.Path, plugin_root: pathlib.Path) -> bool:
    """Merge a PreToolUse hook entry into .claude/settings.local.json.

    Returns ``True`` when this call actually mutated the settings-level
    ``hooks`` registration (a new command entry was appended, the matcher was
    upgraded, or a stale sibling entry was pruned) — ``False`` for a pure
    idempotent no-op or the plugin-sourced skip (INFRA-323 § A/B: the caller
    uses this to decide whether the ``hook_registration`` restart surface
    changed).

    Registers the combined matcher PRETOOLUSE_MATCHER ("Task|Agent|Edit|Write|Read")
    covering all three pre_tool_use.py dispatch families (CER-065 / INFRA-206).

    Uses the absolute resolved path of pre_tool_use.py (computed from plugin_root,
    never from ${CLAUDE_PLUGIN_ROOT}). The target block is located by scanning for
    an inner hook entry whose command already matches (not by matcher string) so
    that a legacy "Task"-only block, a legacy "Task|Agent" block, or an
    already-migrated combined block are all found alike. If found, that block's
    matcher is upgraded in place to the canonical combined matcher (in-place
    migration — never orphaned as a dead sibling); if not found, a new block is
    appended. The command is added to the block's inner hooks only if not already
    present (idempotent).

    INFRA-319 (CER-127): *settings_path* is the project's **committed**
    ``.claude/settings.json`` path — kept as the parameter shape callers
    already pass (``<project>/.claude/settings.json``) so ``project_dir`` can
    be derived as ``settings_path.parent.parent`` — but the hook entry itself
    is written to ``.claude/settings.local.json`` (see _hook_settings_path):
    a machine-bound absolute path belongs in the machine-local file, never in
    the committed one. Any stale entry already in the committed file is
    evicted after the correct entry is guaranteed present (A7). Also gains
    the same plugin-source skip _register_context_budget_hooks already had
    (A1, INFRA-288/CER-104): a project that already gets PreToolUse from an
    installed plugin's hooks.json must not also get a settings-level entry.

    Creates the local settings file (and its .gitignore guard) if absent.
    """
    project_dir = settings_path.parent.parent
    local_settings_path = _hook_settings_path(project_dir)

    pre_tool_use_path = plugin_root / "hooks" / "pre_tool_use.py"
    command = f"uv run python {pre_tool_use_path}"

    plugin_registered = _plugin_registered_hook_pairs(project_dir)
    if ("PreToolUse", pre_tool_use_path.name) in plugin_registered:
        click.echo(
            "skipping PreToolUse registration for pre_tool_use.py: already "
            "registered by an installed plugin's hooks.json — a "
            "settings-level duplicate would run the hook twice per event "
            "(INFRA-288/CER-104, CER-127)"
        )
        return False

    if local_settings_path.exists():
        try:
            data = json.loads(local_settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    # A hand-edited settings file may hold a malformed "hooks" shape (not a
    # dict) or event value (not a list). Treat either as absent rather than
    # crashing (Ensures 10).
    if not isinstance(data.get("hooks"), dict):
        data["hooks"] = {}
    hooks_top = data["hooks"]
    if not isinstance(hooks_top.get("PreToolUse"), list):
        hooks_top["PreToolUse"] = []
    pre_tool_use_list: list[dict] = hooks_top["PreToolUse"]

    # Find the block carrying our command, by command — not by matcher string.
    # This finds a legacy "Task" block, a legacy "Task|Agent" block, or an
    # already-migrated combined block alike, so widening the matcher never
    # breaks idempotency on subsequent runs.
    target_block: dict | None = None
    for block in pre_tool_use_list:
        inner_hooks: list[dict] = block.get("hooks", [])
        if any(h.get("command") == command for h in inner_hooks):
            target_block = block
            break

    if target_block is None:
        # Fallback: a stale entry whose basename matches but whose full path
        # points at a different plugin_root (a 0.2.0 -> 0.3.0 migration). Migrate
        # its command in place rather than appending a duplicate block.
        basename_match = _find_block_by_command_basename(
            pre_tool_use_list, pre_tool_use_path.name
        )
        if basename_match is not None:
            target_block, stale_entry = basename_match
            stale_entry["command"] = command

    if target_block is None:
        target_block = {"matcher": PRETOOLUSE_MATCHER, "hooks": []}
        pre_tool_use_list.append(target_block)

    # Migrate the matcher in place (idempotent when already canonical).
    matcher_changed = target_block.get("matcher") != PRETOOLUSE_MATCHER
    target_block["matcher"] = PRETOOLUSE_MATCHER

    inner_hooks = target_block.setdefault("hooks", [])

    # Idempotency: only add if no entry with this command already exists
    already_registered = any(
        h.get("command") == command for h in inner_hooks
    )
    if not already_registered:
        inner_hooks.append({"type": "command", "command": command})

    # Remove any stale same-basename sibling entries (CER-081): the correct
    # entry is guaranteed present above, so pruning here can never leave the
    # event with zero flex hooks.
    pruned = _prune_stale_hook_entries(pre_tool_use_list, pre_tool_use_path.name, command)

    local_settings_path.parent.mkdir(parents=True, exist_ok=True)
    local_settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    _ensure_gitignore_ignores_settings_local(project_dir)

    # A7: evict any stale entry left in the committed settings.json now that
    # the correct entry is guaranteed present above — ordering is
    # load-bearing (never zero registrations for this pair in between).
    _evict_stale_committed_hook_entries(settings_path, "PreToolUse", pre_tool_use_path.name)

    return bool((not already_registered) or matcher_changed or pruned)


# Load-bearing context-budget-gate hooks that must be registered downstream
# alongside PreToolUse (CER-067): without these three, context_budget_user_turn_seq
# never increments (INFRA-192 UserPromptSubmit), context_current_tokens never
# resets on /clear (SessionStart), and context_current_tokens is never written
# from a live transcript read (INFRA-182 PostToolUse Task|Agent). Each entry is a
# thin, safe-to-blanket-register dispatcher that no-ops when the project is not a
# pairmode repo.
#
# Deliberately NOT included here (INFRA-208): Stop, PermissionRequest/
# ExitPlanMode, PostToolUse Write|Edit|MultiEdit, SessionEnd. These four are
# companion-sidebar relays, not part of context-budget-gate correctness; whether
# a downstream project runs the companion sidebar is a separate product
# decision, deferred as a future opt-in story rather than folded into this
# correctness fix.
#
# INFRA-298 (CER-114): SubagentStop is added here despite this tuple's
# "context-budget" name — it is not a context-budget-gate hook, it is the
# effort-completion relay (subagent_stop.py -> reconcile_one). It is added to
# THIS tuple anyway, not a new one, because the load-bearing property this
# story needs is the registrar mechanism, not the name: a spec listed here
# automatically inherits the INFRA-288/CER-104 plugin-already-registered skip
# (below), so a project that gets SubagentStop from an installed plugin's
# hooks.json gains no duplicate settings-level entry. Without this entry, a
# project consuming pairmode via a settings-level (non-plugin) install would
# get no SubagentStop registration at all, and every async spawn's effort.db
# row would stay pending until the quiescence backstop or a later session's
# sweep — exactly the CER-114 gap this story exists to close. Matcher is
# None, matching hooks.json's own SubagentStop block (no matcher — it is not
# a tool-scoped event).
CONTEXT_BUDGET_HOOK_SPECS: tuple[dict, ...] = (
    {"event": "UserPromptSubmit", "hook_file": "hooks/user_prompt_submit.py", "matcher": None},
    {"event": "SessionStart", "hook_file": "hooks/session_start.py", "matcher": None},
    {"event": "PostToolUse", "hook_file": "hooks/post_tool_use.py", "matcher": "Task|Agent"},
    {"event": "SubagentStop", "hook_file": "hooks/subagent_stop.py", "matcher": None},
)


def _register_context_budget_hooks(settings_path: pathlib.Path, plugin_root: pathlib.Path) -> bool:
    """Merge the four load-bearing context-budget-gate hook entries into
    .claude/settings.local.json (INFRA-208; see CER-067, INFRA-192, INFRA-175, INFRA-182).

    Returns ``True`` when at least one spec's registration was actually new
    (added, or a stale sibling entry was pruned) — ``False`` for a fully
    idempotent no-op run (INFRA-323 § A/B: the ``hook_registration`` restart
    surface only changed when this returns ``True``).

    Registers UserPromptSubmit and SessionStart with no matcher (they fire
    unconditionally per event in hooks.json) and PostToolUse Task|Agent as a
    sibling block alongside any pre-existing PostToolUse block for a different
    command (e.g. a local pytest-runner hook) — never merged into or replacing it.

    Mirrors _register_pretooluse_hook's by-command find/migrate idempotency: the
    target block for each event is located by scanning for an inner hook entry
    whose command already matches the computed absolute command, not by matcher
    or event name alone. If found, that block is reused (and its matcher set in
    place); if not found, a new block is appended. The command is added to a
    block's inner hooks only if not already present.

    Reads the file once, mutates all four events, and writes once (trailing
    newline, json.dumps(..., indent=2)). Creates the file if it does not exist.

    INFRA-288 (CER-104): a spec is SKIPPED (with one line saying so) when the
    merged hook view already reports a **plugin-sourced** entry for the same
    (event, command-basename) pair — a project that gets the hook from an
    installed plugin must carry no settings-level entry for it, or the hook
    fires twice per event and every effort row is written twice (the CER-104
    duplicate-pair shape). If the merged view cannot be computed, registration
    proceeds as before: failing closed here would leave a project with *no*
    recording hook, which is strictly worse than a duplicated one.

    INFRA-319 (CER-127): *settings_path* is the project's **committed**
    ``.claude/settings.json`` path — kept as the parameter shape callers
    already pass so ``project_dir`` can be derived as
    ``settings_path.parent.parent`` — but every entry is written to
    ``.claude/settings.local.json`` (see _hook_settings_path); any stale
    entry already in the committed file for a spec actually registered this
    run is evicted afterward (A7).
    """
    project_dir = settings_path.parent.parent
    local_settings_path = _hook_settings_path(project_dir)

    if local_settings_path.exists():
        try:
            data = json.loads(local_settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    # A hand-edited settings file may hold a malformed "hooks" shape (not a
    # dict) or event value (not a list). Treat either as absent rather than
    # crashing (Ensures 10).
    if not isinstance(data.get("hooks"), dict):
        data["hooks"] = {}
    hooks_top = data["hooks"]

    # INFRA-288: (event, basename) pairs already registered by an installed
    # plugin's hooks.json. Best-effort — see the docstring for why a failure
    # here must degrade to "register as today", never to "register nothing".
    plugin_registered = _plugin_registered_hook_pairs(project_dir)

    registered_this_run: list[tuple[str, str]] = []
    any_change = False

    for spec in CONTEXT_BUDGET_HOOK_SPECS:
        hook_path = plugin_root / spec["hook_file"]
        command = f"uv run python {hook_path}"
        matcher = spec["matcher"]

        if (spec["event"], hook_path.name) in plugin_registered:
            click.echo(
                f"skipping {spec['event']} registration for {hook_path.name}: "
                "already registered by an installed plugin's hooks.json — a "
                "settings-level duplicate would run the hook twice per event "
                "(INFRA-288, CER-104)"
            )
            continue

        if not isinstance(hooks_top.get(spec["event"]), list):
            hooks_top[spec["event"]] = []
        event_list: list[dict] = hooks_top[spec["event"]]

        # Find the block by command, not by matcher/event alone — see
        # _register_pretooluse_hook for the same discipline. This preserves
        # any pre-existing sibling block for an unrelated command (e.g. a
        # local pytest-runner PostToolUse hook) untouched.
        target_block: dict | None = None
        for block in event_list:
            inner_hooks: list[dict] = block.get("hooks", [])
            if any(h.get("command") == command for h in inner_hooks):
                target_block = block
                break

        if target_block is None:
            # Fallback: a stale entry whose basename matches but whose full path
            # points at a different plugin_root (a 0.2.0 -> 0.3.0 migration).
            # The basename check itself isolates this event's hook from any
            # unrelated sibling block (a different basename entirely). Migrate
            # the command in place rather than appending a duplicate block.
            basename_match = _find_block_by_command_basename(
                event_list, hook_path.name
            )
            if basename_match is not None:
                target_block, stale_entry = basename_match
                stale_entry["command"] = command

        if target_block is None:
            target_block = {"hooks": []}
            if matcher is not None:
                target_block["matcher"] = matcher
            event_list.append(target_block)

        if matcher is not None:
            target_block["matcher"] = matcher

        inner_hooks = target_block.setdefault("hooks", [])
        already_registered = any(h.get("command") == command for h in inner_hooks)
        if not already_registered:
            inner_hooks.append({"type": "command", "command": command})

        # Remove any stale same-basename sibling entries for this event
        # (CER-081). The basename isolates this event's hook from unrelated
        # sibling blocks (a different basename entirely).
        pruned = _prune_stale_hook_entries(event_list, hook_path.name, command)

        if (not already_registered) or pruned:
            any_change = True

        registered_this_run.append((spec["event"], hook_path.name))

    local_settings_path.parent.mkdir(parents=True, exist_ok=True)
    local_settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    _ensure_gitignore_ignores_settings_local(project_dir)

    # A7: evict any stale committed-settings.json entry for every (event,
    # basename) pair actually registered above — never for a spec that was
    # skipped (a plugin-sourced entry already covers it and this run wrote
    # nothing local to guarantee as a replacement).
    for event, basename in registered_this_run:
        _evict_stale_committed_hook_entries(settings_path, event, basename)

    return any_change


def _merge_allow_rules(settings_path: pathlib.Path, new_entries: list[str]) -> None:
    """
    Merge *new_entries* into the permissions.allow array in settings_path.

    Creates the file if it does not exist.  Existing entries are preserved;
    duplicates are not added.  No glob-subsumption pruning is applied — allow
    rules accumulate without removal of existing entries.
    """
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    permissions = data.setdefault("permissions", {})
    allow: list[str] = permissions.get("allow", [])

    for entry in new_entries:
        if entry not in allow:
            allow.append(entry)

    permissions["allow"] = allow
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def _print_next_steps(project_dir: pathlib.Path, repo_root: pathlib.Path) -> None:
    """Print the recommended follow-on actions after a successful bootstrap."""
    click.echo("\n## Next steps\n")
    click.echo(f"  1. Create and set your first story:")
    click.echo(
        f"       uv run python skills/pairmode/scripts/story_new.py \\\n"
        f"         --rail RAIL --title \"My first story\" --project-dir {project_dir}\n"
        f"       uv run python skills/pairmode/scripts/story_context.py --set RAIL-001 \\\n"
        f"         --project-dir {project_dir}\n"
    )
    click.echo(f"  2. Register this project with flex for drift tracking:")
    click.echo(f"       cd {repo_root}")
    click.echo(
        f"       uv run python skills/pairmode/scripts/pairmode_sync.py register \\\n"
        f"         --project-dir {project_dir}\n"
    )
    click.echo(f"  3. Run an audit to verify the scaffold:")
    click.echo(
        f"       uv run python skills/pairmode/scripts/audit.py --project-dir {project_dir}"
    )


def _load_seed_expected_step_tokens() -> int:
    """Return the thin-harness per-step context growth constant (CER-053).

    No longer reads the effort baseline seed. Returns THIN_HARNESS_STEP_TOKENS
    — the dispatch loop's per-step context growth. Side-effect-free.
    """
    return THIN_HARNESS_STEP_TOKENS


def _record_state(
    state_path: pathlib.Path,
    version: str,
    *,
    restart_changed: "list[str] | None" = None,
    restart_action: str = "bootstrap",
) -> bool:
    """Write pairmode_version into .companion/state.json, creating if absent.

    INFRA-323 § B11: when *restart_changed* is non-empty, the § A6
    ``agent_surfaces_written_at`` / ``agent_surfaces_written_by`` stamp is
    folded into this same write — no second write of state.json.

    Pairmode bootstraps also auto-enable ``effort_tracking`` so the
    orchestrator's per-attempt recorder will start writing rows immediately.
    Plain flex (non-pairmode) bootstraps leave the flag unset; only this
    pairmode-specific bootstrap sets it.  An existing ``effort_tracking``
    field (e.g. user explicitly set it to ``false``) is preserved.

    For NEW state.json files (file did not exist before this call), the
    context-budget defaults from INFRA-127 are also seeded:
    ``context_budget_threshold``, ``context_budget_overrun_pct``,
    ``expected_step_tokens`` (from the effort baseline seed), and
    ``context_budget_reprompt_margin``. Existing state.json files are NOT
    modified — these defaults are only added for fresh projects.

    Returns ``True`` if ``effort_tracking`` was newly set (was absent before
    this call), ``False`` if it was already present.
    """
    is_new_state = not state_path.exists()
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    data["pairmode_version"] = version
    newly_enabled = "effort_tracking" not in data
    if newly_enabled:
        data["effort_tracking"] = True

    if restart_changed:
        session_lifecycle.stamp_agent_surfaces(
            data, changed=restart_changed, action=restart_action
        )

    # INFRA-127: seed context-budget defaults only for NEW state.json files.
    # Existing state.json files are left untouched per spec.
    # INFRA-174: also seed context_current_tokens=1 so the very first build
    # step passes the budget check without requiring a manual set-context-tokens
    # call. Value 1 passes the value <= 0 guard; the orchestrator's
    # set-context-tokens call replaces it before the first real build step.
    # No recorded_at is seeded — a missing timestamp skips the staleness check,
    # which is correct here.
    if is_new_state:
        data.setdefault("context_budget_threshold", 120000)
        data.setdefault("context_budget_overrun_pct", 0.10)
        data.setdefault("expected_step_tokens", _load_seed_expected_step_tokens())
        data.setdefault("context_budget_reprompt_margin", 10000)
        data.setdefault("context_current_tokens", 1)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(state_path, data)
    return newly_enabled


def _load_product_json(project_dir: pathlib.Path) -> dict:
    """Load .companion/product.json if it exists; return {} otherwise."""
    product_path = project_dir / ".companion" / "product.json"
    if product_path.exists():
        try:
            return json.loads(product_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _ideology_capture_flow() -> dict:
    """Prompt the developer for ideology content. Returns template context dict."""
    convictions: list[str] = []
    for i in range(1, 4):
        value = click.prompt(
            f"\nIdeology capture — core conviction #{i}\n"
            f"What does this project believe? (e.g. \"we prefer X over Y because Z\")\n"
            f"Enter conviction or press Enter to skip",
            default="",
            show_default=False,
        ).strip()
        if not value:
            break
        convictions.append(value)

    value_hierarchy_entry = click.prompt(
        "\nValue hierarchy — top entry\n"
        "When two values conflict, which wins?\n"
        "Enter or press Enter to skip",
        default="",
        show_default=False,
    ).strip()
    value_hierarchy = [value_hierarchy_entry] if value_hierarchy_entry else []

    constraint_rule = click.prompt(
        "\nAccepted constraint — most important rule\n"
        "What must this system never do?\n"
        "Enter constraint rule or press Enter to skip",
        default="",
        show_default=False,
    ).strip()
    constraints: list[dict] = []
    if constraint_rule:
        constraints.append({
            "name": "Constraint 1",
            "rule": constraint_rule,
            "protects": "_(to be filled in)_",
            "rationale": "_(to be filled in)_",
        })

    must_preserve_entry = click.prompt(
        "\nReconstruction — what must survive any implementation?\n"
        "Enter or press Enter to skip",
        default="",
        show_default=False,
    ).strip()
    must_preserve = [must_preserve_entry] if must_preserve_entry else []

    return {
        "convictions": convictions,
        "value_hierarchy": value_hierarchy,
        "constraints": constraints,
        "must_preserve": must_preserve,
    }


# ---------------------------------------------------------------------------
# Rail initialization helpers
# ---------------------------------------------------------------------------


def _infer_project_type(stack: str, project_name: str) -> str:
    """Infer project type from stack string and project name."""
    stack_lower = stack.lower()
    name_lower = project_name.lower()

    if "pairmode" in stack_lower or "pairmode" in name_lower:
        return "pairmode"

    web_keywords = {"web", "api", "ui", "flask", "django", "fastapi", "react", "vue"}
    if any(kw in stack_lower for kw in web_keywords):
        return "web"

    cli_keywords = {"cli", "terminal", "argparse", "click", "typer"}
    if any(kw in stack_lower for kw in cli_keywords):
        return "cli"

    return "generic"


def _build_era_001_content(
    project_name: str,
    rails: list[str],
    strategic_intent: str = "",
) -> str:
    """Build the content of docs/eras/001-initial.md."""
    name = f"{project_name} — Initial development"
    frontmatter = (
        "---\n"
        'id: "001"\n'
        f"name: {name}\n"
        "status: active\n"
        "---\n"
    )
    intent_body = strategic_intent.strip() if strategic_intent.strip() else "_(fill in)_"
    strategic_intent_section = f"\n## Strategic intent\n\n{intent_body}\n"
    rails_header = (
        "\n"
        "## Rails\n"
        "\n"
        "| Rail | Primary domain |\n"
        "|------|----------------|\n"
    )
    rails_rows = "".join(f"| {rail} | _(fill in)_ |\n" for rail in rails)

    phases_table = (
        "\n"
        "## Phases\n"
        "\n"
        "| Phase | Title | Status |\n"
        "|-------|-------|--------|\n"
    )

    return frontmatter + strategic_intent_section + rails_header + rails_rows + phases_table


def _initialize_rails(
    project_dir: pathlib.Path,
    context: dict,
    stack: str,
    dry_run: bool,
    ideology_skip: bool,
    yes: bool = False,
) -> None:
    """Initialize rail directories and Era 001 after scaffold write."""
    project_name = context.get("project_name", "project")
    project_type = _infer_project_type(stack, project_name)
    default_rails = PAIRMODE_DEFAULT_RAILS[project_type]

    # Determine confirmed rails
    skip_prompt = ideology_skip or yes or not sys.stdin.isatty()
    if skip_prompt:
        confirmed_rails = list(default_rails)
    else:
        click.echo(f"\nRail initialization (project type: {project_type})")
        click.echo("Suggested rails: " + ", ".join(default_rails))
        user_input = click.prompt(
            "Confirm rails (enter to accept, or type comma-separated list to override)",
            default="",
            show_default=False,
        ).strip()
        if user_input:
            confirmed_rails = [r.strip().upper() for r in user_input.split(",") if r.strip()]
        else:
            confirmed_rails = list(default_rails)

    if dry_run:
        for rail in confirmed_rails:
            click.echo(f"  [dry-run] would create: docs/stories/{rail}/")
        click.echo("  [dry-run] would create: docs/eras/001-initial.md")
        return

    # Create rail directories (idempotent)
    stories_dir = project_dir / "docs" / "stories"
    for rail in confirmed_rails:
        rail_dir = stories_dir / rail
        if rail_dir.exists():
            click.echo(f"  skipped (exists): docs/stories/{rail}/")
        else:
            rail_dir.mkdir(parents=True, exist_ok=True)
            click.echo(f"  created rail dir: docs/stories/{rail}/")

    # Create docs/eras/001-initial.md (idempotent)
    eras_dir = project_dir / "docs" / "eras"
    era_path = eras_dir / "001-initial.md"
    if era_path.exists():
        click.echo(f"  skipped (exists): docs/eras/001-initial.md")
    else:
        eras_dir.mkdir(parents=True, exist_ok=True)
        era_intent = context.get("era_intent", "")
        era_content = _build_era_001_content(project_name, confirmed_rails, era_intent)
        era_path.write_text(era_content, encoding="utf-8")
        click.echo(f"  created: docs/eras/001-initial.md")

    # Update Phase 1 manifest to set era: "001" frontmatter (if present, no era yet)
    phases_dir = project_dir / "docs" / "phases"
    phase1_candidates = list(phases_dir.glob("phase-1.md")) + list(phases_dir.glob("001-*.md"))
    for phase_file in phase1_candidates:
        try:
            content = phase_file.read_text(encoding="utf-8")
        except OSError:
            continue
        # Only prepend era frontmatter if no era field exists yet
        existing_fm = _parse_frontmatter(content)
        if existing_fm is None or "era" not in existing_fm:
            content = '---\nera: "001"\n---\n\n' + content
            phase_file.write_text(content, encoding="utf-8")
            click.echo(f"  updated: {phase_file.relative_to(project_dir)} — added era: \"001\"")
        break  # Only update the first found


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.command()
@click.option(
    "--project-dir",
    default=".",
    show_default=True,
    help="Target project directory.",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
)
@click.option("--project-name", default=None, help="Project name (prompted if omitted).")
@click.option("--stack", default=None, help="Technology stack (prompted if omitted).")
@click.option("--what", default=None, help="What the project produces (prompted if omitted; blank allowed).")
@click.option("--why", default=None, help="Why the project exists (prompted if omitted; blank allowed).")
@click.option(
    "--operator-note",
    default=None,
    help="How the operator wants to work with this build loop — priorities, review habits, "
    "risk tolerance (prompted if omitted; blank allowed). A non-blank answer is written to "
    "docs/narratives/OPERATOR/OPERATOR-010-project.md; blank writes no extension file.",
)
@click.option(
    "--build-command",
    default=None,
    help="Build/test command (inferred from project files if omitted, else prompted).",
)
@click.option(
    "--test-dir",
    default=None,
    help="Test-location convention for this project (e.g. tests/pairmode/, tests/). "
    "Defaults to tests/ if omitted -- the builder/reviewer procedure skills read this "
    "value from the project rendered CLAUDE.build.md rather than assuming a fixed layout.",
)
@click.option(
    "--phase-title",
    default=None,
    help="Title for the initial phase-1.md (prompted in TTY if omitted; blank allowed).",
)
@click.option(
    "--phase-goal",
    default=None,
    help="Goal for the initial phase-1.md (prompted in TTY if omitted; blank allowed).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be written without writing anything.",
)
@click.option(
    "--force-agents",
    is_flag=True,
    default=False,
    help="Overwrite existing agent files in .claude/agents/ even if already present.",
)
@click.option(
    "--ideology-skip",
    is_flag=True,
    default=False,
    help="Skip guided ideology capture; write placeholder ideology.md.",
)
@click.option(
    "--conviction",
    multiple=True,
    help="Core conviction (repeatable). Bypasses TTY prompt.",
)
@click.option(
    "--constraint",
    multiple=True,
    help="Key constraint rule (repeatable). Bypasses TTY prompt.",
)
@click.option(
    "--from-reconstruction",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to a reconstruction.md brief. Pre-populates ideology context.",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    default=False,
    help="Auto-confirm all prompts. Use for non-interactive/CI invocations.",
)
def bootstrap(
    project_dir: str,
    project_name: str | None,
    stack: str | None,
    what: str | None,
    why: str | None,
    operator_note: str | None,
    build_command: str | None,
    test_dir: str | None,
    phase_title: str | None,
    phase_goal: str | None,
    dry_run: bool,
    force_agents: bool,
    ideology_skip: bool,
    conviction: tuple[str, ...],
    constraint: tuple[str, ...],
    from_reconstruction: str | None,
    yes: bool,
) -> None:
    """Bootstrap a pairmode scaffold into PROJECT_DIR."""

    project_path = pathlib.Path(project_dir).resolve()

    # ------------------------------------------------------------------
    # 0. Security: path traversal containment guard
    # ------------------------------------------------------------------
    if not project_path.is_dir() or len(project_path.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {project_path}",
            err=True,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # 1. Gather values: CLI → product.json → prompt
    # ------------------------------------------------------------------
    product = _load_product_json(project_path)

    if project_name is None:
        project_name = product.get("project_name") or click.prompt("Project name")

    if stack is None:
        stack = click.prompt("Stack (e.g. Python / FastAPI / PostgreSQL)")

    if what is None:
        what = product.get("what") or (
            click.prompt("What does this project produce? (blank to skip)", default="")
            if sys.stdin.isatty() and not yes
            else ""
        )

    if why is None:
        why = product.get("why") or (
            click.prompt("Why does this project exist? (blank to skip)", default="")
            if sys.stdin.isatty() and not yes
            else ""
        )

    # Non-TTY/--yes warning: if what or why ended up blank, inform the user how to populate them.
    if (not sys.stdin.isatty() or yes) and (not what or not why):
        click.echo(
            "warning: non-interactive mode — docs/brief.md what/why left blank.\n"
            "         Pass --what and --why flags to populate, or edit docs/brief.md after bootstrap.",
            err=True,
        )

    # INFRA-353: operator seed-then-extend — one more free-text, blank-to-skip
    # prompt in the same style as what/why, above. A non-blank answer becomes
    # docs/narratives/OPERATOR/OPERATOR-010-project.md (written in step 4c,
    # below); a blank answer writes nothing — the OPERATOR-000 seed itself is
    # never touched by this prompt either way.
    if operator_note is None:
        operator_note = (
            click.prompt(
                "Anything specific about how you want to work with this build loop — "
                "priorities, review habits, risk tolerance? (blank to skip)",
                default="",
            )
            if sys.stdin.isatty() and not yes
            else ""
        )

    if build_command is None:
        inferred = _infer_build_command(project_path)
        if inferred:
            build_command = inferred
        else:
            build_command = click.prompt(
                "Build command (e.g. pnpm build && pnpm typecheck)"
            )

    if phase_title is None:
        phase_title = (
            click.prompt("Phase 1 title (blank to leave as placeholder)", default="")
            if sys.stdin.isatty() and not yes
            else ""
        )

    if phase_goal is None:
        phase_goal = (
            click.prompt("Phase 1 goal (blank to skip)", default="")
            if sys.stdin.isatty() and not yes
            else ""
        )

    # test_command is derived from build_command for now
    test_command = build_command

    # test_dir: the project's test-location convention. Defaults to "tests/" when
    # not supplied -- this is the per-project value the builder/reviewer procedure
    # skills read from CLAUDE.build.md's Build standards section instead of
    # hardcoding flex's own "tests/pairmode/" convention (INFRA-240).
    if not test_dir:
        test_dir = "tests/"

    # ------------------------------------------------------------------
    # 1a. Era strategic intent (BUILD-016)
    # ------------------------------------------------------------------
    if yes or not sys.stdin.isatty():
        era_intent = ""
    else:
        era_intent = click.prompt(
            "Era strategic intent — what is this project's initial era trying to accomplish?\n"
            "Enter a sentence or two, or press Enter to fill in later",
            default="",
            show_default=False,
        ).strip()

    # ------------------------------------------------------------------
    # 1b. Ideology context: --from-reconstruction → CLI flags → TTY prompt → non-TTY placeholder
    # ------------------------------------------------------------------
    if from_reconstruction is not None:
        click.echo(f"  Reading reconstruction brief: {from_reconstruction}")
        ideology_context: dict = _ideology_parser.parse_reconstruction_brief(
            _Path(from_reconstruction)
        )
        # Normalize constraints: parse_reconstruction_brief returns {name, rule} dicts
        # but ideology.md.j2 expects {name, rule, protects, rationale} — fill defaults.
        normalized_constraints = []
        for c in ideology_context.get("constraints", []):
            normalized_constraints.append({
                "name": c.get("name", "Unnamed constraint"),
                "rule": c.get("rule", ""),
                "protects": c.get("protects", "_(to be filled in)_"),
                "rationale": c.get("rationale", "_(to be filled in)_"),
                "override_path": c.get("override_path", "Document the exception in spec.json conflicts with a stated reason before proceeding."),
            })
        ideology_context["constraints"] = normalized_constraints
    elif conviction or constraint:
        # CLI flags provided — use them directly, skip prompting
        ideology_context = {
            "convictions": list(conviction),
            "value_hierarchy": [],
            "constraints": [
                {
                    "name": f"Constraint {i + 1}",
                    "rule": rule,
                    "protects": "_(to be filled in)_",
                    "rationale": "_(to be filled in)_",
                }
                for i, rule in enumerate(constraint)
            ],
            "must_preserve": [],
        }
    elif sys.stdin.isatty() and not ideology_skip and not yes:
        ideology_context = _ideology_capture_flow()
    else:
        ideology_context = {}
        if not ideology_skip and not yes:
            click.echo(
                "warning: non-interactive mode — docs/ideology.md will be written as "
                "placeholder.\n"
                "         Pass --conviction or --constraint flags to populate, "
                "or edit docs/ideology.md after bootstrap.",
                err=True,
            )

    # ------------------------------------------------------------------
    # 2. Derive spec-based checklist and deny list (if spec present)
    # ------------------------------------------------------------------
    companion_dir = project_path / ".companion"
    spec = _spec_reader.read_project_spec(companion_dir)

    if spec is not None:
        modules = spec["modules"]

        # Load module_paths from .companion/modules.json
        modules_json_path = companion_dir / "modules.json"
        if modules_json_path.exists():
            try:
                raw_modules = json.loads(modules_json_path.read_text(encoding="utf-8"))
                module_paths: dict[str, list[str]] = {
                    entry["name"]: entry.get("paths", [])
                    for entry in raw_modules
                    if "name" in entry
                }
            except (json.JSONDecodeError, KeyError):
                module_paths = {}
        else:
            module_paths = {}

        derived_checklist = _checklist_deriver.derive_checklist(modules)
        derived_denylist = _denylist_deriver.derive_denylist(modules, module_paths)
    else:
        derived_checklist = []
        derived_denylist = []

    # The effective deny list: spec-derived when available, static default otherwise.
    effective_deny = (
        [rule["path_pattern"] for rule in derived_denylist]
        if derived_denylist
        else DEFAULT_DENY
    )

    # ------------------------------------------------------------------
    # 3. Validate derived values before committing them to context
    # ------------------------------------------------------------------
    for _warn in _validate_test_command(test_command, stack):
        click.echo(f"warning: {_warn}", err=True)

    # ------------------------------------------------------------------
    # 4. Build template context
    # ------------------------------------------------------------------
    context: dict = {
        "project_name": project_name,
        "project_description": product.get("project_description", ""),
        "stack": stack,
        "what": what or "",
        "why": why or "",
        "core_beliefs": "",
        "accepted_tradeoffs": "",
        # brief.md.j2 expects a string; ideology.md.j2 expects a list — use separate keys.
        "must_preserve_str": "",   # newline-joined string for brief.md.j2
        "must_preserve": [],       # list form for ideology.md.j2
        "operator_contact": product.get("operator_contact", ""),
        "build_command": build_command,
        "test_command": test_command,
        "test_dir": test_dir,
        "migration_command": "",
        "pairmode_scripts_dir": str(pathlib.Path(__file__).parent),
        "domain_model": "",
        "checklist_items": derived_checklist,  # spec-derived only; universal items are hardcoded in templates
        "protected_paths": [],
        "covered_contracts": [],  # INFRA-317: doc-section::source-file pairs; empty-and-harmless default
        "non_negotiables": [],
        # architecture.md.j2 needs these; provide empty defaults
        "module_structure": [],
        "layer_rules": [],
        # agent templates need this
        "domain_isolation_rule": "",
        # CER backlog template variables
        "cer_entries": [],
        "last_updated": datetime.date.today().isoformat(),
        # ideology.md.j2 variables — all default to empty lists (renders placeholders)
        "convictions": ideology_context.get("convictions", []),
        "value_hierarchy": ideology_context.get("value_hierarchy", []),
        "constraints": ideology_context.get("constraints", []),
        "fingerprints": [],
        "should_question": ideology_context.get("should_question", []),
        "free_to_change": ideology_context.get("free_to_change", []),
        "comparison_dimensions": [],
        # reconstruction.md.j2 variables
        "reconstruction_what": what or "",
        "reconstruction_why": why or "",
        "generated_date": datetime.date.today().isoformat(),
        # BUILD-016: era strategic intent — threaded through to _build_era_001_content
        "era_intent": era_intent,
    }
    # Merge ideology_context must_preserve into context.
    # must_preserve (list) → ideology.md.j2; must_preserve_str (string) → brief.md.j2.
    mp_list = ideology_context.get("must_preserve", [])
    context["must_preserve"] = mp_list
    context["must_preserve_str"] = "\n".join(f"- {item}" for item in mp_list) if mp_list else ""

    # ------------------------------------------------------------------
    # 5. Render and write scaffold files
    # ------------------------------------------------------------------
    if dry_run:
        click.echo("Dry run — no files will be written.\n")

    click.echo(f"Bootstrapping pairmode scaffold into {project_path}\n")

    for dest_rel, template_name in SCAFFOLD_FILES:
        dest = project_path / dest_rel
        try:
            content = _render_template(template_name, context)
        except jinja2.TemplateError as exc:
            click.echo(f"  ERROR rendering {template_name}: {exc}", err=True)
            sys.exit(1)
        _write_file(dest, content, dry_run=dry_run, yes=yes)

    # ------------------------------------------------------------------
    # 4a. Write per-phase structure (replaces legacy docs/phase-prompts.md)
    # ------------------------------------------------------------------
    _resolved_phase_title = phase_title if phase_title else "— fill in —"
    _resolved_phase_goal = phase_goal if phase_goal else ""
    phase_index_context = {
        "project_name": project_name,
        "phases": [
            {"id": 1, "title": _resolved_phase_title, "status": "planned", "file": "phase-1.md"},
        ],
    }
    phase_one_context = {
        "project_name": project_name,
        "phase_id": 1,
        "phase_title": _resolved_phase_title,
        "prev_phase": None,
        "next_phase": None,
        "goal": _resolved_phase_goal,
        "stories": [],
        "era_id": None,
    }
    for dest_rel, template_name, ctx in [
        ("docs/phases/index.md", "docs/phases/index.md.j2", phase_index_context),
        ("docs/phases/phase-1.md", "docs/phases/phase.md.j2", phase_one_context),
    ]:
        dest = project_path / dest_rel
        try:
            content = _render_template(template_name, ctx)
        except jinja2.TemplateError as exc:
            click.echo(f"  ERROR rendering {template_name}: {exc}", err=True)
            sys.exit(1)
        _write_file(dest, content, dry_run=dry_run, yes=yes)

    # INFRA-323 § B8: surfaces the notice actually enumerates — only agent
    # shells whose write was performed. Never appended for the
    # "skipped (project-owned)" branch, dry-run, or a declined overwrite
    # prompt inside _write_file.
    written_agent_shells: list[str] = []

    for dest_rel, template_name in AGENT_FILES:
        dest = project_path / dest_rel
        if not dry_run and dest.exists() and not force_agents:
            click.echo(
                f"  skipped (project-owned): {dest} — use --force-agents to overwrite"
            )
            continue
        try:
            content = _render_template(template_name, context)
        except jinja2.TemplateError as exc:
            click.echo(f"  ERROR rendering {template_name}: {exc}", err=True)
            sys.exit(1)
        if force_agents and not dry_run:
            # Overwrite without prompting — user explicitly requested this
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            click.echo(f"  wrote: {dest}")
            written_agent_shells.append(dest_rel)
        else:
            wrote = _write_file(dest, content, dry_run=dry_run, yes=yes)
            if wrote and not dry_run:
                written_agent_shells.append(dest_rel)

    # ------------------------------------------------------------------
    # 4b. Write the nine harness-role narrative files (INFRA-351)
    # ------------------------------------------------------------------
    for dest_rel, template_name in NARRATIVE_FILES:
        dest = project_path / dest_rel
        try:
            content = _render_template(template_name, context)
        except jinja2.TemplateError as exc:
            click.echo(f"  ERROR rendering {template_name}: {exc}", err=True)
            sys.exit(1)
        _write_file(dest, content, dry_run=dry_run, yes=yes)

    # ------------------------------------------------------------------
    # 4c. Write the OPERATOR seed-then-extend narrative (INFRA-353)
    # ------------------------------------------------------------------
    # The seed always scaffolds, identically, regardless of the operator-note
    # prompt answer — the same render/write pipeline as NARRATIVE_FILES, just
    # kept out of that shared list (see OPERATOR_SEED_FILE above).
    operator_seed_dest_rel, operator_seed_template = OPERATOR_SEED_FILE
    operator_seed_dest = project_path / operator_seed_dest_rel
    try:
        operator_seed_content = _render_template(operator_seed_template, context)
    except jinja2.TemplateError as exc:
        click.echo(f"  ERROR rendering {operator_seed_template}: {exc}", err=True)
        sys.exit(1)
    _write_file(operator_seed_dest, operator_seed_content, dry_run=dry_run, yes=yes)

    # A non-blank operator-note answer becomes a separate, numbered extension
    # file — the seed above is never edited by this prompt (the story's
    # forbidden proxy). A blank answer writes no extension file at all.
    if operator_note:
        operator_extension_dest = (
            project_path / "docs" / "narratives" / "OPERATOR" / "OPERATOR-010-project.md"
        )
        operator_extension_content = (
            "---\n"
            "id: OPERATOR-010\n"
            "role: OPERATOR\n"
            "title: Project-specific operator extension\n"
            "status: draft\n"
            "stories: []\n"
            "---\n"
            "\n"
            "## Narrative\n"
            "\n"
            f"{operator_note}\n"
        )
        _write_file(
            operator_extension_dest,
            operator_extension_content,
            dry_run=dry_run,
            yes=yes,
        )

    # ------------------------------------------------------------------
    # 4.5. Save template context for audit/sync rendering
    # ------------------------------------------------------------------
    context_path = project_path / ".companion" / "pairmode_context.json"
    serialisable_context = {
        "project_name": context["project_name"],
        "project_description": context["project_description"],
        "stack": context["stack"],
        "what": context["what"],
        "why": context["why"],
        "operator_contact": context["operator_contact"],
        "build_command": context["build_command"],
        "test_command": context["test_command"],
        "test_dir": context["test_dir"],
        "migration_command": context["migration_command"],
        "domain_model": context["domain_model"],
        "domain_isolation_rule": context["domain_isolation_rule"],
        "checklist_items": context["checklist_items"],
        "protected_paths": context["protected_paths"],
        "covered_contracts": context["covered_contracts"],
        "non_negotiables": context["non_negotiables"],
        "module_structure": context["module_structure"],
        "layer_rules": context["layer_rules"],
    }
    if dry_run:
        click.echo(f"  [dry-run] would save template context to: {context_path}")
    else:
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text(json.dumps(serialisable_context, indent=2) + "\n", encoding="utf-8")
        click.echo(f"Saving template context to {context_path}")

    # ------------------------------------------------------------------
    # 5. Merge deny list into .claude/settings.json
    # ------------------------------------------------------------------
    settings_path = project_path / ".claude" / "settings.json"
    if dry_run:
        click.echo(f"\n  [dry-run] would merge deny list into: {settings_path}")
    else:
        click.echo(f"\nMerging deny list into {settings_path}")
        _merge_deny_list(settings_path, effective_deny)

    # ------------------------------------------------------------------
    # 5b. Register PreToolUse + context-budget-gate hooks into
    #     .claude/settings.local.json (INFRA-206 PreToolUse; INFRA-208
    #     UserPromptSubmit / SessionStart / PostToolUse Task|Agent — see
    #     CER-067; moved out of the committed settings.json by INFRA-319 /
    #     CER-127 — a machine-bound absolute path in a committed file is
    #     portable for exactly one machine)
    # ------------------------------------------------------------------
    plugin_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
    hook_registration_changed = False
    if dry_run:
        click.echo(
            f"  [dry-run] would register PreToolUse + context-budget-gate "
            f"hooks in: {_hook_settings_path(project_path)}"
        )
    else:
        pretooluse_changed = _register_pretooluse_hook(settings_path, plugin_root)
        context_budget_changed = _register_context_budget_hooks(settings_path, plugin_root)
        hook_registration_changed = bool(pretooluse_changed or context_budget_changed)

    # ------------------------------------------------------------------
    # 5a. Merge allow rules into .claude/settings.local.json
    # ------------------------------------------------------------------
    settings_local_path = project_path / ".claude" / "settings.local.json"
    if dry_run:
        click.echo(f"  [dry-run] would merge allow rules into: {settings_local_path}")
    else:
        click.echo(f"Merging allow rules into {settings_local_path}")
        _merge_allow_rules(settings_local_path, PAIRMODE_ALLOW)

    # ------------------------------------------------------------------
    # 6. Write deny-rationale sidecar
    # ------------------------------------------------------------------
    rationale_path = project_path / ".claude" / "settings.deny-rationale.json"
    rationale_data: dict = {
        "generated_by": "flex:pairmode",
        "pairmode_version": PAIRMODE_VERSION,
        "rules": [
            {
                "pattern": rule["path_pattern"],
                "module": rule["module"],
                "non_negotiable": rule["non_negotiable"],
            }
            for rule in derived_denylist
        ],
    }
    if dry_run:
        click.echo(f"  [dry-run] would write deny rationale to: {rationale_path}")
    else:
        rationale_path.parent.mkdir(parents=True, exist_ok=True)
        rationale_path.write_text(
            json.dumps(rationale_data, indent=2) + "\n", encoding="utf-8"
        )
        click.echo(f"Writing deny rationale to {rationale_path}")

    # ------------------------------------------------------------------
    # 7. Record pairmode version
    # ------------------------------------------------------------------
    # INFRA-323 § A2/B8: the restart-notice surface list — agent shells whose
    # write was actually performed, plus "hook_registration" when the
    # settings-level registration actually changed something.
    restart_changed: list[str] = list(written_agent_shells)
    if hook_registration_changed:
        restart_changed.append("hook_registration")

    state_path = project_path / ".companion" / "state.json"
    if dry_run:
        click.echo(f"  [dry-run] would record pairmode_version in: {state_path}")
    else:
        click.echo(f"Recording pairmode_version in {state_path}")
        effort_newly_enabled = _record_state(
            state_path,
            PAIRMODE_VERSION,
            restart_changed=restart_changed,
            restart_action="bootstrap",
        )
        if effort_newly_enabled:
            click.echo(
                "  effort tracking enabled (local sqlite only — no data leaves the host)"
            )

    # ------------------------------------------------------------------
    # 8. Initialize rails and Era 001
    # ------------------------------------------------------------------
    click.echo("\nInitializing rails...")
    _initialize_rails(project_path, context, stack, dry_run=dry_run, ideology_skip=ideology_skip, yes=yes)

    click.echo("\nDone." if not dry_run else "\nDry run complete.")

    if not dry_run:
        repo_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        _print_next_steps(project_path, repo_root)

        # INFRA-323 § B7/B9/B10: the RESTART REQUIRED notice is the final
        # output of a completed non-dry-run bootstrap. A dry run prints no
        # notice (§ B9); a re-bootstrap where every agent shell was skipped
        # and no hook registration changed prints nothing (§ B10 no-op
        # contract).
        notice = session_lifecycle.render_restart_notice(
            restart_changed, action="bootstrap"
        )
        if notice:
            click.echo("\n" + notice)


if __name__ == "__main__":
    bootstrap()
