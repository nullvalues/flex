#!/usr/bin/env python3
# thin dispatcher — Write/Edit/MultiEdit → sidebar pipe relay; Task/Agent → context_budget.py
"""
PostToolUse hook — Pair Partner + Validator roles.

Fires after every file write/edit. Thin relay only.
Sends file change event to sidebar for UML delta + spec check.

Also fires after Task/Agent/SendMessage tool calls. Task/Agent get three
delegated calls (never blocks — each wrapped independently, exits silently
on any failure):
  1. context_budget.read_current_tokens() (INFRA-182) — reads the JSONL
     transcript and writes context_current_tokens +
     context_current_tokens_recorded_at to state.json. Also calls
     context_budget.record_step_growth() (INFRA-254) in the same
     read-modify-write, appending the observed delta to the
     context_step_growth_samples ring buffer and re-deriving
     expected_step_tokens live — see that module for the derivation tiers.
  2. subagent_transcript.record_attempt_from_transcript() (INFRA-236) —
     reads the same live transcript for the just-completed spawn's own
     usage, plus tool_input/tool_response/state.json for role/story/model/
     outcome, and writes one effort.db attempt row. This is a DIFFERENT
     metric than (1) — a subagent's own resource cost never entered the
     orchestrator's own context window (DP7); the two calls must never be
     merged or have their outputs cross-written.
  3. SendMessage (CER-091 defect 1) resumes an existing agent rather than
     spawning one, so it gets exactly one delegated call —
     subagent_transcript.log_recording_event(decision="observed:non-spawn-tool")
     — and never reaches record_attempt_from_transcript: recording an
     attempts row for a continuation is a modelling question, not this
     story's scope (see docs/architecture.md § Accepted losses). The point
     is visibility, not recording.

Protected-file classification is intentionally NOT done here.
The hook must stay a thin relay (millisecond exit, no file reads beyond
the grandfathered state.json read).  The sidebar process is responsible
for loading deny-rationale.json and calling display_override_prompt()
when a changed file matches a protected-file rule.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "skills" / "pairmode" / "scripts"))


PIPE_PATH = os.path.join(tempfile.gettempdir(), "companion.pipe")
STATE_PATH = ".companion/state.json"

WATCHED_TOOLS = {"Write", "Edit", "MultiEdit"}


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    if tool_name in ("Task", "Agent", "SendMessage"):
        project_dir = Path(data.get("cwd") or ".")
        session_id = data.get("session_id", "")

        if tool_name == "SendMessage":
            # CER-091 defect 1: a continuation, not a spawn — observed only.
            try:
                import subagent_transcript
                subagent_transcript.log_recording_event(
                    project_dir,
                    tool_name=tool_name,
                    subagent_type=None,
                    tool_use_id=data.get("tool_use_id"),
                    story_id=None,
                    decision="observed:non-spawn-tool",
                    row_id=None,
                )
            except Exception:
                pass
            sys.exit(0)

        # Two delegated calls (INFRA-236), each independently wrapped so a
        # failure in one never blocks the other. Never blocks — exits
        # silently on any failure.

        # 1. context_current_tokens writer (INFRA-182) — read JSONL, write
        #    fresh count to state.json.
        #    INFRA-285 (CER-097): the count, its stamp, the step-growth ring
        #    buffer and expected_step_tokens are read and written through this
        #    session's own context_sessions entry, so two interleaving sessions
        #    can no longer mix deltas from two unrelated context windows into
        #    one buffer. The spawn-output prefix (item D2) is captured inside
        #    this same read-modify-write — the hook performs exactly one state
        #    write per invocation, as it did before.
        stored_prefix = None
        try:
            import context_budget
            import session_state
            import state_utils
            from datetime import datetime, timezone

            live_tokens = context_budget.read_current_tokens(
                project_dir=project_dir,
                session_id=session_id,
            )

            import subagent_transcript
            _agent_id, spawn_output = subagent_transcript._extract_spawn_ref(
                data.get("tool_response")
            )
            spawn_prefix = subagent_transcript.session_output_prefix(spawn_output)

            def _mutate(state: dict) -> None:
                view = session_state.session_view(state, session_id)
                if live_tokens is not None:
                    previous_tokens = view.get("context_current_tokens")
                    view["context_current_tokens"] = live_tokens
                    view["context_current_tokens_recorded_at"] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    context_budget.record_step_growth(
                        view, previous_tokens, live_tokens
                    )
                    # INFRA-374: provenance stamp mirroring
                    # user_turn_seq.record_user_turn's § C6 stamp. Literal
                    # value, not an import — canonical definitions are
                    # context_model.CONTEXT_CURRENT_TOKENS_SOURCE_KEY /
                    # CONTEXT_CURRENT_TOKENS_SOURCES[0] ("post-tool-use").
                    # Written to state (top level), not the per-session view.
                    state["context_current_tokens_source"] = "post-tool-use"
                # The ring buffer must become session-owned on this session's
                # FIRST write, not on its first positive delta. session_view()
                # inherits any key the session's entry lacks from the flat
                # mirror (A3) — correct for a cold-start seed, but if the key
                # were left absent from the entry, the NEXT write would inherit
                # again from a mirror another session had since advanced, and
                # the two sessions' deltas would remix. Pinning it here is what
                # makes C4 hold.
                view.setdefault(context_budget.CONTEXT_STEP_GROWTH_SAMPLES_KEY, [])
                session_state.apply_session_view(state, session_id, view)
                if spawn_prefix and session_id:
                    entry = state.get(
                        session_state.CONTEXT_SESSIONS_KEY, {}
                    ).get(session_id)
                    if isinstance(entry, dict):
                        entry["spawn_output_prefix"] = spawn_prefix

            state_path = project_dir / ".companion" / "state.json"
            updated = state_utils.update_state_json(state_path, _mutate)
            if isinstance(updated, dict) and session_id:
                entry = updated.get(session_state.CONTEXT_SESSIONS_KEY, {}).get(
                    session_id
                )
                if isinstance(entry, dict):
                    stored_prefix = entry.get("spawn_output_prefix")
        except Exception:
            pass

        # 2. effort.db attempt-row writer (INFRA-236) — separate metric,
        #    separate store. See module docstring above.
        #    INFRA-285 (CER-097, item D6): the sweep this call performs is
        #    scoped to this session's own rows via the prefix stored above. A
        #    None prefix (first spawn of a session) means "no filter" — today's
        #    global sweep — never an exclusion, or orphan rows would strand.
        try:
            import subagent_transcript
            subagent_transcript.record_attempt_from_transcript(
                project_dir=project_dir,
                session_id=session_id,
                tool_input=data.get("tool_input", {}),
                tool_response=data.get("tool_response"),
                tool_use_id=data.get("tool_use_id"),
                tool_name=tool_name,
                output_prefix=stored_prefix,
            )
        except Exception as exc:
            try:
                import subagent_transcript
                subagent_transcript.log_recording_event(
                    project_dir,
                    tool_name=tool_name,
                    tool_use_id=data.get("tool_use_id"),
                    decision=f"error:{type(exc).__name__}",
                )
            except Exception:
                pass

        sys.exit(0)

    if tool_name not in WATCHED_TOOLS:
        sys.exit(0)

    if not os.path.exists(PIPE_PATH):
        sys.exit(0)

    # get file path from tool input
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""

    cwd = data.get("cwd") or os.getcwd()

    loaded_modules = []
    try:
        state = json.loads(open(STATE_PATH).read())
        loaded_modules = state.get("last_loaded_modules", [])
    except Exception:
        pass

    try:
        fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
        msg: dict = {
            "event": "post_tool_use",
            "type": "file_changed",
            "path": file_path,
            "tool": tool_name,
            "file_path": file_path,
            "loaded_modules": loaded_modules,
            "session_id": data.get("session_id"),
            "cwd": cwd,
        }
        event = json.dumps(msg) + "\n"
        os.write(fd, event.encode())
        os.close(fd)
    except (OSError, BlockingIOError):
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
