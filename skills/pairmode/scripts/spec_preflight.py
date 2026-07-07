"""
spec_preflight.py — Scan a story file's body sections for route and constant
references and verify they exist in the project source tree.

Always exits 0. Output is plain-text warnings; empty output means clean.

Story: INFRA-190.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import click

# Route pattern: /api/<path>
_ROUTE_RE = re.compile(r"/api/[a-zA-Z0-9/_-]+")

# Constant pattern: SCREAMING_SNAKE of 3+ chars in inline code or code fences
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_CODE_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

# Tokens to exclude from constant warnings
_CONST_EXCLUSIONS = frozenset({
    "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS",
    "NULL", "TRUE", "FALSE", "AND", "NOT", "FOR", "ALL", "NEW",
    "SET", "USE", "ADD", "API", "URL", "SQL", "CSS", "ENV",
    "PASS", "FAIL", "UUID", "ID",
})

# Sections to scan
_SECTIONS_RE = re.compile(
    r"^##\s+(?:Ensures|Instructions|Implementation notes)\s*\n(.*?)(?=^##|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

# Source file extensions to grep
_SOURCE_EXTS = ("*.py", "*.ts", "*.tsx", "*.js", "*.jsx")
_SKIP_DIRS = frozenset({"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"})


def _extract_body_sections(text: str) -> str:
    parts = _SECTIONS_RE.findall(text)
    return "\n".join(parts)


def _grep_source(project_dir: Path, pattern: str) -> bool:
    for ext in _SOURCE_EXTS:
        for f in project_dir.rglob(ext):
            if any(d in f.parts for d in _SKIP_DIRS):
                continue
            try:
                if pattern in f.read_text(encoding="utf-8", errors="ignore"):
                    return True
            except OSError:
                continue
    return False


def _check_routes(body: str, project_dir: Path) -> list[str]:
    warnings = []
    for m in _ROUTE_RE.finditer(body):
        route = m.group(0).rstrip("\"',.")
        if not _grep_source(project_dir, route):
            warnings.append(
                f"Route warning: '{route}' referenced in story but no route definition found in source tree."
            )
    return warnings


def _check_constants(body: str, project_dir: Path) -> list[str]:
    seen: set[str] = set()

    for m in _INLINE_CODE_RE.finditer(body):
        token = m.group(1).strip()
        if re.match(r"^[A-Z][A-Z0-9_]{2,}$", token) and token not in _CONST_EXCLUSIONS:
            seen.add(token)

    for fence_m in _CODE_FENCE_RE.finditer(body):
        for token_m in re.finditer(r"\b([A-Z][A-Z0-9_]{2,})\b", fence_m.group(1)):
            token = token_m.group(1)
            if token not in _CONST_EXCLUSIONS:
                seen.add(token)

    warnings = []
    for token in sorted(seen):
        if not _grep_source(project_dir, token):
            warnings.append(
                f"Constant warning: '{token}' referenced in story but no definition found in source tree."
            )
    return warnings


def run_preflight(story_path: Path, project_dir: Path) -> list[str]:
    """Parse story and return list of warning strings. Empty list = clean."""
    try:
        text = story_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read story file: {exc}"]

    body = _extract_body_sections(text)
    if not body.strip():
        return []

    warnings: list[str] = []
    warnings.extend(_check_routes(body, project_dir))
    warnings.extend(_check_constants(body, project_dir))
    return warnings


@click.command()
@click.option("--story-id", required=True, help="Story ID (e.g. INFRA-190).")
@click.option(
    "--project-dir",
    default=".",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Project root to grep for route/constant definitions.",
)
def spec_preflight(story_id: str, project_dir: str) -> None:
    """Scan a story's body sections for unverifiable route and constant references.

    Always exits 0. Non-empty output = warnings to review before building.
    """
    project_path = Path(project_dir).resolve()
    rail = story_id.split("-", 1)[0]
    story_path = project_path / "docs" / "stories" / rail / f"{story_id}.md"

    if not story_path.exists():
        click.echo(f"spec-preflight: story file not found: {story_path}", err=True)
        sys.exit(0)

    for w in run_preflight(story_path, project_path):
        click.echo(w)


if __name__ == "__main__":
    spec_preflight()
