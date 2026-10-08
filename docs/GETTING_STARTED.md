# Getting Started with MALTS

Begin with the product model, choose your Host/source, review installation, then start or continue the project. The established onboarding sequence remains stable.

## 1. Understand the Model

MALTS preserves goals, current progress, evidence and recovery across finite project work. Single Agent is the normal path; collaboration and experience review are selected by actual need. It is one complete product, currently **2.0.0**.

### Initialization Versus Ordinary Entry

New setup establishes a project and first executable Phase. Existing work reads current binding/task state without reinitialization or historical scans.

## 2. Choose an Installation Source

The verified path uses Windows, Python3.11+ and PowerShell; PowerShell7 is recommended. Ensure Codex, Claude Code, OpenCode or DeepSeek Harness already works. Obtain the selected version from the [repository](https://github.com/SssoGin/MALTS). Installation enables discovery; project setup preserves your work.

## 3. Verify the Repository Source

Review remote/ref, VERSION and MALTS_RELEASE.json. Use the exact reviewed 2.0.0 tree; main guide revisions and the original tagged archive can differ while retaining the same version. See [Install](INSTALL.md) for inventory verification.

## 4. Create an Installation Plan

From the repository:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```



Select one or several Hosts. Harness uses the dedicated Plan/Execute procedure in [Install](INSTALL.md); AllIncluded does not select it.

## 5. Review and Execute

Review source, destinations, personal-content treatment, recovery and exact reported hash before applying. Then verify the selected Boot/discovery and Doctor, reload native workflows/MCP and distinguish installation from project adoption.

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
