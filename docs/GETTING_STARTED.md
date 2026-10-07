# Getting Started with MALTS

Install MALTS and start a project using the current2.0.0 release. Ordinary users work through Agent workflows; exact controller protocols are in [Operations](V2_PREVIEW_USAGE.md).

## 1. Prepare tools and source

The verified path uses Windows, Python3.11+ and PowerShell; PowerShell7 is recommended. Ensure Codex, Claude Code, OpenCode or DeepSeek Harness already works. Obtain the selected version from the [repository](https://github.com/SssoGin/MALTS). Installation enables discovery; project setup preserves your work.

## 2. Install and verify loading

From the repository:

```powershell
.\scripts\Install-MALTS.ps1 -RepositoryRoot (Get-Location).Path -UseDefaultRoots -Tool Codex
```

Review source, destinations, existing-content treatment and recovery, then substitute actual output values:

```powershell
.\scripts\Install-MALTS.ps1 -Apply -PlanPath '<plan-path>' -ExpectedPlanHash '<plan-sha256>'
```

See [Install](INSTALL.md) for tool/root selection, offline use and entry checks. Reload the Agent tool and verify actual workflow/tool availability, not file existence alone.

## 3. Define a goal with an ending

Example: “Use MALTS for this module migration. Inspect behavior, preserve goals/compatibility, organize stages, implement and verify. Edit this project only and protect data; decide commit/publication separately.”

Select preflight for material ambiguity, project-init for basic multi-turn records and long-project-workspace-init for stages/recovery. Workflows add no delegation, cost or publication permission.

## 4. Establish finite project work

A new long project defines overall goal, first stage, tasks and acceptance. Require phase_ready=true; init/store creation alone is insufficient. Existing projects inspect current progress/tasks/results/uncertainty without reinitialization. Task workflows provide current methods without requiring internal IDs in every user request.

## 5. Execute and assess results

Agents complete scoped work and check actual outputs. Assess original goals, check coverage and remaining limits. File existence, exit and completion labels are insufficient. Preserve useful decisions/checkpoints and create reports/handoffs/reviews by purpose. task-verify CURRENT_EVIDENCE_VALID proves its declared task scope, with business evidence separate.

## 6. Continue after interruption

Request current tasks/checkpoints, preserved results, unsettled effects/executors and exact next work. Reconcile UNKNOWN without blind replay. Recovery retains consumption. Use handoff for a successor. See [Handoff](HANDOFF.md) and [Lifecycle](LIFECYCLE.md).

## 7. Delegate or review when needed

Use scheduling for explicitly authorized separable work; the main Agent integrates/accepts. Corrections, failed checks and useful methods can justify lightweight Growth; material stages/requested reviews can justify retrospectives. No-signal success creates no empty report or global rule.

## 8. Runnable example and further reading

Controllers can run the [isolated file example](V2_PREVIEW_USAGE.md#v2-start) to verify creation/acceptance/backup. It installs/calls no model, proves no general benefit and requires a new directory. It is TASK_ONLY, not complete long setup. See [Usage](USAGE.md), [Overview](SYSTEM_OVERVIEW.md) and [Design](CORE_DESIGN.md).
