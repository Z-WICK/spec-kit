import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_claude_plugin_hook_config_present():
    hook_config = REPO_ROOT / "plugins" / "spec-kit" / "hooks" / "hooks.json"
    assert hook_config.exists()

    payload = json.loads(hook_config.read_text(encoding="utf-8"))
    hooks = payload.get("hooks", {})
    assert isinstance(hooks, dict)
    stop_hooks = hooks.get("Stop")
    assert isinstance(stop_hooks, list) and stop_hooks

    command_hooks = []
    for hook in stop_hooks:
        if hook.get("type") == "command":
            command_hooks.append(hook)
        for nested in hook.get("hooks", []):
            if nested.get("type") == "command":
                command_hooks.append(nested)

    assert command_hooks, "Stop hooks must include a command hook"
    assert any(
        "pipeline-gate-hook.sh" in hook.get("command", "") for hook in command_hooks
    )


def test_claude_plugin_hook_script_exists():
    hook_script = (
        REPO_ROOT
        / "plugins"
        / "spec-kit"
        / "scripts"
        / "pipeline-gate-hook.sh"
    )
    assert hook_script.exists()
    text = hook_script.read_text(encoding="utf-8")
    assert "pipeline-stage-gate.sh" in text
