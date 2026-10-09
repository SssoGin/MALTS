# Install MALTS

Install MALTS into the Agent tools you choose. One shared core supplies project work, continuity, verification and experience workflows; each tool receives its own native entry. Current version: **2.0.0**. Installation is review-first and does not call a model, install the Host application or adopt existing projects.

## Prerequisites

- Windows with Python 3.11+ and PowerShell; PowerShell 7 is recommended. Current protected v2 content uses Windows current-user DPAPI.
- At least one installed Host: **Codex, Claude Code, OpenCode or DeepSeek Harness**.
- A reviewed public repository checkout, or an explicitly verified offline package.
- A lifecycle root outside every selected tool configuration root; a new plan path outside the distribution tree.

The lifecycle root stores generations, registry, plans and transaction recovery. Tool roots contain native projections and `MALTS_BOOT.md`, not another copy of the implementation. Choose actual Host configuration roots; the examples below use generic current-user defaults and disclose no maintainer machine paths.

The Host must already be usable on its own. MALTS adds workflows and state/recovery integration; it does not configure a provider account or purchase model access. For evidence protected with current-user DPAPI, keep the relevant Windows user identity and recovery conditions available; copying encrypted state to another account is not sufficient restoration.

Use short, explicit roots with no ambiguous links/protected overlaps. Lifecycle planning checks supported path bounds before mutation. Long generated paths can fail even when a repository itself opens normally, so shorten the intended lifecycle/tool root instead of bypassing checks.

## Repository Installation (Primary)

Use a reviewed checkout of the [public repository](https://github.com/SssoGin/MALTS). Check the actual remote/ref and confirm `MALTS_RELEASE.json` and `VERSION` both identify 2.0.0. A documentation revision on `main` can retain the same version while having its own exact source-tree identity. The installer checks the actual selected tree; do not add business files or caches inside it.

| Host | Entry | Scope |
|---|---|---|
| Codex | `Install-MALTS.ps1 -Tool Codex` | Selected Codex root |
| Claude Code | `Install-MALTS.ps1 -Tool ClaudeCode` | Selected Claude Code root |
| OpenCode | `Install-MALTS.ps1 -Tool OpenCode` | Selected OpenCode root |
| DeepSeek Harness | `Install-MALTS.ps1 -Tool DeepSeekHarness` | Selected Harness root, shared default lifecycle |

Alternative first-installation plans:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool ClaudeCode
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool OpenCode
```

These are alternative plan examples; execute only your selected plan. `-Tool Codex,ClaudeCode` chooses those two. **`AllIncluded` selects Codex, Claude Code, OpenCode and DeepSeek Harness.** Explicit paths use `-LifecycleRoot`, matching `-ToolRootCodex`, `-ToolRootClaudeCode` or `-ToolRootOpenCode`/`-ToolRootDeepSeekHarness`, and `-PlanPath`.

### DeepSeek Harness Installation

Harness uses the same installation entry and default shared lifecycle as the other Hosts. Choose only the Hosts you need. For a fresh Harness-only installation, create the plan with:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool DeepSeekHarness
```

For a fresh shared four-Host installation, use `-Tool AllIncluded`. `-ToolRootDeepSeekHarness` specifies the actual Harness configuration root; `ToolRootDeepSeekDesktop` remains an alias for existing callers. The default root is `~/.dsh`; the shared installation root is `~/.agent-system/lifecycle`. Accounts, sessions and model settings remain owned by each Host.

An existing three-Host installation cannot become a four-Host installation through a normal update or by changing Boot manually. If Harness is already installed separately, align both exact installed source identities and use the reviewed consolidation procedure in [Lifecycle](LIFECYCLE.md#consolidating-existing-installations). If it is not installed, choose a reviewed fresh installation strategy that preserves existing user content; the normal updater keeps its fixed registered Host set.

The Install command saves a plan and returns its path/hash; it does not activate the plan. Review ownership, personal-content merges, preimages and selected roots, then use the [Review And Execute](#review-and-execute) step. This installs MALTS integration; the Harness application, accounts and models are managed separately.

Each selected Host receives its own Boot and native integration while sharing one verified active generation. `AllIncluded` selects all four; choosing one Host does not implicitly select the others. Explicitly separate lifecycle roots remain supported when independent deployments are required.

Keep plan files outside the source repository and examine the actual selected roots in the plan.

## Review And Execute

The ordinary Install command creates a plan and reports its exact path/hash. Review selected destinations, source identity, ownership, personal-content merges, recoverable preimages and postchecks. For the selected Hosts, use the actual output values:

```powershell
.\scripts\Install-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

Source, target or plan drift rejects execution. Identical installed content may return `NO_OP`. Different bytes with the same version use a reviewed lifecycle `finalize` transaction with preserved snapshots; do not overwrite the active generation or invent another version. See [Lifecycle](LIFECYCLE.md).

| Observed result | Meaning | Next step |
|---|---|---|
| Plan/hash returned | Reviewable preparation exists | Review exact source, roots and merge/recovery decisions |
| NO_OP | Exact intended installation is already present | Verify discovery/loading instead of forcing a rewrite |
| Successful execution | Planned transaction reached its checked result | Read back registry/Boot/projections and native loading |
| Drift/conflict rejection | A reviewed precondition no longer matches | Preserve the scene and review a new plan/source decision |
| Interrupted transaction | Effect/activation may be incomplete | Inspect/recover the original operation |

Do not replace a meaningful failure with a manual file copy or a success label. Installation and project adoption remain separate; an old project can still require explicit migration after the new runtime is installed.

## Optional Offline Archive

The current Release attachment is `MALTS-2.0.0.zip`. A same-version reissue has its own qualified package, source commit and SHA-256 in the Release notes. Verify the exact downloaded revision before offline installation. GitHub-generated source archives follow the current version tag. The current tag, qualified repository and MALTS-uploaded package should identify the same source revision, although archive layouts differ.

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.0.0.zip -ExtractOutput '<new-extraction-root>' -Apply
```

Obtain the verifier from the matching reviewed source. Run the extracted payload's lifecycle entry with `-ReleaseRoot '<extracted-package-root>'`, then the same plan/hash sequence. Harness uses the same lifecycle entry with ReleaseRoot and every Host registered to that installation. Never copy a payload into an active generation. See [Release Archive](RELEASE_ARTIFACT.md).

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

## Optional Cleanup Of Old Generations

Installation and ordinary updates retain earlier generations. To remove an unused `retiring` generation, use the explicit Python CLI retirement workflow in [Lifecycle](LIFECYCLE.md#retiring-unused-generations). It verifies the exact inactive target and approved recycler before removing its registry record; the active version and project state are preserved. It does not empty the Recycle Bin or fall back to permanent deletion.

旧安装代际的清理是独立的显式操作，不随更新自动执行。操作步骤及失败恢复见[生命周期说明](LIFECYCLE.md#清理不再使用的安装代际)；不能直接删除已注册的目录来代替退役流程。
