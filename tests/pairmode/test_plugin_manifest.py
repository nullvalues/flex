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

The expected-name set for check 3 is derived from the filesystem
(``skills/*/SKILL.md``) rather than hand-restated, so a fifth top-level
skill is guarded the moment its directory exists instead of shipping
unguarded until someone remembers to edit this module (CER-109).

Stdlib only (json, pathlib, re) — no YAML dependency. Reads the real repo
files, not fixtures, so it guards the shipped manifest (same idiom as
``tests/pairmode/test_version_match.py``'s ``_REPO_ROOT``).
"""

import json
import pathlib
import re

import pytest

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


def _frontmatter_name(skill_md_path: pathlib.Path) -> str:
    text = skill_md_path.read_text()
    match = re.search(r"^name:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    assert match, f"no `name:` frontmatter line found in {skill_md_path}"
    return match.group(1)


def _derive_expected_skill_names(root: pathlib.Path) -> dict[str, str]:
    """Map each top-level ``skills/*/SKILL.md`` to its expected bare name.

    The expected name is the skill directory's basename
    (``skills/seed/SKILL.md`` -> ``"seed"``). Deliberately single-level
    (``skills/*/SKILL.md``, not a recursive glob): nested procedure
    skills such as ``skills/pairmode/gate_worker/SKILL.md`` are
    plugin-versioned procedure documents loaded by path, not installed
    top-level plugin skills, so their correctly ``flex:``-prefixed names
    must not be reached by this glob.
    """
    return {
        str(path.relative_to(root)): path.parent.name
        for path in sorted(root.glob("skills/*/SKILL.md"))
    }


def _assert_skill_names_bare(root: pathlib.Path) -> None:
    for rel_path, expected_name in _derive_expected_skill_names(root).items():
        skill_md_path = root / rel_path
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


def _write_skill_md(root: pathlib.Path, dir_name: str, frontmatter_name: str) -> None:
    skill_dir = root / "skills" / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {frontmatter_name}\n---\n\nBody.\n"
    )


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
    _assert_skill_names_bare(_REPO_ROOT)


def test_bare_name_check_catches_flex_prefix(tmp_path):
    _write_skill_md(tmp_path, "widget", "flex:widget")
    with pytest.raises(AssertionError, match="widget"):
        _assert_skill_names_bare(tmp_path)


def test_bare_name_check_passes_for_bare_name(tmp_path):
    _write_skill_md(tmp_path, "widget", "widget")
    _assert_skill_names_bare(tmp_path)  # must not raise


def test_fifth_skill_auto_covered_by_derivation(tmp_path):
    for dir_name in ("seed", "companion", "pairmode", "observability", "widget"):
        _write_skill_md(tmp_path, dir_name, dir_name)

    derived = _derive_expected_skill_names(tmp_path)
    assert len(derived) == 5, (
        f"expected the derivation to pick up all five skill directories, "
        f"got {len(derived)}: {derived!r}"
    )
    assert "widget" in derived.values(), (
        "the fifth skill's expected name did not appear in the derived "
        "mapping — a fifth skill must be auto-covered with no edit to this "
        "test module (CER-109)."
    )

    # All five are bare so far — the guard must accept them.
    _assert_skill_names_bare(tmp_path)

    # Now give the fifth a flex:-prefixed name: "auto-covered" means the
    # *guard* catches it, not merely that it is present in the derived dict.
    _write_skill_md(tmp_path, "widget", "flex:widget")
    with pytest.raises(AssertionError, match="widget"):
        _assert_skill_names_bare(tmp_path)


def test_derivation_excludes_dir_without_skill_md(tmp_path):
    _write_skill_md(tmp_path, "has_skill_md", "has_skill_md")
    (tmp_path / "skills" / "no_skill_md").mkdir(parents=True, exist_ok=True)

    derived = _derive_expected_skill_names(tmp_path)

    assert set(derived.values()) == {"has_skill_md"}, (
        f"expected only the directory containing SKILL.md to appear in the "
        f"derived mapping, got {derived!r} — a skills/<name>/ directory with "
        "no SKILL.md must be excluded (CER-109)."
    )


def test_derived_skill_names_anti_vacuity_floor():
    derived = _derive_expected_skill_names(_REPO_ROOT)
    assert derived, (
        "skills/*/SKILL.md derivation matched zero files (CER-109): a glob "
        "that matches nothing produces an empty loop and a green test, which "
        "is strictly worse than the hardcoded dict it replaced, because no "
        "top-level skill would be guarded at all."
    )
    assert len(derived) >= 4, (
        f"skills/*/SKILL.md derivation matched only {len(derived)} file(s), "
        "fewer than the four known top-level skills (seed, companion, "
        "pairmode, observability) — CER-109: a shrunken glob means the "
        "derivation is broken, not that the repo shed skills."
    )
    assert "pairmode" in derived.values(), (
        "expected 'pairmode' among the derived skill names as a named "
        "canary — a glob that silently resolves against the wrong root "
        "could otherwise satisfy the count floor alone without this check."
    )
