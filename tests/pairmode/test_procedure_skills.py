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


class TestCoveredContractsGate:
    """Story INFRA-317: the builder procedure's pre-build step must be a
    concrete, executable intersection gate -- not advisory "be aware of
    covered contracts" prose. Pins: the intersection step, the doc-wins
    rule, and the evidence-quoting obligation into the story's `## Evidence`
    section. Forbidden proxy: awareness prose with no intersection/evidence
    steps must not be what lands."""

    def test_builder_procedure_names_covered_contracts(self):
        text = BUILDER_PROCEDURE.read_text(encoding="utf-8")
        assert "covered_contracts" in text
        assert "covered-contracts gate" in text.lower()

    def test_builder_procedure_has_intersection_step(self):
        text = BUILDER_PROCEDURE.read_text(encoding="utf-8")
        assert "primary_files" in text
        assert "touches" in text
        assert "intersection" in text.lower()

    def test_builder_procedure_requires_reading_both_halves(self):
        text = BUILDER_PROCEDURE.read_text(encoding="utf-8")
        assert "read **both**" in text or "read both" in text.lower()

    def test_builder_procedure_has_doc_wins_rule(self):
        text = BUILDER_PROCEDURE.read_text(encoding="utf-8")
        assert "the doc wins" in text.lower()

    def test_builder_procedure_has_evidence_quoting_obligation(self):
        text = BUILDER_PROCEDURE.read_text(encoding="utf-8")
        assert "## Evidence" in text
        assert "quote" in text.lower()

    def test_builder_procedure_names_pair_separator(self):
        text = BUILDER_PROCEDURE.read_text(encoding="utf-8")
        assert "`::`" in text


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
        ("agents/spec-writer.md.j2", "skills/pairmode/skills/spec-writer/procedure.md"),
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


# ---------------------------------------------------------------------------
# INFRA-305 — CER-078/084/100 doc-currency and durable parity tests.
#
# The whole defect class (CER-078, 084, 100) exists because nothing tested
# the security-auditor procedure's grading contract against the live hook
# sources. These two tests close that gap: one pins the PIPE CONTRACT text
# (Ensures 11), the other mechanizes the hook-import <-> exception-list
# parity check so the class fails a test the next time it recurs
# (Ensures 12).
# ---------------------------------------------------------------------------

import ast
import re


class TestPipePathAbsence:
    """Ensures 11: neither cold-eyes procedure instructs reading the retired
    `pipe_path` state.json key; both name the current tempfile.gettempdir()
    convention. Pins the copy source (reviewer) against the copy (security-
    auditor) so the two procedures cannot drift apart again."""

    @pytest.mark.parametrize(
        "procedure_path",
        [SECURITY_AUDITOR_PROCEDURE, REVIEWER_PROCEDURE],
        ids=["security-auditor", "reviewer"],
    )
    def test_no_read_from_pipe_path_instruction(self, procedure_path: pathlib.Path):
        text = procedure_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            assert not re.search(r"read from .*pipe_path", line, re.IGNORECASE), (
                f"{procedure_path} instructs reading the retired pipe_path "
                f"state.json key (CER-078): {line!r}"
            )

    @pytest.mark.parametrize(
        "procedure_path",
        [SECURITY_AUDITOR_PROCEDURE, REVIEWER_PROCEDURE],
        ids=["security-auditor", "reviewer"],
    )
    def test_names_tempfile_gettempdir(self, procedure_path: pathlib.Path):
        text = procedure_path.read_text(encoding="utf-8")
        assert "tempfile.gettempdir()" in text, (
            f"{procedure_path} must name the current pipe-path convention "
            "tempfile.gettempdir() (INFRA-238)"
        )


# The delegate-capable hooks and the plain pipe relays that must be absent
# from the exception block (docs/architecture.md:2573).
_HOOKS_DIR = REPO_ROOT / "hooks"
_SCRIPTS_DIR = REPO_ROOT / "skills" / "pairmode" / "scripts"


def _hook_delegates(hook_path: pathlib.Path) -> tuple[set[str], set[str]]:
    """AST-walk a hook file for Import/ImportFrom nodes (module-level and
    function-local) whose module basename is a skills/pairmode/scripts/
    module. Returns (module_names, symbol_names)."""
    mods = {p.stem for p in _SCRIPTS_DIR.glob("*.py")}
    tree = ast.parse(hook_path.read_text(encoding="utf-8"), filename=str(hook_path))
    module_names: set[str] = set()
    symbol_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".")[0]
                if base in mods:
                    module_names.add(base)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                base = node.module.split(".")[0]
                if base in mods:
                    module_names.add(base)
                    for alias in node.names:
                        symbol_names.add(alias.name)
    return module_names, symbol_names


def _exception_block_text() -> str:
    text = SECURITY_AUDITOR_PROCEDURE.read_text(encoding="utf-8")
    start = text.index("Documented thin-delegation exceptions")
    end = text.index("### 2. PIPE CONTRACT", start)
    return text[start:end]


class TestHookDelegationDocumentation:
    """INFRA-305 Ensures 12/13: the durable procedure-vs-architecture parity
    test. This is the mechanical guard the CER-078/084/100 defect class
    needed and never had — a hook that gains a new skills/pairmode/scripts/
    delegation must be documented in the security-auditor exception block
    (both the module name and, for `from module import name` delegations,
    the imported symbol name) or this test fails.

    Note (Ensures 13 feasibility record): only the *import* half of the
    exception list is mechanically checkable this way. The *state.json key*
    half (e.g. `context_step_growth_samples`, `expected_step_tokens`) is not,
    because those keys are written inside the delegate modules
    (`context_budget.record_step_growth` writes its own keys;
    `session_reset.decide_reset` returns a dict the hook splats) and never
    appear as literals in the hook source. A key-level parity test would
    require either a hand-maintained hook->key map (the same drift surface
    it is meant to police) or a call-graph analysis of the delegate modules.
    Deliberately not built here (see docs/stories/INFRA/INFRA-305.md
    § Out of scope).
    """

    def test_hook_delegations_are_documented_exceptions(self):
        exception_block = _exception_block_text()
        for hook_path in sorted(_HOOKS_DIR.glob("*.py")):
            module_names, symbol_names = _hook_delegates(hook_path)
            if not module_names and not symbol_names:
                # Plain pipe relays are correctly absent from the block
                # (docs/architecture.md:2573). Match the `hooks/<name>`
                # form used in the bullets, not the bare basename -- a bare
                # "stop.py" is a substring of "subagent_stop.py" and would
                # false-positive.
                assert f"hooks/{hook_path.name}" not in exception_block, (
                    f"{hook_path.name} has no skills/pairmode/scripts/ "
                    "delegation and must not appear in the documented "
                    "thin-delegation exception block"
                )
                continue

            assert f"hooks/{hook_path.name}" in exception_block, (
                f"{hook_path.name} delegates to {module_names or symbol_names} "
                "but is not named in the security-auditor procedure's "
                "documented thin-delegation exception block "
                f"(CER-078/084/100 drift shape). File: {SECURITY_AUDITOR_PROCEDURE}"
            )
            for module_name in module_names:
                assert module_name in exception_block, (
                    f"{hook_path.name} imports from {module_name!r} but that "
                    "module is not named in the security-auditor procedure's "
                    "exception block (CER-078/084/100 drift shape). "
                    f"File: {SECURITY_AUDITOR_PROCEDURE}"
                )
            for symbol_name in symbol_names:
                assert symbol_name in exception_block, (
                    f"{hook_path.name} imports the symbol {symbol_name!r} but "
                    "it is not named in the security-auditor procedure's "
                    "exception block (CER-078/084/100 drift shape). "
                    f"File: {SECURITY_AUDITOR_PROCEDURE}"
                )

    def test_plain_pipe_relays_absent_from_exception_block(self):
        exception_block = _exception_block_text()
        for name in ("stop.py", "session_end.py", "exit_plan_mode.py"):
            hook_path = _HOOKS_DIR / name
            module_names, symbol_names = _hook_delegates(hook_path)
            assert not module_names and not symbol_names, (
                f"{name} was expected to have no skills/pairmode/scripts/ "
                "delegation (docs/architecture.md:2573) but does; update "
                "this test's assumptions"
            )
            assert f"hooks/{name}" not in exception_block
