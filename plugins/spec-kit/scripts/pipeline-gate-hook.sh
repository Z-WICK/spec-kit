#!/usr/bin/env bash
set -euo pipefail

project_root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
state_file="$project_root/.specify/pipeline-state.json"
gate_script="$project_root/.specify/scripts/bash/pipeline-stage-gate.sh"

if [[ ! -f "$state_file" ]] || [[ ! -f "$gate_script" ]]; then
  exit 0
fi

python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
fi

if [[ -z "$python_bin" ]]; then
  exit 0
fi

state_output="$("$python_bin" - <<'PY' "$state_file")" || exit 0
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

def val(key: str) -> str:
    raw = data.get(key)
    if raw is None:
        return ""
    return str(raw)

print(val("pipeline_id"))
print(val("current_stage"))
print(val("feature_dir"))
print(val("worktree_root"))
print(val("main_repo_root"))
PY

pipeline_id="$(printf '%s\n' "$state_output" | sed -n '1p')"
current_stage="$(printf '%s\n' "$state_output" | sed -n '2p')"
feature_dir="$(printf '%s\n' "$state_output" | sed -n '3p')"
worktree_root="$(printf '%s\n' "$state_output" | sed -n '4p')"
main_repo_root="$(printf '%s\n' "$state_output" | sed -n '5p')"

if [[ -z "$current_stage" ]]; then
  exit 0
fi

if [[ -z "$main_repo_root" ]]; then
  main_repo_root="$project_root"
fi

runtime_dir=""
docs_summary_file=""
receipt=""
if [[ -n "$pipeline_id" ]] && [[ -n "$main_repo_root" ]]; then
  runtime_dir="$main_repo_root/.specify/pipeline-runtime/$pipeline_id"
  docs_summary_file="$runtime_dir/docs-summary.md"
  receipt="$runtime_dir/stage-${current_stage}.receipt.json"
fi

base_branch=""
project_config="$project_root/.specify/.project"
if [[ -f "$project_config" ]]; then
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    [[ "$line" == \#* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    if [[ "$key" == "BASE_BRANCH" ]]; then
      base_branch="$value"
      break
    fi
  done < "$project_config"
fi

gate_args=(--stage "$current_stage")

if [[ -n "$feature_dir" ]]; then
  gate_args+=(--feature-dir "$feature_dir")
fi

if [[ -n "$worktree_root" ]]; then
  gate_args+=(--worktree-root "$worktree_root")
fi

if [[ -n "$docs_summary_file" ]]; then
  gate_args+=(--docs-summary-file "$docs_summary_file")
fi

if [[ -n "$main_repo_root" ]]; then
  gate_args+=(--main-repo-root "$main_repo_root")
fi

if [[ -n "$base_branch" ]]; then
  gate_args+=(--base-branch "$base_branch")
fi

if [[ -n "$receipt" ]]; then
  gate_args+=(--receipt "$receipt")
fi

if ! gate_output="$("$gate_script" "${gate_args[@]}" 2>&1)"; then
  printf '%s\n' "$gate_output" >&2
  echo "Spec Kit pipeline gate failed for stage ${current_stage}. Resolve missing artifacts or rerun /speckit.pipeline to resume." >&2
  exit 2
fi
