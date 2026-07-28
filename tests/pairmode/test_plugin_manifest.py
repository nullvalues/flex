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

Stdlib only (json, pathlib) — no YAML dependency. Reads the real repo files,
not fixtures, so it guards the shipped manifest (same idiom as
``tests/pairmode/test_version_match.py``'s ``_REPO_ROOT``).
"""

import json
import pathlib

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


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
