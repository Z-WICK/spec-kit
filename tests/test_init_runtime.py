from pathlib import Path

import pytest
import typer
from rich.console import Console

from specify_cli.init_runtime import (
    build_init_tracker,
    install_requested_preset,
    resolve_ai_selection,
    resolve_project_target,
    resolve_script_selection,
    validate_raw_option_values,
)


class FakeTracker:
    def __init__(self, title: str):
        self.title = title
        self.steps = []

    def add(self, key: str, label: str):
        self.steps.append((key, label, "pending", ""))

    def complete(self, key: str, detail: str = ""):
        self.steps.append((key, "", "done", detail))


def test_validate_raw_option_values_rejects_flag_as_ai_value():
    console = Console(record=True)

    with pytest.raises(typer.Exit) as exc:
        validate_raw_option_values("--here", None, console, {"claude": {}, "generic": {}})

    assert exc.value.exit_code == 1
    assert "Invalid value for --ai" in console.export_text()


def test_validate_raw_option_values_rejects_flag_as_ai_commands_dir():
    console = Console(record=True)

    with pytest.raises(typer.Exit) as exc:
        validate_raw_option_values("generic", "--here", console, {"claude": {}, "generic": {}})

    assert exc.value.exit_code == 1
    assert "Invalid value for --ai-commands-dir" in console.export_text()


def test_resolve_project_target_uses_cwd_for_dot(tmp_path):
    console = Console(record=True)

    target = resolve_project_target(
        ".",
        False,
        False,
        console,
        cwd=tmp_path,
        confirm=lambda _message: True,
    )

    assert target.here is True
    assert target.project_name == tmp_path.name
    assert target.project_path == tmp_path


def test_resolve_project_target_rejects_existing_directory(tmp_path):
    console = Console(record=True)
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(typer.Exit) as exc:
        resolve_project_target(
            str(existing),
            False,
            False,
            console,
            cwd=tmp_path,
            confirm=lambda _message: True,
        )

    assert exc.value.exit_code == 1
    assert "Directory Conflict" in console.export_text()


def test_resolve_ai_selection_normalizes_alias():
    console = Console(record=True)

    selected_ai, ai_skills = resolve_ai_selection(
        "kiro",
        False,
        None,
        console,
        {
            "claude": {"name": "Claude Code"},
            "generic": {"name": "Generic"},
            "kiro-cli": {"name": "Kiro CLI"},
        },
        aliases={"kiro": "kiro-cli"},
        select_fn=lambda *_args, **_kwargs: "claude",
        resolve_ai_skills_mode_fn=lambda selected_ai, _raw_ai, ai_skills, _console: ai_skills,
    )

    assert selected_ai == "kiro-cli"
    assert ai_skills is False


def test_resolve_ai_selection_requires_commands_dir_for_generic():
    console = Console(record=True)

    with pytest.raises(typer.Exit) as exc:
        resolve_ai_selection(
            "generic",
            False,
            None,
            console,
            {
                "claude": {"name": "Claude Code"},
                "generic": {"name": "Generic"},
            },
            aliases={},
            select_fn=lambda *_args, **_kwargs: "claude",
            resolve_ai_skills_mode_fn=lambda selected_ai, _raw_ai, ai_skills, _console: ai_skills,
        )

    assert exc.value.exit_code == 1
    assert "--ai-commands-dir is required when using --ai generic" in console.export_text()


def test_resolve_ai_selection_rejects_ai_commands_dir_for_non_generic():
    console = Console(record=True)

    with pytest.raises(typer.Exit) as exc:
        resolve_ai_selection(
            "claude",
            False,
            ".myagent/commands",
            console,
            {
                "claude": {"name": "Claude Code"},
                "generic": {"name": "Generic"},
            },
            aliases={},
            select_fn=lambda *_args, **_kwargs: "claude",
            resolve_ai_skills_mode_fn=lambda selected_ai, _raw_ai, ai_skills, _console: ai_skills,
        )

    assert exc.value.exit_code == 1
    assert "can only be used with --ai generic" in console.export_text()


def test_resolve_script_selection_uses_platform_default_for_non_tty():
    console = Console(record=True)

    selected_script = resolve_script_selection(
        None,
        {"sh": "POSIX Shell", "ps": "PowerShell"},
        console,
        os_name="posix",
        stdin_is_tty=False,
        select_fn=lambda *_args, **_kwargs: "ps",
    )

    assert selected_script == "sh"


def test_build_init_tracker_adds_ai_skills_step_only_when_enabled():
    tracker = build_init_tracker("claude", "sh", False, tracker_cls=FakeTracker)
    assert not any(step[0] == "ai-skills" for step in tracker.steps)

    tracker_with_skills = build_init_tracker("claude", "sh", True, tracker_cls=FakeTracker)
    assert any(step[0] == "ai-skills" for step in tracker_with_skills.steps)


def test_install_requested_preset_prefers_local_directory(tmp_path):
    console = Console(record=True)
    project_path = tmp_path / "project"
    project_path.mkdir()
    preset_dir = tmp_path / "preset-dir"
    preset_dir.mkdir()
    (preset_dir / "preset.yml").write_text("name: demo\n", encoding="utf-8")

    class FakePresetManager:
        def __init__(self, project_root: Path):
            assert project_root == project_path
            self.installed_from_dir = None

        def install_from_directory(self, local_path: Path, version: str):
            self.installed_from_dir = (local_path, version)
            FakePresetManager.last_call = self.installed_from_dir

    install_requested_preset(
        project_path,
        str(preset_dir),
        "1.2.3",
        console,
        preset_manager_cls=FakePresetManager,
    )

    assert FakePresetManager.last_call == (preset_dir.resolve(), "1.2.3")
