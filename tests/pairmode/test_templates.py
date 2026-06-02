"""Tests for pairmode Jinja2 templates CLAUDE.md.j2 and CLAUDE.build.md.j2."""

import pathlib
import jinja2
import pytest


TEMPLATES_DIR = pathlib.Path(__file__).parent.parent.parent / "skills" / "pairmode" / "templates"

CLAUDE_MD_CONTEXT = {
    "project_name": "myapp",
    "project_description": "a sample web application for testing",
    "stack": "Python 3.11+ / FastAPI / PostgreSQL",
    "domain_model": "multi-tenant SaaS with organisation and workspace hierarchy",
    "build_command": "uv run pytest",
    "test_command": "uv run pytest tests/ -x -q",
    "checklist_items": [
        {
            "name": "HOOK PERFORMANCE",
            "description": "Do any hook scripts make API calls or block? Hooks are thin relays only.",
            "severity": "CRITICAL",
        },
        {
            "name": "PIPE CONTRACT",
            "description": "Do all hook scripts write only to /tmp/companion.pipe?",
            "severity": "CRITICAL",
        },
        {
            "name": "SKILL ISOLATION",
            "description": "Do any skill scripts use hardcoded absolute paths?",
            "severity": "MEDIUM",
        },
    ],
    "protected_paths": [
        "hooks/",
        "skills/seed/scripts/",
        ".claude-plugin/plugin.json",
    ],
}

CLAUDE_BUILD_MD_CONTEXT = {
    "project_name": "myapp",
    "build_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q",
    "test_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q",
    "migration_command": "uv run alembic upgrade head",
    "pairmode_scripts_dir": "/path/to/flex/skills/pairmode/scripts",
}

CLAUDE_BUILD_MD_NO_MIGRATION_CONTEXT = {
    "project_name": "myapp",
    "build_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q",
    "test_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q",
    "migration_command": "",
    "pairmode_scripts_dir": "/path/to/flex/skills/pairmode/scripts",
}


def render(template_name: str, context: dict) -> str:
    loader = jinja2.FileSystemLoader(str(TEMPLATES_DIR))
    env = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)
    template = env.get_template(template_name)
    return template.render(**context)


# ---------------------------------------------------------------------------
# CLAUDE.md.j2 tests
# ---------------------------------------------------------------------------

class TestClaudeMdTemplate:
    def setup_method(self):
        self.output = render("CLAUDE.md.j2", CLAUDE_MD_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_project_name_in_title(self):
        assert "myapp" in self.output

    def test_read_before_any_task_section(self):
        assert "## Read before any task" in self.output
        assert "docs/brief.md" in self.output
        assert "docs/architecture.md" in self.output

    def test_session_modes_section_present(self):
        assert "## Session modes" in self.output

    def test_build_mode_present(self):
        assert "**Build mode**" in self.output
        assert "Build Phase N" in self.output
        assert "Build next story" in self.output
        assert "Continue building" in self.output

    def test_review_mode_present(self):
        assert "**Review mode**" in self.output
        assert "adversarial checker" in self.output

    def test_review_checklist_header(self):
        assert "## Review checklist" in self.output

    def test_spec_checklist_items_not_rendered(self):
        # L005: spec-derived items must NOT appear — reviewer checklist is universal only
        assert "HOOK PERFORMANCE" not in self.output
        assert "PIPE CONTRACT" not in self.output
        assert "SKILL ISOLATION" not in self.output

    def test_universal_protected_files_item(self):
        assert "PROTECTED FILES" in self.output

    def test_universal_story_scope_item(self):
        assert "STORY SCOPE" in self.output

    def test_universal_build_gate_item(self):
        assert "BUILD GATE" in self.output
        assert "uv run pytest" in self.output

    def test_review_output_format_section(self):
        assert "## Review output format" in self.output
        assert "PASS / FAIL" in self.output
        assert "CRITICAL" in self.output
        assert "HIGH" in self.output
        assert "MEDIUM" in self.output
        assert "LOW" in self.output

    def test_loop_breaker_section(self):
        assert "## Loop-breaker mode" in self.output
        assert "LOOP-BREAKER:" in self.output
        assert "first principles" in self.output

    def test_story_test_verification_section(self):
        assert "## Story test verification" in self.output
        assert "uv run pytest tests/ -x -q 2>&1 | tail -30" in self.output

    def test_brief_md_appears_before_architecture_md(self):
        brief_pos = self.output.index("docs/brief.md")
        arch_pos = self.output.index("docs/architecture.md")
        assert brief_pos < arch_pos

    def test_portability_statement_present(self):
        assert "cold-start" in self.output


# ---------------------------------------------------------------------------
# Story INFRA-126 — DOC CURRENCY pointer uses shipped path .claude/agents/reviewer.md
# ---------------------------------------------------------------------------

class TestClaudeMdDocCurrencyPointer:
    """Story INFRA-126: the DOCUMENTATION CURRENCY pointer in CLAUDE.md.j2 must
    reference the shipped path `.claude/agents/reviewer.md`, not the bare
    `agents/reviewer.md` (which does not exist in a bootstrapped project)."""

    def setup_method(self):
        self.output = render("CLAUDE.md.j2", CLAUDE_MD_CONTEXT)

    def test_rendered_contains_dotclaude_agents_reviewer_md(self):
        assert ".claude/agents/reviewer.md" in self.output

    def test_doc_currency_pointer_line_starts_with_dotclaude(self):
        # Find the line containing the DOC CURRENCY pointer reference.
        pointer_line = None
        for line in self.output.splitlines():
            if "agents/reviewer.md" in line and "§ 4" in line:
                pointer_line = line
                break
        assert pointer_line is not None, (
            "Could not find the DOC CURRENCY pointer line "
            "(expected a line containing 'agents/reviewer.md' and '§ 4')"
        )
        stripped = pointer_line.lstrip()
        assert stripped.startswith("See `.claude/agents/reviewer.md`"), (
            f"DOC CURRENCY pointer line does not start with the .claude/ prefix: {pointer_line!r}"
        )


# ---------------------------------------------------------------------------
# Story INFRA-124 — {{ test_command }} variable in CLAUDE.md.j2 Story test
# verification block
# ---------------------------------------------------------------------------

class TestClaudeMdTestCommandVariable:
    """Story INFRA-124: the Story test verification fenced bash block uses
    {{ test_command | default(..., true) }} so that:
      1. A Python-stack context renders the full pytest command.
      2. A Node-stack context renders the pnpm command and not pytest.
      3. An empty test_command renders the self-flagging NOT CONFIGURED placeholder.
    """

    def _render(self, test_command: str) -> str:
        ctx = {**CLAUDE_MD_CONTEXT, "test_command": test_command}
        return render("CLAUDE.md.j2", ctx)

    def test_python_stack_command_on_own_line_followed_by_tail(self):
        cmd = "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q"
        output = self._render(cmd)
        expected_line = f"{cmd} 2>&1 | tail -30"
        assert expected_line in output

    def test_node_stack_command_rendered_and_pytest_absent_in_verification_block(self):
        output = self._render("pnpm test")
        assert "pnpm test 2>&1 | tail -30" in output
        # The Story test verification fenced block must not contain pytest
        # (only the node command should appear there).
        section_start = output.index("## Story test verification")
        section_end = output.index("\n## ", section_start + 1)
        verification_section = output[section_start:section_end]
        assert "pytest" not in verification_section

    def test_empty_test_command_renders_not_configured_placeholder(self):
        output = self._render("")
        assert "TEST COMMAND NOT CONFIGURED" in output
        assert "exit 1" in output


# ---------------------------------------------------------------------------
# brief.md.j2 tests
# ---------------------------------------------------------------------------

BRIEF_MD_CONTEXT = {
    "project_name": "myapp",
    "project_description": "a sample web application for testing",
    "stack": "Python 3.11+ / FastAPI / PostgreSQL",
    "what": "A REST API that manages user accounts and permissions for enterprise clients.",
    "why": "Existing solutions lack fine-grained role management required by our enterprise customers.",
    "core_beliefs": "We prefer X.",
    "accepted_tradeoffs": "We gave up Y for Z.",
    "must_preserve_str": "The data contract.",
    "operator_contact": "alice@example.com",
}

BRIEF_MD_EMPTY_CONTEXT = {
    "project_name": "myapp",
    "project_description": "",
    "stack": "Python",
    "what": "",
    "why": "",
    "core_beliefs": "",
    "accepted_tradeoffs": "",
    "must_preserve_str": "",
    "operator_contact": "",
}


class TestBriefMdTemplate:
    def setup_method(self):
        self.output = render("docs/brief.md.j2", BRIEF_MD_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_project_name_in_title(self):
        assert "myapp" in self.output

    def test_not_in_scope_section_present(self):
        assert "Not in scope" in self.output

    def test_what_section_present(self):
        assert "What this project produces" in self.output
        assert "A REST API that manages user accounts" in self.output

    def test_why_section_present(self):
        assert "Why it exists" in self.output
        assert "fine-grained role management" in self.output

    def test_operator_contact_present(self):
        assert "alice@example.com" in self.output

    def test_constraints_section_present(self):
        assert "Constraints" in self.output

    def test_portability_statement_present(self):
        assert "cold-start" in self.output
        assert "docs/brief.md" in self.output
        assert "docs/architecture.md" in self.output


class TestBriefMdTemplateEmptyFields:
    def test_renders_gracefully_with_empty_what_and_why(self):
        output = render("docs/brief.md.j2", BRIEF_MD_EMPTY_CONTEXT)
        assert output
        assert "Not in scope" in output
        assert "myapp" in output

    def test_empty_what_shows_placeholder(self):
        output = render("docs/brief.md.j2", BRIEF_MD_EMPTY_CONTEXT)
        assert "not yet specified" in output

    def test_empty_why_shows_placeholder(self):
        output = render("docs/brief.md.j2", BRIEF_MD_EMPTY_CONTEXT)
        assert "not yet specified" in output


# ---------------------------------------------------------------------------
# Story 10.1 — brief.md.j2 positive ideology sections
# ---------------------------------------------------------------------------

BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT = {
    "project_name": "myapp",
    "project_description": "",
    "stack": "Python",
    "what": "",
    "why": "",
    "core_beliefs": "",
    "accepted_tradeoffs": "",
    "must_preserve_str": "",
    "operator_contact": "",
}


class TestBriefMdIdeologySections:
    """Story 10.1: three new ideology sections in docs/brief.md.j2."""

    def test_core_beliefs_heading_present_in_empty_render(self):
        output = render("docs/brief.md.j2", BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT)
        assert "## Core beliefs" in output

    def test_accepted_tradeoffs_heading_present_in_empty_render(self):
        output = render("docs/brief.md.j2", BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT)
        assert "## Accepted tradeoffs" in output

    def test_must_preserve_heading_present_in_empty_render(self):
        output = render("docs/brief.md.j2", BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT)
        assert "## What a second implementation must preserve" in output

    def test_core_beliefs_real_value_renders(self):
        ctx = {**BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT, "core_beliefs": "We prefer X."}
        output = render("docs/brief.md.j2", ctx)
        assert "We prefer X." in output

    def test_core_beliefs_real_value_no_placeholder(self):
        ctx = {**BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT, "core_beliefs": "We prefer X."}
        output = render("docs/brief.md.j2", ctx)
        # Placeholder for core_beliefs should not appear when real value provided
        assert "_(not yet specified — what does this project believe" not in output

    def test_empty_core_beliefs_shows_placeholder(self):
        output = render("docs/brief.md.j2", BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT)
        assert "_(not yet specified" in output

    def test_existing_headings_still_present(self):
        output = render("docs/brief.md.j2", BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT)
        assert "## What this project produces" in output
        assert "## Why it exists" in output
        assert "## Constraints" in output
        assert "## Not in scope" in output


# ---------------------------------------------------------------------------
# CLAUDE.build.md.j2 tests
# ---------------------------------------------------------------------------

class TestClaudeBuildMdTemplate:
    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_project_name_in_title(self):
        assert "myapp" in self.output

    def test_session_modes_section(self):
        assert "## Session modes" in self.output
        assert "**Build mode**" in self.output
        assert "Build Phase N" in self.output

    def test_build_loop_steps(self):
        assert "## Build loop" in self.output
        assert "### Step 1" in self.output
        assert "### Step 2" in self.output
        assert "### Step 3" in self.output

    def test_spawn_builder_instruction(self):
        assert "Spawn the `builder` subagent" in self.output

    def test_spawn_reviewer_instruction(self):
        assert "Spawn the `reviewer` subagent" in self.output

    def test_checkpoint_sequence_section(self):
        assert "## Checkpoint sequence" in self.output

    def test_checkpoint_steps_present(self):
        assert "### 1. Build gate" in self.output
        assert "### 2. Security audit" in self.output
        assert "### 3. Intent review" in self.output
        assert "### 4. Documentation review" in self.output
        assert "### 5. Phase completion check" in self.output
        assert "### 6. CER backlog review" in self.output
        assert "### 7. Tag the checkpoint" in self.output
        assert "### 8. Report" in self.output

    def test_before_loop_uses_current_phase_cli(self):
        # BUILD-011: "Before the first build loop" uses current-phase + next_story.py
        # instead of reading docs/brief.md and docs/architecture.md upfront.
        # Only look at the numbered steps block (up to the first ### subsection).
        section_start = self.output.index("## Before the first build loop")
        # The numbered steps end when the first sub-heading appears.
        first_sub_heading = self.output.index("### ", section_start)
        before_loop_steps = self.output[section_start:first_sub_heading]
        assert "current-phase" in before_loop_steps
        assert "next_story.py" in before_loop_steps
        # The blanket brief.md / architecture.md reads must not be in the steps.
        assert "docs/brief.md" not in before_loop_steps
        assert "docs/architecture.md" not in before_loop_steps

    def test_cer_backlog_review_heading_present(self):
        assert "CER backlog review" in self.output

    def test_checkpoint_report_contains_cer_backlog_line(self):
        assert "CER backlog:" in self.output

    def test_checkpoint_regression_all_pre_phase7_lines_present(self):
        # Regression: no pre-Phase-7 checkpoint lines removed by Documentation review step insertion
        assert "### 1. Build gate" in self.output
        assert "### 2. Security audit" in self.output
        assert "### 3. Intent review" in self.output
        assert "### 5. Phase completion check" in self.output
        assert "### 6. CER backlog review" in self.output
        assert "### 7. Tag the checkpoint" in self.output
        assert "### 8. Report" in self.output
        assert "Build gate:" in self.output
        assert "Security audit:" in self.output
        assert "Intent review:" in self.output
        assert "Git tag:" in self.output

    def test_documentation_review_step_present(self):
        # Story 8.8: Documentation review step must be present in checkpoint sequence
        assert "### 4. Documentation review" in self.output

    def test_documentation_review_references_readme(self):
        # Story 8.8: The documentation review step must mention README.md
        checkpoint_start = self.output.index("## Checkpoint sequence")
        # Find where the checkpoint sequence ends (next top-level section)
        next_section_match = self.output.find("\n## ", checkpoint_start + 1)
        checkpoint_section = self.output[checkpoint_start:next_section_match] if next_section_match != -1 else self.output[checkpoint_start:]
        assert "README" in checkpoint_section

    def test_build_command_substituted(self):
        assert "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q" in self.output

    def test_test_command_substituted(self):
        assert "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q" in self.output

    def test_migration_command_present_when_provided(self):
        assert "uv run alembic upgrade head" in self.output
        assert "## Running migrations" in self.output

    def test_loop_breaker_section(self):
        # Loop-breaker is now embedded in Step 3 escalation, not a standalone section
        assert "Attempt 2 FAIL" in self.output
        assert "LOOP-BREAKER:" in self.output
        assert "BUILD PAUSED" in self.output

    def test_rules_section(self):
        assert "## Rules" in self.output
        assert "Do not write code" in self.output

    def test_before_first_build_loop_section(self):
        assert "## Before the first build loop" in self.output
        assert "git log --oneline" in self.output


class TestClaudeBuildMdNoMigration:
    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_NO_MIGRATION_CONTEXT)

    def test_migration_section_absent_when_empty(self):
        assert "## Running migrations" not in self.output
        assert "alembic" not in self.output

    def test_other_sections_still_present(self):
        assert "## Build loop" in self.output
        assert "## Checkpoint sequence" in self.output


# ---------------------------------------------------------------------------
# Story INFRA-041 — fallback-policy pointer propagated to CLAUDE.build.md.j2
# ---------------------------------------------------------------------------

class TestClaudeBuildMdFallbackPolicyPointer:
    """Story INFRA-041: CLAUDE.build.md.j2 contains the same one-line fallback
    note that INFRA-033 added to flex's own CLAUDE.build.md, so future
    pairmode bootstraps inherit the orchestrator-level pointer."""

    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)

    def test_rendered_template_contains_opus_to_sonnet_fallback(self):
        assert "Opus → Sonnet" in self.output

    def test_rendered_template_contains_never_below_haiku(self):
        assert "never below Haiku" in self.output

    def test_rendered_template_points_at_architecture_section(self):
        assert "Model selection and fallback" in self.output


# ---------------------------------------------------------------------------
# Story INFRA-042 — pre-reviewer commit discipline encoded in CLAUDE.build.md.j2
# ---------------------------------------------------------------------------

class TestClaudeBuildMdPreReviewerCommitDiscipline:
    """Story INFRA-042: CLAUDE.build.md.j2 (and flex's own CLAUDE.build.md)
    encode an explicit pre-reviewer step that commits any uncommitted
    methodology files and runs `git checkout -- lessons/` before the reviewer
    is spawned. Backs the architecture-doc claim about "pre-reviewer commit
    discipline" with an actual orchestrator instruction."""

    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)

    def test_rendered_template_contains_methodology_commit_message(self):
        assert "pre-reviewer methodology file commit" in self.output

    def test_rendered_template_contains_git_checkout_lessons(self):
        assert "git checkout -- lessons/" in self.output

    def test_flex_claude_build_md_contains_methodology_commit_message(self):
        flex_build_md = (
            pathlib.Path(__file__).parent.parent.parent / "CLAUDE.build.md"
        ).read_text(encoding="utf-8")
        assert "pre-reviewer methodology file commit" in flex_build_md

    def test_flex_claude_build_md_contains_git_checkout_lessons(self):
        flex_build_md = (
            pathlib.Path(__file__).parent.parent.parent / "CLAUDE.build.md"
        ).read_text(encoding="utf-8")
        assert "git checkout -- lessons/" in flex_build_md


# ---------------------------------------------------------------------------
# Agent template shared context
# ---------------------------------------------------------------------------

AGENT_CONTEXT = {
    "project_name": "myapp",
    "build_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q",
    "test_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q",
    "protected_paths": [
        "hooks/",
        "skills/seed/scripts/",
        ".claude-plugin/plugin.json",
    ],
    "domain_isolation_rule": "filter all queries by workspace_id",
    "checklist_items": [
        {
            "name": "HOOK PERFORMANCE",
            "description": "Do any hook scripts make API calls or block? Hooks are thin relays only.",
            "severity": "CRITICAL",
        },
        {
            "name": "PIPE CONTRACT",
            "description": "Do all hook scripts write only to /tmp/companion.pipe?",
            "severity": "CRITICAL",
        },
        {
            "name": "SKILL ISOLATION",
            "description": "Do any skill scripts use hardcoded absolute paths?",
            "severity": "MEDIUM",
        },
    ],
}


# ---------------------------------------------------------------------------
# Builder agent template tests
# ---------------------------------------------------------------------------

class TestBuilderAgentTemplate:
    def setup_method(self):
        self.output = render("agents/builder.md.j2", AGENT_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_frontmatter_name(self):
        assert "name: builder" in self.output

    def test_frontmatter_tools(self):
        assert "tools: [Read, Write, Edit, Glob, Grep, Bash]" in self.output

    def test_frontmatter_model(self):
        assert "model: sonnet" in self.output

    def test_project_name_in_description(self):
        assert "myapp" in self.output

    def test_before_writing_section(self):
        assert "Before writing anything" in self.output
        assert "architecture.md" in self.output

    def test_protected_paths_listed(self):
        assert "hooks/" in self.output
        assert ".claude-plugin/plugin.json" in self.output

    def test_implementation_rules_section(self):
        assert "Implementation rules" in self.output
        assert "filter all queries by workspace_id" in self.output

    def test_test_command_substituted(self):
        assert "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q" in self.output

    def test_developer_action_gates_section(self):
        assert "DEVELOPER ACTION" in self.output
        assert "BUILDER PAUSED" in self.output

    def test_completion_report_format(self):
        # Verbose block removed in BUILD-019; minimal block remains
        assert "BUILD-RESULT: DONE" in self.output
        assert "SUMMARY:" in self.output
        assert "BUILT: Story" not in self.output
        assert "Build gate: PASS" not in self.output

    def test_builder_stuck_format(self):
        assert "BUILDER STUCK" in self.output
        assert "Attempted:" in self.output
        assert "loop-breaker" in self.output


# ---------------------------------------------------------------------------
# Reviewer agent template tests
# ---------------------------------------------------------------------------

class TestReviewerAgentTemplate:
    def setup_method(self):
        self.output = render("agents/reviewer.md.j2", AGENT_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_frontmatter_name(self):
        assert "name: reviewer" in self.output

    def test_project_name_in_description(self):
        assert "myapp" in self.output

    def test_before_reviewing_section(self):
        assert "Before reviewing" in self.output
        assert "architecture.md" in self.output
        assert "git diff HEAD" in self.output

    def test_spec_checklist_items_not_rendered(self):
        # L005: spec-derived items must NOT appear in reviewer checklist
        assert "HOOK PERFORMANCE" not in self.output
        assert "PIPE CONTRACT" not in self.output
        assert "SKILL ISOLATION" not in self.output

    def test_universal_checklist_items_rendered(self):
        assert "PROTECTED FILES" in self.output
        assert "STORY SCOPE" in self.output
        assert "BUILD GATE" in self.output
        assert "DOCUMENTATION CURRENCY" in self.output

    def test_story_scope_checklist_item(self):
        assert "STORY SCOPE" in self.output

    def test_test_run_section(self):
        assert "Test run" in self.output
        assert "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q" in self.output

    def test_pass_conditions(self):
        assert "PASS conditions" in self.output
        assert "No CRITICAL findings" in self.output
        assert "No HIGH findings" in self.output

    def test_commit_format_on_pass(self):
        assert "git add -A" in self.output
        assert "git commit" in self.output
        # Verbose REVIEW PASS block removed in BUILD-019; minimal block remains
        assert "feat(story-RAIL-NNN):" in self.output
        assert "REVIEW PASS" not in self.output

    def test_fail_conditions(self):
        assert "FAIL conditions" in self.output
        # Verbose REVIEW FAIL block removed in BUILD-019
        assert "REVIEW FAIL" not in self.output
        assert "git checkout ." in self.output

    def test_revert_on_fail(self):
        assert "git checkout ." in self.output
        assert "git clean -fd" in self.output

    def test_what_you_must_not_do_section(self):
        assert "What you must not do" in self.output
        assert "Do not write" in self.output

    def test_rail_scope_checklist_item_present(self):
        # Story 16.3: reviewer.md.j2 must contain RAIL SCOPE checklist item
        assert "RAIL SCOPE" in self.output


# ---------------------------------------------------------------------------
# Loop-breaker agent template tests
# ---------------------------------------------------------------------------

class TestLoopBreakerAgentTemplate:
    def setup_method(self):
        self.output = render("agents/loop-breaker.md.j2", AGENT_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_frontmatter_name(self):
        assert "name: loop-breaker" in self.output

    def test_project_name_in_description(self):
        assert "myapp" in self.output

    def test_input_format_section(self):
        assert "LOOP-BREAKER:" in self.output
        assert "TRIED:" in self.output

    def test_process_section(self):
        assert "Your process" in self.output
        assert "architecture.md" in self.output
        assert "root cause" in self.output

    def test_domain_isolation_rule_present(self):
        assert "filter all queries by workspace_id" in self.output

    def test_protected_paths_listed(self):
        assert "hooks/" in self.output

    def test_output_format_section(self):
        assert "LOOP-BREAKER ANALYSIS" in self.output
        assert "Root cause:" in self.output
        assert "Proposed approach:" in self.output
        assert "PROTECTED FILE INVOLVED" in self.output

    def test_what_you_must_not_do_section(self):
        assert "What you must not do" in self.output
        assert "Do not propose more than one approach" in self.output


# ---------------------------------------------------------------------------
# Security-auditor agent template tests
# ---------------------------------------------------------------------------

class TestSecurityAuditorAgentTemplate:
    def setup_method(self):
        self.output = render("agents/security-auditor.md.j2", AGENT_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_frontmatter_name(self):
        assert "name: security-auditor" in self.output

    def test_project_name_in_description(self):
        assert "myapp" in self.output

    def test_before_auditing_section(self):
        assert "Before auditing" in self.output
        assert "architecture.md" in self.output

    def test_domain_isolation_rule_in_preamble(self):
        assert "filter all queries by workspace_id" in self.output

    def test_hook_integrity_check(self):
        assert "HOOK INTEGRITY" in self.output
        assert "CRITICAL" in self.output

    def test_credential_exposure_check(self):
        assert "CREDENTIAL EXPOSURE" in self.output

    def test_path_traversal_check(self):
        assert "PATH TRAVERSAL" in self.output
        assert "Path.resolve()" in self.output

    def test_protected_paths_listed(self):
        assert "hooks/" in self.output
        assert ".claude-plugin/plugin.json" in self.output

    def test_domain_isolation_violation_check(self):
        assert "DOMAIN ISOLATION" in self.output

    def test_layer_violation_check(self):
        assert "LAYER VIOLATION" in self.output

    def test_report_format_section(self):
        assert "SECURITY AUDIT" in self.output
        assert "CRITICAL:" in self.output
        assert "HIGH:" in self.output
        assert "MEDIUM:" in self.output


# ---------------------------------------------------------------------------
# Intent-reviewer agent template tests
# ---------------------------------------------------------------------------

class TestIntentReviewerAgentTemplate:
    def setup_method(self):
        self.output = render("agents/intent-reviewer.md.j2", AGENT_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_frontmatter_name(self):
        assert "name: intent-reviewer" in self.output

    def test_project_name_in_description(self):
        assert "myapp" in self.output

    def test_before_reviewing_section(self):
        assert "Before reviewing" in self.output
        assert "architecture.md" in self.output
        assert "git diff" in self.output

    def test_build_and_test_commands_present(self):
        assert "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q" in self.output
        assert "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q" in self.output

    def test_domain_isolation_rule_present(self):
        assert "filter all queries by workspace_id" in self.output

    def test_story_alignment_section(self):
        assert "Story alignment" in self.output
        assert "ALIGNED" in self.output
        assert "PARTIAL" in self.output
        assert "PIVOT" in self.output
        assert "MISSING" in self.output

    def test_design_pivot_detection_section(self):
        assert "Design pivot detection" in self.output
        assert "API drift" in self.output
        assert "Schema drift" in self.output
        assert "Layer drift" in self.output

    def test_isolation_drift_check(self):
        assert "Isolation drift" in self.output

    def test_output_format_section(self):
        assert "INTENT REVIEW" in self.output
        assert "STORY ALIGNMENT" in self.output
        assert "PIVOTS AND CONCERNS" in self.output
        assert "DOWNSTREAM RISKS" in self.output
        assert "RECOMMENDED DOC EDITS" in self.output

    def test_calibration_section(self):
        assert "Calibration" in self.output

    def test_cross_rail_file_touches_in_pivot_detection(self):
        # Story 16.3: intent-reviewer.md.j2 must contain Cross-rail pivot detection item
        assert "Cross-rail" in self.output


# ---------------------------------------------------------------------------
# Docs template shared context
# ---------------------------------------------------------------------------

DOCS_CONTEXT = {
    "project_name": "myapp",
    "project_description": "a sample web application for testing",
    "stack": "Python 3.11+ / FastAPI / PostgreSQL",
    "domain_model": "multi-tenant SaaS with organisation and workspace hierarchy",
    "module_structure": [
        {
            "name": "api",
            "description": "HTTP layer — routes and request validation",
            "paths": ["src/api/", "src/routers/"],
        },
        {
            "name": "services",
            "description": "Business logic — no HTTP or DB concerns",
            "paths": ["src/services/"],
        },
    ],
    "layer_rules": [
        {
            "layer": "api/",
            "may_import": "services/, stdlib",
            "may_not_import": "db/ directly",
        },
        {
            "layer": "services/",
            "may_import": "db/, stdlib",
            "may_not_import": "api/",
        },
    ],
    "build_command": "uv run pytest",
    "test_command": "uv run pytest tests/ -x -q",
    "protected_paths": [
        "hooks/",
        "skills/seed/scripts/",
        ".claude-plugin/plugin.json",
    ],
    "non_negotiables": [
        "All DB queries must filter by workspace_id.",
        "Hooks must never make API calls.",
    ],
}

DOCS_CONTEXT_NO_NON_NEGOTIABLES = {**DOCS_CONTEXT, "non_negotiables": []}


# ---------------------------------------------------------------------------
# architecture.md.j2 tests
# ---------------------------------------------------------------------------

class TestArchitectureMdTemplate:
    def setup_method(self):
        self.output = render("docs/architecture.md.j2", DOCS_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_project_name_in_title(self):
        assert "myapp" in self.output

    def test_project_description_present(self):
        assert "a sample web application for testing" in self.output

    def test_stack_section(self):
        assert "Python 3.11+ / FastAPI / PostgreSQL" in self.output

    def test_domain_model_section(self):
        assert "multi-tenant SaaS with organisation and workspace hierarchy" in self.output

    def test_module_structure_rendered(self):
        assert "api/" in self.output
        assert "HTTP layer" in self.output
        assert "services/" in self.output
        assert "Business logic" in self.output

    def test_module_paths_rendered(self):
        assert "src/api/" in self.output
        assert "src/routers/" in self.output
        assert "src/services/" in self.output

    def test_layer_rules_table_rendered(self):
        assert "Layer" in self.output
        assert "May import from" in self.output
        assert "May not import from" in self.output
        assert "services/, stdlib" in self.output
        assert "db/ directly" in self.output

    def test_build_and_test_commands(self):
        assert "uv run pytest" in self.output

    def test_protected_paths_listed(self):
        assert "hooks/" in self.output
        assert ".claude-plugin/plugin.json" in self.output

    def test_non_negotiables_rendered(self):
        assert "All DB queries must filter by workspace_id." in self.output
        assert "Hooks must never make API calls." in self.output

    def test_empty_non_negotiables_shows_placeholder(self):
        output = render("docs/architecture.md.j2", DOCS_CONTEXT_NO_NON_NEGOTIABLES)
        assert "No non-negotiables defined yet" in output
        assert "All DB queries must filter by workspace_id." not in output


# ---------------------------------------------------------------------------
# phase-prompts.md.j2 tests
# ---------------------------------------------------------------------------

class TestPhasePromptsMdTemplate:
    def setup_method(self):
        self.output = render("docs/phase-prompts.md.j2", DOCS_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_project_name_in_header(self):
        assert "myapp" in self.output

    def test_header_present(self):
        assert "Phase Prompts" in self.output

    def test_instructions_blurb_present(self):
        assert "build orchestrator" in self.output

    def test_phase_1_section_present(self):
        assert "Phase 1" in self.output

    def test_story_1_1_section_present(self):
        assert "Story 1.1" in self.output

    def test_acceptance_criterion_placeholder(self):
        assert "Acceptance criterion" in self.output

    def test_instructions_placeholder(self):
        assert "Instructions" in self.output

    def test_jinja_comments_not_in_output(self):
        # Jinja {# ... #} comments must not appear in rendered output
        assert "{#" not in self.output
        assert "#}" not in self.output

    def test_story_format_guidance_present(self):
        # The template includes a comment about story format — should appear as rendered text somehow,
        # or at minimum not break rendering. The comment block is a Jinja comment so it won't render.
        # Just verify the file rendered fully.
        assert "Acceptance criterion" in self.output


# ---------------------------------------------------------------------------
# checkpoints.md.j2 tests
# ---------------------------------------------------------------------------

class TestCheckpointsMdTemplate:
    def setup_method(self):
        self.output = render("docs/checkpoints.md.j2", DOCS_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_project_name_in_header(self):
        assert "myapp" in self.output

    def test_header_present(self):
        assert "Checkpoints" in self.output

    def test_checkpoint_description_present(self):
        assert "checkpoint sequence" in self.output

    def test_cp1_placeholder_present(self):
        assert "cp1-" in self.output

    def test_tag_command_structure_present(self):
        assert "git tag" in self.output
        assert "git push" in self.output

    def test_phase_reference_present(self):
        assert "Phase:" in self.output

    def test_acceptance_placeholder_present(self):
        assert "Acceptance:" in self.output


# ---------------------------------------------------------------------------
# Per-phase template tests (Story 7.2)
# ---------------------------------------------------------------------------

INDEX_PHASE_CONTEXT = {
    "project_name": "myapp",
    "phases": [
        {"id": 1, "title": "— fill in —", "status": "planned", "file": "phase-1.md"},
    ],
}

PHASE_ONE_CONTEXT = {
    "project_name": "myapp",
    "phase_id": 1,
    "phase_title": "Foundation",
    "prev_phase": None,
    "next_phase": None,
    "goal": "",
    "stories": [],
    "era_id": None,
}

PHASE_BOTH_NAV_CONTEXT = {
    "project_name": "myapp",
    "phase_id": 2,
    "phase_title": "Core Features",
    "prev_phase": {"id": 1, "title": "Foundation"},
    "next_phase": {"id": 3, "title": "Polish"},
    "goal": "Build the core feature set.",
    "stories": [
        {"id": "2.1", "title": "User auth"},
        {"id": "2.2", "title": "Dashboard"},
    ],
    "era_id": None,
}


class TestIndexMdJ2Template:
    """Tests for docs/phases/index.md.j2"""

    def setup_method(self):
        self.output = render("docs/phases/index.md.j2", INDEX_PHASE_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_project_name_in_title(self):
        assert "myapp" in self.output

    def test_phase_id_column_present(self):
        assert "1" in self.output

    def test_status_column_present(self):
        assert "planned" in self.output

    def test_phase_file_link_present(self):
        assert "phase-1.md" in self.output

    def test_table_header_present(self):
        assert "Phase" in self.output
        assert "Title" in self.output
        assert "Status" in self.output
        assert "Link" in self.output


class TestBootstrap005IndexQueueSemantics:
    """Tests for BOOTSTRAP-005 queue-semantic additions to docs/phases/index.md.j2"""

    def setup_method(self):
        self.output = render("docs/phases/index.md.j2", INDEX_PHASE_CONTEXT)

    def test_next_to_build_present(self):
        assert "**Next to build:**" in self.output

    def test_next_to_build_file_link_present(self):
        assert "phase-1.md" in self.output
        assert "**Next to build:**" in self.output
        # Both must appear together in the rendered output
        idx_ntb = self.output.index("**Next to build:**")
        idx_link = self.output.index("phase-1.md")
        assert idx_link > idx_ntb

    def test_deferred_from_column_in_header(self):
        assert "Deferred from" in self.output

    def test_backlog_promotions_section_present(self):
        assert "## Backlog promotions" in self.output


class TestPhaseMdJ2BothNavigation:
    """Tests for docs/phases/phase.md.j2 with both prev and next phase."""

    def setup_method(self):
        self.output = render("docs/phases/phase.md.j2", PHASE_BOTH_NAV_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_left_navigation_link_present(self):
        # prev_phase is present — left nav arrow must appear
        assert "← " in self.output
        assert "Phase 1" in self.output
        assert "Foundation" in self.output

    def test_right_navigation_link_present(self):
        # next_phase is present — right nav arrow must appear
        assert "→" in self.output
        assert "Phase 3" in self.output
        assert "Polish" in self.output

    def test_goal_section_present(self):
        assert "## Goal" in self.output
        assert "Build the core feature set." in self.output

    def test_stories_table_present(self):
        # New manifest format: Stories section is a table
        assert "| ID | Title | Status |" in self.output
        assert "|----|-------|--------|" in self.output

    def test_cold_eyes_checklist_section(self):
        assert "CP-2 Cold-eyes checklist" in self.output


class TestPhaseMdJ2NoPrevNavigation:
    """Tests for docs/phases/phase.md.j2 with no prev_phase (Phase 1 boundary)."""

    def setup_method(self):
        self.output = render("docs/phases/phase.md.j2", PHASE_ONE_CONTEXT)

    def test_renders_without_error(self):
        assert self.output

    def test_left_navigation_link_absent(self):
        # prev_phase is None — left nav arrow must NOT appear
        assert "← " not in self.output

    def test_cold_eyes_checklist_section(self):
        assert "CP-1 Cold-eyes checklist" in self.output


class TestPhaseMdJ2EmptyStories:
    """Tests for docs/phases/phase.md.j2 with stories=[]."""

    def setup_method(self):
        self.output = render("docs/phases/phase.md.j2", PHASE_ONE_CONTEXT)

    def test_renders_without_crashing(self):
        assert self.output

    def test_no_story_heading_rendered(self):
        # No stories — no numbered story headings
        assert "### Story" not in self.output

    def test_stories_section_present(self):
        # ## Stories header should still appear
        assert "## Stories" in self.output


class TestBootstrapPhasesIntegration:
    """Integration tests: bootstrap writes per-phase files correctly."""

    def test_bootstrap_writes_phases_index(self, tmp_path):
        from click.testing import CliRunner
        from skills.pairmode.scripts.bootstrap import bootstrap

        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "newproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "docs/phases/index.md").exists()

    def test_bootstrap_writes_phase1(self, tmp_path):
        from click.testing import CliRunner
        from skills.pairmode.scripts.bootstrap import bootstrap

        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "newproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "docs/phases/phase-1.md").exists()

    def test_bootstrap_does_not_write_phase_prompts_md(self, tmp_path):
        from click.testing import CliRunner
        from skills.pairmode.scripts.bootstrap import bootstrap

        runner = CliRunner()
        result = runner.invoke(
            bootstrap,
            [
                "--project-dir", str(tmp_path),
                "--project-name", "newproject",
                "--stack", "Python / pytest",
                "--build-command", "uv run pytest",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert not (tmp_path / "docs/phase-prompts.md").exists(), (
            "Bootstrap must not write docs/phase-prompts.md for new projects"
        )


# ---------------------------------------------------------------------------
# CER backlog template tests (Story 7.3)
# ---------------------------------------------------------------------------

CER_BACKLOG_CONTEXT_EMPTY = {
    "project_name": "myapp",
    "last_updated": "2026-04-21",
    "cer_entries": [],
}

CER_BACKLOG_CONTEXT_WITH_ENTRIES = {
    "project_name": "myapp",
    "last_updated": "2026-04-21",
    "cer_entries": [
        {
            "id": "CER-001",
            "quadrant": "do_now",
            "finding": "SQL injection in user search endpoint",
            "source": "security-auditor",
            "date": "2026-04-21",
            "phase": "7",
        },
        {
            "id": "CER-002",
            "quadrant": "do_later",
            "finding": "Add request ID tracing",
            "source": "internal review",
            "date": "2026-04-21",
            "phase": "8",
        },
        {
            "id": "CER-003",
            "quadrant": "do_much_later",
            "finding": "Migrate to async DB driver",
            "source": "architect",
            "date": "2026-04-21",
            "phase": "",
        },
        {
            "id": "CER-004",
            "quadrant": "do_never",
            "finding": "Rewrite in Rust",
            "source": "random suggestion",
            "date": "2026-04-21",
            "phase": "",
            "resolution": "Not worth the migration cost given current scale.",
        },
    ],
}


class TestCerBacklogTemplateEmpty:
    """Render backlog.md.j2 with no entries — all four quadrant headings must appear."""

    def setup_method(self):
        self.output = render("docs/cer/backlog.md.j2", CER_BACKLOG_CONTEXT_EMPTY)

    def test_renders_without_error(self):
        assert self.output

    def test_project_name_in_title(self):
        assert "myapp" in self.output

    def test_last_updated_in_output(self):
        assert "2026-04-21" in self.output

    def test_do_now_heading_present(self):
        assert "## Do Now" in self.output

    def test_do_later_heading_present(self):
        assert "## Do Later" in self.output

    def test_do_much_later_heading_present(self):
        assert "## Do Much Later" in self.output

    def test_do_never_heading_present(self):
        assert "## Do Never" in self.output

    def test_empty_quadrants_show_none_placeholder(self):
        assert "*(none)*" in self.output

    def test_do_never_has_resolution_column(self):
        assert "Resolution" in self.output


class TestCerBacklogTemplateWithEntries:
    """Render backlog.md.j2 with one entry per quadrant — each appears under correct heading."""

    def setup_method(self):
        self.output = render("docs/cer/backlog.md.j2", CER_BACKLOG_CONTEXT_WITH_ENTRIES)

    def test_renders_without_error(self):
        assert self.output

    def test_do_now_entry_appears(self):
        assert "SQL injection in user search endpoint" in self.output

    def test_do_later_entry_appears(self):
        assert "Add request ID tracing" in self.output

    def test_do_much_later_entry_appears(self):
        assert "Migrate to async DB driver" in self.output

    def test_do_never_entry_appears(self):
        assert "Rewrite in Rust" in self.output

    def test_do_now_entry_under_do_now_heading(self):
        do_now_pos = self.output.index("## Do Now")
        do_later_pos = self.output.index("## Do Later")
        entry_pos = self.output.index("SQL injection in user search endpoint")
        assert do_now_pos < entry_pos < do_later_pos

    def test_do_later_entry_under_do_later_heading(self):
        do_later_pos = self.output.index("## Do Later")
        do_much_later_pos = self.output.index("## Do Much Later")
        entry_pos = self.output.index("Add request ID tracing")
        assert do_later_pos < entry_pos < do_much_later_pos

    def test_do_much_later_entry_under_do_much_later_heading(self):
        do_much_later_pos = self.output.index("## Do Much Later")
        do_never_pos = self.output.index("## Do Never")
        entry_pos = self.output.index("Migrate to async DB driver")
        assert do_much_later_pos < entry_pos < do_never_pos

    def test_do_never_entry_under_do_never_heading(self):
        do_never_pos = self.output.index("## Do Never")
        entry_pos = self.output.index("Rewrite in Rust")
        assert do_never_pos < entry_pos

    def test_do_never_resolution_appears(self):
        assert "Not worth the migration cost given current scale." in self.output

    def test_cer_ids_present(self):
        assert "CER-001" in self.output
        assert "CER-002" in self.output
        assert "CER-003" in self.output
        assert "CER-004" in self.output


# ---------------------------------------------------------------------------
# Story 8.1 — template migration: phase-prompts.md reference tests
# ---------------------------------------------------------------------------

import re


class TestClaudeBuildMdPermissionScopeCommands:
    """Story BUILD-002 / INFRA-131: CLAUDE.build.md.j2 must contain explicit
    bash commands that exercise the story-scoped permission lifecycle and the
    story-status update.  After INFRA-131 collapsed the inline ``python -c``
    blocks into ``flex_build.py`` subcommands, the assertions reference the
    new CLI surface (``write-permissions`` / ``clear-permissions``) while
    ``story_update.py`` continues to be invoked directly."""

    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)

    def test_write_story_permissions_present(self):
        assert "flex_build.py write-permissions" in self.output

    def test_clear_story_permissions_present(self):
        assert "flex_build.py clear-permissions" in self.output

    def test_story_update_py_present(self):
        assert "story_update.py" in self.output


class TestClaudeBuildMdPhasePromptsReferences:
    """Assert that CLAUDE.build.md.j2 references phase-prompts.md only as a
    parenthetical legacy fallback, never as a standalone primary instruction."""

    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)

    def _standalone_references(self) -> list[str]:
        """Return lines that mention phase-prompts.md outside a parenthetical."""
        bad = []
        for line in self.output.splitlines():
            if "phase-prompts.md" in line:
                # A parenthetical legacy note contains "(or" and "legacy"
                if not ("(or" in line and "legacy" in line):
                    bad.append(line.strip())
        return bad

    def test_no_standalone_phase_prompts_md_reference(self):
        """phase-prompts.md must not appear as a standalone read instruction."""
        bad_lines = self._standalone_references()
        assert bad_lines == [], (
            f"Found standalone phase-prompts.md reference(s) in CLAUDE.build.md.j2:\n"
            + "\n".join(bad_lines)
        )

    def test_legacy_fallback_notes_present(self):
        """At least one parenthetical legacy fallback note must exist."""
        assert "(or" in self.output and "legacy" in self.output and "phase-prompts.md" in self.output

    def test_phase_n_md_is_primary_reference(self):
        """docs/phases/phase-N.md appears as the primary phase file reference."""
        assert "docs/phases/phase-N.md" in self.output


class TestIntentReviewerPhasePromptsReferences:
    """Assert that agents/intent-reviewer.md.j2 references phase-prompts.md only
    as a parenthetical legacy fallback, never as a standalone primary instruction."""

    def setup_method(self):
        self.output = render("agents/intent-reviewer.md.j2", AGENT_CONTEXT)

    def _standalone_references(self) -> list[str]:
        """Return lines that mention phase-prompts.md outside a parenthetical."""
        bad = []
        for line in self.output.splitlines():
            if "phase-prompts.md" in line:
                if not ("(or" in line and "legacy" in line):
                    bad.append(line.strip())
        return bad

    def test_no_standalone_phase_prompts_md_reference(self):
        """phase-prompts.md must not appear as a standalone read instruction."""
        bad_lines = self._standalone_references()
        assert bad_lines == [], (
            f"Found standalone phase-prompts.md reference(s) in intent-reviewer.md.j2:\n"
            + "\n".join(bad_lines)
        )

    def test_legacy_fallback_notes_present(self):
        """At least one parenthetical legacy fallback note must exist."""
        assert "(or" in self.output and "legacy" in self.output and "phase-prompts.md" in self.output

    def test_phase_n_md_is_primary_reference(self):
        """docs/phases/phase-N.md appears as the primary phase file reference."""
        assert "docs/phases/phase-N.md" in self.output


# ---------------------------------------------------------------------------
# Story 10.0 — ideology.md.j2 template tests
# ---------------------------------------------------------------------------

IDEOLOGY_EMPTY_CONTEXT = {
    "project_name": "myapp",
    "convictions": [],
    "value_hierarchy": [],
    "constraints": [],
    "fingerprints": [],
    "must_preserve": [],
    "should_question": [],
    "free_to_change": [],
    "comparison_dimensions": [],
}


class TestIdeologyMdTemplate:
    """Tests for docs/ideology.md.j2."""

    def test_renders_without_error_empty_context(self):
        output = render("docs/ideology.md.j2", IDEOLOGY_EMPTY_CONTEXT)
        assert output

    def test_all_six_section_headings_present(self):
        output = render("docs/ideology.md.j2", IDEOLOGY_EMPTY_CONTEXT)
        assert "## Core convictions" in output
        assert "## Value hierarchy" in output
        assert "## Accepted constraints" in output
        assert "## Prototype fingerprints" in output
        assert "## Reconstruction guidance" in output
        assert "## Comparison basis" in output

    def test_placeholder_strings_present_in_empty_context(self):
        output = render("docs/ideology.md.j2", IDEOLOGY_EMPTY_CONTEXT)
        # Each empty section should contain the "_(not yet specified" placeholder
        assert "_(not yet specified" in output

    def test_project_name_in_title(self):
        output = render("docs/ideology.md.j2", IDEOLOGY_EMPTY_CONTEXT)
        assert "myapp" in output

    def test_project_name_substituted_with_testproject(self):
        context = {**IDEOLOGY_EMPTY_CONTEXT, "project_name": "TestProject"}
        output = render("docs/ideology.md.j2", context)
        assert "TestProject" in output

    def test_conviction_value_renders_when_provided(self):
        context = {**IDEOLOGY_EMPTY_CONTEXT, "convictions": ["We prefer X over Y"]}
        output = render("docs/ideology.md.j2", context)
        assert "We prefer X over Y" in output

    def test_conviction_placeholder_absent_when_convictions_provided(self):
        context = {**IDEOLOGY_EMPTY_CONTEXT, "convictions": ["We prefer X over Y"]}
        output = render("docs/ideology.md.j2", context)
        # The placeholder should not appear when actual convictions are provided
        assert "_(not yet specified — fill in before first story" not in output


# ---------------------------------------------------------------------------
# Story 10.2 — reviewer.md.j2: IDEOLOGY ALIGNMENT checklist item
# ---------------------------------------------------------------------------

class TestReviewerAgentIdeologyAlignment:
    """Story 10.2: reviewer.md.j2 must contain IDEOLOGY ALIGNMENT as checklist item 5."""

    def setup_method(self):
        self.output = render("agents/reviewer.md.j2", AGENT_CONTEXT)

    def test_ideology_alignment_present(self):
        assert "IDEOLOGY ALIGNMENT" in self.output

    def test_sub_checks_5a_5b_5c_present(self):
        assert "5a." in self.output
        assert "5b." in self.output
        assert "5c." in self.output

    def test_docs_ideology_md_referenced(self):
        assert "docs/ideology.md" in self.output

    def test_documentation_currency_still_present_regression(self):
        assert "DOCUMENTATION CURRENCY" in self.output

    def test_protected_files_still_present_regression(self):
        assert "PROTECTED FILES" in self.output

    def test_story_scope_still_present_regression(self):
        assert "STORY SCOPE" in self.output

    def test_build_gate_still_present_regression(self):
        assert "BUILD GATE" in self.output


# ---------------------------------------------------------------------------
# Story 10.3 — intent-reviewer.md.j2: ideology drift check
# ---------------------------------------------------------------------------

class TestIntentReviewerIdeologyDrift:
    """Story 10.3: intent-reviewer.md.j2 must include ideology drift checks."""

    def setup_method(self):
        self.output = render("agents/intent-reviewer.md.j2", AGENT_CONTEXT)

    def test_ideology_drift_in_output_format(self):
        assert "IDEOLOGY DRIFT" in self.output

    def test_step_6_docs_ideology_md_in_before_reviewing(self):
        # Step 6 must reference docs/ideology.md in the ## Before reviewing section
        before_idx = self.output.index("## Before reviewing")
        # Find the next ## section after "Before reviewing"
        next_section_idx = self.output.find("\n## ", before_idx + 1)
        before_section = self.output[before_idx:next_section_idx] if next_section_idx != -1 else self.output[before_idx:]
        assert "docs/ideology.md" in before_section
        assert "6." in before_section

    def test_ideology_drift_in_design_pivot_detection(self):
        # "Ideology drift" entry must appear in Design pivot detection section
        pivot_idx = self.output.index("## Design pivot detection")
        next_section_idx = self.output.find("\n## ", pivot_idx + 1)
        pivot_section = self.output[pivot_idx:next_section_idx] if next_section_idx != -1 else self.output[pivot_idx:]
        assert "Ideology drift" in pivot_section

    def test_docs_ideology_md_in_recommended_doc_edits(self):
        # docs/ideology.md: block must appear in RECOMMENDED DOC EDITS
        rec_idx = self.output.index("RECOMMENDED DOC EDITS")
        edits_section = self.output[rec_idx:]
        assert "docs/ideology.md" in edits_section

    def test_story_alignment_still_present_regression(self):
        assert "STORY ALIGNMENT" in self.output

    def test_pivots_and_concerns_still_present_regression(self):
        assert "PIVOTS AND CONCERNS" in self.output

    def test_downstream_risks_still_present_regression(self):
        assert "DOWNSTREAM RISKS" in self.output

    def test_recommended_doc_edits_still_present_regression(self):
        assert "RECOMMENDED DOC EDITS" in self.output


# ---------------------------------------------------------------------------
# Story 11.0 — must_preserve dual-key contract tests
# ---------------------------------------------------------------------------

class TestBriefMdMustPreserveStr:
    """Story 11.0: brief.md.j2 uses must_preserve_str (string), not must_preserve (list)."""

    def test_must_preserve_str_value_renders_in_brief_md(self):
        """Providing must_preserve_str renders the string content, not a list repr."""
        ctx = {**BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT, "must_preserve_str": "- prefer X\n- prefer Y"}
        output = render("docs/brief.md.j2", ctx)
        assert "prefer X" in output
        assert "prefer Y" in output

    def test_must_preserve_str_no_list_repr_in_brief_md(self):
        """must_preserve_str renders as prose — no Python list repr like ['item']."""
        ctx = {**BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT, "must_preserve_str": "- prefer X\n- prefer Y"}
        output = render("docs/brief.md.j2", ctx)
        assert "['prefer X'" not in output
        assert "['prefer X', 'prefer Y']" not in output

    def test_empty_must_preserve_str_shows_placeholder(self):
        """Empty must_preserve_str renders the placeholder text."""
        ctx = {**BRIEF_MD_IDEOLOGY_EMPTY_CONTEXT, "must_preserve_str": ""}
        output = render("docs/brief.md.j2", ctx)
        assert "_(not yet specified — which values, constraints, or behaviors must survive" in output

    def test_must_preserve_str_key_used_not_must_preserve(self):
        """brief.md.j2 renders correctly with must_preserve_str key present (no StrictUndefined error)."""
        # Omitting 'must_preserve' key entirely — template should not reference it
        ctx = {
            "project_name": "myapp",
            "what": "",
            "why": "",
            "core_beliefs": "",
            "accepted_tradeoffs": "",
            "must_preserve_str": "- key item",
            "operator_contact": "",
        }
        output = render("docs/brief.md.j2", ctx)
        assert "key item" in output


class TestIdeologyMdMustPreserveList:
    """Story 11.0: ideology.md.j2 uses must_preserve as a list via {% for %}."""

    def test_must_preserve_list_renders_via_for_loop(self):
        """ideology.md.j2 iterates must_preserve list and renders each item."""
        ctx = {**IDEOLOGY_EMPTY_CONTEXT, "must_preserve": ["item one", "item two"]}
        output = render("docs/ideology.md.j2", ctx)
        assert "item one" in output
        assert "item two" in output

    def test_must_preserve_list_no_python_repr(self):
        """ideology.md.j2 does not produce a Python list repr for must_preserve."""
        ctx = {**IDEOLOGY_EMPTY_CONTEXT, "must_preserve": ["item one", "item two"]}
        output = render("docs/ideology.md.j2", ctx)
        assert "['item one'" not in output

    def test_must_preserve_empty_list_shows_placeholder(self):
        """Empty must_preserve list renders the placeholder text in ideology.md."""
        ctx = {**IDEOLOGY_EMPTY_CONTEXT, "must_preserve": []}
        output = render("docs/ideology.md.j2", ctx)
        assert "Derive from the accepted constraints" in output


# ---------------------------------------------------------------------------
# Story 11.1 — reconstruction.md.j2 template tests
# ---------------------------------------------------------------------------

RECONSTRUCTION_EMPTY_CONTEXT: dict = {}


def render_lenient(template_name: str, context: dict) -> str:
    """Render a template with lenient (non-strict) undefined handling.

    Used for partial-context tests where some variables are intentionally absent.
    """
    loader = jinja2.FileSystemLoader(str(TEMPLATES_DIR))
    env = jinja2.Environment(loader=loader, undefined=jinja2.Undefined)
    template = env.get_template(template_name)
    return template.render(**context)


class TestReconstructionMdTemplate:
    """Tests for docs/reconstruction.md.j2."""

    def test_renders_without_error_empty_context(self):
        output = render_lenient("docs/reconstruction.md.j2", {})
        assert output

    def test_what_you_are_building_section_present(self):
        output = render_lenient("docs/reconstruction.md.j2", {})
        assert "## What you are building" in output

    def test_non_negotiable_ideology_section_present(self):
        output = render_lenient("docs/reconstruction.md.j2", {})
        assert "## Non-negotiable ideology" in output

    def test_what_must_survive_section_present(self):
        output = render_lenient("docs/reconstruction.md.j2", {})
        assert "## What must survive any implementation" in output

    def test_comparison_rubric_section_present(self):
        output = render_lenient("docs/reconstruction.md.j2", {})
        assert "## Comparison rubric" in output

    def test_instructions_for_reconstruction_agent_section_present(self):
        output = render_lenient("docs/reconstruction.md.j2", {})
        assert "## Instructions for the reconstruction agent" in output

    def test_conviction_renders_when_provided(self):
        output = render_lenient("docs/reconstruction.md.j2", {"convictions": ["We prefer X"]})
        assert "We prefer X" in output

    def test_constraint_name_rule_rationale_render(self):
        ctx = {
            "constraints": [
                {"name": "C1", "rule": "never do X", "rationale": "because Y"}
            ]
        }
        output = render_lenient("docs/reconstruction.md.j2", ctx)
        assert "C1" in output
        assert "never do X" in output
        assert "because Y" in output

    def test_project_name_in_title(self):
        output = render_lenient("docs/reconstruction.md.j2", {"project_name": "TestProject"})
        assert "TestProject" in output


# ---------------------------------------------------------------------------
# Story 12.1 — RECONSTRUCTION.md.j2 scoring template tests
# ---------------------------------------------------------------------------

class TestReconstructionReportTemplate:
    """Tests for RECONSTRUCTION.md.j2 — the report a reconstruction agent produces."""

    def test_renders_without_error_empty_context(self):
        output = render_lenient("RECONSTRUCTION.md.j2", {})
        assert output

    def test_ideology_adherence_section_present(self):
        output = render_lenient("RECONSTRUCTION.md.j2", {})
        assert "## Ideology adherence" in output

    def test_constraint_compliance_section_present(self):
        output = render_lenient("RECONSTRUCTION.md.j2", {})
        assert "## Constraint compliance" in output

    def test_comparison_rubric_scores_section_present(self):
        output = render_lenient("RECONSTRUCTION.md.j2", {})
        assert "## Comparison rubric scores" in output

    def test_summary_verdict_section_present(self):
        output = render_lenient("RECONSTRUCTION.md.j2", {})
        assert "## Summary verdict" in output

    def test_conviction_heading_renders_when_provided(self):
        output = render_lenient("RECONSTRUCTION.md.j2", {"convictions": ["We prefer X over Y"]})
        assert "### Conviction: We prefer X over Y" in output

    def test_comparison_dimension_name_and_description_render(self):
        ctx = {
            "comparison_dimensions": [
                {"name": "Decision fidelity", "description": "desc"}
            ]
        }
        output = render_lenient("RECONSTRUCTION.md.j2", ctx)
        assert "Decision fidelity" in output
        assert "desc" in output

    def test_project_name_in_title(self):
        output = render_lenient("RECONSTRUCTION.md.j2", {"project_name": "TestProject"})
        assert "TestProject" in output


# ---------------------------------------------------------------------------
# Story 14.1 — reconstruction-agent.md.j2 agent definition template tests
# ---------------------------------------------------------------------------

class TestReconstructionAgentTemplate:
    """Tests for agents/reconstruction-agent.md.j2."""

    def setup_method(self):
        self.output = render("agents/reconstruction-agent.md.j2", {"project_name": "TestProject"})

    def test_renders_without_error(self):
        assert self.output

    def test_phase_1_read_the_brief_section_present(self):
        assert "## Phase 1 — Read the brief" in self.output

    def test_phase_4_fill_in_scoring_report_section_present(self):
        assert "## Phase 4 — Fill in the scoring report" in self.output

    def test_project_name_substituted(self):
        assert "TestProject" in self.output

    def test_allowed_tools_in_frontmatter(self):
        assert "allowed-tools" in self.output


# ---------------------------------------------------------------------------
# Story INFRA-026 — reviewer-class agents pinned to model: opus
# ---------------------------------------------------------------------------

import sys as _sys

_SCRIPTS_DIR = (
    pathlib.Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
)
if str(_SCRIPTS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS_DIR))

from schema_validator import _parse_frontmatter  # noqa: E402


REVIEWER_CLASS_TEMPLATES = [
    "agents/reviewer.md.j2",
    "agents/intent-reviewer.md.j2",
    "agents/loop-breaker.md.j2",
    "agents/security-auditor.md.j2",
]

# Story INFRA-044: the three reviewer-class templates flipped from opus to
# sonnet baseline; loop-breaker stays opus because by the time it fires the
# case is hard by definition.
REVIEWER_CLASS_SONNET_BASELINE = [
    "agents/reviewer.md.j2",
    "agents/intent-reviewer.md.j2",
    "agents/security-auditor.md.j2",
]

# Per-template upgrade-comment text (Story INFRA-044).
REVIEWER_CLASS_UPGRADE_COMMENTS = {
    "agents/reviewer.md.j2": "# upgrade: opus  (when retry / pre-PR audit / mid-phase pivot)",
    "agents/intent-reviewer.md.j2": "# upgrade: opus  (when mid-phase pivot / pre-PR checkpoint)",
    "agents/security-auditor.md.j2": "# upgrade: opus  (when phase touched production code / pre-PR audit)",
}


class TestReviewerClassAgentsSonnetBaseline:
    """Story INFRA-044: reviewer-class agent templates (reviewer,
    intent-reviewer, security-auditor) carry `model: sonnet` in YAML
    frontmatter as the baseline. Loop-breaker remains pinned to `opus`
    because by the time it fires the case is hard by definition. Builder
    remains pinned to `sonnet` (regression). Each affected template gains
    an `# upgrade: opus` comment; the existing INFRA-033 `# fallback:`
    comments remain (fallback handles rate limits, upgrade handles edge
    cases — both apply)."""

    @pytest.mark.parametrize("template_name", REVIEWER_CLASS_SONNET_BASELINE)
    def test_reviewer_class_template_has_model_sonnet(self, template_name):
        rendered = render(template_name, AGENT_CONTEXT)
        fm = _parse_frontmatter(rendered)
        assert fm is not None, (
            f"{template_name}: rendered output has no parseable frontmatter"
        )
        assert "model" in fm, (
            f"{template_name}: frontmatter missing `model` key — got keys {sorted(fm)}"
        )
        assert fm["model"] == "sonnet", (
            f"{template_name}: expected model=sonnet, got model={fm['model']!r}"
        )

    @pytest.mark.parametrize("template_name", REVIEWER_CLASS_SONNET_BASELINE)
    def test_reviewer_class_template_raw_source_has_model_sonnet(self, template_name):
        # Verify the raw template source carries the baseline pin (pre-render),
        # so a project bootstrapped from these files inherits the pin even
        # if the consuming Jinja context does not pass any model variable.
        raw = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
        fm = _parse_frontmatter(raw)
        assert fm is not None, (
            f"{template_name}: raw template has no parseable frontmatter"
        )
        assert fm.get("model") == "sonnet", (
            f"{template_name}: raw template expected model=sonnet, got {fm.get('model')!r}"
        )

    @pytest.mark.parametrize(
        "template_name",
        list(REVIEWER_CLASS_UPGRADE_COMMENTS.keys()),
    )
    def test_reviewer_class_template_has_upgrade_comment(self, template_name):
        # Each affected template carries an inline `# upgrade: opus` comment
        # documenting the call-time upgrade triggers for that role.
        raw = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
        expected = REVIEWER_CLASS_UPGRADE_COMMENTS[template_name]
        assert expected in raw, (
            f"{template_name}: expected upgrade comment {expected!r} in raw template"
        )

    @pytest.mark.parametrize(
        "template_name",
        list(REVIEWER_CLASS_UPGRADE_COMMENTS.keys()),
    )
    def test_reviewer_class_rendered_has_upgrade_comment(self, template_name):
        rendered = render(template_name, AGENT_CONTEXT)
        expected = REVIEWER_CLASS_UPGRADE_COMMENTS[template_name]
        assert expected in rendered, (
            f"{template_name}: expected upgrade comment {expected!r} in rendered output"
        )

    def test_loop_breaker_remains_pinned_to_opus(self):
        # Regression: loop-breaker is the one reviewer-class agent that stays
        # on opus by default, because by the time it fires the case is hard.
        rendered = render("agents/loop-breaker.md.j2", AGENT_CONTEXT)
        fm = _parse_frontmatter(rendered)
        assert fm is not None, "loop-breaker.md.j2 has no parseable frontmatter"
        assert fm.get("model") == "opus", (
            f"loop-breaker.md.j2: expected model=opus, got {fm.get('model')!r}"
        )

    def test_loop_breaker_raw_source_remains_pinned_to_opus(self):
        raw = (TEMPLATES_DIR / "agents/loop-breaker.md.j2").read_text(encoding="utf-8")
        fm = _parse_frontmatter(raw)
        assert fm is not None, "loop-breaker.md.j2 raw template has no parseable frontmatter"
        assert fm.get("model") == "opus", (
            f"loop-breaker.md.j2 raw: expected model=opus, got {fm.get('model')!r}"
        )

    def test_builder_template_pinned_to_sonnet(self):
        rendered = render("agents/builder.md.j2", AGENT_CONTEXT)
        fm = _parse_frontmatter(rendered)
        assert fm is not None, "builder.md.j2 has no parseable frontmatter"
        assert fm.get("model") == "sonnet", (
            f"builder.md.j2: expected model=sonnet, got {fm.get('model')!r}"
        )

    @pytest.mark.parametrize(
        "template_name",
        REVIEWER_CLASS_TEMPLATES + ["agents/builder.md.j2"],
    )
    def test_affected_templates_have_valid_frontmatter(self, template_name):
        rendered = render(template_name, AGENT_CONTEXT)
        fm = _parse_frontmatter(rendered)
        assert fm is not None, (
            f"{template_name}: rendered output produced no parseable frontmatter"
        )
        # Sanity-check the frontmatter at least carries the canonical fields
        # all agent templates have (`name` and `description`).
        assert "name" in fm, f"{template_name}: missing `name` in frontmatter"
        assert "description" in fm, (
            f"{template_name}: missing `description` in frontmatter"
        )

    def test_architecture_doc_has_sonnet_baseline_subsection(self):
        # Story INFRA-044: the architecture doc replaces the old "Model
        # selection and fallback" subsection with the "sonnet baseline,
        # opus on demand" framing.
        arch_path = REPO_ROOT / "docs" / "architecture.md"
        text = arch_path.read_text(encoding="utf-8")
        assert "sonnet baseline" in text or "opus on demand" in text, (
            "docs/architecture.md: expected new 'sonnet baseline, opus on demand' "
            "framing in the model-selection subsection"
        )


# ---------------------------------------------------------------------------
# Story INFRA-027 — reviewer-class agents restricted to read-only tools
# ---------------------------------------------------------------------------

REVIEWER_CLASS_WITH_BASH = [
    "agents/reviewer.md.j2",
    "agents/intent-reviewer.md.j2",
    "agents/loop-breaker.md.j2",
]


class TestReviewerClassAgentsToolRestriction:
    """Story INFRA-027: reviewer-class agent templates restrict the `tools`
    frontmatter field to read-only tools plus Bash (security-auditor: no Bash
    since it never runs commands). Builder remains unrestricted."""

    @pytest.mark.parametrize("template_name", REVIEWER_CLASS_WITH_BASH)
    def test_reviewer_class_tools_field_is_read_only_plus_bash(self, template_name):
        rendered = render(template_name, AGENT_CONTEXT)
        fm = _parse_frontmatter(rendered)
        assert fm is not None, (
            f"{template_name}: rendered output has no parseable frontmatter"
        )
        assert "tools" in fm, (
            f"{template_name}: frontmatter missing `tools` key — got keys {sorted(fm)}"
        )
        # The minimal frontmatter parser stores flow-style YAML lists as the
        # raw scalar string. Compare against the canonical literal.
        assert fm["tools"] == "[Read, Grep, Glob, Bash]", (
            f"{template_name}: expected tools=[Read, Grep, Glob, Bash], "
            f"got tools={fm['tools']!r}"
        )

    @pytest.mark.parametrize("template_name", REVIEWER_CLASS_WITH_BASH)
    def test_reviewer_class_raw_source_has_tools_field(self, template_name):
        # Verify the raw template source carries the restriction as well, so a
        # project bootstrapped from these files inherits the field even without
        # a Jinja context that overrides it.
        raw = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
        fm = _parse_frontmatter(raw)
        assert fm is not None, (
            f"{template_name}: raw template has no parseable frontmatter"
        )
        assert fm.get("tools") == "[Read, Grep, Glob, Bash]", (
            f"{template_name}: raw template expected tools=[Read, Grep, Glob, Bash], "
            f"got {fm.get('tools')!r}"
        )

    def test_security_auditor_tools_field_omits_bash(self):
        rendered = render("agents/security-auditor.md.j2", AGENT_CONTEXT)
        fm = _parse_frontmatter(rendered)
        assert fm is not None, (
            "agents/security-auditor.md.j2: rendered output has no parseable frontmatter"
        )
        assert fm.get("tools") == "[Read, Grep, Glob]", (
            f"security-auditor: expected tools=[Read, Grep, Glob] (no Bash), "
            f"got tools={fm.get('tools')!r}"
        )

    def test_security_auditor_raw_source_tools_field_omits_bash(self):
        raw = (TEMPLATES_DIR / "agents/security-auditor.md.j2").read_text(encoding="utf-8")
        fm = _parse_frontmatter(raw)
        assert fm is not None, (
            "security-auditor.md.j2 raw template has no parseable frontmatter"
        )
        assert fm.get("tools") == "[Read, Grep, Glob]", (
            f"security-auditor raw: expected tools=[Read, Grep, Glob] (no Bash), "
            f"got {fm.get('tools')!r}"
        )

    def test_builder_tools_field_unchanged(self):
        # Builder must retain the full tool set (Read, Write, Edit, Glob, Grep, Bash).
        rendered = render("agents/builder.md.j2", AGENT_CONTEXT)
        fm = _parse_frontmatter(rendered)
        assert fm is not None, "builder.md.j2 has no parseable frontmatter"
        assert fm.get("tools") == "[Read, Write, Edit, Glob, Grep, Bash]", (
            f"builder.md.j2: expected tools=[Read, Write, Edit, Glob, Grep, Bash], "
            f"got tools={fm.get('tools')!r}"
        )


# ---------------------------------------------------------------------------
# Story INFRA-033 — model fallback comments in agent templates
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent

REVIEWER_FALLBACK_COMMENT = "# fallback: sonnet  (never below)"
BUILDER_FALLBACK_COMMENT = "# fallback: haiku  (never below)"


class TestAgentTemplateFallbackComments:
    """Story INFRA-033: each agent template carries an inline YAML comment
    after `model:` declaring the fallback tier. Builder falls to haiku;
    reviewer-class agents fall to sonnet."""

    @pytest.mark.parametrize("template_name", REVIEWER_CLASS_TEMPLATES)
    def test_reviewer_class_template_has_fallback_comment(self, template_name):
        raw = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
        assert REVIEWER_FALLBACK_COMMENT in raw, (
            f"{template_name}: expected fallback comment "
            f"{REVIEWER_FALLBACK_COMMENT!r} in raw template"
        )

    @pytest.mark.parametrize("template_name", REVIEWER_CLASS_TEMPLATES)
    def test_reviewer_class_rendered_has_fallback_comment(self, template_name):
        rendered = render(template_name, AGENT_CONTEXT)
        assert REVIEWER_FALLBACK_COMMENT in rendered, (
            f"{template_name}: expected fallback comment "
            f"{REVIEWER_FALLBACK_COMMENT!r} in rendered output"
        )

    def test_builder_template_has_fallback_comment(self):
        raw = (TEMPLATES_DIR / "agents/builder.md.j2").read_text(encoding="utf-8")
        assert BUILDER_FALLBACK_COMMENT in raw, (
            f"builder.md.j2: expected fallback comment "
            f"{BUILDER_FALLBACK_COMMENT!r} in raw template"
        )

    def test_builder_rendered_has_fallback_comment(self):
        rendered = render("agents/builder.md.j2", AGENT_CONTEXT)
        assert BUILDER_FALLBACK_COMMENT in rendered, (
            f"builder.md.j2: expected fallback comment "
            f"{BUILDER_FALLBACK_COMMENT!r} in rendered output"
        )

    def test_architecture_doc_has_model_selection_subsection(self):
        # Story INFRA-044: the subsection was renamed from "Model selection
        # and fallback" to "Model selection: sonnet baseline, opus on demand"
        # when the reviewer-class baseline flipped from opus to sonnet. The
        # fallback policy is still documented inside the new subsection
        # (rate-limit substitution downward), so the underlying contract is
        # preserved.
        arch_path = REPO_ROOT / "docs" / "architecture.md"
        text = arch_path.read_text(encoding="utf-8")
        assert "Model selection" in text, (
            "docs/architecture.md: expected a 'Model selection' subsection heading"
        )
        assert "sonnet baseline" in text or "opus on demand" in text, (
            "docs/architecture.md: expected new 'sonnet baseline, opus on demand' "
            "framing introduced by INFRA-044"
        )


# ---------------------------------------------------------------------------
# Story INFRA-030 — record_attempt.py wiring in build-loop instructions
# ---------------------------------------------------------------------------


class TestEffortTrackingWiring:
    """Story INFRA-030: flex's CLAUDE.build.md, the rendered
    CLAUDE.build.md.j2 template, and docs/architecture.md must wire effort
    recording into the build loop after each builder spawn and each reviewer
    spawn, and document the data model."""

    def test_flex_claude_build_md_records_after_builder_and_reviewer(self):
        flex_build_md = (REPO_ROOT / "CLAUDE.build.md").read_text(encoding="utf-8")
        # record_attempt.py must appear at least twice — once after the builder
        # spawn instruction (Step 1) and once after the reviewer spawn (Step 2).
        assert flex_build_md.count("record_attempt.py") >= 2, (
            "CLAUDE.build.md: expected at least 2 references to record_attempt.py "
            "(after builder spawn and after reviewer spawn); found "
            f"{flex_build_md.count('record_attempt.py')}"
        )
        # Both invocations must be properly tagged by --agent-role.
        assert "--agent-role builder" in flex_build_md, (
            "CLAUDE.build.md: expected `--agent-role builder` invocation"
        )
        assert "--agent-role reviewer" in flex_build_md, (
            "CLAUDE.build.md: expected `--agent-role reviewer` invocation"
        )

    def test_rendered_template_records_after_builder_and_reviewer(self):
        rendered = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)
        assert rendered.count("record_attempt.py") >= 2, (
            "CLAUDE.build.md.j2 (rendered): expected at least 2 references to "
            "record_attempt.py (after builder spawn and after reviewer spawn); "
            f"found {rendered.count('record_attempt.py')}"
        )
        assert "--agent-role builder" in rendered, (
            "CLAUDE.build.md.j2 (rendered): expected `--agent-role builder` invocation"
        )
        assert "--agent-role reviewer" in rendered, (
            "CLAUDE.build.md.j2 (rendered): expected `--agent-role reviewer` invocation"
        )

    def test_architecture_doc_has_effort_tracking_section(self):
        arch_path = REPO_ROOT / "docs" / "architecture.md"
        text = arch_path.read_text(encoding="utf-8")
        assert "## Effort tracking" in text, (
            "docs/architecture.md: expected '## Effort tracking' section heading"
        )


# ---------------------------------------------------------------------------
# Story INFRA-077 — optional spec review step in CLAUDE.build.md.j2
# ---------------------------------------------------------------------------

class TestClaudeBuildMdSpecReviewStep:
    """Story INFRA-077: CLAUDE.build.md.j2 contains an optional spec-review
    step (### 0. Spec review) inside ## Before the first build loop, placed
    after step 7 and before ## Model evaluation."""

    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)
        self.raw = (TEMPLATES_DIR / "CLAUDE.build.md.j2").read_text(encoding="utf-8")

    def test_rendered_template_contains_spec_review_heading(self):
        assert "Spec review" in self.output

    def test_rendered_template_spec_review_in_before_loop_section(self):
        before_start = self.output.index("## Before the first build loop")
        model_eval_start = self.output.index("## Model evaluation")
        before_section = self.output[before_start:model_eval_start]
        assert "Spec review" in before_section

    def test_rendered_template_spec_review_mentions_general_purpose(self):
        assert "general-purpose" in self.output

    def test_rendered_template_spec_review_mentions_critical_and_high(self):
        # The step instructs to report CRITICAL and HIGH findings only
        before_start = self.output.index("## Before the first build loop")
        model_eval_start = self.output.index("## Model evaluation")
        before_section = self.output[before_start:model_eval_start]
        assert "CRITICAL" in before_section
        assert "HIGH" in before_section

    def test_rendered_template_spec_review_has_skip_guidance(self):
        # Skip condition for single-story hotfix phases must be mentioned
        assert "single-story hotfix" in self.output

    def test_raw_template_contains_spec_review_heading(self):
        assert "Spec review" in self.raw

    def test_flex_claude_build_md_contains_spec_review(self):
        flex_build_md = (REPO_ROOT / "CLAUDE.build.md").read_text(encoding="utf-8")
        assert "Spec review" in flex_build_md

    def test_flex_claude_build_md_spec_review_in_before_loop_section(self):
        flex_build_md = (REPO_ROOT / "CLAUDE.build.md").read_text(encoding="utf-8")
        before_start = flex_build_md.index("## Before the first build loop")
        model_eval_start = flex_build_md.index("## Model evaluation")
        before_section = flex_build_md[before_start:model_eval_start]
        assert "Spec review" in before_section

    def test_architecture_doc_mentions_spec_review_step(self):
        arch_path = REPO_ROOT / "docs" / "architecture.md"
        text = arch_path.read_text(encoding="utf-8")
        assert "spec review" in text.lower() or "Spec review" in text


# ---------------------------------------------------------------------------
# Story INFRA-129 — Context budget check section replaced with mechanical-
# enforcement pointer in CLAUDE.build.md.j2, flex CLAUDE.md HOOK PERFORMANCE
# carve-out, and docs/architecture.md step 9 rewrite.
# ---------------------------------------------------------------------------

class TestInfra129ContextBudgetMechanicalEnforcementDocs:
    """Story INFRA-129: the prose describing the context budget check must
    point at the mechanical enforcement (hooks/pre_tool_use.py +
    skills/pairmode/scripts/context_budget.py), name all four state.json
    tunables, and drop the old four-step LLM ritual phrases. The flex-local
    CLAUDE.md grows a HOOK PERFORMANCE carve-out documenting the thin-
    delegation exception for pre_tool_use.py."""

    def setup_method(self):
        self.rendered_build_md = render(
            "CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT
        )

    def test_rendered_build_md_contains_enforced_mechanically(self):
        assert "Enforced mechanically" in self.rendered_build_md

    def test_rendered_build_md_names_hook_and_module(self):
        assert "hooks/pre_tool_use.py" in self.rendered_build_md
        assert (
            "skills/pairmode/scripts/context_budget.py"
            in self.rendered_build_md
        )

    def test_rendered_build_md_lists_all_four_tunables(self):
        assert "context_budget_threshold" in self.rendered_build_md
        assert "context_budget_overrun_pct" in self.rendered_build_md
        assert "expected_step_tokens" in self.rendered_build_md
        assert "context_budget_reprompt_margin" in self.rendered_build_md

    def test_rendered_build_md_drops_old_ritual_phrases(self):
        # None of the old four-step LLM ritual phrases may appear in the
        # rendered template — that ritual has been replaced wholesale by
        # the mechanical-enforcement pointer.
        assert (
            "Read `context_budget_threshold` from"
            not in self.rendered_build_md
        )
        assert (
            "Compare your current context window"
            not in self.rendered_build_md
        )
        assert (
            "Your context token count is visible"
            not in self.rendered_build_md
        )

    def test_flex_claude_md_contains_thin_delegation_exception(self):
        flex_claude_md = (
            REPO_ROOT / "CLAUDE.md"
        ).read_text(encoding="utf-8")
        assert "Documented thin-delegation exception:" in flex_claude_md
        assert "hooks/pre_tool_use.py" in flex_claude_md
        assert (
            "skills/pairmode/scripts/context_budget.py" in flex_claude_md
        )
        assert "remains CRITICAL" in flex_claude_md

    def test_architecture_md_step_9_names_hook_and_module(self):
        arch_path = REPO_ROOT / "docs" / "architecture.md"
        text = arch_path.read_text(encoding="utf-8")
        # Locate the rewritten step 9 region and assert both names appear
        # near it (the section header is "## The pairmode build loop" and
        # step 9 is "**Context budget check**").
        assert "hooks/pre_tool_use.py" in text
        assert "skills/pairmode/scripts/context_budget.py" in text


# ---------------------------------------------------------------------------
# Story INFRA-130 — Auth check generalization: reads recorded classification
# from docs/architecture.md before prompting the user
# ---------------------------------------------------------------------------

class TestInfra130AuthCheckGeneralization:
    """Story INFRA-130: the auth check section in CLAUDE.build.md.j2 gains a
    detection step that reads a recorded **Classification:** line from
    docs/architecture.md and auto-satisfies the check when one is found.
    The fallback path (load auth-coexistence.md and prompt) is preserved but
    is no longer the unconditional first step."""

    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)

    def test_rendered_contains_classification_detection_marker(self):
        """The rendered template must contain the bold **Classification:** marker
        used to detect a recorded classification in docs/architecture.md."""
        assert "**Classification:**" in self.output

    def test_rendered_contains_auto_satisfied(self):
        """The auto-satisfy branch must be present in the rendered template."""
        assert "auto-satisfied" in self.output

    def test_rendered_contains_auth_coexistence_md_fallback(self):
        """The fallback prompt path must still reference auth-coexistence.md."""
        assert "auth-coexistence.md" in self.output

    def test_rendered_contains_docs_architecture_md_in_auth_check(self):
        """docs/architecture.md must be referenced inside the auth check section."""
        auth_start = self.output.index("## Auth check")
        # Find the next top-level section after auth check
        next_section = self.output.find("\n## ", auth_start + 1)
        auth_section = self.output[auth_start:next_section] if next_section != -1 else self.output[auth_start:]
        assert "docs/architecture.md" in auth_section

    def test_auth_coexistence_md_not_unconditional_first_step(self):
        """auth-coexistence.md must appear AFTER 'If no recorded classification',
        not as the unconditional first instruction in the auth check section."""
        auth_start = self.output.index("## Auth check")
        next_section = self.output.find("\n## ", auth_start + 1)
        auth_section = self.output[auth_start:next_section] if next_section != -1 else self.output[auth_start:]
        no_recorded_pos = auth_section.index("If no recorded classification")
        coexistence_pos = auth_section.index("auth-coexistence.md")
        assert coexistence_pos > no_recorded_pos, (
            "auth-coexistence.md must appear after 'If no recorded classification', "
            "not as an unconditional first step in the auth check section"
        )


# ---------------------------------------------------------------------------
# Story BOOTSTRAP-004 — Schema delivery section in phase.md.j2
# ---------------------------------------------------------------------------

PHASE_SCHEMA_DELIVERY_CONTEXT = {
    "project_name": "myapp",
    "phase_id": 3,
    "phase_title": "Data Layer",
    "prev_phase": None,
    "next_phase": None,
    "goal": "",
    "stories": [],
    "era_id": None,
}


class TestBootstrap004SchemaDelivery:
    """Story BOOTSTRAP-004: docs/phases/phase.md.j2 contains a ## Schema delivery
    section after ## Stories and before the CP-N Cold-eyes checklist."""

    def setup_method(self):
        self.output = render("docs/phases/phase.md.j2", PHASE_SCHEMA_DELIVERY_CONTEXT)

    def test_rendered_output_contains_schema_delivery_heading(self):
        assert "## Schema delivery" in self.output

    def test_rendered_output_contains_management_surface_table_header(self):
        assert "Management surface" in self.output

    def test_rendered_output_contains_schema_delivery_empty_placeholder_row(self):
        assert "| | | |" in self.output


# ---------------------------------------------------------------------------
# Story INFRA-131 — flex_build.py CLI replaces inline python -c blocks in
# CLAUDE.build.md.j2
# ---------------------------------------------------------------------------


class TestInfra131FlexBuildTemplate:
    """Story INFRA-131: CLAUDE.build.md.j2 collapses the 8 inline
    ``uv run python -c "..."`` heredocs into one-liner calls to
    ``flex_build.py`` subcommands."""

    def setup_method(self):
        self.output = render("CLAUDE.build.md.j2", CLAUDE_BUILD_MD_CONTEXT)

    def test_rendered_template_calls_flex_build_select_builder_model(self):
        assert "flex_build.py select-builder-model" in self.output

    def test_rendered_template_has_no_inline_sys_path_boilerplate(self):
        assert "sys.path.insert(0, " not in self.output
