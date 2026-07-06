---
id: INFRA-190
rail: INFRA
title: "spec_preflight.py — route and constant reference checker"
status: planned
phase: "84"
story_class: code
auth_gated: false
schema_introduces: false
primary_files:
  - skills/pairmode/scripts/spec_preflight.py
touches:
  - tests/pairmode/test_spec_preflight.py
---

## Requires

- `skills/pairmode/scripts/` directory exists with sibling scripts following the pattern: `from __future__ import annotations`, stdlib-only plus `click`, `sys.path.insert` for repo-root imports, `@click.command()` with `if __name__ == "__main__"` guard.
- No existing `spec_preflight.py` in `skills/pairmode/scripts/`.
- INFRA-187 has landed (body-section enforcement ensures story Ensures sections are non-pointer for code stories — the sections the preflight scans).

## Ensures

- `skills/pairmode/scripts/spec_preflight.py` exists as a new file.
- `grep -n "def run_preflight" skills/pairmode/scripts/spec_preflight.py` returns at least one match.
- `grep -n "ROUTE_RE\|_route_re\|/api/" skills/pairmode/scripts/spec_preflight.py` returns at least one match.
- `grep -n "CONST_RE\|_const_re\|SCREAMING\|[A-Z][A-Z0-9_]" skills/pairmode/scripts/spec_preflight.py` returns at least one match (constant pattern).
- `uv run python skills/pairmode/scripts/spec_preflight.py --story-id INFRA-190 --project-dir .` exits 0 (always — informational tool).
- When a story's Ensures section references `/api/nonexistent-route-zzz9` and no such route is defined in the project source, running the tool against that story prints a warning containing `"route"` and `"/api/nonexistent-route-zzz9"`.
- When a story references `FAKE_CONSTANT_ZZZ9` in a code fence and no such token is defined in the project source, running the tool prints a warning containing `"constant"` and `"FAKE_CONSTANT_ZZZ9"`.
- The tokens `GET`, `POST`, `PUT`, `DELETE`, `NULL`, `TRUE`, `FALSE` do NOT produce constant warnings.
- Running the tool against a story with no route or constant references produces empty stdout and exits 0.
- `tests/pairmode/test_spec_preflight.py` exists and all tests pass.

## Instructions

**Create `skills/pairmode/scripts/spec_preflight.py`** as a new file with this structure:

```python
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
```

**No changes to any existing file in this story.** All changes are in the new file.

## Tests

Create `tests/pairmode/test_spec_preflight.py`:

```python
"""Tests for skills/pairmode/scripts/spec_preflight.py — INFRA-190."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))
import spec_preflight as sp


def test_extract_sections_returns_ensures_and_instructions():
    text = "---\nid: X\n---\n## Ensures\n- foo bar\n\n## Instructions\nbaz\n"
    body = sp._extract_body_sections(text)
    assert "foo bar" in body
    assert "baz" in body


def test_extract_sections_ignores_requires():
    text = "---\nid: X\n---\n## Requires\nprecondition\n\n## Ensures\n- assertion\n"
    body = sp._extract_body_sections(text)
    assert "assertion" in body
    assert "precondition" not in body


def test_check_routes_warns_when_route_not_in_source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("// no routes here\n")
    warnings = sp._check_routes("Call /api/nonexistent-zzz9 to fetch data.", tmp_path)
    assert any("/api/nonexistent-zzz9" in w for w in warnings)


def test_check_routes_clean_when_route_found(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "routes.ts").write_text('router.get("/api/health", handler)\n')
    warnings = sp._check_routes("Call /api/health to check status.", tmp_path)
    assert not warnings


def test_check_routes_empty_body_no_warnings(tmp_path):
    warnings = sp._check_routes("No routes mentioned here.", tmp_path)
    assert not warnings


def test_check_constants_warns_when_constant_not_in_source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")
    warnings = sp._check_constants("Use `FAKE_CONSTANT_ZZZ9` in the config.", tmp_path)
    assert any("FAKE_CONSTANT_ZZZ9" in w for w in warnings)


def test_check_constants_clean_when_constant_found(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "config.py").write_text("REAL_CONST = 42\n")
    warnings = sp._check_constants("Set `REAL_CONST` to configure.", tmp_path)
    assert not warnings


def test_check_constants_excludes_http_methods(tmp_path):
    warnings = sp._check_constants("Use `GET` and `POST`.", tmp_path)
    assert not warnings


def test_check_constants_excludes_null_true_false(tmp_path):
    warnings = sp._check_constants("Value should be `NULL` or `TRUE` or `FALSE`.", tmp_path)
    assert not warnings


def test_run_preflight_returns_empty_for_clean_story(tmp_path):
    story = tmp_path / "docs" / "stories" / "INFRA"
    story.mkdir(parents=True)
    (story / "INFRA-190.md").write_text(
        "---\nid: INFRA-190\nrail: INFRA\n---\n## Ensures\n- The file exists.\n"
    )
    (tmp_path / "src").mkdir()
    assert sp.run_preflight(story / "INFRA-190.md", tmp_path) == []


def test_run_preflight_warns_on_missing_route(tmp_path):
    story = tmp_path / "docs" / "stories" / "INFRA"
    story.mkdir(parents=True)
    (story / "INFRA-191.md").write_text(
        "---\nid: INFRA-191\nrail: INFRA\n---\n## Ensures\n- Call /api/ghost-route-zzz.\n"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("# nothing\n")
    warnings = sp.run_preflight(story / "INFRA-191.md", tmp_path)
    assert any("/api/ghost-route-zzz" in w for w in warnings)


def test_run_preflight_cli_exits_0(tmp_path):
    story = tmp_path / "docs" / "stories" / "INFRA"
    story.mkdir(parents=True)
    (story / "INFRA-190.md").write_text(
        "---\nid: INFRA-190\nrail: INFRA\n---\n## Ensures\n- plain assertion.\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        sp.spec_preflight,
        ["--story-id", "INFRA-190", "--project-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
```

```bash
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/test_spec_preflight.py -x -q
PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q
```
