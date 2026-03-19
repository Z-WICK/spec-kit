"""Regression tests for enhanced command and release consistency."""

import shutil
from pathlib import Path

import yaml
import pytest

from specify_cli.agents import AGENT_CONFIG, AGENT_COMMAND_CONFIGS
from specify_cli.command_lint import lint_repository
from specify_cli.extensions import CommandRegistrar
from specify_cli.fork_customizations import find_command_template


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_agent_keys_are_consistent_across_modules():
    """Agent keys should stay aligned between CLI and extension registration."""
    cli_keys = set(AGENT_CONFIG.keys())
    command_keys = set(AGENT_COMMAND_CONFIGS.keys())
    registrar_keys = set(CommandRegistrar.AGENT_CONFIGS.keys())

    assert cli_keys == command_keys == registrar_keys


def test_enhanced_agent_directories_follow_conventions():
    """High-variance agent directory conventions should not regress."""
    assert AGENT_COMMAND_CONFIGS["cursor-agent"]["dir"] == ".cursor/commands"
    assert AGENT_COMMAND_CONFIGS["codex"]["dir"] == ".agents/skills"
    assert AGENT_COMMAND_CONFIGS["kilocode"]["dir"] == ".kilocode/rules"
    assert AGENT_COMMAND_CONFIGS["auggie"]["dir"] == ".augment/rules"
    assert AGENT_COMMAND_CONFIGS["roo"]["dir"] == ".roo/rules"
    assert AGENT_COMMAND_CONFIGS["droid"]["dir"] == ".factory/skills"
    assert AGENT_COMMAND_CONFIGS["agy"]["dir"] == ".agent/commands"


def test_codex_init_guidance_uses_skills_workflow():
    """Codex onboarding text should stay aligned with /skills + $skill usage."""
    cli_source = (REPO_ROOT / "src" / "specify_cli" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "from .fork_customizations import" in cli_source
    assert "build_next_steps_lines" in cli_source
    assert "build_enhancement_panel_lines" in cli_source
    assert "Legacy .codex/skills remains supported for compatibility." not in cli_source
    assert 'enhancement_prefix = "$speckit-" if selected_ai == "codex"' not in cli_source


def test_repository_command_lint_passes():
    """Lint checks should catch command/release drift before shipping."""
    result = lint_repository(REPO_ROOT)
    assert result.errors == [], "\n".join(result.errors)


def test_specify_template_validation_flow_does_not_loop():
    """Specify command should advance to step 7 after validation passes."""
    specify_template = (REPO_ROOT / "templates" / "commands" / "specify.md").read_text(
        encoding="utf-8"
    )
    assert "proceed to step 7" in specify_template
    assert "proceed to step 6" not in specify_template


def test_pipeline_template_excludes_extension_hooks():
    """Pipeline template remains agent-agnostic; Claude hooks live in plugin config."""
    pipeline_template = find_command_template(REPO_ROOT, "pipeline").read_text(encoding="utf-8")
    assert "hooks.before_tasks" not in pipeline_template
    assert "hooks.after_tasks" not in pipeline_template
    assert "hooks.before_implement" not in pipeline_template
    assert "hooks.after_implement" not in pipeline_template


def test_pipeline_template_allows_flexible_input():
    """Pipeline input parsing should accept common description aliases."""
    pipeline_template = find_command_template(REPO_ROOT, "pipeline").read_text(encoding="utf-8")
    assert "需求:" in pipeline_template
    assert "Feature description" in pipeline_template
    assert "描述:" in pipeline_template


@pytest.mark.parametrize("command_name", ["pipeline", "fixbug"])
@pytest.mark.parametrize(
    ("injected_text", "expected_marker"),
    [
        (".claude/commands/speckit.plan.md", "agent-specific path '.claude/commands'"),
        ("hooks.before_tasks", "command-level hook marker 'hooks.before_tasks'"),
    ],
)
def test_repository_lint_rejects_agent_specific_leaks_in_agent_agnostic_fork_templates(
    tmp_path: Path, command_name: str, injected_text: str, expected_marker: str
):
    """Agent-agnostic fork templates should not bake in agent storage or hook wiring."""
    fixture_root = tmp_path / "fixture-repo"
    fixture_root.mkdir()

    for rel in (".github", "memory", "scripts", "src", "templates"):
        shutil.copytree(REPO_ROOT / rel, fixture_root / rel)

    target = fixture_root / "templates" / "fork-commands" / f"{command_name}.md"
    target.write_text(
        target.read_text(encoding="utf-8") + f"\n\nInjected regression marker: {injected_text}\n",
        encoding="utf-8",
    )

    result = lint_repository(fixture_root)

    expected_error = (
        f"templates/fork-commands/{command_name}.md: agent-agnostic fork template "
        f"must not reference {expected_marker}"
    )
    assert expected_error in result.errors


def test_pipeline_readme_documents_agent_agnostic_hook_boundary():
    """README should explain that pipeline is shared across CLIs but not hook-equivalent."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "shared pipeline template is agent-agnostic" in readme
    assert ".specify/extensions.yml" in readme
    assert "Codex" in readme


def test_update_agent_context_scripts_support_droid_agent():
    """Droid must be accepted by both bash and PowerShell context update scripts."""
    bash_script = (REPO_ROOT / "scripts" / "bash" / "update-agent-context.sh").read_text(
        encoding="utf-8"
    )
    registry = (REPO_ROOT / "scripts" / "agent-registry.txt").read_text(encoding="utf-8")
    ps_script = (
        REPO_ROOT / "scripts" / "powershell" / "update-agent-context.ps1"
    ).read_text(encoding="utf-8")

    assert "droid|Factory Droid|" in registry
    assert "agent-registry.sh" in bash_script
    assert "agent-registry.ps1" in ps_script


def test_find_placeholders_scripts_are_not_claude_hardcoded():
    """Placeholder scanners should target a caller-provided agent directory."""
    bash_script = (REPO_ROOT / "scripts" / "bash" / "find-placeholders.sh").read_text(
        encoding="utf-8"
    )
    ps_script = (
        REPO_ROOT / "scripts" / "powershell" / "find-placeholders.ps1"
    ).read_text(encoding="utf-8")
    init_template = find_command_template(REPO_ROOT, "init").read_text(encoding="utf-8")

    assert ".claude" not in bash_script
    assert ".claude" not in ps_script
    assert "{SCRIPT} \"<AGENT_DIR>\"" in init_template


def test_agent_templates_require_name_and_description_frontmatter():
    """All packaged agent templates must carry required frontmatter fields."""
    agents_dir = REPO_ROOT / "templates" / "agents"
    for agent_file in sorted(agents_dir.glob("*.md")):
        text = agent_file.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{agent_file} must start with frontmatter"
        parts = text.split("---", 2)
        assert len(parts) >= 3, f"{agent_file} has malformed frontmatter"
        frontmatter = yaml.safe_load(parts[1]) or {}
        assert isinstance(frontmatter.get("name"), str) and frontmatter["name"].strip()
        assert isinstance(frontmatter.get("description"), str) and frontmatter[
            "description"
        ].strip()
