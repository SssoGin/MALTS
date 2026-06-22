[CmdletBinding()]
param(
    [ValidateSet('All', 'SkillBridgeDiscovery', 'LocalizedProjectControl', 'UpdateSafety')]
    [string] $Check = 'All'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([string] $Message)
    $failures.Add($Message)
}

function Test-SkillBridgeDiscovery {
    $probeRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'MALTS-regression-probe'
    $installScript = Join-Path $PSScriptRoot 'Install-MALTS.ps1'
    $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $installScript `
        -Tool AllIncluded -TargetRoot $probeRoot 2>&1 | Out-String

    if ($LASTEXITCODE -ne 0) {
        Add-Failure "SkillBridgeDiscovery: install dry-run failed.`n$output"
        return
    }

    $skillNames = @(
        'grill-me-preflight',
        'malts-project-init',
        'multi-agent-long-task-scheduling',
        'project-retrospective-growth',
        'session-handoff',
        'single-agent-lightweight-growth'
    )

    foreach ($tool in @('Codex', 'ClaudeCode', 'OpenCode')) {
        foreach ($skillName in $skillNames) {
            $expected = Join-Path $probeRoot "$tool\skills\$skillName\SKILL.md"
            if ($output -notmatch [regex]::Escape($expected)) {
                Add-Failure "SkillBridgeDiscovery: missing planned bridge $expected"
            }
        }
    }
}

function Test-LocalizedProjectControl {
    $lintScript = Join-Path $repoRoot 'tools\agent_system_lint.py'
    $template = Join-Path $repoRoot 'runtime\CH\templates\PROJECT_CONTROL.template.zh-CN.md'
    $output = & python $lintScript check-project-control --project-control $template 2>&1 | Out-String

    if ($LASTEXITCODE -ne 0) {
        Add-Failure "LocalizedProjectControl: Chinese canonical template is rejected by check-project-control.`n$output"
    }

    $initSkill = Get-Content -LiteralPath (Join-Path $repoRoot 'skills\malts-project-init\SKILL.md') -Raw -Encoding UTF8
    $requiredTokens = @(
        'NarrativeLanguage',
        'runtime\CH\templates\PROJECT_CONTROL.template.zh-CN.md',
        'runtime\CH\templates\WORK_TASK_REPORT.template.zh-CN.md'
    )
    foreach ($token in $requiredTokens) {
        if ($initSkill -notmatch [regex]::Escape($token)) {
            Add-Failure "LocalizedProjectControl: malts-project-init is missing language-routing token $token"
        }
    }
}

function Test-UpdateSafety {
    $updateTest = Join-Path $PSScriptRoot 'Test-MALTSUpdate.ps1'
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $updateTest -Check All 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($exitCode -ne 0) {
        Add-Failure "UpdateSafety: update regression suite failed.`n$output"
    }
}

if ($Check -in @('All', 'SkillBridgeDiscovery')) {
    Test-SkillBridgeDiscovery
}
if ($Check -in @('All', 'LocalizedProjectControl')) {
    Test-LocalizedProjectControl
}
if ($Check -in @('All', 'UpdateSafety')) {
    Test-UpdateSafety
}

if ($failures.Count -gt 0) {
    Write-Host "FAIL: $($failures.Count) regression assertion(s) failed."
    foreach ($failure in $failures) {
        Write-Host "- $failure"
    }
    exit 1
}

Write-Host "PASS: $Check"
exit 0
