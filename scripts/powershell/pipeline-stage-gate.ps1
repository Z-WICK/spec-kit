#!/usr/bin/env pwsh
<#
.SYNOPSIS
Deterministic stage gate for speckit.pipeline.

.DESCRIPTION
Validates required artifacts for each stage and optionally validates a stage
receipt JSON payload. Designed to reduce workflow drift on weaker models.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Stage,
    [string]$FeatureDir,
    [string]$WorktreeRoot,
    [string]$DocsSummaryFile,
    [string]$MainRepoRoot,
    [string]$BaseBranch,
    [string]$Receipt,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$evidence = New-Object System.Collections.Generic.List[string]

function Add-Evidence {
    param([string]$PathLike)
    if (-not [string]::IsNullOrWhiteSpace($PathLike)) {
        $evidence.Add($PathLike)
    }
}

function Emit-Fail {
    param([string]$Message)
    if ($Json) {
        @{
            ok    = $false
            stage = $Stage
            error = $Message
        } | ConvertTo-Json -Compress
    } else {
        Write-Error $Message
    }
    exit 1
}

function Emit-Ok {
    if ($Json) {
        @{
            ok       = $true
            stage    = $Stage
            evidence = @($evidence)
        } | ConvertTo-Json -Compress
    } else {
        Write-Output "OK: stage $Stage gate passed"
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
    $content = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($content)) {
        Emit-Fail "$Label is empty: $Path"
    }
    Add-Evidence $Path
}

function Require-Dir {
    param(
        [string]$Path,
        [string]$Label
    )
    if ([string]::IsNullOrWhiteSpace($Path)) {
        Emit-Fail "$Label path is empty"
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        Emit-Fail "$Label not found: $Path"
    }
    Add-Evidence $Path
}

function Get-TaskShards {
    param([string]$BaseDir)

    Get-ChildItem -Path $BaseDir -Filter 'tasks-*.md' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne 'tasks-index.md' } |
        Sort-Object -Property Name
}

function Get-TaskFiles {
    param([string]$BaseDir)

    $files = @()
    $singleTasks = Join-Path $BaseDir 'tasks.md'
    if (Test-Path -LiteralPath $singleTasks -PathType Leaf) {
        $files += $singleTasks
    }

    $tasksIndexPath = Join-Path $BaseDir 'tasks-index.md'
    if (Test-Path -LiteralPath $tasksIndexPath -PathType Leaf) {
        $files += $tasksIndexPath
    }

    $shards = Get-TaskShards -BaseDir $BaseDir
    if ($shards) {
        $files += $shards.FullName
    }

    return $files
}

function Require-TaskManifest {
    param([string]$BaseDir)

    $tasksPath = Join-Path $BaseDir 'tasks.md'
    $tasksIndexPath = Join-Path $BaseDir 'tasks-index.md'

    if (Test-Path -LiteralPath $tasksPath -PathType Leaf) {
        Require-File -Path $tasksPath -Label 'tasks.md'
        return
    }

    if (Test-Path -LiteralPath $tasksIndexPath -PathType Leaf) {
        Require-File -Path $tasksIndexPath -Label 'tasks-index.md'
        $shards = Get-TaskShards -BaseDir $BaseDir
        if (-not $shards) {
            Emit-Fail 'tasks-index.md found but no tasks-<module>.md shards'
        }
        Add-Evidence "$tasksIndexPath + tasks-<module>.md"
        return
    }

    Emit-Fail "stage $Stage requires tasks.md or (tasks-index.md + tasks-<module>.md)"
}

function Assert-TasksCompleted {
    param([string]$BaseDir)

    $taskPattern = '^[\s]*-[\s]*\[[ xX]\]'
    $uncheckedPattern = '^[\s]*-[\s]*\[\s\]'
    $filesWithTasks = @()
    $filesWithUnchecked = @()

    $taskFiles = Get-TaskFiles -BaseDir $BaseDir
    foreach ($taskFile in $taskFiles) {
        Add-Evidence $taskFile
        if (Select-String -Path $taskFile -Pattern $taskPattern -Quiet) {
            $filesWithTasks += $taskFile
        }
        if (Select-String -Path $taskFile -Pattern $uncheckedPattern -Quiet) {
            $filesWithUnchecked += $taskFile
        }
    }

    if (-not $filesWithTasks) {
        Emit-Fail 'stage 5 requires tasks with checklist items'
    }

    if ($filesWithUnchecked) {
        $uncheckedList = $filesWithUnchecked -join ', '
        Emit-Fail "stage 5 requires all tasks checked; unchecked tasks remain in: $uncheckedList"
    }
}

function Check-Receipt {
    if ([string]::IsNullOrWhiteSpace($Receipt)) {
        return
    }

    Require-File -Path $Receipt -Label 'stage receipt'
    $raw = Get-Content -LiteralPath $Receipt -Raw
    try {
        $payload = $raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Emit-Fail "receipt JSON parse failed: $Receipt"
    }

    if (-not $payload.PSObject.Properties.Match('stage')) {
        Emit-Fail "receipt missing stage: $Receipt"
    }
    if (-not $payload.PSObject.Properties.Match('status')) {
        Emit-Fail "receipt missing status: $Receipt"
    }

    $receiptStage = [string]$payload.stage
    $receiptStatus = [string]$payload.status

    if ([string]::IsNullOrWhiteSpace($receiptStage)) {
        Emit-Fail "receipt missing stage: $Receipt"
    }
    if ([string]::IsNullOrWhiteSpace($receiptStatus)) {
        Emit-Fail "receipt missing status: $Receipt"
    }
    if ($receiptStage -ne $Stage) {
        Emit-Fail "receipt stage mismatch: expected $Stage in $Receipt"
    }
    if ($receiptStatus -notin @('completed', 'success', 'passed')) {
        Emit-Fail "receipt status must be completed/success/passed: $Receipt"
    }
}

switch ($Stage) {
    '0' {
        if ([string]::IsNullOrWhiteSpace($DocsSummaryFile)) {
            Emit-Fail 'stage 0 requires --docs-summary-file'
        }
        Require-File -Path $DocsSummaryFile -Label 'docs summary'
    }
    '1' {
        Require-Dir -Path $WorktreeRoot -Label 'worktree root'
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-File -Path (Join-Path $FeatureDir 'spec.md') -Label 'spec.md'
    }
    '2' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        $specPath = Join-Path $FeatureDir 'spec.md'
        Require-File -Path $specPath -Label 'spec.md'
        if (-not (Select-String -Path $specPath -Pattern '(^##\s+Clarifications)|clarification' -Quiet)) {
            Emit-Fail 'spec.md does not contain clarification markers'
        }
        if (-not (Select-String -Path $specPath -Pattern '^[\s]*-[\s]*Q:.*Source:\s*\S+' -Quiet)) {
            Emit-Fail 'stage 2 requires clarification entries with Source anchors'
        }
    }
    '3' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-File -Path (Join-Path $FeatureDir 'plan.md') -Label 'plan.md'
        Require-File -Path (Join-Path $FeatureDir 'research.md') -Label 'research.md'
    }
    '3.5' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-File -Path (Join-Path $FeatureDir 'impact-pre-analysis.md') -Label 'impact-pre-analysis.md'
    }
    '4' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-TaskManifest -BaseDir $FeatureDir
    }
    '5' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-File -Path (Join-Path $FeatureDir 'implementation-summary.md') -Label 'implementation-summary.md'
        Require-TaskManifest -BaseDir $FeatureDir
        Assert-TasksCompleted -BaseDir $FeatureDir

        if (-not [string]::IsNullOrWhiteSpace($BaseBranch) -and
            -not [string]::IsNullOrWhiteSpace($WorktreeRoot) -and
            (Get-Command git -ErrorAction SilentlyContinue)) {
            $null = & git -C $WorktreeRoot rev-parse --verify $BaseBranch 2>$null
            if ($LASTEXITCODE -eq 0) {
                & git -C $WorktreeRoot diff --quiet "$BaseBranch...HEAD"
                if ($LASTEXITCODE -eq 0) {
                    Emit-Fail "stage 5 has no diff against $BaseBranch"
                }
                Add-Evidence "git diff $BaseBranch...HEAD"
            }
        }
    }
    '5.5' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-File -Path (Join-Path $FeatureDir 'impact-analysis.md') -Label 'impact-analysis.md'
    }
    '6' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-File -Path (Join-Path $FeatureDir 'code-review.md') -Label 'code-review.md'
    }
    '7' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-File -Path (Join-Path $FeatureDir 'test-summary.md') -Label 'test-summary.md'
    }
    '8' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        Require-File -Path (Join-Path $FeatureDir 'merge-summary.md') -Label 'merge-summary.md'
        if (-not [string]::IsNullOrWhiteSpace($MainRepoRoot) -and
            -not [string]::IsNullOrWhiteSpace($BaseBranch) -and
            (Get-Command git -ErrorAction SilentlyContinue)) {
            $null = & git -C $MainRepoRoot rev-parse --verify $BaseBranch 2>$null
            if ($LASTEXITCODE -eq 0) {
                Add-Evidence "git branch verified: $BaseBranch"
            }
        }
    }
    '9' {
        Require-Dir -Path $FeatureDir -Label 'feature directory'
        $healthPath = Join-Path $FeatureDir 'deploy-healthcheck.md'
        $skipPath = Join-Path $FeatureDir 'deploy-skipped.md'
        if (Test-Path -LiteralPath $healthPath -PathType Leaf) {
            Require-File -Path $healthPath -Label 'deploy-healthcheck.md'
        } elseif (Test-Path -LiteralPath $skipPath -PathType Leaf) {
            Require-File -Path $skipPath -Label 'deploy-skipped.md'
        } else {
            Emit-Fail 'stage 9 requires deploy-healthcheck.md or deploy-skipped.md'
        }
    }
    default {
        Emit-Fail "unsupported stage: $Stage"
    }
}

Check-Receipt
Emit-Ok
