#!/usr/bin/env pwsh
#requires -Version 7.0

<#
.SYNOPSIS
    Build Spec Kit template release archives for each supported AI assistant and script type.

.DESCRIPTION
    create-release-packages.ps1 (workflow-local)
    Build Spec Kit template release archives for each supported AI assistant and script type.

.PARAMETER Version
    Version string with leading 'v' (e.g., v0.2.0)

.PARAMETER Agents
    Comma or space separated subset of agents to build (default: all)
    Valid agents: claude, gemini, copilot, cursor-agent, qwen, opencode, windsurf, codex, kilocode, auggie, roo, codebuddy, qodercli, amp, shai, tabnine, kiro-cli, agy, bob, droid, vibe, kimi, trae, pi, iflow, generic

.PARAMETER Scripts
    Comma or space separated subset of script types to build (default: both)
    Valid scripts: sh, ps

.EXAMPLE
    .\create-release-packages.ps1 -Version v0.2.0

.EXAMPLE
    .\create-release-packages.ps1 -Version v0.2.0 -Agents claude,copilot -Scripts sh

.EXAMPLE
    .\create-release-packages.ps1 -Version v0.2.0 -Agents claude -Scripts ps
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Version,

    [Parameter(Mandatory=$false)]
    [string]$Agents = "",

    [Parameter(Mandatory=$false)]
    [string]$Scripts = ""
)

$ErrorActionPreference = "Stop"

# Validate version format
if ($Version -notmatch '^v\d+\.\d+\.\d+$') {
    Write-Error "Version must look like v0.0.0"
    exit 1
}

Write-Host "Building release packages for $Version"

# Create and use .genreleases directory for all build artifacts
$GenReleasesDir = if ($env:GENRELEASES_DIR) { $env:GENRELEASES_DIR } else { ".genreleases" }
if (Test-Path $GenReleasesDir) {
    Remove-Item -Path $GenReleasesDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $GenReleasesDir -Force | Out-Null

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
. (Join-Path $RepoRoot 'scripts/powershell/agent-registry.ps1')
$AgentRegistry = Get-AgentRegistryMap

function Rewrite-Paths {
    param([string]$Content)

    $Content = $Content -replace '(/?)\bmemory/', '.specify/memory/'
    $Content = $Content -replace '(/?)\bscripts/', '.specify/scripts/'
    $Content = $Content -replace '(/?)\btemplates/', '.specify/templates/'
    return $Content
}

function Get-CommandTemplates {
    if (-not (Test-Path "templates/commands")) {
        return @()
    }
    return Get-ChildItem -Path (Join-Path "templates/commands" "*.md") -File -ErrorAction SilentlyContinue |
        Sort-Object FullName
}

function Generate-Commands {
    param(
        [string]$Agent,
        [string]$Extension,
        [string]$ArgFormat,
        [string]$OutputDir,
        [string]$ScriptVariant
    )

    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

    $templates = Get-CommandTemplates

    foreach ($template in $templates) {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($template.Name)

        # Read file content and normalize line endings
        $fileContent = (Get-Content -Path $template.FullName -Raw) -replace "`r`n", "`n"

        # Extract description from YAML frontmatter
        $description = ""
        if ($fileContent -match '(?m)^description:\s*(.+)$') {
            $description = $matches[1]
        }

        $body = $fileContent

        $scriptCommand = ""
        if ($fileContent -match "(?m)^\s*${ScriptVariant}:\s*(.+)$") {
            $scriptCommand = $matches[1]
        }

        if ([string]::IsNullOrEmpty($scriptCommand)) {
            Write-Warning "No script command found for $ScriptVariant in $($template.Name)"
            $scriptCommand = "(Missing script command for $ScriptVariant)"
        }

        $agentScriptCommand = ""
        if ($fileContent -match "(?ms)agent_scripts:.*?^\s*${ScriptVariant}:\s*(.+?)$") {
            $agentScriptCommand = $matches[1].Trim()
        }

        $body = $body -replace '\{SCRIPT\}', $scriptCommand

        if (-not [string]::IsNullOrEmpty($agentScriptCommand)) {
            $body = $body -replace '\{AGENT_SCRIPT\}', $agentScriptCommand
        }

        # Codex and Kimi skills strip source frontmatter script matrices after
        # placeholders are concretized; other agents keep the original frontmatter.
        if ($Agent -in @('codex', 'kimi')) {

            $lines = $body -split "`n"
            $outputLines = @()
            $inFrontmatter = $false
            $skipScripts = $false
            $dashCount = 0

            foreach ($line in $lines) {
                if ($line -match '^---$') {
                    $outputLines += $line
                    $dashCount++
                    if ($dashCount -eq 1) {
                        $inFrontmatter = $true
                    } else {
                        $inFrontmatter = $false
                    }
                    continue
                }

                if ($inFrontmatter) {
                    if ($line -match '^(scripts|agent_scripts):$') {
                        $skipScripts = $true
                        continue
                    }
                    if ($line -match '^[a-zA-Z].*:' -and $skipScripts) {
                        $skipScripts = $false
                    }
                    if ($skipScripts -and $line -match '^\s+') {
                        continue
                    }
                }

                $outputLines += $line
            }

            $body = $outputLines -join "`n"
        }
        # Apply other substitutions
        $body = $body -replace '\{ARGS\}', $ArgFormat
        $body = $body -replace '__AGENT__', $Agent
        $body = Rewrite-Paths -Content $body

        # Generate output file based on extension
        $outputFile = Join-Path $OutputDir "speckit.$name.$Extension"

        switch ($Extension) {
            'toml' {
                $body = $body -replace '\\', '\\'
                $output = "description = `"$description`"`n`nprompt = `"`"`"`n$body`n`"`"`""
                Set-Content -Path $outputFile -Value $output -NoNewline
            }
            'md' {
                if ($Agent -eq 'codex') {
                    $skillName = "speckit-$name"
                    $skillDir = Join-Path $OutputDir $skillName
                    New-Item -ItemType Directory -Path $skillDir -Force | Out-Null

                    $skillBody = $body
                    if ($skillBody -match '(?ms)^\s*---\n.*?\n---\n?(.*)$') {
                        $skillBody = $matches[1]
                    }

                    $escapedDescription = $description -replace '"', '\"'
                    $skillContent = @"
---
name: $skillName
description: "$escapedDescription"
---

$skillBody
"@
                    Set-Content -Path (Join-Path $skillDir "SKILL.md") -Value $skillContent -NoNewline
                } else {
                    Set-Content -Path $outputFile -Value $body -NoNewline
                }
            }
            'agent.md' {
                Set-Content -Path $outputFile -Value $body -NoNewline
            }
        }
    }
}

function Generate-CopilotPrompts {
    param(
        [string]$AgentsDir,
        [string]$PromptsDir
    )

    New-Item -ItemType Directory -Path $PromptsDir -Force | Out-Null

    $agentFiles = Get-ChildItem -Path "$AgentsDir/speckit.*.agent.md" -File -ErrorAction SilentlyContinue

    foreach ($agentFile in $agentFiles) {
        $basename = $agentFile.Name -replace '\.agent\.md$', ''
        $promptFile = Join-Path $PromptsDir "$basename.prompt.md"

        $content = @"
---
agent: $basename
---
"@
        Set-Content -Path $promptFile -Value $content
    }
}

# Create Kimi Code skills in .kimi/skills/<name>/SKILL.md format.
# Kimi CLI discovers skills as directories containing a SKILL.md file,
# invoked with /skill:<name> (e.g. /skill:speckit-specify).
function New-KimiSkills {
    param(
        [string]$SkillsDir,
        [string]$ScriptVariant
    )

    $templates = Get-CommandTemplates

    foreach ($template in $templates) {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($template.Name)
        $skillName = "speckit-$name"
        $skillDir = Join-Path $SkillsDir $skillName
        New-Item -ItemType Directory -Force -Path $skillDir | Out-Null

        $fileContent = (Get-Content -Path $template.FullName -Raw) -replace "`r`n", "`n"

        # Extract description
        $description = "Spec Kit: $name workflow"
        if ($fileContent -match '(?m)^description:\s*(.+)$') {
            $description = $matches[1]
        }

        # Extract script command
        $scriptCommand = "(Missing script command for $ScriptVariant)"
        if ($fileContent -match "(?m)^\s*${ScriptVariant}:\s*(.+)$") {
            $scriptCommand = $matches[1]
        }

        # Extract agent_script command from frontmatter if present
        $agentScriptCommand = ""
        if ($fileContent -match "(?ms)agent_scripts:.*?^\s*${ScriptVariant}:\s*(.+?)$") {
            $agentScriptCommand = $matches[1].Trim()
        }

        # Replace {SCRIPT}, strip scripts sections, rewrite paths
        $body = $fileContent -replace '\{SCRIPT\}', $scriptCommand
        if (-not [string]::IsNullOrEmpty($agentScriptCommand)) {
            $body = $body -replace '\{AGENT_SCRIPT\}', $agentScriptCommand
        }

        $lines = $body -split "`n"
        $outputLines = @()
        $inFrontmatter = $false
        $skipScripts = $false
        $dashCount = 0

        foreach ($line in $lines) {
            if ($line -match '^---$') {
                $outputLines += $line
                $dashCount++
                $inFrontmatter = ($dashCount -eq 1)
                continue
            }
            if ($inFrontmatter) {
                if ($line -match '^(scripts|agent_scripts):$') { $skipScripts = $true; continue }
                if ($line -match '^[a-zA-Z].*:' -and $skipScripts) { $skipScripts = $false }
                if ($skipScripts -and $line -match '^\s+') { continue }
            }
            $outputLines += $line
        }

        $body = $outputLines -join "`n"
        $body = $body -replace '\{ARGS\}', '$ARGUMENTS'
        $body = $body -replace '__AGENT__', 'kimi'
        $body = Rewrite-Paths -Content $body

        # Strip existing frontmatter, keep only body
        $templateBody = ""
        $fmCount = 0
        $inBody = $false
        foreach ($line in ($body -split "`n")) {
            if ($line -match '^---$') {
                $fmCount++
                if ($fmCount -eq 2) { $inBody = $true }
                continue
            }
            if ($inBody) { $templateBody += "$line`n" }
        }

        $skillContent = "---`nname: `"$skillName`"`ndescription: `"$description`"`n---`n`n$templateBody"
        Set-Content -Path (Join-Path $skillDir "SKILL.md") -Value $skillContent -NoNewline
    }
}

function Build-Variant {
    param(
        [string]$Agent,
        [string]$Script
    )

    $baseDir = Join-Path $GenReleasesDir "sdd-${Agent}-package-${Script}"
    Write-Host "Building $Agent ($Script) package..."
    New-Item -ItemType Directory -Path $baseDir -Force | Out-Null

    # Copy base structure but filter scripts by variant
    $specDir = Join-Path $baseDir ".specify"
    New-Item -ItemType Directory -Path $specDir -Force | Out-Null

    # Copy memory directory
    if (Test-Path "memory") {
        Copy-Item -Path "memory" -Destination $specDir -Recurse -Force
        Write-Host "Copied memory -> .specify"
    }

    # Only copy the relevant script variant directory
    if (Test-Path "scripts") {
        $scriptsDestDir = Join-Path $specDir "scripts"
        New-Item -ItemType Directory -Path $scriptsDestDir -Force | Out-Null

        switch ($Script) {
            'sh' {
                if (Test-Path "scripts/bash") {
                    Copy-Item -Path "scripts/bash" -Destination $scriptsDestDir -Recurse -Force
                    Write-Host "Copied scripts/bash -> .specify/scripts"
                }
            }
            'ps' {
                if (Test-Path "scripts/powershell") {
                    Copy-Item -Path "scripts/powershell" -Destination $scriptsDestDir -Recurse -Force
                    Write-Host "Copied scripts/powershell -> .specify/scripts"
                }
            }
        }

        Get-ChildItem -Path "scripts" -File -ErrorAction SilentlyContinue | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $scriptsDestDir -Force
        }
    }

    # Copy templates (excluding commands directory and vscode-settings.json)
    if (Test-Path "templates") {
        $templatesDestDir = Join-Path $specDir "templates"
        New-Item -ItemType Directory -Path $templatesDestDir -Force | Out-Null

        Get-ChildItem -Path "templates" -Recurse -File | Where-Object {
            $isCommandTemplate = $_.FullName -match 'templates[/\\]commands[/\\]'
            $isForkCommandTemplate = $_.FullName -match 'templates[/\\]fork-commands[/\\]'
            $isAgentTemplate = $_.FullName -match 'templates[/\\]agents[/\\]'
            (-not $isCommandTemplate) -and
            (-not $isForkCommandTemplate) -and
            ($_.Name -ne 'vscode-settings.json') -and
            ((-not $AgentRegistry[$Agent].ExcludeAgentTemplates) -or (-not $isAgentTemplate))
        } | ForEach-Object {
            $relativePath = $_.FullName.Substring((Resolve-Path "templates").Path.Length + 1)
            $destFile = Join-Path $templatesDestDir $relativePath
            $destFileDir = Split-Path $destFile -Parent
            New-Item -ItemType Directory -Path $destFileDir -Force | Out-Null
            Copy-Item -Path $_.FullName -Destination $destFile -Force
        }
        Write-Host "Copied templates -> .specify/templates"
    }

    # Generate agent-specific command files
    $agentConfig = $AgentRegistry[$Agent]
    if ($null -eq $agentConfig) {
        throw "Unsupported agent '$Agent'."
    }

    $cmdDir = Join-Path $baseDir $agentConfig.CommandDir
    New-Item -ItemType Directory -Path $cmdDir -Force | Out-Null
    $argFormat = Resolve-AgentArgsToken -ArgsToken $agentConfig.ArgsToken

    switch ($agentConfig.PackageStrategy) {
        'standard_commands' { }
        'copilot_agent' { }
        'codex_skill_tree' { }
        'kimi_skill_tree' {
            New-KimiSkills -SkillsDir $cmdDir -ScriptVariant $Script
        }
        default {
            throw "Unsupported packaging strategy '$($agentConfig.PackageStrategy)' for agent '$Agent'."
        }
    }

    if ($agentConfig.PackageStrategy -ne 'kimi_skill_tree') {
        $commandExtension = switch ($agentConfig.Extension) {
            '.md' { 'md' }
            '.toml' { 'toml' }
            '.agent.md' { 'agent.md' }
            '/SKILL.md' { 'md' }
            default { throw "Unsupported command extension '$($agentConfig.Extension)' for agent '$Agent'." }
        }
        Generate-Commands -Agent $Agent -Extension $commandExtension -ArgFormat $argFormat -OutputDir $cmdDir -ScriptVariant $Script
    }

    if ($agentConfig.PackageStrategy -eq 'copilot_agent') {
        $promptsDir = Join-Path $baseDir ".github/prompts"
        Generate-CopilotPrompts -AgentsDir $cmdDir -PromptsDir $promptsDir
    }

    if ($agentConfig.CopyVscodeSettings) {
        $vscodeDir = Join-Path $baseDir ".vscode"
        New-Item -ItemType Directory -Path $vscodeDir -Force | Out-Null
        if (Test-Path "templates/vscode-settings.json") {
            Copy-Item -Path "templates/vscode-settings.json" -Destination (Join-Path $vscodeDir "settings.json")
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($agentConfig.RootCopySource) -and -not [string]::IsNullOrWhiteSpace($agentConfig.RootCopyDest)) {
        if (Test-Path $agentConfig.RootCopySource) {
            Copy-Item -Path $agentConfig.RootCopySource -Destination (Join-Path $baseDir $agentConfig.RootCopyDest)
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($agentConfig.CopyAgentTemplatesTo) -and (Test-Path "templates/agents")) {
        $agentsDir = Join-Path $baseDir $agentConfig.CopyAgentTemplatesTo
        New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null
        Get-ChildItem "templates/agents/*.md" | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $agentsDir
        }
        Write-Host "Copied agents -> $($agentConfig.CopyAgentTemplatesTo)"
    }

    if (-not [string]::IsNullOrWhiteSpace($agentConfig.LegacyMirrorDir)) {
        $legacyDir = Join-Path $baseDir $agentConfig.LegacyMirrorDir
        New-Item -ItemType Directory -Path $legacyDir -Force | Out-Null
        Copy-Item -Path (Join-Path $cmdDir "*") -Destination $legacyDir -Recurse -Force
    }
    # Generate .version and .file-hashes for update tracking
    Set-Content -Path (Join-Path $specDir ".version") -Value $Version -NoNewline
    $hashFile = Join-Path $specDir ".file-hashes"
    $allFiles = Get-ChildItem -Path $baseDir -Recurse -File | Where-Object { $_.Name -ne '.file-hashes' } | Sort-Object FullName
    $hashLines = @()
    $basePath = (Resolve-Path $baseDir).Path.TrimEnd('\', '/')
    foreach ($f in $allFiles) {
        $relativePath = $f.FullName.Substring($basePath.Length).TrimStart('\', '/') -replace '\\', '/'
        $hash = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash.ToLower()
        $hashLines += "$hash  ./$relativePath"
    }
    Set-Content -Path $hashFile -Value ($hashLines -join "`n")

    # Create zip archive
    $zipFile = Join-Path $GenReleasesDir "spec-kit-template-${Agent}-${Script}-${Version}.zip"
    Compress-Archive -Path "$baseDir/*" -DestinationPath $zipFile -Force
    Write-Host "Created $zipFile"
}

# Define all agents and scripts
$AllAgents = (Get-AgentRegistry | ForEach-Object { $_.Agent })
$AllScripts = @('sh', 'ps')

function Normalize-List {
    param([string]$Input)

    if ([string]::IsNullOrEmpty($Input)) {
        return @()
    }

    $items = $Input -split '[,\s]+' | Where-Object { $_ } | Select-Object -Unique
    return $items
}

function Validate-Subset {
    param(
        [string]$Type,
        [string[]]$Allowed,
        [string[]]$Items
    )

    $ok = $true
    foreach ($item in $Items) {
        if ($item -notin $Allowed) {
            Write-Error "Unknown $Type '$item' (allowed: $($Allowed -join ', '))"
            $ok = $false
        }
    }
    return $ok
}

# Determine agent list
if (-not [string]::IsNullOrEmpty($Agents)) {
    $AgentList = Normalize-List -Input $Agents
    if (-not (Validate-Subset -Type 'agent' -Allowed $AllAgents -Items $AgentList)) {
        exit 1
    }
} else {
    $AgentList = $AllAgents
}

# Determine script list
if (-not [string]::IsNullOrEmpty($Scripts)) {
    $ScriptList = Normalize-List -Input $Scripts
    if (-not (Validate-Subset -Type 'script' -Allowed $AllScripts -Items $ScriptList)) {
        exit 1
    }
} else {
    $ScriptList = $AllScripts
}

Write-Host "Agents: $($AgentList -join ', ')"
Write-Host "Scripts: $($ScriptList -join ', ')"

# Build all variants
foreach ($agent in $AgentList) {
    foreach ($script in $ScriptList) {
        Build-Variant -Agent $agent -Script $script
    }
}

Write-Host "`nArchives in ${GenReleasesDir}:"
Get-ChildItem -Path $GenReleasesDir -Filter "spec-kit-template-*-${Version}.zip" | ForEach-Object {
    Write-Host "  $($_.Name)"
}
