"""Structural parity checks between CLAUDE.build.md (live) and its .j2 template (INFRA-342).

Rather than diffing whole `##`-delimited sections (the approach
`pairmode_drift_report.py` already takes and which is too noisy for this pair —
see docs/stories/INFRA/INFRA-342.md § Context), this test extracts two specific
structural invariants that must match between the live file and the template
regardless of the template's intentional flex-specific literal substitutions
(paths, project name, branch name):

1. The key set of the `ACTION_SUBAGENT_TYPE = { ... }` dict literal.
2. The key set of the `**Build standards**` line's `key=` clauses.

Both extraction helpers are exercised against inline fixtures first, including
a red-path case that proves the helper actually discriminates a deliberately
broken fixture pair rather than vacuously reporting equal (possibly empty) sets.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_PATH = REPO_ROOT / "CLAUDE.build.md"
TEMPLATE_PATH = REPO_ROOT / "skills" / "pairmode" / "templates" / "CLAUDE.build.md.j2"


def extract_action_subagent_type_keys(text: str) -> set[str]:
    """Return the set of keys inside the `ACTION_SUBAGENT_TYPE = { ... }` dict literal."""
    match = re.search(r"ACTION_SUBAGENT_TYPE = \{([^}]*)\}", text)
    assert match is not None, "no ACTION_SUBAGENT_TYPE = { ... } dict literal found"
    body = match.group(1)
    keys: set[str] = set()
    for entry in body.split(","):
        entry = entry.strip()
        if not entry:
            continue
        key = entry.split(":", 1)[0].strip()
        keys.add(key)
    return keys


def extract_build_standards_keys(text: str) -> set[str]:
    """Return the set of `key=` names on the `**Build standards**` line.

    Only matches a bare word immediately followed by `` =` `` (the pattern every
    declared Build-standards key uses to open its backtick-quoted value, e.g.
    ``test_command=`pytest` ``). A naive `(\\w+)=` regex over the whole line also
    matches `key=value` fragments embedded *inside* those backtick-quoted values
    themselves (e.g. the literal `PATH=$HOME/...` inside a `test_command` value,
    or `model=null` inside explanatory prose) — those are not declared
    Build-standards keys and must not be counted.
    """
    lines = text.splitlines()
    standards_line = next((ln for ln in lines if ln.startswith("**Build standards**")), None)
    assert standards_line is not None, "no **Build standards** line found"
    return set(re.findall(r"(\w+)=`", standards_line))


# --- Unit tests: extraction helpers against inline fixtures --------------------


def test_extract_action_subagent_type_keys_green() -> None:
    fixture = "ACTION_SUBAGENT_TYPE = {spawn-builder: builder, spawn-reviewer: reviewer}  # comment"
    assert extract_action_subagent_type_keys(fixture) == {"spawn-builder", "spawn-reviewer"}


def test_extract_action_subagent_type_keys_red_path_detects_dropped_key() -> None:
    """A fixture pair with one key deliberately dropped from one side must NOT compare equal."""
    full = "ACTION_SUBAGENT_TYPE = {spawn-builder: builder, spawn-reviewer: reviewer, checkpoint-docs: docs-reviewer}"
    missing_one = "ACTION_SUBAGENT_TYPE = {spawn-builder: builder, spawn-reviewer: reviewer}"
    full_keys = extract_action_subagent_type_keys(full)
    missing_keys = extract_action_subagent_type_keys(missing_one)
    assert full_keys != missing_keys
    assert full_keys - missing_keys == {"checkpoint-docs"}


def test_extract_build_standards_keys_green() -> None:
    fixture = "**Build standards** (facts): test_command=`pytest` | test_dir=`tests/` | domain_isolation_rule=`(none)`"
    assert extract_build_standards_keys(fixture) == {"test_command", "test_dir", "domain_isolation_rule"}


def test_extract_build_standards_keys_red_path_detects_dropped_key() -> None:
    """A fixture pair with one Build-standards key deliberately dropped must NOT compare equal."""
    full = "**Build standards** (facts): test_command=`pytest` | test_dir=`tests/` | intent_review=`(unset)`"
    missing_one = "**Build standards** (facts): test_command=`pytest` | test_dir=`tests/`"
    full_keys = extract_build_standards_keys(full)
    missing_keys = extract_build_standards_keys(missing_one)
    assert full_keys != missing_keys
    assert full_keys - missing_keys == {"intent_review"}


# --- Integration test: real files off disk --------------------------------------


def test_live_and_template_action_subagent_type_keys_match() -> None:
    live_text = LIVE_PATH.read_text(encoding="utf-8")
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    live_keys = extract_action_subagent_type_keys(live_text)
    template_keys = extract_action_subagent_type_keys(template_text)
    symmetric_diff = live_keys ^ template_keys
    assert live_keys == template_keys, (
        "ACTION_SUBAGENT_TYPE key sets diverge between CLAUDE.build.md and "
        f"CLAUDE.build.md.j2; symmetric difference: {sorted(symmetric_diff)} "
        f"(live-only: {sorted(live_keys - template_keys)}, "
        f"template-only: {sorted(template_keys - live_keys)})"
    )


def test_live_and_template_build_standards_keys_match() -> None:
    live_text = LIVE_PATH.read_text(encoding="utf-8")
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    live_keys = extract_build_standards_keys(live_text)
    template_keys = extract_build_standards_keys(template_text)
    symmetric_diff = live_keys ^ template_keys
    assert live_keys == template_keys, (
        "Build standards key sets diverge between CLAUDE.build.md and "
        f"CLAUDE.build.md.j2; symmetric difference: {sorted(symmetric_diff)} "
        f"(live-only: {sorted(live_keys - template_keys)}, "
        f"template-only: {sorted(template_keys - live_keys)})"
    )
