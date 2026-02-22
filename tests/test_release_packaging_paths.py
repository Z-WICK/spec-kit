import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for release packaging tests")
def test_release_packages_keep_script_matrix_and_placeholder(tmp_path):
    """Regression for #1609: generated commands should stay cross-platform."""
    repo_root = Path(__file__).resolve().parents[1]
    fixture_root = tmp_path / "fixture-repo"
    fixture_root.mkdir()

    for rel in (".github", "templates", "scripts", "memory"):
        shutil.copytree(repo_root / rel, fixture_root / rel)

    release_script = fixture_root / ".github" / "workflows" / "scripts" / "create-release-packages.sh"
    env = os.environ.copy()
    env["AGENTS"] = "claude"
    env["SCRIPTS"] = "sh,ps"

    result = subprocess.run(
        ["bash", str(release_script), "v9.9.9"],
        cwd=fixture_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    sh_command = fixture_root / ".genreleases" / "sdd-claude-package-sh" / ".claude" / "commands" / "speckit.plan.md"
    ps_command = fixture_root / ".genreleases" / "sdd-claude-package-ps" / ".claude" / "commands" / "speckit.plan.md"

    assert sh_command.exists()
    assert ps_command.exists()

    sh_text = sh_command.read_text(encoding="utf-8")
    ps_text = ps_command.read_text(encoding="utf-8")

    assert "{SCRIPT}" in sh_text
    assert "Run `{SCRIPT}` from repo root" in sh_text
    assert "scripts:" in sh_text
    assert "sh: .specify/scripts/bash/setup-plan.sh --json" in sh_text
    assert "ps: .specify/scripts/powershell/setup-plan.ps1 -Json" in sh_text

    # The command body should be identical regardless of selected build script type.
    assert sh_text == ps_text
