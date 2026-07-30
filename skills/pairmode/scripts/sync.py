"""
sync.py — Pairmode project syncer.

Applies the delta from an audit result to a project. EXTRA items are preserved
unless canon has explicitly retired them (``RETIRED_SECTIONS``); project
overrides win over retirement. Every change — additions, updates, and
retirement prunes alike — is applied only behind an explicit per-section
confirmation (or ``--yes``).
"""

from __future__ import annotations

import difflib
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import click
import jinja2

# Insert repo root so sibling imports work when run as CLI
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.pairmode.scripts.audit import audit_project, AuditResult, AuditItem  # noqa: E402
from skills.pairmode.scripts.audit import (  # noqa: E402
    TEMPLATES_DIR,
    CANONICAL_FILES,
    EXISTENCE_CHECK_FILES,
    SCAFFOLD_FILES,
    _split_sections,
    _normalise,
    _enrich_scaffold_context,
    _load_project_context as _audit_load_project_context,
    _load_overrides,
    _SECTION_RE,
)
from skills.pairmode.scripts._version import PAIRMODE_VERSION  # noqa: E402
from skills.pairmode.scripts.context_model import THIN_HARNESS_STEP_TOKENS
from skills.pairmode.scripts.state_utils import (  # noqa: E402
    _atomic_write_json,
    state_lock,
)
from skills.pairmode.scripts.bootstrap import (  # noqa: E402
    DEFAULT_DENY,
    PAIRMODE_DEFAULT_RAILS,
    _SUPERSEDED_DENY_ENTRIES,
    _infer_project_type,
    _merge_deny_list,
    _prune_superseded_deny_entries,
    _register_context_budget_hooks,
    _register_pretooluse_hook,
    _validate_test_command,
)
from skills.pairmode.scripts.story_new import _add_rail_to_era, _find_era  # noqa: E402

# ---------------------------------------------------------------------------
# Canon-retired sections registry (INFRA-311)
# ---------------------------------------------------------------------------
#
# Section keys that canon once shipped in CANONICAL_FILES templates and has
# since removed, mapped to the story ID that retired them. Sync deletes a
# downstream EXTRA section **only** when its key appears here (and only in
# CANONICAL_FILES — scaffold-file bodies are inherently project-specific);
# everything else keeps the preservation contract verbatim. A project
# `.pairmode-overrides` entry naming a retired key is a legitimate
# "keep it anyway" signal and wins over this registry.
#
# Keys are the normalised section keys produced by audit._normalise on the
# section boundary line (``##`` headers, ``###`` headers, and bold numbered
# checklist markers — the same _SECTION_RE granularity audit uses).
#
# Seed content: the INFRA-241 thin-agent reduction. These 46 keys were present
# in the pre-INFRA-241 fat agent templates (git 9acb9145^,
# skills/pairmode/templates/agents/*.md.j2) and are absent from the thin
# shells that replaced them.
RETIRED_SECTIONS: dict[str, str] = {
    # --- builder.md.j2 (retired by INFRA-241 thin-agent reduction) ---
    "## starting a story": "INFRA-241",
    "## before writing anything": "INFRA-241",
    "## implementation rules": "INFRA-241",
    "## ⚙️ developer action gates": "INFRA-241",
    "## when you are done": "INFRA-241",
    "## if you cannot complete the story": "INFRA-241",
    "## final output to orchestrator": "INFRA-241",  # also reviewer.md.j2
    # --- reviewer.md.j2 (retired by INFRA-241) ---
    "## starting a review": "INFRA-241",
    "## before reviewing": "INFRA-241",  # also intent-reviewer.md.j2
    "## contract check": "INFRA-241",
    "## review checklist": "INFRA-241",
    "**1. protected files**": "INFRA-241",
    "**2. story scope**": "INFRA-241",
    "**2.5 story spec**": "INFRA-241",
    "**3. build gate**": "INFRA-241",
    "**4. documentation currency**": "INFRA-241",
    "**5. ideology alignment**": "INFRA-241",
    "**5a. conviction consistency**": "INFRA-241",
    "**5b. constraint rationale preservation**": "INFRA-241",
    "**5c. fingerprint awareness**": "INFRA-241",
    "**6. rail scope (new stories only — skip if story has no story file)**": "INFRA-241",
    "## test run": "INFRA-241",
    "## decision": "INFRA-241",
    "### pass conditions": "INFRA-241",
    "### fail conditions": "INFRA-241",
    "## what you must not do": "INFRA-241",  # also loop-breaker.md.j2
    # --- loop-breaker.md.j2 (retired by INFRA-241) ---
    "## input format": "INFRA-241",
    "## your process": "INFRA-241",
    "## output format": "INFRA-241",  # also intent-reviewer.md.j2
    # --- security-auditor.md.j2 (retired by INFRA-241) ---
    "## before auditing": "INFRA-241",
    "## audit priorities": "INFRA-241",
    "### 1. hook integrity (critical if violated)": "INFRA-241",
    "### 2. credential exposure (critical if violated)": "INFRA-241",
    "### 3. path traversal (high if violated)": "INFRA-241",
    "### 4. domain isolation violation (high if violated)": "INFRA-241",
    "### 5. layer violation (high if violated)": "INFRA-241",
    "### 6. spec file protection (medium if violated)": "INFRA-241",
    "## report format": "INFRA-241",
    # --- intent-reviewer.md.j2 (retired by INFRA-241) ---
    "## inputs you will receive": "INFRA-241",
    "## story alignment": "INFRA-241",
    "## design pivot detection": "INFRA-241",
    "## calibration": "INFRA-241",
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SyncResult:
    project_dir: Path
    applied: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    retired: list[str] = field(default_factory=list)
    pairmode_version: str = PAIRMODE_VERSION
    last_sync: str = field(default_factory=lambda: date.today().isoformat())
    lessons_applied: list[str] = field(default_factory=list)
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Rail gap detection
# ---------------------------------------------------------------------------


def _check_rail_gaps(project_dir: Path, stack: str) -> list[str]:
    """Return list of default rails for this stack not present in docs/stories/.

    If docs/stories/ does not exist, returns empty list (project pre-dates rail
    structure). This function has no I/O side effects.
    """
    stories_dir = project_dir / "docs" / "stories"
    if not stories_dir.is_dir():
        return []

    project_type = _infer_project_type(stack, "")
    default_rails = PAIRMODE_DEFAULT_RAILS.get(project_type, PAIRMODE_DEFAULT_RAILS["generic"])

    present = {p.name.upper() for p in stories_dir.iterdir() if p.is_dir()}
    return [rail for rail in default_rails if rail.upper() not in present]


# ---------------------------------------------------------------------------
# Section-aware merge helpers
# ---------------------------------------------------------------------------


def _header_from_key(key: str) -> str:
    """Convert a normalised section key back to a best-effort header.

    Keys derived from ``## Foo bar`` headers will have the form ``## foo bar``.
    We just title-case words after the leading ``#`` markers.
    """
    return key


def _split_by_h2(text: str) -> list[tuple[str, str]]:
    """Split text into (header_line, section_body) pairs.

    The first tuple's header_line may be empty (preamble content).
    Each section_body does NOT include the trailing newline before the next header.
    """
    lines = text.splitlines(keepends=True)
    parts: list[tuple[str, str]] = []
    current_header = ""
    current_body_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            # Flush previous section
            parts.append((current_header, "".join(current_body_lines)))
            current_header = line.rstrip("\n")
            current_body_lines = []
        else:
            current_body_lines.append(line)

    # Flush final section
    parts.append((current_header, "".join(current_body_lines)))
    return parts


def _reconstruct_from_parts(parts: list[tuple[str, str]]) -> str:
    """Reconstruct a file from (header_line, body) pairs."""
    chunks: list[str] = []
    for header, body in parts:
        if header:
            chunks.append(header + "\n")
        if body:
            chunks.append(body)
    return "".join(chunks)


def _find_bold_marker_range(project_text: str, section_key: str) -> tuple[int, int] | None:
    """Locate a bold-marker checklist item (e.g. ``**3. BUILD GATE**``) by section_key.

    Uses the same ``_SECTION_RE`` boundary pattern as audit.py's ``_split_sections``
    so audit and sync agree on where a bold-marker section starts and ends. This
    lets a bold-marker item nested inside a larger ``##`` section be located and
    patched independently of its enclosing section and of sibling bold-marker items.

    Returns (header_idx, end_idx) line-index range (end_idx exclusive), or None
    if no line matches section_key. end_idx is either the next line that matches
    _SECTION_RE (of any boundary kind: ``##``, ``---``, or another bold marker),
    or len(lines) when the matched section runs to the end of the file.
    """
    lines = project_text.splitlines(keepends=True)
    header_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n").rstrip("\r")
        if _SECTION_RE.fullmatch(stripped) and _normalise(stripped) == section_key:
            header_idx = i
            break

    if header_idx is None:
        return None

    end_idx = len(lines)
    for i in range(header_idx + 1, len(lines)):
        stripped = lines[i].rstrip("\n").rstrip("\r")
        if _SECTION_RE.fullmatch(stripped):
            end_idx = i
            break

    return header_idx, end_idx


def _replace_section_in_file(project_text: str, section_key: str, canonical_body: str) -> str:
    """Locate the section identified by section_key in project_text and replace its body.

    section_key is the normalised form produced by _normalise(header_line).
    canonical_body is the raw body text from the canonical template.
    Handles both H2 top-level sections and H3+ nested sections.
    If the section is not found (shouldn't happen for INCONSISTENT), the text is returned unchanged.
    """
    import re as _re

    # First try H2 split (fast path for top-level sections)
    parts = _split_by_h2(project_text)
    new_parts: list[tuple[str, str]] = []
    replaced = False

    for header, body in parts:
        if not replaced and _normalise(header) == section_key:
            new_body = canonical_body if canonical_body.endswith("\n") else canonical_body + "\n"
            new_parts.append((header, new_body))
            replaced = True
        else:
            new_parts.append((header, body))

    if replaced:
        return _reconstruct_from_parts(new_parts)

    # Fallback: find H3+ section by scanning lines for a matching header
    heading_hashes = len(section_key) - len(section_key.lstrip("#"))
    lines = project_text.splitlines(keepends=True)
    header_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n").rstrip("\r")
        if stripped.startswith("#") and _normalise(stripped) == section_key:
            header_idx = i
            break

    if header_idx is not None:
        # Find end of section: next header at same or shallower depth
        end_idx = len(lines)
        for i in range(header_idx + 1, len(lines)):
            stripped = lines[i].rstrip("\n").rstrip("\r")
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                if level <= heading_hashes:
                    end_idx = i
                    break

        # Preserve the original header line; replace the body (lines after it)
        new_body = canonical_body if canonical_body.endswith("\n") else canonical_body + "\n"
        result_lines = lines[: header_idx + 1] + ["\n", new_body] + lines[end_idx:]
        return "".join(result_lines)

    # Fallback: bold-marker checklist item (e.g. **3. BUILD GATE**), which does
    # not start with a literal "#" so the H3+ scan above never matches it.
    bold_range = _find_bold_marker_range(project_text, section_key)
    if bold_range is not None:
        bold_header_idx, bold_end_idx = bold_range
        new_body = canonical_body if canonical_body.endswith("\n") else canonical_body + "\n"
        result_lines = (
            lines[: bold_header_idx + 1] + ["\n", new_body] + lines[bold_end_idx:]
        )
        return "".join(result_lines)

    return project_text  # not found


def _remove_section_from_file(project_text: str, section_key: str) -> str:
    """Remove the section identified by section_key (boundary line + body).

    Uses the same ``_SECTION_RE`` boundary pattern as audit.py's
    ``_split_sections`` so removal granularity exactly matches audit's EXTRA
    classification granularity: the removed range is the matching boundary
    line (``##``/``###`` header or bold checklist marker) through the line
    before the next ``_SECTION_RE`` boundary (of any kind), or end of file.

    If the section is not found, the text is returned unchanged.
    """
    lines = project_text.splitlines(keepends=True)
    header_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n").rstrip("\r")
        if _SECTION_RE.fullmatch(stripped) and _normalise(stripped) == section_key:
            header_idx = i
            break

    if header_idx is None:
        return project_text  # not found

    end_idx = len(lines)
    for i in range(header_idx + 1, len(lines)):
        stripped = lines[i].rstrip("\n").rstrip("\r")
        if _SECTION_RE.fullmatch(stripped):
            end_idx = i
            break

    return "".join(lines[:header_idx] + lines[end_idx:])


def _append_section_to_file(project_text: str, header_key: str, canonical_body: str) -> str:
    """Append a new section to the end of project_text.

    header_key is the normalised form. We try to reconstruct an approximate header
    from the key (e.g. ``## foo bar`` → ``## Foo bar``).
    """
    # Reconstruct a plausible header from the normalised key
    # Keys look like: "## foo bar" or "__preamble__0"
    if header_key.startswith("__"):
        # Preamble — just append the canonical body directly
        if not project_text.endswith("\n"):
            project_text += "\n"
        return project_text + "\n" + canonical_body
    else:
        # Try to recover something readable from the key
        # The key was normalised from the actual template header
        header_text = header_key  # Already in "## ..." form
        if not project_text.endswith("\n"):
            project_text += "\n"
        body_text = canonical_body if canonical_body.endswith("\n") else canonical_body + "\n"
        return project_text + "\n" + header_text + "\n" + body_text


# ---------------------------------------------------------------------------
# Template content helper
# ---------------------------------------------------------------------------

_JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=jinja2.Undefined,  # silently replaces unknown vars with ""
    keep_trailing_newline=True,
)


def _load_project_context(project_dir: Path) -> dict:
    """Load the saved bootstrap context, or return a minimal empty context."""
    context, _ = _audit_load_project_context(project_dir)
    return context


def _render_template(template_rel: str, context: dict) -> str:
    """Render a Jinja2 template with context. Returns empty string on failure."""
    try:
        return _JINJA_ENV.get_template(template_rel).render(**context)
    except (jinja2.TemplateNotFound, jinja2.TemplateError):
        return ""


def _get_template_text(template_rel: str) -> str:
    """Return raw text content of a template file."""
    path = TEMPLATES_DIR / template_rel
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _dest_to_template(dest_rel: str) -> str | None:
    """Look up the template path for a given destination relative path."""
    for d, t in CANONICAL_FILES:
        if d == dest_rel:
            return t
    # Check scaffold files (Phase 7 docs with section-level comparison)
    for d, t in SCAFFOLD_FILES:
        if d == dest_rel:
            return t
    # Also check existence-check files (now empty, kept for compat)
    for d, t, _desc in EXISTENCE_CHECK_FILES:
        if d == dest_rel:
            return t
    return None


# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------


def _make_diff(current_body: str, canonical_body: str, n: int = 10) -> str:
    """Return a unified diff between current_body and canonical_body, limited to n context lines."""
    current_lines = current_body.splitlines(keepends=True)
    canonical_lines = canonical_body.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            current_lines,
            canonical_lines,
            fromfile="current",
            tofile="canonical",
            n=n,
        )
    )
    return "".join(diff_lines)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------


def sync_project(
    project_dir: Path,
    applies_to: str = "all",
    yes: bool = False,
    dry_run: bool = False,
) -> SyncResult:
    """
    Runs audit, then applies MISSING and INCONSISTENT items and prunes EXTRA
    items in CANONICAL_FILES whose section key canon has explicitly retired.
    EXTRA items are preserved unless canon has explicitly retired them
    (``RETIRED_SECTIONS``); project overrides win over retirement.
    Returns SyncResult describing what was changed and what was preserved.

    When yes=False, the user is prompted before each change — retirement
    prunes included, each named with its section key and retiring story ID.
    Declined changes are recorded in result.skipped.

    When dry_run=True, nothing is written and no prompts are shown; the
    result carries the same classifications (including RETIRED) that the
    apply path would act on.
    """
    project_dir = Path(project_dir).resolve()

    # Security: path traversal containment guard
    if not project_dir.is_dir() or len(project_dir.parts) < 3:
        click.echo(
            f"error: project-dir resolves to a suspicious path: {project_dir}",
            err=True,
        )
        sys.exit(1)

    result = SyncResult(project_dir=project_dir, dry_run=dry_run)

    # Load saved template context for rendering when creating/patching files
    context = _load_project_context(project_dir)
    # audit_project() injects this at runtime but _load_project_context does not;
    # sync's rendering path must inject it here so CLAUDE.build.md.j2 renders correctly.
    context.setdefault("pairmode_scripts_dir", str(Path(__file__).resolve().parent))

    # Warn if test_command disagrees with stack (advisory; does not block sync)
    _test_cmd = context.get("test_command", "")
    _stack = context.get("stack", "")
    for _warn in _validate_test_command(_test_cmd, _stack):
        click.echo(f"warning: {_warn}", err=True)

    # Load overrides: sections intentionally diverged from canonical templates
    overrides = _load_overrides(project_dir)

    # Run audit to get the delta
    audit = audit_project(project_dir, applies_to=applies_to)

    # Collect lesson IDs from MISSING items
    for item in audit.missing:
        if item.lesson_id and item.lesson_id not in result.lessons_applied:
            result.lessons_applied.append(item.lesson_id)

    # Group MISSING items by file
    missing_by_file: dict[str, list[AuditItem]] = {}
    for item in audit.missing:
        missing_by_file.setdefault(item.file, []).append(item)

    # Group INCONSISTENT items by file
    inconsistent_by_file: dict[str, list[AuditItem]] = {}
    for item in audit.inconsistent:
        inconsistent_by_file.setdefault(item.file, []).append(item)

    # Build scaffold-file set for quick lookup (Phase 7 docs with section-level comparison)
    scaffold_dests = {d for d, _t in SCAFFOLD_FILES}
    canonical_dests = {d for d, _t in CANONICAL_FILES}

    # Classify EXTRA items (INFRA-311): an EXTRA section in a CANONICAL_FILES
    # file whose key is in RETIRED_SECTIONS is RETIRED (once-canonical, since
    # removed by canon) — everything else is a genuine project extension and
    # keeps the preservation contract. Classification happens here, before
    # any prompt/apply branch, so dry-run and apply consume the same records.
    retired_by_file: dict[str, list[tuple[AuditItem, str]]] = {}
    genuine_extra: list[AuditItem] = []
    for item in audit.extra:
        retiring_story = RETIRED_SECTIONS.get(item.section)
        if retiring_story is not None and item.file in canonical_dests:
            retired_by_file.setdefault(item.file, []).append((item, retiring_story))
        else:
            genuine_extra.append(item)

    # Process files with MISSING items
    for dest_rel, items in missing_by_file.items():
        template_rel = _dest_to_template(dest_rel)
        if template_rel is None:
            continue

        # Scaffold files use enriched context with Phase 7 defaults
        if dest_rel in scaffold_dests:
            enriched_context = _enrich_scaffold_context(context)
            rendered_text = _render_template(template_rel, enriched_context) or _get_template_text(template_rel)
            project_path = project_dir / dest_rel
            if not project_path.exists():
                if not yes and not dry_run:
                    confirmed = click.confirm(
                        f"Create {dest_rel} (file missing)?",
                        default=False,
                    )
                    if not confirmed:
                        result.skipped.append(
                            f"{dest_rel} (file missing) (user declined)"
                        )
                        continue
                if not dry_run:
                    project_path.parent.mkdir(parents=True, exist_ok=True)
                    project_path.write_text(rendered_text, encoding="utf-8")
                result.applied.append(f"Created {dest_rel} (file was missing)")
            else:
                # File exists but is missing some sections — append them
                canonical_sections = _split_sections(rendered_text)
                project_text = project_path.read_text(encoding="utf-8")
                changed = False
                for item in items:
                    section_key = item.section
                    if (dest_rel, section_key) in overrides:
                        click.echo(
                            f"  (skipped: .pairmode-overrides declares this section as project-owned)"
                        )
                        result.skipped.append(
                            f"{dest_rel}: section '{section_key}' (override declared)"
                        )
                        continue
                    if section_key in canonical_sections:
                        canonical_body = canonical_sections[section_key]
                        if not yes and not dry_run:
                            confirmed = click.confirm(
                                f"Append section '{section_key}' to {dest_rel}?",
                                default=False,
                            )
                            if not confirmed:
                                result.skipped.append(
                                    f"{dest_rel}: section '{section_key}' (user declined)"
                                )
                                continue
                        project_text = _append_section_to_file(
                            project_text, section_key, canonical_body
                        )
                        result.applied.append(
                            f"Appended section '{section_key}' to {dest_rel}"
                        )
                        changed = True
                if changed and not dry_run:
                    project_path.write_text(project_text, encoding="utf-8")
            continue

        rendered_text = _render_template(template_rel, context) or _get_template_text(template_rel)
        project_path = project_dir / dest_rel

        if not project_path.exists():
            # File is entirely missing — create it with rendered canonical content
            if not yes and not dry_run:
                confirmed = click.confirm(
                    f"Create {dest_rel} (file missing)?",
                    default=False,
                )
                if not confirmed:
                    result.skipped.append(
                        f"{dest_rel} (file missing) (user declined)"
                    )
                    continue
            if not dry_run:
                project_path.parent.mkdir(parents=True, exist_ok=True)
                project_path.write_text(rendered_text, encoding="utf-8")
            result.applied.append(f"Created {dest_rel} (file was missing)")
        else:
            # File exists but is missing some sections — append them
            canonical_sections = _split_sections(rendered_text)
            project_text = project_path.read_text(encoding="utf-8")
            changed = False
            for item in items:
                section_key = item.section
                if (dest_rel, section_key) in overrides:
                    click.echo(
                        f"  (skipped: .pairmode-overrides declares this section as project-owned)"
                    )
                    result.skipped.append(
                        f"{dest_rel}: section '{section_key}' (override declared)"
                    )
                    continue
                if section_key in canonical_sections:
                    canonical_body = canonical_sections[section_key]
                    if not yes and not dry_run:
                        confirmed = click.confirm(
                            f"Append section '{section_key}' to {dest_rel}?",
                            default=False,
                        )
                        if not confirmed:
                            result.skipped.append(
                                f"{dest_rel}: section '{section_key}' (user declined)"
                            )
                            continue
                    project_text = _append_section_to_file(
                        project_text, section_key, canonical_body
                    )
                    result.applied.append(
                        f"Appended section '{section_key}' to {dest_rel}"
                    )
                    changed = True
            if changed and not dry_run:
                project_path.write_text(project_text, encoding="utf-8")

    # Process files with INCONSISTENT items (skipped when context file is absent)
    if audit.context_missing:
        click.echo(
            "Skipping INCONSISTENT patch: no pairmode_context.json — run bootstrap first.",
            err=True,
        )
        inconsistent_by_file = {}

    for dest_rel, items in inconsistent_by_file.items():
        template_rel = _dest_to_template(dest_rel)
        if template_rel is None:
            continue

        # Scaffold files use enriched context with Phase 7 defaults
        render_context = _enrich_scaffold_context(context) if dest_rel in scaffold_dests else context
        rendered_text = _render_template(template_rel, render_context) or _get_template_text(template_rel)
        canonical_sections = _split_sections(rendered_text)
        project_path = project_dir / dest_rel

        if not project_path.exists():
            # Shouldn't happen (inconsistent means file exists), but handle gracefully
            if not yes and not dry_run:
                confirmed = click.confirm(
                    f"Create {dest_rel} (file missing)?",
                    default=False,
                )
                if not confirmed:
                    result.skipped.append(
                        f"{dest_rel} (file missing) (user declined)"
                    )
                    continue
            if not dry_run:
                project_path.parent.mkdir(parents=True, exist_ok=True)
                project_path.write_text(rendered_text, encoding="utf-8")
            result.applied.append(f"Created {dest_rel} (file was missing during inconsistent pass)")
            continue

        project_text = project_path.read_text(encoding="utf-8")
        changed = False
        for item in items:
            section_key = item.section
            if (dest_rel, section_key) in overrides:
                click.echo(
                    f"  (skipped: .pairmode-overrides declares this section as project-owned)"
                )
                result.skipped.append(
                    f"{dest_rel}: section '{section_key}' (override declared)"
                )
                continue
            if section_key in canonical_sections:
                canonical_body = canonical_sections[section_key]
                if not yes and not dry_run:
                    # Show diff before prompting
                    # Extract current body for this section
                    parts = _split_by_h2(project_text)
                    current_body = ""
                    for header, body in parts:
                        if _normalise(header) == section_key:
                            current_body = body
                            break
                    diff_text = _make_diff(current_body, canonical_body)
                    if diff_text:
                        click.echo(f"  (--- current  +++ canonical)")
                        click.echo(diff_text, nl=False)
                    confirmed = click.confirm(
                        f"Update section '{section_key}' in {dest_rel}?",
                        default=False,
                    )
                    if not confirmed:
                        result.skipped.append(
                            f"{dest_rel}: section '{section_key}' (user declined)"
                        )
                        continue
                project_text = _replace_section_in_file(project_text, section_key, canonical_body)
                result.applied.append(
                    f"Updated section '{section_key}' in {dest_rel} to match canonical"
                )
                changed = True
        if changed and not dry_run:
            project_path.write_text(project_text, encoding="utf-8")

    # Process files with RETIRED items (INFRA-311): EXTRA sections in
    # CANONICAL_FILES whose key canon has explicitly retired. Same three-way
    # contract as every other mutation site: override wins first (recorded as
    # override-kept), then per-section confirmation (default No) naming the
    # section key and the retiring story ID, declined prunes go to skipped.
    for dest_rel, records in retired_by_file.items():
        project_path = project_dir / dest_rel
        if not project_path.exists():
            continue
        project_text = project_path.read_text(encoding="utf-8")
        changed = False
        for item, retiring_story in records:
            section_key = item.section
            if (dest_rel, section_key) in overrides:
                click.echo(
                    f"  (kept: .pairmode-overrides declares this section as "
                    f"project-owned; override wins over retirement)"
                )
                result.preserved.append(
                    f"{dest_rel}: section '{section_key}' "
                    f"(override-kept; canon-retired by {retiring_story})"
                )
                continue
            if not yes and not dry_run:
                confirmed = click.confirm(
                    f"Remove retired section '{section_key}' from {dest_rel} "
                    f"(canon-retired by {retiring_story})?",
                    default=False,
                )
                if not confirmed:
                    result.skipped.append(
                        f"{dest_rel}: section '{section_key}' "
                        f"(canon-retired by {retiring_story}) (user declined)"
                    )
                    continue
            if not dry_run:
                project_text = _remove_section_from_file(project_text, section_key)
                changed = True
            result.retired.append(
                f"{dest_rel}: section '{section_key}' — canon-retired by {retiring_story}"
            )
        if changed and not dry_run:
            project_path.write_text(project_text, encoding="utf-8")

    # Record genuine (non-retired) EXTRA items as preserved
    for item in genuine_extra:
        result.preserved.append(
            f"{item.file}: section '{item.section}' (project-specific)"
        )

    # Rail gap check: prompt to add default rails missing from docs/stories/
    stack = context.get("stack", "")
    missing_rails = _check_rail_gaps(project_dir, stack)
    for rail in missing_rails:
        click.echo(f"  \u26a0 Standard rail {rail} not in this project.")
        if not yes and not dry_run:
            confirmed = click.confirm(f"Add rail {rail}?", default=False)
        else:
            confirmed = True
        if confirmed:
            if not dry_run:
                rail_dir = project_dir / "docs" / "stories" / rail
                rail_dir.mkdir(parents=True, exist_ok=True)
                era_path = _find_era(project_dir)
                if era_path is not None:
                    _add_rail_to_era(era_path, rail)
            result.applied.append(f"Created rail directory docs/stories/{rail}/")

    if dry_run:
        return result

    # Register PreToolUse + context-budget-gate hooks in
    # .claude/settings.local.json (INFRA-206 PreToolUse; INFRA-208
    # UserPromptSubmit / SessionStart / PostToolUse Task|Agent — see
    # CER-067; moved out of the committed settings.json by INFRA-319 /
    # CER-127). settings_path stays the committed-file path — the
    # registrars derive project_dir from it and evict any stale entry left
    # there (A7).
    settings_path = project_dir / ".claude" / "settings.json"
    plugin_root = Path(__file__).resolve().parent.parent.parent.parent
    _register_pretooluse_hook(settings_path, plugin_root)
    _register_context_budget_hooks(settings_path, plugin_root)
    _merge_deny_list(settings_path, DEFAULT_DENY)
    _prune_superseded_deny_entries(settings_path, _SUPERSEDED_DENY_ENTRIES)

    # Update .companion/state.json
    #
    # INFRA-285 (CER-097, item E4): the read-merge-write runs under the advisory
    # state lock and persists via atomic replace. Sync is a whole-file rewrite
    # of state.json that deliberately preserves every key it does not own, so a
    # concurrent hook write landing between the read and the write would be
    # silently discarded — and a torn write would revert the entire companion
    # state to defaults.
    state_path = project_dir / ".companion" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with state_lock(state_path):
        existing_state: dict = {}
        if state_path.exists():
            try:
                existing_state = json.loads(state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing_state = {}

        # Merge — do not overwrite other fields
        existing_state["pairmode_version"] = result.pairmode_version
        existing_state["last_sync"] = result.last_sync
        existing_state["lessons_applied"] = result.lessons_applied

        # Seed context budget defaults when absent (INFRA-133)
        for key, default in [
            ("context_budget_threshold", 120000),
            ("context_budget_overrun_pct", 0.10),
            ("expected_step_tokens", THIN_HARNESS_STEP_TOKENS),
            ("context_budget_reprompt_margin", 10000),
        ]:
            existing_state.setdefault(key, default)

        _atomic_write_json(state_path, existing_state)

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_sync_output(result: SyncResult) -> str:
    """Human-readable sync report."""
    lines: list[str] = []
    if result.dry_run:
        lines.append(f"SYNC DRY-RUN — {result.project_dir.name} (no files written)")
    else:
        lines.append(f"SYNC COMPLETE — {result.project_dir.name}")
    lines.append("")

    if result.applied:
        lines.append("Would apply (dry-run):" if result.dry_run else "Applied:")
        for change in result.applied:
            lines.append(f"  \u2713 {change}")
        lines.append("")

    if result.retired:
        lines.append(
            "RETIRED (canon-removed, would prune):"
            if result.dry_run
            else "RETIRED (canon-removed, pruned):"
        )
        for item in result.retired:
            lines.append(f"  \u2717 {item}")
        lines.append("")

    if result.preserved:
        lines.append("Preserved:")
        for item in result.preserved:
            lines.append(f"  \u2192 {item}")
        lines.append("")

    if result.skipped:
        lines.append("Skipped (user declined):")
        for item in result.skipped:
            lines.append(f"  \u2717 {item}")
        lines.append("")

    if result.dry_run:
        lines.append("State not updated (dry-run)")
    else:
        lines.append("State updated: .companion/state.json")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to the project directory to sync.",
)
@click.option(
    "--applies-to",
    default="all",
    show_default=True,
    help="Project type for lesson filtering (e.g. 'python', 'typescript', 'all').",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Apply all changes without prompting for confirmation.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Report what would change (including RETIRED prunes) without writing anything.",
)
def main(project_dir: Path, applies_to: str, yes: bool, dry_run: bool) -> None:
    """Sync a project directory against canonical pairmode templates."""
    result = sync_project(project_dir, applies_to=applies_to, yes=yes, dry_run=dry_run)
    click.echo(format_sync_output(result))


if __name__ == "__main__":
    main()
