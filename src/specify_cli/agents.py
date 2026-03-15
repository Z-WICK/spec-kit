"""Shared AI agent metadata and command registration helpers."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List

import yaml


DEFAULT_SKILLS_DIR = ".agents/skills"


BASE_AGENT_METADATA: Dict[str, Dict[str, Any]] = {
    "copilot": {
        "name": "GitHub Copilot",
        "folder": ".github/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".github/agents",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".agent.md",
    },
    "claude": {
        "name": "Claude Code",
        "folder": ".claude/",
        "install_url": "https://docs.anthropic.com/en/docs/claude-code/setup",
        "requires_cli": True,
        "command_dir": ".claude/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "gemini": {
        "name": "Gemini CLI",
        "folder": ".gemini/",
        "install_url": "https://github.com/google-gemini/gemini-cli",
        "requires_cli": True,
        "command_dir": ".gemini/commands",
        "command_format": "toml",
        "args": "{{args}}",
        "extension": ".toml",
    },
    "cursor-agent": {
        "name": "Cursor",
        "folder": ".cursor/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".cursor/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "qwen": {
        "name": "Qwen Code",
        "folder": ".qwen/",
        "install_url": "https://github.com/QwenLM/qwen-code",
        "requires_cli": True,
        "command_dir": ".qwen/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "opencode": {
        "name": "opencode",
        "folder": ".opencode/",
        "install_url": "https://opencode.ai",
        "requires_cli": True,
        "command_dir": ".opencode/command",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "codex": {
        "name": "Codex CLI",
        "folder": ".agents/",
        "install_url": "https://github.com/openai/codex",
        "requires_cli": True,
        "command_dir": ".agents/skills",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": "/SKILL.md",
    },
    "windsurf": {
        "name": "Windsurf",
        "folder": ".windsurf/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".windsurf/workflows",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "kilocode": {
        "name": "Kilo Code",
        "folder": ".kilocode/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".kilocode/rules",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "auggie": {
        "name": "Auggie CLI",
        "folder": ".augment/",
        "install_url": "https://docs.augmentcode.com/cli/setup-auggie/install-auggie-cli",
        "requires_cli": True,
        "command_dir": ".augment/rules",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "roo": {
        "name": "Roo Code",
        "folder": ".roo/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".roo/rules",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "codebuddy": {
        "name": "CodeBuddy",
        "folder": ".codebuddy/",
        "install_url": "https://www.codebuddy.ai/cli",
        "requires_cli": True,
        "command_dir": ".codebuddy/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "qodercli": {
        "name": "Qoder CLI",
        "folder": ".qoder/",
        "install_url": "https://qoder.com/cli",
        "requires_cli": True,
        "command_dir": ".qoder/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "amp": {
        "name": "Amp",
        "folder": ".agents/",
        "install_url": "https://ampcode.com/manual#install",
        "requires_cli": True,
        "command_dir": ".agents/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "shai": {
        "name": "SHAI",
        "folder": ".shai/",
        "install_url": "https://github.com/ovh/shai",
        "requires_cli": True,
        "command_dir": ".shai/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "tabnine": {
        "name": "Tabnine CLI",
        "folder": ".tabnine/agent/",
        "install_url": "https://docs.tabnine.com/main/getting-started/tabnine-cli",
        "requires_cli": True,
        "command_dir": ".tabnine/agent/commands",
        "command_format": "toml",
        "args": "{{args}}",
        "extension": ".toml",
    },
    "kiro-cli": {
        "name": "Kiro CLI",
        "folder": ".kiro/",
        "install_url": "https://kiro.dev/docs/cli/",
        "requires_cli": True,
        "command_dir": ".kiro/prompts",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "agy": {
        "name": "Antigravity",
        "folder": ".agent/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".agent/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "bob": {
        "name": "IBM Bob",
        "folder": ".bob/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".bob/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "droid": {
        "name": "Factory Droid",
        "folder": ".factory/",
        "install_url": "https://docs.factory.ai/cli/getting-started/quickstart",
        "requires_cli": True,
        "command_dir": ".factory/skills",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "vibe": {
        "name": "Mistral Vibe",
        "folder": ".vibe/",
        "install_url": "https://github.com/mistralai/mistral-vibe",
        "requires_cli": True,
        "command_dir": ".vibe/prompts",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
    "kimi": {
        "name": "Kimi Code",
        "folder": ".kimi/",
        "install_url": "https://code.kimi.com/",
        "requires_cli": True,
        "command_dir": ".kimi/skills",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": "/SKILL.md",
    },
    "generic": {
        "name": "Generic (bring your own agent)",
        "folder": None,
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".speckit/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
}


LOCAL_AGENT_METADATA_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "copilot": {
        "context_file": ".github/agents/copilot-instructions.md",
        "context_name": "GitHub Copilot",
        "packaging_strategy": "copilot_agent",
        "copy_vscode_settings": True,
    },
    "claude": {
        "context_file": "CLAUDE.md",
        "context_name": "Claude Code",
        "copy_agent_templates_to": ".claude/agents",
    },
    "gemini": {
        "context_file": "GEMINI.md",
        "context_name": "Gemini CLI",
        "root_copy_source": "agent_templates/gemini/GEMINI.md",
        "root_copy_dest": "GEMINI.md",
    },
    "cursor-agent": {
        "context_file": ".cursor/rules/specify-rules.mdc",
        "context_name": "Cursor IDE",
        "context_format": "mdc",
    },
    "qwen": {
        "context_file": "QWEN.md",
        "context_name": "Qwen Code",
        "root_copy_source": "agent_templates/qwen/QWEN.md",
        "root_copy_dest": "QWEN.md",
    },
    "opencode": {
        "context_file": "AGENTS.md",
        "context_name": "opencode",
    },
    "codex": {
        "skills_dir": ".agents/skills",
        "skill_name_style": "hyphen",
        "skill_file_mode": "normalized",
        "context_file": "AGENTS.md",
        "context_name": "Codex CLI",
        "packaging_strategy": "codex_skill_tree",
        "exclude_agent_templates": True,
    },
    "windsurf": {
        "context_file": ".windsurf/rules/specify-rules.md",
        "context_name": "Windsurf",
    },
    "kilocode": {
        "context_file": ".kilocode/rules/specify-rules.md",
        "context_name": "Kilo Code",
    },
    "auggie": {
        "context_file": ".augment/rules/specify-rules.md",
        "context_name": "Auggie CLI",
    },
    "roo": {
        "context_file": ".roo/rules/specify-rules.md",
        "context_name": "Roo Code",
    },
    "codebuddy": {
        "context_file": "CODEBUDDY.md",
        "context_name": "CodeBuddy CLI",
    },
    "qodercli": {
        "context_file": "QODER.md",
        "context_name": "Qoder CLI",
    },
    "amp": {
        "context_file": "AGENTS.md",
        "context_name": "Amp",
    },
    "shai": {
        "context_file": "SHAI.md",
        "context_name": "SHAI",
    },
    "tabnine": {
        "context_file": "TABNINE.md",
        "context_name": "Tabnine CLI",
        "root_copy_source": "agent_templates/tabnine/TABNINE.md",
        "root_copy_dest": "TABNINE.md",
    },
    "kiro-cli": {
        "context_file": "AGENTS.md",
        "context_name": "Kiro CLI",
    },
    "agy": {
        "context_file": ".agent/rules/specify-rules.md",
        "context_name": "Antigravity",
    },
    "bob": {
        "context_file": "AGENTS.md",
        "context_name": "IBM Bob",
    },
    "droid": {
        "context_file": ".factory/rules/specify-rules.md",
        "context_name": "Factory Droid",
        "copy_agent_templates_to": ".factory/droids",
        "legacy_mirror_dir": ".factory/commands",
    },
    "vibe": {
        "context_file": ".vibe/agents/specify-agents.md",
        "context_name": "Mistral Vibe",
    },
    "kimi": {
        "skill_name_style": "dot",
        "skill_file_mode": "literal",
        "context_file": "KIMI.md",
        "context_name": "Kimi Code",
        "packaging_strategy": "kimi_skill_tree",
    },
    "generic": {
        "context_name": "Generic",
    },
}


LEGACY_AGENT_ALIASES: Dict[str, str] = {
    "cursor": "cursor-agent",
    "kiro": "kiro-cli",
    "qoder": "qodercli",
}


def _merge_agent_metadata(
    base_metadata: Dict[str, Dict[str, Any]],
    overlays: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for agent, metadata in base_metadata.items():
        merged[agent] = dict(metadata)
        merged[agent].update(overlays.get(agent, {}))
    return merged


def _default_skills_dir(folder: str | None) -> str:
    if folder:
        return f"{folder.rstrip('/')}/skills"
    return DEFAULT_SKILLS_DIR


def _normalize_agent_metadata(
    metadata: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for agent, config in metadata.items():
        row = dict(config)
        row.setdefault("skills_dir", _default_skills_dir(row.get("folder")))
        row.setdefault("skill_name_style", "hyphen")
        row.setdefault("skill_file_mode", "none")
        row.setdefault("context_name", row["name"])
        row.setdefault("context_file", "")
        row.setdefault("context_format", "plain")
        row.setdefault("packaging_strategy", "standard_commands")
        row.setdefault("root_copy_source", "")
        row.setdefault("root_copy_dest", "")
        row.setdefault("copy_agent_templates_to", "")
        row.setdefault("legacy_mirror_dir", "")
        row.setdefault("exclude_agent_templates", False)
        row.setdefault("copy_vscode_settings", False)
        normalized[agent] = row
    return normalized


AGENT_METADATA: Dict[str, Dict[str, Any]] = _normalize_agent_metadata(
    _merge_agent_metadata(BASE_AGENT_METADATA, LOCAL_AGENT_METADATA_OVERRIDES)
)


def resolve_agent_name(agent_name: str) -> str:
    """Resolve a legacy alias to its canonical agent key."""
    return LEGACY_AGENT_ALIASES.get(agent_name, agent_name)


def get_agent_metadata(agent_name: str) -> Dict[str, Any]:
    """Return canonical metadata for the given agent key or alias."""
    return AGENT_METADATA[resolve_agent_name(agent_name)]


def get_agent_skills_dir_relative(agent_name: str) -> str:
    """Return the project-relative skills directory for the agent."""
    resolved = resolve_agent_name(agent_name)
    if resolved not in AGENT_METADATA:
        return DEFAULT_SKILLS_DIR
    return str(AGENT_METADATA[resolved]["skills_dir"])


def get_agent_skill_name_style(agent_name: str) -> str:
    """Return the skill naming style used by the agent."""
    resolved = resolve_agent_name(agent_name)
    if resolved not in AGENT_METADATA:
        return "hyphen"
    return str(AGENT_METADATA[resolved]["skill_name_style"])


def build_skill_name(agent_name: str, command_name: str) -> str:
    """Build the visible skill name for the given agent and command."""
    style = get_agent_skill_name_style(agent_name)
    if style == "dot":
        return command_name if command_name.startswith("speckit.") else f"speckit.{command_name}"
    return command_name if command_name.startswith("speckit-") else f"speckit-{command_name}"


AGENT_CONFIG: Dict[str, Dict[str, Any]] = {
    key: {
        "name": value["name"],
        "folder": value["folder"],
        "install_url": value["install_url"],
        "requires_cli": value["requires_cli"],
        "commands_subdir": value["command_dir"].rsplit("/", 1)[-1],
    }
    for key, value in AGENT_METADATA.items()
}


AGENT_COMMAND_CONFIGS: Dict[str, Dict[str, Any]] = {
    key: {
        "dir": value["command_dir"],
        "format": value["command_format"],
        "args": value["args"],
        "extension": value["extension"],
        "skill_name_style": value["skill_name_style"],
        "skill_file_mode": value["skill_file_mode"],
    }
    for key, value in AGENT_METADATA.items()
}


AGENT_CONTEXT_CONFIGS: Dict[str, Dict[str, str]] = {
    key: {
        "file": str(value["context_file"]),
        "name": str(value["context_name"]),
        "format": str(value["context_format"]),
    }
    for key, value in AGENT_METADATA.items()
}


AGENT_PACKAGING_CONFIGS: Dict[str, Dict[str, Any]] = {
    key: {
        "dir": value["command_dir"],
        "format": value["command_format"],
        "args": value["args"],
        "extension": value["extension"],
        "strategy": value["packaging_strategy"],
        "root_copy_source": str(value["root_copy_source"]),
        "root_copy_dest": str(value["root_copy_dest"]),
        "copy_agent_templates_to": str(value["copy_agent_templates_to"]),
        "legacy_mirror_dir": str(value["legacy_mirror_dir"]),
        "exclude_agent_templates": bool(value["exclude_agent_templates"]),
        "copy_vscode_settings": bool(value["copy_vscode_settings"]),
    }
    for key, value in AGENT_METADATA.items()
}


class CommandRegistrar:
    """Handles registration of commands with AI agents."""

    AGENT_CONFIGS = AGENT_COMMAND_CONFIGS

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from Markdown content."""
        if not content.startswith("---"):
            return {}, content

        end_marker = content.find("---", 3)
        if end_marker == -1:
            return {}, content

        frontmatter_str = content[3:end_marker].strip()
        body = content[end_marker + 3 :].strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            frontmatter = {}

        return frontmatter, body

    @staticmethod
    def render_frontmatter(frontmatter: dict) -> str:
        """Render a frontmatter dictionary as YAML."""
        if not frontmatter:
            return ""

        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_str}---\n"

    def _adjust_script_paths(self, frontmatter: dict) -> dict:
        """Adjust script paths from extension-relative to repo-relative."""
        if "scripts" not in frontmatter:
            return frontmatter

        updated = dict(frontmatter)
        updated_scripts = dict(updated["scripts"])
        for key, script_path in updated_scripts.items():
            if script_path.startswith("../../scripts/"):
                updated_scripts[key] = f".specify/scripts/{script_path[14:]}"
        updated["scripts"] = updated_scripts
        return updated

    def render_markdown_command(
        self,
        frontmatter: dict,
        body: str,
        source_id: str,
        context_note: str | None = None,
    ) -> str:
        """Render a Markdown command file."""
        if context_note is None:
            context_note = f"\n<!-- Source: {source_id} -->\n"
        return self.render_frontmatter(frontmatter) + "\n" + context_note + body

    def render_toml_command(self, frontmatter: dict, body: str, source_id: str) -> str:
        """Render a TOML command file."""
        toml_lines: list[str] = []

        if "description" in frontmatter:
            desc = str(frontmatter["description"]).replace('"', '\\"')
            toml_lines.append(f'description = "{desc}"')
            toml_lines.append("")

        toml_lines.append(f"# Source: {source_id}")
        toml_lines.append("")
        toml_lines.append('prompt = """')
        toml_lines.append(body)
        toml_lines.append('"""')
        return "\n".join(toml_lines)

    @staticmethod
    def codex_skill_name(command_name: str) -> str:
        """Convert a command name to a normalized skill directory name."""
        normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", command_name).strip("-").lower()
        return normalized or "skill"

    def _render_skill_command(
        self,
        skill_name: str,
        description: str,
        body: str,
        source_id: str,
        context_note: str | None = None,
    ) -> str:
        """Render a skill payload with minimal frontmatter."""
        if context_note is None:
            context_note = f"\n<!-- Source: {source_id} -->\n"
        skill_frontmatter = {
            "name": skill_name,
            "description": description or f"Skill for {skill_name}",
        }
        return self.render_frontmatter(skill_frontmatter) + "\n" + context_note + body

    @staticmethod
    def _convert_argument_placeholder(content: str, from_placeholder: str, to_placeholder: str) -> str:
        """Convert argument placeholder format."""
        return content.replace(from_placeholder, to_placeholder)

    def _skill_file_path(self, agent_name: str, commands_dir: Path, command_name: str) -> Path | None:
        """Return the skill file path for skill-based agents."""
        agent_config = self.AGENT_CONFIGS[agent_name]
        mode = agent_config.get("skill_file_mode", "none")
        if mode == "normalized":
            return commands_dir / self.codex_skill_name(command_name) / "SKILL.md"
        if mode == "literal":
            return commands_dir / command_name / "SKILL.md"
        return None

    def _skill_output_name(self, agent_name: str, command_name: str) -> str:
        """Return the skill name written into SKILL.md frontmatter."""
        agent_config = self.AGENT_CONFIGS[agent_name]
        mode = agent_config.get("skill_file_mode", "none")
        if mode == "normalized":
            return self.codex_skill_name(command_name)
        return command_name

    def register_commands(
        self,
        agent_name: str,
        commands: List[Dict[str, Any]],
        source_id: str,
        source_dir: Path,
        project_root: Path,
        context_note: str | None = None,
    ) -> List[str]:
        """Register commands for a specific agent."""
        resolved_agent = resolve_agent_name(agent_name)
        if resolved_agent not in self.AGENT_CONFIGS:
            raise ValueError(f"Unsupported agent: {agent_name}")

        agent_config = self.AGENT_CONFIGS[resolved_agent]
        commands_dir = project_root / agent_config["dir"]
        commands_dir.mkdir(parents=True, exist_ok=True)

        registered: list[str] = []

        for cmd_info in commands:
            cmd_name = cmd_info["name"]
            cmd_file = cmd_info["file"]

            source_file = source_dir / cmd_file
            if not source_file.exists():
                continue

            content = source_file.read_text(encoding="utf-8")
            frontmatter, body = self.parse_frontmatter(content)
            frontmatter = self._adjust_script_paths(frontmatter)
            body = self._convert_argument_placeholder(body, "$ARGUMENTS", agent_config["args"])
            description = str(frontmatter.get("description", "")).strip()

            dest_file = self._skill_file_path(resolved_agent, commands_dir, cmd_name)
            if dest_file is not None:
                output = self._render_skill_command(
                    self._skill_output_name(resolved_agent, cmd_name),
                    description,
                    body,
                    source_id,
                    context_note=context_note,
                )
            elif agent_config["format"] == "markdown":
                output = self.render_markdown_command(frontmatter, body, source_id, context_note)
                dest_file = commands_dir / f"{cmd_name}{agent_config['extension']}"
            elif agent_config["format"] == "toml":
                output = self.render_toml_command(frontmatter, body, source_id)
                dest_file = commands_dir / f"{cmd_name}{agent_config['extension']}"
            else:
                raise ValueError(f"Unsupported format: {agent_config['format']}")

            dest_file.parent.mkdir(parents=True, exist_ok=True)
            dest_file.write_text(output, encoding="utf-8")

            if resolved_agent == "copilot":
                self.write_copilot_prompt(project_root, cmd_name)

            registered.append(cmd_name)

            for alias in cmd_info.get("aliases", []):
                alias_file = self._skill_file_path(resolved_agent, commands_dir, alias)
                if alias_file is not None:
                    alias_output = self._render_skill_command(
                        self._skill_output_name(resolved_agent, alias),
                        description,
                        body,
                        source_id,
                        context_note=context_note,
                    )
                else:
                    alias_output = output
                    alias_file = commands_dir / f"{alias}{agent_config['extension']}"

                alias_file.parent.mkdir(parents=True, exist_ok=True)
                alias_file.write_text(alias_output, encoding="utf-8")

                if resolved_agent == "copilot":
                    self.write_copilot_prompt(project_root, alias)

                registered.append(alias)

        return registered

    @staticmethod
    def write_copilot_prompt(project_root: Path, cmd_name: str) -> None:
        """Generate a companion .prompt.md file for a Copilot agent command."""
        prompts_dir = project_root / ".github" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = prompts_dir / f"{cmd_name}.prompt.md"
        prompt_file.write_text(f"---\nagent: {cmd_name}\n---\n", encoding="utf-8")

    def register_commands_for_all_agents(
        self,
        commands: List[Dict[str, Any]],
        source_id: str,
        source_dir: Path,
        project_root: Path,
        context_note: str | None = None,
    ) -> Dict[str, List[str]]:
        """Register commands for all detected agents in the project."""
        results: dict[str, list[str]] = {}

        for agent_name, agent_config in self.AGENT_CONFIGS.items():
            agent_dir = project_root / agent_config["dir"].split("/")[0]
            if not agent_dir.exists():
                continue

            try:
                registered = self.register_commands(
                    agent_name,
                    commands,
                    source_id,
                    source_dir,
                    project_root,
                    context_note=context_note,
                )
            except ValueError:
                continue

            if registered:
                results[agent_name] = registered

        return results

    def unregister_commands(self, registered_commands: Dict[str, List[str]], project_root: Path) -> None:
        """Remove previously registered command files from agent directories."""
        for agent_name, cmd_names in registered_commands.items():
            resolved_agent = resolve_agent_name(agent_name)
            if resolved_agent not in self.AGENT_CONFIGS:
                continue

            agent_config = self.AGENT_CONFIGS[resolved_agent]
            commands_dir = project_root / agent_config["dir"]

            for cmd_name in cmd_names:
                cmd_file = self._skill_file_path(resolved_agent, commands_dir, cmd_name)
                if cmd_file is None:
                    cmd_file = commands_dir / f"{cmd_name}{agent_config['extension']}"

                if cmd_file.exists():
                    cmd_file.unlink()

                if agent_config.get("skill_file_mode", "none") != "none":
                    skill_dir = cmd_file.parent
                    if skill_dir.is_dir() and not any(skill_dir.iterdir()):
                        skill_dir.rmdir()

                if resolved_agent == "copilot":
                    prompt_file = project_root / ".github" / "prompts" / f"{cmd_name}.prompt.md"
                    if prompt_file.exists():
                        prompt_file.unlink()
