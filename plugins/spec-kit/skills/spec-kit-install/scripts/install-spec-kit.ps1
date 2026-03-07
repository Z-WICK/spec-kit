$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Get-Location).Path
$ResourceRoot = Join-Path $ScriptDir 'resources/ps'

function Copy-FileSafe {
    param(
        [string]$Source,
        [string]$Destination
    )

    $Parent = Split-Path -Parent $Destination
    if (-not (Test-Path $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }
    Copy-Item -Path $Source -Destination $Destination -Force
}

function Should-Preserve {
    param([string]$RelativePath)

    return $RelativePath -like 'specs/*' -or
        $RelativePath -like '.specify/memory/*' -or
        $RelativePath -like '.specify/extensions/*' -or
        $RelativePath -eq '.specify/.project' -or
        $RelativePath -like '.specify/pipeline-state*'
}

function Copy-TreePreserve {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot
    )

    Get-ChildItem -Path $SourceRoot -Recurse -Force | ForEach-Object {
        $Relative = $_.FullName.Substring($SourceRoot.Length).TrimStart('\\', '/') -replace '\\', '/'
        if ([string]::IsNullOrEmpty($Relative)) {
            return
        }

        $Destination = Join-Path $DestinationRoot ($Relative -replace '/', [IO.Path]::DirectorySeparatorChar)

        if ($_.PSIsContainer) {
            if (-not (Test-Path $Destination)) {
                New-Item -ItemType Directory -Path $Destination -Force | Out-Null
            }
            return
        }

        if ((Should-Preserve $Relative) -and (Test-Path $Destination)) {
            return
        }

        Copy-FileSafe -Source $_.FullName -Destination $Destination
    }
}

Copy-TreePreserve -SourceRoot (Join-Path $ResourceRoot '.claude') -DestinationRoot (Join-Path $ProjectRoot '.claude')
Copy-TreePreserve -SourceRoot (Join-Path $ResourceRoot '.specify') -DestinationRoot (Join-Path $ProjectRoot '.specify')

$TemplateConstitution = Join-Path $ProjectRoot '.specify/templates/constitution-template.md'
$MemoryConstitution = Join-Path $ProjectRoot '.specify/memory/constitution.md'
if ((Test-Path $TemplateConstitution) -and -not (Test-Path $MemoryConstitution)) {
    $MemoryDir = Split-Path -Parent $MemoryConstitution
    if (-not (Test-Path $MemoryDir)) {
        New-Item -ItemType Directory -Path $MemoryDir -Force | Out-Null
    }
    Copy-Item -Path $TemplateConstitution -Destination $MemoryConstitution -Force
}

Write-Host "Spec Kit assets installed into $ProjectRoot"
