#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer",
#     "rich",
#     "platformdirs",
#     "readchar",
#     "httpx",
#     "json5",
# ]
# ///
"""
Specify CLI - Setup tool for Specify projects

Usage:
    uvx specify-cli.py init <project-name>
    uvx specify-cli.py init .
    uvx specify-cli.py init --here

Or install globally:
    uv tool install --from specify-cli.py specify-cli
    specify init <project-name>
    specify init .
    specify init --here
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
import shutil
import yaml
from pathlib import Path
from typing import Optional, Tuple

import typer
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.table import Table
from rich.tree import Tree
from typer.core import TyperGroup

# For cross-platform keyboard input
import readchar
from datetime import datetime

from .agent_runtime import (
    AGENT_SKILLS_DIR_OVERRIDES as AGENT_SKILLS_DIR_OVERRIDES,
    DEFAULT_SKILLS_DIR as DEFAULT_SKILLS_DIR,
    INIT_OPTIONS_FILE as INIT_OPTIONS_FILE,
    SKILL_DESCRIPTIONS as SKILL_DESCRIPTIONS,
    _get_skills_dir as _get_skills_dir,
    cleanup_extracted_commands_after_skill_install,
    install_ai_skills,
    load_init_options as load_init_options,
    resolve_ai_skills_mode,
    save_init_options,
)
from .agents import AGENT_CONFIG, LEGACY_AGENT_ALIASES
from .fork_customizations import (
    build_agent_folder_security_notice,
    build_enhancement_panel_lines,
    build_next_steps_lines,
)
from . import template_runtime as _template_runtime_module
from .init_runtime import (
    build_init_tracker,
    install_requested_preset,
    persist_init_options,
    relocate_generic_commands_dir,
    resolve_ai_selection,
    resolve_project_target,
    resolve_script_selection,
    validate_raw_option_values,
)
from .template_runtime import (
    _github_auth_headers,
    download_template_from_github as download_template_from_github,
    download_and_extract_template,
    ensure_constitution_from_template,
    ensure_executable_scripts,
    handle_vscode_settings as handle_vscode_settings,
    merge_json_files as merge_json_files,
    ssl_context,
)

client = httpx.Client(verify=ssl_context)

AI_ASSISTANT_ALIASES = dict(LEGACY_AGENT_ALIASES)

# Agents that use TOML command format (others use Markdown)
_TOML_AGENTS = frozenset({"gemini", "tabnine"})

# Agents whose template archives already ship native skills in final layout.
NATIVE_SKILLS_AGENTS = {"codex", "kimi"}


def _build_ai_assistant_help() -> str:
    """Build the --ai help text from AGENT_CONFIG so it stays in sync."""
    non_generic_agents = sorted(agent for agent in AGENT_CONFIG if agent != "generic")
    base_help = (
        f"AI assistant to use: {', '.join(non_generic_agents)}, "
        "or generic (requires --ai-commands-dir)."
    )

    if not AI_ASSISTANT_ALIASES:
        return base_help

    alias_phrases = [
        f"'{alias}' as an alias for '{target}'"
        for alias, target in sorted(AI_ASSISTANT_ALIASES.items())
    ]

    if len(alias_phrases) == 1:
        aliases_text = alias_phrases[0]
    else:
        aliases_text = ", ".join(alias_phrases[:-1]) + " and " + alias_phrases[-1]

    return base_help + " Use " + aliases_text + "."


AI_ASSISTANT_HELP = _build_ai_assistant_help()


def download_and_extract_template(*args, **kwargs):
    """Compatibility wrapper so tests/patches can replace download_template_from_github via specify_cli."""
    original = _template_runtime_module.download_template_from_github
    _template_runtime_module.download_template_from_github = download_template_from_github
    try:
        return _template_runtime_module.download_and_extract_template(*args, **kwargs)
    finally:
        _template_runtime_module.download_template_from_github = original


def _has_bundled_codex_skills(project_path: Path) -> bool:
    """Return True when the extracted template already contains Spec Kit Codex skills."""
    skills_dir = project_path / ".agents" / "skills"
    return any(skills_dir.glob("speckit-*/SKILL.md"))


def _has_bundled_skills(project_path: Path, selected_ai: str) -> bool:
    """Return True when the extracted template already contains native skills."""
    skills_dir = _get_skills_dir(project_path, selected_ai)
    if not skills_dir.is_dir():
        return False
    return any(skills_dir.glob("speckit-*/SKILL.md"))


def _migrate_legacy_kimi_dotted_skills(skills_dir: Path) -> tuple[int, int]:
    """Migrate legacy Kimi dotted skill dirs (speckit.xxx) to hyphenated format."""
    if not skills_dir.is_dir():
        return (0, 0)

    migrated_count = 0
    removed_count = 0

    for legacy_dir in sorted(skills_dir.glob("speckit.*")):
        if not legacy_dir.is_dir():
            continue
        legacy_skill = legacy_dir / "SKILL.md"
        if not legacy_skill.is_file():
            continue

        suffix = legacy_dir.name[len("speckit.") :]
        if not suffix:
            continue

        target_dir = skills_dir / f"speckit-{suffix.replace('.', '-')}"
        if not target_dir.exists():
            shutil.move(str(legacy_dir), str(target_dir))
            migrated_count += 1
            continue

        target_skill = target_dir / "SKILL.md"
        if not target_skill.is_file():
            continue

        try:
            if target_skill.read_bytes() != legacy_skill.read_bytes():
                continue

            has_extra_entries = any(child.name != "SKILL.md" for child in legacy_dir.iterdir())
            if not has_extra_entries:
                shutil.rmtree(legacy_dir)
                removed_count += 1
        except OSError:
            # Best-effort migration only; preserve legacy dirs on read errors.
            continue

    return (migrated_count, removed_count)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _locate_core_pack() -> Optional[Path]:
    """Locate bundled/source core assets for offline scaffolding."""
    pkg_root = Path(__file__).resolve().parent
    wheel_core = pkg_root / "core_pack"
    if wheel_core.exists():
        return wheel_core

    repo_root = _repo_root()
    templates_dir = repo_root / "templates" / "commands"
    if templates_dir.is_dir():
        return repo_root / "templates"

    return None


def _resolve_release_script() -> Optional[Path]:
    """Resolve the release packaging script used for offline scaffolding parity."""
    repo_script = _repo_root() / ".github" / "workflows" / "scripts" / "create-release-packages.sh"
    if repo_script.exists():
        return repo_script

    wheel_script = Path(__file__).resolve().parent / "core_pack" / "release_scripts" / "create-release-packages.sh"
    if wheel_script.exists():
        return wheel_script

    return None


def scaffold_from_core_pack(
    project_path: Path,
    selected_ai: str,
    selected_script: str,
    here: bool = False,
    tracker: StepTracker | None = None,
) -> bool:
    """Scaffold a project from bundled assets without a network download.

    In a source checkout this shells out to the same release-packaging script
    used by CI, then unzips the generated agent package into ``project_path``.
    This keeps offline scaffolding byte-for-byte aligned with release artifacts.
    """
    release_script = _resolve_release_script()
    if release_script is None:
        if tracker:
            tracker.error("scaffold", "release script not found")
        return False

    bash_bin = shutil.which("bash")
    if bash_bin is None:
        if tracker:
            tracker.error("scaffold", "'bash' not found on PATH")
        return False

    if tracker:
        tracker.add("scaffold", "Apply bundled assets")
        tracker.start("scaffold")

    with tempfile.TemporaryDirectory(prefix="specify-core-pack-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        version = "v0.0.0"
        env = os.environ.copy()
        env["AGENTS"] = selected_ai
        env["SCRIPTS"] = selected_script
        env["GENRELEASES_DIR"] = str(tmpdir_path)

        result = subprocess.run(
            [bash_bin, str(release_script), version],
            cwd=_repo_root(),
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"release script failed ({result.returncode})"
            if tracker:
                tracker.error("scaffold", detail)
            return False

        zip_path = tmpdir_path / f"spec-kit-template-{selected_ai}-{selected_script}-{version}.zip"
        if not zip_path.exists():
            if tracker:
                tracker.error("scaffold", f"missing generated package: {zip_path.name}")
            return False

        project_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(project_path)

    if tracker:
        tracker.complete("scaffold", "bundled assets copied")
    return True

SCRIPT_TYPE_CHOICES = {"sh": "POSIX Shell (bash/zsh)", "ps": "PowerShell"}

CLAUDE_LOCAL_PATH = Path.home() / ".claude" / "local" / "claude"
CLAUDE_NPM_LOCAL_PATH = Path.home() / ".claude" / "local" / "node_modules" / ".bin" / "claude"

BANNER = """
███████╗██████╗ ███████╗ ██████╗██╗███████╗██╗   ██╗
██╔════╝██╔══██╗██╔════╝██╔════╝██║██╔════╝╚██╗ ██╔╝
███████╗██████╔╝█████╗  ██║     ██║█████╗   ╚████╔╝ 
╚════██║██╔═══╝ ██╔══╝  ██║     ██║██╔══╝    ╚██╔╝  
███████║██║     ███████╗╚██████╗██║██║        ██║   
╚══════╝╚═╝     ╚══════╝ ╚═════╝╚═╝╚═╝        ╚═╝   
"""

TAGLINE = "GitHub Spec Kit - Spec-Driven Development Toolkit"
class StepTracker:
    """Track and render hierarchical steps without emojis, similar to Claude Code tree output.
    Supports live auto-refresh via an attached refresh callback.
    """
    def __init__(self, title: str):
        self.title = title
        self.steps = []  # list of dicts: {key, label, status, detail}
        self.status_order = {"pending": 0, "running": 1, "done": 2, "error": 3, "skipped": 4}
        self._refresh_cb = None  # callable to trigger UI refresh

    def attach_refresh(self, cb):
        self._refresh_cb = cb

    def add(self, key: str, label: str):
        if key not in [s["key"] for s in self.steps]:
            self.steps.append({"key": key, "label": label, "status": "pending", "detail": ""})
            self._maybe_refresh()

    def start(self, key: str, detail: str = ""):
        self._update(key, status="running", detail=detail)

    def complete(self, key: str, detail: str = ""):
        self._update(key, status="done", detail=detail)

    def error(self, key: str, detail: str = ""):
        self._update(key, status="error", detail=detail)

    def skip(self, key: str, detail: str = ""):
        self._update(key, status="skipped", detail=detail)

    def _update(self, key: str, status: str, detail: str):
        for s in self.steps:
            if s["key"] == key:
                s["status"] = status
                if detail:
                    s["detail"] = detail
                self._maybe_refresh()
                return

        self.steps.append({"key": key, "label": key, "status": status, "detail": detail})
        self._maybe_refresh()

    def _maybe_refresh(self):
        if self._refresh_cb:
            try:
                self._refresh_cb()
            except Exception:
                pass

    def render(self):
        tree = Tree(f"[cyan]{self.title}[/cyan]", guide_style="grey50")
        for step in self.steps:
            label = step["label"]
            detail_text = step["detail"].strip() if step["detail"] else ""

            status = step["status"]
            if status == "done":
                symbol = "[green]●[/green]"
            elif status == "pending":
                symbol = "[green dim]○[/green dim]"
            elif status == "running":
                symbol = "[cyan]○[/cyan]"
            elif status == "error":
                symbol = "[red]●[/red]"
            elif status == "skipped":
                symbol = "[yellow]○[/yellow]"
            else:
                symbol = " "

            if status == "pending":
                # Entire line light gray (pending)
                if detail_text:
                    line = f"{symbol} [bright_black]{label} ({detail_text})[/bright_black]"
                else:
                    line = f"{symbol} [bright_black]{label}[/bright_black]"
            else:
                # Label white, detail (if any) light gray in parentheses
                if detail_text:
                    line = f"{symbol} [white]{label}[/white] [bright_black]({detail_text})[/bright_black]"
                else:
                    line = f"{symbol} [white]{label}[/white]"

            tree.add(line)
        return tree

def get_key():
    """Get a single keypress in a cross-platform way using readchar."""
    key = readchar.readkey()

    if key == readchar.key.UP or key == readchar.key.CTRL_P:
        return 'up'
    if key == readchar.key.DOWN or key == readchar.key.CTRL_N:
        return 'down'

    if key == readchar.key.ENTER:
        return 'enter'

    if key == readchar.key.ESC:
        return 'escape'

    if key == readchar.key.CTRL_C:
        raise KeyboardInterrupt

    return key

def select_with_arrows(options: dict, prompt_text: str = "Select an option", default_key: str = None) -> str:
    """
    Interactive selection using arrow keys with Rich Live display.
    
    Args:
        options: Dict with keys as option keys and values as descriptions
        prompt_text: Text to show above the options
        default_key: Default option key to start with
        
    Returns:
        Selected option key
    """
    option_keys = list(options.keys())
    if default_key and default_key in option_keys:
        selected_index = option_keys.index(default_key)
    else:
        selected_index = 0

    selected_key = None

    def create_selection_panel():
        """Create the selection panel with current selection highlighted."""
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="left", width=3)
        table.add_column(style="white", justify="left")

        for i, key in enumerate(option_keys):
            if i == selected_index:
                table.add_row("▶", f"[cyan]{key}[/cyan] [dim]({options[key]})[/dim]")
            else:
                table.add_row(" ", f"[cyan]{key}[/cyan] [dim]({options[key]})[/dim]")

        table.add_row("", "")
        table.add_row("", "[dim]Use ↑/↓ to navigate, Enter to select, Esc to cancel[/dim]")

        return Panel(
            table,
            title=f"[bold]{prompt_text}[/bold]",
            border_style="cyan",
            padding=(1, 2)
        )

    console.print()

    def run_selection_loop():
        nonlocal selected_key, selected_index
        with Live(create_selection_panel(), console=console, transient=True, auto_refresh=False) as live:
            while True:
                try:
                    key = get_key()
                    if key == 'up':
                        selected_index = (selected_index - 1) % len(option_keys)
                    elif key == 'down':
                        selected_index = (selected_index + 1) % len(option_keys)
                    elif key == 'enter':
                        selected_key = option_keys[selected_index]
                        break
                    elif key == 'escape':
                        console.print("\n[yellow]Selection cancelled[/yellow]")
                        raise typer.Exit(1)

                    live.update(create_selection_panel(), refresh=True)

                except KeyboardInterrupt:
                    console.print("\n[yellow]Selection cancelled[/yellow]")
                    raise typer.Exit(1)

    run_selection_loop()

    if selected_key is None:
        console.print("\n[red]Selection failed.[/red]")
        raise typer.Exit(1)

    return selected_key

console = Console()

class BannerGroup(TyperGroup):
    """Custom group that shows banner before help."""

    def format_help(self, ctx, formatter):
        # Show banner before help
        show_banner()
        super().format_help(ctx, formatter)


app = typer.Typer(
    name="specify",
    help="Setup tool for Specify spec-driven development projects",
    add_completion=False,
    invoke_without_command=True,
    cls=BannerGroup,
)

def show_banner():
    """Display the ASCII art banner."""
    banner_lines = BANNER.strip().split('\n')
    colors = ["bright_blue", "blue", "cyan", "bright_cyan", "white", "bright_white"]

    styled_banner = Text()
    for i, line in enumerate(banner_lines):
        color = colors[i % len(colors)]
        styled_banner.append(line + "\n", style=color)

    console.print(Align.center(styled_banner))
    console.print(Align.center(Text(TAGLINE, style="italic bright_yellow")))
    console.print()

@app.callback()
def callback(ctx: typer.Context):
    """Show banner when no subcommand is provided."""
    if ctx.invoked_subcommand is None and "--help" not in sys.argv and "-h" not in sys.argv:
        show_banner()
        console.print(Align.center("[dim]Run 'specify --help' for usage information[/dim]"))
        console.print()

def run_command(cmd: list[str], check_return: bool = True, capture: bool = False, shell: bool = False) -> Optional[str]:
    """Run a shell command and optionally capture output."""
    try:
        if capture:
            result = subprocess.run(cmd, check=check_return, capture_output=True, text=True, shell=shell)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, check=check_return, shell=shell)
            return None
    except subprocess.CalledProcessError as e:
        if check_return:
            console.print(f"[red]Error running command:[/red] {' '.join(cmd)}")
            console.print(f"[red]Exit code:[/red] {e.returncode}")
            if hasattr(e, 'stderr') and e.stderr:
                console.print(f"[red]Error output:[/red] {e.stderr}")
            raise
        return None

def check_tool(tool: str, tracker: StepTracker = None) -> bool:
    """Check if a tool is installed. Optionally update tracker.
    
    Args:
        tool: Name of the tool to check
        tracker: Optional StepTracker to update with results
        
    Returns:
        True if tool is found, False otherwise
    """
    # Special handling for Claude CLI after `claude migrate-installer`
    # See: https://github.com/github/spec-kit/issues/123
    # The migrate-installer command REMOVES the original executable from PATH
    # and creates an alias at ~/.claude/local/claude instead
    # This path should be prioritized over other claude executables in PATH
    if tool == "claude":
        if (
            (CLAUDE_LOCAL_PATH.exists() and CLAUDE_LOCAL_PATH.is_file())
            or (CLAUDE_NPM_LOCAL_PATH.exists() and CLAUDE_NPM_LOCAL_PATH.is_file())
        ):
            if tracker:
                tracker.complete(tool, "available")
            return True
    
    if tool == "kiro-cli":
        # Kiro currently supports both executable names. Prefer kiro-cli and
        # accept kiro as a compatibility fallback.
        found = shutil.which("kiro-cli") is not None or shutil.which("kiro") is not None
    else:
        found = shutil.which(tool) is not None
    
    if tracker:
        if found:
            tracker.complete(tool, "available")
        else:
            tracker.error(tool, "not found")
    
    return found

def is_git_repo(path: Path = None) -> bool:
    """Check if the specified path is inside a git repository."""
    if path is None:
        path = Path.cwd()
    
    if not path.is_dir():
        return False

    try:
        # Use git command to check if inside a work tree
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            cwd=path,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def init_git_repo(project_path: Path, quiet: bool = False) -> Tuple[bool, Optional[str]]:
    """Initialize a git repository in the specified path.
    
    Args:
        project_path: Path to initialize git repository in
        quiet: if True suppress console output (tracker handles status)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        original_cwd = Path.cwd()
        os.chdir(project_path)
        if not quiet:
            console.print("[cyan]Initializing git repository...[/cyan]")
        subprocess.run(["git", "init"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "Initial commit from Specify template"], check=True, capture_output=True, text=True)
        if not quiet:
            console.print("[green]✓[/green] Git repository initialized")
        return True, None

    except subprocess.CalledProcessError as e:
        error_msg = f"Command: {' '.join(e.cmd)}\nExit code: {e.returncode}"
        if e.stderr:
            error_msg += f"\nError: {e.stderr.strip()}"
        elif e.stdout:
            error_msg += f"\nOutput: {e.stdout.strip()}"
        
        if not quiet:
            console.print(f"[red]Error initializing git repository:[/red] {e}")
        return False, error_msg
    finally:
        os.chdir(original_cwd)


@app.command()
def init(
    project_name: str = typer.Argument(None, help="Name for your new project directory (optional if using --here, or use '.' for current directory)"),
    ai_assistant: str = typer.Option(None, "--ai", help=AI_ASSISTANT_HELP),
    ai_commands_dir: str = typer.Option(None, "--ai-commands-dir", help="Directory for agent command files (required with --ai generic, e.g. .myagent/commands/)"),
    script_type: str = typer.Option(None, "--script", help="Script type to use: sh or ps"),
    ignore_agent_tools: bool = typer.Option(False, "--ignore-agent-tools", help="Skip checks for AI agent tools like Claude Code"),
    no_git: bool = typer.Option(False, "--no-git", help="Skip git repository initialization"),
    here: bool = typer.Option(False, "--here", help="Initialize project in the current directory instead of creating a new one"),
    force: bool = typer.Option(False, "--force", help="Force merge/overwrite when using --here (skip confirmation)"),
    skip_tls: bool = typer.Option(False, "--skip-tls", help="Skip SSL/TLS verification (not recommended)"),
    debug: bool = typer.Option(False, "--debug", help="Show verbose diagnostic output for network and extraction failures"),
    github_token: str = typer.Option(None, "--github-token", help="GitHub token to use for API requests (or set GH_TOKEN or GITHUB_TOKEN environment variable)"),
    ai_skills: bool = typer.Option(False, "--ai-skills", help="Install Prompt.MD templates as agent skills (requires --ai)"),
    offline: bool = typer.Option(False, "--offline", help="Use bundled assets instead of downloading from GitHub (no network access required)"),
    preset: str = typer.Option(None, "--preset", help="Install a preset during initialization (by preset ID)"),
    branch_numbering: str = typer.Option(None, "--branch-numbering", help="Branch numbering strategy: 'sequential' (001, 002, ...) or 'timestamp' (YYYYMMDD-HHMMSS)"),
):
    """
    Initialize a new Specify project from the latest template.
    
    This command will:
    1. Check that required tools are installed (git is optional)
    2. Let you choose your AI assistant
    3. Download the appropriate template from GitHub (or use bundled assets with --offline)
    4. Extract the template to a new project directory or current directory
    5. Initialize a fresh git repository (if not --no-git and no existing repo)
    6. Optionally set up AI assistant commands
    
    Examples:
        specify init my-project
        specify init my-project --ai claude
        specify init my-project --ai copilot --no-git
        specify init --ignore-agent-tools my-project
        specify init . --ai claude         # Initialize in current directory
        specify init .                     # Initialize in current directory (interactive AI selection)
        specify init --here --ai claude    # Alternative syntax for current directory
        specify init --here --ai codex
        specify init --here --ai codebuddy
        specify init --here --ai vibe      # Initialize with Mistral Vibe support
        specify init --here
        specify init --here --force  # Skip confirmation when current directory not empty
        specify init my-project --ai claude --ai-skills   # Install agent skills
        specify init --here --ai gemini --ai-skills
        specify init my-project --ai generic --ai-commands-dir .myagent/commands/  # Unsupported agent
        specify init my-project --offline  # Use bundled assets (no network access)
        specify init my-project --ai claude --preset healthcare-compliance  # With preset
    """

    show_banner()

    validate_raw_option_values(ai_assistant, ai_commands_dir, console, AGENT_CONFIG)

    if ai_skills and not ai_assistant:
        console.print("[red]Error:[/red] --ai-skills requires --ai to be specified")
        console.print("[yellow]Usage:[/yellow] specify init <project> --ai <agent> --ai-skills")
        raise typer.Exit(1)

    BRANCH_NUMBERING_CHOICES = {"sequential", "timestamp"}
    if branch_numbering and branch_numbering not in BRANCH_NUMBERING_CHOICES:
        console.print(
            f"[red]Error:[/red] Invalid --branch-numbering value '{branch_numbering}'. "
            f"Choose from: {', '.join(sorted(BRANCH_NUMBERING_CHOICES))}"
        )
        raise typer.Exit(1)

    init_target = resolve_project_target(project_name, here, force, console, confirm=typer.confirm)
    project_name = init_target.project_name
    project_path = init_target.project_path
    here = init_target.here

    selected_ai, ai_skills = resolve_ai_selection(
        ai_assistant,
        ai_skills,
        ai_commands_dir,
        console,
        AGENT_CONFIG,
        aliases=AI_ASSISTANT_ALIASES,
        select_fn=select_with_arrows,
        resolve_ai_skills_mode_fn=resolve_ai_skills_mode,
    )

    current_dir = Path.cwd()

    setup_lines = [
        "[cyan]Specify Project Setup[/cyan]",
        "",
        f"{'Project':<15} [green]{project_path.name}[/green]",
        f"{'Working Path':<15} [dim]{current_dir}[/dim]",
    ]

    if not here:
        setup_lines.append(f"{'Target Path':<15} [dim]{project_path}[/dim]")

    console.print(Panel("\n".join(setup_lines), border_style="cyan", padding=(1, 2)))

    should_init_git = False
    if not no_git:
        should_init_git = check_tool("git")
        if not should_init_git:
            console.print("[yellow]Git not found - will skip repository initialization[/yellow]")

    if not ignore_agent_tools:
        agent_config = AGENT_CONFIG.get(selected_ai)
        if agent_config and agent_config["requires_cli"]:
            install_url = agent_config["install_url"]
            if not check_tool(selected_ai):
                error_panel = Panel(
                    f"[cyan]{selected_ai}[/cyan] not found\n"
                    f"Install from: [cyan]{install_url}[/cyan]\n"
                    f"{agent_config['name']} is required to continue with this project type.\n\n"
                    "Tip: Use [cyan]--ignore-agent-tools[/cyan] to skip this check",
                    title="[red]Agent Detection Error[/red]",
                    border_style="red",
                    padding=(1, 2)
                )
                console.print()
                console.print(error_panel)
                raise typer.Exit(1)

    selected_script = resolve_script_selection(
        script_type,
        SCRIPT_TYPE_CHOICES,
        console,
        select_fn=select_with_arrows,
    )

    console.print(f"[cyan]Selected AI assistant:[/cyan] {selected_ai}")
    console.print(f"[cyan]Selected script type:[/cyan] {selected_script}")

    tracker = build_init_tracker(
        selected_ai,
        selected_script,
        ai_skills,
        tracker_cls=StepTracker,
    )
    use_github = not offline
    if not use_github:
        tracker.add("scaffold", "Apply bundled assets")
        for key in ("fetch", "download", "extract", "zip-list", "extracted-summary"):
            tracker.skip(key, "--offline")

    sys._specify_tracker_active = True

    # Track git error message outside Live context so it persists
    git_error_message = None

    with Live(tracker.render(), console=console, refresh_per_second=8, transient=True) as live:
        tracker.attach_refresh(lambda: live.update(tracker.render()))
        try:
            verify = not skip_tls
            local_ssl_context = ssl_context if verify else False
            if use_github:
                with httpx.Client(verify=local_ssl_context) as local_client:
                    download_and_extract_template(
                        project_path,
                        selected_ai,
                        selected_script,
                        here,
                        skip_legacy_codex_prompts=(selected_ai == "codex" and ai_skills),
                        verbose=False,
                        tracker=tracker,
                        client=local_client,
                        debug=debug,
                        github_token=github_token,
                    )
            else:
                scaffold_ok = scaffold_from_core_pack(project_path, selected_ai, selected_script, here=here, tracker=tracker)
                if not scaffold_ok:
                    if not here and project_path.exists():
                        shutil.rmtree(project_path)
                    raise typer.Exit(1)

            relocate_generic_commands_dir(project_path, selected_ai, ai_commands_dir, tracker)

            ensure_executable_scripts(project_path, tracker=tracker)

            ensure_constitution_from_template(project_path, tracker=tracker)

            migrated_legacy_kimi_skills = 0
            removed_legacy_kimi_skills = 0
            skills_dir: Optional[Path] = None
            if selected_ai in NATIVE_SKILLS_AGENTS:
                skills_dir = _get_skills_dir(project_path, selected_ai)
                if selected_ai == "kimi" and skills_dir.is_dir():
                    (
                        migrated_legacy_kimi_skills,
                        removed_legacy_kimi_skills,
                    ) = _migrate_legacy_kimi_dotted_skills(skills_dir)

            if ai_skills:
                if selected_ai in NATIVE_SKILLS_AGENTS:
                    bundled_found = _has_bundled_skills(project_path, selected_ai)
                    if bundled_found:
                        detail = f"bundled skills → {skills_dir.relative_to(project_path)}"
                        if migrated_legacy_kimi_skills or removed_legacy_kimi_skills:
                            detail += (
                                f" (migrated {migrated_legacy_kimi_skills}, "
                                f"removed {removed_legacy_kimi_skills} legacy Kimi dotted skills)"
                            )
                        tracker.start("ai-skills")
                        tracker.complete("ai-skills", detail)
                    else:
                        fallback_ok = install_ai_skills(
                            project_path,
                            selected_ai,
                            tracker=tracker,
                            console=console,
                            overwrite_existing=True,
                        )
                        if not fallback_ok:
                            expected_dir = _get_skills_dir(project_path, selected_ai)
                            raise RuntimeError(
                                f"Expected bundled agent skills in {expected_dir.relative_to(project_path)}, "
                                "but none were found and fallback conversion failed. "
                                "Re-run with an up-to-date template."
                            )
                else:
                    skills_ok = install_ai_skills(
                        project_path,
                        selected_ai,
                        tracker=tracker,
                        console=console,
                    )

                    # When --ai-skills is used on a NEW project and skills were
                    # successfully installed, remove the command files that the
                    # template archive just created.  Skills replace commands, so
                    # keeping both would be confusing.  For --here on an existing
                    # repo we leave pre-existing commands untouched to avoid a
                    # breaking change.  We only delete AFTER skills succeed so the
                    # project always has at least one of {commands, skills}.
                    if skills_ok:
                        cleanup_extracted_commands_after_skill_install(
                            project_path,
                            selected_ai,
                            keep_existing_commands=here,
                            console=console,
                        )

            if not no_git:
                tracker.start("git")
                if is_git_repo(project_path):
                    tracker.complete("git", "existing repo detected")
                elif should_init_git:
                    success, error_msg = init_git_repo(project_path, quiet=True)
                    if success:
                        tracker.complete("git", "initialized")
                    else:
                        tracker.error("git", "init failed")
                        git_error_message = error_msg
                else:
                    tracker.skip("git", "git not available")
            else:
                tracker.skip("git", "--no-git flag")

            # Persist the CLI options so later operations (e.g. preset add)
            # can adapt their behaviour without re-scanning the filesystem.
            # Must be saved BEFORE preset install so _get_skills_dir() works.
            speckit_version = get_speckit_version()
            persist_init_options(
                project_path,
                selected_ai=selected_ai,
                ai_skills=ai_skills,
                ai_commands_dir=ai_commands_dir,
                here=here,
                preset=preset,
                selected_script=selected_script,
                speckit_version=speckit_version,
                branch_numbering=branch_numbering or "sequential",
                offline=offline,
                save_init_options_fn=save_init_options,
            )
            install_requested_preset(project_path, preset, speckit_version, console)

            if not use_github:
                tracker.skip("cleanup", "not needed (no download)")

            tracker.complete("final", "project ready")
        except Exception as e:
            tracker.error("final", str(e))
            console.print(Panel(f"Initialization failed: {e}", title="Failure", border_style="red"))
            if debug:
                _env_pairs = [
                    ("Python", sys.version.split()[0]),
                    ("Platform", sys.platform),
                    ("CWD", str(Path.cwd())),
                ]
                _label_width = max(len(k) for k, _ in _env_pairs)
                env_lines = [f"{k.ljust(_label_width)} → [bright_black]{v}[/bright_black]" for k, v in _env_pairs]
                console.print(Panel("\n".join(env_lines), title="Debug Environment", border_style="magenta"))
            if not here and project_path.exists():
                shutil.rmtree(project_path)
            raise typer.Exit(1)
        finally:
            pass

    console.print(tracker.render())
    console.print("\n[bold green]Project ready.[/bold green]")
    
    # Show git error details if initialization failed
    if git_error_message:
        console.print()
        git_error_panel = Panel(
            f"[yellow]Warning:[/yellow] Git repository initialization failed\n\n"
            f"{git_error_message}\n\n"
            f"[dim]You can initialize git manually later with:[/dim]\n"
            f"[cyan]cd {project_path if not here else '.'}[/cyan]\n"
            f"[cyan]git init[/cyan]\n"
            f"[cyan]git add .[/cyan]\n"
            f"[cyan]git commit -m \"Initial commit\"[/cyan]",
            title="[red]Git Initialization Failed[/red]",
            border_style="red",
            padding=(1, 2)
        )
        console.print(git_error_panel)

    # Agent folder security notice
    agent_config = AGENT_CONFIG.get(selected_ai)
    if agent_config:
        agent_folder = ai_commands_dir if selected_ai == "generic" else agent_config["folder"]
        if agent_folder:
            security_notice = Panel(
                build_agent_folder_security_notice(agent_folder),
                title="[yellow]Agent Folder Security[/yellow]",
                border_style="yellow",
                padding=(1, 2)
            )
            console.print()
            console.print(security_notice)

    steps_lines = build_next_steps_lines(selected_ai, here, project_name)
    steps_panel = Panel("\n".join(steps_lines), title="Next Steps", border_style="cyan", padding=(1,2))
    console.print()
    console.print(steps_panel)

    enhancement_lines = build_enhancement_panel_lines(selected_ai)
    enhancements_panel = Panel("\n".join(enhancement_lines), title="Enhancement Commands", border_style="cyan", padding=(1,2))
    console.print()
    console.print(enhancements_panel)

@app.command()
def check():
    """Check that all required tools are installed."""
    show_banner()
    console.print("[bold]Checking for installed tools...[/bold]\n")

    tracker = StepTracker("Check Available Tools")

    tracker.add("git", "Git version control")
    git_ok = check_tool("git", tracker=tracker)

    agent_results = {}
    for agent_key, agent_config in AGENT_CONFIG.items():
        if agent_key == "generic":
            continue  # Generic is not a real agent to check
        agent_name = agent_config["name"]
        requires_cli = agent_config["requires_cli"]

        tracker.add(agent_key, agent_name)

        if requires_cli:
            agent_results[agent_key] = check_tool(agent_key, tracker=tracker)
        else:
            # IDE-based agent - skip CLI check and mark as optional
            tracker.skip(agent_key, "IDE-based, no CLI check")
            agent_results[agent_key] = False  # Don't count IDE agents as "found"

    # Check VS Code variants (not in agent config)
    tracker.add("code", "Visual Studio Code")
    check_tool("code", tracker=tracker)

    tracker.add("code-insiders", "Visual Studio Code Insiders")
    check_tool("code-insiders", tracker=tracker)

    console.print(tracker.render())

    console.print("\n[bold green]Specify CLI is ready to use![/bold green]")

    if not git_ok:
        console.print("[dim]Tip: Install git for repository management[/dim]")

    if not any(agent_results.values()):
        console.print("[dim]Tip: Install an AI assistant for the best experience[/dim]")


@app.command("lint-commands")
def lint_commands(
    repo_root: str = typer.Option(
        ".",
        "--repo-root",
        help="Repository root containing templates/commands, scripts, and release workflows",
    )
):
    """Lint enhanced command templates and release mapping consistency."""
    from .command_lint import lint_repository

    show_banner()
    root = Path(repo_root).resolve()
    console.print(f"[bold]Linting command templates in:[/bold] [cyan]{root}[/cyan]\n")

    result = lint_repository(root)

    if result.warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  • {warning}")
        console.print()

    if result.errors:
        console.print("[red]Errors:[/red]")
        for error in result.errors:
            console.print(f"  • {error}")
        raise typer.Exit(1)

    console.print("[bold green]Command template lint passed.[/bold green]")


@app.command()
def version():
    """Display version and system information."""
    import platform
    import importlib.metadata
    
    show_banner()
    
    # Get CLI version from package metadata
    cli_version = "unknown"
    try:
        cli_version = importlib.metadata.version("specify-cli")
    except Exception:
        # Fallback: try reading from pyproject.toml if running from source
        try:
            import tomllib
            pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    cli_version = data.get("project", {}).get("version", "unknown")
        except Exception:
            pass
    
    # Fetch latest template release version
    repo_owner = "Z-WICK"
    repo_name = "spec-kit"
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    
    template_version = "unknown"
    release_date = "unknown"
    
    try:
        response = client.get(
            api_url,
            timeout=10,
            follow_redirects=True,
            headers=_github_auth_headers(),
        )
        if response.status_code == 200:
            release_data = response.json()
            template_version = release_data.get("tag_name", "unknown")
            # Remove 'v' prefix if present
            if template_version.startswith("v"):
                template_version = template_version[1:]
            release_date = release_data.get("published_at", "unknown")
            if release_date != "unknown":
                # Format the date nicely
                try:
                    dt = datetime.fromisoformat(release_date.replace('Z', '+00:00'))
                    release_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    pass
    except Exception:
        pass

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Key", style="cyan", justify="right")
    info_table.add_column("Value", style="white")

    info_table.add_row("CLI Version", cli_version)
    info_table.add_row("Template Version", template_version)
    info_table.add_row("Released", release_date)
    info_table.add_row("", "")
    info_table.add_row("Python", platform.python_version())
    info_table.add_row("Platform", platform.system())
    info_table.add_row("Architecture", platform.machine())
    info_table.add_row("OS Version", platform.version())

    panel = Panel(
        info_table,
        title="[bold cyan]Specify CLI Information[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )

    console.print(panel)
    console.print()


# ===== Extension Commands =====

extension_app = typer.Typer(
    name="extension",
    help="Manage spec-kit extensions",
    add_completion=False,
)
app.add_typer(extension_app, name="extension")

catalog_app = typer.Typer(
    name="catalog",
    help="Manage extension catalogs",
    add_completion=False,
)
extension_app.add_typer(catalog_app, name="catalog")

preset_app = typer.Typer(
    name="preset",
    help="Manage spec-kit presets",
    add_completion=False,
)
app.add_typer(preset_app, name="preset")

preset_catalog_app = typer.Typer(
    name="catalog",
    help="Manage preset catalogs",
    add_completion=False,
)
preset_app.add_typer(preset_catalog_app, name="catalog")


def get_speckit_version() -> str:
    """Get current spec-kit version."""
    import importlib.metadata
    try:
        return importlib.metadata.version("specify-cli")
    except Exception:
        # Fallback: try reading from pyproject.toml
        try:
            import tomllib
            pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    return data.get("project", {}).get("version", "unknown")
        except Exception:
            # Intentionally ignore any errors while reading/parsing pyproject.toml.
            # If this lookup fails for any reason, we fall back to returning "unknown" below.
            pass
    return "unknown"


# ===== Preset Commands =====


@preset_app.command("list")
def preset_list():
    """List installed presets."""
    from .presets import PresetManager

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = PresetManager(project_root)
    installed = manager.list_installed()

    if not installed:
        console.print("[yellow]No presets installed.[/yellow]")
        console.print("\nInstall a preset with:")
        console.print("  [cyan]specify preset add <pack-name>[/cyan]")
        return

    console.print("\n[bold cyan]Installed Presets:[/bold cyan]\n")
    for pack in installed:
        status = "[green]enabled[/green]" if pack.get("enabled", True) else "[red]disabled[/red]"
        pri = pack.get('priority', 10)
        console.print(f"  [bold]{pack['name']}[/bold] ({pack['id']}) v{pack['version']} — {status} — priority {pri}")
        console.print(f"    {pack['description']}")
        if pack.get("tags"):
            tags_str = ", ".join(pack["tags"])
            console.print(f"    [dim]Tags: {tags_str}[/dim]")
        console.print(f"    [dim]Templates: {pack['template_count']}[/dim]")
        console.print()


@preset_app.command("add")
def preset_add(
    pack_id: str = typer.Argument(None, help="Preset ID to install from catalog"),
    from_url: str = typer.Option(None, "--from", help="Install from a URL (ZIP file)"),
    dev: str = typer.Option(None, "--dev", help="Install from local directory (development mode)"),
    priority: int = typer.Option(10, "--priority", help="Resolution priority (lower = higher precedence, default 10)"),
):
    """Install a preset."""
    from .presets import (
        PresetManager,
        PresetCatalog,
        PresetError,
        PresetValidationError,
        PresetCompatibilityError,
    )

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = PresetManager(project_root)
    speckit_version = get_speckit_version()

    try:
        if dev:
            dev_path = Path(dev).resolve()
            if not dev_path.exists():
                console.print(f"[red]Error:[/red] Directory not found: {dev}")
                raise typer.Exit(1)

            console.print(f"Installing preset from [cyan]{dev_path}[/cyan]...")
            manifest = manager.install_from_directory(dev_path, speckit_version, priority)
            console.print(f"[green]✓[/green] Preset '{manifest.name}' v{manifest.version} installed (priority {priority})")

        elif from_url:
            # Validate URL scheme before downloading
            from urllib.parse import urlparse as _urlparse
            _parsed = _urlparse(from_url)
            _is_localhost = _parsed.hostname in ("localhost", "127.0.0.1", "::1")
            if _parsed.scheme != "https" and not (_parsed.scheme == "http" and _is_localhost):
                console.print(f"[red]Error:[/red] URL must use HTTPS (got {_parsed.scheme}://). HTTP is only allowed for localhost.")
                raise typer.Exit(1)

            console.print(f"Installing preset from [cyan]{from_url}[/cyan]...")
            import urllib.request
            import urllib.error
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = Path(tmpdir) / "preset.zip"
                try:
                    with urllib.request.urlopen(from_url, timeout=60) as response:
                        zip_path.write_bytes(response.read())
                except urllib.error.URLError as e:
                    console.print(f"[red]Error:[/red] Failed to download: {e}")
                    raise typer.Exit(1)

                manifest = manager.install_from_zip(zip_path, speckit_version, priority)

            console.print(f"[green]✓[/green] Preset '{manifest.name}' v{manifest.version} installed (priority {priority})")

        elif pack_id:
            catalog = PresetCatalog(project_root)
            pack_info = catalog.get_pack_info(pack_id)

            if not pack_info:
                console.print(f"[red]Error:[/red] Preset '{pack_id}' not found in catalog")
                raise typer.Exit(1)

            if not pack_info.get("_install_allowed", True):
                catalog_name = pack_info.get("_catalog_name", "unknown")
                console.print(f"[red]Error:[/red] Preset '{pack_id}' is from the '{catalog_name}' catalog which is discovery-only (install not allowed).")
                console.print("Add the catalog with --install-allowed or install from the preset's repository directly with --from.")
                raise typer.Exit(1)

            console.print(f"Installing preset [cyan]{pack_info.get('name', pack_id)}[/cyan]...")

            try:
                zip_path = catalog.download_pack(pack_id)
                manifest = manager.install_from_zip(zip_path, speckit_version, priority)
                console.print(f"[green]✓[/green] Preset '{manifest.name}' v{manifest.version} installed (priority {priority})")
            finally:
                if 'zip_path' in locals() and zip_path.exists():
                    zip_path.unlink(missing_ok=True)
        else:
            console.print("[red]Error:[/red] Specify a preset ID, --from URL, or --dev path")
            raise typer.Exit(1)

    except PresetCompatibilityError as e:
        console.print(f"[red]Compatibility Error:[/red] {e}")
        raise typer.Exit(1)
    except PresetValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        raise typer.Exit(1)
    except PresetError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@preset_app.command("remove")
def preset_remove(
    pack_id: str = typer.Argument(..., help="Preset ID to remove"),
):
    """Remove an installed preset."""
    from .presets import PresetManager

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = PresetManager(project_root)

    if not manager.registry.is_installed(pack_id):
        console.print(f"[red]Error:[/red] Preset '{pack_id}' is not installed")
        raise typer.Exit(1)

    if manager.remove(pack_id):
        console.print(f"[green]✓[/green] Preset '{pack_id}' removed successfully")
    else:
        console.print(f"[red]Error:[/red] Failed to remove preset '{pack_id}'")
        raise typer.Exit(1)


@preset_app.command("search")
def preset_search(
    query: str = typer.Argument(None, help="Search query"),
    tag: str = typer.Option(None, "--tag", help="Filter by tag"),
    author: str = typer.Option(None, "--author", help="Filter by author"),
):
    """Search for presets in the catalog."""
    from .presets import PresetCatalog, PresetError

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    catalog = PresetCatalog(project_root)

    try:
        results = catalog.search(query=query, tag=tag, author=author)
    except PresetError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not results:
        console.print("[yellow]No presets found matching your criteria.[/yellow]")
        return

    console.print(f"\n[bold cyan]Presets ({len(results)} found):[/bold cyan]\n")
    for pack in results:
        console.print(f"  [bold]{pack.get('name', pack['id'])}[/bold] ({pack['id']}) v{pack.get('version', '?')}")
        console.print(f"    {pack.get('description', '')}")
        if pack.get("tags"):
            tags_str = ", ".join(pack["tags"])
            console.print(f"    [dim]Tags: {tags_str}[/dim]")
        console.print()


@preset_app.command("resolve")
def preset_resolve(
    template_name: str = typer.Argument(..., help="Template name to resolve (e.g., spec-template)"),
):
    """Show which template will be resolved for a given name."""
    from .presets import PresetResolver

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    resolver = PresetResolver(project_root)
    result = resolver.resolve_with_source(template_name)

    if result:
        console.print(f"  [bold]{template_name}[/bold]: {result['path']}")
        console.print(f"    [dim](from: {result['source']})[/dim]")
    else:
        console.print(f"  [yellow]{template_name}[/yellow]: not found")
        console.print("    [dim]No template with this name exists in the resolution stack[/dim]")


@preset_app.command("info")
def preset_info(
    pack_id: str = typer.Argument(..., help="Preset ID to get info about"),
):
    """Show detailed information about a preset."""
    from .presets import PresetCatalog, PresetManager, PresetError

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    # Check if installed locally first
    manager = PresetManager(project_root)
    local_pack = manager.get_pack(pack_id)

    if local_pack:
        console.print(f"\n[bold cyan]Preset: {local_pack.name}[/bold cyan]\n")
        console.print(f"  ID:          {local_pack.id}")
        console.print(f"  Version:     {local_pack.version}")
        console.print(f"  Description: {local_pack.description}")
        if local_pack.author:
            console.print(f"  Author:      {local_pack.author}")
        if local_pack.tags:
            console.print(f"  Tags:        {', '.join(local_pack.tags)}")
        console.print(f"  Templates:   {len(local_pack.templates)}")
        for tmpl in local_pack.templates:
            console.print(f"    - {tmpl['name']} ({tmpl['type']}): {tmpl.get('description', '')}")
        repo = local_pack.data.get("preset", {}).get("repository")
        if repo:
            console.print(f"  Repository:  {repo}")
        license_val = local_pack.data.get("preset", {}).get("license")
        if license_val:
            console.print(f"  License:     {license_val}")
        console.print("\n  [green]Status: installed[/green]")
        console.print()
        return

    # Fall back to catalog
    catalog = PresetCatalog(project_root)
    try:
        pack_info = catalog.get_pack_info(pack_id)
    except PresetError:
        pack_info = None

    if not pack_info:
        console.print(f"[red]Error:[/red] Preset '{pack_id}' not found (not installed and not in catalog)")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Preset: {pack_info.get('name', pack_id)}[/bold cyan]\n")
    console.print(f"  ID:          {pack_info['id']}")
    console.print(f"  Version:     {pack_info.get('version', '?')}")
    console.print(f"  Description: {pack_info.get('description', '')}")
    if pack_info.get("author"):
        console.print(f"  Author:      {pack_info['author']}")
    if pack_info.get("tags"):
        console.print(f"  Tags:        {', '.join(pack_info['tags'])}")
    if pack_info.get("repository"):
        console.print(f"  Repository:  {pack_info['repository']}")
    if pack_info.get("license"):
        console.print(f"  License:     {pack_info['license']}")
    console.print("\n  [yellow]Status: not installed[/yellow]")
    console.print(f"  Install with: [cyan]specify preset add {pack_id}[/cyan]")
    console.print()


@preset_app.command("set-priority")
def preset_set_priority(
    pack_id: str = typer.Argument(help="Preset ID"),
    priority: int = typer.Argument(help="New priority (lower = higher precedence)"),
):
    """Set the resolution priority of an installed preset."""
    from .extensions import normalize_priority
    from .presets import PresetManager

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    if priority < 1:
        console.print("[red]Error:[/red] Priority must be a positive integer (1 or higher)")
        raise typer.Exit(1)

    manager = PresetManager(project_root)

    if not manager.registry.is_installed(pack_id):
        console.print(f"[red]Error:[/red] Preset '{pack_id}' is not installed")
        raise typer.Exit(1)

    metadata = manager.registry.get(pack_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]Error:[/red] Preset '{pack_id}' not found in registry (corrupted state)")
        raise typer.Exit(1)

    raw_priority = metadata.get("priority")
    if isinstance(raw_priority, int) and raw_priority == priority:
        console.print(f"[yellow]Preset '{pack_id}' already has priority {priority}[/yellow]")
        raise typer.Exit(0)

    old_priority = normalize_priority(raw_priority)
    manager.registry.update(pack_id, {"priority": priority})

    console.print(f"[green]✓[/green] Preset '{pack_id}' priority changed: {old_priority} → {priority}")
    console.print("\n[dim]Lower priority = higher precedence in template resolution[/dim]")


@preset_app.command("enable")
def preset_enable(
    pack_id: str = typer.Argument(help="Preset ID to enable"),
):
    """Enable a disabled preset."""
    from .presets import PresetManager

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = PresetManager(project_root)

    if not manager.registry.is_installed(pack_id):
        console.print(f"[red]Error:[/red] Preset '{pack_id}' is not installed")
        raise typer.Exit(1)

    metadata = manager.registry.get(pack_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]Error:[/red] Preset '{pack_id}' not found in registry (corrupted state)")
        raise typer.Exit(1)

    if metadata.get("enabled", True):
        console.print(f"[yellow]Preset '{pack_id}' is already enabled[/yellow]")
        raise typer.Exit(0)

    manager.registry.update(pack_id, {"enabled": True})

    console.print(f"[green]✓[/green] Preset '{pack_id}' enabled")
    console.print("\nTemplates from this preset will now be included in resolution.")
    console.print("[dim]Note: Previously registered commands/skills remain active.[/dim]")


@preset_app.command("disable")
def preset_disable(
    pack_id: str = typer.Argument(help="Preset ID to disable"),
):
    """Disable a preset without removing it."""
    from .presets import PresetManager

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = PresetManager(project_root)

    if not manager.registry.is_installed(pack_id):
        console.print(f"[red]Error:[/red] Preset '{pack_id}' is not installed")
        raise typer.Exit(1)

    metadata = manager.registry.get(pack_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]Error:[/red] Preset '{pack_id}' not found in registry (corrupted state)")
        raise typer.Exit(1)

    if not metadata.get("enabled", True):
        console.print(f"[yellow]Preset '{pack_id}' is already disabled[/yellow]")
        raise typer.Exit(0)

    manager.registry.update(pack_id, {"enabled": False})

    console.print(f"[green]✓[/green] Preset '{pack_id}' disabled")
    console.print("\nTemplates from this preset will be skipped during resolution.")
    console.print("[dim]Note: Previously registered commands/skills remain active until preset removal.[/dim]")
    console.print(f"To re-enable: specify preset enable {pack_id}")


# ===== Preset Catalog Commands =====


@preset_catalog_app.command("list")
def preset_catalog_list():
    """List all active preset catalogs."""
    from .presets import PresetCatalog, PresetValidationError

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    catalog = PresetCatalog(project_root)

    try:
        active_catalogs = catalog.get_active_catalogs()
    except PresetValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print("\n[bold cyan]Active Preset Catalogs:[/bold cyan]\n")
    for entry in active_catalogs:
        install_str = (
            "[green]install allowed[/green]"
            if entry.install_allowed
            else "[yellow]discovery only[/yellow]"
        )
        console.print(f"  [bold]{entry.name}[/bold] (priority {entry.priority})")
        if entry.description:
            console.print(f"     {entry.description}")
        console.print(f"     URL: {entry.url}")
        console.print(f"     Install: {install_str}")
        console.print()

    config_path = project_root / ".specify" / "preset-catalogs.yml"
    user_config_path = Path.home() / ".specify" / "preset-catalogs.yml"
    if os.environ.get("SPECKIT_PRESET_CATALOG_URL"):
        console.print("[dim]Catalog configured via SPECKIT_PRESET_CATALOG_URL environment variable.[/dim]")
    else:
        try:
            proj_loaded = config_path.exists() and catalog._load_catalog_config(config_path) is not None
        except PresetValidationError:
            proj_loaded = False
        if proj_loaded:
            console.print(f"[dim]Config: {config_path.relative_to(project_root)}[/dim]")
        else:
            try:
                user_loaded = user_config_path.exists() and catalog._load_catalog_config(user_config_path) is not None
            except PresetValidationError:
                user_loaded = False
            if user_loaded:
                console.print("[dim]Config: ~/.specify/preset-catalogs.yml[/dim]")
            else:
                console.print("[dim]Using built-in default catalog stack.[/dim]")
                console.print(
                    "[dim]Add .specify/preset-catalogs.yml to customize.[/dim]"
                )


@preset_catalog_app.command("add")
def preset_catalog_add(
    url: str = typer.Argument(help="Catalog URL (must use HTTPS)"),
    name: str = typer.Option(..., "--name", help="Catalog name"),
    priority: int = typer.Option(10, "--priority", help="Priority (lower = higher priority)"),
    install_allowed: bool = typer.Option(
        False, "--install-allowed/--no-install-allowed",
        help="Allow presets from this catalog to be installed",
    ),
    description: str = typer.Option("", "--description", help="Description of the catalog"),
):
    """Add a catalog to .specify/preset-catalogs.yml."""
    from .presets import PresetCatalog, PresetValidationError

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    # Validate URL
    tmp_catalog = PresetCatalog(project_root)
    try:
        tmp_catalog._validate_catalog_url(url)
    except PresetValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    config_path = specify_dir / "preset-catalogs.yml"

    # Load existing config
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text()) or {}
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to read {config_path}: {e}")
            raise typer.Exit(1)
    else:
        config = {}

    catalogs = config.get("catalogs", [])
    if not isinstance(catalogs, list):
        console.print("[red]Error:[/red] Invalid catalog config: 'catalogs' must be a list.")
        raise typer.Exit(1)

    # Check for duplicate name
    for existing in catalogs:
        if isinstance(existing, dict) and existing.get("name") == name:
            console.print(f"[yellow]Warning:[/yellow] A catalog named '{name}' already exists.")
            console.print("Use 'specify preset catalog remove' first, or choose a different name.")
            raise typer.Exit(1)

    catalogs.append({
        "name": name,
        "url": url,
        "priority": priority,
        "install_allowed": install_allowed,
        "description": description,
    })

    config["catalogs"] = catalogs
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    install_label = "install allowed" if install_allowed else "discovery only"
    console.print(f"\n[green]✓[/green] Added catalog '[bold]{name}[/bold]' ({install_label})")
    console.print(f"  URL: {url}")
    console.print(f"  Priority: {priority}")
    console.print(f"\nConfig saved to {config_path.relative_to(project_root)}")


@preset_catalog_app.command("remove")
def preset_catalog_remove(
    name: str = typer.Argument(help="Catalog name to remove"),
):
    """Remove a catalog from .specify/preset-catalogs.yml."""
    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    config_path = specify_dir / "preset-catalogs.yml"
    if not config_path.exists():
        console.print("[red]Error:[/red] No preset catalog config found. Nothing to remove.")
        raise typer.Exit(1)

    try:
        config = yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        console.print("[red]Error:[/red] Failed to read preset catalog config.")
        raise typer.Exit(1)

    catalogs = config.get("catalogs", [])
    if not isinstance(catalogs, list):
        console.print("[red]Error:[/red] Invalid catalog config: 'catalogs' must be a list.")
        raise typer.Exit(1)
    original_count = len(catalogs)
    catalogs = [c for c in catalogs if isinstance(c, dict) and c.get("name") != name]

    if len(catalogs) == original_count:
        console.print(f"[red]Error:[/red] Catalog '{name}' not found.")
        raise typer.Exit(1)

    config["catalogs"] = catalogs
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    console.print(f"[green]✓[/green] Removed catalog '{name}'")
    if not catalogs:
        console.print("\n[dim]No catalogs remain in config. Built-in defaults will be used.[/dim]")


# ===== Extension Commands =====


def _resolve_installed_extension(
    argument: str,
    installed_extensions: list,
    command_name: str = "command",
    allow_not_found: bool = False,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve an extension argument (ID or display name) to an installed extension.

    Args:
        argument: Extension ID or display name provided by user
        installed_extensions: List of installed extension dicts from manager.list_installed()
        command_name: Name of the command for error messages (e.g., "enable", "disable")
        allow_not_found: If True, return (None, None) when not found instead of raising

    Returns:
        Tuple of (extension_id, display_name), or (None, None) if allow_not_found=True and not found

    Raises:
        typer.Exit: If extension not found (and allow_not_found=False) or name is ambiguous
    """
    from rich.table import Table

    # First, try exact ID match
    for ext in installed_extensions:
        if ext["id"] == argument:
            return (ext["id"], ext["name"])

    # If not found by ID, try display name match
    name_matches = [ext for ext in installed_extensions if ext["name"].lower() == argument.lower()]

    if len(name_matches) == 1:
        # Unique display-name match
        return (name_matches[0]["id"], name_matches[0]["name"])
    elif len(name_matches) > 1:
        # Ambiguous display-name match
        console.print(
            f"[red]Error:[/red] Extension name '{argument}' is ambiguous. "
            "Multiple installed extensions share this name:"
        )
        table = Table(title="Matching extensions")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Version", style="green")
        for ext in name_matches:
            table.add_row(ext.get("id", ""), ext.get("name", ""), str(ext.get("version", "")))
        console.print(table)
        console.print("\nPlease rerun using the extension ID:")
        console.print(f"  [bold]specify extension {command_name} <extension-id>[/bold]")
        raise typer.Exit(1)
    else:
        # No match by ID or display name
        if allow_not_found:
            return (None, None)
        console.print(f"[red]Error:[/red] Extension '{argument}' is not installed")
        raise typer.Exit(1)


def _resolve_catalog_extension(
    argument: str,
    catalog,
    command_name: str = "info",
) -> tuple[Optional[dict], Optional[Exception]]:
    """Resolve an extension argument (ID or display name) from the catalog.

    Args:
        argument: Extension ID or display name provided by user
        catalog: ExtensionCatalog instance
        command_name: Name of the command for error messages

    Returns:
        Tuple of (extension_info, catalog_error)
        - If found: (ext_info_dict, None)
        - If catalog error: (None, error)
        - If not found: (None, None)
    """
    from rich.table import Table
    from .extensions import ExtensionError

    try:
        # First try by ID
        ext_info = catalog.get_extension_info(argument)
        if ext_info:
            return (ext_info, None)

        # Try by display name - search using argument as query, then filter for exact match
        search_results = catalog.search(query=argument)
        name_matches = [ext for ext in search_results if ext["name"].lower() == argument.lower()]

        if len(name_matches) == 1:
            return (name_matches[0], None)
        elif len(name_matches) > 1:
            # Ambiguous display-name match in catalog
            console.print(
                f"[red]Error:[/red] Extension name '{argument}' is ambiguous. "
                "Multiple catalog extensions share this name:"
            )
            table = Table(title="Matching extensions")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="white")
            table.add_column("Version", style="green")
            table.add_column("Catalog", style="dim")
            for ext in name_matches:
                table.add_row(
                    ext.get("id", ""),
                    ext.get("name", ""),
                    str(ext.get("version", "")),
                    ext.get("_catalog_name", ""),
                )
            console.print(table)
            console.print("\nPlease rerun using the extension ID:")
            console.print(f"  [bold]specify extension {command_name} <extension-id>[/bold]")
            raise typer.Exit(1)

        # Not found
        return (None, None)

    except ExtensionError as e:
        return (None, e)


@extension_app.command("list")
def extension_list(
    available: bool = typer.Option(False, "--available", help="Show available extensions from catalog"),
    all_extensions: bool = typer.Option(False, "--all", help="Show both installed and available"),
):
    """List installed extensions."""
    from .extensions import ExtensionManager

    project_root = Path.cwd()

    # Check if we're in a spec-kit project
    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)
    installed = manager.list_installed()

    if not installed and not (available or all_extensions):
        console.print("[yellow]No extensions installed.[/yellow]")
        console.print("\nInstall an extension with:")
        console.print("  specify extension add <extension-name>")
        return

    if installed:
        console.print("\n[bold cyan]Installed Extensions:[/bold cyan]\n")

        for ext in installed:
            status_icon = "✓" if ext["enabled"] else "✗"
            status_color = "green" if ext["enabled"] else "red"
            priority = ext.get("priority", 10)

            console.print(f"  [{status_color}]{status_icon}[/{status_color}] [bold]{ext['name']}[/bold] ({ext['id']}) (v{ext['version']})")
            console.print(f"     {ext['description']}")
            console.print(f"     Commands: {ext['command_count']} | Hooks: {ext['hook_count']} | Status: {'Enabled' if ext['enabled'] else 'Disabled'}")
            console.print(f"     Priority: {priority}")
            console.print()

    if available or all_extensions:
        console.print("\nInstall an extension:")
        console.print("  [cyan]specify extension add <name>[/cyan]")


@catalog_app.command("list")
def catalog_list():
    """List all active extension catalogs."""
    from .extensions import ExtensionCatalog, ValidationError

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    catalog = ExtensionCatalog(project_root)

    try:
        active_catalogs = catalog.get_active_catalogs()
    except ValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print("\n[bold cyan]Active Extension Catalogs:[/bold cyan]\n")
    for entry in active_catalogs:
        install_str = (
            "[green]install allowed[/green]"
            if entry.install_allowed
            else "[yellow]discovery only[/yellow]"
        )
        console.print(f"  [bold]{entry.name}[/bold] (priority {entry.priority})")
        if entry.description:
            console.print(f"     {entry.description}")
        console.print(f"     URL: {entry.url}")
        console.print(f"     Install: {install_str}")
        console.print()

    config_path = project_root / ".specify" / "extension-catalogs.yml"
    user_config_path = Path.home() / ".specify" / "extension-catalogs.yml"
    if os.environ.get("SPECKIT_CATALOG_URL"):
        console.print("[dim]Catalog configured via SPECKIT_CATALOG_URL environment variable.[/dim]")
    else:
        try:
            proj_loaded = config_path.exists() and catalog._load_catalog_config(config_path) is not None
        except ValidationError:
            proj_loaded = False
        if proj_loaded:
            console.print(f"[dim]Config: {config_path.relative_to(project_root)}[/dim]")
        else:
            try:
                user_loaded = user_config_path.exists() and catalog._load_catalog_config(user_config_path) is not None
            except ValidationError:
                user_loaded = False
            if user_loaded:
                console.print("[dim]Config: ~/.specify/extension-catalogs.yml[/dim]")
            else:
                console.print("[dim]Using built-in default catalog stack.[/dim]")
                console.print(
                    "[dim]Add .specify/extension-catalogs.yml to customize.[/dim]"
                )


@catalog_app.command("add")
def catalog_add(
    url: str = typer.Argument(help="Catalog URL (must use HTTPS)"),
    name: str = typer.Option(..., "--name", help="Catalog name"),
    priority: int = typer.Option(10, "--priority", help="Priority (lower = higher priority)"),
    install_allowed: bool = typer.Option(
        False, "--install-allowed/--no-install-allowed",
        help="Allow extensions from this catalog to be installed",
    ),
    description: str = typer.Option("", "--description", help="Description of the catalog"),
):
    """Add a catalog to .specify/extension-catalogs.yml."""
    from .extensions import ExtensionCatalog, ValidationError

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    # Validate URL
    tmp_catalog = ExtensionCatalog(project_root)
    try:
        tmp_catalog._validate_catalog_url(url)
    except ValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    config_path = specify_dir / "extension-catalogs.yml"

    # Load existing config
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text()) or {}
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to read {config_path}: {e}")
            raise typer.Exit(1)
    else:
        config = {}

    catalogs = config.get("catalogs", [])
    if not isinstance(catalogs, list):
        console.print("[red]Error:[/red] Invalid catalog config: 'catalogs' must be a list.")
        raise typer.Exit(1)

    # Check for duplicate name
    for existing in catalogs:
        if isinstance(existing, dict) and existing.get("name") == name:
            console.print(f"[yellow]Warning:[/yellow] A catalog named '{name}' already exists.")
            console.print("Use 'specify extension catalog remove' first, or choose a different name.")
            raise typer.Exit(1)

    catalogs.append({
        "name": name,
        "url": url,
        "priority": priority,
        "install_allowed": install_allowed,
        "description": description,
    })

    config["catalogs"] = catalogs
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    install_label = "install allowed" if install_allowed else "discovery only"
    console.print(f"\n[green]✓[/green] Added catalog '[bold]{name}[/bold]' ({install_label})")
    console.print(f"  URL: {url}")
    console.print(f"  Priority: {priority}")
    console.print(f"\nConfig saved to {config_path.relative_to(project_root)}")


@catalog_app.command("remove")
def catalog_remove(
    name: str = typer.Argument(help="Catalog name to remove"),
):
    """Remove a catalog from .specify/extension-catalogs.yml."""
    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    config_path = specify_dir / "extension-catalogs.yml"
    if not config_path.exists():
        console.print("[red]Error:[/red] No catalog config found. Nothing to remove.")
        raise typer.Exit(1)

    try:
        config = yaml.safe_load(config_path.read_text()) or {}
    except Exception:
        console.print("[red]Error:[/red] Failed to read catalog config.")
        raise typer.Exit(1)

    catalogs = config.get("catalogs", [])
    if not isinstance(catalogs, list):
        console.print("[red]Error:[/red] Invalid catalog config: 'catalogs' must be a list.")
        raise typer.Exit(1)
    original_count = len(catalogs)
    catalogs = [c for c in catalogs if isinstance(c, dict) and c.get("name") != name]

    if len(catalogs) == original_count:
        console.print(f"[red]Error:[/red] Catalog '{name}' not found.")
        raise typer.Exit(1)

    config["catalogs"] = catalogs
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    console.print(f"[green]✓[/green] Removed catalog '{name}'")
    if not catalogs:
        console.print("\n[dim]No catalogs remain in config. Built-in defaults will be used.[/dim]")


@extension_app.command("add")
def extension_add(
    extension: str = typer.Argument(help="Extension name or path"),
    dev: bool = typer.Option(False, "--dev", help="Install from local directory"),
    from_url: Optional[str] = typer.Option(None, "--from", help="Install from custom URL"),
    priority: int = typer.Option(10, "--priority", help="Resolution priority (lower = higher precedence, default 10)"),
):
    """Install an extension."""
    from .extensions import ExtensionManager, ExtensionCatalog, ExtensionError, ValidationError, CompatibilityError

    project_root = Path.cwd()

    # Check if we're in a spec-kit project
    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)
    speckit_version = get_speckit_version()

    try:
        with console.status(f"[cyan]Installing extension: {extension}[/cyan]"):
            if dev:
                # Install from local directory
                source_path = Path(extension).expanduser().resolve()
                if not source_path.exists():
                    console.print(f"[red]Error:[/red] Directory not found: {source_path}")
                    raise typer.Exit(1)

                if not (source_path / "extension.yml").exists():
                    console.print(f"[red]Error:[/red] No extension.yml found in {source_path}")
                    raise typer.Exit(1)

                manifest = manager.install_from_directory(source_path, speckit_version, priority=priority)

            elif from_url:
                # Install from URL (ZIP file)
                import urllib.request
                import urllib.error
                from urllib.parse import urlparse

                # Validate URL
                parsed = urlparse(from_url)
                is_localhost = parsed.hostname in ("localhost", "127.0.0.1", "::1")

                if parsed.scheme != "https" and not (parsed.scheme == "http" and is_localhost):
                    console.print("[red]Error:[/red] URL must use HTTPS for security.")
                    console.print("HTTP is only allowed for localhost URLs.")
                    raise typer.Exit(1)

                # Warn about untrusted sources
                console.print("[yellow]Warning:[/yellow] Installing from external URL.")
                console.print("Only install extensions from sources you trust.\n")
                console.print(f"Downloading from {from_url}...")

                # Download ZIP to temp location
                download_dir = project_root / ".specify" / "extensions" / ".cache" / "downloads"
                download_dir.mkdir(parents=True, exist_ok=True)
                zip_path = download_dir / f"{extension}-url-download.zip"

                try:
                    with urllib.request.urlopen(from_url, timeout=60) as response:
                        zip_data = response.read()
                    zip_path.write_bytes(zip_data)

                    # Install from downloaded ZIP
                    manifest = manager.install_from_zip(zip_path, speckit_version, priority=priority)
                except urllib.error.URLError as e:
                    console.print(f"[red]Error:[/red] Failed to download from {from_url}: {e}")
                    raise typer.Exit(1)
                finally:
                    # Clean up downloaded ZIP
                    if zip_path.exists():
                        zip_path.unlink()

            else:
                # Install from catalog
                catalog = ExtensionCatalog(project_root)

                # Check if extension exists in catalog (supports both ID and display name)
                ext_info, catalog_error = _resolve_catalog_extension(extension, catalog, "add")
                if catalog_error:
                    console.print(f"[red]Error:[/red] Could not query extension catalog: {catalog_error}")
                    raise typer.Exit(1)
                if not ext_info:
                    console.print(f"[red]Error:[/red] Extension '{extension}' not found in catalog")
                    console.print("\nSearch available extensions:")
                    console.print("  specify extension search")
                    raise typer.Exit(1)

                # Enforce install_allowed policy
                if not ext_info.get("_install_allowed", True):
                    catalog_name = ext_info.get("_catalog_name", "community")
                    console.print(
                        f"[red]Error:[/red] '{extension}' is available in the "
                        f"'{catalog_name}' catalog but installation is not allowed from that catalog."
                    )
                    console.print(
                        f"\nTo enable installation, add '{extension}' to an approved catalog "
                        f"(install_allowed: true) in .specify/extension-catalogs.yml."
                    )
                    raise typer.Exit(1)

                # Download extension ZIP (use resolved ID, not original argument which may be display name)
                extension_id = ext_info['id']
                console.print(f"Downloading {ext_info['name']} v{ext_info.get('version', 'unknown')}...")
                zip_path = catalog.download_extension(extension_id)

                try:
                    # Install from downloaded ZIP
                    manifest = manager.install_from_zip(zip_path, speckit_version, priority=priority)
                finally:
                    # Clean up downloaded ZIP
                    if zip_path.exists():
                        zip_path.unlink()

        console.print("\n[green]✓[/green] Extension installed successfully!")
        console.print(f"\n[bold]{manifest.name}[/bold] (v{manifest.version})")
        console.print(f"  {manifest.description}")
        console.print(f"  Priority: {priority}")
        console.print("\n[bold cyan]Provided commands:[/bold cyan]")
        for cmd in manifest.commands:
            console.print(f"  • {cmd['name']} - {cmd.get('description', '')}")

        console.print("\n[yellow]⚠[/yellow]  Configuration may be required")
        console.print(f"   Check: .specify/extensions/{manifest.id}/")

    except ValidationError as e:
        console.print(f"\n[red]Validation Error:[/red] {e}")
        raise typer.Exit(1)
    except CompatibilityError as e:
        console.print(f"\n[red]Compatibility Error:[/red] {e}")
        raise typer.Exit(1)
    except ExtensionError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1)


@extension_app.command("set-priority")
def extension_set_priority(
    extension: str = typer.Argument(help="Extension ID or name"),
    priority: int = typer.Argument(help="New priority (lower = higher precedence)"),
):
    """Set the resolution priority of an installed extension."""
    from .extensions import ExtensionManager, normalize_priority

    project_root = Path.cwd()

    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    if priority < 1:
        console.print("[red]Error:[/red] Priority must be a positive integer (1 or higher)")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)
    installed = manager.list_installed()
    extension_id, _display_name = _resolve_installed_extension(extension, installed, "set-priority")

    metadata = manager.registry.get(extension_id)
    if metadata is None or not isinstance(metadata, dict):
        console.print(f"[red]Error:[/red] Extension '{extension_id}' not found in registry (corrupted state)")
        raise typer.Exit(1)

    raw_priority = metadata.get("priority")
    if isinstance(raw_priority, int) and raw_priority == priority:
        console.print(f"[yellow]Extension '{extension_id}' already has priority {priority}[/yellow]")
        raise typer.Exit(0)

    old_priority = normalize_priority(raw_priority)
    manager.registry.update(extension_id, {"priority": priority})

    console.print(f"[green]✓[/green] Extension '{extension_id}' priority changed: {old_priority} → {priority}")
    console.print("\n[dim]Lower priority = higher precedence in template resolution[/dim]")


@extension_app.command("remove")
def extension_remove(
    extension: str = typer.Argument(help="Extension ID or name to remove"),
    keep_config: bool = typer.Option(False, "--keep-config", help="Don't remove config files"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Uninstall an extension."""
    from .extensions import ExtensionManager

    project_root = Path.cwd()

    # Check if we're in a spec-kit project
    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)

    # Resolve extension ID from argument (handles ambiguous names)
    installed = manager.list_installed()
    extension_id, display_name = _resolve_installed_extension(extension, installed, "remove")

    # Get extension info for command count
    ext_manifest = manager.get_extension(extension_id)
    cmd_count = len(ext_manifest.commands) if ext_manifest else 0

    # Confirm removal
    if not force:
        console.print("\n[yellow]⚠  This will remove:[/yellow]")
        console.print(f"   • {cmd_count} commands from AI agent")
        console.print(f"   • Extension directory: .specify/extensions/{extension_id}/")
        if not keep_config:
            console.print("   • Config files (will be backed up)")
        console.print()

        confirm = typer.confirm("Continue?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit(0)

    # Remove extension
    success = manager.remove(extension_id, keep_config=keep_config)

    if success:
        console.print(f"\n[green]✓[/green] Extension '{display_name}' removed successfully")
        if keep_config:
            console.print(f"\nConfig files preserved in .specify/extensions/{extension_id}/")
        else:
            console.print(f"\nConfig files backed up to .specify/extensions/.backup/{extension_id}/")
        console.print(f"\nTo reinstall: specify extension add {extension_id}")
    else:
        console.print("[red]Error:[/red] Failed to remove extension")
        raise typer.Exit(1)


@extension_app.command("search")
def extension_search(
    query: str = typer.Argument(None, help="Search query (optional)"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    author: Optional[str] = typer.Option(None, "--author", help="Filter by author"),
    verified: bool = typer.Option(False, "--verified", help="Show only verified extensions"),
):
    """Search for available extensions in catalog."""
    from .extensions import ExtensionCatalog, ExtensionError

    project_root = Path.cwd()

    # Check if we're in a spec-kit project
    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    catalog = ExtensionCatalog(project_root)

    try:
        console.print("🔍 Searching extension catalog...")
        results = catalog.search(query=query, tag=tag, author=author, verified_only=verified)

        if not results:
            console.print("\n[yellow]No extensions found matching criteria[/yellow]")
            if query or tag or author or verified:
                console.print("\nTry:")
                console.print("  • Broader search terms")
                console.print("  • Remove filters")
                console.print("  • specify extension search (show all)")
            raise typer.Exit(0)

        console.print(f"\n[green]Found {len(results)} extension(s):[/green]\n")

        for ext in results:
            # Extension header
            verified_badge = " [green]✓ Verified[/green]" if ext.get("verified") else ""
            console.print(f"[bold]{ext['name']}[/bold] (v{ext['version']}){verified_badge}")
            console.print(f"  {ext['description']}")

            # Metadata
            console.print(f"\n  [dim]Author:[/dim] {ext.get('author', 'Unknown')}")
            if ext.get('tags'):
                tags_str = ", ".join(ext['tags'])
                console.print(f"  [dim]Tags:[/dim] {tags_str}")

            # Source catalog
            catalog_name = ext.get("_catalog_name", "")
            install_allowed = ext.get("_install_allowed", True)
            if catalog_name:
                if install_allowed:
                    console.print(f"  [dim]Catalog:[/dim] {catalog_name}")
                else:
                    console.print(f"  [dim]Catalog:[/dim] {catalog_name} [yellow](discovery only — not installable)[/yellow]")

            # Stats
            stats = []
            if ext.get('downloads') is not None:
                stats.append(f"Downloads: {ext['downloads']:,}")
            if ext.get('stars') is not None:
                stats.append(f"Stars: {ext['stars']}")
            if stats:
                console.print(f"  [dim]{' | '.join(stats)}[/dim]")

            # Links
            if ext.get('repository'):
                console.print(f"  [dim]Repository:[/dim] {ext['repository']}")

            # Install command (show warning if not installable)
            if install_allowed:
                console.print(f"\n  [cyan]Install:[/cyan] specify extension add {ext['id']}")
            else:
                console.print(f"\n  [yellow]⚠[/yellow]  Not directly installable from '{catalog_name}'.")
                console.print(
                    f"  Add to an approved catalog with install_allowed: true, "
                    f"or install from a ZIP URL: specify extension add {ext['id']} --from <zip-url>"
                )
            console.print()

    except ExtensionError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        console.print("\nTip: The catalog may be temporarily unavailable. Try again later.")
        raise typer.Exit(1)


@extension_app.command("info")
def extension_info(
    extension: str = typer.Argument(help="Extension ID or name"),
):
    """Show detailed information about an extension."""
    from .extensions import ExtensionCatalog, ExtensionManager

    project_root = Path.cwd()

    # Check if we're in a spec-kit project
    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    catalog = ExtensionCatalog(project_root)
    manager = ExtensionManager(project_root)
    installed = manager.list_installed()

    # Try to resolve from installed extensions first (by ID or name)
    # Use allow_not_found=True since the extension may be catalog-only
    resolved_installed_id, resolved_installed_name = _resolve_installed_extension(
        extension, installed, "info", allow_not_found=True
    )

    # Try catalog lookup (with error handling)
    # If we resolved an installed extension by display name, use its ID for catalog lookup
    # to ensure we get the correct catalog entry (not a different extension with same name)
    lookup_key = resolved_installed_id if resolved_installed_id else extension
    ext_info, catalog_error = _resolve_catalog_extension(lookup_key, catalog, "info")

    # Case 1: Found in catalog - show full catalog info
    if ext_info:
        _print_extension_info(ext_info, manager)
        return

    # Case 2: Installed locally but catalog lookup failed or not in catalog
    if resolved_installed_id:
        # Get local manifest info
        ext_manifest = manager.get_extension(resolved_installed_id)
        metadata = manager.registry.get(resolved_installed_id)

        console.print(f"\n[bold]{resolved_installed_name}[/bold] (v{metadata.get('version', 'unknown')})")
        console.print(f"ID: {resolved_installed_id}")
        console.print()

        if ext_manifest:
            console.print(f"{ext_manifest.description}")
            console.print()
            # Author is optional in extension.yml, safely retrieve it
            author = ext_manifest.data.get("extension", {}).get("author")
            if author:
                console.print(f"[dim]Author:[/dim] {author}")
                console.print()

            if ext_manifest.commands:
                console.print("[bold]Commands:[/bold]")
                for cmd in ext_manifest.commands:
                    console.print(f"  • {cmd['name']}: {cmd.get('description', '')}")
                console.print()

        # Show catalog status
        if catalog_error:
            console.print(f"[yellow]Catalog unavailable:[/yellow] {catalog_error}")
            console.print("[dim]Note: Using locally installed extension; catalog info could not be verified.[/dim]")
        else:
            console.print("[yellow]Note:[/yellow] Not found in catalog (custom/local extension)")

        console.print()
        console.print("[green]✓ Installed[/green]")
        console.print(f"\nTo remove: specify extension remove {resolved_installed_id}")
        return

    # Case 3: Not found anywhere
    if catalog_error:
        console.print(f"[red]Error:[/red] Could not query extension catalog: {catalog_error}")
        console.print("\nTry again when online, or use the extension ID directly.")
    else:
        console.print(f"[red]Error:[/red] Extension '{extension}' not found")
        console.print("\nTry: specify extension search")
    raise typer.Exit(1)


def _print_extension_info(ext_info: dict, manager):
    """Print formatted extension info from catalog data."""
    # Header
    verified_badge = " [green]✓ Verified[/green]" if ext_info.get("verified") else ""
    console.print(f"\n[bold]{ext_info['name']}[/bold] (v{ext_info['version']}){verified_badge}")
    console.print(f"ID: {ext_info['id']}")
    console.print()

    # Description
    console.print(f"{ext_info['description']}")
    console.print()

    # Author and License
    console.print(f"[dim]Author:[/dim] {ext_info.get('author', 'Unknown')}")
    console.print(f"[dim]License:[/dim] {ext_info.get('license', 'Unknown')}")

    # Source catalog
    if ext_info.get("_catalog_name"):
        install_allowed = ext_info.get("_install_allowed", True)
        install_note = "" if install_allowed else " [yellow](discovery only)[/yellow]"
        console.print(f"[dim]Source catalog:[/dim] {ext_info['_catalog_name']}{install_note}")
    console.print()

    # Requirements
    if ext_info.get('requires'):
        console.print("[bold]Requirements:[/bold]")
        reqs = ext_info['requires']
        if reqs.get('speckit_version'):
            console.print(f"  • Spec Kit: {reqs['speckit_version']}")
        if reqs.get('tools'):
            for tool in reqs['tools']:
                tool_name = tool['name']
                tool_version = tool.get('version', 'any')
                required = " (required)" if tool.get('required') else " (optional)"
                console.print(f"  • {tool_name}: {tool_version}{required}")
        console.print()

    # Provides
    if ext_info.get('provides'):
        console.print("[bold]Provides:[/bold]")
        provides = ext_info['provides']
        if provides.get('commands'):
            console.print(f"  • Commands: {provides['commands']}")
        if provides.get('hooks'):
            console.print(f"  • Hooks: {provides['hooks']}")
        console.print()

    # Tags
    if ext_info.get('tags'):
        tags_str = ", ".join(ext_info['tags'])
        console.print(f"[bold]Tags:[/bold] {tags_str}")
        console.print()

    # Statistics
    stats = []
    if ext_info.get('downloads') is not None:
        stats.append(f"Downloads: {ext_info['downloads']:,}")
    if ext_info.get('stars') is not None:
        stats.append(f"Stars: {ext_info['stars']}")
    if stats:
        console.print(f"[bold]Statistics:[/bold] {' | '.join(stats)}")
        console.print()

    # Links
    console.print("[bold]Links:[/bold]")
    if ext_info.get('repository'):
        console.print(f"  • Repository: {ext_info['repository']}")
    if ext_info.get('homepage'):
        console.print(f"  • Homepage: {ext_info['homepage']}")
    if ext_info.get('documentation'):
        console.print(f"  • Documentation: {ext_info['documentation']}")
    if ext_info.get('changelog'):
        console.print(f"  • Changelog: {ext_info['changelog']}")
    console.print()

    # Installation status and command
    is_installed = manager.registry.is_installed(ext_info['id'])
    install_allowed = ext_info.get("_install_allowed", True)
    if is_installed:
        console.print("[green]✓ Installed[/green]")
        console.print(f"\nTo remove: specify extension remove {ext_info['id']}")
    elif install_allowed:
        console.print("[yellow]Not installed[/yellow]")
        console.print(f"\n[cyan]Install:[/cyan] specify extension add {ext_info['id']}")
    else:
        catalog_name = ext_info.get("_catalog_name", "community")
        console.print("[yellow]Not installed[/yellow]")
        console.print(
            f"\n[yellow]⚠[/yellow]  '{ext_info['id']}' is available in the '{catalog_name}' catalog "
            f"but not in your approved catalog. Add it to .specify/extension-catalogs.yml "
            f"with install_allowed: true to enable installation."
        )


@extension_app.command("update")
def extension_update(
    extension: str = typer.Argument(None, help="Extension ID or name to update (or all)"),
):
    """Update extension(s) to latest version."""
    from .extensions import (
        ExtensionManager,
        ExtensionCatalog,
        ExtensionError,
        ValidationError,
        CommandRegistrar,
        HookExecutor,
    )
    from packaging import version as pkg_version
    import shutil

    project_root = Path.cwd()

    # Check if we're in a spec-kit project
    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)
    catalog = ExtensionCatalog(project_root)
    speckit_version = get_speckit_version()

    try:
        # Get list of extensions to update
        installed = manager.list_installed()
        if extension:
            # Update specific extension - resolve ID from argument (handles ambiguous names)
            extension_id, _ = _resolve_installed_extension(extension, installed, "update")
            extensions_to_update = [extension_id]
        else:
            # Update all extensions
            extensions_to_update = [ext["id"] for ext in installed]

        if not extensions_to_update:
            console.print("[yellow]No extensions installed[/yellow]")
            raise typer.Exit(0)

        console.print("🔄 Checking for updates...\n")

        updates_available = []

        for ext_id in extensions_to_update:
            # Get installed version
            metadata = manager.registry.get(ext_id)
            if metadata is None or "version" not in metadata:
                console.print(f"⚠  {ext_id}: Registry entry corrupted or missing (skipping)")
                continue
            try:
                installed_version = pkg_version.Version(metadata["version"])
            except pkg_version.InvalidVersion:
                console.print(
                    f"⚠  {ext_id}: Invalid installed version '{metadata.get('version')}' in registry (skipping)"
                )
                continue

            # Get catalog info
            ext_info = catalog.get_extension_info(ext_id)
            if not ext_info:
                console.print(f"⚠  {ext_id}: Not found in catalog (skipping)")
                continue

            # Check if installation is allowed from this catalog
            if not ext_info.get("_install_allowed", True):
                console.print(f"⚠  {ext_id}: Updates not allowed from '{ext_info.get('_catalog_name', 'catalog')}' (skipping)")
                continue

            try:
                catalog_version = pkg_version.Version(ext_info["version"])
            except pkg_version.InvalidVersion:
                console.print(
                    f"⚠  {ext_id}: Invalid catalog version '{ext_info.get('version')}' (skipping)"
                )
                continue

            if catalog_version > installed_version:
                updates_available.append(
                    {
                        "id": ext_id,
                        "name": ext_info.get("name", ext_id),  # Display name for status messages
                        "installed": str(installed_version),
                        "available": str(catalog_version),
                        "download_url": ext_info.get("download_url"),
                    }
                )
            else:
                console.print(f"✓ {ext_id}: Up to date (v{installed_version})")

        if not updates_available:
            console.print("\n[green]All extensions are up to date![/green]")
            raise typer.Exit(0)

        # Show available updates
        console.print("\n[bold]Updates available:[/bold]\n")
        for update in updates_available:
            console.print(
                f"  • {update['id']}: {update['installed']} → {update['available']}"
            )

        console.print()
        confirm = typer.confirm("Update these extensions?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit(0)

        # Perform updates with atomic backup/restore
        console.print()
        updated_extensions = []
        failed_updates = []
        registrar = CommandRegistrar()
        hook_executor = HookExecutor(project_root)

        for update in updates_available:
            extension_id = update["id"]
            ext_name = update["name"]  # Use display name for user-facing messages
            console.print(f"📦 Updating {ext_name}...")

            # Backup paths
            backup_base = manager.extensions_dir / ".backup" / f"{extension_id}-update"
            backup_ext_dir = backup_base / "extension"
            backup_commands_dir = backup_base / "commands"
            backup_config_dir = backup_base / "config"

            # Store backup state
            backup_registry_entry = None
            backup_hooks = None  # None means no hooks key in config; {} means hooks key existed
            backed_up_command_files = {}

            try:
                # 1. Backup registry entry (always, even if extension dir doesn't exist)
                backup_registry_entry = manager.registry.get(extension_id)

                # 2. Backup extension directory
                extension_dir = manager.extensions_dir / extension_id
                if extension_dir.exists():
                    backup_base.mkdir(parents=True, exist_ok=True)
                    if backup_ext_dir.exists():
                        shutil.rmtree(backup_ext_dir)
                    shutil.copytree(extension_dir, backup_ext_dir)

                    # Backup config files separately so they can be restored
                    # after a successful install (install_from_directory clears dest dir).
                    config_files = list(extension_dir.glob("*-config.yml")) + list(
                        extension_dir.glob("*-config.local.yml")
                    )
                    for cfg_file in config_files:
                        backup_config_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(cfg_file, backup_config_dir / cfg_file.name)

                # 3. Backup command files for all agents
                registered_commands = backup_registry_entry.get("registered_commands", {})
                for agent_name, cmd_names in registered_commands.items():
                    if agent_name not in registrar.AGENT_CONFIGS:
                        continue
                    agent_config = registrar.AGENT_CONFIGS[agent_name]
                    commands_dir = project_root / agent_config["dir"]

                    for cmd_name in cmd_names:
                        cmd_file = commands_dir / f"{cmd_name}{agent_config['extension']}"
                        if cmd_file.exists():
                            backup_cmd_path = backup_commands_dir / agent_name / cmd_file.name
                            backup_cmd_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(cmd_file, backup_cmd_path)
                            backed_up_command_files[str(cmd_file)] = str(backup_cmd_path)

                        # Also backup copilot prompt files
                        if agent_name == "copilot":
                            prompt_file = project_root / ".github" / "prompts" / f"{cmd_name}.prompt.md"
                            if prompt_file.exists():
                                backup_prompt_path = backup_commands_dir / "copilot-prompts" / prompt_file.name
                                backup_prompt_path.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(prompt_file, backup_prompt_path)
                                backed_up_command_files[str(prompt_file)] = str(backup_prompt_path)

                # 4. Backup hooks from extensions.yml
                # Use backup_hooks=None to indicate config had no "hooks" key (don't create on restore)
                # Use backup_hooks={} to indicate config had "hooks" key with no hooks for this extension
                config = hook_executor.get_project_config()
                if "hooks" in config:
                    backup_hooks = {}  # Config has hooks key - preserve this fact
                    for hook_name, hook_list in config["hooks"].items():
                        ext_hooks = [h for h in hook_list if h.get("extension") == extension_id]
                        if ext_hooks:
                            backup_hooks[hook_name] = ext_hooks

                # 5. Download new version
                zip_path = catalog.download_extension(extension_id)
                try:
                    # 6. Validate extension ID from ZIP BEFORE modifying installation
                    # Handle both root-level and nested extension.yml (GitHub auto-generated ZIPs)
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        import yaml
                        manifest_data = None
                        namelist = zf.namelist()

                        # First try root-level extension.yml
                        if "extension.yml" in namelist:
                            with zf.open("extension.yml") as f:
                                manifest_data = yaml.safe_load(f) or {}
                        else:
                            # Look for extension.yml in a single top-level subdirectory
                            # (e.g., "repo-name-branch/extension.yml")
                            manifest_paths = [n for n in namelist if n.endswith("/extension.yml") and n.count("/") == 1]
                            if len(manifest_paths) == 1:
                                with zf.open(manifest_paths[0]) as f:
                                    manifest_data = yaml.safe_load(f) or {}

                        if manifest_data is None:
                            raise ValueError("Downloaded extension archive is missing 'extension.yml'")

                    zip_extension_id = manifest_data.get("extension", {}).get("id")
                    if zip_extension_id != extension_id:
                        raise ValueError(
                            f"Extension ID mismatch: expected '{extension_id}', got '{zip_extension_id}'"
                        )

                    # 7. Remove old extension (handles command file cleanup and registry removal)
                    manager.remove(extension_id, keep_config=True)

                    # 8. Install new version
                    _ = manager.install_from_zip(zip_path, speckit_version)

                    # Restore user config files from backup after successful install.
                    new_extension_dir = manager.extensions_dir / extension_id
                    if backup_config_dir.exists() and new_extension_dir.exists():
                        for cfg_file in backup_config_dir.iterdir():
                            if cfg_file.is_file():
                                shutil.copy2(cfg_file, new_extension_dir / cfg_file.name)

                    # 9. Restore metadata from backup (installed_at, enabled state)
                    if backup_registry_entry:
                        # Copy current registry entry to avoid mutating internal
                        # registry state before explicit restore().
                        current_metadata = manager.registry.get(extension_id)
                        if current_metadata is None:
                            raise RuntimeError(
                                f"Registry entry for '{extension_id}' missing after install — update incomplete"
                            )
                        new_metadata = dict(current_metadata)

                        # Preserve the original installation timestamp
                        if "installed_at" in backup_registry_entry:
                            new_metadata["installed_at"] = backup_registry_entry["installed_at"]

                        # If extension was disabled before update, disable it again
                        if not backup_registry_entry.get("enabled", True):
                            new_metadata["enabled"] = False

                        # Use restore() instead of update() because update() always
                        # preserves the existing installed_at, ignoring our override
                        manager.registry.restore(extension_id, new_metadata)

                        # Also disable hooks in extensions.yml if extension was disabled
                        if not backup_registry_entry.get("enabled", True):
                            config = hook_executor.get_project_config()
                            if "hooks" in config:
                                for hook_name in config["hooks"]:
                                    for hook in config["hooks"][hook_name]:
                                        if hook.get("extension") == extension_id:
                                            hook["enabled"] = False
                                hook_executor.save_project_config(config)
                finally:
                    # Clean up downloaded ZIP
                    if zip_path.exists():
                        zip_path.unlink()

                # 10. Clean up backup on success
                if backup_base.exists():
                    shutil.rmtree(backup_base)

                console.print(f"   [green]✓[/green] Updated to v{update['available']}")
                updated_extensions.append(ext_name)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                console.print(f"   [red]✗[/red] Failed: {e}")
                failed_updates.append((ext_name, str(e)))

                # Rollback on failure
                console.print(f"   [yellow]↩[/yellow] Rolling back {ext_name}...")

                try:
                    # Restore extension directory
                    # Only perform destructive rollback if backup exists (meaning we
                    # actually modified the extension). This avoids deleting a valid
                    # installation when failure happened before changes were made.
                    extension_dir = manager.extensions_dir / extension_id
                    if backup_ext_dir.exists():
                        if extension_dir.exists():
                            shutil.rmtree(extension_dir)
                        shutil.copytree(backup_ext_dir, extension_dir)

                    # Remove any NEW command files created by failed install
                    # (files that weren't in the original backup)
                    try:
                        new_registry_entry = manager.registry.get(extension_id)
                        if new_registry_entry is None:
                            new_registered_commands = {}
                        else:
                            new_registered_commands = new_registry_entry.get("registered_commands", {})
                        for agent_name, cmd_names in new_registered_commands.items():
                            if agent_name not in registrar.AGENT_CONFIGS:
                                continue
                            agent_config = registrar.AGENT_CONFIGS[agent_name]
                            commands_dir = project_root / agent_config["dir"]

                            for cmd_name in cmd_names:
                                cmd_file = commands_dir / f"{cmd_name}{agent_config['extension']}"
                                # Delete if it exists and wasn't in our backup
                                if cmd_file.exists() and str(cmd_file) not in backed_up_command_files:
                                    cmd_file.unlink()

                                # Also handle copilot prompt files
                                if agent_name == "copilot":
                                    prompt_file = project_root / ".github" / "prompts" / f"{cmd_name}.prompt.md"
                                    if prompt_file.exists() and str(prompt_file) not in backed_up_command_files:
                                        prompt_file.unlink()
                    except KeyError:
                        pass  # No new registry entry exists, nothing to clean up

                    # Restore backed up command files
                    for original_path, backup_path in backed_up_command_files.items():
                        backup_file = Path(backup_path)
                        if backup_file.exists():
                            original_file = Path(original_path)
                            original_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(backup_file, original_file)

                    # Restore hooks in extensions.yml
                    # - backup_hooks=None means original config had no "hooks" key
                    # - backup_hooks={} or {...} means config had hooks key
                    config = hook_executor.get_project_config()
                    if "hooks" in config:
                        modified = False

                        if backup_hooks is None:
                            # Original config had no "hooks" key; remove it entirely
                            del config["hooks"]
                            modified = True
                        else:
                            # Remove any hooks for this extension added by failed install
                            for hook_name, hooks_list in config["hooks"].items():
                                original_len = len(hooks_list)
                                config["hooks"][hook_name] = [
                                    h for h in hooks_list
                                    if h.get("extension") != extension_id
                                ]
                                if len(config["hooks"][hook_name]) != original_len:
                                    modified = True

                            # Add back the backed up hooks if any
                            if backup_hooks:
                                for hook_name, hooks in backup_hooks.items():
                                    if hook_name not in config["hooks"]:
                                        config["hooks"][hook_name] = []
                                    config["hooks"][hook_name].extend(hooks)
                                    modified = True

                        if modified:
                            hook_executor.save_project_config(config)

                    # Restore registry entry (use restore() since entry was removed)
                    if backup_registry_entry:
                        manager.registry.restore(extension_id, backup_registry_entry)

                    console.print("   [green]✓[/green] Rollback successful")
                    # Clean up backup directory only on successful rollback
                    if backup_base.exists():
                        shutil.rmtree(backup_base)
                except Exception as rollback_error:
                    console.print(f"   [red]✗[/red] Rollback failed: {rollback_error}")
                    console.print(f"   [dim]Backup preserved at: {backup_base}[/dim]")

        # Summary
        console.print()
        if updated_extensions:
            console.print(f"[green]✓[/green] Successfully updated {len(updated_extensions)} extension(s)")
        if failed_updates:
            console.print(f"[red]✗[/red] Failed to update {len(failed_updates)} extension(s):")
            for ext_name, error in failed_updates:
                console.print(f"   • {ext_name}: {error}")
            raise typer.Exit(1)

    except ValidationError as e:
        console.print(f"\n[red]Validation Error:[/red] {e}")
        raise typer.Exit(1)
    except ExtensionError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1)


@extension_app.command("enable")
def extension_enable(
    extension: str = typer.Argument(help="Extension ID or name to enable"),
):
    """Enable a disabled extension."""
    from .extensions import ExtensionManager, HookExecutor

    project_root = Path.cwd()

    # Check if we're in a spec-kit project
    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)
    hook_executor = HookExecutor(project_root)

    # Resolve extension ID from argument (handles ambiguous names)
    installed = manager.list_installed()
    extension_id, display_name = _resolve_installed_extension(extension, installed, "enable")

    # Update registry
    metadata = manager.registry.get(extension_id)
    if metadata is None:
        console.print(f"[red]Error:[/red] Extension '{extension_id}' not found in registry (corrupted state)")
        raise typer.Exit(1)
    
    if metadata.get("enabled", True):
        console.print(f"[yellow]Extension '{display_name}' is already enabled[/yellow]")
        raise typer.Exit(0)

    metadata["enabled"] = True
    manager.registry.update(extension_id, metadata)

    # Enable hooks in extensions.yml
    config = hook_executor.get_project_config()
    if "hooks" in config:
        for hook_name in config["hooks"]:
            for hook in config["hooks"][hook_name]:
                if hook.get("extension") == extension_id:
                    hook["enabled"] = True
        hook_executor.save_project_config(config)

    console.print(f"[green]✓[/green] Extension '{display_name}' enabled")


@extension_app.command("disable")
def extension_disable(
    extension: str = typer.Argument(help="Extension ID or name to disable"),
):
    """Disable an extension without removing it."""
    from .extensions import ExtensionManager, HookExecutor

    project_root = Path.cwd()

    # Check if we're in a spec-kit project
    specify_dir = project_root / ".specify"
    if not specify_dir.exists():
        console.print("[red]Error:[/red] Not a spec-kit project (no .specify/ directory)")
        console.print("Run this command from a spec-kit project root")
        raise typer.Exit(1)

    manager = ExtensionManager(project_root)
    hook_executor = HookExecutor(project_root)

    # Resolve extension ID from argument (handles ambiguous names)
    installed = manager.list_installed()
    extension_id, display_name = _resolve_installed_extension(extension, installed, "disable")

    # Update registry
    metadata = manager.registry.get(extension_id)
    if metadata is None:
        console.print(f"[red]Error:[/red] Extension '{extension_id}' not found in registry (corrupted state)")
        raise typer.Exit(1)
    
    if not metadata.get("enabled", True):
        console.print(f"[yellow]Extension '{display_name}' is already disabled[/yellow]")
        raise typer.Exit(0)

    metadata["enabled"] = False
    manager.registry.update(extension_id, metadata)

    # Disable hooks in extensions.yml
    config = hook_executor.get_project_config()
    if "hooks" in config:
        for hook_name in config["hooks"]:
            for hook in config["hooks"][hook_name]:
                if hook.get("extension") == extension_id:
                    hook["enabled"] = False
        hook_executor.save_project_config(config)

    console.print(f"[green]✓[/green] Extension '{display_name}' disabled")
    console.print("\nCommands will no longer be available. Hooks will not execute.")
    console.print(f"To re-enable: specify extension enable {extension_id}")


def main():
    app()

if __name__ == "__main__":
    main()
