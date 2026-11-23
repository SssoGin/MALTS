[CmdletBinding()]
param(
    [string] $ReleaseRoot,
    [string] $RepositoryRoot,
    [string] $LifecycleRoot,
    [ValidateSet('Codex', 'ClaudeCode', 'OpenCode', 'DeepSeekHarness', 'Antigravity', 'AllIncluded')]
    [string[]] $Tool = @(),
    [string] $ToolRootCodex,
    [string] $ToolRootClaudeCode,
    [string] $ToolRootOpenCode,
    [string] $ToolRootAntigravity,
    [Alias('ToolRootDeepSeekDesktop')]
    [string] $ToolRootDeepSeekHarness,
    [string[]] $LegacyRoot = @(),
    [string[]] $HostConfig = @(),
    [string[]] $Workspace = @(),
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
