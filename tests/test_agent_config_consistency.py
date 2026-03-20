"""Consistency checks for agent configuration across runtime and packaging scripts."""

from pathlib import Path

import yaml

from specify_cli import AGENT_CONFIG, AI_ASSISTANT_ALIASES, AI_ASSISTANT_HELP
from specify_cli.agents import (
    AGENT_COMMAND_CONFIGS,
    AGENT_CONTEXT_CONFIGS,
    AGENT_PACKAGING_CONFIGS,
    get_agent_skills_dir_relative,
)
from specify_cli.extensions import CommandRegistrar


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_agent_registry() -> dict[str, dict[str, str]]:
    registry: dict[str, dict[str, str]] = {}
    registry_file = REPO_ROOT / "scripts" / "agent-registry.txt"
    for raw_line in registry_file.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        parts = raw_line.split("|")
        registry[parts[0]] = {
            "display_name": parts[1],
            "command_dir": parts[2],
            "command_format": parts[3],
            "args_token": parts[4],
            "extension": parts[5],
            "skills_dir": parts[6],
            "context_file": parts[7],
            "context_name": parts[8],
            "context_format": parts[9],
            "package_strategy": parts[10],
            "root_copy_source": parts[11],
            "root_copy_dest": parts[12],
            "copy_agent_templates_to": parts[13],
            "legacy_mirror_dir": parts[14],
            "exclude_agent_templates": parts[15],
            "copy_vscode_settings": parts[16],
        }
    return registry


class TestAgentConfigConsistency:
    """Keep runtime config, packaging, and docs-facing surfaces aligned."""

    def test_runtime_config_uses_kiro_cli_and_removes_q(self):
        """AGENT_CONFIG should include kiro-cli and exclude legacy q."""
        assert "kiro-cli" in AGENT_CONFIG
        assert AGENT_CONFIG["kiro-cli"]["folder"] == ".kiro/"
        assert AGENT_CONFIG["kiro-cli"]["commands_subdir"] == "prompts"
        assert "q" not in AGENT_CONFIG

    def test_extension_registrar_uses_kiro_cli_and_codex_skills(self):
        """Shared registrar should expose canonical Kiro and Codex paths."""
        cfg = CommandRegistrar.AGENT_CONFIGS
        assert "kiro-cli" in cfg
        assert cfg["kiro-cli"]["dir"] == ".kiro/prompts"
        assert "codex" in cfg
        assert cfg["codex"]["dir"] == ".agents/skills"
        assert "q" not in cfg

    def test_agent_registry_matches_runtime_metadata(self):
        """Shared registry should stay aligned with runtime agent metadata."""
        registry = _load_agent_registry()

        assert set(registry) == set(AGENT_CONFIG)

        args_token_map = {
            "$ARGUMENTS": "markdown_args",
            "{{args}}": "toml_args",
        }

        for agent, row in registry.items():
            assert row["command_dir"] == AGENT_COMMAND_CONFIGS[agent]["dir"]
            assert row["command_format"] == AGENT_COMMAND_CONFIGS[agent]["format"]
            assert row["args_token"] == args_token_map[AGENT_COMMAND_CONFIGS[agent]["args"]]
            assert row["extension"] == AGENT_COMMAND_CONFIGS[agent]["extension"]
            assert row["skills_dir"] == get_agent_skills_dir_relative(agent)
            assert row["context_file"] == AGENT_CONTEXT_CONFIGS[agent]["file"]
            assert row["context_name"] == AGENT_CONTEXT_CONFIGS[agent]["name"]
            assert row["context_format"] == AGENT_CONTEXT_CONFIGS[agent]["format"]
            assert row["package_strategy"] == AGENT_PACKAGING_CONFIGS[agent]["strategy"]
            assert row["root_copy_source"] == AGENT_PACKAGING_CONFIGS[agent]["root_copy_source"]
            assert row["root_copy_dest"] == AGENT_PACKAGING_CONFIGS[agent]["root_copy_dest"]
            assert row["copy_agent_templates_to"] == AGENT_PACKAGING_CONFIGS[agent]["copy_agent_templates_to"]
            assert row["legacy_mirror_dir"] == AGENT_PACKAGING_CONFIGS[agent]["legacy_mirror_dir"]
            assert row["exclude_agent_templates"] == ("1" if AGENT_PACKAGING_CONFIGS[agent]["exclude_agent_templates"] else "0")
            assert row["copy_vscode_settings"] == ("1" if AGENT_PACKAGING_CONFIGS[agent]["copy_vscode_settings"] else "0")

    def test_release_scripts_load_shared_registry(self):
        """Bash and PowerShell release scripts should derive agents from the shared registry."""
        sh_text = (REPO_ROOT / ".github" / "workflows" / "scripts" / "create-release-packages.sh").read_text(encoding="utf-8")
        ps_text = (REPO_ROOT / ".github" / "workflows" / "scripts" / "create-release-packages.ps1").read_text(encoding="utf-8")

        assert "agent-registry.sh" in sh_text
        assert 'ALL_AGENTS=("${AGENT_REGISTRY_ORDER[@]}")' in sh_text
        assert "agent-registry.ps1" in ps_text
        assert "Get-AgentRegistry" in ps_text

    def test_release_scripts_use_expected_paths_for_agy_and_tabnine(self):
        """Registry should retain fork-specific packaging paths."""
        registry = _load_agent_registry()

        assert registry["agy"]["command_dir"] == ".agent/commands"
        assert registry["tabnine"]["command_dir"] == ".tabnine/agent/commands"
        assert registry["droid"]["legacy_mirror_dir"] == ".factory/commands"
        assert registry["kimi"]["package_strategy"] == "kimi_skill_tree"

    def test_github_release_includes_new_agent_packages(self):
        """GitHub release script should build assets from the shared registry."""
        gh_release_text = (REPO_ROOT / ".github" / "workflows" / "scripts" / "create-github-release.sh").read_text(encoding="utf-8")

        assert "agent-registry.sh" in gh_release_text
        assert 'for agent in "${AGENT_REGISTRY_ORDER[@]}"' in gh_release_text
        assert 'spec-kit-template-${agent}-${variant}-${VERSION}.zip' in gh_release_text

    def test_agent_context_scripts_cover_supported_agents(self):
        """Context update scripts should derive supported agents from the shared registry."""
        bash_text = (REPO_ROOT / "scripts" / "bash" / "update-agent-context.sh").read_text(encoding="utf-8")
        pwsh_text = (REPO_ROOT / "scripts" / "powershell" / "update-agent-context.ps1").read_text(encoding="utf-8")
        registry = _load_agent_registry()

        for token in ("kiro-cli", "tabnine", "kimi", "droid"):
            assert token in registry

        assert "agent-registry.sh" in bash_text
        assert "agent-registry.ps1" in pwsh_text

        assert "Amazon Q Developer CLI" not in bash_text
        assert "Amazon Q Developer CLI" not in pwsh_text

    def test_ai_help_includes_aliases_and_optional_agents(self):
        """CLI help text should stay in sync with runtime aliases and agent list."""
        for alias, target in AI_ASSISTANT_ALIASES.items():
            assert alias in AI_ASSISTANT_HELP
            assert target in AI_ASSISTANT_HELP

        for agent in ("roo", "tabnine", "kimi", "droid"):
            assert agent in AI_ASSISTANT_HELP

    def test_devcontainer_kiro_installer_uses_pinned_checksum(self):
        """Devcontainer installer should always verify Kiro installer via pinned SHA256."""
        post_create_text = (REPO_ROOT / ".devcontainer" / "post-create.sh").read_text(encoding="utf-8")

        assert 'KIRO_INSTALLER_SHA256="7487a65cf310b7fb59b357c4b5e6e3f3259d383f4394ecedb39acf70f307cffb"' in post_create_text
        assert "sha256sum -c -" in post_create_text
        assert "KIRO_SKIP_KIRO_INSTALLER_VERIFY" not in post_create_text

    def test_runtime_config_includes_tabnine_and_kimi(self):
        """Runtime config should expose Tabnine and Kimi with correct metadata."""
        assert AGENT_CONFIG["tabnine"]["folder"] == ".tabnine/agent/"
        assert AGENT_CONFIG["tabnine"]["commands_subdir"] == "commands"
        assert AGENT_CONFIG["tabnine"]["requires_cli"] is True

        assert AGENT_CONFIG["kimi"]["folder"] == ".kimi/"
        assert AGENT_CONFIG["kimi"]["commands_subdir"] == "skills"
        assert AGENT_CONFIG["kimi"]["requires_cli"] is True

    def test_extension_registrar_includes_tabnine_and_kimi(self):
        """Registrar should expose Tabnine TOML and Kimi skill layouts."""
        cfg = CommandRegistrar.AGENT_CONFIGS

        assert cfg["tabnine"]["dir"] == ".tabnine/agent/commands"
        assert cfg["tabnine"]["format"] == "toml"
        assert cfg["tabnine"]["args"] == "{{args}}"
        assert cfg["tabnine"]["extension"] == ".toml"

        assert cfg["kimi"]["dir"] == ".kimi/skills"
        assert cfg["kimi"]["extension"] == "/SKILL.md"

    def test_runtime_config_includes_trae_pi_and_iflow(self):
        """Runtime config should expose newly merged upstream agents."""
        assert AGENT_CONFIG["trae"]["folder"] == ".trae/"
        assert AGENT_CONFIG["trae"]["commands_subdir"] == "rules"
        assert AGENT_CONFIG["trae"]["requires_cli"] is False

        assert AGENT_CONFIG["pi"]["folder"] == ".pi/"
        assert AGENT_CONFIG["pi"]["commands_subdir"] == "prompts"
        assert AGENT_CONFIG["pi"]["requires_cli"] is True

        assert AGENT_CONFIG["iflow"]["folder"] == ".iflow/"
        assert AGENT_CONFIG["iflow"]["commands_subdir"] == "commands"
        assert AGENT_CONFIG["iflow"]["requires_cli"] is True

    def test_extension_registrar_includes_trae_pi_and_iflow(self):
        """Registrar should expose the merged upstream agent command layouts."""
        cfg = CommandRegistrar.AGENT_CONFIGS

        assert cfg["trae"]["dir"] == ".trae/rules"
        assert cfg["trae"]["extension"] == ".md"

        assert cfg["pi"]["dir"] == ".pi/prompts"
        assert cfg["pi"]["extension"] == ".md"

        assert cfg["iflow"]["dir"] == ".iflow/commands"
        assert cfg["iflow"]["extension"] == ".md"

    def test_release_trigger_workflow_falls_back_when_release_pat_is_missing(self):
        """Release trigger should not hard-require RELEASE_PAT just to start."""
        workflow_text = (REPO_ROOT / ".github" / "workflows" / "release-trigger.yml").read_text(encoding="utf-8")

        assert "steps.release_token.outputs.token" in workflow_text
        assert "secrets.RELEASE_PAT" in workflow_text
        assert "github.token" in workflow_text
        assert "token: ${{ secrets.RELEASE_PAT }}" not in workflow_text
        assert "GITHUB_TOKEN: ${{ secrets.RELEASE_PAT }}" not in workflow_text

    def test_release_trigger_dispatches_release_when_using_github_token_fallback(self):
        """Release trigger should explicitly start the release workflow on fallback token flow."""
        workflow_text = (REPO_ROOT / ".github" / "workflows" / "release-trigger.yml").read_text(encoding="utf-8")

        assert "actions: write" in workflow_text
        assert "if: steps.release_token.outputs.source == 'github_token'" in workflow_text
        assert "gh workflow run release.yml" in workflow_text
        assert "tag=${{ steps.version.outputs.tag }}" in workflow_text

    def test_release_workflow_supports_manual_dispatch_with_tag_input(self):
        """Create Release should support workflow_dispatch so Release Trigger can invoke it directly."""
        workflow_text = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        workflow = yaml.load(workflow_text, Loader=yaml.BaseLoader)

        assert "workflow_dispatch" in workflow["on"]
        assert workflow["on"]["workflow_dispatch"]["inputs"]["tag"]["required"] == "true"
        assert "ref: ${{ github.event.inputs.tag || github.ref }}" in workflow_text
        assert "INPUT_TAG: ${{ github.event.inputs.tag }}" in workflow_text
