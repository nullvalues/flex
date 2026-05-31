"""Tests for .pairmode-overrides.j2 boilerplate correctness (INFRA-125)."""

import pathlib
import sys
import jinja2

# Ensure the scripts directory is importable
_SCRIPTS_DIR = (
    pathlib.Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from pairmode_drift_report import _load_overrides  # noqa: E402

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent.parent / "skills" / "pairmode" / "templates"


def render_overrides_template() -> str:
    """Render .pairmode-overrides.j2 with an empty context."""
    loader = jinja2.FileSystemLoader(str(TEMPLATES_DIR))
    env = jinja2.Environment(loader=loader, undefined=jinja2.Undefined, keep_trailing_newline=True)
    template = env.get_template(".pairmode-overrides.j2")
    return template.render()


class TestOverridesBoilerplate:
    """INFRA-125: .pairmode-overrides.j2 uses parser-correct section-key format."""

    def setup_method(self):
        self.rendered = render_overrides_template()

    def test_rendered_contains_parser_correct_example(self):
        """Rendered boilerplate must contain the ##-prefixed example key."""
        assert "CLAUDE.md:## review checklist" in self.rendered

    def test_example_entries_ignored_as_comments_by_load_overrides(self, tmp_path):
        """Comment lines in the rendered boilerplate are correctly ignored by _load_overrides."""
        overrides_path = tmp_path / ".pairmode-overrides"
        overrides_path.write_text(self.rendered, encoding="utf-8")

        result = _load_overrides(tmp_path)

        # All lines in the boilerplate start with # — no non-comment data lines
        # so the result must be an empty set (examples are well-formed comments).
        assert result == set(), (
            f"Expected _load_overrides to return an empty set (all lines are comments), "
            f"but got: {result!r}"
        )
