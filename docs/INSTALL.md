# Install MALTS

Install MALTS into the Agent tools you choose. One shared core supplies project work, continuity, verification and experience workflows; each tool receives its own native entry. Current version: **2.0.0**. Installation is review-first and does not call a model, install the Host application or adopt existing projects.

## Prerequisites

- Windows with Python 3.11+ and PowerShell; PowerShell 7 is recommended. Current protected v2 content uses Windows current-user DPAPI.
- At least one installed Host: **Codex, Claude Code, OpenCode or DeepSeek Harness**.
- A reviewed public repository checkout, or an explicitly verified offline package.
- A lifecycle root outside every selected tool configuration root; a new plan path outside the distribution tree.

The lifecycle root stores generations, registry, plans and transaction recovery. Tool roots contain native projections and `MALTS_BOOT.md`, not another copy of the implementation. Choose actual Host configuration roots; the examples below use generic current-user defaults and disclose no maintainer machine paths.

## Repository Installation (Primary)

Use a reviewed checkout of the [public repository](https://github.com/SssoGin/MALTS). Check the actual remote/ref and confirm `MALTS_RELEASE.json` and `VERSION` both identify 2.0.0. A documentation revision on `main` can retain the same version while having its own exact source-tree identity. The installer checks the actual selected tree; do not add business files or caches inside it.

| Host | Entry | Scope |
|---|---|---|
| Codex | `Install-MALTS.ps1 -Tool Codex` | Selected Codex root |
| Claude Code | `Install-MALTS.ps1 -Tool ClaudeCode` | Selected Claude Code root |
| OpenCode | `Install-MALTS.ps1 -Tool OpenCode` | Selected OpenCode root |
| DeepSeek Harness | `Invoke-MALTSLifecycle.ps1 -ToolRootDeepSeekDesktop` | Dedicated Harness lifecycle/root |

For one or several of the first three Hosts:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool ClaudeCode
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool OpenCode
```

These are alternative plan examples; execute only your selected plan. `-Tool Codex,ClaudeCode` chooses those two. **`AllIncluded` includes Codex, Claude Code and OpenCode only.** It does not install Harness. Explicit paths use `-LifecycleRoot`, matching `-ToolRootCodex`, `-ToolRootClaudeCode` or `-ToolRootOpenCode`, and `-PlanPath`.

### DeepSeek Harness Installation

The dedicated lifecycle uses identity `deepseek-harness`. The public parameter `ToolRootDeepSeekDesktop` is retained for compatibility and refers to the current Harness configuration root. Use the actual `.dsh` root and a separate Harness lifecycle; an old Desktop identity/path is not a substitute.

From the repository root, create and save a review plan:

```powershell
$harnessRoot = Join-Path $env:USERPROFILE '.dsh'
$harnessLifecycle = Join-Path $env:USERPROFILE '.agent-system/deepseek-harness-lifecycle'
$planPath = Join-Path $env:TEMP ('malts-harness-plan-' + [guid]::NewGuid().ToString('N') + '.json')
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Plan -Operation install `
  -RepositoryRoot (Get-Location).Path `
  -LifecycleRoot $harnessLifecycle `
  -ToolRootDeepSeekDesktop $harnessRoot `
  -OutPath $planPath -Apply
```

Here `Plan -Apply` **saves the plan file only**; it does not activate an installation. Without `-Apply`, Plan prints a dry-run plan. Review the reported `plan_hash`, source identity, roots, merge classifications and snapshots. Execute it with:

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Execute -PlanPath '<reviewed-plan-path>' `
  -ExpectedPlanHash '<reviewed-plan-sha256>' -Apply
```

The planner selects Harness from `-ToolRootDeepSeekDesktop`; the generic lifecycle's `-Tool deepseek-harness` selector is used by PreviewPlan. Do not pass Harness to Install/Update's three-Host `-Tool` parameter. This installs MALTS integration, not DeepSeek Harness, a model, a key or a provider subscription.

## Review And Execute

The ordinary Install command creates a plan and reports its exact path/hash. Review selected destinations, source identity, ownership, personal-content merges, recoverable preimages and postchecks. For the first three Hosts, use the actual output values:

```powershell
.\scripts\Install-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

Source, target or plan drift rejects execution. Identical installed content may return `NO_OP`. Different bytes with the same version use a reviewed lifecycle `finalize` transaction with preserved snapshots; do not overwrite the active generation or invent another version. See [Lifecycle](LIFECYCLE.md).

## Optional Offline Archive

The Release's optional `MALTS-2.0.0.zip` preserves its original tagged content. Later same-version documentation amendments on `main` do not rewrite that immutable archive. Use the repository for current guides; use the archive when you explicitly need its fixed offline input.

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip -ExtractOutput '<new-extraction-root>' -Apply
```

Obtain the verifier from the matching reviewed source. Run the extracted payload's lifecycle entry with `-ReleaseRoot '<extracted-package-root>'`, then the same plan/hash sequence. Harness uses its dedicated lifecycle entry with ReleaseRoot. Never copy a payload into an active generation. See [Release Archive](RELEASE_ARTIFACT.md).

## Verify The Installed Runtime

Read the selected tool's exact Boot and use its MALTS_ROOT:

```powershell
$runtime = '<MALTS_ROOT-from-tool-boot>'
$toolRoot = '<selected-tool-config-root>'
python -B "$runtime/tools/malts_lifecycle.py" discover --tool-root $toolRoot
python -B "$runtime/tools/malts_v2.py" capabilities
```

Require discovery PASS and matching registry, pointer, identity and VERSION. Capabilities declare interfaces, not effective model behavior. Doctor checks installation trust and drift without repair. For Harness:

```powershell
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Doctor -LifecycleRoot $harnessLifecycle `
  -ToolRootDeepSeekDesktop $harnessRoot
```

For the shared lifecycle, provide all its actual selected tool roots to Doctor. Reload the Host and verify native Skill/MCP discovery; file presence alone is insufficient. Current Harness native evidence is scoped to Windows Desktop 0.2.0-rc.2; CLI/Web and GUI model cancellation have separate limits.

## Verify The Workspace Lifecycle

Installation changes only selected installation/tool roots. It does not migrate or initialize projects. Check an existing workspace with the verified runtime:

```powershell
python -B "$runtime/tools/malts_v2.py" workspace --workspace '<project-workspace>'
```

An adopted result must have a verified binding before current task services are used. A pre-adoption workspace keeps its verified contract until explicit adoption. Do not run legacy initialization against an adopted workspace. See [State Contract](V2_STATE_CONTRACT.md).

## First Use

Use the installed MALTS workflow matching your goal: project setup, long-workspace setup, current tasks, handoff, review or approved collaboration. Ordinary entry creates no unrelated entities. Start with [Getting Started](GETTING_STARTED.md), then [Usage](USAGE.md). For Harness-specific loading and profile limits, see the [adapter guide](../adapters/deepseek-harness/README.md).
