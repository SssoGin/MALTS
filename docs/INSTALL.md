# Install MALTS

MALTS installs from a verified public repository by default. Installation is review-first: the first command writes a plan, and no files are changed until the user supplies the exact reviewed plan hash with `-Apply`.

## Prerequisites

- Windows 10 or later
- PowerShell 5.1 or later; PowerShell 7 is recommended
- Python 3.11 or later
- At least one of Codex, Claude Code, or OpenCode
- A lifecycle root outside every selected tool root

The lifecycle root stores immutable MALTS generations, the active-generation registry, plans, and transaction state. Each selected tool root receives only its projection and boot pointer.

## Repository Installation (Primary)

1. Open the public repository root.
2. Read `MALTS_RELEASE.json` and confirm its `version` equals `VERSION`.
3. When Git metadata is present, confirm its `release_tag` matches the checked-out tag.
4. Create a plan.

```powershell
.\scripts\Install-MALTS.ps1 `
  -RepositoryRoot (Get-Location).Path `
  -UseDefaultRoots `
  -Tool Codex
```

For explicit paths:

```powershell
.\scripts\Install-MALTS.ps1 `
  -RepositoryRoot <PUBLIC_REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_PLAN_PATH>
```

Supported `-Tool` values are `Codex`, `ClaudeCode`, `OpenCode`, and `AllIncluded`.

The repository is validated as an exact user source before the plan is written. Any unexpected file, cache, `.malts` residue, missing identity file, version mismatch, or source-tree hash mismatch stops before installation.

## Review and Execute

The plan contains selected roots, intended generation identity, planned changes, user-modification classifications, migration or cleanup actions, rollback, and post-validation checks. Review it before execution.

```powershell
.\scripts\Install-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_PLAN_SHA256>
```

Changing the source, roots, or plan invalidates the hash. A missing or mismatched hash fails before installation.

## Optional Offline Archive

The Release page may offer one optional archive named `MALTS-<version>.zip`. It is not required for repository installation and is never downloaded automatically by the installer.

To use it, obtain `scripts/Verify-MALTSBootstrap.ps1` from the same reviewed public source/tag, then verify and extract the ZIP:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.0.0.zip `
  -ExtractOutput <EXTRACTED_RELEASE_ROOT> `
  -Apply
```

Then create the normal review plan from the extracted package:

```powershell
<EXTRACTED_RELEASE_ROOT>\lifecycle_artifact\payload\scripts\Install-MALTS.ps1 `
  -ReleaseRoot <EXTRACTED_RELEASE_ROOT> `
  -UseDefaultRoots `
  -Tool Codex
```

The bootstrap verifier checks deterministic ZIP structure, safe paths, and the extracted immutable package before it writes the final extraction.

## First Use

After installation, each selected tool reads its `MALTS_BOOT.md` pointer to resolve the active immutable generation. Do not copy runtime files into a project manually. Use an installed `malts-*` Skill entry point instead.

See [Getting Started](GETTING_STARTED.md), [Lifecycle](LIFECYCLE.md), and [Security](SECURITY.md).
