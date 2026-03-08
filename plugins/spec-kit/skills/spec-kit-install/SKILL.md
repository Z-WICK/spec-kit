---
name: spec-kit-install
description: Install Spec Kit Claude workflow assets into the current project after the plugin is installed. Use this immediately after adding the plugin from marketplace.
---

# Spec Kit Install

Use this skill right after installing the Spec Kit plugin to copy the bundled Claude Code workflow assets into the current project.

## What this installs

- `.claude/commands/*`
- `.claude/agents/*`
- `.specify/*`

## How to run

Choose the command that matches your shell environment:

- macOS / Linux:
  `bash ${CLAUDE_SKILL_DIR}/scripts/install-spec-kit.sh`
- Windows PowerShell:
  `powershell -ExecutionPolicy Bypass -File "$env:CLAUDE_SKILL_DIR/scripts/install-spec-kit.ps1"`

## Notes

- Run this from the target project root.
- Re-running is safe: existing project knowledge files are preserved using the same rules as the CLI re-init flow.
- After installation, restart Claude Code if newly copied commands do not appear immediately.
