[CmdletBinding()]
param(
    [ValidateSet('Codex', 'ClaudeCode', 'OpenCode', 'AllIncluded')]
    [string] $Tool = 'AllIncluded',

    [string] $TempRoot,

    [switch] $KeepTemp
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$createdTemp = $false

if (-not $TempRoot) {
    $TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MALTS-install-smoke-" + [System.Guid]::NewGuid().ToString("N"))
    $createdTemp = $true
}
$TempRoot = [System.IO.Path]::GetFullPath($TempRoot)
$targetsRoot = Join-Path $TempRoot 'targets'
$sharedRoot = Join-Path $TempRoot 'shared'

if (Test-Path -LiteralPath $TempRoot) {
    throw "TempRoot already exists; choose an empty path: $TempRoot"
}

function Assert-SafeTempPath {
    param([string] $Path)
    $resolved = [System.IO.Path]::GetFullPath($Path)
    $tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $leaf = Split-Path -Leaf $resolved
    if (-not $resolved.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside temp root: $resolved"
    }
    if (-not $leaf.StartsWith('MALTS-install-smoke-', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path without MALTS smoke-test prefix: $resolved"
    }
}

function Get-InstallRoots {
    if ($Tool -eq 'AllIncluded') {
        return @(
            [pscustomobject]@{ Tool = 'Codex'; Root = Join-Path $targetsRoot 'Codex' },
            [pscustomobject]@{ Tool = 'ClaudeCode'; Root = Join-Path $targetsRoot 'ClaudeCode' },
            [pscustomobject]@{ Tool = 'OpenCode'; Root = Join-Path $targetsRoot 'OpenCode' }
        )
    }
    return @([pscustomobject]@{ Tool = $Tool; Root = $targetsRoot })
}

try {
    $installScript = Join-Path $repoRoot 'scripts\Install-MALTS.ps1'
    $lintScript = Join-Path $repoRoot 'tools\agent_system_lint.py'

    & powershell -NoProfile -ExecutionPolicy Bypass -File $installScript -Tool $Tool -TargetRoot $targetsRoot -SharedRoot $sharedRoot -Apply -Overwrite
    if ($LASTEXITCODE -ne 0) {
        throw 'Install-MALTS.ps1 smoke install failed.'
    }

    foreach ($entry in Get-InstallRoots) {
        & python $lintScript check-install-layout --install-root $entry.Root --tool $entry.Tool
        if ($LASTEXITCODE -ne 0) {
            throw "Installed layout check failed for $($entry.Tool): $($entry.Root)"
        }
    }

    Write-Host "PASS: MALTS install smoke test completed at $TempRoot"
}
finally {
    if ($createdTemp -and -not $KeepTemp -and (Test-Path -LiteralPath $TempRoot)) {
        Assert-SafeTempPath -Path $TempRoot
        Remove-Item -LiteralPath $TempRoot -Recurse -Force
        Write-Host "Removed smoke-test temp directory: $TempRoot"
    } elseif (Test-Path -LiteralPath $TempRoot) {
        Write-Host "Kept smoke-test temp directory: $TempRoot"
    }
}
