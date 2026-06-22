[CmdletBinding()]
param(
    [ValidateSet('All', 'SharedRootIsolation', 'MergeSafePreservation', 'NoUpdateNoInstall', 'ManagedStaleCleanup', 'InstructionManagedMerge', 'PublicConsistency')]
    [string] $Check = 'All'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$installScript = Join-Path $PSScriptRoot 'Install-MALTS.ps1'
$updateScript = Join-Path $PSScriptRoot 'Update-MALTS.ps1'
$failures = [System.Collections.Generic.List[string]]::new()
$tempRoots = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([string] $Message)
    $failures.Add($Message)
}

function New-AuditRoot {
    param([string] $Label)
    $path = Join-Path ([System.IO.Path]::GetTempPath()) ("MALTS-update-test-$Label-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $path | Out-Null
    $tempRoots.Add($path)
    return $path
}

function Invoke-ChildPowerShell {
    param([string] $Script, [string[]] $Arguments)
    $savedErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $Script @Arguments 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
        return [pscustomobject]@{
            ExitCode = $exitCode
            Output = $output
        }
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
}

function Test-SharedRootIsolation {
    $root = New-AuditRoot 'shared-root'
    $profile = Join-Path $root 'profile'
    $target = Join-Path $root 'tool-target'
    $expectedShared = [System.IO.Path]::GetFullPath((Join-Path $profile '.malts'))
    $forbiddenShared = [System.IO.Path]::GetFullPath((Join-Path $target 'MALTS_ROOT'))
    $savedUserProfile = $env:USERPROFILE

    try {
        $env:USERPROFILE = $profile
        $result = Invoke-ChildPowerShell -Script $installScript -Arguments @('-Tool', 'Codex', '-TargetRoot', $target)
    } finally {
        $env:USERPROFILE = $savedUserProfile
    }

    if ($result.ExitCode -ne 0) {
        Add-Failure "SharedRootIsolation: installer dry-run failed.`n$($result.Output)"
        return
    }
    if ($result.Output -notmatch [regex]::Escape("Shared MALTS_ROOT: $expectedShared")) {
        Add-Failure "SharedRootIsolation: expected default shared root $expectedShared."
    }
    if ($result.Output -match [regex]::Escape("Shared MALTS_ROOT: $forbiddenShared")) {
        Add-Failure "SharedRootIsolation: full MALTS root is nested below the tool target."
    }
}

function Initialize-TemporaryInstall {
    param([string] $Root)
    $targets = Join-Path $Root 'targets'
    $shared = Join-Path $Root 'shared'
    $result = Invoke-ChildPowerShell -Script $installScript -Arguments @(
        '-Tool', 'AllIncluded',
        '-TargetRoot', $targets,
        '-SharedRoot', $shared,
        '-Apply'
    )
    if ($result.ExitCode -ne 0) {
        Add-Failure "Temporary install failed.`n$($result.Output)"
        return $null
    }
    return [pscustomobject]@{ Targets = $targets; Shared = $shared }
}

function Test-MergeSafePreservation {
    $root = New-AuditRoot 'merge-safe'
    $install = Initialize-TemporaryInstall -Root $root
    if (-not $install) { return }

    $sentinels = @{
        (Join-Path $install.Targets 'Codex\config.toml') = '# USER-CODEX-CONFIG'
        (Join-Path $install.Targets 'ClaudeCode\agents\planner.md') = '# USER-CLAUDE-PLANNER'
        (Join-Path $install.Targets 'OpenCode\opencode.json') = '{"user":"opencode-config"}'
    }
    foreach ($entry in $sentinels.GetEnumerator()) {
        Set-Content -LiteralPath $entry.Key -Value $entry.Value -Encoding UTF8
    }

    $result = Invoke-ChildPowerShell -Script $updateScript -Arguments @(
        '-Mode', 'InstallOnly',
        '-Tool', 'AllIncluded',
        '-Strategy', 'MergeSafe',
        '-RepoRoot', $repoRoot,
        '-TargetRoot', $install.Targets,
        '-SharedRoot', $install.Shared,
        '-Apply'
    )
    if ($result.ExitCode -ne 0) {
        Add-Failure "MergeSafePreservation: update failed.`n$($result.Output)"
        return
    }

    foreach ($entry in $sentinels.GetEnumerator()) {
        $actual = (Get-Content -LiteralPath $entry.Key -Raw -Encoding UTF8).Trim()
        if ($actual -ne $entry.Value) {
            Add-Failure "MergeSafePreservation: user-editable file was overwritten: $($entry.Key)"
        }
    }
}

function Test-NoUpdateNoInstall {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Add-Failure 'NoUpdateNoInstall: git is unavailable.'
        return
    }

    $root = New-AuditRoot 'no-update'
    $remote = Join-Path $root 'remote.git'
    $work = Join-Path $root 'work'
    & git init --bare $remote | Out-Null
    & git init $work | Out-Null
    & git -C $work config user.email 'malts-test@example.invalid'
    & git -C $work config user.name 'MALTS Test'
    Set-Content -LiteralPath (Join-Path $work 'README.md') -Value '# test' -Encoding UTF8
    & git -C $work add README.md
    & git -C $work commit -m 'test baseline' | Out-Null
    & git -C $work branch -M main
    & git -C $work remote add origin $remote
    & git -C $work push -u origin main | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Add-Failure 'NoUpdateNoInstall: failed to prepare local git remote.'
        return
    }

    $result = Invoke-ChildPowerShell -Script $updateScript -Arguments @(
        '-Mode', 'PullAndInstall',
        '-Tool', 'Codex',
        '-RepoRoot', $work,
        '-Apply'
    )
    if ($result.ExitCode -ne 0) {
        Add-Failure "NoUpdateNoInstall: no-update run failed.`n$($result.Output)"
        return
    }
    if ($result.Output -notmatch 'Already up to date') {
        Add-Failure 'NoUpdateNoInstall: no-update condition was not detected.'
    }
    if ($result.Output -match 'Invoking installer|MALTS install') {
        Add-Failure 'NoUpdateNoInstall: installer still ran without a remote update.'
    }
}

function Add-ManifestProbe {
    param(
        [string] $ManifestPath,
        [string] $RelativePath,
        [string] $Category,
        [string] $InstalledSha256
    )
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $files = @($manifest.Files)
    $files += [pscustomobject]@{
        Path = $RelativePath
        Category = $Category
        InstalledSha256 = $InstalledSha256
    }
    $manifest.Files = $files
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
}

function Test-ManagedStaleCleanup {
    $root = New-AuditRoot 'stale-cleanup'
    $install = Initialize-TemporaryInstall -Root $root
    if (-not $install) { return }

    $manifestPath = Join-Path $install.Shared '.malts-managed-files.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        Add-Failure "ManagedStaleCleanup: install manifest missing: $manifestPath"
        return
    }

    $unchanged = Join-Path $install.Shared 'docs\obsolete-unchanged.md'
    $modified = Join-Path $install.Shared 'docs\obsolete-modified.md'
    Set-Content -LiteralPath $unchanged -Value 'managed-content' -Encoding UTF8
    Set-Content -LiteralPath $modified -Value 'managed-content' -Encoding UTF8
    $managedHash = (Get-FileHash -LiteralPath $unchanged -Algorithm SHA256).Hash
    Set-Content -LiteralPath $modified -Value 'user-modified-content' -Encoding UTF8

    Add-ManifestProbe -ManifestPath $manifestPath -RelativePath 'docs/obsolete-unchanged.md' -Category 'Shared' -InstalledSha256 $managedHash
    Add-ManifestProbe -ManifestPath $manifestPath -RelativePath 'docs/obsolete-modified.md' -Category 'Shared' -InstalledSha256 $managedHash

    $result = Invoke-ChildPowerShell -Script $installScript -Arguments @(
        '-Tool', 'AllIncluded',
        '-TargetRoot', $install.Targets,
        '-SharedRoot', $install.Shared,
        '-MergeSafe',
        '-SkipInstructionTemplate',
        '-Apply'
    )
    if ($result.ExitCode -ne 0) {
        Add-Failure "ManagedStaleCleanup: reinstall failed.`n$($result.Output)"
        return
    }
    if (Test-Path -LiteralPath $unchanged) {
        Add-Failure 'ManagedStaleCleanup: unchanged stale managed file was not removed.'
    }
    if (-not (Test-Path -LiteralPath $modified)) {
        Add-Failure 'ManagedStaleCleanup: modified stale file was removed.'
    }
}

function Test-InstructionManagedMerge {
    $root = New-AuditRoot 'instruction-merge'

    $preflightTarget = Join-Path $root 'preflight-target'
    $preflightShared = Join-Path $root 'preflight-shared'
    New-Item -ItemType Directory -Force -Path $preflightTarget | Out-Null
    $preflightInstruction = Join-Path $preflightTarget 'AGENTS.md'
    Set-Content -LiteralPath $preflightInstruction -Value 'USER-PREFLIGHT-INSTRUCTION' -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $preflightTarget 'config.toml') -Value 'USER-PREFLIGHT-CONFIG' -Encoding UTF8
    $preflightHash = (Get-FileHash -LiteralPath $preflightInstruction -Algorithm SHA256).Hash
    $preflight = Invoke-ChildPowerShell -Script $installScript -Arguments @(
        '-Tool', 'Codex', '-TargetRoot', $preflightTarget, '-SharedRoot', $preflightShared, '-Apply'
    )
    if ($preflight.ExitCode -eq 0) {
        Add-Failure 'InstructionManagedMerge: existing support conflict did not stop the unqualified install.'
    }
    if ((Get-FileHash -LiteralPath $preflightInstruction -Algorithm SHA256).Hash -ne $preflightHash) {
        Add-Failure 'InstructionManagedMerge: instruction changed before an existing support conflict was reported.'
    }

    $targets = Join-Path $root 'targets'
    $shared = Join-Path $root 'shared'
    $codexTarget = Join-Path $targets 'Codex'
    $claudeTarget = Join-Path $targets 'ClaudeCode'
    $openCodeTarget = Join-Path $targets 'OpenCode'
    foreach ($path in @($codexTarget, $claudeTarget, $openCodeTarget)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
    }

    $codexPath = Join-Path $codexTarget 'AGENTS.md'
    $claudePath = Join-Path $claudeTarget 'CLAUDE.md'
    $openCodePath = Join-Path $openCodeTarget 'AGENTS.md'
    $utf8Bom = [System.Text.UTF8Encoding]::new($true)
    [System.IO.File]::WriteAllText($codexPath, "# User Rules`r`n`r`nUSER-CODEX-PREFIX`r`n", $utf8Bom)
    Set-Content -LiteralPath $claudePath -Encoding UTF8 -Value @'
# User Rules

USER-CLAUDE-PREFIX

# Global Agent System Discovery

STALE-LEGACY-MALTS

## User Tail

USER-CLAUDE-SUFFIX
'@
    Set-Content -LiteralPath $openCodePath -Encoding UTF8 -Value "# User Rules`n`nUSER-OPENCODE-PREFIX`n"

    $mergeArgs = @(
        '-Tool', 'AllIncluded',
        '-TargetRoot', $targets,
        '-SharedRoot', $shared,
        '-MergeSafe',
        '-InstructionMode', 'ManagedMerge',
        '-Apply'
    )
    $result = Invoke-ChildPowerShell -Script $installScript -Arguments $mergeArgs
    if ($result.ExitCode -ne 0) {
        Add-Failure "InstructionManagedMerge: initial managed merge failed.`n$($result.Output)"
        return
    }

    $startMarker = '<!-- MALTS:BEGIN managed instruction -->'
    $endMarker = '<!-- MALTS:END managed instruction -->'
    foreach ($entry in @(
        @{ Path = $codexPath; Prefix = 'USER-CODEX-PREFIX' },
        @{ Path = $claudePath; Prefix = 'USER-CLAUDE-PREFIX' },
        @{ Path = $openCodePath; Prefix = 'USER-OPENCODE-PREFIX' }
    )) {
        $text = Get-Content -LiteralPath $entry.Path -Raw -Encoding UTF8
        if (-not $text.Contains($entry.Prefix)) {
            Add-Failure "InstructionManagedMerge: user prefix was not preserved: $($entry.Path)"
        }
        if (([regex]::Matches($text, [regex]::Escape($startMarker))).Count -ne 1 -or
            ([regex]::Matches($text, [regex]::Escape($endMarker))).Count -ne 1) {
            Add-Failure "InstructionManagedMerge: expected exactly one managed marker pair: $($entry.Path)"
        }
    }

    $claudeText = Get-Content -LiteralPath $claudePath -Raw -Encoding UTF8
    if ($claudeText.Contains('STALE-LEGACY-MALTS')) {
        Add-Failure 'InstructionManagedMerge: legacy unmarked MALTS block was not replaced.'
    }
    if (-not $claudeText.Contains('USER-CLAUDE-SUFFIX')) {
        Add-Failure 'InstructionManagedMerge: content after the legacy MALTS block was not preserved.'
    }

    $codexBytes = [System.IO.File]::ReadAllBytes($codexPath)
    if ($codexBytes.Length -lt 3 -or $codexBytes[0] -ne 0xEF -or $codexBytes[1] -ne 0xBB -or $codexBytes[2] -ne 0xBF) {
        Add-Failure 'InstructionManagedMerge: UTF-8 BOM was not preserved.'
    }
    $codexRaw = [System.IO.File]::ReadAllText($codexPath, [System.Text.Encoding]::UTF8)
    if ($codexRaw -match '(?<!\r)\n') {
        Add-Failure 'InstructionManagedMerge: CRLF newline style was not preserved.'
    }

    $beforeSecondRun = @{}
    foreach ($path in @($codexPath, $claudePath, $openCodePath)) {
        $beforeSecondRun[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    $second = Invoke-ChildPowerShell -Script $installScript -Arguments $mergeArgs
    if ($second.ExitCode -ne 0) {
        Add-Failure "InstructionManagedMerge: repeated merge failed.`n$($second.Output)"
        return
    }
    foreach ($path in @($codexPath, $claudePath, $openCodePath)) {
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $beforeSecondRun[$path]) {
            Add-Failure "InstructionManagedMerge: repeated merge was not idempotent: $path"
        }
    }

    $beforeSkip = (Get-FileHash -LiteralPath $codexPath -Algorithm SHA256).Hash
    $skip = Invoke-ChildPowerShell -Script $installScript -Arguments @(
        '-Tool', 'Codex', '-TargetRoot', $codexTarget, '-SharedRoot', $shared,
        '-MergeSafe', '-InstructionMode', 'Skip', '-Apply'
    )
    if ($skip.ExitCode -ne 0 -or (Get-FileHash -LiteralPath $codexPath -Algorithm SHA256).Hash -ne $beforeSkip) {
        Add-Failure "InstructionManagedMerge: Skip did not preserve the instruction file.`n$($skip.Output)"
    }

    Set-Content -LiteralPath $codexPath -Value 'USER-REPLACE-PROBE' -Encoding UTF8
    $replace = Invoke-ChildPowerShell -Script $installScript -Arguments @(
        '-Tool', 'Codex', '-TargetRoot', $codexTarget, '-SharedRoot', $shared,
        '-Overwrite', '-InstructionMode', 'Replace', '-Apply'
    )
    $sourcePath = Join-Path $repoRoot 'adapters\codex\AGENTS.example.md'
    if ($replace.ExitCode -ne 0 -or (Get-FileHash -LiteralPath $codexPath -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash) {
        Add-Failure "InstructionManagedMerge: explicit Replace did not copy the complete source instruction file.`n$($replace.Output)"
    }

    Set-Content -LiteralPath $codexPath -Value "USER-AMBIGUOUS`n$startMarker`nBROKEN" -Encoding UTF8
    $beforeAmbiguous = (Get-FileHash -LiteralPath $codexPath -Algorithm SHA256).Hash
    $ambiguous = Invoke-ChildPowerShell -Script $installScript -Arguments @(
        '-Tool', 'Codex', '-TargetRoot', $codexTarget, '-SharedRoot', $shared,
        '-MergeSafe', '-InstructionMode', 'ManagedMerge', '-Apply'
    )
    if ($ambiguous.ExitCode -eq 0) {
        Add-Failure 'InstructionManagedMerge: incomplete marker set did not stop the install.'
    }
    if ((Get-FileHash -LiteralPath $codexPath -Algorithm SHA256).Hash -ne $beforeAmbiguous) {
        Add-Failure 'InstructionManagedMerge: ambiguous instruction target changed before failure.'
    }
}

function Test-PublicConsistency {
    $forbidden = @(
        ('Do not install tool-local ' + '`skills/`'),
        ('不要安装工具本地 ' + '`skills/`'),
        ("copies these skills into each supported tool's " + 'local skill directory'),
        ('把这些 skills 复制到各受支持工具的' + '本地 skill 目录')
    )
    foreach ($path in Get-ChildItem -LiteralPath (Join-Path $repoRoot 'docs') -Recurse -File -Filter '*.md') {
        $text = Get-Content -LiteralPath $path.FullName -Raw -Encoding UTF8
        foreach ($token in $forbidden) {
            if ($text.Contains($token)) {
                Add-Failure "PublicConsistency: legacy install wording remains in $($path.FullName): $token"
            }
        }
    }

    foreach ($relative in @(
        'adapters\codex\AGENTS.example.md',
        'adapters\claude-code\CLAUDE.example.md',
        'adapters\opencode\AGENTS.example.md'
    )) {
        $path = Join-Path $repoRoot $relative
        $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        if ($text -match '<MALTS_ROOT>[/\\]Handoff[/\\]PROJECT_HANDOFF\.md') {
            Add-Failure "PublicConsistency: public adapter references missing local-only handoff path: $relative"
        }
    }
}

try {
    if ($Check -in @('All', 'SharedRootIsolation')) { Test-SharedRootIsolation }
    if ($Check -in @('All', 'MergeSafePreservation')) { Test-MergeSafePreservation }
    if ($Check -in @('All', 'NoUpdateNoInstall')) { Test-NoUpdateNoInstall }
    if ($Check -in @('All', 'ManagedStaleCleanup')) { Test-ManagedStaleCleanup }
    if ($Check -in @('All', 'InstructionManagedMerge')) { Test-InstructionManagedMerge }
    if ($Check -in @('All', 'PublicConsistency')) { Test-PublicConsistency }
} finally {
    foreach ($path in $tempRoots) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
        }
    }
}

if ($failures.Count -gt 0) {
    Write-Host "FAIL: $($failures.Count) update regression assertion(s) failed."
    foreach ($failure in $failures) {
        Write-Host "- $failure"
    }
    exit 1
}

Write-Host "PASS: $Check"
exit 0
