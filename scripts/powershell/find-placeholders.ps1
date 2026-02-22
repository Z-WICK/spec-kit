#!/usr/bin/env pwsh

# Find unfilled placeholders in an agent directory
#
# Usage: ./find-placeholders.ps1 <agent_dir>
#
# Returns: List of files with unfilled placeholders

param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$AgentDir
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $AgentDir -PathType Container)) {
    Write-Error "Agent directory not found: $AgentDir"
    exit 1
}

Get-ChildItem -Path $AgentDir -Recurse -Include "*.md" -ErrorAction SilentlyContinue | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    # Match [PLACEHOLDER_PATTERN] but exclude HTML comments and examples
    if ($content -match '\[([A-Z_]+)\]' -and $content -notmatch '<!--.*\[([A-Z_]+)\].*-->' -and $content -notmatch 'example') {
        Select-String -Path $_.FullName -Pattern '\[([A-Z_]+)\]' | Where-Object {
            $_.Line -notmatch '<!--' -and $_.Line -notmatch 'example'
        }
    }
}
