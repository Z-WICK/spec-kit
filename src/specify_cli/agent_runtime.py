"""Runtime helpers for agent-specific init, skills, and compatibility flows."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import typer
import yaml

from .agents import (
    AGENT_CONFIG,
    DEFAULT_SKILLS_DIR,
    build_skill_name,
    get_agent_skills_dir_relative,
)
from .fork_customizations import (
    command_template_source_label,
    find_command_template,
    iter_command_templates,
)


INIT_OPTIONS_FILE = ".specify/init-options.json"


def _default_agent_skills_dir(folder: str | None) -> str:
    if folder:
        return f"{folder.rstrip('/')}/skills"
    return DEFAULT_SKILLS_DIR


AGENT_SKILLS_DIR_OVERRIDES = {
    agent: get_agent_skills_dir_relative(agent)
    for agent, config in AGENT_CONFIG.items()
    if get_agent_skills_dir_relative(agent) != _default_agent_skills_dir(config.get("folder"))
}
if "codex" in AGENT_CONFIG:
    AGENT_SKILLS_DIR_OVERRIDES.setdefault("codex", get_agent_skills_dir_relative("codex"))


SKILL_DESCRIPTIONS = {
    "specify": "Create or update feature specifications from natural language descriptions. Use when starting new features or refining requirements. Generates spec.md with user stories, functional requirements, and acceptance criteria following spec-driven development methodology.",
    "plan": "Generate technical implementation plans from feature specifications. Use after creating a spec to define architecture, tech stack, and implementation phases. Creates plan.md with detailed technical design.",
    "tasks": "Break down implementation plans into actionable task lists. Use after planning to create a structured task breakdown. Generates tasks.md with ordered, dependency-aware tasks.",
    "implement": "Execute all tasks from the task breakdown to build the feature. Use after task generation to systematically implement the planned solution following TDD approach where applicable.",
    "analyze": "Perform cross-artifact consistency analysis across spec.md, plan.md, and tasks.md. Use after task generation to identify gaps, duplications, and inconsistencies before implementation.",
    "clarify": "Structured clarification workflow for underspecified requirements. Use before planning to resolve ambiguities through coverage-based questioning. Records answers in spec clarifications section.",
    "constitution": "Create or update project governing principles and development guidelines. Use at project start to establish code quality, testing standards, and architectural constraints that guide all development.",
    "checklist": "Generate custom quality checklists for validating requirements completeness and clarity. Use to create unit tests for English that ensure spec quality before implementation.",
    "taskstoissues": "Convert tasks from tasks.md into GitHub issues. Use after task breakdown to track work items in GitHub project management.",
}


def save_init_options(project_path: Path, options: dict[str, Any]) -> None:
    """Persist the CLI options used during ``specify init``."""
    dest = project_path / INIT_OPTIONS_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(options, indent=2, sort_keys=True))


def load_init_options(project_path: Path) -> dict[str, Any]:
    """Load the init options previously saved by ``specify init``."""
    path = project_path / INIT_OPTIONS_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _get_skills_dir(project_path: Path, selected_ai: str) -> Path:
    """Resolve the agent-specific skills directory for the given AI assistant."""
    return project_path / get_agent_skills_dir_relative(selected_ai)


def _agent_command_templates(templates_dir: Path, selected_ai: str) -> list[Path]:
    """Return only packaged spec-kit command templates for the selected agent."""
    if not templates_dir.exists():
        return []

    pattern = "speckit.*.agent.md" if selected_ai == "copilot" else "speckit.*.md"
    return sorted(path for path in templates_dir.glob(pattern) if path.is_file())


def _command_name_from_template(command_file: Path) -> str:
    """Normalize a packaged command filename to its logical command name."""
    command_name = command_file.name
    if command_name.endswith(".agent.md"):
        command_name = command_name[: -len(".agent.md")]
    else:
        command_name = command_file.stem

    if command_name.startswith("speckit."):
        command_name = command_name[len("speckit.") :]

    return command_name


def install_ai_skills(
    project_path: Path,
    selected_ai: str,
    tracker: Any | None = None,
    console: Any | None = None,
    *,
    overwrite_existing: bool = False,
) -> bool:
    """Install Prompt.MD files from the packaged or repo fallback command templates as agent skills."""
    agent_config = AGENT_CONFIG.get(selected_ai, {})
    agent_folder = agent_config.get("folder", "")
    commands_subdir = agent_config.get("commands_subdir", "commands")
    package_file = getattr(sys.modules.get("specify_cli"), "__file__", __file__)
    script_dir = Path(package_file).resolve().parent.parent.parent
    if agent_folder:
        templates_dir = project_path / agent_folder.rstrip("/") / commands_subdir
    else:
        templates_dir = project_path / commands_subdir

    command_files = _agent_command_templates(templates_dir, selected_ai)

    if not command_files:
        fallback_templates = iter_command_templates(script_dir)
    else:
        fallback_templates = []

    if not fallback_templates and not command_files:
        if tracker:
            tracker.error("ai-skills", "command templates not found")
        elif console:
            console.print("[yellow]Warning: command templates not found, skipping skills installation[/yellow]")
        return False

    if not command_files and fallback_templates:
        command_files = fallback_templates

    if not command_files:
        if tracker:
            tracker.skip("ai-skills", "no command templates found")
        elif console:
            console.print("[yellow]No command templates found to install[/yellow]")
        return False

    skills_dir = _get_skills_dir(project_path, selected_ai)
    skills_dir.mkdir(parents=True, exist_ok=True)

    if tracker:
        tracker.start("ai-skills")

    installed_count = 0
    skipped_count = 0
    for command_file in command_files:
        try:
            content = command_file.read_text(encoding="utf-8")

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    if not isinstance(frontmatter, dict):
                        frontmatter = {}
                    body = parts[2].strip()
                else:
                    frontmatter = {}
                    body = content
            else:
                frontmatter = {}
                body = content

            command_name = _command_name_from_template(command_file)

            skill_name = build_skill_name(selected_ai, command_name)
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            original_desc = frontmatter.get("description", "")
            enhanced_desc = SKILL_DESCRIPTIONS.get(
                command_name,
                original_desc or f"Spec-kit workflow command: {command_name}",
            )

            source_name = command_file.name
            if source_name.endswith(".agent.md"):
                source_name = source_name[: -len(".agent.md")] + ".md"
            if source_name.startswith("speckit."):
                source_name = source_name[len("speckit."):]

            if command_file.is_relative_to(project_path):
                source_template = find_command_template(script_dir, command_name)
                if source_template is not None:
                    source_label = command_template_source_label(script_dir, source_template)
                else:
                    source_label = f"templates/commands/{source_name}"
            else:
                source_label = command_template_source_label(script_dir, command_file)

            frontmatter_data = {
                "name": skill_name,
                "description": enhanced_desc,
                "compatibility": "Requires spec-kit project structure with .specify/ directory",
                "metadata": {
                    "author": "github-spec-kit",
                    "source": source_label,
                },
            }
            frontmatter_text = yaml.safe_dump(frontmatter_data, sort_keys=False).strip()
            skill_content = (
                f"---\n"
                f"{frontmatter_text}\n"
                f"---\n\n"
                f"# Speckit {command_name.title()} Skill\n\n"
                f"{body}\n"
            )

            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                if overwrite_existing:
                    skill_file.write_text(skill_content, encoding="utf-8")
                    installed_count += 1
                    continue
                skipped_count += 1
                continue

            skill_file.write_text(skill_content, encoding="utf-8")
            installed_count += 1
        except Exception as exc:
            if console:
                console.print(f"[yellow]Warning: Failed to install skill {command_file.stem}: {exc}[/yellow]")
            continue

    relative_dir = skills_dir.relative_to(project_path)
    if tracker:
        if installed_count > 0 and skipped_count > 0:
            tracker.complete("ai-skills", f"{installed_count} new + {skipped_count} existing skills in {relative_dir}")
        elif installed_count > 0:
            tracker.complete("ai-skills", f"{installed_count} skills → {relative_dir}")
        elif skipped_count > 0:
            tracker.complete("ai-skills", f"{skipped_count} skills already present")
        else:
            tracker.error("ai-skills", "no skills installed")
    elif console:
        if installed_count > 0:
            console.print(f"[green]✓[/green] Installed {installed_count} agent skills to {relative_dir}/")
        elif skipped_count > 0:
            console.print(f"[green]✓[/green] {skipped_count} agent skills already present in {relative_dir}/")
        else:
            console.print("[yellow]No skills were installed[/yellow]")

    return installed_count > 0 or skipped_count > 0


def cleanup_extracted_commands_after_skill_install(
    project_path: Path,
    selected_ai: str,
    *,
    keep_existing_commands: bool,
    console: Any,
) -> None:
    """Remove extracted command files after successful skill installation."""
    if keep_existing_commands:
        return

    agent_cfg = AGENT_CONFIG.get(selected_ai, {})
    agent_folder = agent_cfg.get("folder", "")
    commands_subdir = agent_cfg.get("commands_subdir", "commands")
    if not agent_folder:
        return

    cmds_dir = project_path / agent_folder.rstrip("/") / commands_subdir
    if not cmds_dir.exists():
        return

    try:
        shutil.rmtree(cmds_dir)
    except OSError:
        console.print("[yellow]Warning: could not remove extracted commands directory[/yellow]")


def _handle_agy_deprecation(console: Any) -> None:
    """Print the Antigravity deprecation error and exit."""
    console.print("\n[red]Error:[/red] Explicit command support was deprecated in Antigravity version 1.20.5.")
    console.print("Please use [cyan]--ai-skills[/cyan] when initializing to install templates as agent skills instead.")
    console.print("[yellow]Usage:[/yellow] specify init <project> --ai agy --ai-skills")
    raise typer.Exit(1)


def _handle_codex_deprecation(console: Any) -> None:
    """Print the Codex native-skills migration error and exit."""
    console.print("\n[red]Error:[/red] Custom prompt-based spec-kit initialization is deprecated for Codex CLI.")
    console.print("Please use [cyan]--ai-skills[/cyan] so Spec Kit installs or validates native skills instead.")
    console.print("[yellow]Usage:[/yellow] specify init <project> --ai codex --ai-skills")
    raise typer.Exit(1)


def resolve_ai_skills_mode(
    selected_ai: str,
    ai_assistant: str | None,
    ai_skills: bool,
    console: Any,
) -> bool:
    """Apply agent-specific compatibility rules for --ai-skills selection."""
    if ai_skills:
        return ai_skills

    if selected_ai == "agy":
        if ai_assistant:
            _handle_agy_deprecation(console)

        console.print(
            "\n[yellow]Note:[/yellow] 'agy' was selected interactively; "
            "enabling [cyan]--ai-skills[/cyan] automatically for compatibility "
            "(explicit .agent/commands usage is deprecated)."
        )
        return True

    if selected_ai == "codex":
        if ai_assistant:
            _handle_codex_deprecation(console)

        console.print(
            "\n[yellow]Note:[/yellow] 'codex' was selected interactively; "
            "enabling [cyan]--ai-skills[/cyan] automatically because Codex uses native skills."
        )
        return True

    return ai_skills
