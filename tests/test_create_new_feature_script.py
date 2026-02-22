import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bash" / "create-new-feature.sh"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for script tests")
def test_create_new_feature_ignores_fetch_stdout_noise(tmp_path):
    """Regression for issue #1592: fetch stdout must not corrupt BRANCH_NUMBER."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".specify" / "templates").mkdir(parents=True)
    (repo / "specs").mkdir()
    (repo / ".specify" / "templates" / "spec-template.md").write_text("# Spec template\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text(
        """#!/usr/bin/env bash
set -e
cmd="$1"
shift || true
case "$cmd" in
  rev-parse)
    if [ "${1:-}" = "--show-toplevel" ]; then
      pwd
      exit 0
    fi
    ;;
  fetch)
    # This message used to leak into BRANCH_NUMBER via command substitution.
    echo "Fetching origin"
    exit 0
    ;;
  branch)
    echo "* main"
    echo "  remotes/origin/main"
    exit 0
    ;;
  checkout)
    exit 0
    ;;
  *)
    echo "Unexpected git command in test stub: $cmd" >&2
    exit 1
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--json", "Native-like month/year scrolling selector mode"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["FEATURE_NUM"] == "001"
    assert payload["BRANCH_NAME"].startswith("001-")
    assert (repo / "specs" / payload["BRANCH_NAME"] / "spec.md").exists()
