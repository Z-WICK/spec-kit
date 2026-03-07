#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(pwd)"
RESOURCE_ROOT="$SCRIPT_DIR/resources/sh"

copy_file() {
  local src="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
}

copy_tree_preserve() {
  local src_root="$1"
  local dest_root="$2"
  local relative
  while IFS= read -r -d '' path; do
    relative="${path#${src_root}/}"
    case "$relative" in
      specs/*|.specify/memory/*|.specify/extensions/*|.specify/.project|.specify/pipeline-state*)
        if [[ -e "$dest_root/$relative" ]]; then
          continue
        fi
        ;;
    esac
    if [[ -d "$path" ]]; then
      mkdir -p "$dest_root/$relative"
    else
      copy_file "$path" "$dest_root/$relative"
    fi
  done < <(find "$src_root" \( -type d -o -type f \) -print0)
}

copy_tree_preserve "$RESOURCE_ROOT/.claude" "$PROJECT_ROOT/.claude"
copy_tree_preserve "$RESOURCE_ROOT/.specify" "$PROJECT_ROOT/.specify"

if [[ -f "$PROJECT_ROOT/.specify/templates/constitution-template.md" && ! -f "$PROJECT_ROOT/.specify/memory/constitution.md" ]]; then
  mkdir -p "$PROJECT_ROOT/.specify/memory"
  cp "$PROJECT_ROOT/.specify/templates/constitution-template.md" "$PROJECT_ROOT/.specify/memory/constitution.md"
fi

find "$PROJECT_ROOT/.specify/scripts" -type f -name '*.sh' | while read -r script; do
  if head -c 2 "$script" 2>/dev/null | grep -q '^#!'; then
    chmod +x "$script" || true
  fi
done

printf 'Spec Kit assets installed into %s\n' "$PROJECT_ROOT"
