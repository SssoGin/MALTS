[CmdletBinding()]
param(
    [ValidateSet('Codex', 'ClaudeCode', 'OpenCode', 'AllIncluded')]
    [string] $Tool = 'Codex',

    [switch] $SkipInstructionTemplate,

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
                $_.Name -ne 'README.md' -and -not ($SkipInstructionTemplate -and $_.Name -eq 'AGENTS.example.md')
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
}

$selectedTools = if ($Tool -eq 'AllIncluded') { @('Codex', 'ClaudeCode', 'OpenCode') } else { @($Tool) }

foreach ($selected in $selectedTools) {
    $target = if ($TargetRoot -and $selectedTools.Count -eq 1) { $TargetRoot } else { Get-DefaultTarget -SelectedTool $selected }
    Invoke-InstallPlan -SelectedTool $selected -SelectedTarget $target
}

if ($dryRun) {
    Write-Host ''
    Write-Host 'Dry run only. No files changed. Re-run with -Apply to install.'
}
