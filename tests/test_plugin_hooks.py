import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _collect_command_hooks(entries: list[dict]) -> list[dict]:
    command_hooks: list[dict] = []
    for entry in entries:
        if entry.get("type") == "command":
            command_hooks.append(entry)
        for nested in entry.get("hooks", []):
            if nested.get("type") == "command":
                command_hooks.append(nested)
    return command_hooks


def test_claude_plugin_hook_config_present():
    hook_config = REPO_ROOT / "plugins" / "spec-kit" / "hooks" / "hooks.json"
    assert hook_config.exists()

    payload = json.loads(hook_config.read_text(encoding="utf-8"))
    hooks = payload.get("hooks", {})
    assert isinstance(hooks, dict)

    session_start_hooks = hooks.get("SessionStart")
    assert isinstance(session_start_hooks, list) and session_start_hooks
    matchers = {entry.get("matcher") for entry in session_start_hooks}
    assert matchers == {"startup", "resume", "clear"}

    session_commands = _collect_command_hooks(session_start_hooks)
    assert session_commands, "SessionStart hooks must include a command hook"
    assert all(
        "session-start-update-reminder.sh" in hook.get("command", "")
        for hook in session_commands
    )

    stop_hooks = hooks.get("Stop")
    assert isinstance(stop_hooks, list) and stop_hooks
    stop_commands = _collect_command_hooks(stop_hooks)
    assert stop_commands, "Stop hooks must include a command hook"
    assert any(
        "pipeline-gate-hook.sh" in hook.get("command", "") for hook in stop_commands
    )


def test_claude_plugin_hook_scripts_exist():
    pipeline_hook = REPO_ROOT / "plugins" / "spec-kit" / "scripts" / "pipeline-gate-hook.sh"
    reminder_hook = REPO_ROOT / "plugins" / "spec-kit" / "scripts" / "session-start-update-reminder.sh"

    assert pipeline_hook.exists()
    assert reminder_hook.exists()

    assert "pipeline-stage-gate.sh" in pipeline_hook.read_text(encoding="utf-8")
    reminder_text = reminder_hook.read_text(encoding="utf-8")
    assert "/speckit.update" in reminder_text
    assert "releases/latest" in reminder_text
    assert "SPEC_KIT_RELEASE_LATEST" in reminder_text


def _run_session_start_reminder(script_path: Path, project_root: Path, *, latest_release: str, source: str = "startup") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script_path)],
        input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(project_root), "source": source}),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **{"SPEC_KIT_RELEASE_LATEST": latest_release}},
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for plugin hook tests")
def test_session_start_reminder_warns_when_release_latest_is_newer(tmp_path: Path):
    project_root = tmp_path / "project"
    (project_root / ".specify").mkdir(parents=True)
    (project_root / ".claude" / "commands").mkdir(parents=True)
    (project_root / ".specify" / ".version").write_text("v1.0.26\n", encoding="utf-8")
    (project_root / ".claude" / "commands" / "speckit.update.md").write_text("update\n", encoding="utf-8")
    nested_dir = project_root / "apps" / "web"
    nested_dir.mkdir(parents=True)

    script_path = REPO_ROOT / "plugins" / "spec-kit" / "scripts" / "session-start-update-reminder.sh"
    result = _run_session_start_reminder(script_path, nested_dir, latest_release="v1.0.27")

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    payload = json.loads(result.stdout)
    assert "/speckit.update" in payload["systemMessage"]
    assert "v1.0.27" in payload["systemMessage"]
    assert "v1.0.26" in payload["systemMessage"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for plugin hook tests")
def test_session_start_reminder_stays_quiet_when_project_matches_release(tmp_path: Path):
    project_root = tmp_path / "project"
    (project_root / ".specify").mkdir(parents=True)
    (project_root / ".claude" / "commands").mkdir(parents=True)
    (project_root / ".specify" / ".version").write_text("v1.0.26\n", encoding="utf-8")
    (project_root / ".claude" / "commands" / "speckit.update.md").write_text("update\n", encoding="utf-8")

    script_path = REPO_ROOT / "plugins" / "spec-kit" / "scripts" / "session-start-update-reminder.sh"
    result = _run_session_start_reminder(script_path, project_root, latest_release="v1.0.26", source="resume")

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert result.stdout.strip() == ""


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for plugin hook tests")
def test_session_start_reminder_ignores_plugin_manifest_if_release_is_not_newer(tmp_path: Path):
    plugin_root = tmp_path / "plugin"
    manifest_dir = plugin_root / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "spec-kit", "version": "9.9.9"}),
        encoding="utf-8",
    )

    project_root = tmp_path / "project"
    (project_root / ".specify").mkdir(parents=True)
    (project_root / ".claude" / "commands").mkdir(parents=True)
    (project_root / ".specify" / ".version").write_text("v1.0.26\n", encoding="utf-8")
    (project_root / ".claude" / "commands" / "speckit.update.md").write_text("update\n", encoding="utf-8")

    script_path = REPO_ROOT / "plugins" / "spec-kit" / "scripts" / "session-start-update-reminder.sh"
    result = subprocess.run(
        ["bash", str(script_path)],
        input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(project_root), "source": "clear"}),
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            **{
                "CLAUDE_PLUGIN_ROOT": str(plugin_root),
                "SPEC_KIT_RELEASE_LATEST": "v1.0.26",
            },
        },
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert result.stdout.strip() == ""
