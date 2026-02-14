"""Shared AI agent metadata for Specify CLI.

This module is the single source of truth for:
- CLI-facing agent metadata (`AGENT_CONFIG`)
- command registration metadata used by extensions (`AGENT_COMMAND_CONFIGS`)
"""

from __future__ import annotations

from typing import Any, Dict


AGENT_METADATA: Dict[str, Dict[str, Any]] = {
    "copilot": {
        "name": "GitHub Copilot",
        "folder": ".github/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".github/agents",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
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
        "command_format": "toml",
        "args": "{{args}}",
        "extension": ".toml",
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
        "folder": ".codex/",
        "install_url": "https://github.com/openai/codex",
        "requires_cli": True,
        "command_dir": ".codex/prompts",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
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
    "qoder": {
        "name": "Qoder CLI",
        "folder": ".qoder/",
        "install_url": "https://qoder.com/cli",
        "requires_cli": True,
        "command_dir": ".qoder/commands",
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
    "q": {
        "name": "Amazon Q Developer CLI",
        "folder": ".amazonq/",
        "install_url": "https://aws.amazon.com/developer/learning/q-developer-cli/",
        "requires_cli": True,
        "command_dir": ".amazonq/prompts",
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
    "agy": {
        "name": "Antigravity",
        "folder": ".agent/",
        "install_url": None,
        "requires_cli": False,
        "command_dir": ".agent/workflows",
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
        "command_dir": ".factory/commands",
        "command_format": "markdown",
        "args": "$ARGUMENTS",
        "extension": ".md",
    },
}

# Backward-compatible aliases for previously used keys.
LEGACY_AGENT_ALIASES: Dict[str, str] = {
    "cursor": "cursor-agent",
}

AGENT_CONFIG: Dict[str, Dict[str, Any]] = {
    key: {
        "name": value["name"],
        "folder": value["folder"],
        "install_url": value["install_url"],
        "requires_cli": value["requires_cli"],
    }
    for key, value in AGENT_METADATA.items()
}

AGENT_COMMAND_CONFIGS: Dict[str, Dict[str, str]] = {
    key: {
        "dir": value["command_dir"],
        "format": value["command_format"],
        "args": value["args"],
        "extension": value["extension"],
    }
    for key, value in AGENT_METADATA.items()
}
