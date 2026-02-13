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

function Test-TaskChecked {
    param([string]$BaseDir)

    $checkedPattern = '^[\s]*-[\s]*\[x\]'
    $found = $false

    $singleTasks = Join-Path $BaseDir 'tasks.md'
    if (Test-Path -LiteralPath $singleTasks -PathType Leaf) {
        if (Select-String -Path $singleTasks -Pattern $checkedPattern -Quiet) {
            Add-Evidence $singleTasks
            $found = $true
        }
    }

    $shards = Get-ChildItem -Path $BaseDir -Filter 'tasks-*.md' -File -ErrorAction SilentlyContinue
    foreach ($shard in $shards) {
        if (Select-String -Path $shard.FullName -Pattern $checkedPattern -Quiet) {
            Add-Evidence $shard.FullName
            $found = $true
            break
        }
    }

    return $found
}

function Check-Receipt {
    if ([string]::IsNullOrWhiteSpace($Receipt)) {
        return
    }

    Require-File -Path $Receipt -Label 'stage receipt'
    $raw = Get-Content -LiteralPath $Receipt -Raw

    if ($raw -notmatch '"stage"\s*:\s*"?'+ [regex]::Escape($Stage) +'"?') {
        Emit-Fail "receipt stage mismatch: expected $Stage in $Receipt"
    }

    if ($raw -notmatch '"status"\s*:\s*"(completed|success|passed)"') {
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
        $specPath = Join-Path $FeatureDir 'spec.md'
        Require-File -Path $specPath -Label 'spec.md'
        if (-not (Select-String -Path $specPath -Pattern '(^##\s+Clarifications)|clarification' -Quiet)) {
            Emit-Fail 'spec.md does not contain clarification markers'
        }
    }
    '3' {
        Require-File -Path (Join-Path $FeatureDir 'plan.md') -Label 'plan.md'
        Require-File -Path (Join-Path $FeatureDir 'research.md') -Label 'research.md'
    }
    '3.5' {
        $preImpactPath = Join-Path $FeatureDir 'impact-pre-analysis.md'
        if (Test-Path -LiteralPath $preImpactPath -PathType Leaf) {
            Require-File -Path $preImpactPath -Label 'impact-pre-analysis.md'
        } else {
            $planPath = Join-Path $FeatureDir 'plan.md'
            if ((Test-Path -LiteralPath $planPath -PathType Leaf) -and
                (Select-String -Path $planPath -Pattern 'impact|risk|风险' -Quiet)) {
                Add-Evidence $planPath
            } else {
                Emit-Fail 'stage 3.5 requires impact-pre-analysis.md or impact warnings in plan.md'
            }
        }
    }
    '4' {
        $tasksPath = Join-Path $FeatureDir 'tasks.md'
        $tasksIndexPath = Join-Path $FeatureDir 'tasks-index.md'
        if (Test-Path -LiteralPath $tasksPath -PathType Leaf) {
            Require-File -Path $tasksPath -Label 'tasks.md'
        } elseif (Test-Path -LiteralPath $tasksIndexPath -PathType Leaf) {
            Require-File -Path $tasksIndexPath -Label 'tasks-index.md'
            $shards = Get-ChildItem -Path $FeatureDir -Filter 'tasks-*.md' -File -ErrorAction SilentlyContinue
            if (-not $shards) {
                Emit-Fail 'tasks-index.md found but no tasks-<module>.md shards'
            }
            Add-Evidence "$tasksIndexPath + tasks-*.md"
        } else {
            Emit-Fail 'stage 4 requires tasks.md or (tasks-index.md + tasks-*.md)'
        }
    }
    '5' {
        Require-File -Path (Join-Path $FeatureDir 'implementation-summary.md') -Label 'implementation-summary.md'
        if (-not (Test-TaskChecked -BaseDir $FeatureDir)) {
            Emit-Fail 'stage 5 requires checked task markers ([x]) in tasks files'
        }

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
        Require-File -Path (Join-Path $FeatureDir 'impact-analysis.md') -Label 'impact-analysis.md'
    }
    '6' {
        Require-File -Path (Join-Path $FeatureDir 'code-review.md') -Label 'code-review.md'
    }
    '7' {
        Require-File -Path (Join-Path $FeatureDir 'test-summary.md') -Label 'test-summary.md'
    }
    '8' {
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
