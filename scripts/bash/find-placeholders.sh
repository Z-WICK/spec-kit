#!/usr/bin/env bash

# Find unfilled placeholders in an agent directory
#
# Usage: ./find-placeholders.sh <agent_dir>
#
# Returns: List of files with unfilled placeholders

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <agent_dir>" >&2
    exit 2
fi

AGENT_DIR="$1"

if [[ ! -d "$AGENT_DIR" ]]; then
    echo "Error: Agent directory not found: $AGENT_DIR" >&2
    exit 1
fi

grep -r '\[.*_.*\]' "$AGENT_DIR" --include='*.md' | grep -v '<!--' | grep -v 'example' || true
