import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="bash and git are required for update-agent-context script tests",
)
def test_update_agent_context_accepts_droid_agent_type(tmp_path):
    """Regression for #4/#9: droid should be a supported agent type."""
    repo_root = Path(__file__).resolve().parents[1]
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "001-droid"], cwd=repo, check=True, capture_output=True, text=True)

    scripts_dir = repo / "scripts" / "bash"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(repo_root / "scripts" / "bash" / "update-agent-context.sh", scripts_dir / "update-agent-context.sh")
    shutil.copy2(repo_root / "scripts" / "bash" / "common.sh", scripts_dir / "common.sh")
    shutil.copy2(repo_root / "scripts" / "bash" / "agent-registry.sh", scripts_dir / "agent-registry.sh")
    shutil.copy2(repo_root / "scripts" / "agent-registry.txt", repo / "scripts" / "agent-registry.txt")
    (scripts_dir / "update-agent-context.sh").chmod(0o755)

    (repo / ".specify" / "templates").mkdir(parents=True)
    (repo / ".specify" / "templates" / "agent-file-template.md").write_text(
        "# Agent File Template\n\n"
        "**Last updated**: [DATE]\n\n"
        "## Active Technologies\n\n"
        "## Recent Changes\n",
        encoding="utf-8",
    )

    (repo / "specs" / "001-droid").mkdir(parents=True)
    (repo / "specs" / "001-droid" / "plan.md").write_text(
        "**Language/Version**: Python 3.12\n"
        "**Primary Dependencies**: pytest\n"
        "**Storage**: N/A\n"
        "**Project Type**: cli\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(scripts_dir / "update-agent-context.sh"), "droid"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "Unknown agent type 'droid'" not in result.stdout
    assert "Unknown agent type 'droid'" not in result.stderr
    droid_context = repo / ".factory" / "rules" / "specify-rules.md"
    assert droid_context.exists()
