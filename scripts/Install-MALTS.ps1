[CmdletBinding()]
param(
    [string] $ReleaseRoot,
    [string] $RepositoryRoot,
    [string] $LifecycleRoot,
    [ValidateSet('Codex', 'ClaudeCode', 'OpenCode', 'AllIncluded')]
    [string[]] $Tool = @(),
    [string] $ToolRootCodex,
    [string] $ToolRootClaudeCode,
    [string] $ToolRootOpenCode,
    [string[]] $LegacyRoot = @(),
    [string] $OperationId,
    [string] $PlanPath,
    [string] $ExpectedPlanHash,
    [switch] $UseDefaultRoots,
    [switch] $Interactive,
    [switch] $Apply
)

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'Invoke-MALTSUserLifecycle.ps1'
& $runner -Operation install @PSBoundParameters
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
