[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Plan', 'PreviewPlan', 'Execute', 'Recover', 'Scan', 'Inspect', 'Doctor', 'DoctorRepairPlan')]
    [string] $Command,

    [string] $LifecycleRoot,
    [string] $ToolRootCodex,
    [string] $ToolRootClaudeCode,
    [string] $ToolRootOpenCode,
    [ValidateSet('codex', 'claude-code', 'opencode')]
    [string[]] $Tool = @(),

    [ValidateSet('install', 'update', 'repair', 'uninstall')]
    [string] $Operation,

    [string] $ReleaseRoot,
    [string] $RepositoryRoot,
    [string] $PreviewRoot,
    [string[]] $ProtectedRoot = @(),
    [string[]] $LegacyRoot = @(),
    [string] $DefaultLegacyRoot = (Join-Path $env:USERPROFILE '.malts'),
    [string] $OperationId,
    [string] $Timestamp,
    [string] $ModificationOverrides,
    [string] $PlanPath,
    [string] $ExpectedPlanHash,
    [string] $OutPath,

    [ValidateSet('DISCOVER', 'LOCK', 'PLAN', 'STAGE', 'SNAPSHOT', 'PREVALIDATE', 'ACTIVATE', 'POSTVALIDATE', 'CLEAN', 'COMMIT', 'ROLLBACK', 'AUDIT_WRITE', 'AUDIT_PRUNE')]
    [string] $FaultAt,

    [switch] $Apply
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$engine = Join-Path $repoRoot 'tools\malts_lifecycle.py'

function Add-RequiredValue {
    param(
        [System.Collections.Generic.List[string]] $Arguments,
        [string] $Name,
        [string] $Value
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Command requires $Name."
    }
    $Arguments.Add($Name)
    $Arguments.Add($Value)
}

function Add-OptionalValue {
    param(
        [System.Collections.Generic.List[string]] $Arguments,
        [string] $Name,
        [string] $Value
    )
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        $Arguments.Add($Name)
        $Arguments.Add($Value)
    }
}

function Add-ToolRoots {
    param([System.Collections.Generic.List[string]] $Arguments)
    $selected = 0
    foreach ($entry in @(
        @{ Tool = 'codex'; Name = 'ToolRootCodex'; Value = $ToolRootCodex },
        @{ Tool = 'claude-code'; Name = 'ToolRootClaudeCode'; Value = $ToolRootClaudeCode },
        @{ Tool = 'opencode'; Name = 'ToolRootOpenCode'; Value = $ToolRootOpenCode }
    )) {
        if (-not [string]::IsNullOrWhiteSpace($entry.Value)) {
            Add-RequiredValue $Arguments '--tool-root' "$($entry.Tool)=$($entry.Value)"
            $selected++
        }
    }
    if ($selected -eq 0) {
        throw "$Command requires at least one of -ToolRootCodex, -ToolRootClaudeCode, or -ToolRootOpenCode."
    }
}

$arguments = [System.Collections.Generic.List[string]]::new()
$arguments.Add($engine)
$cliCommand = switch ($Command) {
    'PreviewPlan' { 'preview-plan' }
    'DoctorRepairPlan' { 'doctor-repair-plan' }
    default { $Command.ToLowerInvariant() }
}
$arguments.Add($cliCommand)

switch ($Command) {
    'Plan' {
        Add-RequiredValue $arguments '--operation' $Operation
        Add-RequiredValue $arguments '--lifecycle-root' $LifecycleRoot
        Add-ToolRoots $arguments
        Add-OptionalValue $arguments '--release-root' $ReleaseRoot
        Add-OptionalValue $arguments '--repository-root' $RepositoryRoot
        foreach ($legacy in $LegacyRoot) {
            Add-OptionalValue $arguments '--legacy-root' $legacy
        }
        Add-OptionalValue $arguments '--default-legacy-root' $DefaultLegacyRoot
        Add-OptionalValue $arguments '--operation-id' $OperationId
        Add-OptionalValue $arguments '--timestamp' $Timestamp
        Add-OptionalValue $arguments '--modification-overrides' $ModificationOverrides
        Add-OptionalValue $arguments '--out' $OutPath
    }
    'PreviewPlan' {
        Add-RequiredValue $arguments '--preview-root' $PreviewRoot
        Add-OptionalValue $arguments '--release-root' $ReleaseRoot
        Add-OptionalValue $arguments '--repository-root' $RepositoryRoot
        foreach ($protected in $ProtectedRoot) {
            Add-OptionalValue $arguments '--protected-root' $protected
        }
        foreach ($selectedTool in $Tool) {
            Add-OptionalValue $arguments '--tool' $selectedTool
        }
        Add-OptionalValue $arguments '--operation-id' $OperationId
        Add-OptionalValue $arguments '--timestamp' $Timestamp
        Add-OptionalValue $arguments '--out' $OutPath
    }
    'Execute' {
        Add-RequiredValue $arguments '--plan' $PlanPath
        Add-RequiredValue $arguments '--expected-plan-hash' $ExpectedPlanHash
        Add-OptionalValue $arguments '--fault-at' $FaultAt
    }
    'Recover' {
        Add-RequiredValue $arguments '--lifecycle-root' $LifecycleRoot
        Add-OptionalValue $arguments '--operation-id' $OperationId
        Add-OptionalValue $arguments '--fault-at' $FaultAt
    }
    { $_ -in @('Scan', 'Inspect', 'Doctor') } {
        Add-RequiredValue $arguments '--lifecycle-root' $LifecycleRoot
        Add-ToolRoots $arguments
        if ($Command -eq 'Doctor') {
            Add-OptionalValue $arguments '--timestamp' $Timestamp
        }
    }
    'DoctorRepairPlan' {
        Add-RequiredValue $arguments '--lifecycle-root' $LifecycleRoot
        Add-ToolRoots $arguments
        Add-OptionalValue $arguments '--release-root' $ReleaseRoot
        Add-OptionalValue $arguments '--repository-root' $RepositoryRoot
        Add-OptionalValue $arguments '--operation-id' $OperationId
        Add-OptionalValue $arguments '--timestamp' $Timestamp
        Add-OptionalValue $arguments '--out' $OutPath
    }
}

if ($Apply) {
    $arguments.Add('--apply')
}

& python -B @arguments
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    exit $exitCode
}
