# Update MALTS

Update the selected MALTS installation while preserving project work and personal configuration. The established update, ownership, diagnosis and recovery sections apply to the whole product.

## Before Updating

Inspect the installed identity, intended source, workspace binding, user edits, relevant writers and pending effects. Preserve recovery materials. The updater does not pull Git and performs no automatic repository selection, automatic ZIP download, provider call or implicit project migration. Current version remains **2.0.0**.

## Repository Update Review

Choose the reviewed repository revision, then create a plan:

```powershell
.\scripts\Update-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```

Choose ClaudeCode, OpenCode, a selected combination or AllIncluded for the first three only. Review source, destinations, ownership, merges, snapshots and postchecks, then execute actual output values:

```powershell
.\scripts\Update-MALTS.ps1 -Apply -PlanPath '<reviewed-plan-path>' -ExpectedPlanHash '<reviewed-plan-sha256>'
```

### DeepSeek Harness Update

Use its existing actual lifecycle and `.dsh` root. For the generic current-user layout:

```powershell
$harnessRoot = Join-Path $env:USERPROFILE '.dsh'
$harnessLifecycle = Join-Path $env:USERPROFILE '.agent-system/deepseek-harness-lifecycle'
$planPath = Join-Path $env:TEMP ('malts-harness-plan-' + [guid]::NewGuid().ToString('N') + '.json')
.\scripts\Invoke-MALTSLifecycle.ps1 `
  -Command Plan -Operation update `
  -RepositoryRoot (Get-Location).Path `
  -LifecycleRoot $harnessLifecycle `
  -ToolRootDeepSeekDesktop $harnessRoot `
  -OutPath $planPath -Apply
```

Plan -Apply saves a plan only. Review its hash, then use the Execute command from [Install](INSTALL.md). Use `-Operation finalize` only for an explicitly reviewed same-version content correction. Harness is not an Install/Update AllIncluded member.

## Version Migration And Collision Handling

An identical installed source can return NO_OP. Different bytes under the same semantic version require the reviewed current-v2 finalize transaction, preserving target snapshots and the exact source binding. Do not patch the generation, delete it first, change VERSION to bypass a collision or rewrite the old publication. A main documentation revision remains distinct from the original v2.0.0 tag/ZIP.

## Optional Offline Archive Update

Verify and safely extract the selected fixed archive, use its ReleaseRoot and the same plan/hash sequence. Harness uses its dedicated generic lifecycle entry. The original archive retains its original documentation; the repository supplies later same-version guide updates. See [Release Archive](RELEASE_ARTIFACT.md).

## User Modifications And Cleanup

| Class | Meaning | Treatment |
|---|---|---|
| U0 | Missing/exactly MALTS-owned | Only planned replacement/removal |
| U1 | Mergeable marked instruction block | Preserve surrounding personal content |
| U2 | Deterministic evidence-backed merge | Validate the recorded merge |
| U3 | User-owned or ambiguous | Preserve pending a specific decision |
| U4 | Sensitive/unsafe conflict | Fail closed |

Do not apply a whole-file replacement merely because an adapter changed. Cleanup is separate from update and assesses ownership, references and recovery. Preserve unknown objects and necessary snapshots.

## Diagnose Before Repair

Use read-only Doctor for all roots sharing the selected lifecycle; diagnose Harness separately. Inspect core trust before choosing a repair source. DoctorRepairPlan prepares a review; Execute uses the reviewed hash. Do not edit journals/locks or change permissions to bypass a failed precondition.

## Update Workspace Controls

Installation does not adopt projects. Before v2 adoption, review current facts, mappings, writers, unknown effects and backups. Adopted workspaces use current task services; preserve binding/source-seals and do not run old Markdown initialization/reorganization writes. Current Core reads/writes Schema69 only; changing a version field is not a development-store migration.

## Recovery

Follow the original transaction and observed recovery decision. Project restoration uses a new epoch and reconciles post-backup work, unknown effects and budget consumption. It revives no old Grant/Host/acceptance or legacy runtime. Cross-user DPAPI restoration, arbitrary-writer exclusion and GUI model cancellation remain uncertified.

## Post-Update Discovery

Managed instructions identify the exact MALTS_BOOT_PATH; use that pointer even if it differs from the instruction-file directory. Reload each selected Host, resolve its exact Boot, run discovery and Doctor, and verify actual native Skills/MCP. Preserve AGENTS.override.md and outside-block content; installation does not create/remove that override. Recheck workspace binding separately. Report version, exact content identity, actual checks, recovery location and unresolved items. See [Lifecycle](LIFECYCLE.md).
