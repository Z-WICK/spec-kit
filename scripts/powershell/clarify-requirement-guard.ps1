#!/usr/bin/env pwsh
<#
.SYNOPSIS
Guard script for /speckit.clarify.

.DESCRIPTION
Ensures clarify updates remain anchored and avoid drifting from original
requirements by default.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Before,
    [Parameter(Mandatory = $true)]
    [string]$After,
    [switch]$AllowNonClarificationChange,
    [int]$MinClarifications = 1,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Emit-Fail {
    param([string]$Message)
    if ($Json) {
        @{
            ok    = $false
            error = $Message
        } | ConvertTo-Json -Compress
    } else {
        Write-Error $Message
    }
    exit 1
}

function Emit-Ok {
    param(
        [bool]$NonClarificationChanged,
        [int]$ClarificationCount,
        [int]$SourceTaggedCount
    )
    if ($Json) {
        @{
            ok                       = $true
            non_clarification_changed = $NonClarificationChanged
            clarification_count      = $ClarificationCount
            source_tagged_count      = $SourceTaggedCount
        } | ConvertTo-Json -Compress
    } else {
        Write-Output 'OK: clarify guard passed'
        Write-Output "  non_clarification_changed=$NonClarificationChanged"
        Write-Output "  clarification_count=$ClarificationCount"
        Write-Output "  source_tagged_count=$SourceTaggedCount"
    }
    exit 0
}

function Require-File {
    param(
        [string]$Path,
        [string]$Label
    )
    if ([string]::IsNullOrWhiteSpace($Path)) {
        Emit-Fail "$Label path is empty"
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Emit-Fail "$Label not found: $Path"
    }
    $raw = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        Emit-Fail "$Label is empty: $Path"
    }
}

function Get-NonClarificationText {
    param([string]$Path)

    $inClar = $false
    $out = New-Object System.Collections.Generic.List[string]

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^##\s+Clarifications(\s|$)') {
            $inClar = $true
            continue
        }
        if ($inClar -and $line -match '^##\s+') {
            $inClar = $false
        }
        if (-not $inClar) {
            $out.Add(($line -replace '\s+$', ''))
        }
    }

    return ($out -join "`n")
}

function Get-ClarificationSectionText {
    param([string]$Path)

    $inClar = $false
    $out = New-Object System.Collections.Generic.List[string]

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^##\s+Clarifications(\s|$)') {
            $inClar = $true
            continue
        }
        if ($inClar -and $line -match '^##\s+') {
            break
        }
        if ($inClar) {
            $out.Add(($line -replace '\s+$', ''))
        }
    }

    return ($out -join "`n")
}

Require-File -Path $Before -Label 'before spec'
Require-File -Path $After -Label 'after spec'

if ($MinClarifications -lt 0) {
    Emit-Fail '-MinClarifications must be a non-negative integer'
}

if (-not (Select-String -Path $After -Pattern '^##\s+Clarifications(\s|$)' -Quiet)) {
    Emit-Fail "after spec missing '## Clarifications' section"
}

$beforeNonClar = Get-NonClarificationText -Path $Before
$afterNonClar = Get-NonClarificationText -Path $After
$nonClarChanged = ($beforeNonClar -cne $afterNonClar)

if ($nonClarChanged -and -not $AllowNonClarificationChange) {
    Emit-Fail 'detected non-clarification content change; clarify should be append-only by default'
}

$clarText = Get-ClarificationSectionText -Path $After
if ([string]::IsNullOrWhiteSpace($clarText)) {
    Emit-Fail 'clarifications section exists but has no content'
}

$clarificationCount = ([regex]::Matches($clarText, '(?m)^[\s]*-[\s]*Q:')).Count
$sourceTaggedCount = ([regex]::Matches($clarText, '(?m)^[\s]*-[\s]*Q:.*Source:\s*\S+')).Count

if ($clarificationCount -lt $MinClarifications) {
    Emit-Fail "clarification entry count ($clarificationCount) is below required minimum ($MinClarifications)"
}

if ($sourceTaggedCount -lt $clarificationCount) {
    Emit-Fail "all clarification entries must include 'Source: <anchor>'"
}

Emit-Ok -NonClarificationChanged:$nonClarChanged -ClarificationCount $clarificationCount -SourceTaggedCount $sourceTaggedCount
