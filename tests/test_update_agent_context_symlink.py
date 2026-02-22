import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="bash and git are required for update-agent-context script tests",
)
def test_update_agent_context_preserves_symlink_target(tmp_path):
    """Regression for #1464: updating context must not replace a symlink file."""
    repo_root = Path(__file__).resolve().parents[1]
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "001-symlink"], cwd=repo, check=True, capture_output=True, text=True)

    scripts_dir = repo / "scripts" / "bash"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(repo_root / "scripts" / "bash" / "update-agent-context.sh", scripts_dir / "update-agent-context.sh")
    shutil.copy2(repo_root / "scripts" / "bash" / "common.sh", scripts_dir / "common.sh")
    (scripts_dir / "update-agent-context.sh").chmod(0o755)

    (repo / ".specify" / "templates").mkdir(parents=True)
    (repo / ".specify" / "templates" / "agent-file-template.md").write_text(
        "# Agent File Template\n\n## Active Technologies\n\n## Recent Changes\n",
        encoding="utf-8",
    )

    (repo / "specs" / "001-symlink").mkdir(parents=True)
    (repo / "specs" / "001-symlink" / "plan.md").write_text(
        "**Language/Version**: Python 3.12\n"
        "**Primary Dependencies**: pytest\n"
        "**Storage**: N/A\n"
        "**Project Type**: cli\n",
        encoding="utf-8",
    )

    agents_file = repo / "AGENTS.md"
    agents_file.write_text(
        "# Agent Context\n\n"
        "**Last updated**: 2026-01-01\n\n"
        "## Active Technologies\n"
        "- Existing\n\n"
        "## Recent Changes\n"
        "- 000-initial: Added baseline\n",
        encoding="utf-8",
    )

    symlink_file = repo / "CLAUDE.md"
    os.symlink("AGENTS.md", symlink_file)
    assert symlink_file.is_symlink()

    result = subprocess.run(
        ["bash", str(scripts_dir / "update-agent-context.sh"), "claude"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert symlink_file.is_symlink(), "CLAUDE.md should remain a symlink"
    assert symlink_file.resolve() == agents_file.resolve()
    assert "001-symlink" in agents_file.read_text(encoding="utf-8")
