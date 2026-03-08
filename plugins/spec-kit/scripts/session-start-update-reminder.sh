#!/usr/bin/env bash
set -euo pipefail

python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
fi

if [[ -z "$python_bin" ]]; then
  exit 0
fi

hook_input="$(cat 2>/dev/null || true)"
project_root="${CLAUDE_PROJECT_DIR:-}"
latest_release="${SPEC_KIT_RELEASE_LATEST:-}"

if [[ -z "$latest_release" ]]; then
  if ! command -v curl >/dev/null 2>&1; then
    exit 0
  fi

  curl_args=(-fsSL --connect-timeout 1 --max-time 2)
  github_token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
  if [[ -n "$github_token" ]]; then
    curl_args+=(-H "Authorization: Bearer ${github_token}")
  fi

  release_payload="$(curl "${curl_args[@]}" "https://api.github.com/repos/Z-WICK/spec-kit/releases/latest" 2>/dev/null || true)"
  if [[ -z "$release_payload" ]]; then
    exit 0
  fi

  latest_release="$(RELEASE_PAYLOAD="$release_payload" "$python_bin" - <<'PY'
import json
import os

payload = os.environ.get("RELEASE_PAYLOAD", "")
try:
    data = json.loads(payload) if payload else {}
except json.JSONDecodeError:
    data = {}

print(str(data.get("tag_name", "")).strip())
PY
)"
fi

if [[ -z "$latest_release" ]]; then
  exit 0
fi

HOOK_INPUT="$hook_input" SPEC_KIT_RELEASE_LATEST="$latest_release" "$python_bin" - "$project_root" <<'PY'
import json
import os
import re
import sys
from pathlib import Path


env_project_root = sys.argv[1].strip() if len(sys.argv) > 1 else ""
hook_input = os.environ.get("HOOK_INPUT", "")
latest_release = os.environ.get("SPEC_KIT_RELEASE_LATEST", "").strip()

try:
    payload = json.loads(hook_input) if hook_input else {}
except json.JSONDecodeError:
    payload = {}

start_dir = Path(env_project_root or str(payload.get("cwd") or Path.cwd()))


def resolve_project_dir(current: Path) -> Path | None:
    for candidate in (current, *current.parents):
        project_version_file = candidate / ".specify" / ".version"
        project_update_command = candidate / ".claude" / "commands" / "speckit.update.md"
        if project_version_file.is_file() and project_update_command.is_file():
            return candidate
    return None


project_dir = resolve_project_dir(start_dir)
if project_dir is None:
    raise SystemExit(0)

project_version = (project_dir / ".specify" / ".version").read_text(encoding="utf-8").strip()
if not latest_release or not project_version:
    raise SystemExit(0)


def normalize(raw: str) -> tuple[int, ...] | None:
    cleaned = raw.strip()
    if cleaned.startswith(("v", "V")):
        cleaned = cleaned[1:]
    parts = cleaned.split(".")
    numbers: list[int] = []
    for part in parts:
        match = re.match(r"^(\d+)", part)
        if match is None:
            return None
        numbers.append(int(match.group(1)))
    return tuple(numbers)


release_tuple = normalize(latest_release)
project_tuple = normalize(project_version)
if release_tuple is None or project_tuple is None:
    raise SystemExit(0)

max_len = max(len(release_tuple), len(project_tuple))
release_tuple += (0,) * (max_len - len(release_tuple))
project_tuple += (0,) * (max_len - len(project_tuple))

if release_tuple <= project_tuple:
    raise SystemExit(0)

message = (
    "检测到 Spec Kit 已发布更新"
    f"（latest: {latest_release}，项目: {project_version}）。"
    "建议先运行 /speckit.update 同步项目内命令与模板，避免继续使用旧版工作流。"
)

json.dump(
    {
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        },
    },
    sys.stdout,
    ensure_ascii=False,
)
sys.stdout.write("\n")
PY
