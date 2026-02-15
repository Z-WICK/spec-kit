"""Regression tests for enhanced command and release consistency."""

from pathlib import Path

from specify_cli.agents import AGENT_CONFIG, AGENT_COMMAND_CONFIGS
from specify_cli.command_lint import lint_repository
from specify_cli.extensions import CommandRegistrar


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
    assert AGENT_COMMAND_CONFIGS["codex"]["dir"] == ".codex/skills"
    assert AGENT_COMMAND_CONFIGS["kilocode"]["dir"] == ".kilocode/rules"
    assert AGENT_COMMAND_CONFIGS["auggie"]["dir"] == ".augment/rules"
    assert AGENT_COMMAND_CONFIGS["roo"]["dir"] == ".roo/rules"
    assert AGENT_COMMAND_CONFIGS["droid"]["dir"] == ".factory/commands"
    assert AGENT_COMMAND_CONFIGS["agy"]["dir"] == ".agent/workflows"


def test_repository_command_lint_passes():
    """Lint checks should catch command/release drift before shipping."""
    result = lint_repository(REPO_ROOT)
    assert result.errors == [], "\n".join(result.errors)
