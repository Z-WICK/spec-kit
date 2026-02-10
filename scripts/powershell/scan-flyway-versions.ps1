#!/usr/bin/env pwsh

# Scan Flyway migration version numbers across repositories and worktrees
#
# Usage: ./scan-flyway-versions.ps1 -MainRepo <path> -WorktreeRoot <path>
#
# Returns: List of occupied version numbers

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$MainRepo,

    [Parameter(Mandatory=$true)]
    [string]$WorktreeRoot
)

$ErrorActionPreference = 'Stop'

$versions = @()

# Scan main repo migrations
$mainMigrations = Join-Path $MainRepo "src/main/resources/db/migration"
if (Test-Path $mainMigrations) {
    Get-ChildItem -Path $mainMigrations -Filter "V*.sql" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -match 'V(\d+)') {
            $versions += [int]$matches[1]
        }
    }
}

# Scan worktree migrations
$worktreeMigrations = Join-Path $WorktreeRoot "src/main/resources/db/migration"
if (Test-Path $worktreeMigrations) {
    Get-ChildItem -Path $worktreeMigrations -Filter "V*.sql" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Name -match 'V(\d+)') {
            $versions += [int]$matches[1]
        }
    }
}

# Scan other worktrees
$worktreeList = git worktree list --porcelain | Select-String '^worktree ' | ForEach-Object {
    $_.Line -replace '^worktree ', ''
}

foreach ($wt in $worktreeList) {
    $wtMigrations = Join-Path $wt "src/main/resources/db/migration"
    if (Test-Path $wtMigrations) {
        Get-ChildItem -Path $wtMigrations -Filter "V*.sql" -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.Name -match 'V(\d+)') {
                $versions += [int]$matches[1]
            }
        }
    }
}

# Output unique sorted versions
$versions | Sort-Object -Unique | ForEach-Object { Write-Output $_ }
