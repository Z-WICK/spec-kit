#!/usr/bin/env bash

# Scan Alembic revision IDs across repositories and worktrees
#
# Usage: ./scan-alembic-revisions.sh <main-repo> <worktree-root>
#
# Returns: List of occupied revision IDs

set -euo pipefail

MAIN_REPO="${1:-}"
WORKTREE_ROOT="${2:-}"

if [[ -z "$MAIN_REPO" ]] || [[ -z "$WORKTREE_ROOT" ]]; then
    echo "Usage: $0 <main-repo> <worktree-root>" >&2
    exit 1
fi

# Scan main repo alembic versions
if [[ -d "$MAIN_REPO/alembic/versions" ]]; then
    find "$MAIN_REPO/alembic/versions" -name "*.py" -exec grep -h "^revision = " {} \; 2>/dev/null || true
fi

# Scan worktree alembic versions
if [[ -d "$WORKTREE_ROOT/alembic/versions" ]]; then
    find "$WORKTREE_ROOT/alembic/versions" -name "*.py" -exec grep -h "^revision = " {} \; 2>/dev/null || true
fi
