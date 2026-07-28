"""Plugin manifest shape guard (INFRA-291).

Guards two invariants that a fresh-machine local install depends on:

1. The `flex` plugin entry's `source` in `marketplace.json` must stay the
   local-relative string ``"./"``. A ``github`` source object makes
   ``claude plugin marketplace add <local-path>`` install the published
   GitHub repo instead of the checkout that was just added — so a developer
   testing local changes silently installs someone else's (or an older) tree.
2. `plugin.json`'s `name` must agree with the `marketplace.json` plugin
   entry's `name` (`flex`) — the invariant that makes
   `claude plugin install flex@nullvalues-flex` resolve at all.
3. Each top-level ``skills/*/SKILL.md`` frontmatter ``name:`` must be bare
   (no ``:`` character) — prevents the doubled ``/flex:flex:*`` namespace
   defect (INFRA-292), where Claude Code already prefixes an installed
   plugin's skills with the ``plugin.json`` name (``flex:``), so a
   frontmatter name that also bakes in the ``flex:`` prefix doubles it.

Stdlib only (json, pathlib, re) — no YAML dependency. Reads the real repo
files, not fixtures, so it guards the shipped manifest (same idiom as
``tests/pairmode/test_version_match.py``'s ``_REPO_ROOT``).
"""

import json
import pathlib
import re

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent

_EXPECTED_SKILL_NAMES = {
    "skills/seed/SKILL.md": "seed",
    "skills/companion/SKILL.md": "companion",
    "skills/pairmode/SKILL.md": "pairmode",
    "skills/observability/SKILL.md": "observability",
}


def _frontmatter_name(skill_md_path: pathlib.Path) -> str:
    text = skill_md_path.read_text()
    match = re.search(r"^name:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    assert match, f"no `name:` frontmatter line found in {skill_md_path}"
    return match.group(1)


def _read_marketplace() -> dict:
    return json.loads(
        (_REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text()
    )


def _read_plugin() -> dict:
    return json.loads((_REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())


def _flex_marketplace_entry() -> dict:
    marketplace = _read_marketplace()
    flex_entries = [p for p in marketplace["plugins"] if p["name"] == "flex"]
    assert flex_entries, "no flex entry found in marketplace.json plugins"
    return flex_entries[0]


def test_marketplace_flex_source_is_local_relative():
    entry = _flex_marketplace_entry()
    assert entry["source"] == "./", (
        f"marketplace.json flex plugin source is {entry['source']!r}, expected "
        "the local-relative string './'. A 'github' source object makes "
        "`claude plugin marketplace add <local-path>` install the published "
        "GitHub repo instead of the checkout that was just added, so a local "
        "install never installs local changes (INFRA-291)."
    )


def test_plugin_and_marketplace_names_agree():
    plugin_name = _read_plugin()["name"]
    marketplace_name = _flex_marketplace_entry()["name"]
    assert plugin_name == marketplace_name, (
        f"plugin.json name {plugin_name!r} must equal the marketplace.json "
        f"flex plugin entry's name {marketplace_name!r} — this is the "
        "invariant that makes `claude plugin install flex@nullvalues-flex` "
        "resolve at all (INFRA-291)."
    )


def test_skill_md_names_are_bare_not_double_namespaced():
    for rel_path, expected_name in _EXPECTED_SKILL_NAMES.items():
        skill_md_path = _REPO_ROOT / rel_path
        actual_name = _frontmatter_name(skill_md_path)
        assert actual_name == expected_name, (
            f"{rel_path} frontmatter name is {actual_name!r}, expected the "
            f"bare form {expected_name!r}. Claude Code already namespaces an "
            "installed plugin's skills as `<plugin.json name>:<skill name>` "
            "(here `flex:`), so a frontmatter name that also bakes in the "
            "`flex:` prefix produces a doubled `/flex:flex:*` command "
            "(INFRA-292)."
        )
        assert ":" not in actual_name, (
            f"{rel_path} frontmatter name {actual_name!r} contains a ':' — "
            "the plugin namespace prefix must not be baked into the skill "
            "name itself (INFRA-292)."
        )
