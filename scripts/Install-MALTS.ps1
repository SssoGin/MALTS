[CmdletBinding()]
param(
    [ValidateSet('Codex', 'ClaudeCode', 'OpenCode', 'AllIncluded')]
    [string] $Tool = 'Codex',

    [switch] $SkipInstructionTemplate,

    [ValidateSet('ManagedMerge', 'Skip', 'Replace')]
    [string] $InstructionMode,

    [switch] $Apply,

    [switch] $Overwrite,

    [switch] $MergeSafe,

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
$manifestName = '.malts-managed-files.json'

if ($Overwrite -and $MergeSafe) {
    throw 'Use either -Overwrite or -MergeSafe, not both.'
}

$instructionModeExplicit = $PSBoundParameters.ContainsKey('InstructionMode')
if ($SkipInstructionTemplate) {
    if ($instructionModeExplicit -and $InstructionMode -ne 'Skip') {
        throw '-SkipInstructionTemplate conflicts with a non-Skip -InstructionMode.'
    }
    $InstructionMode = 'Skip'
} elseif (-not $instructionModeExplicit) {
    $InstructionMode = if ($Overwrite) { 'Replace' } else { 'ManagedMerge' }
}
if ($InstructionMode -eq 'Replace' -and -not $Overwrite) {
    throw '-InstructionMode Replace requires -Overwrite.'
}

$managedInstructionStart = '<!-- MALTS:BEGIN managed instruction -->'
$managedInstructionEnd = '<!-- MALTS:END managed instruction -->'

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
    if (-not $env:USERPROFILE) {
        throw 'USERPROFILE is not set; provide -SharedRoot explicitly.'
    }
    return [System.IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.malts'))
}

function New-InstallItem {
    param(
        [string] $Source,
        [string] $Target,
        [ValidateSet('Shared', 'ToolInstruction', 'ToolSupport', 'ToolBridge', 'ToolBoot')]
        [string] $Category = 'ToolSupport',
        [string] $Content
    )
    return [pscustomobject]@{
        Source = $Source
        Target = $Target
        Category = $Category
        Content = $Content
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
            if ($InstructionMode -ne 'Skip') {
                $items += New-InstallItem -Source (Join-RepoPath 'adapters\codex\AGENTS.example.md') -Target (Join-Path $SelectedTarget 'AGENTS.md') -Category ToolInstruction
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
            if ($InstructionMode -ne 'Skip') {
                $items += New-InstallItem -Source (Join-RepoPath 'adapters\claude-code\CLAUDE.example.md') -Target (Join-Path $SelectedTarget 'CLAUDE.md') -Category ToolInstruction
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
                $_.Name -notlike 'README*.md' -and -not ($InstructionMode -eq 'Skip' -and $_.Name -eq 'AGENTS.example.md')
            } | ForEach-Object {
                $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
                if ($relative -eq 'AGENTS.example.md') {
                    $relative = 'AGENTS.md'
                }
                $category = if ($relative -eq 'AGENTS.md') { 'ToolInstruction' } else { 'ToolSupport' }
                New-InstallItem -Source $_.FullName -Target (Join-Path $SelectedTarget $relative) -Category $category
            }
        }
    }

    $bridgeRoot = Join-RepoPath 'adapters\skill-bridges'
    if (Test-Path -LiteralPath $bridgeRoot) {
        $items += Get-ChildItem -Path $bridgeRoot -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($bridgeRoot.Length).TrimStart('\', '/')
            New-InstallItem -Source $_.FullName -Target (Join-Path (Join-Path $SelectedTarget 'skills') $relative) -Category ToolBridge
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
            $items += New-InstallItem -Source $source -Target (Join-Path $ResolvedSharedRoot $file) -Category Shared
        }
    }

    foreach ($dir in @('runtime', 'skills', 'docs', 'tools', 'adapters', 'scripts')) {
        $sourceRoot = Join-RepoPath $dir
        if (-not (Test-Path -LiteralPath $sourceRoot)) {
            continue
        }
        $items += Get-ChildItem -Path $sourceRoot -Recurse -File | Where-Object {
            $_.Extension -ne '.pyc' -and
            $_.Name -notin @('.DS_Store', 'Thumbs.db') -and
            $_.FullName -notmatch '[\\/](?:__pycache__|\.pytest_cache|\.mypy_cache)[\\/]'
        } | ForEach-Object {
            $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
            New-InstallItem -Source $_.FullName -Target (Join-Path (Join-Path $ResolvedSharedRoot $dir) $relative) -Category Shared
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

function Get-ManagedRelativePath {
    param([string] $Root, [string] $Path)
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    $prefix = $rootFull + [System.IO.Path]::DirectorySeparatorChar
    if (-not $pathFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Managed target is outside its install root: $pathFull"
    }
    return $pathFull.Substring($prefix.Length).Replace('\', '/')
}

function Get-FileHashValue {
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Read-ManagedManifest {
    param([string] $Root)
    $entries = @{}
    $path = Join-Path $Root $manifestName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $entries }

    $data = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in @($data.Files)) {
        if ($entry.Path) { $entries[$entry.Path] = $entry }
    }
    return $entries
}

function Write-ManagedManifest {
    param([string] $Root, [object[]] $Records)
    if ($dryRun) { return }
    if (-not (Test-Path -LiteralPath $Root)) {
        New-Item -ItemType Directory -Force -Path $Root | Out-Null
    }
    $versionPath = Join-RepoPath 'VERSION'
    $sourceVersion = if (Test-Path -LiteralPath $versionPath) {
        (Get-Content -LiteralPath $versionPath -Raw -Encoding UTF8).Trim()
    } else {
        $null
    }
    $manifest = [ordered]@{
        SchemaVersion = 1
        SourceVersion = $sourceVersion
        Generated = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')
        Files = @($Records | Sort-Object Path)
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Root $manifestName) -Encoding UTF8
}

function Test-SafeManifestRelativePath {
    param([string] $RelativePath)
    if ([System.IO.Path]::IsPathRooted($RelativePath)) { return $false }
    return -not (($RelativePath -replace '\\', '/') -split '/' | Where-Object { $_ -eq '..' })
}

function Get-TextFileProfile {
    param([string] $Path)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    $text = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))
    $newline = if ($text.Contains("`r`n")) { "`r`n" } elseif ($text.Contains("`n")) { "`n" } else { [System.Environment]::NewLine }
    return [pscustomobject]@{
        Text = $text
        HasBom = $hasBom
        Newline = $newline
    }
}

function Convert-TextNewlines {
    param([string] $Text, [string] $Newline)
    return [regex]::Replace($Text, "`r`n|`r|`n", $Newline)
}

function Write-Utf8TextFile {
    param(
        [string] $Path,
        [string] $Text,
        [bool] $HasBom
    )
    $targetDir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }
    $temporary = Join-Path $targetDir ('.malts-write-' + [System.Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [System.IO.File]::WriteAllText($temporary, $Text, [System.Text.UTF8Encoding]::new($HasBom))
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Get-ManagedInstructionSource {
    param([string] $Path)
    $profile = Get-TextFileProfile -Path $Path
    $startMatches = [regex]::Matches($profile.Text, [regex]::Escape($managedInstructionStart))
    $endMatches = [regex]::Matches($profile.Text, [regex]::Escape($managedInstructionEnd))
    if ($startMatches.Count -ne 1 -or $endMatches.Count -ne 1) {
        throw "Instruction source must contain exactly one MALTS managed marker pair: $Path"
    }
    $start = $startMatches[0].Index
    $end = $endMatches[0].Index + $managedInstructionEnd.Length
    if ($end -le $start) {
        throw "Instruction source has an invalid MALTS managed marker order: $Path"
    }
    return [pscustomobject]@{
        Profile = $profile
        Block = $profile.Text.Substring($start, $end - $start)
    }
}

function Get-LegacyInstructionEnd {
    param(
        [string] $Text,
        [int] $SearchStart
    )
    $knownHeadings = @(
        'MALTS Operating Rules',
        'Codex Long-Task Mode',
        'Claude Code Long-Task Mode',
        'OpenCode Long-Task Mode',
        'Model Policy',
        'Handoff Document Rule',
        'Migration Package Rule',
        'Runtime Documents',
        'Safety'
    )
    $headingMatches = [regex]::Matches($Text.Substring($SearchStart), '(?m)^(#{1,2})[ \t]+([^\r\n]+?)[ \t]*\r?$')
    foreach ($heading in $headingMatches) {
        $level = $heading.Groups[1].Value.Length
        $title = $heading.Groups[2].Value.Trim()
        if ($level -eq 1 -or $title -notin $knownHeadings) {
            return $SearchStart + $heading.Index
        }
    }
    return $Text.Length
}

function Get-InstructionMergePlan {
    param([object] $Item)
    $source = Get-ManagedInstructionSource -Path $Item.Source
    if (-not (Test-Path -LiteralPath $Item.Target -PathType Leaf)) {
        return [pscustomobject]@{
            Status = 'create-instruction'
            Changed = $true
            Content = $source.Profile.Text
            HasBom = $source.Profile.HasBom
        }
    }

    $target = Get-TextFileProfile -Path $Item.Target
    $block = Convert-TextNewlines -Text $source.Block -Newline $target.Newline
    $startMatches = [regex]::Matches($target.Text, [regex]::Escape($managedInstructionStart))
    $endMatches = [regex]::Matches($target.Text, [regex]::Escape($managedInstructionEnd))
    if ($startMatches.Count -gt 0 -or $endMatches.Count -gt 0) {
        if ($startMatches.Count -ne 1 -or $endMatches.Count -ne 1) {
            throw "Instruction target has an ambiguous MALTS managed marker set: $($Item.Target)"
        }
        $start = $startMatches[0].Index
        $end = $endMatches[0].Index + $managedInstructionEnd.Length
        if ($end -le $start) {
            throw "Instruction target has an invalid MALTS managed marker order: $($Item.Target)"
        }
        $content = $target.Text.Substring(0, $start) + $block + $target.Text.Substring($end)
        return [pscustomobject]@{
            Status = if ($content -ceq $target.Text) { 'unchanged-managed' } else { 'update-managed' }
            Changed = $content -cne $target.Text
            Content = $content
            HasBom = $target.HasBom
        }
    }

    $legacyMatches = [regex]::Matches($target.Text, '(?m)^#{1,2}[ \t]+Global Agent System Discovery[ \t]*\r?$')
    if ($legacyMatches.Count -gt 1) {
        throw "Instruction target has multiple legacy MALTS discovery headings: $($Item.Target)"
    }
    if ($legacyMatches.Count -eq 1) {
        $legacyStart = $legacyMatches[0].Index
        $searchStart = $legacyMatches[0].Index + $legacyMatches[0].Length
        $legacyEnd = Get-LegacyInstructionEnd -Text $target.Text -SearchStart $searchStart
        $prefix = $target.Text.Substring(0, $legacyStart)
        $suffix = if ($legacyEnd -lt $target.Text.Length) {
            $target.Newline + $target.Newline + $target.Text.Substring($legacyEnd).TrimStart("`r", "`n")
        } else {
            $target.Newline
        }
        return [pscustomobject]@{
            Status = 'migrate-legacy'
            Changed = $true
            Content = $prefix + $block + $suffix
            HasBom = $target.HasBom
        }
    }

    $separator = if ($target.Text.Length -eq 0) {
        ''
    } elseif ($target.Text.EndsWith($target.Newline + $target.Newline)) {
        ''
    } elseif ($target.Text.EndsWith($target.Newline)) {
        $target.Newline
    } else {
        $target.Newline + $target.Newline
    }
    return [pscustomobject]@{
        Status = 'append-managed'
        Changed = $true
        Content = $target.Text + $separator + $block + $target.Newline
        HasBom = $target.HasBom
    }
}

function Test-CanReplaceExisting {
    param([object] $Item, [object] $PreviousEntry)
    if (-not (Test-Path -LiteralPath $Item.Target)) { return $true }
    if ($Overwrite) { return $true }
    if (-not $MergeSafe) { return $false }
    if ($Item.Category -in @('Shared', 'ToolBridge', 'ToolBoot')) { return $true }
    if ($Item.Category -eq 'ToolInstruction') { return $false }
    if ($PreviousEntry -and $PreviousEntry.InstalledSha256) {
        return (Get-FileHashValue -Path $Item.Target) -eq $PreviousEntry.InstalledSha256
    }
    return $false
}

function Invoke-ManagedPlan {
    param(
        [object[]] $Items,
        [string] $Root
    )

    $previous = Read-ManagedManifest -Root $Root
    $records = [System.Collections.Generic.List[object]]::new()
    $planned = @{}

    if (-not $MergeSafe -and -not $Overwrite) {
        foreach ($item in $Items) {
            if ($item.Category -eq 'ToolInstruction' -and $InstructionMode -eq 'ManagedMerge') { continue }
            if (-not (Test-Path -LiteralPath $item.Target)) { continue }
            if ($item.Source -and [System.IO.Path]::GetFullPath($item.Source).Equals(
                [System.IO.Path]::GetFullPath($item.Target),
                [System.StringComparison]::OrdinalIgnoreCase
            )) { continue }
            throw "Refusing to overwrite existing file without -Overwrite or -MergeSafe: $($item.Target)"
        }
    }

    foreach ($item in $Items) {
        $relative = Get-ManagedRelativePath -Root $Root -Path $item.Target
        $planned[$relative] = $true
        $previousEntry = if ($previous.ContainsKey($relative)) { $previous[$relative] } else { $null }

        if ($item.Category -eq 'ToolInstruction' -and $InstructionMode -eq 'ManagedMerge') {
            $instructionPlan = Get-InstructionMergePlan -Item $item
            Write-Host "[$($instructionPlan.Status)] $($item.Target)"
            Write-Host "  managed block from $($item.Source)"
            if (-not $dryRun -and $instructionPlan.Changed) {
                Write-Utf8TextFile -Path $item.Target -Text $instructionPlan.Content -HasBom $instructionPlan.HasBom
            }
            $records.Add([pscustomobject]@{
                Path = $relative
                Category = $item.Category
                InstalledSha256 = if ($dryRun) { $null } else { Get-FileHashValue -Path $item.Target }
            })
            continue
        }

        $exists = Test-Path -LiteralPath $item.Target
        $sameSourceTarget = $item.Source -and (
            [System.IO.Path]::GetFullPath($item.Source).Equals(
                [System.IO.Path]::GetFullPath($item.Target),
                [System.StringComparison]::OrdinalIgnoreCase
            )
        )
        $replace = if ($sameSourceTarget) { $false } else { Test-CanReplaceExisting -Item $item -PreviousEntry $previousEntry }
        $status = if ($sameSourceTarget) { 'canonical-existing' } elseif (-not $exists) { 'new' } elseif ($replace) { 'update-managed' } else { 'preserve-existing' }
        Write-Host "[$status] $($item.Target)"
        if ($item.Source) {
            Write-Host "  from $($item.Source)"
        } else {
            Write-Host '  generated content'
        }

        if ($exists -and -not $replace -and -not $MergeSafe) {
            throw "Refusing to overwrite existing file without -Overwrite or -MergeSafe: $($item.Target)"
        }

        $copied = $false
        if (-not $dryRun -and (-not $exists -or $replace)) {
            $targetDir = Split-Path -Parent $item.Target
            if (-not (Test-Path -LiteralPath $targetDir)) {
                New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
            }
            if ($item.Source) {
                Copy-Item -LiteralPath $item.Source -Destination $item.Target -Force
            } else {
                Set-Content -LiteralPath $item.Target -Value $item.Content -Encoding UTF8
            }
            $copied = $true
        }

        $installedHash = $null
        if (-not $dryRun) {
            if ($copied) {
                $installedHash = Get-FileHashValue -Path $item.Target
            } elseif ($previousEntry -and $previousEntry.InstalledSha256) {
                $installedHash = $previousEntry.InstalledSha256
            } elseif ($item.Source -and (Get-FileHashValue -Path $item.Source) -eq (Get-FileHashValue -Path $item.Target)) {
                $installedHash = Get-FileHashValue -Path $item.Target
            }
        }
        $records.Add([pscustomobject]@{
            Path = $relative
            Category = $item.Category
            InstalledSha256 = $installedHash
        })
    }

    foreach ($relative in @($previous.Keys | Sort-Object)) {
        if ($planned.ContainsKey($relative)) { continue }
        $entry = $previous[$relative]
        if ($entry.Category -eq 'ToolInstruction') {
            $records.Add($entry)
            continue
        }
        if (-not (Test-SafeManifestRelativePath -RelativePath $relative)) {
            Write-Warning "Ignoring unsafe managed manifest path: $relative"
            continue
        }
        $candidate = [System.IO.Path]::GetFullPath((Join-Path $Root ($relative -replace '/', '\')))
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $currentHash = Get-FileHashValue -Path $candidate
        if ($entry.InstalledSha256 -and $currentHash -eq $entry.InstalledSha256) {
            Write-Host "[remove-stale] $candidate"
            if (-not $dryRun) { Remove-Item -LiteralPath $candidate -Force }
        } else {
            Write-Host "[preserve-modified-stale] $candidate"
            $records.Add($entry)
        }
    }

    Write-ManagedManifest -Root $Root -Records $records
}

function Invoke-ToolInstall {
    param(
        [string] $SelectedTool,
        [string] $SelectedTarget,
        [string] $ResolvedSharedRoot
    )

    $plan = @(Get-ToolInstallItems -SelectedTool $SelectedTool -SelectedTarget $SelectedTarget)
    $plan += New-InstallItem -Target (Join-Path $SelectedTarget 'MALTS_BOOT.md') -Category ToolBoot -Content (Get-BootText -SelectedTool $SelectedTool -ResolvedSharedRoot $ResolvedSharedRoot)

    Write-Host ''
    Write-Host "Tool: $SelectedTool"
    Write-Host "Target: $SelectedTarget"
    Write-Host "Instruction mode: $InstructionMode"
    Write-Host "Tool-local skills: Discovery bridges included; shared MALTS_ROOT remains canonical"
    Write-Host "Installed boot pointer: Included as MALTS_BOOT.md"
    Write-Host "Mode: $(if ($dryRun) { 'DryRun' } else { 'Apply' })"

    Invoke-ManagedPlan -Items $plan -Root $SelectedTarget
}

function Test-PathNested {
    param([string] $Path, [string] $Parent)
    $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\', '/')
    if ($pathFull.Equals($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    $prefix = $parentFull + [System.IO.Path]::DirectorySeparatorChar
    return $pathFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

$selectedTools = if ($Tool -eq 'AllIncluded') { @('Codex', 'ClaudeCode', 'OpenCode') } else { @($Tool) }
$resolvedSharedRoot = Resolve-SharedRoot
$installTargets = @()

foreach ($selected in $selectedTools) {
    $target = if ($TargetRoot -and $selectedTools.Count -eq 1) {
        $TargetRoot
    } elseif ($TargetRoot) {
        Join-Path $TargetRoot $selected
    } else {
        Get-DefaultTarget -SelectedTool $selected
    }
    $target = [System.IO.Path]::GetFullPath($target)
    if ((Test-PathNested -Path $resolvedSharedRoot -Parent $target) -or (Test-PathNested -Path $target -Parent $resolvedSharedRoot)) {
        throw "Shared MALTS_ROOT and tool target must be separate paths: shared=$resolvedSharedRoot target=$target"
    }
    $installTargets += [pscustomobject]@{ Tool = $selected; Target = $target }
}

Write-Host "MALTS install"
Write-Host "Shared MALTS_ROOT: $resolvedSharedRoot"
Write-Host "Shared runtime copy: Included once at shared MALTS_ROOT"
Write-Host "Tool set: $($selectedTools -join ', ')"

$sharedPlan = @(Get-SharedRootInstallItems -ResolvedSharedRoot $resolvedSharedRoot)
Invoke-ManagedPlan -Items $sharedPlan -Root $resolvedSharedRoot

foreach ($entry in $installTargets) {
    Invoke-ToolInstall -SelectedTool $entry.Tool -SelectedTarget $entry.Target -ResolvedSharedRoot $resolvedSharedRoot
}

if ($dryRun) {
    Write-Host ''
    Write-Host 'Dry run only. No files changed. Re-run with -Apply to install.'
    Write-Host 'For double-click review on Windows, run scripts\Install-MALTS.review.cmd so the console stays open.'
}
