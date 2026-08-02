"""tests/pairmode/test_stage_integration.py — reusable stage-to-stage
integration-test harness (INFRA-336, Ensures 7-8).

Drives the *real* CLI surface (``flex_build.py``'s ``next-action``,
``create-story-worktree``, ``discard-story-worktree``) via
``click.testing.CliRunner`` against a real temporary project directory with
real ``.companion/state.json`` / ``.companion/attempt_counter.json`` files
and a real git repository on disk — no monkeypatched internals for the
worktree-lifecycle or attempt-counter machinery itself.

This module exists so later phase-117 stories (INFRA-339, INFRA-341,
INFRA-344 — see ``docs/phases/phase-117.md`` § Ordering) can add sibling
test functions here that reuse :func:`_scaffold_project` and
:func:`_invoke` rather than re-deriving the setup. See
``docs/architecture.md``'s test-strategy section for the pointer to this
file.

Root-cause background (CRITICAL finding F1,
``docs/build-loop-cold-eyes-review-20260801.md``): the FAIL-escalation
ladder did not reliably advance because ``discard-story-worktree`` clears
the ``current_stories`` stamp *before* the reconciliation sweep that
processes the FAIL runs (the sweep does not fire synchronously inside
``discard-story-worktree`` — it fires later, on the next hook-driven or
CLI-driven sweep). :func:`TestEscalationLadderAdvancesAfterDiscard
.test_next_action_create_discard_reconcile_next_action_advances_attempt`
drives exactly that sequence end to end.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "pairmode" / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import effort_db  # noqa: E402
from flex_build import flex_build  # noqa: E402


# ---------------------------------------------------------------------------
# Scaffold helpers — reusable by later stories in this phase (Instructions 5)
# ---------------------------------------------------------------------------


def _init_git_repo(project: Path) -> None:
    """Initialise *project* as a git repo with one commit on the default
    branch (mirrors ``test_flex_build.py``'s ``_init_git_repo``)."""
    subprocess.run(["git", "init", "-q"], cwd=str(project), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(project),
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(project), check=True)
    (project / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(project), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=str(project), check=True)


def _write_index(project_dir: Path, rows: list[tuple[str, str, str]]) -> Path:
    """Write ``docs/phases/index.md`` with ``(phase_ref, title, status)``
    rows (mirrors ``test_next_action.py``'s ``_write_index``)."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    index_path = phases_dir / "index.md"
    lines = [
        "# Phase Index\n\n",
        "| Phase | Title | Status | Tag |\n",
        "|-------|-------|--------|-----|\n",
    ]
    for phase_ref, title, status in rows:
        lines.append(f"| {phase_ref} | {title} | {status} | |\n")
    index_path.write_text("".join(lines), encoding="utf-8")
    return index_path


def _write_phase(
    project_dir: Path, phase_ref: str, stories: list[tuple[str, str]]
) -> Path:
    """Write ``docs/phases/phase-{phase_ref}.md`` with a Stories table."""
    phases_dir = project_dir / "docs" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)
    phase_path = phases_dir / f"phase-{phase_ref}.md"
    lines = [
        f"# Phase {phase_ref}\n\n",
        "## Stories\n\n",
        "| ID | Title | Status |\n",
        "|----|-------|--------|\n",
    ]
    for story_id, status in stories:
        lines.append(f"| {story_id} | A story | {status} |\n")
    phase_path.write_text("".join(lines), encoding="utf-8")
    return phase_path


def _write_story(
    project_dir: Path,
    story_id: str,
    *,
    phase: str = "1",
    primary_files: "list[str] | None" = None,
) -> Path:
    """Write a minimal, non-stub story spec (>=5 Ensures lines, RESOLVER-009)."""
    rail = story_id.split("-", 1)[0]
    story_dir = project_dir / "docs" / "stories" / rail
    story_dir.mkdir(parents=True, exist_ok=True)
    story_path = story_dir / f"{story_id}.md"
    pf = primary_files or ["src/app.py"]
    pf_yaml = "\nprimary_files:\n" + "".join(f"  - {p}\n" for p in pf)
    content = (
        "---\n"
        f"id: {story_id}\n"
        f"rail: {rail}\n"
        "status: planned\n"
        f"phase: '{phase}'\n"
        "story_class: code\n"
        f"{pf_yaml}"
        "auth_gated: false\n"
        "schema_introduces: false\n"
        "---\n\n"
        "## Ensures\n\n"
        "- It works as designed.\n"
        "- All inputs are validated.\n"
        "- The output format is correct.\n"
        "- Tests pass.\n"
        "- No regressions introduced.\n"
    )
    story_path.write_text(content, encoding="utf-8")
    return story_path


def _enable_effort_tracking(project_dir: Path) -> None:
    """Write ``.companion/state.json`` with ``effort_tracking: true`` — the
    reconciliation sweep (``reconcile_pending_attempts``) is a no-op without
    it."""
    companion = project_dir / ".companion"
    companion.mkdir(parents=True, exist_ok=True)
    state_path = companion / "state.json"
    payload = {"effort_tracking": True}
    if state_path.exists():
        try:
            payload = {**json.loads(state_path.read_text(encoding="utf-8")), **payload}
        except (json.JSONDecodeError, OSError):
            pass
    state_path.write_text(json.dumps(payload), encoding="utf-8")


def _output_assistant_entry(
    msg_id: str,
    tokens_in: int,
    tokens_out: int,
    *,
    stop_reason: "str | None" = None,
    text: "str | None" = None,
    model: str = "claude-sonnet-5",
) -> dict:
    """A single synthetic ``assistant`` transcript-turn entry (mirrors
    ``test_subagent_transcript.py``'s helper of the same name)."""
    message: dict = {
        "id": msg_id,
        "model": model,
        "usage": {
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }
    if stop_reason is not None:
        message["stop_reason"] = stop_reason
    if text is not None:
        message["content"] = [{"type": "text", "text": text}]
    return {"type": "assistant", "message": message}


def _write_output_file(path: Path, entries: "list[dict]") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def _scaffold_project(project_dir: Path, story_id: str, *, phase: str = "1") -> None:
    """Assemble a minimal but complete pairmode project: git repo, an active
    phase with one planned story, and effort tracking enabled.

    Factored so later stories (INFRA-339/341/344) can call this directly
    rather than re-deriving the setup (Instructions 5).
    """
    _init_git_repo(project_dir)
    _write_index(project_dir, [(phase, "Phase " + phase, "active")])
    _write_phase(project_dir, phase, [(story_id, "planned")])
    _write_story(project_dir, story_id, phase=phase)
    _enable_effort_tracking(project_dir)


def _invoke(*args: str):
    """Invoke the real ``flex_build`` Click group in-process via
    ``CliRunner`` — the real CLI surface named in Ensures 7, not
    monkeypatched internals."""
    runner = CliRunner()
    return runner.invoke(flex_build, list(args), catch_exceptions=False)


def _next_action_json(project_dir: Path) -> dict:
    result = _invoke("next-action", "--project-dir", str(project_dir), "--json")
    assert result.exit_code == 0, f"next-action failed: {result.output}"
    return json.loads(result.output.strip())


def _record_fail_via_real_reconciliation(
    project_dir: Path, story_id: str, *, agent_role: str = "reviewer"
) -> None:
    """Insert a pending ``effort.db`` row carrying a FAIL verdict and
    reconcile it through the *real* reconciliation path
    (``subagent_transcript.reconcile_pending_attempts`` — the module the
    story names as ``reconcile_attempts_from_effort_db``), never a direct
    ``write_attempt_count``/``bump_attempt_count`` call — Ensures 7 requires
    the bug's actual code path be exercised, not bypassed."""
    # Imported lazily so importing this module never imports subagent_transcript
    # (and its own flex_build re-import) before flex_build has finished
    # initialising in the test process.
    from skills.pairmode.scripts import subagent_transcript as st

    db_path = project_dir / ".companion" / "effort.db"
    effort_db.init_db(db_path)
    from datetime import datetime, timedelta, timezone

    row_id = effort_db.insert_attempt(
        db_path,
        story_id=story_id,
        agent_role=agent_role,
        attempt_number=1,
        ts=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    )
    output_file = project_dir / ".companion" / "tasks" / f"{agent_role}.output"
    _write_output_file(
        output_file,
        [
            _output_assistant_entry(
                f"msg_{agent_role}", 100, 50, stop_reason="end_turn",
                text=json.dumps({
                    "type": "REVIEW-RESULT" if agent_role == "reviewer" else "BUILD-RESULT",
                    "verdict": "FAIL",
                    "outcome": "FAIL",
                    "findings": ["x"],
                    "reason": "simulated FAIL for INFRA-336's integration harness",
                }),
            )
        ],
    )
    effort_db.set_spawn_ref(db_path, row_id, f"agent-{agent_role}", str(output_file))

    st.reconcile_pending_attempts(project_dir=project_dir)


# ---------------------------------------------------------------------------
# Ensures 7: the escalation ladder advances after a discard
# ---------------------------------------------------------------------------


class TestEscalationLadderAdvancesAfterDiscard:
    def test_next_action_create_discard_reconcile_next_action_advances_attempt(
        self, tmp_path: Path
    ) -> None:
        """The exact sequence named in the story's Context and Ensures 7:

        next-action (spawn-builder, attempt 1) -> create-story-worktree ->
        [FAIL row inserted] -> discard-story-worktree (clears the
        current_stories stamp) -> the FAIL reconciled via the real
        reconciliation path (*after* the discard — the actual race the bug
        report traces) -> next-action again, asserting the second poll's
        attempt equals 2.

        Reconciling *after* discard (rather than before, as a looser
        reading of the Ensures 7 prose might suggest) is deliberate: only
        that ordering exercises CER-091 defect 4's real root cause — a
        story's first FAIL commonly is not reconciled until after
        discard-story-worktree has already cleared its current_stories
        stamp. Reconciling before the discard would pass even against the
        pre-fix code (the story is still "current" at that point), which
        would fail this test module's own reviewer negative check (`git
        stash` the fix, confirm this test goes red).
        """
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        story_id = "INFRA-900"
        _scaffold_project(project_dir, story_id)

        first = _next_action_json(project_dir)
        assert first["action"] == "spawn-builder"
        assert first["scalar"] == story_id
        assert first["meta"]["attempt"] == 1

        create_result = _invoke(
            "create-story-worktree", "--story-id", story_id, "--project-dir", str(project_dir)
        )
        assert create_result.exit_code == 0, create_result.output

        discard_result = _invoke(
            "discard-story-worktree", "--story-id", story_id, "--project-dir", str(project_dir)
        )
        assert discard_result.exit_code == 0, discard_result.output

        _record_fail_via_real_reconciliation(project_dir, story_id)

        second = _next_action_json(project_dir)
        assert second["action"] == "spawn-builder"
        assert second["scalar"] == story_id
        assert second["meta"]["attempt"] == 2


# ---------------------------------------------------------------------------
# INFRA-339 (Phase 117, F2/F12): Row 8's context-etiquette check is removed
# ---------------------------------------------------------------------------


class TestRow8ContextPauseRemoved:
    """The INFRA-316 Row-8 seam ("story committed (PASS), more stories
    remain") used to consult an orchestrator-track context check before
    handing out the next story, emitting ``pause-context`` instead of
    ``spawn-builder`` when over threshold. INFRA-339 removed it because it
    was provably unreachable from a live ``infer_position`` call (F2) and,
    separately, session-scoping-unsafe (F12) -- see the story's Context/
    Requires 2. This drives the real sequence the story stub asked for:
    next-action (spawn-builder) -> create-story-worktree -> a commit whose
    subject satisfies ``_has_story_commit`` -> merge-story-worktree ->
    next-action again, with a deliberately over-threshold state.json set
    before the second poll -- the exact fixture shape the now-deleted unit
    test (``TestResolveNextActionRow8ContextPause
    .test_over_threshold_no_ack_emits_pause_context``) used to assert
    *paused* on. Proves the second poll still emits ``spawn-builder`` (never
    ``pause-context``, which is no longer even a member of ``ACTIONS``) --
    Row 2/Row 8 in the live loop was always the reachable path, exactly as
    F2 found, and removing the second, broken gate changes nothing
    observable in the live sequence."""

    def test_second_poll_emits_spawn_builder_even_over_context_threshold(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        story_a = "INFRA-910"
        story_b = "INFRA-911"
        phase = "1"

        _init_git_repo(project_dir)
        _write_index(project_dir, [(phase, "Phase " + phase, "active")])
        _write_phase(project_dir, phase, [(story_a, "planned"), (story_b, "planned")])
        _write_story(project_dir, story_a, phase=phase)
        _write_story(project_dir, story_b, phase=phase)
        _enable_effort_tracking(project_dir)

        first = _next_action_json(project_dir)
        assert first["action"] == "spawn-builder"
        assert first["scalar"] == story_a
        assert first["meta"]["attempt"] == 1

        create_result = _invoke(
            "create-story-worktree", "--story-id", story_a, "--project-dir", str(project_dir)
        )
        assert create_result.exit_code == 0, create_result.output
        wt_path = Path(create_result.output.strip())

        # A commit whose subject satisfies _has_story_commit (CER-116 scope
        # rule: a conventional-commit scope naming the story ID is itself
        # the build evidence).
        (wt_path / "CHANGES.md").write_text("done\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(wt_path), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"story({story_a}): implement the thing"],
            cwd=str(wt_path),
            check=True,
        )

        merge_result = _invoke(
            "merge-story-worktree", "--story-id", story_a, "--project-dir", str(project_dir)
        )
        assert merge_result.exit_code == 0, merge_result.output

        # Deliberately over-threshold, unacknowledged orchestrator-track
        # state before the second poll (mirrors the deleted unit test's
        # fixture values: tokens=140000, threshold=120000).
        state_path = project_dir / ".companion" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["context_current_tokens"] = 140_000
        state["context_budget_threshold"] = 120_000
        state_path.write_text(json.dumps(state), encoding="utf-8")

        second = _next_action_json(project_dir)
        assert second["action"] == "spawn-builder"
        assert second["action"] != "pause-context"
        assert second["scalar"] == story_b
        assert second["meta"]["attempt"] == 1
        # SCHEMA_VERSION 6 (Ensures 3) is the one observable signal in this
        # sequence that actually distinguishes pre-story from post-story
        # code: the `action` assertion above passes even against pre-story
        # code with PAUSE_CONTEXT still wired, because F2's reachability bug
        # (last_attempt_outcome == OUTCOME_PASS is unreachable from a live
        # infer_position call) means Row 8's context check never fired
        # either way — that unreachability is the whole story. This
        # assertion is what actually goes red against pre-story code
        # (schema_version 5, not yet bumped).
        assert second["meta"]["schema_version"] == 6


class TestEscalationLadderAdvancesAfterDiscardMarker:
    def test_marker_gone_after_the_sequence_completes(self, tmp_path: Path) -> None:
        """Ensures 3: after the above sequence runs, the discard-side
        marker for this story_id is consumed, not lingering."""
        from skills.pairmode.scripts.story_context import (
            RECENTLY_DISCARDED_STORIES_KEY,
            read_state,
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        story_id = "INFRA-901"
        _scaffold_project(project_dir, story_id)

        _invoke(
            "create-story-worktree", "--story-id", story_id, "--project-dir", str(project_dir)
        )
        _invoke(
            "discard-story-worktree", "--story-id", story_id, "--project-dir", str(project_dir)
        )
        _record_fail_via_real_reconciliation(project_dir, story_id)

        state = read_state(project_dir / ".companion")
        marker = state.get(RECENTLY_DISCARDED_STORIES_KEY, {})
        assert story_id not in marker
