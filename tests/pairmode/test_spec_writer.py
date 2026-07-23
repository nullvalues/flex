"""
tests/pairmode/test_spec_writer.py — coverage for INFRA-242: ideology enforcement
redesign (spec-time alignment + narrow reviewer drift check).

Coverage:
- spec-writer/procedure.md declares docs/ideology.md as its fifth bounded input,
  and its elaboration checklist gains an ideology-alignment step (Step 4a) that
  is caught at spec-writer time (a spec draft contradicting docs/ideology.md is
  either resolved inline or flagged for the operator, never silently proceeded).
- spec-writer/procedure.md's ideology-alignment step mirrors 0.2's skip behaviour
  when docs/ideology.md is absent, rather than failing.
- reviewer/procedure.md gains a narrow IDEOLOGY DRIFT check that is gated on
  out-of-spec diff content: an in-scope, spec-clean diff skips the
  docs/ideology.md re-read entirely; only out-of-spec diff content triggers it.
- reviewer/procedure.md's narrow drift check is explicitly distinguished from a
  full re-audit of the whole of docs/ideology.md on every story.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SPEC_WRITER_PROCEDURE = (
    _REPO_ROOT / "skills" / "pairmode" / "skills" / "spec-writer" / "procedure.md"
)
_REVIEWER_PROCEDURE = (
    _REPO_ROOT / "skills" / "pairmode" / "skills" / "reviewer" / "procedure.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# spec-writer: docs/ideology.md as a declared bounded input
# ---------------------------------------------------------------------------


def test_spec_writer_declares_five_bounded_inputs() -> None:
    text = _read(_SPEC_WRITER_PROCEDURE)
    assert "exactly five" in text, (
        "spec-writer procedure must declare five bounded inputs after gaining "
        "docs/ideology.md (INFRA-242)"
    )
    assert "exactly four" not in text, (
        "spec-writer procedure still references the old four-input contract"
    )


def test_spec_writer_declares_ideology_as_input() -> None:
    text = _read(_SPEC_WRITER_PROCEDURE)
    input_contract = text.split("## Input contract", 1)[1].split("## Procedure", 1)[0]
    assert "docs/ideology.md" in input_contract, (
        "spec-writer's declared Input contract section must name docs/ideology.md "
        "as a bounded input"
    )


def test_spec_writer_ideology_step_present() -> None:
    text = _read(_SPEC_WRITER_PROCEDURE)
    assert "Step 4a" in text, "spec-writer procedure must add an ideology-alignment step"
    step = text.split("### Step 4a", 1)[1].split("### Step 5", 1)[0]
    # modeled on 0.2's 5a/5b/5c structure: convictions, constraints, fingerprints
    assert "Core convictions" in step
    assert "Accepted constraints" in step
    assert "Prototype fingerprints" in step


def test_spec_writer_ideology_step_skips_gracefully_when_absent() -> None:
    text = _read(_SPEC_WRITER_PROCEDURE)
    step = text.split("### Step 4a", 1)[1].split("### Step 5", 1)[0]
    assert "skip" in step.lower(), (
        "ideology-alignment step must document a skip path when docs/ideology.md "
        "does not exist, mirroring 0.2's skip behaviour rather than failing"
    )


def test_spec_writer_ideology_conflict_resolution_documented() -> None:
    """The spec-writer must decide and document its conflict-resolution behaviour:
    resolve inline (preferred) or flag for the operator via status: revised."""
    text = _read(_SPEC_WRITER_PROCEDURE)
    step = text.split("### Step 4a", 1)[1].split("### Step 5", 1)[0]
    assert "resolve inline" in step.lower() or "resolved inline" in step.lower()
    assert "flag" in step.lower()

    # Step 5 (human-review signals) must reference the unresolved-conflict case,
    # proving the flagged path actually routes to status: "revised".
    step5 = text.split("### Step 5", 1)[1].split("### Step 6", 1)[0]
    assert "4a" in step5, (
        "Step 5's human-review signals must reference Step 4a's unresolved-conflict "
        "case so a flagged ideology conflict routes to status: revised"
    )


# ---------------------------------------------------------------------------
# reviewer: narrow, spec-gated IDEOLOGY DRIFT check
# ---------------------------------------------------------------------------


def test_reviewer_has_ideology_drift_checklist_item() -> None:
    text = _read(_REVIEWER_PROCEDURE)
    assert "IDEOLOGY DRIFT" in text, (
        "reviewer procedure must add a narrow IDEOLOGY DRIFT checklist item (INFRA-242)"
    )


def test_reviewer_ideology_drift_is_not_a_full_reaudit() -> None:
    text = _read(_REVIEWER_PROCEDURE)
    drift_section = text.split("### 12. IDEOLOGY DRIFT", 1)[1].split("---", 1)[0]
    assert "not" in drift_section.lower()
    assert "full re-audit" in drift_section.lower() or "full ideology re-audit" in drift_section.lower(), (
        "the drift check must explicitly distinguish itself from a full "
        "docs/ideology.md re-audit on every story"
    )


def test_reviewer_ideology_drift_gated_on_out_of_spec_content() -> None:
    """A diff that exactly matches its spec-approved scope must skip the
    docs/ideology.md re-read entirely; only out-of-spec content triggers it."""
    text = _read(_REVIEWER_PROCEDURE)
    drift_section = text.split("### 12. IDEOLOGY DRIFT", 1)[1].split("---", 1)[0]
    assert "in-spec" in drift_section
    assert "out-of-spec" in drift_section
    assert "skip" in drift_section.lower()


def test_reviewer_ideology_drift_input_is_conditional() -> None:
    """docs/ideology.md must be declared as a conditionally-read input, not an
    unconditional per-story read."""
    text = _read(_REVIEWER_PROCEDURE)
    input_contract = text.split("You read **only**:", 1)[1].split(
        "You **must not**", 1
    )[0]
    assert "docs/ideology.md" in input_contract
    assert "conditionally" in input_contract.lower()


def test_reviewer_ideology_drift_checklist_runs_every_invocation_but_gate_exempts_reread() -> None:
    """The checklist preamble says every item runs every invocation; the drift
    check's own text must be the thing that gates the docs/ideology.md re-read,
    not an exemption from running the check itself."""
    text = _read(_REVIEWER_PROCEDURE)
    assert "Run every item on every review invocation." in text
    drift_section = text.split("### 12. IDEOLOGY DRIFT", 1)[1].split("---", 1)[0]
    assert "PASS" in drift_section and "skipped" in drift_section.lower()
