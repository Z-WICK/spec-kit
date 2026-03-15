Set-StrictMode -Version Latest

$script:AgentRegistryPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'agent-registry.txt'

function Get-AgentRegistry {
    param(
        [string]$RegistryPath = $script:AgentRegistryPath
    )

    if (-not (Test-Path $RegistryPath)) {
        throw "Agent registry not found: $RegistryPath"
    }

    $rows = @()
    foreach ($line in Get-Content -LiteralPath $RegistryPath -Encoding utf8) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) {
            continue
        }

        $parts = $line -split '\|', 17
        if ($parts.Count -lt 17) {
            throw "Malformed agent registry line: $line"
        }

        $rows += [PSCustomObject]@{
            Agent                   = $parts[0]
            DisplayName             = $parts[1]
            CommandDir              = $parts[2]
            CommandFormat           = $parts[3]
            ArgsToken               = $parts[4]
            Extension               = $parts[5]
            SkillsDir               = $parts[6]
            ContextFile             = $parts[7]
            ContextName             = $parts[8]
            ContextFormat           = $parts[9]
            PackageStrategy         = $parts[10]
            RootCopySource          = $parts[11]
            RootCopyDest            = $parts[12]
            CopyAgentTemplatesTo    = $parts[13]
            LegacyMirrorDir         = $parts[14]
            ExcludeAgentTemplates   = $parts[15] -eq '1'
            CopyVscodeSettings      = $parts[16] -eq '1'
        }
    }

    return $rows
}

function Get-AgentRegistryMap {
    param(
        [string]$RegistryPath = $script:AgentRegistryPath
    )

    $map = @{}
    foreach ($row in Get-AgentRegistry -RegistryPath $RegistryPath) {
        $map[$row.Agent] = $row
    }
    return $map
}

function Resolve-AgentArgsToken {
    param(
        [Parameter(Mandatory=$true)]
        [string]$ArgsToken
    )

    switch ($ArgsToken) {
        'markdown_args' { return '$ARGUMENTS' }
        'toml_args' { return '{{args}}' }
        default { throw "Unknown args token '$ArgsToken' in $script:AgentRegistryPath" }
    }
}
