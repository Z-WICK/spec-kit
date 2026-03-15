from pathlib import Path

from specify_cli.fork_customizations import (
    FORK_COMMAND_NAMES,
    build_enhancement_panel_lines,
    build_next_steps_lines,
    find_command_template,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_fork_only_command_templates_are_isolated_from_core_dir():
    core_dir = REPO_ROOT / "templates" / "commands"
    fork_dir = REPO_ROOT / "templates" / "fork-commands"

    for command_name in FORK_COMMAND_NAMES:
        assert not (core_dir / f"{command_name}.md").exists()
        assert (fork_dir / f"{command_name}.md").exists()


def test_find_command_template_resolves_core_and_fork_sources():
    assert find_command_template(REPO_ROOT, "specify") == (
        REPO_ROOT / "templates" / "commands" / "specify.md"
    )
    assert find_command_template(REPO_ROOT, "pipeline") == (
        REPO_ROOT / "templates" / "fork-commands" / "pipeline.md"
    )


def test_codex_next_steps_and_enhancements_are_config_driven():
    steps_lines = build_next_steps_lines(selected_ai="codex", here=False, project_name="demo")
    enhancement_lines = build_enhancement_panel_lines(selected_ai="codex")

    assert any(".agents/skills/<skill>/SKILL.md" in line for line in steps_lines)
    assert any("Legacy .codex/skills remains supported for compatibility." in line for line in steps_lines)
    assert any("$speckit-init" in line for line in enhancement_lines)
    assert any("$speckit-pipeline" in line for line in enhancement_lines)
