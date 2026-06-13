[CmdletBinding()]
param(
    [ValidateSet('Codex', 'ClaudeCode', 'OpenCode', 'AllIncluded')]
    [string] $Tool = 'Codex',

    [switch] $SkipInstructionTemplate,

    [switch] $SkipRuntime,

    [switch] $SkipBoot,

    [switch] $Apply,

    [switch] $Overwrite,

    [string] $TargetRoot
)

$ErrorActionPreference = 'Stop'

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

function Get-InstallPlan {
    param(
        [string] $SelectedTool,
        [string] $SelectedTarget
    )

    $items = @()

    switch ($SelectedTool) {
        'Codex' {
            if (-not $SkipInstructionTemplate) {
                $items += [pscustomobject]@{
                    Source = Join-RepoPath 'adapters\codex\AGENTS.example.md'
                    Target = Join-Path $SelectedTarget 'AGENTS.md'
                }
            }
            $sourceRoot = Join-RepoPath 'adapters\codex\.codex'
            if (Test-Path -LiteralPath $sourceRoot) {
                $items += Get-ChildItem -Path $sourceRoot -Recurse -File | ForEach-Object {
                    $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
                    [pscustomobject]@{
                        Source = $_.FullName
                        Target = Join-Path (Join-Path $SelectedTarget '.codex') $relative
                    }
                }
            }
        }
        'ClaudeCode' {
            if (-not $SkipInstructionTemplate) {
                $items += [pscustomobject]@{
                    Source = Join-RepoPath 'adapters\claude-code\CLAUDE.example.md'
                    Target = Join-Path $SelectedTarget 'CLAUDE.md'
                }
            }
            $sourceRoot = Join-RepoPath 'adapters\claude-code\.claude'
            $items += Get-ChildItem -Path $sourceRoot -Recurse -File | ForEach-Object {
                $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
                [pscustomobject]@{
                    Source = $_.FullName
                    Target = Join-Path $SelectedTarget $relative
                }
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
                [pscustomobject]@{
                    Source = $_.FullName
                    Target = Join-Path $SelectedTarget $relative
                }
            }
        }
    }

    $items += Get-SharedSkillInstallItems -SelectedTarget $SelectedTarget
    if (-not $SkipRuntime) {
        $items += Get-MaltsRootInstallItems -SelectedTarget $SelectedTarget
    }

    return $items
}

function Get-SharedSkillInstallItems {
    param([string] $SelectedTarget)

    $sourceRoot = Join-RepoPath 'skills'
    if (-not (Test-Path -LiteralPath $sourceRoot)) {
        return @()
    }

    return Get-ChildItem -Path $sourceRoot -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
        [pscustomobject]@{
            Source = $_.FullName
            Target = Join-Path (Join-Path $SelectedTarget 'skills') $relative
        }
    }
}

function Get-MaltsRootInstallItems {
    param([string] $SelectedTarget)

    $installRoot = Join-Path $SelectedTarget 'malts'
    $items = @()
    $rootFiles = @(
        'README.md',
        'README.zh-CN.md',
        'VERSION',
        'LICENSE',
        'THIRD_PARTY_NOTICES.md'
    )

    foreach ($file in $rootFiles) {
        $source = Join-RepoPath $file
        if (Test-Path -LiteralPath $source) {
            $items += [pscustomobject]@{
                Source = $source
                Target = Join-Path $installRoot $file
            }
        }
    }

    foreach ($dir in @('runtime', 'skills', 'docs', 'tools', 'adapters')) {
        $sourceRoot = Join-RepoPath $dir
        if (-not (Test-Path -LiteralPath $sourceRoot)) {
            continue
        }
        $items += Get-ChildItem -Path $sourceRoot -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
            [pscustomobject]@{
                Source = $_.FullName
                Target = Join-Path (Join-Path $installRoot $dir) $relative
            }
        }
    }

    return $items
}

function Get-BootText {
    param(
        [string] $SelectedTool,
        [string] $SelectedTarget
    )

    $installRoot = Join-Path $SelectedTarget 'malts'
    $generatedAt = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
    return @"
# MALTS_BOOT

Generated: $generatedAt
Tool: $SelectedTool

MALTS_ROOT: $installRoot
SourcePackageRoot: $repoRoot

Required runtime checks:
- MALTS_ROOT must contain README.md
- MALTS_ROOT must contain skills/
- MALTS_ROOT must contain runtime/EN/templates/
- MALTS_ROOT must contain runtime/EN/checklists/

Agents should resolve MALTS_ROOT from this file before running MALTS project initialization or long-task workflows.
"@
}

function Invoke-InstallPlan {
    param(
        [string] $SelectedTool,
        [string] $SelectedTarget
    )

    $plan = @(Get-InstallPlan -SelectedTool $SelectedTool -SelectedTarget $SelectedTarget)

    Write-Host "Tool: $SelectedTool"
    Write-Host "Target: $SelectedTarget"
    Write-Host "Instruction template: $(if ($SkipInstructionTemplate) { 'Skipped' } else { 'Included optional enhancement' })"
    Write-Host "Shared skills: Included from repository skills/"
    Write-Host "Installed MALTS runtime copy: $(if ($SkipRuntime) { 'Skipped' } else { 'Included under target\\malts' })"
    Write-Host "Installed boot pointer: $(if ($SkipBoot) { 'Skipped' } else { 'Included as MALTS_BOOT.md' })"
    Write-Host "Mode: $(if ($dryRun) { 'DryRun' } else { 'Apply' })"

    foreach ($item in $plan) {
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

    if (-not $SkipBoot) {
        $bootTarget = Join-Path $SelectedTarget 'MALTS_BOOT.md'
        $exists = Test-Path -LiteralPath $bootTarget
        $status = if ($exists) { 'exists' } else { 'new' }
        Write-Host "[$status] $bootTarget"
        Write-Host "  generated MALTS root pointer"

        if (-not $dryRun) {
            if ($exists -and -not $Overwrite) {
                throw "Refusing to overwrite existing file without -Overwrite: $bootTarget"
            }
            $targetDir = Split-Path -Parent $bootTarget
            if (-not (Test-Path -LiteralPath $targetDir)) {
                New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            }
            Set-Content -LiteralPath $bootTarget -Value (Get-BootText -SelectedTool $SelectedTool -SelectedTarget $SelectedTarget) -Encoding UTF8
        }
    }
}

$selectedTools = if ($Tool -eq 'AllIncluded') { @('Codex', 'ClaudeCode', 'OpenCode') } else { @($Tool) }

foreach ($selected in $selectedTools) {
    $target = if ($TargetRoot -and $selectedTools.Count -eq 1) {
        $TargetRoot
    } elseif ($TargetRoot) {
        Join-Path $TargetRoot $selected
    } else {
        Get-DefaultTarget -SelectedTool $selected
    }
    Invoke-InstallPlan -SelectedTool $selected -SelectedTarget $target
}

if ($dryRun) {
    Write-Host ''
    Write-Host 'Dry run only. No files changed. Re-run with -Apply to install.'
    Write-Host 'For double-click review on Windows, run scripts\Install-MALTS.review.cmd so the console stays open.'
}
