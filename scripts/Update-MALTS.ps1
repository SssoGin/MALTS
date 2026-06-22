[CmdletBinding()]
param(
    [ValidateSet('Codex', 'ClaudeCode', 'OpenCode', 'AllIncluded')]
    [string] $Tool = 'Codex',

    [ValidateSet('PullOnly', 'InstallOnly', 'PullAndInstall')]
    [string] $Mode = 'PullAndInstall',

    [ValidateSet('MergeSafe', 'Overwrite')]
    [string] $Strategy = 'MergeSafe',

    [ValidateSet('ManagedMerge', 'Skip', 'Replace')]
    [string] $InstructionMode,

    [string] $RepoRoot,

    [string] $TargetRoot,

    [string] $SharedRoot,

    [string] $Branch,

    [switch] $Apply,

    [switch] $AllowDirty,

    [switch] $Reinstall
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

if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
$dryRun = -not $Apply
$resolvedInstructionMode = if ($PSBoundParameters.ContainsKey('InstructionMode')) {
    $InstructionMode
} elseif ($Strategy -eq 'Overwrite') {
    'Replace'
} else {
    'ManagedMerge'
}
if ($resolvedInstructionMode -eq 'Replace' -and $Strategy -ne 'Overwrite') {
    throw '-InstructionMode Replace requires -Strategy Overwrite.'
}

function Invoke-Git {
    param([string[]] $Arguments)
    return (& git -C $RepoRoot @Arguments) 2>&1
}

function Test-GitRepo {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'git was not found on PATH. Install Git, or run with -Mode InstallOnly from an already downloaded MALTS package.'
    }
    $inside = Invoke-Git @('rev-parse', '--is-inside-work-tree')
    if ($LASTEXITCODE -ne 0 -or ($inside | Select-Object -First 1) -ne 'true') {
        throw "RepoRoot is not a git working tree: $RepoRoot"
    }
}

function Invoke-RepoChecks {
    $lint = Join-Path $RepoRoot 'tools\agent_system_lint.py'
    if (-not (Test-Path -LiteralPath $lint)) {
        Write-Warning "Skipping repo checks; lint script not found: $lint"
        return
    }
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Warning 'Skipping repo checks; python was not found on PATH.'
        return
    }

    & python $lint check-public-safety --malts-root $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw 'check-public-safety failed.' }
    & python $lint check-doc-sync --output-root (Join-Path $RepoRoot 'runtime') --require-ch
    if ($LASTEXITCODE -ne 0) { throw 'runtime doc sync check failed.' }
    & python $lint check-adapter-parity --malts-root $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw 'adapter parity check failed.' }
    & python $lint check-semantic-freshness --malts-root $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw 'semantic freshness check failed.' }
}

function Invoke-Installer {
    $installScript = Join-Path $RepoRoot 'scripts\Install-MALTS.ps1'
    if (-not (Test-Path -LiteralPath $installScript)) {
        throw "Install script not found: $installScript"
    }

    $installArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installScript, '-Tool', $Tool)
    if ($TargetRoot) {
        $installArgs += @('-TargetRoot', $TargetRoot)
    }
    if ($SharedRoot) {
        $installArgs += @('-SharedRoot', $SharedRoot)
    }
    if ($Strategy -eq 'MergeSafe') {
        $installArgs += '-MergeSafe'
    } else {
        $installArgs += '-Overwrite'
    }
    $installArgs += @('-InstructionMode', $resolvedInstructionMode)
    if ($Apply) {
        $installArgs += '-Apply'
    }

    Write-Host "Invoking installer with strategy: $Strategy"
    & powershell @installArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Install-MALTS.ps1 failed.'
    }
}

Write-Host "MALTS update"
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Tool: $Tool"
Write-Host "Mode: $Mode"
Write-Host "Strategy: $Strategy"
Write-Host "InstructionMode: $resolvedInstructionMode"
Write-Host "TargetRoot: $(if ($TargetRoot) { $TargetRoot } else { '<tool default>' })"
Write-Host "SharedRoot: $(if ($SharedRoot) { $SharedRoot } else { '<default shared MALTS_ROOT>' })"
Write-Host "Apply: $Apply"
Write-Host "Reinstall: $Reinstall"

if ($Mode -eq 'PullOnly' -and $Reinstall) {
    throw '-Reinstall cannot be combined with -Mode PullOnly.'
}

$remoteUpdateAvailable = $false

if ($Mode -ne 'InstallOnly') {
    Test-GitRepo

    if (-not $Branch) {
        $Branch = (Invoke-Git @('rev-parse', '--abbrev-ref', 'HEAD') | Select-Object -First 1).Trim()
    }
    $remote = (Invoke-Git @('config', '--get', "branch.$Branch.remote") | Select-Object -First 1).Trim()
    if (-not $remote) { $remote = 'origin' }

    $mergeRef = (Invoke-Git @('config', '--get', "branch.$Branch.merge") | Select-Object -First 1).Trim()
    if (-not $mergeRef) { $mergeRef = "refs/heads/$Branch" }

    $localHead = (Invoke-Git @('rev-parse', 'HEAD') | Select-Object -First 1).Trim()
    $remoteLine = Invoke-Git @('ls-remote', $remote, $mergeRef) | Select-Object -First 1
    if (-not $remoteLine) {
        throw "Could not read remote branch: $remote $mergeRef"
    }
    $remoteHead = ($remoteLine -split "\s+")[0]
    $dirty = @(Invoke-Git @('status', '--porcelain') | Where-Object { $_ })

    Write-Host "Branch: $Branch"
    Write-Host "Remote: $remote"
    Write-Host "Local HEAD: $localHead"
    Write-Host "Remote HEAD: $remoteHead"

    if ($localHead -eq $remoteHead) {
        Write-Host 'Already up to date. No remote update is available.'
    } else {
        $remoteUpdateAvailable = $true
        if ($dirty.Count -gt 0) {
            Write-Host "Working tree has local changes: $($dirty.Count) item(s)."
            if ($Apply -and -not $AllowDirty) {
                throw 'Refusing to pull with local changes. Commit/stash them first, or rerun with -AllowDirty after review.'
            }
        }
        if ($dryRun) {
            Write-Host 'Remote update is available. Dry-run only; rerun with -Apply to pull.'
        } else {
            Write-Host 'Pulling remote updates with --ff-only...'
            Invoke-Git @('pull', '--ff-only', $remote, $Branch) | Write-Host
            if ($LASTEXITCODE -ne 0) {
                throw 'git pull --ff-only failed.'
            }
        }
    }
}

$shouldInstall = $Mode -eq 'InstallOnly' -or $remoteUpdateAvailable -or $Reinstall
if ($shouldInstall) {
    Invoke-Installer
} elseif ($Mode -eq 'PullAndInstall') {
    Write-Host 'Skipping install because no remote update is available. Use -Reinstall to reinstall the current version.'
}

if ($Apply) {
    Invoke-RepoChecks
} else {
    Write-Host 'Dry run only. No files changed. Re-run with -Apply to pull and/or install.'
}
