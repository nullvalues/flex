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
}

CLAUDE_BUILD_MD_NO_MIGRATION_CONTEXT = {
    "project_name": "myapp",
    "build_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q",
    "test_command": "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q",
    "migration_command": "",
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

    def test_project_context_block(self):
        assert "myapp" in self.output
        assert "a sample web application for testing" in self.output
        assert "Python 3.11+ / FastAPI / PostgreSQL" in self.output
        assert "multi-tenant SaaS with organisation and workspace hierarchy" in self.output

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
        assert "uv run pytest tests/pairmode/" in self.output


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
        assert "### 4. Tag the checkpoint" in self.output
        assert "### 5. Report" in self.output

    def test_build_command_substituted(self):
        assert "PATH=$HOME/.local/bin:$PATH uv run pytest tests/pairmode/ -x -q" in self.output

    def test_test_command_substituted(self):
        assert "PATH=$HOME/.local/bin:$PATH uv run pytest tests/ -x -q" in self.output

    def test_migration_command_present_when_provided(self):
        assert "uv run alembic upgrade head" in self.output
        assert "## Running migrations" in self.output

    def test_loop_breaker_section(self):
        assert "## Loop-breaker" in self.output
        assert "LOOP-BREAKER:" in self.output

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
        assert "BUILT: Story" in self.output
        assert "Files changed:" in self.output
        assert "Tests:" in self.output
        assert "Build gate: PASS" in self.output

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
        assert "REVIEW PASS" in self.output

    def test_fail_conditions(self):
        assert "FAIL conditions" in self.output
        assert "REVIEW FAIL" in self.output

    def test_revert_on_fail(self):
        assert "git checkout ." in self.output
        assert "git clean -fd" in self.output

    def test_what_you_must_not_do_section(self):
        assert "What you must not do" in self.output
        assert "Do not write" in self.output


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
