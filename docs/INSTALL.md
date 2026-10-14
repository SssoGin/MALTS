# Install MALTS

Install MALTS into the Agent tools you choose. One shared core supplies project work, continuity, verification and experience workflows; each tool receives its own native entry. Current version: **2.1.0**. Installation is review-first and does not call a model, install the Host application or adopt existing projects.

## Prerequisites

- Windows with Python 3.11+ and PowerShell; PowerShell 7 is recommended. Current protected v2 content uses Windows current-user DPAPI.
- At least one installed Host: **Codex, Claude Code, OpenCode or DeepSeek Harness**.
- A reviewed public repository checkout, or an explicitly verified offline package.
- A lifecycle root outside every selected tool configuration root; a new plan path outside the distribution tree.

The lifecycle root stores generations, registry, plans and transaction recovery. Tool roots contain native projections and `MALTS_BOOT.md`, not another copy of the implementation. Choose actual Host configuration roots; the examples below use generic current-user defaults and disclose no maintainer machine paths.

The Host must already be usable on its own. MALTS adds workflows and state/recovery integration; it does not configure a provider account or purchase model access. For evidence protected with current-user DPAPI, keep the relevant Windows user identity and recovery conditions available; copying encrypted state to another account is not sufficient restoration.

Use short, explicit roots with no ambiguous links/protected overlaps. Lifecycle planning checks supported path bounds before mutation. Long generated paths can fail even when a repository itself opens normally, so shorten the intended lifecycle/tool root instead of bypassing checks.

## Repository Installation (Primary)

Use a reviewed checkout of the [public repository](https://github.com/SssoGin/MALTS). Check the actual remote/ref and confirm `MALTS_RELEASE.json` and `VERSION` both identify 2.1.0. A documentation revision on `main` can retain the same version while having its own exact source-tree identity. The installer checks the actual selected tree; do not add business files or caches inside it.

| Host | Entry | Scope |
|---|---|---|
| Codex | `Install-MALTS.ps1 -Tool Codex` | Selected Codex root |
| Claude Code | `Install-MALTS.ps1 -Tool ClaudeCode` | Selected Claude Code root |
| OpenCode | `Install-MALTS.ps1 -Tool OpenCode` | Selected OpenCode root |
| DeepSeek Harness | `Install-MALTS.ps1 -Tool DeepSeekHarness` | Selected Harness root, shared default lifecycle |

Shared four-Host installation plan:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

The shared formal installation uses one plan. **`AllIncluded` selects Codex, Claude Code, OpenCode and DeepSeek Harness.** Explicit paths use `-LifecycleRoot`, matching `-ToolRootCodex`, `-ToolRootClaudeCode` or `-ToolRootOpenCode`/`-ToolRootDeepSeekHarness`, and `-PlanPath`.

### DeepSeek Harness Installation

Harness shares the formal installation with Codex, Claude Code and OpenCode and uses the same entry. Create a complete four-Host plan with:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool AllIncluded
```

The default shared lifecycle root is `~/.agent-system/lifecycle`; the Harness configuration root is `~/.dsh`. Use `-ToolRootDeepSeekHarness` for an explicit Host path. Accounts, sessions and model settings stay with each Host rather than being copied or merged into the MALTS installation.

The installer saves the plan and reports its path/hash. Review the source, actual four-Host roots, personal-content merges and recovery preimages before the execution step below. Use the update workflow for an existing formal installation; manually editing Boot, registration or an active generation is not installation. This workflow installs MALTS integration; the Harness application and models remain managed by their own installer.

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

The current Release attachment is `MALTS-2.1.0.zip`. A same-version reissue has its own qualified package, source commit and SHA-256 in the Release notes. Verify the exact downloaded revision before offline installation. GitHub-generated source archives follow the current version tag. The current tag, qualified repository and MALTS-uploaded package should identify the same source revision, although archive layouts differ.

```powershell
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.1.0.zip
.\scripts\Verify-MALTSBootstrap.ps1 -ArchivePath .\MALTS-2.1.0.zip -ExtractOutput '<new-extraction-root>' -Apply
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

Require discovery PASS with matching registration, active pointer, generation identity and VERSION. Doctor checks installation trust and drift without applying repairs. Supply all four actual Host roots for the shared installation:

```powershell
$shared = Join-Path $env:USERPROFILE '.agent-system/lifecycle'
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Doctor -LifecycleRoot $shared `
  -ToolRootCodex (Join-Path $env:USERPROFILE '.codex') `
  -ToolRootClaudeCode (Join-Path $env:USERPROFILE '.claude') `
  -ToolRootOpenCode (Join-Path $env:USERPROFILE '.config/opencode') `
  -ToolRootDeepSeekHarness (Join-Path $env:USERPROFILE '.dsh')
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

## Workspace Management Data and Migration

Ordinary new workspaces use `workspace-init` to place task state, managed evidence and recovery data under an owned `.malts` directory; explicit external layouts remain supported. Installation updates do not move existing projects. Healthy adopted stores can relocate through a read-only plan, backup/restore, current-effect review and formal forward switch. The new epoch does not restore old Grants/acceptance or activate a Phase automatically. Retain old stores, external historical references and source capsules according to their actual dependencies. See [workspace management and store relocation](MANAGEMENT_AND_RELOCATION.md) for steps and limits.

## Installation Integrity and Recovery Verification

Deep entry verification separates the exact installed user payload from reproducible interpreter caches. Source, metadata and hash chains must still match; a current-interpreter cache is accepted only when reproduced from verified source. Other interpreter caches, corrupt caches, extra files and source changes fail closed without deleting caches or editing manifests. CLI deep entry and MCP malts_entry_status share safe cause codes. Recovery results distinguish registered effects from external writer coverage; compatible format, business acceptance, isolated recovery and writer quiescence are separate conclusions. See [management and recovery verification](MANAGEMENT_AND_RELOCATION.md) for staged preservation, UTF-8 plans and isolated recovery commands.

CPython marshal serialization can vary in immutable-object sharing and reference numbering after modules are imported. Cache verification compares a bounded structural digest against freshly compiled verified source, including every code field, constant, bytecode, filename and line/exception table. It checks header/source metadata and the exact observed cache-file hash, rejects unsupported, cyclic, mutable or trailing data, and never loads or executes cache code. The returned derived-cache inventory is separate from the unchanged user-purity identity; it is current local verification, not an added package trust source. The structure profiles cover CPython 3.11–3.13; other interpreter cache profiles fail closed.

## Checking Host MCP Configuration

When the planning interpreter lacks a YAML parser, the plan seals the exact configuration bytes and desired managed entry with `yaml_preparation_deferred=true`. After dependency setup and before activation, the installer parses the structure, checks ownership/conflicts and binds the exact after-image to the original plan. Failure at this step stops before Host configuration or installation activation.

MCP is a required part of the installation for every selected Host. The same reviewed plan includes its dependency environment, fixed launcher, managed `malts` entry, exact configuration preimages and a real stdio connection check. Success requires `mcp_installation.status=READY`; file deployment alone is insufficient. There is no separate enable-MCP switch.

The lifecycle-owned environment is under `runtime/mcp/env-<requirements-digest>`, outside immutable generations. The launcher loads the generation verified through that Host’s Boot, registry and pointer. Codex uses `config.toml`; Claude Code uses the sibling `.claude.json`; OpenCode uses its existing `opencode.json` and/or `opencode.jsonc`; when both are present, both receive the same owned entry for their merged configuration; Harness uses each existing profile’s `cordis.patch.yml`, or a new `default` profile if none exists. Other settings and MCP servers remain intact. A conflicting unowned `malts` entry or edits to a managed entry stop the affected operation instead of being overwritten.

First installation needs access to the pinned Python packages. The MALTS ZIP does not bundle their wheels. An offline installation therefore needs an already verified managed environment or an available local package source; offline dependency failure leaves installation incomplete. The installer records installed dependency versions. It does not change PATH or install packages into another application’s environment.

Reload the Host if it does not reload configuration automatically, then call `malts_installation`. It should report `MCP_READY` and version `2.1.0`. A cold connection check establishes a newly started server; it cannot switch an already running Host process. For existing project-specific endpoints and detailed diagnostics, see [MCP configuration](MCP_CONFIGURATION.md).

### Project MCP Entries And Upgrade Checks

Ordinary read-only projects inherit the global standard entry. Dedicated bindings, interpreters, environments or permissions can retain a project endpoint. Select `--workspace` / `--host-config` for update, Doctor and retirement checks; configuration precedence and actual Host loading are verified separately. `mcp-config --stable` follows the active generation while retaining fixed state and policy. MALTS 2.1.0 provides four-Host reviewed entry changes, layer fingerprints, protected preimages and original-operation recovery without recreating project state; native scope and actual Host loading remain separate. See [MCP configuration](MCP_CONFIGURATION.md#selected-project-configuration) for commands and limits.
