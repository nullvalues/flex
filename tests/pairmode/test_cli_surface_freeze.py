"""CLI-surface freeze guard test (RELEASE-003 / DP4.4).

Snapshots the 0.2.x flex_build.py command/flag surface and asserts that
the live surface is a SUPERSET of the snapshot.  Additions are allowed;
removals and renames fail.

To regenerate the snapshot after the 0.2->0.3 flip (HARNESS006), run:

    python -c "
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
from skills.pairmode.scripts.flex_build import flex_build
surface = {
    name: sorted(
        opt
        for p in cmd.params
        for opt in (p.opts if hasattr(p, 'opts') else [p.name])
    )
    for name, cmd in flex_build.commands.items()
}
print(json.dumps(surface, indent=2))
" > tests/pairmode/fixtures/cli_surface_0_2.json
"""

import json
import pathlib

import pytest

from skills.pairmode.scripts.flex_build import flex_build  # noqa: E402


_FIXTURE = (
    pathlib.Path(__file__).parent / "fixtures" / "cli_surface_0_2.json"
)


def _live_surface() -> dict[str, list[str]]:
    """Extract the current click surface from the live flex_build group."""
    return {
        name: sorted(
            opt
            for p in cmd.params
            for opt in (p.opts if hasattr(p, "opts") else [p.name])
        )
        for name, cmd in flex_build.commands.items()
    }


def _snapshot() -> dict[str, list[str]]:
    return json.loads(_FIXTURE.read_text())


def test_no_commands_removed() -> None:
    """Every command in the 0.2.x snapshot must still exist in the live group."""
    snapshot = _snapshot()
    live = _live_surface()

    missing = sorted(set(snapshot) - set(live))
    assert not missing, (
        f"CLI surface regression: command(s) removed or renamed since the "
        f"0.2.x freeze: {missing!r}"
    )


def test_no_flags_removed() -> None:
    """For every snapshotted command, every snapshotted flag must still be present."""
    snapshot = _snapshot()
    live = _live_surface()

    regressions: list[str] = []
    for cmd_name, frozen_flags in snapshot.items():
        if cmd_name not in live:
            # Already caught by test_no_commands_removed; skip here.
            continue
        live_flags = set(live[cmd_name])
        for flag in frozen_flags:
            if flag not in live_flags:
                regressions.append(f"  {cmd_name}: missing flag {flag!r}")

    assert not regressions, (
        "CLI surface regression: flag(s) removed or renamed since the "
        "0.2.x freeze:\n" + "\n".join(regressions)
    )


def test_additions_are_allowed() -> None:
    """Commands/flags present live but absent from the snapshot must not fail."""
    snapshot = _snapshot()
    live = _live_surface()

    # New top-level commands are fine.
    new_commands = sorted(set(live) - set(snapshot))
    # New flags on existing commands are fine.
    new_flags: dict[str, list[str]] = {}
    for cmd_name in snapshot:
        if cmd_name in live:
            extras = sorted(set(live[cmd_name]) - set(snapshot[cmd_name]))
            if extras:
                new_flags[cmd_name] = extras

    # This test always passes — it documents what is allowed.
    # If you want to audit what was added, inspect the locals below.
    _ = new_commands
    _ = new_flags


if __name__ == "__main__":
    # Generator helper: print the current surface as JSON.
    import sys

    surface = _live_surface()
    json.dump(surface, sys.stdout, indent=2)
    print()
