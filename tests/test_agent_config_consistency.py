"""Consistency checks for agent configuration across runtime and packaging scripts."""

import re
from pathlib import Path

from specify_cli import AGENT_CONFIG, AI_ASSISTANT_ALIASES, AI_ASSISTANT_HELP
from specify_cli.extensions import CommandRegistrar


REPO_ROOT = Path(__file__).resolve().parent.parent


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

    def test_release_agent_lists_include_expected_union(self):
        """Bash and PowerShell release scripts should agree on supported agents."""
        sh_text = (REPO_ROOT / ".github" / "workflows" / "scripts" / "create-release-packages.sh").read_text(encoding="utf-8")
        ps_text = (REPO_ROOT / ".github" / "workflows" / "scripts" / "create-release-packages.ps1").read_text(encoding="utf-8")

        sh_match = re.search(r"ALL_AGENTS=\(([^)]*)\)", sh_text)
        assert sh_match is not None
        sh_agents = sh_match.group(1).split()

        ps_match = re.search(r"\$AllAgents = @\(([^)]*)\)", ps_text)
        assert ps_match is not None
        ps_agents = re.findall(r"'([^']+)'", ps_match.group(1))

        for agent in ("kiro-cli", "shai", "tabnine", "agy", "droid", "kimi"):
            assert agent in sh_agents
            assert agent in ps_agents

        assert "q" not in sh_agents
        assert "q" not in ps_agents

    def test_release_scripts_use_expected_paths_for_agy_and_tabnine(self):
        """Packaging scripts should emit current agent-specific directories."""
        sh_text = (REPO_ROOT / ".github" / "workflows" / "scripts" / "create-release-packages.sh").read_text(encoding="utf-8")
        ps_text = (REPO_ROOT / ".github" / "workflows" / "scripts" / "create-release-packages.ps1").read_text(encoding="utf-8")

        assert re.search(r"agy\)\s*\n.*?\.agent/commands", sh_text, re.S) is not None
        assert re.search(r"'agy'\s*\{.*?\.agent/commands", ps_text, re.S) is not None
        assert ".tabnine/agent/commands" in sh_text
        assert ".tabnine/agent/commands" in ps_text

    def test_github_release_includes_new_agent_packages(self):
        """GitHub release script should include all fork-supported extra packages."""
        gh_release_text = (REPO_ROOT / ".github" / "workflows" / "scripts" / "create-github-release.sh").read_text(encoding="utf-8")

        for fragment in (
            "spec-kit-template-kiro-cli-sh-",
            "spec-kit-template-tabnine-sh-",
            "spec-kit-template-droid-sh-",
            "spec-kit-template-kimi-sh-",
        ):
            assert fragment in gh_release_text

        assert "spec-kit-template-q-sh-" not in gh_release_text
        assert "spec-kit-template-q-ps-" not in gh_release_text

    def test_agent_context_scripts_cover_supported_agents(self):
        """Agent context update scripts should support current fork-only agents."""
        bash_text = (REPO_ROOT / "scripts" / "bash" / "update-agent-context.sh").read_text(encoding="utf-8")
        pwsh_text = (REPO_ROOT / "scripts" / "powershell" / "update-agent-context.ps1").read_text(encoding="utf-8")

        for token in ("kiro-cli", "tabnine", "kimi", "droid"):
            assert token in bash_text
            assert token in pwsh_text

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
