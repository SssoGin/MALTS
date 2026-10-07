# Install MALTS

This is part of the complete MALTS system documentation. Current implementation/version is2.0.0; workflow context is in [System Overview](SYSTEM_OVERVIEW.md) and [Usage](USAGE.md).

## 1. Repository Installation (Primary)

The verified installation path is Windows with Python 3.11+ and PowerShell; PowerShell 7 is recommended. v2 protected content currently uses Windows current-user DPAPI. Select Codex, Claude Code or OpenCode; see the [DeepSeek Harness adapter](../adapters/deepseek-harness/README.md) for its dedicated path. Installation neither calls a model nor migrates projects automatically.

Normally use a reviewed checkout of the [public repository](https://github.com/SssoGin/MALTS). Check remote, commit/tag and `MALTS_RELEASE.json`; its version must match VERSION 2.0.0. The installer verifies exact paths/content. Keep caches and business files outside the distribution directory.

## 2. Plan and execute (review-first)

From the repository root:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```

`-Tool AllIncluded` selects Codex, Claude Code and OpenCode only. For explicit roots, supply `-LifecycleRoot`, matching `-ToolRootCodex`, `-ToolRootClaudeCode`, `-ToolRootOpenCode`, and a new `-PlanPath`. Keep lifecycle root outside tool configuration roots.

The first command only creates a plan and reports its path/SHA-256. Review source, destinations, personal-content merges and recovery preimages, then use the actual reported values:

```powershell
$plan = '<reviewed-plan-path>'
$hash = '<reviewed-plan-sha256>'
.\scripts\Install-MALTS.ps1 -Apply -PlanPath $plan -ExpectedPlanHash $hash
```

Source, target or plan drift rejects execution. Identical installed content may return `NO_OP`. Different content under the same version needs the formal lifecycle consolidation/recovery path, never a manual generation overwrite.

## 3. Verify the entry

Read the selected tool configuration root's `MALTS_BOOT.md`, resolve MALTS_ROOT, then run:

```powershell
$runtime = '<MALTS_ROOT-from-tool-boot>'
$toolRoot = '<selected-tool-config-root>'
python -B "$runtime/tools/malts_lifecycle.py" discover --tool-root $toolRoot
python -B "$runtime/tools/malts_v2.py" capabilities
```

Require discovery PASS and matching registry, active pointer and VERSION. Capabilities declare interfaces, not native behavior. See [Lifecycle](LIFECYCLE.md) for read-only Doctor. Reload/restart the Host and verify actual Skill/MCP discovery instead of file presence alone.

## 4. Optional Offline Archive

For an offline source, use `MALTS-2.0.0.zip` and obtain `scripts/Verify-MALTSBootstrap.ps1` from the same reviewed source:

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip -ExtractOutput '<new-extraction-root>' -Apply
```

Run the extracted payload's installer with `-ReleaseRoot '<extracted-package-root>'` and the same plan/hash sequence. Do not copy payload into an active generation. See [Release Archive](RELEASE_ARTIFACT.md) and [Getting Started](GETTING_STARTED.md).
