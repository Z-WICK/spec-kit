import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for script tests")
def test_find_placeholders_scans_passed_agent_directory(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "bash" / "find-placeholders.sh"
    agent_dir = tmp_path / ".factory" / "commands"
    agent_dir.mkdir(parents=True)
    file_with_placeholder = agent_dir / "demo.md"
    file_with_placeholder.write_text("Value: [BUILD_COMMAND]\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(script), str(agent_dir)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "demo.md" in result.stdout
    assert "[BUILD_COMMAND]" in result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for script tests")
def test_find_placeholders_requires_agent_directory_argument(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "bash" / "find-placeholders.sh"

    result = subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Usage:" in result.stderr
