#!/usr/bin/env bash

# Deterministic stage gate for speckit.pipeline.
# Purpose: reduce workflow drift on weaker models by verifying stage artifacts
# before allowing pipeline progression.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: pipeline-stage-gate.sh --stage <id> [options]

Required:
  --stage <id>                Stage id: 0|1|2|3|3.5|4|5|5.5|6|7|8|9

Optional:
  --feature-dir <path>        Feature directory (specs/xxx)
  --worktree-root <path>      Worktree root path
  --docs-summary-file <path>  Stage 0 summary markdown file
  --main-repo-root <path>     Main repo root (for optional git checks)
  --base-branch <name>        Base branch name (for optional git checks)
  --receipt <path>            Stage receipt JSON file
  --json                      Emit JSON result
  --help                      Show this help
EOF
}

json_mode=false
stage=""
feature_dir=""
worktree_root=""
docs_summary_file=""
main_repo_root=""
base_branch=""
receipt=""
evidence=()

add_evidence() {
  evidence+=("$1")
}

json_escape() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

emit_fail() {
  local message=$1
  if $json_mode; then
    printf '{"ok":false,"stage":"%s","error":"%s"}\n' \
      "$(json_escape "$stage")" "$(json_escape "$message")"
  else
    echo "ERROR: $message" >&2
  fi
  exit 1
}

emit_ok() {
  if $json_mode; then
    local json='['
    local first=true
    local item
    for item in "${evidence[@]}"; do
      if $first; then
        first=false
      else
        json+=","
      fi
      json+="\"$(json_escape "$item")\""
    done
    json+="]"
    printf '{"ok":true,"stage":"%s","evidence":%s}\n' "$(json_escape "$stage")" "$json"
  else
    echo "OK: stage $stage gate passed"
  fi
}

require_file() {
  local path=$1
  local label=$2
  [[ -n "$path" ]] || emit_fail "$label path is empty"
  [[ -f "$path" ]] || emit_fail "$label not found: $path"
  [[ -s "$path" ]] || emit_fail "$label is empty: $path"
  add_evidence "$path"
}

require_dir() {
  local path=$1
  local label=$2
  [[ -n "$path" ]] || emit_fail "$label path is empty"
  [[ -d "$path" ]] || emit_fail "$label not found: $path"
  add_evidence "$path"
}

check_receipt() {
  [[ -z "$receipt" ]] && return 0
  require_file "$receipt" "stage receipt"

  if ! grep -Eq "\"stage\"[[:space:]]*:[[:space:]]*\"?$stage\"?" "$receipt"; then
    emit_fail "receipt stage mismatch: expected $stage in $receipt"
  fi

  if ! grep -Eq "\"status\"[[:space:]]*:[[:space:]]*\"(completed|success|passed)\"" "$receipt"; then
    emit_fail "receipt status must be completed/success/passed: $receipt"
  fi
}

has_checked_tasks() {
  local found=false
  local task_file

  if [[ -f "$feature_dir/tasks.md" ]] && grep -Eq '^[[:space:]]*-[[:space:]]*\[x\]' "$feature_dir/tasks.md"; then
    add_evidence "$feature_dir/tasks.md"
    found=true
  fi

  while IFS= read -r task_file; do
    if grep -Eq '^[[:space:]]*-[[:space:]]*\[x\]' "$task_file"; then
      add_evidence "$task_file"
      found=true
      break
    fi
  done < <(find "$feature_dir" -maxdepth 1 -type f -name 'tasks-*.md' 2>/dev/null | sort)

  [[ "$found" == true ]]
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage)
      stage="${2:-}"
      shift 2
      ;;
    --feature-dir)
      feature_dir="${2:-}"
      shift 2
      ;;
    --worktree-root)
      worktree_root="${2:-}"
      shift 2
      ;;
    --docs-summary-file)
      docs_summary_file="${2:-}"
      shift 2
      ;;
    --main-repo-root)
      main_repo_root="${2:-}"
      shift 2
      ;;
    --base-branch)
      base_branch="${2:-}"
      shift 2
      ;;
    --receipt)
      receipt="${2:-}"
      shift 2
      ;;
    --json)
      json_mode=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      emit_fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$stage" ]] || emit_fail "--stage is required"

case "$stage" in
  0)
    [[ -n "$docs_summary_file" ]] || emit_fail "stage 0 requires --docs-summary-file"
    require_file "$docs_summary_file" "docs summary"
    ;;
  1)
    require_dir "$worktree_root" "worktree root"
    require_dir "$feature_dir" "feature directory"
    require_file "$feature_dir/spec.md" "spec.md"
    ;;
  2)
    require_file "$feature_dir/spec.md" "spec.md"
    if ! grep -Eqi '(^##[[:space:]]+Clarifications)|clarification' "$feature_dir/spec.md"; then
      emit_fail "spec.md does not contain clarification markers"
    fi
    if ! grep -Eq '^[[:space:]]*-[[:space:]]*Q:.*Source:[[:space:]]*\S+' "$feature_dir/spec.md"; then
      emit_fail "stage 2 requires clarification entries with Source anchors"
    fi
    ;;
  3)
    require_file "$feature_dir/plan.md" "plan.md"
    require_file "$feature_dir/research.md" "research.md"
    ;;
  3.5)
    if [[ -f "$feature_dir/impact-pre-analysis.md" ]]; then
      require_file "$feature_dir/impact-pre-analysis.md" "impact-pre-analysis.md"
    elif [[ -f "$feature_dir/plan.md" ]] && grep -Eqi 'impact|risk|风险' "$feature_dir/plan.md"; then
      add_evidence "$feature_dir/plan.md"
    else
      emit_fail "stage 3.5 requires impact-pre-analysis.md or impact warnings in plan.md"
    fi
    ;;
  4)
    if [[ -f "$feature_dir/tasks.md" ]]; then
      require_file "$feature_dir/tasks.md" "tasks.md"
    elif [[ -f "$feature_dir/tasks-index.md" ]]; then
      require_file "$feature_dir/tasks-index.md" "tasks-index.md"
      if ! find "$feature_dir" -maxdepth 1 -type f -name 'tasks-*.md' | grep -q .; then
        emit_fail "tasks-index.md found but no tasks-<module>.md shards"
      fi
      add_evidence "$feature_dir/tasks-index.md + tasks-*.md"
    else
      emit_fail "stage 4 requires tasks.md or (tasks-index.md + tasks-*.md)"
    fi
    ;;
  5)
    require_file "$feature_dir/implementation-summary.md" "implementation-summary.md"
    if ! has_checked_tasks; then
      emit_fail "stage 5 requires checked task markers ([x]) in tasks files"
    fi
    if [[ -n "$base_branch" ]] && [[ -n "$worktree_root" ]] && command -v git >/dev/null 2>&1; then
      if git -C "$worktree_root" rev-parse --verify "$base_branch" >/dev/null 2>&1; then
        if git -C "$worktree_root" diff --quiet "$base_branch...HEAD"; then
          emit_fail "stage 5 has no diff against $base_branch"
        fi
        add_evidence "git diff $base_branch...HEAD"
      fi
    fi
    ;;
  5.5)
    require_file "$feature_dir/impact-analysis.md" "impact-analysis.md"
    ;;
  6)
    require_file "$feature_dir/code-review.md" "code-review.md"
    ;;
  7)
    require_file "$feature_dir/test-summary.md" "test-summary.md"
    ;;
  8)
    require_file "$feature_dir/merge-summary.md" "merge-summary.md"
    if [[ -n "$main_repo_root" ]] && [[ -n "$base_branch" ]] && command -v git >/dev/null 2>&1; then
      if git -C "$main_repo_root" rev-parse --verify "$base_branch" >/dev/null 2>&1; then
        add_evidence "git branch verified: $base_branch"
      fi
    fi
    ;;
  9)
    if [[ -f "$feature_dir/deploy-healthcheck.md" ]]; then
      require_file "$feature_dir/deploy-healthcheck.md" "deploy-healthcheck.md"
    elif [[ -f "$feature_dir/deploy-skipped.md" ]]; then
      require_file "$feature_dir/deploy-skipped.md" "deploy-skipped.md"
    else
      emit_fail "stage 9 requires deploy-healthcheck.md or deploy-skipped.md"
    fi
    ;;
  *)
    emit_fail "unsupported stage: $stage"
    ;;
esac

check_receipt
emit_ok
