#!/usr/bin/env pwsh

# Find unfilled placeholders in .claude/ directory
#
# Usage: ./find-placeholders.ps1
#
# Returns: List of files with unfilled placeholders

$ErrorActionPreference = 'Stop'

Get-ChildItem -Path ".claude" -Recurse -Include "*.md" -ErrorAction SilentlyContinue | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    # Match [PLACEHOLDER_PATTERN] but exclude HTML comments and examples
    if ($content -match '\[([A-Z_]+)\]' -and $content -notmatch '<!--.*\[([A-Z_]+)\].*-->' -and $content -notmatch 'example') {
        Select-String -Path $_.FullName -Pattern '\[([A-Z_]+)\]' | Where-Object {
            $_.Line -notmatch '<!--' -and $_.Line -notmatch 'example'
        }
    }
}
