#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

VERSION="${1:-v0.0.0}"
PLUGIN_RESOURCES_ROOT="$ROOT_DIR/plugins/spec-kit/skills/spec-kit-install/scripts/resources"
GENERATED_ROOT="$ROOT_DIR/.genreleases"

chmod +x "$ROOT_DIR/.github/workflows/scripts/create-release-packages.sh"
AGENTS=claude SCRIPTS="sh ps" "$ROOT_DIR/.github/workflows/scripts/create-release-packages.sh" "$VERSION"

compare_variant() {
  local script_variant="$1"
  local generated_dir="$GENERATED_ROOT/sdd-claude-package-${script_variant}"
  local bundled_dir="$PLUGIN_RESOURCES_ROOT/${script_variant}"

  if [[ ! -d "$generated_dir" ]]; then
    echo "Missing generated Claude package for script variant: $script_variant" >&2
    exit 1
  fi

  if [[ ! -d "$bundled_dir" ]]; then
    echo "Missing bundled plugin resources for script variant: $script_variant" >&2
    exit 1
  fi

  for metadata_file in .version .file-hashes; do
    if [[ ! -s "$generated_dir/.specify/$metadata_file" ]]; then
      echo "Missing generated metadata file for ${script_variant}: .specify/$metadata_file" >&2
      exit 1
    fi
    if [[ ! -s "$bundled_dir/.specify/$metadata_file" ]]; then
      echo "Missing bundled metadata file for ${script_variant}: .specify/$metadata_file" >&2
      exit 1
    fi
    if ! diff -u "$generated_dir/.specify/$metadata_file" "$bundled_dir/.specify/$metadata_file"; then
      echo "Plugin resource drift detected for ${script_variant} metadata: .specify/$metadata_file" >&2
      exit 1
    fi
  done

  if ! diff -ru --exclude '.DS_Store' "$generated_dir/.claude" "$bundled_dir/.claude"; then
    echo "Plugin resource drift detected for ${script_variant} .claude assets" >&2
    exit 1
  fi

  if ! diff -ru --exclude '.DS_Store' --exclude '.version' --exclude '.file-hashes' "$generated_dir/.specify" "$bundled_dir/.specify"; then
    echo "Plugin resource drift detected for ${script_variant} .specify assets" >&2
    exit 1
  fi
}

compare_variant sh
compare_variant ps

echo "Plugin install resources match generated Claude release artifacts."
