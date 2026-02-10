#!/usr/bin/env pwsh

# Scan Alembic revision IDs across repositories and worktrees
#
# Usage: ./scan-alembic-revisions.ps1 -MainRepo <path> -WorktreeRoot <path>
#
# Returns: List of occupied revision IDs

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$MainRepo,

    [Parameter(Mandatory=$true)]
    [string]$WorktreeRoot
)

$ErrorActionPreference = 'Stop'

$revisions = @()

# Scan main repo alembic versions
$mainAlembic = Join-Path $MainRepo "alembic/versions"
if (Test-Path $mainAlembic) {
    Get-ChildItem -Path $mainAlembic -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
        $content = Get-Content $_.FullName -Raw
        if ($content -match '^revision = [''"]([^''"]+)[''"]') {
            $revisions += $matches[1]
        }
    }
}

# Scan worktree alembic versions
$worktreeAlembic = Join-Path $WorktreeRoot "alembic/versions"
if (Test-Path $worktreeAlembic) {
    Get-ChildItem -Path $worktreeAlembic -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
        $content = Get-Content $_.FullName -Raw
        if ($content -match '^revision = [''"]([^''"]+)[''"]') {
            $revisions += $matches[1]
        }
    }
}

# Output unique revisions
$revisions | Sort-Object -Unique | ForEach-Object { Write-Output $_ }
