# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "jinja2"]
# ///
"""
pairmode_sync.py — Re-render agent file frontmatter from canonical templates.

``sync-agents`` walks ``.claude/agents/`` in a target project, finds the
matching Jinja2 template in ``skills/pairmode/templates/agents/`` for each
agent file, renders only the frontmatter block, and replaces the frontmatter
in the target file while preserving the body.

``sync-build`` compares the target project's ``CLAUDE.build.md`` against the
canonical ``CLAUDE.build.md.j2`` template rendered with the project's
``state.json``.  With ``--apply``, it writes the rendered template.

``sync-all`` runs all three sync operations in fixed order: sync.py (methodology
files) → sync-agents (agent frontmatter) → sync-build (CLAUDE.build.md).

Usage:
    uv run python skills/pairmode/scripts/pairmode_sync.py sync-agents \\
        [--project-dir DIR] [--dry-run] [--yes]

    uv run python skills/pairmode/scripts/pairmode_sync.py sync-build \\
        --project-dir DIR [--dry-run] [--apply] [--yes]

    uv run python skills/pairmode/scripts/pairmode_sync.py sync-all \\
        --project-dir DIR [--dry-run] [--apply] [--yes]
"""

from __future__ import annotations

import datetime
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Allow running directly and as a module import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import click
import jinja2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pairmode templates root — parents[1] of this script == skills/pairmode/
_TEMPLATES_ROOT = Path(__file__).resolve().parent.parent / "templates"

# Path to agent templates directory, relative to this script's location:
#   skills/pairmode/scripts/pairmode_sync.py
#   parents[0] = skills/pairmode/scripts/
#   parents[1] = skills/pairmode/
TEMPLATES_DIR = _TEMPLATES_ROOT / "agents"

# Path to the canonical CLAUDE.build.md Jinja2 template
BUILD_TEMPLATE_PATH = _TEMPLATES_ROOT / "CLAUDE.build.md.j2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_state(project_dir: Path) -> dict:
    """Read .companion/state.json; return empty dict if missing or malformed."""
    state_path = project_dir / ".companion" / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_pairmode_context(project_dir: Path) -> dict:
    """Read .companion/pairmode_context.json; return empty dict if missing or malformed."""
    ctx_path = project_dir / ".companion" / "pairmode_context.json"
    if not ctx_path.exists():
        return {}
    try:
        return json.loads(ctx_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _get_project_name(project_dir: Path, state: dict) -> str:
    """Return project_name for template rendering.

    Tries state["project_name"] first; falls back to project_dir.name.
    Strips leading/trailing whitespace and removes embedded newline/carriage-return
    characters to prevent YAML injection when the value is rendered into agent
    file frontmatter (CER-019).
    """
    name = state.get("project_name")
    if isinstance(name, str) and name.strip():
        return name.strip().replace("\n", "").replace("\r", "")
    return project_dir.resolve().name.replace("\n", "").replace("\r", "")


def _render_template_frontmatter(template_path: Path, context: dict) -> str:
    """Render *template_path* with *context* and extract only the frontmatter.

    Returns the frontmatter block including both ``---`` delimiters.
    Raises ``ValueError`` if the rendered output has no frontmatter block.
    """
    loader = jinja2.FileSystemLoader(str(template_path.parent))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)
    rendered = template.render(**context)

    return _extract_frontmatter_block(rendered, source=template_path.name)


def _extract_frontmatter_block(text: str, source: str = "<input>") -> str:
    """Extract the frontmatter block (``---`` … ``---``) from *text*.

    Returns the substring from the first ``---`` to and including the closing
    ``---`` (both delimiters).  Raises ``ValueError`` if the block cannot be
    found.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValueError(f"{source}: rendered output does not start with '---'")

    # Find the closing '---' starting from line index 1
    close_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            close_idx = i
            break

    if close_idx is None:
        raise ValueError(f"{source}: no closing '---' found in rendered frontmatter")

    return "".join(lines[: close_idx + 1])


def _split_agent_file(text: str) -> tuple[str, str] | None:
    """Split an agent file into (frontmatter_block, body).

    The frontmatter block includes both ``---`` delimiters.
    The body is everything after the second ``---`` (including the leading
    newline).

    Returns ``None`` if the file has no valid frontmatter block (no ``---``
    start or no closing ``---``).
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None

    close_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            close_idx = i
            break

    if close_idx is None:
        return None

    frontmatter = "".join(lines[: close_idx + 1])
    body = "".join(lines[close_idx + 1 :])
    return frontmatter, body


def _parse_body_sections(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse a body string into a preamble and a list of (heading_line, content) sections.

    The preamble is all content before the first ``## `` heading.
    Each section is a tuple of (heading_line, content) where:
    - ``heading_line`` is the full line starting with ``## `` (including newline)
    - ``content`` is the text that follows the heading, up to the next ``## `` heading

    Returns (preamble, sections).
    """
    lines = body.splitlines(keepends=True)
    preamble_lines: list[str] = []
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_content_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, "".join(current_content_lines)))
            elif current_content_lines:
                preamble_lines.extend(current_content_lines)
                current_content_lines = []
            else:
                # no content yet — flush preamble_lines from before first heading
                pass
            current_heading = line
            current_content_lines = []
        else:
            current_content_lines.append(line)

    # Flush the last section or remaining preamble content
    if current_heading is not None:
        sections.append((current_heading, "".join(current_content_lines)))
    else:
        preamble_lines.extend(current_content_lines)

    return "".join(preamble_lines), sections


_PSEUDO_HEADER_RE = re.compile(r"^\*\*(.+?)\*\*:?$")
_ENUMERATOR_RE = re.compile(r"^\d+(\.\d+)?[a-z]?[.)]?\s+")
_INLINE_EMPHASIS_CHARS = str.maketrans("", "", "*_`")


def _heading_concept_key(line: str) -> str | None:
    """Return a normalized concept key for a heading-like line, or ``None``.

    Recognizes two heading styles:
    - a true ``## `` (or ``#``) heading line
    - a standalone bold-inline pseudo-header line, i.e. a line whose entire
      stripped content is wrapped in ``**...**`` (optionally with a trailing
      ``:``) — not a bold span embedded in a larger prose sentence.

    Normalization (see INFRA-202 Ensures #1):
    a. strip leading/trailing whitespace
    b. remove a leading ``## `` / ``#`` marker
    c. unwrap a line that is wholly ``**...**`` (optional trailing ``:``)
    d. remove a leading enumerator token (``1. ``, ``2.5 ``, ``5a. ``, ``10) ``)
    e. strip a trailing ``:``
    f. strip remaining inline emphasis / backtick characters
    g. lowercase and collapse internal whitespace runs to a single space

    Returns ``None`` for any line that is not a recognized heading style.
    """
    text = line.strip()
    if not text:
        return None

    is_heading = False

    if text.startswith("## "):
        text = text[3:].strip()
        is_heading = True
    elif text.startswith("#"):
        stripped = text.lstrip("#").strip()
        if stripped != text:
            text = stripped
            is_heading = True

    if not is_heading:
        match = _PSEUDO_HEADER_RE.match(text)
        if not match:
            return None
        text = match.group(1).strip()
        is_heading = True

    if not is_heading:
        return None

    text = _ENUMERATOR_RE.sub("", text, count=1)
    text = text.strip()
    if text.endswith(":"):
        text = text[:-1].strip()
    text = text.translate(_INLINE_EMPHASIS_CHARS)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()

    return text or None


def _target_concept_keys(body: str) -> set[str]:
    """Collect the set of normalized concept keys present anywhere in *body*.

    Scans every line of the target body (not just ``## ``-delimited sections)
    for both true ``## `` headings and standalone bold-inline pseudo-header
    lines, via :func:`_heading_concept_key`.
    """
    keys: set[str] = set()
    for line in body.splitlines():
        key = _heading_concept_key(line)
        if key is not None:
            keys.add(key)
    return keys


def _sections_to_add(
    template_sections: list[tuple[str, str]], target_body: str
) -> list[tuple[str, str]]:
    """Return the subset of *template_sections* that would be appended to *target_body*.

    A template section is "to add" when its normalized concept key (see
    :func:`_heading_concept_key`) is not already present anywhere in the target
    body (see :func:`_target_concept_keys`). Shared by :func:`_merge_body_sections`
    and the INFRA-203 empty-variable-in-appended-section guard so both use an
    identical definition of "would be appended".
    """
    target_keys: set[str] = _target_concept_keys(target_body)
    return [
        (heading, content)
        for heading, content in template_sections
        if _heading_concept_key(heading) not in target_keys
    ]


def _merge_body_sections(template_body: str, target_body: str) -> str:
    """Merge new H2 sections from *template_body* into *target_body*, additively.

    Sections present in the template but absent from the target are appended to
    the target.  Sections already present in the target are left untouched.
    Sections in the target that are absent from the template are preserved
    (project-specific additions are never removed).

    "Present in the target" is decided by normalized concept key (see
    :func:`_heading_concept_key`), not exact heading-string equality, so a
    canonical checklist item already present under a non-``## `` heading style
    (e.g. a ``**N. TITLE**`` pseudo-header) is recognized and never
    duplicate-appended (INFRA-202).

    Returns the merged target body.
    """
    _template_preamble, template_sections = _parse_body_sections(template_body)

    sections_to_add = _sections_to_add(template_sections, target_body)

    if not sections_to_add:
        return target_body

    # Append missing sections to the target body, each preceded by a blank line
    merged = target_body
    # Ensure the body ends with a newline before appending
    if merged and not merged.endswith("\n"):
        merged += "\n"
    for heading, content in sections_to_add:
        merged += "\n" + heading + content

    return merged


def _render_full_template(template_path: Path, context: dict) -> str:
    """Render *template_path* with *context* and return the full rendered output.

    Unlike ``_render_template_frontmatter``, this returns the entire rendered
    file including both frontmatter and body.
    Raises ``ValueError`` if the template cannot be rendered.
    """
    loader = jinja2.FileSystemLoader(str(template_path.parent))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)
    return template.render(**context)


_UNDEFINED_VAR_RE = re.compile(r"'([^']+)' is undefined")


def _reason_for_undefined_error(heading: str, exc: jinja2.UndefinedError) -> str:
    """Build a human-readable render_errors reason for an undefined-in-appended-section failure.

    Names the offending variable when jinja2's error message follows its
    standard "'<name>' is undefined" shape; falls back to the raw exception
    text otherwise.
    """
    match = _UNDEFINED_VAR_RE.search(str(exc))
    var_name = match.group(1) if match else str(exc)
    heading_text = heading.strip().lstrip("#").strip()
    return f"body section '{heading_text}' interpolates empty variable '{var_name}'"


def _empty_variable_in_appended_sections(
    template_path: Path,
    sections_to_add: list[tuple[str, str]],
    body_strict_context: dict,
) -> str | None:
    """Return a render-error reason if an appended section depends on an empty-valued variable.

    INFRA-203: ``_build_template_context`` supplies graceful ``""``/``[]`` fallbacks
    for several variables (``build_command``, ``domain_isolation_rule``,
    ``protected_paths``, ...). Those fallbacks are *defined* values, so the
    loose full-template render under ``StrictUndefined`` never raises for them
    — the empty string is simply interpolated, producing degenerate merged
    content (e.g. `` Does `` pass cleanly? ``). This helper re-renders, in
    isolation, only the raw template source of each section that
    ``_merge_body_sections`` would newly append, using *body_strict_context*
    (the same context with every empty-valued key removed). If that stricter
    render raises ``jinja2.UndefinedError`` for a given section, that section's
    rendered content depends on a variable this project supplies only as an
    empty fallback, and the file must be surfaced as a render error rather
    than merged (Ensures #2). Sections not in *sections_to_add* — i.e. content
    that is not newly appended — are never inspected here (Ensures #4).

    Returns the first offending reason string, or ``None`` if no appended
    section depends on an empty-valued variable.
    """
    if not sections_to_add:
        return None

    raw_text = template_path.read_text(encoding="utf-8")
    raw_parts = _split_agent_file(raw_text)
    raw_body = raw_parts[1] if raw_parts is not None else raw_text
    _raw_preamble, raw_sections = _parse_body_sections(raw_body)

    raw_by_key: dict[str, str] = {}
    for heading, content in raw_sections:
        key = _heading_concept_key(heading)
        if key is not None and key not in raw_by_key:
            raw_by_key[key] = heading + content

    strict_env = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )

    for heading, _rendered_content in sections_to_add:
        key = _heading_concept_key(heading)
        raw_section_source = raw_by_key.get(key) if key is not None else None
        if raw_section_source is None:
            # Could not locate the corresponding raw source for this appended
            # section (e.g. a templated heading) — nothing to strictly
            # re-render against; skip rather than false-block.
            continue
        try:
            strict_env.from_string(raw_section_source).render(**body_strict_context)
        except jinja2.UndefinedError as exc:
            return _reason_for_undefined_error(heading, exc)

    return None


# ---------------------------------------------------------------------------
# sync-build helpers
# ---------------------------------------------------------------------------


def _build_template_context(project_dir: Path) -> dict:
    """Build the Jinja2 context for rendering CLAUDE.build.md.j2.

    Merges state.json and pairmode_context.json, with graceful fallbacks
    for every key the template uses.
    """
    state = _load_state(project_dir)
    pctx = _load_pairmode_context(project_dir)

    # project_name: prefer state.json, then pairmode_context.json, then dir name
    project_name = state.get("project_name") or pctx.get("project_name") or ""
    if not isinstance(project_name, str) or not project_name.strip():
        project_name = project_dir.resolve().name
    else:
        project_name = project_name.strip().replace("\n", "").replace("\r", "")

    default_branch = (
        state.get("default_branch")
        or pctx.get("default_branch")
        or "main"
    )

    return {
        "project_name": project_name,
        "build_command": pctx.get("build_command") or state.get("build_command") or "",
        "test_command": pctx.get("test_command") or state.get("test_command") or "",
        "migration_command": pctx.get("migration_command") or state.get("migration_command") or "",
        "pairmode_scripts_dir": str(Path(__file__).parent),
        "default_branch": default_branch,
        "domain_isolation_rule": pctx.get("domain_isolation_rule") or state.get("domain_isolation_rule") or "",
        "protected_paths": pctx.get("protected_paths") or state.get("protected_paths") or [],
    }


def _render_build_template(context: dict) -> str:
    """Render the canonical CLAUDE.build.md.j2 template with *context*.

    Returns the rendered string.
    Raises ``ValueError`` if the template cannot be rendered.
    """
    loader = jinja2.FileSystemLoader(str(BUILD_TEMPLATE_PATH.parent))
    env = jinja2.Environment(
        loader=loader,
        undefined=jinja2.Undefined,  # silently treat missing vars as empty
        keep_trailing_newline=True,
    )
    try:
        template = env.get_template(BUILD_TEMPLATE_PATH.name)
        return template.render(**context)
    except jinja2.TemplateError as exc:
        raise ValueError(f"Failed to render {BUILD_TEMPLATE_PATH.name}: {exc}") from exc


def _depth_guard_sync_build(project_dir: Path) -> None:
    """Reject project_dir paths with fewer than 3 components (containment guard).

    Raises SystemExit(1) when the path is too shallow.
    """
    if not project_dir.is_dir() or len(project_dir.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {project_dir}",
            err=True,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------


def _collect_changes(
    agents_dir: Path,
    templates_dir: Path,
    context: dict,
) -> tuple[list[tuple[Path, str, str]], list[tuple[str, str]]]:
    """Return (changes, render_errors).

    ``changes`` is a list of (agent_file, old_content, new_content) for changed files.
    ``render_errors`` is a list of (filename, reason) pairs for files skipped because
    the canonical template failed to render (StrictUndefined, syntax error, etc.).

    Warnings about other skip paths (no template found, no frontmatter block) are
    still printed to stderr here; only rendering failures are surfaced via the
    returned ``render_errors`` list so the caller can decide how to react.
    """
    if not agents_dir.is_dir():
        return [], []

    changes: list[tuple[Path, str, str]] = []
    render_errors: list[tuple[str, str]] = []

    for agent_file in sorted(agents_dir.glob("*.md")):
        stem = agent_file.stem  # e.g. "builder"
        template_path = templates_dir / f"{stem}.md.j2"

        if not template_path.exists():
            click.echo(
                f"warning: no template found for {agent_file.name} "
                f"(expected {template_path.name}) — skipping",
                err=True,
            )
            continue

        old_content = agent_file.read_text(encoding="utf-8")

        # Check that the agent file has a frontmatter block
        parts = _split_agent_file(old_content)
        if parts is None:
            click.echo(
                f"warning: {agent_file.name} has no frontmatter block — skipping",
                err=True,
            )
            continue

        old_frontmatter, body = parts

        # Render the new frontmatter from the template
        try:
            new_frontmatter = _render_template_frontmatter(template_path, context)
        except (jinja2.TemplateError, ValueError) as exc:
            render_errors.append((agent_file.name, str(exc)))
            continue

        # --- Path A: raised full-template render (StrictUndefined on a truly
        # missing variable, or any other TemplateError/ValueError). INFRA-203
        # Ensures #1: this is surfaced identically to the frontmatter-render
        # failure above — no silent fall-back to an empty/no-op body merge.
        try:
            full_rendered = _render_full_template(template_path, context)
        except (jinja2.TemplateError, ValueError) as exc:
            render_errors.append((agent_file.name, str(exc)))
            continue

        template_parts = _split_agent_file(full_rendered)
        template_body = template_parts[1] if template_parts is not None else ""

        # --- Path B: full render *succeeded*, but only because a body-referenced
        # variable resolved to a graceful ""/[] fallback from
        # _build_template_context (a *defined*-but-empty value, so
        # StrictUndefined never fired). INFRA-203 Ensures #2/#4: if the
        # section(s) that would be newly appended to the target depend on such
        # an empty value, surface a render error instead of merging degenerate
        # content (e.g. `` Does `` pass cleanly? ``). Sections that are empty
        # but only appear inside content already present in the target (and
        # therefore not appended) are never flagged.
        _preamble, template_sections = _parse_body_sections(template_body)
        sections_to_add = _sections_to_add(template_sections, body)

        if sections_to_add:
            body_strict_context = {
                key: value for key, value in context.items() if value not in ("", [], None)
            }
            reason = _empty_variable_in_appended_sections(
                template_path, sections_to_add, body_strict_context
            )
            if reason is not None:
                render_errors.append((agent_file.name, reason))
                continue

        # Merge new H2 sections from the template body into the target body
        merged_body = _merge_body_sections(template_body, body)

        new_content = new_frontmatter + merged_body

        if new_content != old_content:
            changes.append((agent_file, old_content, new_content))

    return changes, render_errors


def _print_diff(agent_file: Path, old_content: str, new_content: str) -> None:
    """Print a unified diff for the given file change."""
    filename = agent_file.name
    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=filename,
        tofile=filename,
    )
    click.echo("".join(diff), nl=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("sync-agents")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Project root (defaults to current directory).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print diffs without writing any files.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Write files without prompting for confirmation.",
)
def sync_agents(project_dir: str, dry_run: bool, yes: bool) -> None:
    """Re-render agent file frontmatter from canonical pairmode templates.

    For each agent file found in <project-dir>/.claude/agents/, finds the
    matching template in skills/pairmode/templates/agents/ by filename stem,
    renders the template frontmatter, and replaces the frontmatter in the
    target file while preserving the body.

    With --dry-run, prints diffs without writing. With --yes, writes without
    prompting. Otherwise, prompts once before writing all changes.
    """
    project_path = Path(project_dir).resolve()
    _depth_guard_sync_build(project_path)
    agents_dir = project_path / ".claude" / "agents"

    context = _build_template_context(project_path)

    changes, render_errors = _collect_changes(agents_dir, TEMPLATES_DIR, context)

    # Emit each render error to stderr — these are no longer silently swallowed
    for filename, reason in render_errors:
        click.echo(f"error: failed to render {filename}: {reason}", err=True)

    if not changes:
        if render_errors:
            click.echo(
                f"sync-agents: {len(render_errors)} file(s) failed to render — "
                "run with --dry-run to debug",
                err=True,
            )
            sys.exit(1)
        click.echo("No changes to apply.")
        return

    # Print diffs for all changed files
    for agent_file, old_content, new_content in changes:
        _print_diff(agent_file, old_content, new_content)

    if dry_run:
        return

    # Prompt once if needed
    if not yes:
        confirmed = click.confirm("Apply these changes? [y/N]", default=False, prompt_suffix="")
        if not confirmed:
            click.echo("Aborted.")
            return

    # Write all changed files
    for agent_file, _old, new_content in changes:
        agent_file.write_text(new_content, encoding="utf-8")
        click.echo(f"  updated: {agent_file.name}")


def _seed_context_gate_state(project_dir: Path, state_path: Path, dry_run: bool) -> None:
    """Seed missing context gate keys in state.json.

    Checks whether ``context_session_reset_at`` or ``context_current_tokens`` are absent
    from state.json.  If either is missing, and not in dry-run mode, writes the appropriate
    seed values.  In dry-run mode, emits warning lines without writing.

    The three keys managed by this function:
    - ``context_session_reset_at``  — UTC ISO-8601 timestamp; written when absent.
    - ``context_current_tokens``    — integer 25000; written when absent.
    - ``context_current_tokens_recorded_at`` — same timestamp as reset_at; written only when
      context_current_tokens is also absent (paired write).

    Edge cases:
    - Only ``context_session_reset_at`` absent: seed it; leave the other two untouched.
    - Only ``context_current_tokens`` absent: seed it (= 25000) and its ``_recorded_at``
      (= now); leave ``context_session_reset_at`` untouched.
    - state.json missing entirely: create it with only the three keys.
    - ``.companion/`` directory missing: create it before writing.
    """
    # Load or initialise state
    if state_path.exists():
        try:
            state: dict = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except (json.JSONDecodeError, OSError):
            state = {}
    else:
        state = {}

    missing_reset_at = "context_session_reset_at" not in state
    missing_tokens = "context_current_tokens" not in state

    if not missing_reset_at and not missing_tokens:
        # Both present — nothing to do
        return

    if dry_run:
        # Emit warning lines to stdout; do not write
        click.echo("warning: state.json missing context gate keys — run with --apply to seed")
        if missing_reset_at:
            click.echo("  missing: context_session_reset_at")
        if missing_tokens:
            click.echo("  missing: context_current_tokens")
        return

    # --- Apply path: write the missing keys ---
    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if missing_reset_at:
        state["context_session_reset_at"] = now_ts

    if missing_tokens:
        state["context_current_tokens"] = 25000
        state["context_current_tokens_recorded_at"] = now_ts

    # Ensure .companion/ exists
    companion_dir = state_path.parent
    companion_dir.mkdir(parents=True, exist_ok=True)

    # Atomic write: temp file in same directory, then os.replace
    tmp_path = state_path.with_suffix(".json.tmp")
    try:
        tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(str(tmp_path), str(state_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    # Build the seeded line
    seeded_ts = state.get("context_session_reset_at", now_ts)
    click.echo(
        f"  seeded: context gate state (context_current_tokens={state.get('context_current_tokens', 25000)}, reset_at={seeded_ts})"
    )


@click.command("sync-build")
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Project root containing CLAUDE.build.md.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the diff and exit without writing.",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Write the rendered template to CLAUDE.build.md.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip confirmation when --apply is set.",
)
def sync_build(project_dir: str, dry_run: bool, apply: bool, yes: bool) -> None:
    """Compare and optionally update CLAUDE.build.md from the canonical template.

    Renders skills/pairmode/templates/CLAUDE.build.md.j2 with the project's
    state.json variables and diffs the result against the project's current
    CLAUDE.build.md.

    With --dry-run: print the diff and exit 0 without writing.
    With --apply: print the diff, optionally prompt, then write the file.
    Without --apply: print the diff and exit 0 (same as --dry-run).
    With --apply --yes: write without prompting.
    """
    project_path = Path(project_dir).resolve()

    # Containment guard — consistent with all other pairmode entry points
    _depth_guard_sync_build(project_path)

    build_file = project_path / "CLAUDE.build.md"

    # Build template context from state.json + pairmode_context.json
    context = _build_template_context(project_path)

    # Render the canonical template
    try:
        rendered = _render_build_template(context)
    except ValueError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    # Read existing file; treat missing as empty
    if build_file.exists():
        existing = build_file.read_text(encoding="utf-8")
    else:
        existing = ""

    # Compute the unified diff
    diff_lines = list(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            rendered.splitlines(keepends=True),
            fromfile="CLAUDE.build.md",
            tofile="CLAUDE.build.md (rendered)",
        )
    )

    state_path = project_path / ".companion" / "state.json"

    if not diff_lines:
        click.echo("No changes to apply.")
        # Still check and seed context gate state even when build file is up to date
        if dry_run or not apply:
            _seed_context_gate_state(project_path, state_path, dry_run=True)
        else:
            _seed_context_gate_state(project_path, state_path, dry_run=False)
        return

    # --dry-run or no --apply: emit warning before diff output, then exit
    if dry_run or not apply:
        _seed_context_gate_state(project_path, state_path, dry_run=True)
        click.echo("".join(diff_lines), nl=False)
        return

    # Print the diff
    click.echo("".join(diff_lines), nl=False)

    # --apply path: prompt unless --yes
    if not yes:
        confirmed = click.confirm("Apply? [y/N]", default=False, prompt_suffix="")
        if not confirmed:
            click.echo("Aborted.")
            return

    build_file.write_text(rendered, encoding="utf-8")
    click.echo(f"  updated: {build_file.name}")

    # Seed context gate state after writing CLAUDE.build.md
    _seed_context_gate_state(project_path, state_path, dry_run=False)


@click.command("sync-all")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root (defaults to current directory).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=True,
    help="Safe-by-default: preview changes without writing. Pass --apply to write.",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Apply changes to disk. Overrides --dry-run when set.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Suppress confirmation prompts; propagated to each downstream command.",
)
def sync_all(project_dir: str, dry_run: bool, apply: bool, yes: bool) -> None:
    """Run all three sync operations in fixed order.

    Invocation order: sync.py (methodology files) → sync-agents (agent
    frontmatter) → sync-build (CLAUDE.build.md).

    Safe by default — without --apply, only sync-agents and sync-build are
    run in dry-run mode (sync.py is skipped because it has no --dry-run flag).
    Pass --apply to run all three and write changes to disk.

    Fail-fast: if any downstream command exits non-zero, the wrapper halts and
    exits with the same status code. Remaining commands are not invoked.
    """
    project_path = Path(project_dir).resolve()
    _depth_guard_sync_build(project_path)

    # --apply overrides the dry_run flag regardless of its value
    effective_apply = bool(apply)

    # Paths for downstream scripts
    _this_script = Path(__file__).resolve()
    _sync_script = _this_script.parent / "sync.py"

    # Build the downstream invocation list.
    # Each entry: (label, argv, skip_in_dry_run)
    # skip_in_dry_run=True means the command is skipped when effective_apply is False.

    # --- sync.py ---
    sync_argv = [sys.executable, str(_sync_script), "--project-dir", str(project_path)]
    if yes:
        sync_argv.append("--yes")

    # --- sync-agents ---
    agents_argv = [
        sys.executable, str(_this_script),
        "sync-agents",
        "--project-dir", str(project_path),
    ]
    if not effective_apply:
        agents_argv.append("--dry-run")
    if yes:
        agents_argv.append("--yes")

    # --- sync-build ---
    build_argv = [
        sys.executable, str(_this_script),
        "sync-build",
        "--project-dir", str(project_path),
    ]
    if not effective_apply:
        build_argv.append("--dry-run")
    else:
        build_argv.append("--apply")
    if yes:
        build_argv.append("--yes")

    invocations: list[tuple[str, list[str], bool]] = [
        ("sync (methodology files)", sync_argv, True),
        ("sync-agents (agent frontmatter)", agents_argv, False),
        ("sync-build (CLAUDE.build.md)", build_argv, False),
    ]

    for label, argv, skip_in_dry_run in invocations:
        click.echo(f"=== {label} ===")
        if skip_in_dry_run and not effective_apply:
            click.echo(
                "skipped: sync.py does not support --dry-run; pass --apply to run it"
            )
            continue

        result = subprocess.run(argv, check=False)  # noqa: S603
        if result.returncode != 0:
            click.echo(
                f"error: '{label}' exited {result.returncode} — halting chain",
                err=True,
            )
            sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group("pairmode")
def pairmode_cli() -> None:
    """pairmode sync subcommands."""


pairmode_cli.add_command(sync_agents)
pairmode_cli.add_command(sync_build)
pairmode_cli.add_command(sync_all)

# Register the register/unregister/list-projects commands from pairmode_register.py
from pairmode_register import register, unregister, list_projects  # noqa: E402

pairmode_cli.add_command(register)
pairmode_cli.add_command(unregister)
pairmode_cli.add_command(list_projects)


if __name__ == "__main__":
    pairmode_cli()
