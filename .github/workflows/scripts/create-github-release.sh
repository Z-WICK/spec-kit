#!/usr/bin/env bash
set -euo pipefail

# create-github-release.sh
# Create a GitHub release with all template zip files
# Usage: create-github-release.sh <version>

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version>" >&2
  exit 1
fi

VERSION="$1"

# Remove 'v' prefix from version for release title
VERSION_NO_V=${VERSION#v}

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(CDPATH="" cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/bash/agent-registry.sh"
load_agent_registry

assets=()
for agent in "${AGENT_REGISTRY_ORDER[@]}"; do
  for variant in sh ps; do
    assets+=(".genreleases/spec-kit-template-${agent}-${variant}-${VERSION}.zip")
  done
done

gh release create "$VERSION" \
  "${assets[@]}" \
  --title "Spec Kit Templates - $VERSION_NO_V" \
  --notes-file release_notes.md
