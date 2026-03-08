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


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for release packaging tests")
def test_release_packages_codex_use_agents_skills_only(tmp_path):
    """Codex packages should emit skills only under .agents/skills."""
    repo_root = Path(__file__).resolve().parents[1]
    fixture_root = tmp_path / "fixture-repo-codex"
    fixture_root.mkdir()

    for rel in (".github", "templates", "scripts", "memory"):
        shutil.copytree(repo_root / rel, fixture_root / rel)

    release_script = fixture_root / ".github" / "workflows" / "scripts" / "create-release-packages.sh"
    env = os.environ.copy()
    env["AGENTS"] = "codex"
    env["SCRIPTS"] = "sh"

    result = subprocess.run(
        ["bash", str(release_script), "v9.9.9"],
        cwd=fixture_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    skill_file = fixture_root / ".genreleases" / "sdd-codex-package-sh" / ".agents" / "skills" / "speckit-plan" / "SKILL.md"
    legacy_codex_dir = fixture_root / ".genreleases" / "sdd-codex-package-sh" / ".codex" / "skills"
    codex_template_agents_dir = fixture_root / ".genreleases" / "sdd-codex-package-sh" / ".specify" / "templates" / "agents"

    assert skill_file.exists()
    assert not legacy_codex_dir.exists()
    assert not codex_template_agents_dir.exists()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for release packaging tests")
def test_release_packages_codex_pipeline_gate_matches_source(tmp_path):
    """Codex packages should include the latest pipeline stage gate scripts."""
    repo_root = Path(__file__).resolve().parents[1]
    fixture_root = tmp_path / "fixture-repo-codex-gate"
    fixture_root.mkdir()

    for rel in (".github", "templates", "scripts", "memory"):
        shutil.copytree(repo_root / rel, fixture_root / rel)

    release_script = fixture_root / ".github" / "workflows" / "scripts" / "create-release-packages.sh"
    env = os.environ.copy()
    env["AGENTS"] = "codex"
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

    source_sh = (repo_root / "scripts" / "bash" / "pipeline-stage-gate.sh").read_text(encoding="utf-8")
    source_ps = (repo_root / "scripts" / "powershell" / "pipeline-stage-gate.ps1").read_text(encoding="utf-8")

    packaged_sh = (
        fixture_root
        / ".genreleases"
        / "sdd-codex-package-sh"
        / ".specify"
        / "scripts"
        / "bash"
        / "pipeline-stage-gate.sh"
    ).read_text(encoding="utf-8")
    packaged_ps = (
        fixture_root
        / ".genreleases"
        / "sdd-codex-package-ps"
        / ".specify"
        / "scripts"
        / "powershell"
        / "pipeline-stage-gate.ps1"
    ).read_text(encoding="utf-8")

    assert packaged_sh == source_sh
    assert packaged_ps == source_ps


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for release packaging tests")
def test_release_packages_droid_pipeline_gate_matches_source(tmp_path):
    """Droid packages should include the latest pipeline stage gate scripts."""
    repo_root = Path(__file__).resolve().parents[1]
    fixture_root = tmp_path / "fixture-repo-droid-gate"
    fixture_root.mkdir()

    for rel in (".github", "templates", "scripts", "memory"):
        shutil.copytree(repo_root / rel, fixture_root / rel)

    release_script = fixture_root / ".github" / "workflows" / "scripts" / "create-release-packages.sh"
    env = os.environ.copy()
    env["AGENTS"] = "droid"
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

    source_sh = (repo_root / "scripts" / "bash" / "pipeline-stage-gate.sh").read_text(encoding="utf-8")
    source_ps = (repo_root / "scripts" / "powershell" / "pipeline-stage-gate.ps1").read_text(encoding="utf-8")

    packaged_sh = (
        fixture_root
        / ".genreleases"
        / "sdd-droid-package-sh"
        / ".specify"
        / "scripts"
        / "bash"
        / "pipeline-stage-gate.sh"
    ).read_text(encoding="utf-8")
    packaged_ps = (
        fixture_root
        / ".genreleases"
        / "sdd-droid-package-ps"
        / ".specify"
        / "scripts"
        / "powershell"
        / "pipeline-stage-gate.ps1"
    ).read_text(encoding="utf-8")

    assert packaged_sh == source_sh
    assert packaged_ps == source_ps


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for release packaging tests")
def test_release_packages_droid_use_skills_with_legacy_commands_copy(tmp_path):
    """Droid packages should emit .factory/skills and mirror to .factory/commands."""
    repo_root = Path(__file__).resolve().parents[1]
    fixture_root = tmp_path / "fixture-repo-droid"
    fixture_root.mkdir()

    for rel in (".github", "templates", "scripts", "memory"):
        shutil.copytree(repo_root / rel, fixture_root / rel)

    release_script = fixture_root / ".github" / "workflows" / "scripts" / "create-release-packages.sh"
    env = os.environ.copy()
    env["AGENTS"] = "droid"
    env["SCRIPTS"] = "sh"

    result = subprocess.run(
        ["bash", str(release_script), "v9.9.9"],
        cwd=fixture_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    skill_cmd = fixture_root / ".genreleases" / "sdd-droid-package-sh" / ".factory" / "skills" / "speckit.plan.md"
    legacy_cmd = fixture_root / ".genreleases" / "sdd-droid-package-sh" / ".factory" / "commands" / "speckit.plan.md"

    assert skill_cmd.exists()
    assert legacy_cmd.exists()
