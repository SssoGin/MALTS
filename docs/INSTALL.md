# Install MALTS

MALTS installation is review-first. The first command writes a plan, and no files are changed until you review the plan and supply its exact hash with `-Apply`.

## Prerequisites

- Windows 10 or later
- PowerShell 5.1 or later; PowerShell 7 is recommended
- Python 3.11 or later
- At least one of Codex, Claude Code, or OpenCode
- A lifecycle root outside every selected tool root

The lifecycle root stores installed MALTS versions, registry state, plans, and transaction state. Each selected tool root receives only its adapter files and boot pointer.

## Repository Installation (Primary)

1. Open the repository root.
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
  -RepositoryRoot <REPOSITORY_ROOT> `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -Tool Codex `
  -ToolRootCodex <CODEX_ROOT> `
  -PlanPath <NEW_PLAN_PATH>
```

Supported `-Tool` values are `Codex`, `ClaudeCode`, `OpenCode`, and `AllIncluded`.

The repository is validated as an exact source before the plan is written. Any unexpected file, cache, `.malts` residue, missing identity file, version mismatch, or source-tree hash mismatch stops before installation.

Installed version IDs are semantic: v1.1.0 installs as `malts-v1.1.0`. Reinstalling the same version with identical content reports `NO_OP`; the same version with different content, or an unbound same-name directory, fails before any transaction state is created.

## Review And Execute

The plan contains selected roots, intended version identity, planned changes, user-modification classifications, migration or cleanup actions, rollback, and post-validation checks. Review it before execution.

```powershell
.\scripts\Install-MALTS.ps1 `
  -Apply `
  -PlanPath <REVIEWED_PLAN_PATH> `
  -ExpectedPlanHash <REVIEWED_PLAN_SHA256>
```

Changing the source, roots, or plan invalidates the hash. A missing or mismatched hash fails before installation.

## Optional Offline Archive

The Release page may offer one optional archive named `MALTS-<version>.zip`. It is not required for normal installation and is never downloaded automatically by the installer.

To use it, obtain `scripts/Verify-MALTSBootstrap.ps1` from the same reviewed source or tag, then verify and extract the ZIP:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-MALTSBootstrap.ps1 `
  -ArchivePath .\MALTS-1.1.0.zip `
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

## Verify The Installed Runtime

Run the read-only doctor with the lifecycle root and every selected tool root:

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Doctor `
  -LifecycleRoot <LIFECYCLE_ROOT> `
  -ToolRootCodex <CODEX_ROOT> `
  -ToolRootClaudeCode <CLAUDE_CODE_ROOT> `
  -ToolRootOpenCode <OPENCODE_ROOT>
```

`doctor` reports exact expected and observed locators, severity, core trust, and suggested commands. It is always read-only and does not repair anything. If repair is needed, create a separate `DoctorRepairPlan` review using the exact trusted source, then execute only the reviewed plan hash.

Lifecycle operations also keep bounded audit records (one current binding plus recent success, failure/recovery, and monthly summaries). See [Lifecycle](LIFECYCLE.md).

## First Use

After installation, each selected tool reads its `MALTS_BOOT.md` pointer to resolve the active installed version. Do not copy runtime files into a project manually. Use an installed `malts-*` Skill entry point instead.

Verify the binding with the read-only discovery command. It parses the tool boot and cross-checks the lifecycle registry, active pointer, and `VERSION`; MALTS v1.1.1+ does not use a machine-global recovery boot. Any inconsistency blocks use.

See [Getting Started](GETTING_STARTED.md), [Lifecycle](LIFECYCLE.md), and [Security](SECURITY.md).
