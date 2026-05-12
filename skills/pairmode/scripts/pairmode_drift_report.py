"""
pairmode_drift_report.py — Cross-project drift detection for pairmode methodology files.

Compares each project's ``CLAUDE.build.md`` and ``.claude/agents/`` against anchor's
canonical templates and classifies per-project differences as:

  MISSING    — section present in canonical template but absent from project
  EXTRA      — section present in project but absent from canonical template
  DRIFT      — section present in both but content has diverged
  INTENTIONAL — section declared in ``.pairmode-overrides`` (added by INFRA-064)

With ``--convergent``, surfaces drift patterns appearing identically in 2+ projects
as convergence candidates.

CLI:
    uv run python pairmode_drift_report.py drift-report \\
        --projects /path/to/proj1 /path/to/proj2 \\
        [--convergent] [--output text|json]
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import click
import jinja2

# ---------------------------------------------------------------------------
# Repo root on sys.path so sibling imports work when run as CLI
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
AGENTS_TEMPLATES_DIR = TEMPLATES_DIR / "agents"

# Canonical files examined by drift-report: CLAUDE.build.md + all agent files.
# Agent files are discovered dynamically from the project's .claude/agents/ directory.
CLAUDE_BUILD_TEMPLATE = "CLAUDE.build.md.j2"
CLAUDE_BUILD_PROJECT_PATH = "CLAUDE.build.md"


# ---------------------------------------------------------------------------
# Depth guard — mirrors pattern in effort_db.py and audit.py
# ---------------------------------------------------------------------------


def _depth_guard(path: Path) -> Path:
    """Resolve *path* and ensure it is not a suspiciously shallow location.

    Raises ``ValueError`` when the resolved path has fewer than 3 components
    (e.g. ``/tmp`` or ``/``), guarding against path traversal to root-level dirs.
    """
    resolved = Path(path).resolve()
    if len(resolved.parts) < 3:
        raise ValueError(f"project path too shallow: {resolved}")
    return resolved


def _safe_project_dir(raw: str | Path) -> Path | None:
    """Validate a project directory argument.

    Returns the resolved ``Path`` when it is a directory with at least 3 path
    components, ``None`` otherwise (warning written to stderr).
    """
    try:
        resolved = _depth_guard(Path(raw))
    except ValueError as exc:
        click.echo(f"warning: {exc} — skipping", err=True)
        return None
    if not resolved.is_dir():
        click.echo(f"warning: not a directory: {resolved} — skipping", err=True)
        return None
    return resolved


# ---------------------------------------------------------------------------
# Section splitting (reused from audit.py patterns)
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^(##+ .+|---)$", re.MULTILINE)


def _normalise(text: str) -> str:
    """Lowercase and collapse whitespace for fuzzy comparison."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _split_sections(text: str) -> dict[str, str]:
    """Split a markdown document into sections keyed by normalised header.

    Splits on ``##`` headers and ``---`` separators.  Returns an ordered dict
    mapping a normalised key to the section body text.
    """
    parts = _SECTION_RE.split(text)
    sections: dict[str, str] = {}
    key_counter = 0

    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if not chunk:
            i += 1
            continue

        if _SECTION_RE.fullmatch(chunk.strip()):
            header = chunk.strip()
            body = parts[i + 1].strip() if (i + 1) < len(parts) else ""
            key = _normalise(header)
            if key in sections:
                key = f"{key}__{key_counter}"
                key_counter += 1
            sections[key] = body
            i += 2
        else:
            # Preamble before first header
            key = f"__preamble__{key_counter}"
            key_counter += 1
            sections[key] = chunk
            i += 1

    return sections


def _is_separator_key(key: str) -> bool:
    """Return True when *key* represents a ``---`` separator (not a real section)."""
    return bool(re.match(r"^-+(__\d+)?$", key))


# ---------------------------------------------------------------------------
# .pairmode-overrides parser
# Reused from audit.py — same file format, same parsing logic.
# INFRA-064 wires INTENTIONAL classification; here we provide the stub/hook.
# ---------------------------------------------------------------------------


def _load_overrides(project_dir: Path) -> set[tuple[str, str]]:
    """Return set of (relative_file_path, normalised_section_key) declared overrides.

    Parses ``project_dir / ".pairmode-overrides"``. Blank lines and comment
    lines (``#``) are skipped. Each valid line is split on ``:`` (one split)
    into ``(file_path, section_key)``.  The section_key is normalised (lowercased,
    whitespace collapsed) so it matches the keys produced by ``_split_sections``.
    """
    overrides_path = project_dir / ".pairmode-overrides"
    if not overrides_path.exists():
        return set()

    result: set[tuple[str, str]] = set()
    try:
        text = overrides_path.read_text(encoding="utf-8")
    except OSError:
        return result

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        file_path, section_key = stripped.split(":", 1)
        result.add((file_path.strip(), _normalise(section_key.strip())))

    return result


# ---------------------------------------------------------------------------
# Jinja2 environment for rendering canonical templates
# ---------------------------------------------------------------------------

_JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=jinja2.Undefined,  # silently replaces unknown vars with ""
    keep_trailing_newline=True,
)


def _load_project_context(project_dir: Path) -> dict:
    """Load pairmode_context.json for template rendering; fall back to minimal defaults."""
    context_path = project_dir / ".companion" / "pairmode_context.json"
    if context_path.exists():
        try:
            return json.loads(context_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "project_name": project_dir.name,
        "project_description": "",
        "stack": "",
        "build_command": "",
        "test_command": "",
        "migration_command": "",
        "domain_model": "",
        "domain_isolation_rule": "",
        "checklist_items": [],
        "protected_paths": [],
        "non_negotiables": [],
        "module_structure": [],
        "layer_rules": [],
    }


def _render_template_sections(template_rel: str, context: dict) -> dict[str, str]:
    """Render *template_rel* with *context* and return its sections dict."""
    try:
        rendered = _JINJA_ENV.get_template(template_rel).render(**context)
    except (jinja2.TemplateNotFound, jinja2.TemplateError):
        return {}
    return _split_sections(rendered)


def _read_project_sections(project_dir: Path, rel_path: str) -> dict[str, str] | None:
    """Read a project file and return its sections dict, or ``None`` if missing."""
    full_path = project_dir / rel_path
    if not full_path.exists():
        return None
    return _split_sections(full_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class DriftItem:
    """A single classified difference for one file+section in a project."""

    file: str
    section: str
    classification: str  # "MISSING" | "EXTRA" | "DRIFT" | "INTENTIONAL"
    # For DRIFT: the normalised project body (used for convergence grouping)
    project_body: str = ""
    # For DRIFT: the normalised canonical body
    canonical_body: str = ""


@dataclass
class ProjectDriftResult:
    """All drift findings for a single project."""

    project_name: str
    project_dir: Path
    items: list[DriftItem] = field(default_factory=list)

    # Convenience views
    @property
    def missing(self) -> list[DriftItem]:
        return [i for i in self.items if i.classification == "MISSING"]

    @property
    def extra(self) -> list[DriftItem]:
        return [i for i in self.items if i.classification == "EXTRA"]

    @property
    def drift(self) -> list[DriftItem]:
        return [i for i in self.items if i.classification == "DRIFT"]

    @property
    def intentional(self) -> list[DriftItem]:
        return [i for i in self.items if i.classification == "INTENTIONAL"]


@dataclass
class ConvergenceCandidate:
    """A drift pattern shared identically across 2+ projects."""

    file: str
    section: str
    project_body: str  # normalised drifted content
    projects: list[str]  # project names

    @property
    def count(self) -> int:
        return len(self.projects)


# ---------------------------------------------------------------------------
# Per-project drift analysis
# ---------------------------------------------------------------------------


def _analyse_file(
    project_dir: Path,
    project_file_rel: str,
    template_rel: str,
    context: dict,
    overrides: set[tuple[str, str]],
) -> list[DriftItem]:
    """Compare one project file against one canonical template; return drift items.

    ``overrides`` is the parsed ``.pairmode-overrides`` set for this project.
    Sections listed in overrides that would otherwise be classified as DRIFT or
    EXTRA are reclassified as INTENTIONAL and excluded from convergence candidates.
    """
    canonical_sections = _render_template_sections(template_rel, context)
    if not canonical_sections:
        return []

    project_sections = _read_project_sections(project_dir, project_file_rel)

    items: list[DriftItem] = []

    if project_sections is None:
        # Entire file is missing — every canonical section is MISSING
        for key in canonical_sections:
            if _is_separator_key(key):
                continue
            items.append(
                DriftItem(
                    file=project_file_rel,
                    section=key,
                    classification="MISSING",
                )
            )
        return items

    canonical_keys = set(canonical_sections.keys())
    project_keys = set(project_sections.keys())

    # Sections in canonical but not in project → MISSING
    for key in canonical_keys - project_keys:
        if _is_separator_key(key):
            continue
        items.append(
            DriftItem(
                file=project_file_rel,
                section=key,
                classification="MISSING",
            )
        )

    # Sections in project but not in canonical → EXTRA or INTENTIONAL
    for key in project_keys - canonical_keys:
        if _is_separator_key(key):
            continue
        if (project_file_rel, key) in overrides:
            items.append(
                DriftItem(
                    file=project_file_rel,
                    section=key,
                    classification="INTENTIONAL",
                    project_body=_normalise(project_sections[key]),
                )
            )
        else:
            items.append(
                DriftItem(
                    file=project_file_rel,
                    section=key,
                    classification="EXTRA",
                    project_body=_normalise(project_sections[key]),
                )
            )

    # Sections in both — compare bodies; diverged sections are DRIFT or INTENTIONAL
    for key in canonical_keys & project_keys:
        if _is_separator_key(key):
            continue
        canonical_body = _normalise(canonical_sections[key])
        project_body = _normalise(project_sections[key])
        if canonical_body != project_body:
            if (project_file_rel, key) in overrides:
                items.append(
                    DriftItem(
                        file=project_file_rel,
                        section=key,
                        classification="INTENTIONAL",
                        project_body=project_body,
                        canonical_body=canonical_body,
                    )
                )
            else:
                items.append(
                    DriftItem(
                        file=project_file_rel,
                        section=key,
                        classification="DRIFT",
                        project_body=project_body,
                        canonical_body=canonical_body,
                    )
                )

    return items


def _analyse_agents(
    project_dir: Path,
    context: dict,
    overrides: set[tuple[str, str]],
) -> list[DriftItem]:
    """Analyse all agent files in ``<project_dir>/.claude/agents/``.

    For each ``*.md`` file found, looks up the matching template by stem.
    Files without a matching template are surfaced as EXTRA.
    """
    agents_dir = project_dir / ".claude" / "agents"
    if not agents_dir.is_dir():
        # No agents directory — report all canonical agent templates as MISSING
        items: list[DriftItem] = []
        for tpl in sorted(AGENTS_TEMPLATES_DIR.glob("*.md.j2")):
            rel = f".claude/agents/{tpl.stem}"
            canonical_sections = _render_template_sections(
                f"agents/{tpl.name}", context
            )
            for key in canonical_sections:
                if _is_separator_key(key):
                    continue
                items.append(DriftItem(file=rel, section=key, classification="MISSING"))
        return items

    items = []
    seen_stems: set[str] = set()

    for agent_file in sorted(agents_dir.glob("*.md")):
        stem = agent_file.stem
        seen_stems.add(stem)
        template_name = f"agents/{stem}.md.j2"
        template_path = AGENTS_TEMPLATES_DIR / f"{stem}.md.j2"

        project_rel = f".claude/agents/{agent_file.name}"

        if not template_path.exists():
            # Agent exists in project but has no canonical template → EXTRA file
            project_sections = _split_sections(
                agent_file.read_text(encoding="utf-8")
            )
            for key in project_sections:
                if _is_separator_key(key):
                    continue
                items.append(
                    DriftItem(
                        file=project_rel,
                        section=key,
                        classification="EXTRA",
                        project_body=_normalise(project_sections[key]),
                    )
                )
            continue

        file_items = _analyse_file(
            project_dir, project_rel, template_name, context, overrides
        )
        items.extend(file_items)

    # Canonical agent templates with no corresponding project file → MISSING
    for tpl in sorted(AGENTS_TEMPLATES_DIR.glob("*.md.j2")):
        stem = tpl.stem.replace(".md", "")  # strip double .md if any
        # stem already has no extension since glob matched *.md.j2
        # tpl.stem for "builder.md.j2" → "builder.md", so strip:
        stem = Path(tpl.stem).stem  # "builder.md" → "builder"
        if stem not in seen_stems:
            canonical_sections = _render_template_sections(
                f"agents/{tpl.name}", context
            )
            project_rel = f".claude/agents/{stem}.md"
            for key in canonical_sections:
                if _is_separator_key(key):
                    continue
                items.append(
                    DriftItem(file=project_rel, section=key, classification="MISSING")
                )

    return items


def _analyse_project(project_dir: Path) -> ProjectDriftResult:
    """Run full drift analysis for a single project directory.

    Compares:
      - ``CLAUDE.build.md`` against ``CLAUDE.build.md.j2``
      - Each file in ``.claude/agents/`` against its matching template

    Path containment: ``project_dir`` must already be resolved and validated
    by the caller via ``_safe_project_dir``.
    """
    context = _load_project_context(project_dir)
    overrides = _load_overrides(project_dir)

    result = ProjectDriftResult(
        project_name=project_dir.name,
        project_dir=project_dir,
    )

    # Analyse CLAUDE.build.md
    build_items = _analyse_file(
        project_dir,
        CLAUDE_BUILD_PROJECT_PATH,
        CLAUDE_BUILD_TEMPLATE,
        context,
        overrides,
    )
    result.items.extend(build_items)

    # Analyse .claude/agents/
    agent_items = _analyse_agents(project_dir, context, overrides)
    result.items.extend(agent_items)

    return result


# ---------------------------------------------------------------------------
# Convergence detection
# ---------------------------------------------------------------------------


def _find_convergence_candidates(
    results: list[ProjectDriftResult],
) -> list[ConvergenceCandidate]:
    """Return drift patterns that appear identically in 2+ projects.

    Groups DRIFT items by ``(file, section, project_body)``.  A group with
    2+ distinct projects is a convergence candidate.

    INTENTIONAL items are excluded (they are declared overrides, not drift).
    """
    # Key: (file, section, normalised_project_body) → [project_name, ...]
    groups: dict[tuple[str, str, str], list[str]] = {}

    for project_result in results:
        seen_in_project: set[tuple[str, str, str]] = set()
        for item in project_result.drift:  # only DRIFT, not MISSING/EXTRA/INTENTIONAL
            key = (item.file, item.section, item.project_body)
            if key in seen_in_project:
                continue
            seen_in_project.add(key)
            groups.setdefault(key, []).append(project_result.project_name)

    candidates: list[ConvergenceCandidate] = []
    for (file, section, body), projects in groups.items():
        if len(projects) >= 2:
            candidates.append(
                ConvergenceCandidate(
                    file=file,
                    section=section,
                    project_body=body,
                    projects=projects,
                )
            )

    # Sort by count descending, then by (file, section) for determinism
    candidates.sort(key=lambda c: (-c.count, c.file, c.section))
    return candidates


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def drift_report(
    project_dirs: Sequence[str | Path],
    convergent: bool = False,
    output_format: str = "text",
) -> dict:
    """Analyse drift across one or more project directories.

    Args:
        project_dirs: Sequence of paths to project directories.
        convergent: When True, compute and include convergence candidates.
        output_format: "text" or "json" (controls what ``_format_*`` helpers produce;
            caller may also use the returned dict directly).

    Returns:
        A dict with keys:
          ``"projects"``  — list of per-project result dicts
          ``"convergence_candidates"`` — list of candidate dicts (empty when
                                         ``convergent=False``)
    """
    valid_dirs: list[Path] = []
    for raw in project_dirs:
        resolved = _safe_project_dir(raw)
        if resolved is not None:
            # Containment: ensure we do not accidentally walk outside the given dir.
            # _depth_guard already ran inside _safe_project_dir.
            valid_dirs.append(resolved)

    project_results: list[ProjectDriftResult] = []
    for project_dir in valid_dirs:
        project_results.append(_analyse_project(project_dir))

    candidates: list[ConvergenceCandidate] = []
    if convergent:
        candidates = _find_convergence_candidates(project_results)

    return {
        "projects": [_project_result_to_dict(r) for r in project_results],
        "convergence_candidates": [
            _candidate_to_dict(c, valid_dirs if convergent else None)
            for c in candidates
        ],
        "_results": project_results,  # internal: used by text formatter
        "_candidates": candidates,     # internal: used by text formatter
    }


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _project_result_to_dict(result: ProjectDriftResult) -> dict:
    return {
        "project": result.project_name,
        "project_dir": str(result.project_dir),
        "missing": [_item_to_dict(i) for i in result.missing],
        "extra": [_item_to_dict(i) for i in result.extra],
        "drift": [_item_to_dict(i) for i in result.drift],
        "intentional": [_item_to_dict(i) for i in result.intentional],
    }


def _item_to_dict(item: DriftItem) -> dict:
    d: dict = {"file": item.file, "section": item.section}
    if item.classification == "DRIFT":
        d["project_body"] = item.project_body
    return d


def _candidate_to_dict(c: ConvergenceCandidate, project_dirs: list[Path] | None = None) -> dict:
    score: float | None = None
    justification: str = "insufficient data"
    if project_dirs is not None:
        try:
            from skills.pairmode.scripts.drift_evidence import score_convergence_candidate
            pattern_id = f"{c.file}::{c.section}"
            score, justification = score_convergence_candidate(project_dirs, pattern_id)
        except Exception:  # noqa: BLE001
            pass
    return {
        "file": c.file,
        "section": c.section,
        "project_body": c.project_body,
        "projects": c.projects,
        "count": c.count,
        "score": score,
        "justification": justification,
    }


# ---------------------------------------------------------------------------
# Text output formatter
# ---------------------------------------------------------------------------


def _format_text(data: dict) -> str:
    """Render the drift report as human-readable text."""
    lines: list[str] = []

    project_results: list[ProjectDriftResult] = data.get("_results", [])
    candidates: list[ConvergenceCandidate] = data.get("_candidates", [])

    for result in project_results:
        lines.append(f"PROJECT: {result.project_name}  ({result.project_dir})")
        lines.append("-" * 60)

        if result.missing:
            lines.append(f"  MISSING ({len(result.missing)} section(s)):")
            for item in result.missing:
                lines.append(f"    - {item.file}: {item.section}")

        if result.extra:
            lines.append(f"  EXTRA ({len(result.extra)} section(s)):")
            for item in result.extra:
                lines.append(f"    + {item.file}: {item.section}")

        if result.drift:
            lines.append(f"  DRIFT ({len(result.drift)} section(s)):")
            for item in result.drift:
                lines.append(f"    ~ {item.file}: {item.section}")

        if result.intentional:
            lines.append(
                f"  INTENTIONAL (declared in .pairmode-overrides): "
                f"{len(result.intentional)} section(s)."
            )
            for item in result.intentional:
                lines.append(f"    ! {item.file}: {item.section}")

        if not (result.missing or result.extra or result.drift or result.intentional):
            lines.append("  No drift detected.")

        lines.append("")

    if candidates:
        lines.append("CONVERGENCE CANDIDATES")
        lines.append("=" * 60)
        lines.append(
            "The following drift patterns appear identically in 2+ projects"
            " and may warrant a template update:"
        )
        lines.append("")
        for cand in candidates:
            lines.append(
                f"  [{cand.count} projects] {cand.file}: {cand.section}"
            )
            lines.append(f"    Projects: {', '.join(cand.projects)}")
            body_preview = cand.project_body[:120]
            if len(cand.project_body) > 120:
                body_preview += " ..."
            lines.append(f"    Drifted content: {body_preview!r}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@click.command("drift-report")
@click.option(
    "--projects",
    multiple=True,
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="One or more project directories to analyse (repeatable).",
)
@click.option(
    "--convergent",
    is_flag=True,
    default=False,
    help="Surface drift patterns shared across 2+ projects as convergence candidates.",
)
@click.option(
    "--output",
    "output_format",
    default="text",
    show_default=True,
    type=click.Choice(["text", "json"], case_sensitive=False),
    help="Output format.",
)
def main(
    projects: tuple[str, ...],
    convergent: bool,
    output_format: str,
) -> None:
    """Compare projects against canonical pairmode templates and report drift."""
    data = drift_report(
        project_dirs=projects,
        convergent=convergent,
        output_format=output_format,
    )

    if output_format == "json":
        # Strip internal keys before serialising
        output = {k: v for k, v in data.items() if not k.startswith("_")}
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(_format_text(data))


if __name__ == "__main__":
    main()
