"""Version match-guard (RELEASE-002 / DP3).

Enforces the "plugin version and pairmode version bump together" rule across the
four version-bearing files. The plugin manifests carry the bare semver release
core (e.g. ``0.3.0``); the pairmode methodology version may carry a pre-release
suffix on the dev line (e.g. ``0.3.0-dev``). The guard compares the plugin
manifest version against the *release core* of ``PAIRMODE_VERSION`` (the part
before the first ``-``), so it keeps holding after the ``0.3.0-dev -> 0.3.0``
finalization at the flip (HARNESS006).

Stdlib only (json, pathlib, re) — no YAML dependency.
"""

import json
import pathlib
import re

from skills.pairmode.scripts._version import PAIRMODE_VERSION

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def _release_core(version: str) -> str:
    """Strip any pre-release / dev suffix (everything from the first '-')."""
    return version.split("-", 1)[0]


def _read_skill_frontmatter_version() -> str:
    """Parse ``pairmode_version`` from SKILL.md frontmatter (stdlib only)."""
    skill_md = (_REPO_ROOT / "skills" / "pairmode" / "SKILL.md").read_text()
    match = re.search(
        r'^pairmode_version:\s*"([^"]+)"\s*$', skill_md, re.MULTILINE
    )
    assert match is not None, "pairmode_version not found in SKILL.md frontmatter"
    return match.group(1)


def _read_plugin_version() -> str:
    plugin = json.loads(
        (_REPO_ROOT / ".claude-plugin" / "plugin.json").read_text()
    )
    return plugin["version"]


def _read_marketplace_flex_version() -> str:
    marketplace = json.loads(
        (_REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text()
    )
    flex_entries = [p for p in marketplace["plugins"] if p["name"] == "flex"]
    assert flex_entries, "no flex entry found in marketplace.json plugins"
    return flex_entries[0]["version"]


def test_plugin_version_matches_pairmode_release_core():
    core = _release_core(PAIRMODE_VERSION)
    assert _read_plugin_version() == core, (
        f"plugin.json version {_read_plugin_version()!r} must equal the "
        f"release core {core!r} of PAIRMODE_VERSION {PAIRMODE_VERSION!r}"
    )


def test_marketplace_flex_version_matches_pairmode_release_core():
    core = _release_core(PAIRMODE_VERSION)
    assert _read_marketplace_flex_version() == core, (
        f"marketplace.json flex version {_read_marketplace_flex_version()!r} "
        f"must equal the release core {core!r} of PAIRMODE_VERSION "
        f"{PAIRMODE_VERSION!r}"
    )


def test_skill_frontmatter_mirrors_pairmode_version():
    assert _read_skill_frontmatter_version() == PAIRMODE_VERSION, (
        "SKILL.md pairmode_version frontmatter must mirror PAIRMODE_VERSION "
        f"({PAIRMODE_VERSION!r})"
    )
