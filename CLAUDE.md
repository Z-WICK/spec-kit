# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spec Kit is an open-source toolkit for Spec-Driven Development (SDD) — a methodology where specifications are the primary artifact that generates code, not the other way around. The `specify` CLI bootstraps projects with the SDD framework, supporting 18+ AI coding assistants.

This is the Z-WICK enhanced fork with additional commands: `init`, `pipeline`, `issue`, `fixbug`.

## Build & Run Commands

```bash
# Install dependencies
uv sync

# Run CLI locally
uv run specify --help
uv run specify init <project-name> --ai claude

# Direct module execution
python -m src.specify_cli --help

# Editable install for development
uv pip install -e .

# Build wheel
uv build

# Lint markdown (also runs in CI)
markdownlint-cli2 '**/*.md'
```

There is no automated test suite (no pytest/unittest). Testing is manual — run `specify init` with various `--ai` flags and verify generated output.

### Testing Template/Command Changes Locally

```bash
# 1. Generate local release packages
./.github/workflows/scripts/create-release-packages.sh v1.0.0

# 2. Copy to a test project
cp -r .genreleases/sdd-copilot-package-sh/. /path/to/test-project/

# 3. Open test project in your agent and verify
```

## Architecture

The entire CLI lives in a single file: `src/specify_cli/__init__.py` (~2000 lines). Key sections:

- `AGENT_CONFIG` dict (line ~126) — single source of truth for all supported agents. Keys must match actual CLI tool names (e.g., `"cursor-agent"` not `"cursor"`).
- `StepTracker` class — Rich-based progress visualization
- `init()` — main command: downloads templates from GitHub releases, extracts to project, sets up agent-specific command files
- `check()` — verifies installed tools
- `version()` — displays version/system info
- `download_template_from_github()` / `download_and_extract_template()` — handles GitHub release asset download with rate-limit awareness
- `handle_vscode_settings()` / `merge_json_files()` — merges VS Code settings instead of overwriting

### Template System

- `templates/commands/*.md` — SDD workflow command templates (specify, plan, tasks, implement, clarify, analyze, checklist, constitution, plus enhanced: init, pipeline, issue, fixbug)
- `templates/*-template.md` — document templates (spec, plan, tasks, checklist)
- `templates/agent-file-template.md` — wrapper template for generating agent-specific command files

Agent command files use two formats:
- Markdown: `---\ndescription: "..."\n---\n` frontmatter + content, with `$ARGUMENTS` placeholder
- TOML (Gemini, Qwen): `description = "..."` + `prompt = """..."""`, with `{{args}}` placeholder

### Scripts

`scripts/bash/` and `scripts/powershell/` contain project-level scripts that get installed into `.specify/scripts/` in generated projects:
- `create-new-feature.sh` — feature branch creation with auto-numbering
- `setup-plan.sh` — initialize implementation plan from template
- `update-agent-context.sh` — refresh agent command files
- `common.sh` — shared utilities
- `check-prerequisites.sh` — tool verification

### Release Pipeline

CI in `.github/workflows/release.yml` auto-creates releases when templates/scripts change:
1. Determines next semver from git tags
2. Generates template packages for each agent (both sh and ps1 variants)
3. Creates GitHub release with all packages as assets

## Key Conventions

- Python 3.11+ required; uses `hatchling` build backend
- Dependencies: `typer` (CLI), `rich` (terminal UI), `httpx` (HTTP), `platformdirs`, `readchar`, `truststore`
- Cross-platform: bash scripts have PowerShell equivalents; file paths use `pathlib.Path`
- GitHub token for API rate limits: `--github-token` flag or `GH_TOKEN`/`GITHUB_TOKEN` env vars
- AI contribution disclosure required in PRs per CONTRIBUTING.md
