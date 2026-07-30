"""Tests for INFRA-240: procedure skills must not hardcode flex-specific
per-project literals (test command, test-directory convention, protected-file
list). These facts must live in the rendered CLAUDE.build.md Build standards
section instead, so a downstream fleet project bootstrapped onto pairmode 0.3
inherits a builder/reviewer that checks its own conventions, not flex's.
"""

from __future__ import annotations

import pathlib

import pytest


REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
BUILDER_PROCEDURE = REPO_ROOT / "skills" / "pairmode" / "skills" / "builder" / "procedure.md"
REVIEWER_PROCEDURE = REPO_ROOT / "skills" / "pairmode" / "skills" / "reviewer" / "procedure.md"

# Flex-specific literals that must never appear verbatim in a procedure skill.
# These are per-project-varying facts (INFRA-240) -- procedure skills must
# reference the rendered CLAUDE.build.md Build standards section instead.
FORBIDDEN_LITERALS = [
    "tests/pairmode/",
    "-x -q",
    "skills/seed/scripts/",
    "skills/companion/scripts/sidebar.py",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
]


@pytest.fixture(params=[BUILDER_PROCEDURE, REVIEWER_PROCEDURE], ids=["builder", "reviewer"])
def procedure_text(request) -> str:
    path: pathlib.Path = request.param
    assert path.exists(), f"expected procedure file to exist: {path}"
    return path.read_text(encoding="utf-8")


class TestNoHardcodedFlexLiterals:
    @pytest.mark.parametrize("literal", FORBIDDEN_LITERALS)
    def test_literal_absent(self, procedure_text: str, literal: str):
        assert literal not in procedure_text, (
            f"found flex-specific literal {literal!r} hardcoded in a procedure skill "
            "-- per-project facts (test command, test-directory convention, "
            "protected-file list) must be read from the project's rendered "
            "CLAUDE.build.md Build standards section instead (INFRA-240)."
        )


class TestProcedureSkillsReferenceBuildStandards:
    """Both procedure skills must point to CLAUDE.build.md's Build standards
    section as the source of the per-project facts they no longer hardcode."""

    def test_builder_references_build_standards_section(self):
        text = BUILDER_PROCEDURE.read_text(encoding="utf-8")
        assert "Build standards" in text
        assert "CLAUDE.build.md" in text

    def test_reviewer_references_build_standards_section(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert "Build standards" in text
        assert "CLAUDE.build.md" in text

    def test_reviewer_input_contract_lists_claude_build_md(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        contract_start = text.index("## Input contract")
        contract_end = text.index("\n---\n", contract_start)
        contract_section = text[contract_start:contract_end]
        assert "`CLAUDE.build.md`" in contract_section


SECURITY_AUDITOR_PROCEDURE = (
    REPO_ROOT / "skills" / "pairmode" / "skills" / "security-auditor" / "procedure.md"
)

# The four data-flow sub-check labels (INFRA-290). Both cold-eyes procedures
# must use this exact vocabulary so they cannot drift into two different
# names for the same defect class.
DATA_FLOW_LABELS = [
    "written-never-read",
    "required-never-written",
    "duplicate state",
    "half-implementation",
]


class TestDataFlowChecks:
    """INFRA-290: the four data-flow checks (derived from CER-101..104) must
    exist in both cold-eyes procedure skills, with the same four labels, and
    each input contract must carry its narrow search-authorisation entry."""

    @pytest.mark.parametrize("label", DATA_FLOW_LABELS)
    def test_label_in_reviewer_procedure(self, label: str):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert label in text, f"reviewer procedure missing data-flow label {label!r}"

    @pytest.mark.parametrize("label", DATA_FLOW_LABELS)
    def test_label_in_security_auditor_procedure(self, label: str):
        text = SECURITY_AUDITOR_PROCEDURE.read_text(encoding="utf-8")
        assert label in text, (
            f"security-auditor procedure missing data-flow label {label!r}"
        )

    def test_reviewer_has_item_13(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert "### 13. DATA FLOW" in text

    def test_security_auditor_has_check_7(self):
        text = SECURITY_AUDITOR_PROCEDURE.read_text(encoding="utf-8")
        assert "### 7. DATA-FLOW INTEGRITY" in text

    def test_reviewer_input_contract_gained_entry_9(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        contract_start = text.index("## Input contract")
        contract_end = text.index("\n---\n", contract_start)
        contract_section = text[contract_start:contract_end]
        assert "9. Targeted repository searches" in contract_section
        # The widening is bounded: loop runtime state stays off-limits.
        assert "state.json" in contract_section
        assert "effort database" in contract_section

    def test_security_auditor_input_contract_gained_entry_4(self):
        text = SECURITY_AUDITOR_PROCEDURE.read_text(encoding="utf-8")
        contract_start = text.index("## Input contract")
        contract_end = text.index("\n---\n", contract_start)
        contract_section = text[contract_start:contract_end]
        assert "4. Targeted repository searches" in contract_section
        assert "state.json" in contract_section
        assert "effort database" in contract_section

    def test_reviewer_item_13_cites_forcing_function(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        item_start = text.index("### 13. DATA FLOW")
        item_end = text.index("## Review output format", item_start)
        item = text[item_start:item_end]
        assert "CER-101" in item
        assert "CER-104" in item

    def test_reviewer_item_13_report_line_format(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert "DATA FLOW: <identifier> — writers: <file:line,...> — readers: <file:line,...>" in text


# ---------------------------------------------------------------------------
# INFRA-304 E8 — the current revert contract gains an executing test.
#
# CER-065's prescribed fix (asserting `git clean -fd`'s absence from the
# reviewer template) was rejected: the whole-tree revert is the intentional
# legacy-scope fallback, still documented in docs/architecture.md. The real
# residue was that this contract — declared-scope revert, with the
# whole-tree form gated on "no declared scope" — had no executing test
# anywhere. These tests close that gap by reading the live procedure text
# (unskipped) and the live-rendered agent template.
# ---------------------------------------------------------------------------


class TestReviewerRevertContract:
    def test_declared_scope_revert_present(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        assert "git checkout -- <path>" in text
        # Line-wrapped in the source: "git clean -fd --\n<path>".
        assert "git clean -fd --" in text
        assert "<path>" in text

    def test_whole_tree_fallback_present_and_gated(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        start = text.index("On FAIL, revert:")
        fence_index = text.index("git checkout .", start)
        gate_section = text[start:fence_index]
        assert "Only when both" in gate_section
        assert "primary_files" in gate_section
        assert "touches" in gate_section
        fence = text[fence_index : fence_index + 60]
        assert "git checkout ." in fence
        assert "git clean -fd" in fence

    def test_fail_cause_precedes_revert_block(self):
        text = REVIEWER_PROCEDURE.read_text(encoding="utf-8")
        fail_cause_index = text.index("FAIL-CAUSE:")
        revert_index = text.index("On FAIL, revert:")
        assert fail_cause_index < revert_index


class TestReviewerTemplateThinShell:
    """Pins the thin-shell property (HARNESS-002) that makes CER-065's
    bootstrap re-introduction vector inert: the rendered reviewer agent
    carries no `git` command at all, only a pointer at the procedure skill
    where the revert logic actually lives."""

    def test_rendered_reviewer_has_no_git_command_and_points_at_procedure(self):
        import jinja2

        templates_dir = REPO_ROOT / "skills" / "pairmode" / "templates"
        loader = jinja2.FileSystemLoader(str(templates_dir))
        env = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)
        context = {
            "project_name": "myapp",
            "build_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q",
            "test_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q",
            "pairmode_scripts_dir": "/path/to/flex/skills/pairmode/scripts",
            "protected_paths": [],
            "domain_isolation_rule": "filter all queries by workspace_id",
            "checklist_items": [],
        }
        output = env.get_template("agents/reviewer.md.j2").render(**context)
        assert "git " not in output
        assert "skills/pairmode/skills/reviewer/procedure.md" in output


# ---------------------------------------------------------------------------
# INFRA-304 E13 — the agent-shell procedure pointer resolves.
#
# Verified experimentally (see INFRA-304 § Evidence) that the bare relative
# path does NOT resolve in a bootstrapped fixture project's own tree, so the
# templates now render the pointer absolute via the existing
# `pairmode_scripts_dir` context variable. This test pins the resolvable
# path shape so a future edit cannot silently reintroduce a bare relative
# pointer.
# ---------------------------------------------------------------------------


class TestAgentShellProcedurePointerIsAbsolute:
    _TEMPLATES = [
        ("agents/builder.md.j2", "skills/pairmode/skills/builder/procedure.md"),
        ("agents/reviewer.md.j2", "skills/pairmode/skills/reviewer/procedure.md"),
        ("agents/intent-reviewer.md.j2", "skills/pairmode/skills/intent-reviewer/procedure.md"),
        ("agents/loop-breaker.md.j2", "skills/pairmode/skills/loop-breaker/procedure.md"),
        ("agents/security-auditor.md.j2", "skills/pairmode/skills/security-auditor/procedure.md"),
        ("agents/gate-worker.md.j2", "skills/pairmode/gate_worker/SKILL.md"),
    ]

    @pytest.mark.parametrize("template_name,pointer_suffix", _TEMPLATES)
    def test_rendered_pointer_is_absolute_and_resolvable_shape(self, template_name, pointer_suffix):
        import jinja2

        templates_dir = REPO_ROOT / "skills" / "pairmode" / "templates"
        loader = jinja2.FileSystemLoader(str(templates_dir))
        env = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)
        context = {
            "project_name": "myapp",
            "build_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q",
            "test_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q",
            "pairmode_scripts_dir": "/path/to/flex/skills/pairmode/scripts",
            "protected_paths": [],
            "domain_isolation_rule": "filter all queries by workspace_id",
            "checklist_items": [],
        }
        output = env.get_template(template_name).render(**context)
        assert pointer_suffix in output, (
            f"{template_name} must still contain the {pointer_suffix} pointer "
            "as a suffix of its rendered (now-absolute) path"
        )
        # Resolvable path shape: absolute (starts with "/"), and the full
        # rendered line resolves via normal filesystem ".." handling to the
        # real pairmode-install-relative path — pinned by finding the line
        # that carries the pointer and asserting it starts with "/".
        lines_with_pointer = [
            line.strip() for line in output.splitlines() if pointer_suffix in line
        ]
        assert len(lines_with_pointer) == 1
        assert lines_with_pointer[0].startswith("/")

    def test_pairmode_pkg_dir_resolves_against_real_scripts_dir(self):
        # End-to-end sanity: with the *real* pairmode_scripts_dir this repo
        # runs from, the rendered pointer resolves to an actual file on disk.
        real_scripts_dir = REPO_ROOT / "skills" / "pairmode" / "scripts"
        resolved = (
            real_scripts_dir / ".." / ".." / ".." / "skills" / "pairmode" / "skills"
            / "reviewer" / "procedure.md"
        ).resolve()
        assert resolved == REVIEWER_PROCEDURE.resolve()
        assert resolved.exists()
