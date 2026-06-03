"""
global_session_check.py — Global SessionStart pairmode hook.

Runs once when Claude Code starts a session (via a global SessionStart hook in
~/.claude/settings.json).  For pairmode projects it prints a compact status
block so every session opens with the relevant build context in view.  For
non-pairmode projects it emits a soft bootstrap prompt.

Stdlib only — intentionally imports nothing outside the standard library so
the script can be executed as bare ``python3`` without uv or any virtual env.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Pairmode detection
# ---------------------------------------------------------------------------

def _is_pairmode(cwd: Path) -> bool:
    """Return True when the project at *cwd* has pairmode configured."""
    if (cwd / ".companion" / "pairmode_context.json").exists():
        return True
    # Fallback: treat as pairmode-enabled when both sentinel files are present.
    if (cwd / "CLAUDE.build.md").exists() and (cwd / "docs" / "phases" / "index.md").exists():
        return True
    return False


# ---------------------------------------------------------------------------
# State / context readers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    """Read a JSON file and return its contents as a dict; return {} on error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _project_name(cwd: Path) -> str:
    ctx_path = cwd / ".companion" / "pairmode_context.json"
    ctx = _read_json(ctx_path)
    return str(ctx.get("project_name", cwd.name)).strip() or cwd.name


def _current_story(cwd: Path) -> str:
    state = _read_json(cwd / ".companion" / "state.json")
    story = state.get("current_story")
    if not isinstance(story, dict):
        return "none set"
    sid = str(story.get("id", "")).strip()
    if not sid:
        return "none set"
    title = str(story.get("title", "")).strip()
    if title:
        return f"{sid} — {title}"
    return sid


def _active_era(cwd: Path) -> str:
    """Return the active era id by line-scanning docs/eras/*.md frontmatter."""
    eras_dir = cwd / "docs" / "eras"
    if not eras_dir.is_dir():
        return "—"
    try:
        era_files = sorted(eras_dir.glob("*.md"))
    except Exception:
        return "—"
    for era_file in era_files:
        try:
            lines = era_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        in_frontmatter = False
        era_id = ""
        found_active = False
        for line in lines:
            stripped = line.strip()
            if stripped == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                    continue
                else:
                    # End of frontmatter block
                    break
            if not in_frontmatter:
                continue
            if stripped.startswith("id:"):
                raw = stripped[len("id:"):].strip().strip('"').strip("'")
                era_id = raw
            elif stripped.startswith("status:"):
                val = stripped[len("status:"):].strip().strip('"').strip("'")
                if val == "active":
                    found_active = True
        if found_active and era_id:
            return era_id
    return "—"


def _last_tag(cwd: Path) -> str:
    """Return the most recent git tag via git describe, or '—' on failure."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            return tag if tag else "—"
    except Exception:
        pass
    return "—"


# ---------------------------------------------------------------------------
# Canon sync status
# ---------------------------------------------------------------------------

def _find_flex_dir() -> Path | None:
    """Locate the flex repo directory using env var, config file, or common paths."""
    # 1. FLEX_DIR environment variable
    env_flex = os.environ.get("FLEX_DIR", "").strip()
    if env_flex:
        p = Path(env_flex)
        if p.is_dir():
            return p

    # 2. ~/.claude/pairmode_config.json
    try:
        config_path = Path.home() / ".claude" / "pairmode_config.json"
        if config_path.exists():
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            flex_dir = cfg.get("flex_dir", "").strip()
            if flex_dir:
                p = Path(flex_dir)
                if p.is_dir():
                    return p
    except Exception:
        pass

    # 3. Common paths
    for candidate in [
        "/mnt/work/flex",
        os.path.expanduser("~/flex"),
        os.path.expanduser("~/projects/flex"),
    ]:
        p = Path(candidate)
        if p.is_dir():
            return p

    return None


def _read_canon_version(flex_dir: Path) -> str | None:
    """Extract pairmode_version from <flex_dir>/skills/pairmode/SKILL.md."""
    skill_md = flex_dir / "skills" / "pairmode" / "SKILL.md"
    if not skill_md.exists():
        return None
    try:
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("pairmode_version:"):
                return stripped[len("pairmode_version:"):].strip().strip('"').strip("'")
            if stripped.startswith("**Version:**"):
                return stripped[len("**Version:**"):].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def _canon_sync_status(cwd: Path) -> str:
    flex_dir = _find_flex_dir()
    if flex_dir is None:
        return "Set FLEX_DIR env var to enable currency check"

    canon_version = _read_canon_version(flex_dir)
    if canon_version is None:
        return "unknown (version field not found in SKILL.md)"

    state = _read_json(cwd / ".companion" / "state.json")
    project_version = str(state.get("pairmode_version", "")).strip()

    if not project_version:
        return "unknown (run /flex:pairmode audit)"
    if project_version == canon_version:
        return "up to date"
    return "behind canon — run /flex:pairmode sync"


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

_NON_PAIRMODE_MESSAGE = (
    "⚡ Pairmode not configured for this project.\n"
    "   Run /flex:pairmode bootstrap to set up the structured build loop.\n"
    "   (Skip this if pairmode is not applicable here.)"
)


def _pairmode_status_block(cwd: Path) -> str:
    """Build and return the full pairmode status block string."""
    project_name = _project_name(cwd)
    story = _current_story(cwd)
    era = _active_era(cwd)
    tag = _last_tag(cwd)
    sync = _canon_sync_status(cwd)

    lines = [
        f"◆ Pairmode active — {project_name}",
        f"  Current story : {story}",
        f"  Active era    : {era}",
        f"  Last tag      : {tag}",
        f"  Canon sync    : {sync}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cwd = Path(os.getcwd())
    try:
        if not _is_pairmode(cwd):
            print(_NON_PAIRMODE_MESSAGE)
            sys.exit(0)
        print(_pairmode_status_block(cwd))
    except Exception as exc:
        print(f"[pairmode check] warning: unexpected error — {exc}")
    sys.exit(0)


if __name__ == "__main__":
    main()
