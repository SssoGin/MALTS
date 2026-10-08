# Getting Started with MALTS

To begin, select an installed Agent tool and a verified MALTS source, review an installation plan, check native loading, then define a bounded project goal. Current version: **2.0.0**.

## 1. Understand the Model

MALTS preserves goals, current progress, evidence and recovery across finite project work. Single Agent is the normal path; collaboration and experience review are selected by actual need. The current implementation is **2.0.0**.

### Initialization Versus Ordinary Entry

New setup establishes a project and first executable Phase. Existing work reads current binding/task state without reinitialization or historical scans.

## 2. Choose an Installation Source

The verified path uses Windows, Python3.11+ and PowerShell; PowerShell7 is recommended. Ensure Codex, Claude Code, OpenCode or DeepSeek Harness already works. Obtain the selected version from the [repository](https://github.com/SssoGin/MALTS). Installation enables discovery; project setup preserves your work.

## 3. Verify the Repository Source

Review remote/ref, VERSION and MALTS_RELEASE.json. Use the exact reviewed 2.0.0 tree; the current MALTS ZIP identifies its exact source revision and digest in the Release notes, while platform source archives follow their tag. See [Install](INSTALL.md) for inventory verification.

Run the installation entry from the actual reviewed repository root. Keep credentials, project outputs and caches outside that distribution tree. The release identity binds exact user/repository-only inventories, so a modified or incomplete source must be corrected before planning.

For historical reproduction, use the recorded commit or preserved historical reference and its verified package. For current guides, select the qualified current main/version tag and inspect the matching package identity. In either case, version equality alone is not content equality; retain the actual source commit/hash in the installation evidence.

## 4. Create an Installation Plan

From the repository:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```



Select one or several Hosts. Harness uses the dedicated Plan/Execute procedure in [Install](INSTALL.md); AllIncluded does not select it.

## 5. Review and Execute

Review source, destinations, personal-content treatment, recovery and exact reported hash before applying. Then verify the selected Boot/discovery and Doctor, reload native workflows/MCP and distinguish installation from project adoption.

Check that the plan selects the intended lifecycle/tool roots and preserves personal content. Use the reported plan path/hash rather than copy an example's placeholders. Plan creation is preparation; execute is the actual effect. A no-op is appropriate only when identity/content are already identical.

After activation, use the selected tool's MALTS_BOOT_PATH or adjacent Boot to discover the runtime and run Doctor. Reload the Host and inspect actual workflow/tool discovery. Only then start project work; a successfully written adapter file does not establish that the current process loaded it.

## 6. Start a Project

Example: “Use MALTS for this module migration. Inspect behavior, preserve goals/compatibility, organize stages, implement and verify. Edit this project only and protect data; decide commit/publication separately.”

Select preflight for material ambiguity, project-init for basic multi-turn records and long-project-workspace-init for stages/recovery. Workflows add no delegation, cost or publication permission.

## 7. Govern Long Work Explicitly

A new long project defines overall goal, first stage, tasks and acceptance. Require phase_ready=true; init/store creation alone is insufficient. Existing projects inspect current progress/tasks/results/uncertainty without reinitialization. Task workflows provide current methods without requiring internal IDs in every user request.

Agents complete scoped work and check actual outputs. Assess original goals, check coverage and remaining limits. File existence, exit and completion labels are insufficient. Preserve useful decisions/checkpoints and create reports/handoffs/reviews by purpose. task-verify CURRENT_EVIDENCE_VALID proves its declared task scope, with business evidence separate.

Request current tasks/checkpoints, preserved results, unsettled effects/executors and exact next work. Reconcile UNKNOWN without blind replay. Recovery retains consumption. Use handoff for a successor. See [Handoff](HANDOFF.md) and [Lifecycle](LIFECYCLE.md).

Use scheduling for explicitly authorized separable work; the main Agent integrates/accepts. Corrections, failed checks and useful methods can justify lightweight Growth; material stages/requested reviews can justify retrospectives. No-signal success creates no empty report or global rule.

## Next Reading

Controllers can run the [isolated file example](V2_PREVIEW_USAGE.md#v2-start) to verify creation/acceptance/backup. It installs/calls no model, proves no general benefit and requires a new directory. It is TASK_ONLY, not complete long setup. See [Usage](USAGE.md), [Overview](SYSTEM_OVERVIEW.md) and [Design](CORE_DESIGN.md).
