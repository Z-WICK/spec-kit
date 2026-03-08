import shutil
import subprocess
from pathlib import Path

import pytest


def _run_gate(script_path: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script_path), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_failed(result: subprocess.CompletedProcess[str], message: str) -> None:
    assert result.returncode != 0, f"expected failure but got {result.returncode}"
    combined = f"{result.stdout}\n{result.stderr}"
    assert message in combined, combined


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for pipeline gate tests")
def test_stage5_fails_with_unchecked_tasks(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "bash" / "pipeline-stage-gate.sh"

    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()
    (feature_dir / "implementation-summary.md").write_text("done\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("- [ ] T001 Pending task\n", encoding="utf-8")

    result = _run_gate(
        script_path,
        ["--stage", "5", "--feature-dir", str(feature_dir)],
        cwd=tmp_path,
    )

    _assert_failed(result, "unchecked tasks remain")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for pipeline gate tests")
def test_stage5_passes_when_tasks_completed(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "bash" / "pipeline-stage-gate.sh"

    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()
    (feature_dir / "implementation-summary.md").write_text("done\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("- [x] T001 Done task\n", encoding="utf-8")

    result = _run_gate(
        script_path,
        ["--stage", "5", "--feature-dir", str(feature_dir)],
        cwd=tmp_path,
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for pipeline gate tests")
def test_stage2_requires_feature_dir(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "bash" / "pipeline-stage-gate.sh"

    missing_dir = tmp_path / "missing"
    result = _run_gate(
        script_path,
        ["--stage", "2", "--feature-dir", str(missing_dir)],
        cwd=tmp_path,
    )

    _assert_failed(result, "feature directory not found")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required for pipeline gate tests")
def test_receipt_requires_top_level_stage(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "bash" / "pipeline-stage-gate.sh"

    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()
    (feature_dir / "spec.md").write_text("## Clarifications\n- Q: ok -> A: ok | Source: doc\n", encoding="utf-8")

    receipt_path = tmp_path / "stage-1.receipt.json"
    receipt_path.write_text('{"status":"completed","metadata":{"stage":"1"}}\n', encoding="utf-8")

    result = _run_gate(
        script_path,
        [
            "--stage",
            "1",
            "--feature-dir",
            str(feature_dir),
            "--worktree-root",
            str(tmp_path),
            "--receipt",
            str(receipt_path),
        ],
        cwd=tmp_path,
    )

    _assert_failed(result, "receipt missing stage")
