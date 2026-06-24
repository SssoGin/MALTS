[CmdletBinding()]
param(
    [ValidateSet('All', 'SkillBridgeDiscovery', 'LocalizedProjectControl', 'UpdateSafety', 'ProjectControlVersionMetadata', 'ManagedInstructionSync')]
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

function Get-ManagedInstructionBlock {
    param([string] $Path)
    $start = '<!-- MALTS:BEGIN managed instruction -->'
    $end = '<!-- MALTS:END managed instruction -->'
    $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $startIndex = $text.IndexOf($start)
    $endIndex = $text.IndexOf($end)
    if ($startIndex -lt 0 -or $endIndex -lt 0 -or $endIndex -le $startIndex) {
        throw "Managed instruction markers not found in $Path"
    }
    return $text.Substring($startIndex, $endIndex + $end.Length - $startIndex)
}

function Test-ProjectControlVersionMetadata {
    $lintScript = Join-Path $repoRoot 'tools\agent_system_lint.py'
    $probeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MALTS-version-metadata-' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Force -Path $probeRoot | Out-Null
        $maltsRoot = Join-Path $probeRoot 'malts'
        New-Item -ItemType Directory -Force -Path $maltsRoot | Out-Null
        Set-Content -LiteralPath (Join-Path $maltsRoot 'VERSION') -Value '0.1.8' -Encoding UTF8
        $template = Get-Content -LiteralPath (Join-Path $repoRoot 'runtime\EN\templates\PROJECT_CONTROL.template.en.md') -Raw -Encoding UTF8
        $projectControl = Join-Path $probeRoot 'PROJECT_CONTROL.md'

        $staleText = $template.Replace('<MALTS_VERSION>', 'MALTS 0.1.7')
        Set-Content -LiteralPath $projectControl -Value $staleText -Encoding UTF8
        $staleOutput = & python $lintScript check-project-control --project-control $projectControl --malts-root $maltsRoot 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -or $staleOutput -notmatch 'does not match active VERSION') {
            Add-Failure "ProjectControlVersionMetadata: stale current version was not rejected.`n$staleOutput"
        }

        $freshText = $template.Replace('<MALTS_VERSION>', 'MALTS 0.1.8')
        Set-Content -LiteralPath $projectControl -Value $freshText -Encoding UTF8
        $freshOutput = & python $lintScript check-project-control --project-control $projectControl --malts-root $maltsRoot 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "ProjectControlVersionMetadata: active version was rejected.`n$freshOutput"
        }
    } finally {
        if (Test-Path -LiteralPath $probeRoot) {
            Remove-Item -LiteralPath $probeRoot -Recurse -Force
        }
    }
}

function Test-ManagedInstructionSync {
    $lintScript = Join-Path $repoRoot 'tools\agent_system_lint.py'
    $probeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MALTS-instruction-sync-' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Force -Path $probeRoot | Out-Null
        $source = Join-Path $repoRoot 'adapters\codex\AGENTS.example.md'
        $target = Join-Path $probeRoot 'AGENTS.md'
        $block = Get-ManagedInstructionBlock -Path $source
        Set-Content -LiteralPath $target -Value ("# User-owned prefix`n`n$block`n`n## User-owned tail`n") -Encoding UTF8
        $passOutput = & python $lintScript check-managed-instruction-sync --malts-root $repoRoot --install-root $probeRoot --tool Codex 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Add-Failure "ManagedInstructionSync: synchronized managed block with user-owned text was rejected.`n$passOutput"
        }

        $stale = $block.Replace('MALTS version metadata', 'MALTS stale metadata')
        Set-Content -LiteralPath $target -Value ("# User-owned prefix`n`n$stale`n") -Encoding UTF8
        $failOutput = & python $lintScript check-managed-instruction-sync --malts-root $repoRoot --install-root $probeRoot --tool Codex 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -or $failOutput -notmatch 'not synchronized') {
            Add-Failure "ManagedInstructionSync: stale managed block was not rejected.`n$failOutput"
        }
    } finally {
        if (Test-Path -LiteralPath $probeRoot) {
            Remove-Item -LiteralPath $probeRoot -Recurse -Force
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
if ($Check -in @('All', 'ProjectControlVersionMetadata')) {
    Test-ProjectControlVersionMetadata
}
if ($Check -in @('All', 'ManagedInstructionSync')) {
    Test-ManagedInstructionSync
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
