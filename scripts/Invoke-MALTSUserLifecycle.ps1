[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('install', 'update')]
    [string] $Operation,

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
$lifecycleScript = Join-Path $PSScriptRoot 'Invoke-MALTSLifecycle.ps1'

function Get-DefaultReleaseRoot {
    $payloadRoot = Split-Path -Parent $PSScriptRoot
    $artifactRoot = Split-Path -Parent $payloadRoot
    $outerRoot = Split-Path -Parent $artifactRoot
    if (Test-Path -LiteralPath (Join-Path $outerRoot 'release_manifest.json') -PathType Leaf) {
        return $outerRoot
    }
    return $null
}

function Get-DefaultRepositoryRoot {
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    if (Test-Path -LiteralPath (Join-Path $repositoryRoot 'MALTS_RELEASE.json') -PathType Leaf) {
        return $repositoryRoot
    }
    return $null
}

function Read-ValueWithDefault {
    param(
        [Parameter(Mandatory)]
        [string] $Prompt,
        [Parameter(Mandatory)]
        [string] $Default
    )
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value.Trim()
}

function Get-DefaultToolRoot {
    param([Parameter(Mandatory)][string] $Name)
    switch ($Name) {
        'Codex' { return (Join-Path $env:USERPROFILE '.codex') }
        'ClaudeCode' { return (Join-Path $env:USERPROFILE '.claude') }
        'OpenCode' { return (Join-Path $env:USERPROFILE '.config\opencode') }
    }
}

function Add-SelectedTool {
    param(
        [System.Collections.Generic.List[string]] $Items,
        [string] $Name
    )
    if (-not $Items.Contains($Name)) {
        $Items.Add($Name)
    }
}

if (-not (Test-Path -LiteralPath $lifecycleScript -PathType Leaf)) {
    throw "Required lifecycle entry point is missing: $lifecycleScript"
}

if ($Apply) {
    if ([string]::IsNullOrWhiteSpace($PlanPath) -or [string]::IsNullOrWhiteSpace($ExpectedPlanHash)) {
        throw '-Apply requires both -PlanPath and -ExpectedPlanHash from a previously reviewed plan.'
    }
    & $lifecycleScript -Command Execute -PlanPath $PlanPath -ExpectedPlanHash $ExpectedPlanHash -Apply
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    return
}

if (-not [string]::IsNullOrWhiteSpace($ReleaseRoot) -and -not [string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    throw 'Specify exactly one of -ReleaseRoot or -RepositoryRoot.'
}
if ([string]::IsNullOrWhiteSpace($ReleaseRoot) -and [string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $ReleaseRoot = Get-DefaultReleaseRoot
    if ([string]::IsNullOrWhiteSpace($ReleaseRoot)) {
        $RepositoryRoot = Get-DefaultRepositoryRoot
    }
}
if (-not [string]::IsNullOrWhiteSpace($ReleaseRoot)) {
    if (-not (Test-Path -LiteralPath (Join-Path $ReleaseRoot 'release_manifest.json') -PathType Leaf)) {
        throw "ReleaseRoot is not an extracted MALTS outer package: $ReleaseRoot"
    }
} elseif (-not [string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot 'MALTS_RELEASE.json') -PathType Leaf)) {
        throw "RepositoryRoot is not a MALTS public repository source: $RepositoryRoot"
    }
} else {
    throw 'Use an extracted Release package or a public repository root that contains MALTS_RELEASE.json.'
}

$defaultLifecycleRoot = Join-Path $env:USERPROFILE '.agent-system\lifecycle'
if ([string]::IsNullOrWhiteSpace($LifecycleRoot)) {
    if ($UseDefaultRoots) {
        $LifecycleRoot = $defaultLifecycleRoot
    } elseif ($Interactive) {
        $LifecycleRoot = Read-ValueWithDefault -Prompt 'Lifecycle root' -Default $defaultLifecycleRoot
    } else {
        throw '-LifecycleRoot is required unless -UseDefaultRoots or -Interactive is selected.'
    }
}

$selected = [System.Collections.Generic.List[string]]::new()
foreach ($name in $Tool) {
    if ($name -eq 'AllIncluded') {
        foreach ($included in @('Codex', 'ClaudeCode', 'OpenCode')) {
            Add-SelectedTool -Items $selected -Name $included
        }
    } else {
        Add-SelectedTool -Items $selected -Name $name
    }
}
if (-not [string]::IsNullOrWhiteSpace($ToolRootCodex)) { Add-SelectedTool -Items $selected -Name 'Codex' }
if (-not [string]::IsNullOrWhiteSpace($ToolRootClaudeCode)) { Add-SelectedTool -Items $selected -Name 'ClaudeCode' }
if (-not [string]::IsNullOrWhiteSpace($ToolRootOpenCode)) { Add-SelectedTool -Items $selected -Name 'OpenCode' }

if ($selected.Count -eq 0 -and $Interactive) {
    $selection = Read-Host 'Select tools: Codex, ClaudeCode, OpenCode, or AllIncluded'
    if ([string]::IsNullOrWhiteSpace($selection)) {
        throw 'At least one tool must be selected.'
    }
    foreach ($name in $selection.Split(',')) {
        $trimmed = $name.Trim()
        if ($trimmed -eq 'AllIncluded') {
            foreach ($included in @('Codex', 'ClaudeCode', 'OpenCode')) {
                Add-SelectedTool -Items $selected -Name $included
            }
        } elseif ($trimmed -in @('Codex', 'ClaudeCode', 'OpenCode')) {
            Add-SelectedTool -Items $selected -Name $trimmed
        } else {
            throw "Unsupported tool selection: $trimmed"
        }
    }
}
if ($selected.Count -eq 0) {
    throw 'Select at least one -Tool or provide at least one explicit -ToolRoot*.'
}

$toolRoots = @{
    Codex = $ToolRootCodex
    ClaudeCode = $ToolRootClaudeCode
    OpenCode = $ToolRootOpenCode
}
foreach ($name in $selected) {
    if ([string]::IsNullOrWhiteSpace($toolRoots[$name])) {
        $defaultRoot = Get-DefaultToolRoot -Name $name
        if ($UseDefaultRoots) {
            $toolRoots[$name] = $defaultRoot
        } elseif ($Interactive) {
            $toolRoots[$name] = Read-ValueWithDefault -Prompt "$name root" -Default $defaultRoot
        } else {
            throw "A root for $name is required unless -UseDefaultRoots or -Interactive is selected."
        }
    }
}

if ([string]::IsNullOrWhiteSpace($PlanPath)) {
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
    $PlanPath = Join-Path $LifecycleRoot ("plans\MALTS-{0}-{1}.json" -f $Operation, $stamp)
}
if (Test-Path -LiteralPath $PlanPath) {
    throw "Refusing to overwrite an existing plan: $PlanPath"
}

$planParameters = @{
    Command = 'Plan'
    Operation = $Operation
    LifecycleRoot = $LifecycleRoot
    LegacyRoot = $LegacyRoot
    OutPath = $PlanPath
    Apply = $true
}
if (-not [string]::IsNullOrWhiteSpace($ReleaseRoot)) { $planParameters.ReleaseRoot = $ReleaseRoot }
if (-not [string]::IsNullOrWhiteSpace($RepositoryRoot)) { $planParameters.RepositoryRoot = $RepositoryRoot }
if (-not [string]::IsNullOrWhiteSpace($OperationId)) { $planParameters.OperationId = $OperationId }
if ($selected.Contains('Codex')) { $planParameters.ToolRootCodex = $toolRoots.Codex }
if ($selected.Contains('ClaudeCode')) { $planParameters.ToolRootClaudeCode = $toolRoots.ClaudeCode }
if ($selected.Contains('OpenCode')) { $planParameters.ToolRootOpenCode = $toolRoots.OpenCode }

$planOutput = @(& $lifecycleScript @planParameters)
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
$planResult = ($planOutput -join [Environment]::NewLine) | ConvertFrom-Json
$writtenPlan = Get-Content -LiteralPath $PlanPath -Raw -Encoding UTF8 | ConvertFrom-Json
$planHash = [string]$writtenPlan.plan_contract.plan_hash
if ([string]::IsNullOrWhiteSpace($planHash) -or $planResult.plan_hash -ne $planHash) {
    throw 'The persisted plan hash does not match the lifecycle planning result.'
}

$rootSummary = [ordered]@{}
foreach ($name in $selected) { $rootSummary[$name] = $toolRoots[$name] }
$summary = [ordered]@{
    status = 'PASS'
    mode = 'PLAN_REVIEW'
    writes_performed = $true
    operation = $Operation
    source_kind = $(if (-not [string]::IsNullOrWhiteSpace($RepositoryRoot)) { 'repository' } else { 'release-package' })
    release_root = $ReleaseRoot
    repository_root = $RepositoryRoot
    lifecycle_root = $LifecycleRoot
    tool_roots = $rootSummary
    plan_path = $PlanPath
    plan_hash = $planHash
    action_count = @($writtenPlan.plan_contract.actions).Count
    destructive_action_count = @($writtenPlan.plan_contract.actions | Where-Object { $_.destructive }).Count
    user_modification_count = @($writtenPlan.plan_contract.user_modifications).Count
    expected_cleanup_count = @($writtenPlan.plan_contract.expected_cleanup).Count
    next_command = ".\scripts\{0}-MALTS.ps1 -Apply -PlanPath `"{1}`" -ExpectedPlanHash {2}" -f ($(if ($Operation -eq 'install') { 'Install' } else { 'Update' })), $PlanPath, $planHash
}
$summary | ConvertTo-Json -Depth 8

if (-not $Interactive) {
    return
}

Write-Host ''
Write-Host "Review the complete plan before execution: $PlanPath"
Write-Host "Plan hash: $planHash"
Write-Host 'To execute in this same window, type the exact plan hash. Press Enter to stop after review.'
$confirmation = Read-Host 'Plan hash'
if ([string]::IsNullOrWhiteSpace($confirmation)) {
    Write-Host 'Stopped after plan review. No installation or update was executed.'
    return
}
if ($confirmation.Trim().ToUpperInvariant() -ne $planHash.ToUpperInvariant()) {
    throw 'Entered hash does not match the reviewed plan. Nothing was executed.'
}

& $lifecycleScript -Command Execute -PlanPath $PlanPath -ExpectedPlanHash $planHash -Apply
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
