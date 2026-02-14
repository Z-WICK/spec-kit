"""Validation helpers for enhanced command templates and release mappings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple

import yaml

from .agents import AGENT_COMMAND_CONFIGS


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


def _lint_release_scripts(repo_root: Path, result: LintResult) -> None:
    expected_agents = list(AGENT_COMMAND_CONFIGS.keys())
    expected_by_agent = {k: v["dir"] for k, v in AGENT_COMMAND_CONFIGS.items()}

    sh_script = repo_root / ".github" / "workflows" / "scripts" / "create-release-packages.sh"
    ps_script = repo_root / ".github" / "workflows" / "scripts" / "create-release-packages.ps1"
    release_script = repo_root / ".github" / "workflows" / "scripts" / "create-github-release.sh"

    sh_content = _read_checked_text(sh_script, result)
    ps_content = _read_checked_text(ps_script, result)
    release_content = _read_checked_text(release_script, result)
    if not sh_content or not ps_content or not release_content:
        return

    sh_agents = _extract_shell_array(sh_content, "ALL_AGENTS")
    ps_agents = _extract_ps_array(ps_content, "AllAgents")

    if set(sh_agents) != set(expected_agents):
        result.errors.append(
            f"{sh_script}: ALL_AGENTS mismatch. expected={sorted(expected_agents)} actual={sorted(sh_agents)}"
        )
    if set(ps_agents) != set(expected_agents):
        result.errors.append(
            f"{ps_script}: $AllAgents mismatch. expected={sorted(expected_agents)} actual={sorted(ps_agents)}"
        )

    for agent, command_dir in expected_by_agent.items():
        sh_pattern = re.compile(
            rf"generate_commands\s+{re.escape(agent)}\s+.*?\"\$base_dir/{re.escape(command_dir)}\""
        )
        if not sh_pattern.search(sh_content):
            result.errors.append(
                f"{sh_script}: agent '{agent}' is not mapped to '{command_dir}'"
            )

        ps_pattern = re.compile(
            rf"'{re.escape(agent)}'\s*\{{[\s\S]*?Join-Path \$baseDir \"{re.escape(command_dir)}\"",
            flags=re.DOTALL,
        )
        if not ps_pattern.search(ps_content):
            result.errors.append(
                f"{ps_script}: agent '{agent}' is not mapped to '{command_dir}'"
            )

        for variant in ("sh", "ps"):
            asset = f'spec-kit-template-{agent}-{variant}-"$VERSION".zip'
            if asset not in release_content:
                result.errors.append(
                    f"{release_script}: missing release asset '{asset}'"
                )


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
    _lint_pipeline_gate_scripts(repo_root, result)
    _lint_execution_contract(repo_root, result)
    _lint_release_scripts(repo_root, result)
    return result
