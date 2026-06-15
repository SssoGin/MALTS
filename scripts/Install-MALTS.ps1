[CmdletBinding()]
param(
    [ValidateSet('Codex', 'ClaudeCode', 'OpenCode', 'AllIncluded')]
    [string] $Tool = 'Codex',

    [switch] $SkipInstructionTemplate,

    [switch] $Apply,

    [switch] $Overwrite,

    [string] $TargetRoot,

    [string] $SharedRoot
)

$ErrorActionPreference = 'Stop'

function Initialize-Utf8Console {
    try {
        $utf8 = [System.Text.UTF8Encoding]::new($false)
        [Console]::OutputEncoding = $utf8
        [Console]::InputEncoding = $utf8
        $script:OutputEncoding = $utf8
    } catch {
        Write-Warning "Could not force UTF-8 console encoding: $($_.Exception.Message)"
    }
}

Initialize-Utf8Console

$repoRoot = Split-Path -Parent $PSScriptRoot
$dryRun = -not $Apply

function Join-RepoPath {
    param([string] $RelativePath)
    return Join-Path $repoRoot $RelativePath
}

function Get-DefaultTarget {
    param([string] $SelectedTool)

    switch ($SelectedTool) {
        'Codex' { return Join-Path $env:USERPROFILE '.codex' }
        'ClaudeCode' { return Join-Path $env:USERPROFILE '.claude' }
        'OpenCode' { return Join-Path (Join-Path $env:USERPROFILE '.config') 'opencode' }
        default { throw "Unsupported tool: $SelectedTool" }
    }
}

function Resolve-SharedRoot {
    if ($SharedRoot) {
        return [System.IO.Path]::GetFullPath($SharedRoot)
    }
    if ($TargetRoot) {
        return [System.IO.Path]::GetFullPath((Join-Path $TargetRoot 'MALTS_ROOT'))
    }
    if (-not $env:USERPROFILE) {
        throw 'USERPROFILE is not set; provide -SharedRoot explicitly.'
    }
    return [System.IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.malts'))
}

function New-InstallItem {
    param(
        [string] $Source,
        [string] $Target
    )
    return [pscustomobject]@{
        Source = $Source
        Target = $Target
    }
}

function Get-ToolInstallItems {
    param(
        [string] $SelectedTool,
        [string] $SelectedTarget
    )

    $items = @()

    switch ($SelectedTool) {
        'Codex' {
            if (-not $SkipInstructionTemplate) {
                $items += New-InstallItem -Source (Join-RepoPath 'adapters\codex\AGENTS.example.md') -Target (Join-Path $SelectedTarget 'AGENTS.md')
            }
            $sourceRoot = Join-RepoPath 'adapters\codex\.codex'
            if (Test-Path -LiteralPath $sourceRoot) {
                $items += Get-ChildItem -Path $sourceRoot -Recurse -File | ForEach-Object {
                    $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
                    New-InstallItem -Source $_.FullName -Target (Join-Path $SelectedTarget $relative)
                }
            }
        }
        'ClaudeCode' {
            if (-not $SkipInstructionTemplate) {
                $items += New-InstallItem -Source (Join-RepoPath 'adapters\claude-code\CLAUDE.example.md') -Target (Join-Path $SelectedTarget 'CLAUDE.md')
            }
            $sourceRoot = Join-RepoPath 'adapters\claude-code\.claude'
            $items += Get-ChildItem -Path $sourceRoot -Recurse -File | ForEach-Object {
                $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
                New-InstallItem -Source $_.FullName -Target (Join-Path $SelectedTarget $relative)
            }
        }
        'OpenCode' {
            $sourceRoot = Join-RepoPath 'adapters\opencode'
            $items += Get-ChildItem -Path $sourceRoot -Recurse -File | Where-Object {
                $_.Name -notlike 'README*.md' -and -not ($SkipInstructionTemplate -and $_.Name -eq 'AGENTS.example.md')
            } | ForEach-Object {
                $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
                if ($relative -eq 'AGENTS.example.md') {
                    $relative = 'AGENTS.md'
                }
                New-InstallItem -Source $_.FullName -Target (Join-Path $SelectedTarget $relative)
            }
        }
    }

    return $items
}

function Get-SharedRootInstallItems {
    param([string] $ResolvedSharedRoot)

    $items = @()
    $rootFiles = @(
        'README.md',
        'README.zh-CN.md',
        'VERSION',
        'CHANGELOG.md',
        'LICENSE',
        'THIRD_PARTY_NOTICES.md',
        '.editorconfig',
        '.gitattributes'
    )

    foreach ($file in $rootFiles) {
        $source = Join-RepoPath $file
        if (Test-Path -LiteralPath $source) {
            $items += New-InstallItem -Source $source -Target (Join-Path $ResolvedSharedRoot $file)
        }
    }

    foreach ($dir in @('runtime', 'skills', 'docs', 'tools', 'adapters', 'scripts')) {
        $sourceRoot = Join-RepoPath $dir
        if (-not (Test-Path -LiteralPath $sourceRoot)) {
            continue
        }
        $items += Get-ChildItem -Path $sourceRoot -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
            New-InstallItem -Source $_.FullName -Target (Join-Path (Join-Path $ResolvedSharedRoot $dir) $relative)
        }
    }

    return $items
}

function Get-BootText {
    param(
        [string] $SelectedTool,
        [string] $ResolvedSharedRoot
    )

    $generatedAt = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
    return @"
# MALTS_BOOT

Generated: $generatedAt
Tool: $SelectedTool

MALTS_ROOT: $ResolvedSharedRoot
SourcePackageRoot: $repoRoot

Required runtime checks:
- MALTS_ROOT must contain README.md
- MALTS_ROOT must contain skills/
- MALTS_ROOT must contain runtime/EN/templates/
- MALTS_ROOT must contain runtime/EN/checklists/

Agents should resolve MALTS_ROOT from this file before running MALTS project initialization or long-task workflows.
"@
}

function Invoke-PlanItems {
    param([object[]] $Items)

    foreach ($item in $Items) {
        $exists = Test-Path -LiteralPath $item.Target
        $status = if ($exists) { 'exists' } else { 'new' }
        Write-Host "[$status] $($item.Target)"
        Write-Host "  from $($item.Source)"

        if (-not $dryRun) {
            if ($exists -and -not $Overwrite) {
                throw "Refusing to overwrite existing file without -Overwrite: $($item.Target)"
            }
            $targetDir = Split-Path -Parent $item.Target
            if (-not (Test-Path -LiteralPath $targetDir)) {
                New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            }
            Copy-Item -Path $item.Source -Destination $item.Target -Force:$Overwrite
        }
    }
}

function Invoke-ToolInstall {
    param(
        [string] $SelectedTool,
        [string] $SelectedTarget,
        [string] $ResolvedSharedRoot
    )

    $plan = @(Get-ToolInstallItems -SelectedTool $SelectedTool -SelectedTarget $SelectedTarget)

    Write-Host ''
    Write-Host "Tool: $SelectedTool"
    Write-Host "Target: $SelectedTarget"
    Write-Host "Instruction template: $(if ($SkipInstructionTemplate) { 'Skipped' } else { 'Included optional enhancement' })"
    Write-Host "Tool-local skills: Not installed; shared MALTS_ROOT is canonical"
    Write-Host "Installed boot pointer: Included as MALTS_BOOT.md"
    Write-Host "Mode: $(if ($dryRun) { 'DryRun' } else { 'Apply' })"

    Invoke-PlanItems -Items $plan

    $bootTarget = Join-Path $SelectedTarget 'MALTS_BOOT.md'
    $exists = Test-Path -LiteralPath $bootTarget
    $status = if ($exists) { 'exists' } else { 'new' }
    Write-Host "[$status] $bootTarget"
    Write-Host "  generated MALTS root pointer -> $ResolvedSharedRoot"

    if (-not $dryRun) {
        if ($exists -and -not $Overwrite) {
            throw "Refusing to overwrite existing file without -Overwrite: $bootTarget"
        }
        $targetDir = Split-Path -Parent $bootTarget
        if (-not (Test-Path -LiteralPath $targetDir)) {
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        }
        Set-Content -LiteralPath $bootTarget -Value (Get-BootText -SelectedTool $SelectedTool -ResolvedSharedRoot $ResolvedSharedRoot) -Encoding UTF8
    }
}

$selectedTools = if ($Tool -eq 'AllIncluded') { @('Codex', 'ClaudeCode', 'OpenCode') } else { @($Tool) }
$resolvedSharedRoot = Resolve-SharedRoot

Write-Host "MALTS install"
Write-Host "Shared MALTS_ROOT: $resolvedSharedRoot"
Write-Host "Shared runtime copy: Included once at shared MALTS_ROOT"
Write-Host "Tool set: $($selectedTools -join ', ')"

$sharedPlan = @(Get-SharedRootInstallItems -ResolvedSharedRoot $resolvedSharedRoot)
Invoke-PlanItems -Items $sharedPlan

foreach ($selected in $selectedTools) {
    $target = if ($TargetRoot -and $selectedTools.Count -eq 1) {
        $TargetRoot
    } elseif ($TargetRoot) {
        Join-Path $TargetRoot $selected
    } else {
        Get-DefaultTarget -SelectedTool $selected
    }
    $target = [System.IO.Path]::GetFullPath($target)
    Invoke-ToolInstall -SelectedTool $selected -SelectedTarget $target -ResolvedSharedRoot $resolvedSharedRoot
}

if ($dryRun) {
    Write-Host ''
    Write-Host 'Dry run only. No files changed. Re-run with -Apply to install.'
    Write-Host 'For double-click review on Windows, run scripts\Install-MALTS.review.cmd so the console stays open.'
}
