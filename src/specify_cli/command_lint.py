"""Validation helpers for enhanced command templates and release mappings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple

import yaml

from .agents import (
    AGENT_COMMAND_CONFIGS,
    AGENT_CONTEXT_CONFIGS,
    AGENT_PACKAGING_CONFIGS,
    get_agent_skills_dir_relative,
)


@dataclass
class LintResult:
    """Container for lint diagnostics."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _normalize_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _read_checked_text(path: Path, result: LintResult) -> str:
    if not path.exists():
        result.errors.append(f"{path}: file not found")
        return ""

    try:
        return _normalize_text(path)
    except OSError as exc:
        result.errors.append(f"{path}: failed to read file ({exc})")
        return ""


def _parse_frontmatter(path: Path, result: LintResult) -> Tuple[Dict[str, Any], str]:
    content = _read_checked_text(path, result)
    if not content:
        return {}, ""

    if not content.startswith("---\n"):
        result.errors.append(f"{path}: missing YAML frontmatter opening delimiter")
        return {}, content

    match = re.match(r"^---\n(.*?)\n---\n?", content, flags=re.DOTALL)
    if not match:
        result.errors.append(f"{path}: malformed YAML frontmatter")
        return {}, content

    fm_raw = match.group(1)
    body = content[match.end() :]

    try:
        frontmatter = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError as exc:
        result.errors.append(f"{path}: invalid YAML frontmatter ({exc})")
        return {}, body

    if not isinstance(frontmatter, dict):
        result.errors.append(f"{path}: frontmatter must be a mapping")
        return {}, body

    return frontmatter, body


def _extract_script_matrices(
    path: Path,
    section_name: str,
    section_value: Any,
    result: LintResult,
) -> List[Tuple[str, Dict[str, Any]]]:
    if not isinstance(section_value, dict):
        result.errors.append(f"{path}: frontmatter '{section_name}' must be a mapping")
        return []

    # Simple form:
    # scripts:
    #   sh: scripts/bash/...
    #   ps: scripts/powershell/...
    if "sh" in section_value or "ps" in section_value:
        return [(section_name, section_value)]

    # Nested form:
    # scripts:
    #   flyway:
    #     sh: ...
    #     ps: ...
    matrices: List[Tuple[str, Dict[str, Any]]] = []
    for label, value in section_value.items():
        if not isinstance(value, dict):
            result.errors.append(
                f"{path}: '{section_name}.{label}' must be a mapping with 'sh'/'ps'"
            )
            continue
        matrices.append((f"{section_name}.{label}", value))
    return matrices


def _first_token(command: str) -> str:
    command = command.strip()
    if not command:
        return ""
    return re.split(r"\s+", command, maxsplit=1)[0].strip("\"'")


def _validate_script_command(
    repo_root: Path,
    path: Path,
    context: str,
    command: str,
    result: LintResult,
) -> None:
    token = _first_token(command)
    if not token:
        result.errors.append(f"{path}: '{context}' command is empty")
        return

    if token.startswith("./"):
        token = token[2:]

    if not token.startswith("scripts/"):
        return

    script_path = repo_root / token
    if not script_path.exists():
        result.errors.append(
            f"{path}: '{context}' references missing script '{token}'"
        )


def _validate_script_section(
    repo_root: Path,
    path: Path,
    section_name: str,
    section_value: Any,
    result: LintResult,
) -> None:
    for label, mapping in _extract_script_matrices(path, section_name, section_value, result):
        for variant in ("sh", "ps"):
            value = mapping.get(variant)
            if not isinstance(value, str) or not value.strip():
                result.errors.append(f"{path}: '{label}' missing non-empty '{variant}' entry")
                continue
            _validate_script_command(repo_root, path, f"{label}.{variant}", value, result)


def _lint_command_templates(repo_root: Path, result: LintResult) -> None:
    templates_dir = repo_root / "templates" / "commands"
    if not templates_dir.exists():
        result.errors.append(f"{templates_dir}: directory not found")
        return

    template_files = sorted(templates_dir.glob("*.md"))
    if not template_files:
        result.errors.append(f"{templates_dir}: no command templates found")
        return

    for template in template_files:
        frontmatter, body = _parse_frontmatter(template, result)
        description = frontmatter.get("description")
        if not isinstance(description, str) or not description.strip():
            result.errors.append(f"{template}: frontmatter 'description' is required")

        has_script_placeholder = "{SCRIPT}" in body
        has_agent_script_placeholder = "{AGENT_SCRIPT}" in body

        scripts = frontmatter.get("scripts")
        agent_scripts = frontmatter.get("agent_scripts")

        if has_script_placeholder and scripts is None:
            result.errors.append(f"{template}: uses '{{SCRIPT}}' but frontmatter 'scripts' is missing")
        if has_agent_script_placeholder and agent_scripts is None:
            result.errors.append(
                f"{template}: uses '{{AGENT_SCRIPT}}' but frontmatter 'agent_scripts' is missing"
            )

        if scripts is not None:
            _validate_script_section(repo_root, template, "scripts", scripts, result)
        if agent_scripts is not None:
            _validate_script_section(repo_root, template, "agent_scripts", agent_scripts, result)

        if template.name == "init.md":
            legacy_markers = (
                "`.claude/` directory must already exist",
                "ERROR: .claude/ directory not found.",
            )
            for marker in legacy_markers:
                if marker in body:
                    result.errors.append(
                        f"{template}: still contains Claude-specific init prerequisite '{marker}'"
                    )
            if "AGENT_DIR" not in body:
                result.errors.append(
                    f"{template}: missing AGENT_DIR guidance for agent-specific initialization"
                )


def _lint_agent_templates(repo_root: Path, result: LintResult) -> None:
    agents_dir = repo_root / "templates" / "agents"
    if not agents_dir.exists():
        result.errors.append(f"{agents_dir}: directory not found")
        return

    agent_files = sorted(agents_dir.glob("*.md"))
    if not agent_files:
        result.errors.append(f"{agents_dir}: no agent templates found")
        return

    for template in agent_files:
        frontmatter, _ = _parse_frontmatter(template, result)
        name = frontmatter.get("name")
        description = frontmatter.get("description")

        if not isinstance(name, str) or not name.strip():
            result.errors.append(f"{template}: frontmatter 'name' is required")
        if not isinstance(description, str) or not description.strip():
            result.errors.append(f"{template}: frontmatter 'description' is required")

        if isinstance(name, str) and name.strip() and name.strip() != template.stem:
            result.warnings.append(
                f"{template}: frontmatter 'name' differs from file stem '{template.stem}'"
            )


def _lint_placeholder_scan_scripts(repo_root: Path, result: LintResult) -> None:
    bash_script = repo_root / "scripts" / "bash" / "find-placeholders.sh"
    ps_script = repo_root / "scripts" / "powershell" / "find-placeholders.ps1"
    init_template = repo_root / "templates" / "commands" / "init.md"

    bash_content = _read_checked_text(bash_script, result)
    ps_content = _read_checked_text(ps_script, result)
    init_content = _read_checked_text(init_template, result)
    if not bash_content or not ps_content or not init_content:
        return

    if ".claude" in bash_content:
        result.errors.append(
            f"{bash_script}: hardcoded '.claude' path detected; use agent-dir argument"
        )
    if ".claude" in ps_content:
        result.errors.append(
            f"{ps_script}: hardcoded '.claude' path detected; use agent-dir argument"
        )

    expected_invocation = '{SCRIPT} "<AGENT_DIR>"'
    if expected_invocation not in init_content:
        result.errors.append(
            "templates/commands/init.md: must invoke placeholder scan as "
            f"`{expected_invocation}`"
        )


def _extract_shell_array(content: str, name: str) -> List[str]:
    match = re.search(rf"{re.escape(name)}=\(([^)]*)\)", content, flags=re.DOTALL)
    if not match:
        return []
    return [item for item in re.split(r"\s+", match.group(1).strip()) if item]


def _extract_ps_array(content: str, name: str) -> List[str]:
    match = re.search(rf"\${re.escape(name)}\s*=\s*@\((.*?)\)", content, flags=re.DOTALL)
    if not match:
        return []
    return re.findall(r"'([^']+)'", match.group(1))


def _parse_agent_registry(repo_root: Path, result: LintResult) -> Dict[str, Dict[str, str]]:
    registry_path = repo_root / "scripts" / "agent-registry.txt"
    content = _read_checked_text(registry_path, result)
    if not content:
        return {}

    registry: Dict[str, Dict[str, str]] = {}
    expected_columns = 17
    column_names = (
        "agent",
        "display_name",
        "command_dir",
        "command_format",
        "args_token",
        "extension",
        "skills_dir",
        "context_file",
        "context_name",
        "context_format",
        "package_strategy",
        "root_copy_source",
        "root_copy_dest",
        "copy_agent_templates_to",
        "legacy_mirror_dir",
        "exclude_agent_templates",
        "copy_vscode_settings",
    )

    for lineno, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line or raw_line.startswith("#"):
            continue
        parts = raw_line.split("|")
        if len(parts) != expected_columns:
            result.errors.append(
                f"{registry_path}:{lineno}: expected {expected_columns} fields, found {len(parts)}"
            )
            continue
        row = dict(zip(column_names, parts))
        agent = row.pop("agent")
        registry[agent] = row

    return registry


def _lint_release_scripts(repo_root: Path, result: LintResult) -> None:
    expected_agents = list(AGENT_COMMAND_CONFIGS.keys())
    registry = _parse_agent_registry(repo_root, result)
    if not registry:
        return

    sh_script = repo_root / ".github" / "workflows" / "scripts" / "create-release-packages.sh"
    ps_script = repo_root / ".github" / "workflows" / "scripts" / "create-release-packages.ps1"
    release_script = repo_root / ".github" / "workflows" / "scripts" / "create-github-release.sh"

    sh_content = _read_checked_text(sh_script, result)
    ps_content = _read_checked_text(ps_script, result)
    release_content = _read_checked_text(release_script, result)
    if not sh_content or not ps_content or not release_content:
        return

    registry_agents = sorted(registry.keys())
    if registry_agents != sorted(expected_agents):
        result.errors.append(
            f"scripts/agent-registry.txt: agent set mismatch. expected={sorted(expected_agents)} actual={registry_agents}"
        )

    args_token_map = {
        "$ARGUMENTS": "markdown_args",
        "{{args}}": "toml_args",
    }

    for agent, command_cfg in AGENT_COMMAND_CONFIGS.items():
        row = registry.get(agent)
        if row is None:
            result.errors.append(
                f"scripts/agent-registry.txt: missing agent '{agent}'"
            )
            continue

        expected_context = AGENT_CONTEXT_CONFIGS[agent]
        expected_packaging = AGENT_PACKAGING_CONFIGS[agent]

        if row["command_dir"] != command_cfg["dir"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' command_dir mismatch. expected='{command_cfg['dir']}' actual='{row['command_dir']}'"
            )
        if row["command_format"] != command_cfg["format"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' command_format mismatch. expected='{command_cfg['format']}' actual='{row['command_format']}'"
            )
        if row["extension"] != command_cfg["extension"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' extension mismatch. expected='{command_cfg['extension']}' actual='{row['extension']}'"
            )
        if row["skills_dir"] != get_agent_skills_dir_relative(agent):
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' skills_dir mismatch. expected='{get_agent_skills_dir_relative(agent)}' actual='{row['skills_dir']}'"
            )
        expected_args_token = args_token_map.get(command_cfg["args"], "")
        if row["args_token"] != expected_args_token:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' args token mismatch. expected='{expected_args_token}' actual='{row['args_token']}'"
            )
        if row["context_file"] != expected_context["file"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' context_file mismatch. expected='{expected_context['file']}' actual='{row['context_file']}'"
            )
        if row["context_name"] != expected_context["name"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' context_name mismatch. expected='{expected_context['name']}' actual='{row['context_name']}'"
            )
        if row["context_format"] != expected_context["format"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' context_format mismatch. expected='{expected_context['format']}' actual='{row['context_format']}'"
            )
        if row["package_strategy"] != expected_packaging["strategy"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' package_strategy mismatch. expected='{expected_packaging['strategy']}' actual='{row['package_strategy']}'"
            )
        if row["root_copy_source"] != expected_packaging["root_copy_source"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' root_copy_source mismatch. expected='{expected_packaging['root_copy_source']}' actual='{row['root_copy_source']}'"
            )
        if row["root_copy_dest"] != expected_packaging["root_copy_dest"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' root_copy_dest mismatch. expected='{expected_packaging['root_copy_dest']}' actual='{row['root_copy_dest']}'"
            )
        if row["copy_agent_templates_to"] != expected_packaging["copy_agent_templates_to"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' copy_agent_templates_to mismatch. expected='{expected_packaging['copy_agent_templates_to']}' actual='{row['copy_agent_templates_to']}'"
            )
        if row["legacy_mirror_dir"] != expected_packaging["legacy_mirror_dir"]:
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' legacy_mirror_dir mismatch. expected='{expected_packaging['legacy_mirror_dir']}' actual='{row['legacy_mirror_dir']}'"
            )
        if row["exclude_agent_templates"] != ("1" if expected_packaging["exclude_agent_templates"] else "0"):
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' exclude_agent_templates mismatch"
            )
        if row["copy_vscode_settings"] != ("1" if expected_packaging["copy_vscode_settings"] else "0"):
            result.errors.append(
                f"scripts/agent-registry.txt: agent '{agent}' copy_vscode_settings mismatch"
            )

    if "agent-registry.sh" not in sh_content:
        result.errors.append(f"{sh_script}: must load scripts/bash/agent-registry.sh")
    if "agent-registry.ps1" not in ps_content:
        result.errors.append(f"{ps_script}: must load scripts/powershell/agent-registry.ps1")
    if "agent-registry.sh" not in release_content:
        result.errors.append(f"{release_script}: must load scripts/bash/agent-registry.sh")
    if 'for agent in "${AGENT_REGISTRY_ORDER[@]}"' not in release_content:
        result.errors.append(f"{release_script}: must iterate assets from AGENT_REGISTRY_ORDER")
    if "Get-AgentRegistry" not in ps_content:
        result.errors.append(f"{ps_script}: must derive agent list from Get-AgentRegistry")


def _lint_execution_contract(repo_root: Path, result: LintResult) -> None:
    contract = repo_root / "memory" / "execution-contract.md"
    if not contract.exists():
        result.errors.append(f"{contract}: missing shared execution contract")
        return

    pipeline = _read_checked_text(repo_root / "templates" / "commands" / "pipeline.md", result)
    fixbug = _read_checked_text(repo_root / "templates" / "commands" / "fixbug.md", result)
    if not pipeline or not fixbug:
        return
    contract_ref = ".specify/memory/execution-contract.md"

    if contract_ref not in pipeline:
        result.errors.append("templates/commands/pipeline.md: missing shared execution contract reference")
    if contract_ref not in fixbug:
        result.errors.append("templates/commands/fixbug.md: missing shared execution contract reference")


def _lint_pipeline_gate_scripts(repo_root: Path, result: LintResult) -> None:
    required = [
        "scripts/bash/pipeline-stage-gate.sh",
        "scripts/powershell/pipeline-stage-gate.ps1",
        "scripts/bash/clarify-requirement-guard.sh",
        "scripts/powershell/clarify-requirement-guard.ps1",
    ]
    for rel in required:
        path = repo_root / rel
        if not path.exists():
            result.errors.append(f"{path}: missing required gate script")


def lint_repository(repo_root: Path) -> LintResult:
    """Run repository-level checks for enhanced command consistency."""
    result = LintResult()
    _lint_command_templates(repo_root, result)
    _lint_agent_templates(repo_root, result)
    _lint_placeholder_scan_scripts(repo_root, result)
    _lint_pipeline_gate_scripts(repo_root, result)
    _lint_execution_contract(repo_root, result)
    _lint_release_scripts(repo_root, result)
    return result
