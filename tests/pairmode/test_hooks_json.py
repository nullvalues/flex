"""
Regression guard for hooks/hooks.json PreToolUse matcher coverage (INFRA-205 / CER-065),
and (CER-091 / INFRA-264) its PostToolUse mirror.

hooks/pre_tool_use.py is a thin dispatcher branching on ``tool_name``. Every
literal it dispatches on must be covered by at least one registered
PreToolUse matcher in hooks/hooks.json — otherwise the dispatch branch is
dead code (Claude Code never invokes the hook for a tool call whose name has
no matching matcher).

This test scans the *actual* pre_tool_use.py source for the two dispatch
shapes used in main() rather than hand-duplicating the literal list, so a
future dispatch branch added without a matching hooks.json update fails
this test.

CER-091 defect 1's trigger-coverage gap was exactly this class of bug in
reverse for PostToolUse: a SendMessage continuation dispatched by
hooks/post_tool_use.py's spawn branch had no registered PostToolUse matcher
at all, so the hook never ran for it. The tests below are the PostToolUse
mirror of the PreToolUse coverage guard above, so this class of dead branch
cannot recur on either hook.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_JSON_PATH = REPO_ROOT / "hooks" / "hooks.json"
PRE_TOOL_USE_PATH = REPO_ROOT / "hooks" / "pre_tool_use.py"
POST_TOOL_USE_PATH = REPO_ROOT / "hooks" / "post_tool_use.py"


def _extract_dispatched_tool_names(source: str) -> set[str]:
    """Scan pre_tool_use.py source text for dispatched tool_name literals.

    Handles the two dispatch shapes used in main():
      - tool_name in ( "A", "B" )
      - tool_name == "C"
    """
    dispatched: set[str] = set()

    # tool_name in ( ... ) — collect quoted strings inside the tuple.
    for tuple_match in re.finditer(r"tool_name\s+in\s*\(([^)]*)\)", source):
        tuple_body = tuple_match.group(1)
        dispatched.update(re.findall(r'"([^"]+)"', tuple_body))
        dispatched.update(re.findall(r"'([^']+)'", tuple_body))

    # tool_name == "..." — collect the single quoted literal.
    for eq_match in re.finditer(r'tool_name\s*==\s*"([^"]+)"', source):
        dispatched.add(eq_match.group(1))
    for eq_match in re.finditer(r"tool_name\s*==\s*'([^']+)'", source):
        dispatched.add(eq_match.group(1))

    return dispatched


def _registered_pretooluse_tool_names(hooks_config: dict) -> set[str]:
    """Build the set of tool names registered across PreToolUse matchers."""
    registered: set[str] = set()
    for block in hooks_config.get("hooks", {}).get("PreToolUse", []):
        matcher = block.get("matcher", "")
        registered.update(part for part in matcher.split("|") if part)
    return registered


def _registered_posttooluse_tool_names(hooks_config: dict) -> set[str]:
    """Build the set of tool names registered across PostToolUse matchers."""
    registered: set[str] = set()
    for block in hooks_config.get("hooks", {}).get("PostToolUse", []):
        matcher = block.get("matcher", "")
        registered.update(part for part in matcher.split("|") if part)
    return registered


def _extract_posttooluse_dispatched_tool_names(source: str) -> set[str]:
    """Scan post_tool_use.py source text for dispatched tool_name literals.

    Covers both dispatch shapes present in that file: the ``tool_name in
    (...)`` spawn-branch tuple, and the ``WATCHED_TOOLS = {...}`` set
    literal the Write/Edit/MultiEdit relay checks against.
    """
    dispatched: set[str] = set()

    for tuple_match in re.finditer(r"tool_name\s+in\s*\(([^)]*)\)", source):
        tuple_body = tuple_match.group(1)
        dispatched.update(re.findall(r'"([^"]+)"', tuple_body))
        dispatched.update(re.findall(r"'([^']+)'", tuple_body))

    for set_match in re.finditer(r"WATCHED_TOOLS\s*=\s*\{([^}]*)\}", source):
        set_body = set_match.group(1)
        dispatched.update(re.findall(r'"([^"]+)"', set_body))
        dispatched.update(re.findall(r"'([^']+)'", set_body))

    return dispatched


def _load_hooks_json() -> dict:
    return json.loads(HOOKS_JSON_PATH.read_text(encoding="utf-8"))


def _load_pre_tool_use_source() -> str:
    return PRE_TOOL_USE_PATH.read_text(encoding="utf-8")


def _load_post_tool_use_source() -> str:
    return POST_TOOL_USE_PATH.read_text(encoding="utf-8")


def test_pretooluse_source_scan_finds_expected_literals():
    """Guard against a scan regex that silently matches nothing."""
    source = _load_pre_tool_use_source()
    dispatched = _extract_dispatched_tool_names(source)

    assert dispatched, (
        "source scan of pre_tool_use.py found no dispatched tool_name literals — "
        "the scan regex is broken and the superset check below would be vacuous"
    )

    expected_minimum = {"Task", "Agent", "Edit", "Write", "Read"}
    missing = expected_minimum - dispatched
    assert not missing, (
        f"source scan did not find expected dispatched literals: {missing}"
    )


def test_pretooluse_matchers_cover_all_dispatched_tool_names():
    """Core CER-065 regression: dispatched tool_names must be a subset of
    registered PreToolUse matchers in hooks.json."""
    source = _load_pre_tool_use_source()
    dispatched = _extract_dispatched_tool_names(source)

    hooks_config = _load_hooks_json()
    registered = _registered_pretooluse_tool_names(hooks_config)

    uncovered = dispatched - registered
    assert not uncovered, (
        f"pre_tool_use.py dispatches on tool_name(s) {uncovered} that are not "
        f"covered by any registered PreToolUse matcher in hooks.json "
        f"(registered: {registered}) — these dispatch branches are unreachable "
        f"dead code until a matching matcher block is added"
    )


def test_pretooluse_edit_write_and_read_blocks_use_canonical_command():
    """The new Edit|Write and Read blocks must use the same command/timeout
    as the existing Task|Agent block."""
    hooks_config = _load_hooks_json()
    pretooluse_blocks = hooks_config["hooks"]["PreToolUse"]

    canonical_command = "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool_use.py"

    matcher_to_block = {block.get("matcher"): block for block in pretooluse_blocks}

    for expected_matcher in ("Task|Agent", "Edit|Write", "Read"):
        assert expected_matcher in matcher_to_block, (
            f"expected PreToolUse matcher {expected_matcher!r} not found in hooks.json"
        )
        block = matcher_to_block[expected_matcher]
        inner_hooks = block.get("hooks", [])
        assert len(inner_hooks) == 1, (
            f"expected exactly one inner hook for matcher {expected_matcher!r}"
        )
        inner_hook = inner_hooks[0]
        assert inner_hook.get("command") == canonical_command, (
            f"matcher {expected_matcher!r} command mismatch: "
            f"{inner_hook.get('command')!r} != {canonical_command!r}"
        )
        assert inner_hook.get("timeout") == 5, (
            f"matcher {expected_matcher!r} timeout mismatch: "
            f"{inner_hook.get('timeout')!r} != 5"
        )


# ---------------------------------------------------------------------------
# PostToolUse matcher coverage (CER-091 defect 1/E12, INFRA-264)
# ---------------------------------------------------------------------------


def test_posttooluse_source_scan_finds_expected_literals():
    """Guard against a scan regex that silently matches nothing."""
    source = _load_post_tool_use_source()
    dispatched = _extract_posttooluse_dispatched_tool_names(source)

    assert dispatched, (
        "source scan of post_tool_use.py found no dispatched tool_name literals — "
        "the scan regex is broken and the superset check below would be vacuous"
    )

    expected_minimum = {"Task", "Agent", "SendMessage", "Write", "Edit", "MultiEdit"}
    missing = expected_minimum - dispatched
    assert not missing, (
        f"source scan did not find expected dispatched literals: {missing}"
    )


def test_posttooluse_matchers_cover_all_dispatched_tool_names():
    """CER-091 defect 1 regression: every tool_name post_tool_use.py's spawn
    branch dispatches on (including SendMessage) must be covered by a
    registered PostToolUse matcher in hooks.json — a SendMessage
    continuation with no registered matcher is exactly the trigger-coverage
    gap this story closes."""
    source = _load_post_tool_use_source()
    dispatched = _extract_posttooluse_dispatched_tool_names(source)

    hooks_config = _load_hooks_json()
    registered = _registered_posttooluse_tool_names(hooks_config)

    uncovered = dispatched - registered
    assert not uncovered, (
        f"post_tool_use.py dispatches on tool_name(s) {uncovered} that are not "
        f"covered by any registered PostToolUse matcher in hooks.json "
        f"(registered: {registered}) — these dispatch branches are unreachable "
        f"dead code until a matching matcher block is added"
    )


def test_posttooluse_task_agent_sendmessage_matcher_uses_canonical_command():
    hooks_config = _load_hooks_json()
    posttooluse_blocks = hooks_config["hooks"]["PostToolUse"]
    matcher_to_block = {block.get("matcher"): block for block in posttooluse_blocks}

    assert "Task|Agent|SendMessage" in matcher_to_block, (
        "expected PostToolUse matcher 'Task|Agent|SendMessage' not found in hooks.json"
    )
    block = matcher_to_block["Task|Agent|SendMessage"]
    inner_hooks = block.get("hooks", [])
    assert len(inner_hooks) == 1
    inner_hook = inner_hooks[0]
    assert inner_hook.get("command") == "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.py"
    assert inner_hook.get("timeout") == 5


# ---------------------------------------------------------------------------
# SubagentStop registration (INFRA-298, CER-114)
# ---------------------------------------------------------------------------


def test_subagentstop_registered_exactly_once_no_matcher_no_async():
    hooks_config = _load_hooks_json()
    blocks = hooks_config["hooks"].get("SubagentStop")
    assert blocks is not None, "SubagentStop must be a registered top-level event"
    assert len(blocks) == 1, f"expected exactly one SubagentStop block, got {len(blocks)}"

    block = blocks[0]
    assert "matcher" not in block, "SubagentStop must not carry a matcher"

    inner_hooks = block.get("hooks", [])
    assert len(inner_hooks) == 1, f"expected exactly one inner hook, got {len(inner_hooks)}"

    inner_hook = inner_hooks[0]
    assert inner_hook.get("command", "").endswith("hooks/subagent_stop.py")
    assert inner_hook.get("timeout") == 5
    assert "async" not in inner_hook


def test_previously_registered_events_unchanged_by_subagentstop_addition():
    hooks_config = _load_hooks_json()
    events = hooks_config["hooks"]
    for expected in (
        "Stop", "PermissionRequest", "PreToolUse", "PostToolUse",
        "SessionEnd", "SessionStart", "UserPromptSubmit",
    ):
        assert expected in events, f"expected pre-existing event {expected!r} to remain registered"
