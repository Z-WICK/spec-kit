import json
import zipfile
from pathlib import Path

import pytest

from specify_cli.template_runtime import (
    _resolve_project_relative_path,
    _validate_zip_members,
    merge_json_files,
    should_preserve_existing_on_reinit,
)


@pytest.mark.parametrize(
    ("raw_path", "expected"),
    [
        ("specs/auth/spec.md", True),
        (".specify/memory/constitution.md", True),
        (".specify/extensions/example.yml", True),
        (".specify/.project/profile.yml", True),
        (".specify/pipeline-state-backup.json", True),
        ("README.md", False),
        (".specify/templates/constitution-template.md", False),
    ],
)
def test_should_preserve_existing_on_reinit(raw_path: str, expected: bool):
    assert should_preserve_existing_on_reinit(Path(raw_path)) is expected


def test_merge_json_files_deep_merges_nested_dicts(tmp_path):
    existing_path = tmp_path / "settings.json"
    existing_path.write_text(
        json.dumps(
            {
                "editor": {"tabSize": 2, "formatOnSave": False},
                "files.exclude": {"node_modules": True},
            }
        ),
        encoding="utf-8",
    )

    merged = merge_json_files(
        existing_path,
        {
            "editor": {"formatOnSave": True},
            "search.exclude": {"dist": True},
        },
    )

    assert merged == {
        "editor": {"tabSize": 2, "formatOnSave": True},
        "files.exclude": {"node_modules": True},
        "search.exclude": {"dist": True},
    }


@pytest.mark.parametrize("raw_path", ["/tmp/abs", "../escape", "", "."])
def test_resolve_project_relative_path_rejects_unsafe_input(tmp_path, raw_path):
    with pytest.raises(ValueError):
        _resolve_project_relative_path(raw_path, tmp_path)


def test_resolve_project_relative_path_normalizes_safe_path(tmp_path):
    resolved = _resolve_project_relative_path("./.myagent/commands", tmp_path)
    assert resolved == tmp_path / ".myagent" / "commands"


def test_validate_zip_members_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../escape.txt", "blocked")

    with zipfile.ZipFile(zip_path, "r") as zf:
        with pytest.raises(ValueError, match="unsafe path"):
            _validate_zip_members(zf, tmp_path / "dest")
