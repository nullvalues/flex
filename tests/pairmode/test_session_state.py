"""Tests for skills/pairmode/scripts/session_state.py — INFRA-285 (CER-097).

Covers the session-keyed context record (A2-A6) and the spawn-output prefix
derivation the sweep-ownership wiring depends on (D1).
"""

from __future__ import annotations

import copy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "pairmode" / "scripts"))

import session_state  # noqa: E402
import subagent_transcript as st  # noqa: E402


def _iso(minutes_ago: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    ).isoformat()


# ---------------------------------------------------------------------------
# A1 / A2 — module shape and constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_module_is_stdlib_only(self) -> None:
        """A1: no third-party import, and nothing from skills/ but state_utils."""
        source = (
            REPO_ROOT / "skills" / "pairmode" / "scripts" / "session_state.py"
        ).read_text(encoding="utf-8")
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("import ") or line.startswith("from ")
        ]
        allowed_roots = {"datetime", "__future__", "state_utils"}
        for line in import_lines:
            root = line.split()[1].split(".")[0]
            assert root in allowed_roots, f"unexpected import: {line}"

    def test_context_sessions_key(self) -> None:
        assert session_state.CONTEXT_SESSIONS_KEY == "context_sessions"

    def test_session_scoped_keys_exact_set(self) -> None:
        """A2: the key set is a frozenset and is exactly these five keys."""
        assert isinstance(session_state.SESSION_SCOPED_KEYS, frozenset)
        assert session_state.SESSION_SCOPED_KEYS == {
            "context_current_tokens",
            "context_current_tokens_recorded_at",
            "context_session_reset_at",
            "context_step_growth_samples",
            "expected_step_tokens",
        }

    def test_session_live_ttl_is_180_and_not_the_token_ttl(self) -> None:
        """A6 / step 1: deliberately longer than the 60-minute token TTL."""
        import context_budget

        assert session_state.SESSION_LIVE_TTL_MINUTES == 180
        assert (
            session_state.SESSION_LIVE_TTL_MINUTES
            != context_budget._CONTEXT_TOKEN_STALE_MINUTES
        )


# ---------------------------------------------------------------------------
# A3 — session_view
# ---------------------------------------------------------------------------


class TestSessionView:
    def test_overlays_keyed_values_over_flat(self) -> None:
        state = {
            "context_current_tokens": 25_000,
            "expected_step_tokens": 9_000,
            "context_sessions": {
                "LOOP": {"context_current_tokens": 140_000},
            },
        }
        view = session_state.session_view(state, "LOOP")
        assert view["context_current_tokens"] == 140_000
        # A key absent from the entry keeps the flat value.
        assert view["expected_step_tokens"] == 9_000

    def test_never_mutates_the_state_it_reads(self) -> None:
        """A3: the input dict is byte-for-byte unchanged after the call."""
        state = {
            "context_current_tokens": 25_000,
            "context_sessions": {"LOOP": {"context_current_tokens": 140_000}},
        }
        before = copy.deepcopy(state)
        session_state.session_view(state, "LOOP")
        assert state == before

    def test_returns_a_new_dict(self) -> None:
        state = {"context_current_tokens": 1}
        view = session_state.session_view(state, "LOOP")
        assert view is not state
        view["context_current_tokens"] = 999
        assert state["context_current_tokens"] == 1

    def test_falsy_session_id_returns_copy_unchanged(self) -> None:
        state = {"context_current_tokens": 7, "context_sessions": {"X": {"a": 1}}}
        assert session_state.session_view(state, None) == state
        assert session_state.session_view(state, "") == state

    def test_no_record_returns_copy_unchanged(self) -> None:
        state = {"context_current_tokens": 7}
        assert session_state.session_view(state, "LOOP") == state

    def test_malformed_context_sessions_never_raises(self) -> None:
        for bad in (None, [], "nope", 3):
            state = {"context_current_tokens": 7, "context_sessions": bad}
            assert session_state.session_view(state, "LOOP")["context_current_tokens"] == 7

    def test_non_dict_state_returns_empty(self) -> None:
        assert session_state.session_view(None, "LOOP") == {}  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A4 — apply_session_view
# ---------------------------------------------------------------------------


class TestApplySessionView:
    def test_writes_keyed_and_mirrors_flat(self) -> None:
        state: dict = {}
        session_state.apply_session_view(
            state, "S1", {"context_current_tokens": 42_000, "unrelated": "x"}
        )
        entry = state["context_sessions"]["S1"]
        assert entry["context_current_tokens"] == 42_000
        assert "unrelated" not in entry
        assert "last_seen_at" in entry
        # A5: derived mirror.
        assert state["context_current_tokens"] == 42_000
        assert "unrelated" not in state

    def test_does_not_touch_other_sessions_entries(self) -> None:
        """A4: S1's entry is byte-for-byte unchanged after writing S2."""
        state = {
            "context_sessions": {
                "S1": {"context_current_tokens": 140_000, "last_seen_at": _iso(1)}
            }
        }
        before = copy.deepcopy(state["context_sessions"]["S1"])
        session_state.apply_session_view(state, "S2", {"context_current_tokens": 25_000})
        assert state["context_sessions"]["S1"] == before
        assert state["context_sessions"]["S2"]["context_current_tokens"] == 25_000

    def test_falsy_session_id_writes_flat_only(self) -> None:
        state: dict = {}
        session_state.apply_session_view(state, None, {"context_current_tokens": 5})
        assert state["context_current_tokens"] == 5
        assert "context_sessions" not in state

    def test_seeds_spawn_output_prefix_slot(self) -> None:
        state: dict = {}
        session_state.apply_session_view(state, "S1", {})
        assert state["context_sessions"]["S1"]["spawn_output_prefix"] is None

    def test_existing_prefix_is_preserved(self) -> None:
        state = {
            "context_sessions": {"S1": {"spawn_output_prefix": "/tmp/a/b/"}},
        }
        session_state.apply_session_view(state, "S1", {"context_current_tokens": 1})
        assert state["context_sessions"]["S1"]["spawn_output_prefix"] == "/tmp/a/b/"

    def test_malformed_inputs_never_raise(self) -> None:
        session_state.apply_session_view(None, "S1", {})  # type: ignore[arg-type]
        session_state.apply_session_view({}, "S1", None)  # type: ignore[arg-type]
        state = {"context_sessions": "not-a-dict"}
        session_state.apply_session_view(state, "S1", {"context_current_tokens": 3})
        assert state["context_sessions"]["S1"]["context_current_tokens"] == 3


# ---------------------------------------------------------------------------
# A6 — prune_stale_sessions
# ---------------------------------------------------------------------------


class TestPruneStaleSessions:
    def test_prunes_stale_and_unparseable_but_keeps_fresh_and_keep(self) -> None:
        state = {
            "context_sessions": {
                "FRESH": {"last_seen_at": _iso(5)},
                "OLD": {"last_seen_at": _iso(240)},
                "GARBAGE": {"last_seen_at": "garbage"},
            }
        }
        removed = session_state.prune_stale_sessions(state, keep="GARBAGE")
        assert removed == 1
        assert set(state["context_sessions"]) == {"FRESH", "GARBAGE"}

    def test_removes_the_record_entirely_when_empty(self) -> None:
        state = {"context_sessions": {"OLD": {"last_seen_at": _iso(1_000)}}}
        session_state.prune_stale_sessions(state)
        assert "context_sessions" not in state

    def test_custom_ttl_is_honoured(self) -> None:
        state = {"context_sessions": {"A": {"last_seen_at": _iso(30)}}}
        session_state.prune_stale_sessions(state, ttl_minutes=10)
        assert "context_sessions" not in state

    def test_malformed_state_never_raises(self) -> None:
        assert session_state.prune_stale_sessions(None) == 0  # type: ignore[arg-type]
        assert session_state.prune_stale_sessions({"context_sessions": []}) == 0

    def test_exactly_one_non_test_call_site(self) -> None:
        """A6: pruning is called once per SessionStart and nowhere else."""
        roots = [REPO_ROOT / "skills", REPO_ROOT / "hooks"]
        sites: "list[str]" = []
        for root in roots:
            for path in root.rglob("*.py"):
                if "node_modules" in path.parts or "tests" in path.parts:
                    continue
                for lineno, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1
                ):
                    if "prune_stale_sessions(" in line and not line.strip().startswith(
                        ("#", "def ")
                    ):
                        sites.append(f"{path}:{lineno}")
        assert len(sites) == 1, sites
        assert "session_start.py" in sites[0]


# ---------------------------------------------------------------------------
# live_session_ids / other_live_session_prefixes (C2, D5)
# ---------------------------------------------------------------------------


class TestLiveSessions:
    def test_live_session_ids_excludes_self_and_dead(self) -> None:
        state = {
            "context_sessions": {
                "SELF": {"last_seen_at": _iso(1)},
                "OTHER": {"last_seen_at": _iso(2)},
                "DEAD": {"last_seen_at": _iso(600)},
            }
        }
        assert session_state.live_session_ids(state, exclude="SELF") == ("OTHER",)

    def test_other_live_session_prefixes_dedupes_and_skips_empty(self) -> None:
        state = {
            "context_sessions": {
                "SELF": {"last_seen_at": _iso(1), "spawn_output_prefix": "/tmp/self/"},
                "A": {"last_seen_at": _iso(1), "spawn_output_prefix": "/tmp/a/"},
                "B": {"last_seen_at": _iso(1), "spawn_output_prefix": "/tmp/a/"},
                "C": {"last_seen_at": _iso(1), "spawn_output_prefix": None},
                "DEAD": {"last_seen_at": _iso(600), "spawn_output_prefix": "/tmp/d/"},
            }
        }
        assert session_state.other_live_session_prefixes(state, "SELF") == ("/tmp/a/",)

    def test_no_other_live_session_returns_empty_tuple(self) -> None:
        """D5: a single-session project must not lose orphan reconciliation."""
        state = {
            "context_sessions": {
                "SELF": {"last_seen_at": _iso(1), "spawn_output_prefix": "/tmp/self/"}
            }
        }
        assert session_state.other_live_session_prefixes(state, "SELF") == ()

    def test_malformed_state_returns_empty_tuple(self) -> None:
        assert session_state.other_live_session_prefixes({}, "S") == ()
        assert session_state.other_live_session_prefixes(
            {"context_sessions": None}, "S"
        ) == ()


# ---------------------------------------------------------------------------
# D1 — subagent_transcript.session_output_prefix
# ---------------------------------------------------------------------------


class TestSessionOutputPrefix:
    def test_derives_prefix_from_observed_shape(self) -> None:
        assert (
            st.session_output_prefix(
                "/tmp/claude-1000/-mnt-work-flex/abc-123/tasks/x.output"
            )
            == "/tmp/claude-1000/-mnt-work-flex/abc-123/"
        )

    def test_trailing_separator_prevents_sibling_match(self) -> None:
        a = st.session_output_prefix("/tmp/c/slug/abc-123/tasks/x.output")
        b = st.session_output_prefix("/tmp/c/slug/abc-1234/tasks/x.output")
        assert a is not None and b is not None
        assert not b.startswith(a)

    def test_none_returns_none(self) -> None:
        assert st.session_output_prefix(None) is None

    def test_path_with_no_tasks_component_returns_none(self) -> None:
        assert st.session_output_prefix("/tmp/claude-1000/slug/abc/x.output") is None

    def test_accepts_path_objects(self) -> None:
        assert st.session_output_prefix(Path("/tmp/a/b/tasks/x.output")) == "/tmp/a/b/"

    def test_performs_no_existence_check(self, tmp_path: Path) -> None:
        """D1: the file need not exist — a prefix is derived at spawn time."""
        missing = tmp_path / "sess" / "tasks" / "nope.output"
        assert st.session_output_prefix(missing) == str(tmp_path / "sess") + "/"

    def test_garbage_never_raises(self) -> None:
        for bad in (123, object(), b"\x00"):
            assert st.session_output_prefix(bad) is None  # type: ignore[arg-type]
