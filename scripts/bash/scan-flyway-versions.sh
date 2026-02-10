#!/usr/bin/env bash

# Scan Flyway migration version numbers across repositories and worktrees
#
# Usage: ./scan-flyway-versions.sh <main-repo> <worktree-root>
#
# Returns: List of occupied version numbers

set -euo pipefail

MAIN_REPO="${1:-}"
WORKTREE_ROOT="${2:-}"

if [[ -z "$MAIN_REPO" ]] || [[ -z "$WORKTREE_ROOT" ]]; then
    echo "Usage: $0 <main-repo> <worktree-root>" >&2
    exit 1
fi

# Scan main repo migrations
if [[ -d "$MAIN_REPO/src/main/resources/db/migration" ]]; then
    ls "$MAIN_REPO"/src/main/resources/db/migration/V*.sql 2>/dev/null | grep -oE 'V[0-9]+' | grep -oE '[0-9]+' || true
fi

# Scan worktree migrations
if [[ -d "$WORKTREE_ROOT/src/main/resources/db/migration" ]]; then
    ls "$WORKTREE_ROOT"/src/main/resources/db/migration/V*.sql 2>/dev/null | grep -oE 'V[0-9]+' | grep -oE '[0-9]+' || true
fi

# Scan other worktrees
git worktree list --porcelain | grep '^worktree ' | awk '{print $2}' | while read -r wt; do
    if [[ -d "$wt/src/main/resources/db/migration" ]]; then
        ls "$wt"/src/main/resources/db/migration/V*.sql 2>/dev/null | grep -oE 'V[0-9]+' | grep -oE '[0-9]+' || true
    fi
done | sort -u -n
