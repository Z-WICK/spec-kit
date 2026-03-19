from __future__ import annotations

from pathlib import Path


CORE_COMMAND_TEMPLATES_DIR = Path("templates/commands")
FORK_COMMAND_TEMPLATES_DIR = Path("templates/fork-commands")
COMMAND_TEMPLATE_DIRS = (CORE_COMMAND_TEMPLATES_DIR, FORK_COMMAND_TEMPLATES_DIR)

FORK_COMMAND_REGISTRY = (
    {
        "name": "init",
        "description": "Smart project initialization with auto-detection of tech stack",
        "show_in_panel": True,
    },
    {
        "name": "pipeline",
        "description": "Full automation pipeline from requirements to deployment",
        "show_in_panel": True,
    },
    {
        "name": "issue",
        "description": "Create structured GitHub Issues (bug/feature/task)",
        "show_in_panel": True,
    },
    {
        "name": "fixbug",
        "description": "Bug investigation & fix workflow with log analysis",
        "show_in_panel": True,
    },
    {
        "name": "optimize-constitution",
        "description": "Append engineering efficiency principles to constitution",
        "show_in_panel": True,
    },
    {
        "name": "update",
        "description": "Refresh local Spec Kit assets from the latest release",
        "show_in_panel": False,
    },
)
FORK_COMMAND_NAMES = tuple(entry["name"] for entry in FORK_COMMAND_REGISTRY)


def iter_command_templates(repo_root: Path) -> list[Path]:
    """Return command templates from core and fork directories."""
    templates: list[Path] = []
    for relative_dir in COMMAND_TEMPLATE_DIRS:
        template_dir = repo_root / relative_dir
        if not template_dir.exists():
            continue
        templates.extend(sorted(template_dir.glob("*.md")))
    return templates


def find_command_template(repo_root: Path, command_name: str) -> Path | None:
    """Find a command template by short name across core and fork sources."""
    for relative_dir in COMMAND_TEMPLATE_DIRS:
        template_path = repo_root / relative_dir / f"{command_name}.md"
        if template_path.exists():
            return template_path
    return None


def command_template_source_label(repo_root: Path, template_path: Path) -> str:
    """Return the repository-relative template source label."""
    return template_path.resolve().relative_to(repo_root.resolve()).as_posix()


def build_agent_folder_security_notice(agent_folder: str) -> str:
    """Build the agent-folder security reminder shown after init."""
    return (
        "Some agents may store credentials, auth tokens, or other identifying "
        "and private artifacts in the agent folder within your project.\n"
        f"Consider adding [cyan]{agent_folder}[/cyan] (or parts of it) to [cyan].gitignore[/cyan] "
        "to prevent accidental credential leakage."
    )


def build_next_steps_lines(selected_ai: str, here: bool, project_name: str) -> list[str]:
    """Build the post-init next-steps panel lines."""
    lines: list[str] = []
    if not here:
        lines.append(f"1. Go to the project folder: [cyan]cd {project_name}[/cyan]")
        step_num = 2
    else:
        lines.append("1. You're already in the project directory!")
        step_num = 2

    if selected_ai == "codex":
        lines.append(f"{step_num}. Start using skills with Codex:")
        lines.append("   [dim]Skills are generated at .agents/skills/<skill>/SKILL.md.[/dim]")
        lines.append("   [dim]Legacy .codex/skills remains supported for compatibility.[/dim]")
        lines.append("   [dim]In Codex, run /skills and invoke skills as $speckit-...[/dim]")
        command_prefix = "$speckit-"
    elif selected_ai == "kimi":
        lines.append(f"{step_num}. Start using skills with Kimi Code:")
        lines.append("   [dim]Skills are generated at .kimi/skills/<skill>/SKILL.md.[/dim]")
        lines.append("   [dim]In Kimi, invoke skills as /skill:speckit....[/dim]")
        command_prefix = "/skill:speckit."
    else:
        lines.append(f"{step_num}. Start using slash commands with your AI agent:")
        command_prefix = "/speckit."

    lines.append(f"   {step_num}.1 [cyan]{command_prefix}constitution[/] - Establish project principles")
    lines.append(f"   {step_num}.2 [cyan]{command_prefix}specify[/] - Create baseline specification")
    lines.append(f"   {step_num}.3 [cyan]{command_prefix}plan[/] - Create implementation plan")
    lines.append(f"   {step_num}.4 [cyan]{command_prefix}tasks[/] - Generate actionable tasks")
    lines.append(f"   {step_num}.5 [cyan]{command_prefix}implement[/] - Execute implementation")
    return lines


def build_enhancement_panel_lines(selected_ai: str) -> list[str]:
    """Build the fork enhancement panel lines shown after init."""
    if selected_ai == "codex":
        command_prefix = "$speckit-"
        lines = ["Optional skills that you can use for your specs [bright_black](Z-WICK fork)[/bright_black]", ""]
    elif selected_ai == "kimi":
        command_prefix = "/skill:speckit."
        lines = ["Optional skills that you can use for your specs [bright_black](Z-WICK fork)[/bright_black]", ""]
    else:
        command_prefix = "/speckit."
        lines = ["Enhanced commands [bright_black](Z-WICK fork)[/bright_black]", ""]
    for command in FORK_COMMAND_REGISTRY:
        if not command["show_in_panel"]:
            continue
        lines.append(
            f"○ [cyan]{command_prefix}{command['name']}[/] - {command['description']}"
        )
    return lines
