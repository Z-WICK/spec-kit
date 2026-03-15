from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol

import typer
from rich.console import Console
from rich.panel import Panel

from .template_runtime import _resolve_project_relative_path, _safe_move_directory_into_project


class TrackerLike(Protocol):
    def add(self, key: str, label: str) -> None: ...
    def complete(self, key: str, detail: str = "") -> None: ...
    def error(self, key: str, detail: str = "") -> None: ...


@dataclass(frozen=True)
class InitTarget:
    project_name: str
    project_path: Path
    here: bool


def validate_raw_option_values(
    ai_assistant: str | None,
    ai_commands_dir: str | None,
    console: Console,
    agent_config: Mapping[str, object],
) -> None:
    """Reject flag-like values captured as option values."""
    if ai_assistant and ai_assistant.startswith("-"):
        console.print(f"[red]Error:[/red] Invalid value for --ai: '{ai_assistant}'")
        console.print("[yellow]Hint:[/yellow] Did you forget to provide a value for --ai?")
        console.print("[yellow]Rule:[/yellow] --ai requires a valid assistant name")
        console.print("[yellow]Example:[/yellow] specify init --ai claude --here")
        console.print(f"[yellow]Available agents:[/yellow] {', '.join(agent_config.keys())}")
        raise typer.Exit(1)

    if ai_commands_dir and ai_commands_dir.startswith("--"):
        console.print(f"[red]Error:[/red] Invalid value for --ai-commands-dir: '{ai_commands_dir}'")
        console.print("[yellow]Hint:[/yellow] Did you forget to provide a value for --ai-commands-dir?")
        console.print("[yellow]Example:[/yellow] specify init --ai generic --ai-commands-dir .myagent/commands/")
        raise typer.Exit(1)


def resolve_project_target(
    project_name: str | None,
    here: bool,
    force: bool,
    console: Console,
    *,
    cwd: Path | None = None,
    confirm: Callable[[str], bool] = typer.confirm,
) -> InitTarget:
    """Resolve the target project path and current-directory behavior."""
    cwd = cwd or Path.cwd()

    if project_name == ".":
        here = True
        project_name = None

    if here and project_name:
        console.print("[red]Error:[/red] Cannot specify both project name and --here flag")
        raise typer.Exit(1)

    if not here and not project_name:
        console.print(
            "[red]Error:[/red] Must specify either a project name, use '.' for current directory, or use --here flag"
        )
        raise typer.Exit(1)

    if here:
        resolved_project_name = cwd.name
        project_path = cwd

        existing_items = list(project_path.iterdir())
        if existing_items:
            console.print(f"[yellow]Warning:[/yellow] Current directory is not empty ({len(existing_items)} items)")
            console.print("[yellow]Template files will be merged with existing content and may overwrite existing files[/yellow]")
            if force:
                console.print("[cyan]--force supplied: skipping confirmation and proceeding with merge[/cyan]")
            else:
                response = confirm("Do you want to continue?")
                if not response:
                    console.print("[yellow]Operation cancelled[/yellow]")
                    raise typer.Exit(0)

        return InitTarget(project_name=resolved_project_name, project_path=project_path, here=True)

    project_path = Path(project_name).resolve()
    if project_path.exists():
        error_panel = Panel(
            f"Directory '[cyan]{project_name}[/cyan]' already exists\n"
            "Please choose a different project name or remove the existing directory.",
            title="[red]Directory Conflict[/red]",
            border_style="red",
            padding=(1, 2),
        )
        console.print()
        console.print(error_panel)
        raise typer.Exit(1)

    return InitTarget(project_name=str(project_name), project_path=project_path, here=False)


def resolve_ai_selection(
    ai_assistant: str | None,
    ai_skills: bool,
    ai_commands_dir: str | None,
    console: Console,
    agent_config: Mapping[str, Mapping[str, object]],
    *,
    aliases: Mapping[str, str],
    select_fn: Callable[[dict, str, str | None], str],
    resolve_ai_skills_mode_fn: Callable[[str, str | None, bool, Console], bool],
) -> tuple[str, bool]:
    """Resolve the selected AI assistant and validate generic agent inputs."""
    normalized_ai = aliases.get(ai_assistant, ai_assistant) if ai_assistant else None

    if normalized_ai:
        if normalized_ai not in agent_config:
            console.print(
                f"[red]Error:[/red] Invalid AI assistant '{normalized_ai}'. "
                f"Choose from: {', '.join(agent_config.keys())}"
            )
            raise typer.Exit(1)
        selected_ai = normalized_ai
    else:
        ai_choices = {key: config["name"] for key, config in agent_config.items()}
        selected_ai = select_fn(ai_choices, "Choose your AI assistant:", "copilot")

    resolved_ai_skills = resolve_ai_skills_mode_fn(selected_ai, normalized_ai, ai_skills, console)

    if selected_ai == "generic":
        if not ai_commands_dir:
            console.print("[red]Error:[/red] --ai-commands-dir is required when using --ai generic")
            console.print("[dim]Example: specify init my-project --ai generic --ai-commands-dir .myagent/commands/[/dim]")
            raise typer.Exit(1)
    elif ai_commands_dir:
        console.print(
            f"[red]Error:[/red] --ai-commands-dir can only be used with --ai generic (not '{selected_ai}')"
        )
        raise typer.Exit(1)

    return selected_ai, resolved_ai_skills


def resolve_script_selection(
    script_type: str | None,
    script_type_choices: Mapping[str, str],
    console: Console,
    *,
    os_name: str | None = None,
    stdin_is_tty: bool | None = None,
    select_fn: Callable[[dict, str, str | None], str],
) -> str:
    """Resolve the selected script type with platform defaults."""
    if script_type:
        if script_type not in script_type_choices:
            console.print(
                f"[red]Error:[/red] Invalid script type '{script_type}'. "
                f"Choose from: {', '.join(script_type_choices.keys())}"
            )
            raise typer.Exit(1)
        return script_type

    resolved_os_name = os_name if os_name is not None else os.name
    resolved_stdin_is_tty = stdin_is_tty if stdin_is_tty is not None else sys.stdin.isatty()
    default_script = "ps" if resolved_os_name == "nt" else "sh"

    if resolved_stdin_is_tty:
        return select_fn(script_type_choices, "Choose script type (or press Enter)", default_script)
    return default_script


def build_init_tracker(
    selected_ai: str,
    selected_script: str,
    ai_skills: bool,
    *,
    tracker_cls,
):
    """Create the init progress tracker with consistent steps."""
    tracker = tracker_cls("Initialize Specify Project")
    tracker.add("precheck", "Check required tools")
    tracker.complete("precheck", "ok")
    tracker.add("ai-select", "Select AI assistant")
    tracker.complete("ai-select", selected_ai)
    tracker.add("script-select", "Select script type")
    tracker.complete("script-select", selected_script)

    for key, label in [
        ("fetch", "Fetch latest release"),
        ("download", "Download template"),
        ("extract", "Extract template"),
        ("zip-list", "Archive contents"),
        ("extracted-summary", "Extraction summary"),
        ("chmod", "Ensure scripts executable"),
        ("constitution", "Constitution setup"),
    ]:
        tracker.add(key, label)

    if ai_skills:
        tracker.add("ai-skills", "Install agent skills")

    for key, label in [
        ("cleanup", "Cleanup"),
        ("git", "Initialize git repository"),
        ("final", "Finalize"),
    ]:
        tracker.add(key, label)

    return tracker


def relocate_generic_commands_dir(
    project_path: Path,
    selected_ai: str,
    ai_commands_dir: str | None,
    tracker: TrackerLike,
) -> None:
    """Move generic placeholder commands into the requested project-relative directory."""
    if selected_ai != "generic" or not ai_commands_dir:
        return

    placeholder_dir = project_path / ".speckit" / "commands"
    try:
        _resolve_project_relative_path(ai_commands_dir, project_path)
    except ValueError as e:
        tracker.error("final", str(e))
        raise typer.Exit(1) from e

    if placeholder_dir.exists() and placeholder_dir.is_symlink():
        tracker.error("final", f"Source path must not be a symlink: {placeholder_dir}")
        raise typer.Exit(1)

    if placeholder_dir.is_dir():
        try:
            _safe_move_directory_into_project(placeholder_dir, ai_commands_dir, project_path)
        except ValueError as e:
            tracker.error("final", str(e))
            raise typer.Exit(1) from e

        speckit_dir = project_path / ".speckit"
        if speckit_dir.is_dir() and not any(speckit_dir.iterdir()):
            speckit_dir.rmdir()


def persist_init_options(
    project_path: Path,
    *,
    selected_ai: str,
    ai_skills: bool,
    ai_commands_dir: str | None,
    here: bool,
    preset: str | None,
    selected_script: str,
    speckit_version: str,
    save_init_options_fn: Callable[[Path, dict], None],
) -> None:
    """Persist init options in the standard on-disk structure."""
    save_init_options_fn(
        project_path,
        {
            "ai": selected_ai,
            "ai_skills": ai_skills,
            "ai_commands_dir": ai_commands_dir,
            "here": here,
            "preset": preset,
            "script": selected_script,
            "speckit_version": speckit_version,
        },
    )


def install_requested_preset(
    project_path: Path,
    preset: str | None,
    speckit_version: str,
    console: Console,
    *,
    preset_manager_cls=None,
    preset_catalog_cls=None,
    preset_error_cls=None,
) -> None:
    """Install a preset from a local directory or from the configured catalog."""
    if not preset:
        return

    try:
        if preset_manager_cls is None or preset_catalog_cls is None or preset_error_cls is None:
            from .presets import PresetCatalog, PresetError, PresetManager

            preset_manager_cls = preset_manager_cls or PresetManager
            preset_catalog_cls = preset_catalog_cls or PresetCatalog
            preset_error_cls = preset_error_cls or PresetError

        preset_manager = preset_manager_cls(project_path)
        local_path = Path(preset).resolve()
        if local_path.is_dir() and (local_path / "preset.yml").exists():
            preset_manager.install_from_directory(local_path, speckit_version)
            return

        preset_catalog = preset_catalog_cls(project_path)
        pack_info = preset_catalog.get_pack_info(preset)
        if not pack_info:
            console.print(f"[yellow]Warning:[/yellow] Preset '{preset}' not found in catalog. Skipping.")
            return

        try:
            zip_path = preset_catalog.download_pack(preset)
            preset_manager.install_from_zip(zip_path, speckit_version)
            try:
                zip_path.unlink(missing_ok=True)
            except OSError:
                pass
        except preset_error_cls as preset_err:
            console.print(f"[yellow]Warning:[/yellow] Failed to install preset '{preset}': {preset_err}")
    except Exception as preset_err:
        console.print(f"[yellow]Warning:[/yellow] Failed to install preset: {preset_err}")
