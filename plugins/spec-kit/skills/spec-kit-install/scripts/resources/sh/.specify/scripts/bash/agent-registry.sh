#!/usr/bin/env bash

# Shared agent registry loader for repository maintenance scripts.
# Intentionally bash 3.2 compatible: no associative arrays.

_agent_registry_helper_dir="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_REGISTRY_FILE="${AGENT_REGISTRY_FILE:-${_agent_registry_helper_dir%/bash}/agent-registry.txt}"
unset _agent_registry_helper_dir

declare -a AGENT_REGISTRY_ORDER=()
declare -a AGENT_REGISTRY_ROWS=()

load_agent_registry() {
  local line agent

  AGENT_REGISTRY_ORDER=()
  AGENT_REGISTRY_ROWS=()

  while IFS= read -r line || [[ -n $line ]]; do
    [[ -n $line ]] || continue
    [[ ${line:0:1} == "#" ]] && continue

    IFS='|' read -r agent _ <<< "$line"
    [[ -n $agent ]] || continue

    AGENT_REGISTRY_ORDER+=("$agent")
    AGENT_REGISTRY_ROWS+=("$line")
  done < "$AGENT_REGISTRY_FILE"
}

agent_registry_row() {
  local wanted="$1"
  local row agent

  for row in "${AGENT_REGISTRY_ROWS[@]}"; do
    IFS='|' read -r agent _ <<< "$row"
    if [[ "$agent" == "$wanted" ]]; then
      printf '%s\n' "$row"
      return 0
    fi
  done

  return 1
}

agent_registry_field() {
  local agent="$1"
  local field="$2"
  local row
  local f0 f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 f12 f13 f14 f15 f16

  row=$(agent_registry_row "$agent") || return 1
  IFS='|' read -r f0 f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 f12 f13 f14 f15 f16 <<< "$row"

  case "$field" in
    display_name) printf '%s' "$f1" ;;
    command_dir) printf '%s' "$f2" ;;
    command_format) printf '%s' "$f3" ;;
    args_token) printf '%s' "$f4" ;;
    extension) printf '%s' "$f5" ;;
    skills_dir) printf '%s' "$f6" ;;
    context_file) printf '%s' "$f7" ;;
    context_name) printf '%s' "$f8" ;;
    context_format) printf '%s' "$f9" ;;
    package_strategy) printf '%s' "$f10" ;;
    root_copy_source) printf '%s' "$f11" ;;
    root_copy_dest) printf '%s' "$f12" ;;
    copy_agent_templates_to) printf '%s' "$f13" ;;
    legacy_mirror_dir) printf '%s' "$f14" ;;
    exclude_agent_templates) printf '%s' "$f15" ;;
    copy_vscode_settings) printf '%s' "$f16" ;;
    *)
      echo "Unknown agent registry field '$field'" >&2
      return 1
      ;;
  esac
}

agent_registry_args_value() {
  case "$1" in
    markdown_args) printf '%s' "\$ARGUMENTS" ;;
    toml_args) printf '%s' "{{args}}" ;;
    *)
      echo "Unknown args token '$1' in $AGENT_REGISTRY_FILE" >&2
      return 1
      ;;
  esac
}

agent_registry_has_agent() {
  agent_registry_row "$1" >/dev/null 2>&1
}
